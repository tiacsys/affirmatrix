"""Package assembly and persistence — the four documents, and their seal.

Two steps, deliberately kept apart. :func:`assemble` is pure and total: it
collects a scope, judges it, and — only when the judgement is not blocked —
builds the four document bodies in memory as a :class:`Package`. It never
writes, and it never raises for a blocked scope; a blocked scope's
``Package`` simply carries no documents, which is what makes SEG-SREQ-046
("no part of a package for a blocked scope") true by construction rather
than by a check someone could forget. :func:`persist` is the one place that
writes, through the store's proof-document face; called on a blocked
``Package`` it raises a plain error and writes nothing. That refusal is a
stated stopgap, not the operator-facing refusal type the next slice builds:
this module only has to keep the invariant, not explain it.

Two hashes, two purposes
--------------------------

:func:`~affirmatrix.proof.collect_scope` already calls
:func:`affirmatrix.commitment.design_root` once, with an explicit empty
``metadata``, to mint the scope's own snapshot identifier — a content
fingerprint taken before any package exists. This module calls the same
primitive a **second** time, with real metadata, to seal the package's
design consistency proof. The two calls answer different questions over
overlapping but distinct inputs (the fingerprint folds the whole induced
subgraph, evidence included; the package root folds the design subset alone)
and neither is derivable from the other. Conflating them would let a
scope's evidence — an outcome re-run, a waiver granted — silently reseal a
document whose claim is only ever about the design.

The canonical metadata
--------------------------

The package root's metadata is RFC 8785 canonical JSON over exactly three
fields: ``snapshotId`` (the scope's own minted identifier), ``scope`` (the
requested requirement identifiers, sorted), and ``revision`` (the current
revision the caller judged the scope against). All three are plain strings
or an array of them — nothing here is ever a number — which is what lets
the standard library's own JSON encoder stand in for RFC 8785: sorted keys,
compact separators, and UTF-8 without escaping non-ASCII characters
reproduce RFC 8785's canonical form for object member ordering and for
string, boolean and array values, but *not* for RFC 8785's number
formatting (its section 3.2.2.3) — a limit that is inert only as long as no
numeric field ever joins this payload, and any future one must revisit this
encoding rather than assume it still holds.

The design set
-------------------

A package's design consistency proof is folded over the *design* subset of
its scope — Requirement, TestSpecification and Implementation nodes, and
the Refines, Verifies and Implements edges among them — never the evidence
nodes and edges the same scope also carries. A TestOutcome or a Waiver
never appears in a node manifest, and a Confirms,
Witnesses or Excuses edge never appears among the design edges: the design
consistency proof is a claim about what was designed and how it composes,
answered independently of whether it was ever run.

Iteration-0 backlog item B17.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType

from affirmatrix import commitment, gates, records
from affirmatrix.case import AffirmationStore
from affirmatrix.graph import Graph
from affirmatrix.proof._scope import Scope, collect_scope
from affirmatrix.records import EdgeRecord, NodeRecord

_REQUIREMENT = "Requirement"
_TEST_SPECIFICATION = "TestSpecification"
_IMPLEMENTATION = "Implementation"
_TEST_OUTCOME = "TestOutcome"
_WAIVER = "Waiver"
_REFINES = "Refines"
_VERIFIES = "Verifies"
_IMPLEMENTS = "Implements"
_CONFIRMS = "Confirms"
_EXCUSES = "Excuses"

#: The design node kinds a design consistency proof's node manifest carries
#: — never an evidence kind.
_DESIGN_NODE_KINDS = frozenset({_REQUIREMENT, _TEST_SPECIFICATION, _IMPLEMENTATION})

#: The design edge kinds a design consistency proof's edge list carries —
#: the same set :func:`affirmatrix.taxonomy.propagating_edge_kinds` names.
_DESIGN_EDGE_KINDS = frozenset({_REFINES, _VERIFIES, _IMPLEMENTS})

#: The four document names, matching
#: :data:`affirmatrix.case._layout.PROOF_DOCUMENT_SCHEMAS`.
DESIGN_CONSISTENCY_PROOF = "design_consistency_proof"
EXECUTION_COVERAGE_RECORD = "execution_coverage_record"
COVERAGE_REPORT = "coverage_report"
EVIDENCE_MANIFEST = "evidence_manifest"

_DOCUMENT_NAMES = (
    DESIGN_CONSISTENCY_PROOF,
    EXECUTION_COVERAGE_RECORD,
    COVERAGE_REPORT,
    EVIDENCE_MANIFEST,
)


@dataclass(frozen=True, slots=True)
class Package:
    """One assembly's answer: the scope, its judgement, and its documents.

    ``documents`` is ``None`` exactly when ``coverage_report.blocked`` is
    true — a blocked scope's package carries no part of a package
    (SEG-SREQ-046), never a partial one. When it is not ``None`` it maps each
    of the four document names above to that document's body, ready to
    persist unchanged.
    """

    scope: Scope
    coverage_report: gates.CoverageReport
    documents: Mapping[str, Mapping[str, object]] | None

    def __post_init__(self) -> None:
        if self.documents is not None:
            object.__setattr__(self, "documents", MappingProxyType(dict(self.documents)))


def assemble(
    graph: Graph,
    requested_ids: Iterable[str],
    *,
    snapshot_timestamp: datetime,
    evaluation_date: date,
    current_revision: str,
) -> Package:
    """Collect a scope, judge it, and build its documents — pure, and total.

    :implements: SEG-SREQ-035

    Never writes, and never raises for a blocked scope: a blocked scope's
    ``Package.documents`` is ``None``, and no document body is ever
    constructed for it — the invariant SEG-SREQ-046 asks for, kept by
    never building the thing rather than by building and then discarding it.
    """
    scope = collect_scope(graph, requested_ids, snapshot_timestamp=snapshot_timestamp)
    report = gates.package_gate(
        scope.subgraph, evaluation_date=evaluation_date, current_revision=current_revision
    )
    if report.blocked:
        return Package(scope=scope, coverage_report=report, documents=None)
    documents = {
        DESIGN_CONSISTENCY_PROOF: _design_consistency_proof_document(scope, current_revision),
        EXECUTION_COVERAGE_RECORD: _execution_coverage_record_document(scope, report),
        COVERAGE_REPORT: _coverage_report_document(report),
        EVIDENCE_MANIFEST: _evidence_manifest_document(scope, current_revision),
    }
    return Package(scope=scope, coverage_report=report, documents=documents)


def persist(package: Package, store: AffirmationStore) -> Mapping[str, Path]:
    """Write a ready package's four documents under its snapshot directory.

    :implements: SEG-SREQ-041

    Refuses outright, writing nothing, when ``package.documents`` is
    ``None`` — a plain error, not the operator-facing refusal type a later
    slice adds; this function's only obligation is that a blocked package
    never reaches the store as a file. Generation itself changes nothing
    about the graph or the store's node, edge and review-event streams:
    every document here is written under ``proofs/{snapshot_id}/`` alone.
    """
    if package.documents is None:
        raise ValueError(
            f"scope {sorted(package.scope.requested_ids)!r} is blocked; "
            "no part of a package is written for a blocked scope"
        )
    written = {
        name: store.write_proof_document(package.scope.snapshot_id, name, package.documents[name])
        for name in _DOCUMENT_NAMES
    }
    return MappingProxyType(written)


def _canonical_metadata(*, snapshot_id: str, requested_ids: Iterable[str], revision: str) -> bytes:
    """RFC 8785 canonical JSON over ``{snapshotId, scope, revision}`` — see the module docstring."""
    payload = {"snapshotId": snapshot_id, "scope": sorted(requested_ids), "revision": revision}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _design_nodes(scope: Scope) -> list[NodeRecord]:
    """Every design-kind node in the scope's subgraph, ordered by identifier."""
    return [
        node
        for node in (
            scope.subgraph.node(local_id) for local_id in sorted(scope.subgraph.node_ids())
        )
        if node.kind in _DESIGN_NODE_KINDS
    ]


def _design_edges(scope: Scope) -> list[EdgeRecord]:
    """Every design-kind edge in the scope's subgraph, ordered for determinism."""
    return sorted(
        (edge for edge in scope.subgraph.edges if edge.kind in _DESIGN_EDGE_KINDS),
        key=lambda edge: (edge.kind, edge.from_id, edge.to_id),
    )


def _package_root(scope: Scope, current_revision: str) -> bytes:
    """The package's own sealed root — a second, distinct call to
    :func:`~affirmatrix.commitment.design_root`."""
    metadata = _canonical_metadata(
        snapshot_id=scope.snapshot_id, requested_ids=scope.requested_ids, revision=current_revision
    )
    design_nodes = _design_nodes(scope)
    node_hashes = (commitment.node_hash(node.kind, node.content_hashes) for node in design_nodes)
    edge_tuples = ((edge.from_id, edge.to_id, edge.kind) for edge in _design_edges(scope))
    return commitment.design_root(metadata, node_hashes, edge_tuples)


def _design_consistency_proof_document(scope: Scope, current_revision: str) -> Mapping[str, object]:
    """The design consistency proof: what its own root recomputes from, and the root itself.

    :implements: SEG-SREQ-037

    Self-contained: an auditor holding only this document's fields — never
    the graph that produced them — can sort the node manifest's hashes and
    the design edges' tuples, rebuild the canonical metadata from the three
    fields carried alongside them, and arrive at the same root
    (SEG-SYS-005).
    """
    node_manifest = [
        {
            "id": node.local_id,
            "kind": node.kind,
            "hash": records.hex_digest(commitment.node_hash(node.kind, node.content_hashes)),
        }
        for node in _design_nodes(scope)
    ]
    design_edges = [
        {"from": edge.from_id, "to": edge.to_id, "kind": edge.kind} for edge in _design_edges(scope)
    ]
    return {
        "snapshotId": scope.snapshot_id,
        "scope": sorted(scope.requested_ids),
        "revision": current_revision,
        "nodeManifest": node_manifest,
        "designEdges": design_edges,
        "root": records.hex_digest(_package_root(scope, current_revision)),
    }


def _execution_coverage_record_document(
    scope: Scope, report: gates.CoverageReport
) -> Mapping[str, object]:
    """The execution coverage record: fresh evidence only.

    :implements: SEG-SREQ-040

    A stale outcome — one the gate's own judgement named in
    ``report.stale_outcomes`` — is silently absent here, exactly as it would
    be if it had never been recorded; the coverage report is where staleness
    is named, once, and this document does not repeat the telling. A
    non-passing outcome the report reports validly excused carries its
    waiver's identifier and a copy of the waiver's expiry — kept deliberately
    so a later release check needs no graph walk — the waiver record itself
    remains the single source of truth for that date.
    """
    outcomes: list[dict[str, object]] = []
    for node in (scope.subgraph.node(local_id) for local_id in sorted(scope.subgraph.node_ids())):
        if node.kind != _TEST_OUTCOME or node.local_id in report.stale_outcomes:
            continue
        entry: dict[str, object] = {
            "id": node.local_id,
            "result": node.result.value,
            "revision": node.revision,
            "confirms": _confirmed_specification(scope.subgraph, node.local_id),
        }
        if node.local_id in report.excused_outcomes:
            waiver = _excusing_waiver(scope.subgraph, node.local_id)
            entry["waiver"] = {"id": waiver.local_id, "expiry": waiver.expiry.isoformat()}
        outcomes.append(entry)
    return {"outcomes": outcomes}


def _confirmed_specification(subgraph: Graph, outcome_id: str) -> str:
    """The one specification this in-scope outcome confirms.

    Collection's own hop 3 (see :mod:`affirmatrix.proof._scope`) never adds
    an outcome to a scope except by way of a confirmed, in-scope
    specification, and the induced cut keeps every edge between two members
    — so a confirming edge is always here to find. Nothing in the graph
    forbids a second one, though: no requirement constrains an outcome to
    confirm exactly one specification, so an outcome with more than one
    in-scope confirming edge is refused loudly rather than resolved by
    picking one and silently dropping the rest — the same failure this
    generator exists to avoid.
    """
    targets = sorted(edge.to_id for edge in subgraph.outgoing(outcome_id, _CONFIRMS))
    if not targets:
        raise ValueError(
            f"outcome {outcome_id!r} is in the scope with no confirming specification in "
            "the induced subgraph, which collect_scope's own invariant rules out"
        )
    if len(targets) > 1:
        raise ValueError(
            f"outcome {outcome_id!r} confirms more than one in-scope specification "
            f"({', '.join(map(repr, targets))}); the execution coverage record assumes "
            "one confirmed specification per outcome and refuses the ambiguous case"
        )
    return targets[0]


def _excusing_waiver(subgraph: Graph, outcome_id: str) -> NodeRecord:
    """The Waiver record the coverage report already found excuses this outcome.

    Independently re-walks the same ``Excuses`` edge (Waiver to TestOutcome,
    per ``case/schema/edge-excuses.schema.json``) the gate itself reads,
    rather than reaching into the gate's private predicate — the same
    "arrive at the same reading independently" discipline the gate's own
    waiver seam already keeps toward :mod:`affirmatrix.satisfaction`.
    """
    for edge in subgraph.incoming(outcome_id, _EXCUSES):
        try:
            waiver = subgraph.node(edge.from_id)
        except KeyError:
            continue
        if waiver.kind == _WAIVER:
            return waiver
    raise ValueError(
        f"outcome {outcome_id!r} is reported excused but no waiver record excusing it is "
        "present in the scope, which the coverage report's own finding rules out"
    )


def _coverage_report_document(report: gates.CoverageReport) -> Mapping[str, object]:
    """The coverage report, serialized whole — single-authored, nothing added.

    Every field here is a direct reading of one of ``report``'s own seven
    typed findings or its two derived views; this function states none of
    its own.
    """
    return {
        "unreadyEdges": [
            {"from": edge.from_id, "to": edge.to_id, "kind": edge.kind, "state": edge.state.value}
            for edge in report.unready_edges
        ],
        "coverageGaps": sorted(report.coverage_gaps),
        "staleOutcomes": sorted(report.stale_outcomes),
        "discardedOutcomes": sorted(report.discarded_outcomes),
        "unwaivedOutcomes": sorted(report.unwaived_outcomes),
        "excusedOutcomes": sorted(report.excused_outcomes),
        "designSetEmpty": report.design_set_empty,
        "diagnostics": [
            {
                "severity": diagnostic.severity.value,
                "condition": str(diagnostic.condition),
                "subject": diagnostic.subject,
                "detail": diagnostic.detail,
            }
            for diagnostic in report.diagnostics
        ],
        "blocked": report.blocked,
    }


def _evidence_manifest_document(scope: Scope, current_revision: str) -> Mapping[str, object]:
    """The evidence manifest: the package's scope, its totality, and its siblings.

    :implements: SEG-SREQ-038
    :implements: SEG-SREQ-039

    Scope (SEG-SREQ-038) and the partial-vs-total signal (SEG-SREQ-039) both
    live here, on the package's own binder document, rather than on the
    coverage report: both are stated over the package as a whole, and the
    coverage report's seven fields are exactly, and only, the gate's own
    findings. The single ``revision`` is the one source revision a
    single-repository layout has, where a multi-repository layout would
    anchor one per repository.
    """
    return {
        "snapshotId": scope.snapshot_id,
        "requestedScope": sorted(scope.requested_ids),
        "memberScope": sorted(scope.member_ids),
        "total": scope.total,
        "revision": current_revision,
        "designConsistencyProof": f"{DESIGN_CONSISTENCY_PROOF}.jsonld",
        "executionCoverageRecord": f"{EXECUTION_COVERAGE_RECORD}.jsonld",
        "coverageReport": f"{COVERAGE_REPORT}.jsonld",
    }


__all__ = [
    "COVERAGE_REPORT",
    "DESIGN_CONSISTENCY_PROOF",
    "EVIDENCE_MANIFEST",
    "EXECUTION_COVERAGE_RECORD",
    "Package",
    "assemble",
    "persist",
]
