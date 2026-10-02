"""Package assembly and persistence — the four documents, and their seal.

Two steps, deliberately kept apart. :func:`check_readiness` collects a scope
and judges it — a blocked judgement is returned, never raised, though a
scope that cannot be collected at all still raises from collection —
returning both to a caller who wants the judgement without committing to
generate. :func:`assemble` composes
``check_readiness`` and, when the judgement is not blocked, builds the four
document bodies in memory as a :class:`Package` — always a complete package,
never a partial one. When the judgement *is* blocked, ``assemble`` raises
:class:`GenerationRefused` at that one point, before any document body is
built: no part of a package comes into existence in memory (SEG-SREQ-046's
first half), and because :func:`persist` is never reached, none comes into
existence on disk either (its second half) — not even the snapshot
directory a first write would otherwise create. :func:`persist` is the one
place that writes, through the store's proof-document face; it never checks
for a blocked judgement, because a ``Package`` cannot represent one.

Refusal and error are different kinds of stop, and the distinction is
structural, not a matter of message wording: :class:`GenerationRefused` is
raised exactly once, exactly when the gate's own report says a scope is
blocked (SEG-SREQ-048) — the gate's verdict, acted on. An absent or
non-Requirement requested identifier, or an outcome confirming more than
one in-scope specification, are inputs this generator cannot even judge;
they raise their own distinct types, from :func:`~affirmatrix.proof.collect_scope`
and this module's own document builders respectively, and neither is ever
mistaken for the other — a caller catching one never catches the other by
accident, because neither shares a base beyond ``Exception``.

Two hashes, two purposes
--------------------------

:func:`~affirmatrix.proof.collect_scope` already calls
:func:`affirmatrix.commitment.design_root` once, with an explicit empty
``metadata``, to mint the scope's own snapshot identifier — a timestamp
joined to a content fingerprint taken before any package exists. This module
calls the same primitive a **second** time, with real metadata, to seal the
package's design consistency proof. The two calls answer different questions
over overlapping but distinct inputs (the fingerprint folds the whole induced
subgraph, evidence included; the package root folds the design subset alone)
and neither is derivable from the other. Conflating them would let a
scope's evidence — an outcome re-run, a waiver granted — silently reseal a
document whose claim is only ever about the design.

The snapshot identifier therefore names a package and binds nothing: the
design consistency proof carries it so a reader can locate the package, but
it is not an input to the package root. Two packages over the same design
set, scope and revision carry the same root, whatever instant they were
generated at and whatever evidence the scope carried.

The canonical metadata
--------------------------

The package root's metadata is RFC 8785 canonical JSON over exactly two
fields: ``scope`` (the requested requirement identifiers, sorted) and
``revision`` (the current revision the caller judged the scope against).
Both are plain strings or an array of them — nothing here is ever a
number — which is what lets
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


class GenerationRefused(Exception):
    """The proof gate reported the requested scope blocked; there is no package for it.

    :implements: SEG-SREQ-047

    Carries the judgement as two typed attributes, not only in the message,
    so a caller can render every diagnostic rather than parse a string:
    ``scope`` (the collected :class:`~affirmatrix.proof.Scope` — its
    snapshot id and the requested and member identifiers it was collected
    for) and ``coverage_report`` (the gate's own
    :class:`~affirmatrix.gates.CoverageReport`, unchanged). Named without
    the ``Error`` suffix every other refusal in this codebase carries,
    deliberately: this is the gate's own verdict acted on, not an input the
    generator failed to make sense of, and the two are never to be confused
    for one another (SEG-SREQ-048).
    """

    def __init__(self, scope: Scope, coverage_report: gates.CoverageReport) -> None:
        blocking = sum(1 for d in coverage_report.diagnostics if d.severity.blocks_package)
        super().__init__(
            f"scope {sorted(scope.requested_ids)!r} (snapshot {scope.snapshot_id!r}) is "
            f"blocked: {blocking} blocking finding(s)"
        )
        self.scope = scope
        self.coverage_report = coverage_report


@dataclass(frozen=True, slots=True)
class Package:
    """One assembly's answer: the scope, its judgement, and its documents.

    Always complete — a ``Package`` only ever exists for a scope
    :func:`assemble` did not refuse, so ``documents`` maps every one of the
    four document names above to that document's body, ready to persist
    unchanged. There is no partial ``Package``: a blocked scope never
    produces one at all (see :class:`GenerationRefused`).
    """

    scope: Scope
    coverage_report: gates.CoverageReport
    documents: Mapping[str, Mapping[str, object]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "documents", MappingProxyType(dict(self.documents)))


def check_readiness(
    graph: Graph,
    requested_ids: Iterable[str],
    *,
    snapshot_timestamp: datetime,
    evaluation_date: date,
    current_revision: str,
) -> tuple[Scope, gates.CoverageReport]:
    """Collect a scope and judge it — a blocked judgement is returned, never raised.

    For a caller who wants the judgement without committing to generate:
    :func:`assemble` composes exactly this call and then decides what to do
    with the result. Raises whatever :func:`~affirmatrix.proof.collect_scope`
    raises for a requested scope it cannot collect; otherwise always
    returns, blocked or not.
    """
    scope = collect_scope(graph, requested_ids, snapshot_timestamp=snapshot_timestamp)
    report = gates.package_gate(
        scope.subgraph, evaluation_date=evaluation_date, current_revision=current_revision
    )
    return scope, report


def assemble(
    graph: Graph,
    requested_ids: Iterable[str],
    *,
    snapshot_timestamp: datetime,
    evaluation_date: date,
    current_revision: str,
    evidence_bundles: Mapping[str, str] | None = None,
) -> Package:
    """Collect a scope, judge it, and build its documents — or refuse.

    :implements: SEG-SREQ-035
    :implements: SEG-SREQ-046
    :implements: SEG-SREQ-048
    :implements: SEG-SREQ-226

    ``evidence_bundles`` maps the identifier of a test outcome to the digest
    of the run bundle that supplied it. The manifest records the digest of
    every bundle that supplied an outcome in the scope, an outcome the gate
    set aside as stale included. Nothing here binds the digests to the design
    root. Without the mapping the manifest records no digest.

    Composes :func:`check_readiness`. When the judgement is blocked, raises
    :class:`GenerationRefused` at this one point, before any document body
    is built — the whole of SEG-SREQ-046's first half, and SEG-SREQ-048's
    boundary: this is the only place a scope is ever refused, and it is
    refused if and only if the gate's own report says it is blocked.
    """
    scope, report = check_readiness(
        graph,
        requested_ids,
        snapshot_timestamp=snapshot_timestamp,
        evaluation_date=evaluation_date,
        current_revision=current_revision,
    )
    if report.blocked:
        raise GenerationRefused(scope, report)
    documents = {
        DESIGN_CONSISTENCY_PROOF: _design_consistency_proof_document(scope, current_revision),
        EXECUTION_COVERAGE_RECORD: execution_coverage_record_document(scope, report),
        COVERAGE_REPORT: coverage_report_document(report),
        EVIDENCE_MANIFEST: _evidence_manifest_document(
            scope, current_revision, evidence_bundles or {}
        ),
    }
    return Package(scope=scope, coverage_report=report, documents=documents)


def persist(package: Package, store: AffirmationStore) -> Mapping[str, Path]:
    """Write a package's four documents under its snapshot directory.

    :implements: SEG-SREQ-041

    A straight-line write: a ``Package`` is always complete, so there is
    nothing here to check before writing it. SEG-SREQ-046's second half —
    nothing on disk for a blocked scope, not even the snapshot directory a
    first write would otherwise create — holds because this function is
    never reached for one: :func:`assemble` already refused before
    returning. Generation itself changes nothing about the graph or the
    store's node, edge and review-event streams: every document here is
    written under ``proofs/{snapshot_id}/`` alone.
    """
    return MappingProxyType(
        {
            name: store.write_proof_document(
                package.scope.snapshot_id, name, package.documents[name]
            )
            for name in _DOCUMENT_NAMES
        }
    )


def _canonical_metadata(*, requested_ids: Iterable[str], revision: str) -> bytes:
    """RFC 8785 canonical JSON over ``{scope, revision}`` — see the module docstring."""
    payload = {"revision": revision, "scope": sorted(requested_ids)}
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


def sealed_root(
    *,
    requested_ids: Iterable[str],
    revision: str,
    node_hashes: Iterable[bytes],
    edges: Iterable[tuple[str, str, str]],
) -> bytes:
    """The root of a design consistency proof, from the fields the proof itself records.

    The one place the canonical metadata meets the commitment layer's root
    primitive. The generator seals a package with it, and the verifier
    recomputes the root with it from a stored package, so the two cannot
    drift apart.
    """
    metadata = _canonical_metadata(requested_ids=requested_ids, revision=revision)
    return commitment.design_root(metadata, node_hashes, edges)


def _package_root(scope: Scope, current_revision: str) -> bytes:
    """The package's own sealed root — a second, distinct call to
    :func:`~affirmatrix.commitment.design_root`."""
    return sealed_root(
        requested_ids=scope.requested_ids,
        revision=current_revision,
        node_hashes=(
            commitment.node_hash(node.kind, node.content_hashes) for node in _design_nodes(scope)
        ),
        edges=((edge.from_id, edge.to_id, edge.kind) for edge in _design_edges(scope)),
    )


def _design_consistency_proof_document(scope: Scope, current_revision: str) -> Mapping[str, object]:
    """The design consistency proof: what its own root recomputes from, and the root itself.

    :implements: SEG-SREQ-037

    Self-contained: an auditor holding only this document's fields — never
    the graph that produced them — can sort the node manifest's hashes and
    the design edges' tuples, rebuild the canonical metadata from the two
    fields (``scope`` and ``revision``) carried alongside them, and arrive at
    the same root (SEG-SYS-005). The ``snapshotId`` field names the package
    so a reader can locate it and is not part of that recomputation: two
    packages over the same design set, scope and revision carry the same
    root, whatever instant they were generated at and whatever evidence the
    scope carried.
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


def execution_coverage_record_document(
    scope: Scope, report: gates.CoverageReport
) -> Mapping[str, object]:
    """The execution coverage record: fresh evidence only.

    :implements: SEG-SREQ-040

    A stale outcome — one the gate's own judgement named in
    ``report.stale_outcomes`` — is silently absent here, exactly as it would
    be if it had never been recorded; the coverage report is where staleness
    is named, once, and this document does not repeat the telling. A
    failing outcome the report reports validly excused carries its
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


def coverage_report_document(report: gates.CoverageReport) -> Mapping[str, object]:
    """The coverage report, serialized whole — single-authored, nothing added.

    Every field here is a direct reading of one of ``report``'s own eight
    typed findings or its two derived views; this function states none of
    its own. Public, and the one serialization site: a package's own
    ``coverage_report.jsonld`` document and the command line's machine
    readable rendering of the gate's verdict are both exactly this.
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
        "skippedOutcomes": sorted(report.skipped_outcomes),
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


def _evidence_manifest_document(
    scope: Scope, current_revision: str, evidence_bundles: Mapping[str, str]
) -> Mapping[str, object]:
    """The evidence manifest: the package's scope, its totality, and its siblings.

    :implements: SEG-SREQ-038
    :implements: SEG-SREQ-039

    Scope (SEG-SREQ-038) and the partial-vs-total signal (SEG-SREQ-039) both
    live here, on the package's own binder document, rather than on the
    coverage report: both are stated over the package as a whole, and the
    coverage report's eight typed findings are exactly, and only, the gate's own
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
        "runBundles": sorted(
            {
                digest
                for outcome_id, digest in evidence_bundles.items()
                if outcome_id in scope.member_ids
            }
        ),
    }


__all__ = [
    "COVERAGE_REPORT",
    "DESIGN_CONSISTENCY_PROOF",
    "EVIDENCE_MANIFEST",
    "EXECUTION_COVERAGE_RECORD",
    "GenerationRefused",
    "Package",
    "assemble",
    "check_readiness",
    "coverage_report_document",
    "execution_coverage_record_document",
    "persist",
    "sealed_root",
]
