"""The proof verifier — an evidence package, checked.

A package is sealed by its design root alone. The other three documents are
not sealed, and a package handed to an assessor comes without its case, its run
bundles and the readers that made it. So the verifier makes a fixed list of
named checks (:data:`CHECK_NAMES`), and each one reports one of four statuses.

* ``passed`` and ``failed`` are verdicts.
* ``not judged`` means the operator asked for the check and the verifier could
  not reach a verdict, because an input it needs is missing or does not match.
* ``not made`` means the operator did not ask, so nothing was tried.

Three groups of checks, by what they need:

* **The package alone:** ``root``, ``identity``, ``agreement``, ``unblocked``.
  They are always made, with no configuration, no case and no run bundle.
* **The case:** ``affirmations``, made when a case is given.
* **The run bundles:** ``bundle-digests``, ``design-guard``, ``rebuilt-evidence``
  and ``snapshot-id``, made when run bundles are given. The evidence is rebuilt
  only when the bundles are the ones the package lists and the readers of the
  configuration supply the design the package records. Without both, the
  rebuild does not run, and the two checks that need it are ``not judged``. The
  rebuild takes the design edges of the package as affirmed, because the
  affirmations are the case's to show. The ``affirmations`` check shows them.

``sibling-digests`` is always ``not made``: a package records no digest of its
sibling documents, so nothing can be checked against one.

The verifier judges a package at the revision the package records. It reads no
repository, takes no current revision, and writes nothing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from affirmatrix import commitment, gates, graph, records
from affirmatrix.case import AffirmationStore
from affirmatrix.config import Config
from affirmatrix.diagnostics import Severity
from affirmatrix.proof import _package
from affirmatrix.proof._scope import ScopeError, collect_scope
from affirmatrix.proof._stored import StoredPackage, read_package
from affirmatrix.records import EdgeRecord, LinkState, RecordSource
from affirmatrix.sources import composed
from affirmatrix.sources.outcomes import bundle_digest

#: Every check the verifier reports, in the order it reports them.
CHECK_NAMES = (
    "root",
    "identity",
    "agreement",
    "unblocked",
    "affirmations",
    "bundle-digests",
    "design-guard",
    "rebuilt-evidence",
    "snapshot-id",
    "sibling-digests",
)

_BUNDLE_CHECKS = ("bundle-digests", "design-guard", "rebuilt-evidence", "snapshot-id")
_LISTED_LIMIT = 5
_EDGE_SUBJECT = re.compile(r"^(?P<from>.+) -> (?P<to>.+) \((?P<kind>[A-Za-z]+)\)$")
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


class CheckStatus(StrEnum):
    """What one check found. The values are the words the reports print."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_JUDGED = "not judged"
    NOT_MADE = "not made"


@dataclass(frozen=True, slots=True)
class Check:
    """One named check, its status, and the detail that names the subject."""

    name: str
    status: CheckStatus
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Verification:
    """All ten checks of one package, in the order of :data:`CHECK_NAMES`."""

    snapshot_id: str
    checks: tuple[Check, ...]

    def status_of(self, name: str) -> CheckStatus:
        """The status of the check with this name."""
        return next(check.status for check in self.checks if check.name == name)

    @property
    def failed(self) -> bool:
        """Whether any check failed."""
        return any(check.status is CheckStatus.FAILED for check in self.checks)

    @property
    def unjudged(self) -> bool:
        """Whether any check was asked for and could not be judged."""
        return any(check.status is CheckStatus.NOT_JUDGED for check in self.checks)

    def as_document(self) -> Mapping[str, object]:
        """The report as the machine-readable output of ``proof verify``."""
        return {
            "snapshotId": self.snapshot_id,
            "checks": [
                {"name": check.name, "status": str(check.status), "detail": check.detail}
                for check in self.checks
            ],
        }


def verify(
    package: Path,
    *,
    config: Config | None = None,
    bundles: Sequence[Path] = (),
    case: AffirmationStore | None = None,
) -> Verification:
    """Check the evidence package in a directory, and report every check by name.

    :implements: SEG-SREQ-236

    ``package`` is the directory of a package. ``bundles`` are the run bundles
    the operator names; without any, the four bundle checks are not made.
    ``config`` supplies the readers for the design guard and the rebuild, and
    ``case`` supplies the review events for the affirmations check; a check
    that needs a missing one is not made, or not judged when it was asked for.

    A package that reads but fails a check is a report, never an exception.
    Raises :class:`~affirmatrix.case.AffirmationStoreError` for a package that
    cannot be read, and the source adapters' own errors for a run bundle or a
    reader that cannot be read.
    """
    stored = read_package(package)
    results = {
        "root": _check_root(stored),
        "identity": _check_identity(stored, package),
        "agreement": _check_agreement(stored),
        "unblocked": _check_unblocked(stored),
        "affirmations": _check_affirmations(stored, case),
        **_bundle_checks(stored, config, bundles),
        "sibling-digests": Check(
            "sibling-digests",
            CheckStatus.NOT_MADE,
            "the package records no digest of a sibling document",
        ),
    }
    return Verification(
        snapshot_id=str(stored.design["snapshotId"]),
        checks=tuple(results[name] for name in CHECK_NAMES),
    )


def _check_root(stored: StoredPackage) -> Check:
    """Recompute the design root from the design consistency proof alone.

    :implements: SEG-SREQ-237
    """
    design = stored.design
    recomputed = records.hex_digest(
        _package.sealed_root(
            requested_ids=design["scope"],
            revision=design["revision"],
            node_hashes=(records.digest_from_hex(node["hash"]) for node in design["nodeManifest"]),
            edges=((edge["from"], edge["to"], edge["kind"]) for edge in design["designEdges"]),
        )
    )
    if recomputed == design["root"]:
        return Check("root", CheckStatus.PASSED, f"the recorded root is {recomputed}")
    return Check(
        "root",
        CheckStatus.FAILED,
        f"the design recomputes to {recomputed}, and the package records {design['root']}",
    )


def _check_identity(stored: StoredPackage, directory: Path) -> Check:
    """The documents, and the directory, name one package.

    :implements: SEG-SREQ-238
    :implements: SEG-SREQ-264
    """
    design, manifest = stored.design, stored.manifest
    problems = []
    if design["snapshotId"] != manifest["snapshotId"]:
        problems.append(
            f"the snapshot is {design['snapshotId']} in the design consistency proof "
            f"and {manifest['snapshotId']} in the evidence manifest"
        )
    if sorted(design["scope"]) != sorted(manifest["requestedScope"]):
        problems.append("the requested scope differs between the two documents")
    if design["revision"] != manifest["revision"]:
        problems.append(
            f"the revision is {design['revision']} in the design consistency proof "
            f"and {manifest['revision']} in the evidence manifest"
        )
    name = directory.resolve().name
    if name != design["snapshotId"]:
        problems.append(
            f"the snapshot identifier is {design['snapshotId']} and the directory is named {name}"
        )
    if problems:
        return Check("identity", CheckStatus.FAILED, _joined(problems))
    return Check(
        "identity",
        CheckStatus.PASSED,
        f"the documents and the directory name the snapshot {name}",
    )


def _check_agreement(stored: StoredPackage) -> Check:
    """The documents agree on the evidence: members, set-aside outcomes, freshness.

    :implements: SEG-SREQ-239
    :implements: SEG-SREQ-265
    :implements: SEG-SREQ-266
    :implements: SEG-SREQ-267
    """
    design, record, report = stored.design, stored.record, stored.report
    member = frozenset(stored.manifest["memberScope"])
    held = {outcome["id"]: outcome for outcome in record["outcomes"]}
    waivers = {outcome["waiver"]["id"] for outcome in held.values() if "waiver" in outcome}
    named_outcomes = set(held) | _reported_outcomes(report)
    problems = []

    names = [
        *named_outcomes,
        *(outcome["confirms"] for outcome in held.values()),
        *waivers,
        *report["coverageGaps"],
        *(end for edge in report["unreadyEdges"] for end in (edge["from"], edge["to"])),
        *(name for finding in report["diagnostics"] for name in _subject_names(finding["subject"])),
    ]
    strangers = sorted(set(names) - member)
    if strangers:
        problems.append(f"names that are no member of the scope: {_listed(strangers)}")

    skipped = {name for name, outcome in held.items() if outcome["result"] == "skipped"}
    excused = {name for name, outcome in held.items() if "waiver" in outcome}
    # A package sealed before the report listed skips carries no such list: no skip is judged.
    if "skippedOutcomes" in report and skipped != set(report["skippedOutcomes"]):
        problems.append(
            "the record and the report differ on the skipped outcomes: "
            f"{_listed(sorted(skipped ^ set(report['skippedOutcomes'])))}"
        )
    if excused != set(report["excusedOutcomes"]):
        problems.append(
            "the record and the report differ on the excused outcomes: "
            f"{_listed(sorted(excused ^ set(report['excusedOutcomes'])))}"
        )
    set_aside = sorted(set(held) & set(report["staleOutcomes"]))
    if set_aside:
        problems.append(
            f"outcomes that the record holds and the report sets aside: {_listed(set_aside)}"
        )
    other = sorted(
        name for name, outcome in held.items() if outcome["revision"] != design["revision"]
    )
    if other:
        problems.append(f"outcomes of another revision than the package: {_listed(other)}")

    expected = {node["id"] for node in design["nodeManifest"]} | named_outcomes | waivers
    if member != expected:
        too_much, too_little = sorted(member - expected), sorted(expected - member)
        problems.append(
            "the member scope is not what the documents name; "
            f"too much: {_listed(too_much)}; too little: {_listed(too_little)}"
        )
    if problems:
        return Check("agreement", CheckStatus.FAILED, _joined(problems))
    return Check(
        "agreement", CheckStatus.PASSED, "the documents agree on the members and the evidence"
    )


def _reported_outcomes(report: Mapping[str, object]) -> set[str]:
    """Every outcome the coverage report names, whatever the finding."""
    keys = (
        "staleOutcomes",
        "discardedOutcomes",
        "unwaivedOutcomes",
        "excusedOutcomes",
        "skippedOutcomes",
    )
    return {name for key in keys for name in report.get(key, ())}


def _subject_names(subject: str) -> list[str]:
    """The names a diagnostic's subject holds: one name, or the two ends of an edge."""
    edge = _EDGE_SUBJECT.match(subject)
    return [edge["from"], edge["to"]] if edge else [subject]


def _check_unblocked(stored: StoredPackage) -> Check:
    """The report records an unblocked scope, with no unready edge and no blocking finding.

    :implements: SEG-SREQ-240
    :implements: SEG-SREQ-268
    :implements: SEG-SREQ-269
    """
    report = stored.report
    problems = []
    if report["blocked"]:
        problems.append("the report records the scope as blocked")
    unready = [f"{e['from']} -> {e['to']} ({e['kind']})" for e in report["unreadyEdges"]]
    if unready:
        problems.append(f"the report lists unready edges: {_listed(unready)}")
    blocking = [
        f"{finding['condition']} ({finding['subject']})"
        for finding in report["diagnostics"]
        if Severity(finding["severity"]).blocks_package
    ]
    if blocking:
        problems.append(f"the report holds findings that block: {_listed(blocking)}")
    if problems:
        return Check("unblocked", CheckStatus.FAILED, _joined(problems))
    return Check("unblocked", CheckStatus.PASSED, "the report records the scope as not blocked")


def _check_affirmations(stored: StoredPackage, case: AffirmationStore | None) -> Check:
    """The case holds a review event that binds each design edge to the recorded node hashes.

    :implements: SEG-SREQ-241

    A review event binds an edge when the node hash of each end, derived from
    the content hashes the event holds, equals the node hash the package
    records for that end. The edge needs one such event. An older event for the
    same edge, made against other content, does not count against it. The check
    asks whether these hashes were ever affirmed, and the store has no event
    that revokes an affirmation, so one binding event is enough.
    """
    if case is None:
        return Check(
            "affirmations", CheckStatus.NOT_MADE, "the check needs a case, and none is given"
        )
    kinds = {node["id"]: node["kind"] for node in stored.design["nodeManifest"]}
    recorded = {node["id"]: node["hash"] for node in stored.design["nodeManifest"]}
    events: dict[tuple[str, str, str], list[records.ReviewEvent]] = {}
    for event in case.review_events():
        events.setdefault((event.kind, event.from_id, event.to_id), []).append(event)

    def binds(event: records.ReviewEvent, edge: Mapping[str, str]) -> bool:
        ends = (
            (edge["from"], event.from_content_anchors),
            (edge["to"], event.to_content_anchors),
        )
        return all(
            identifier in recorded
            and records.hex_digest(
                commitment.node_hash(
                    kinds[identifier], {name: anchor.digest for name, anchor in anchors.items()}
                )
            )
            == recorded[identifier]
            for identifier, anchors in ends
        )

    edges = stored.design["designEdges"]
    unbound = []
    for edge in edges:
        held = events.get((edge["kind"], edge["from"], edge["to"]), [])
        label = f"{edge['from']} -> {edge['to']} ({edge['kind']})"
        if not held:
            unbound.append(f"{label}: the case holds no review event")
        elif not any(binds(event, edge) for event in held):
            unbound.append(f"{label}: no review event binds the node hashes the package records")
    if unbound:
        return Check(
            "affirmations",
            CheckStatus.FAILED,
            f"{len(unbound)} of {len(edges)} design edges are not bound: {_listed(unbound)}",
        )
    return Check(
        "affirmations",
        CheckStatus.PASSED,
        f"{len(edges)} of {len(edges)} design edges are bound by a review event of the case",
    )


def _bundle_checks(
    stored: StoredPackage, config: Config | None, bundles: Sequence[Path]
) -> dict[str, Check]:
    """The four checks that need run bundles; each one is not made when none is given."""
    if not bundles:
        return {
            name: Check(
                name, CheckStatus.NOT_MADE, "the check needs run bundles, and none is given"
            )
            for name in _BUNDLE_CHECKS
        }
    digests = _check_bundle_digests(stored, bundles)
    guard = _check_design_guard(stored, config)
    if digests.status is CheckStatus.PASSED and guard.status is CheckStatus.PASSED:
        rebuilt, snapshot = _rebuild(stored, config, bundles)
    else:
        reason = (
            "the run bundles are not the listed ones"
            if digests.status is not CheckStatus.PASSED
            else "the readers do not supply the design of the package"
        )
        rebuilt = Check("rebuilt-evidence", CheckStatus.NOT_JUDGED, f"not rebuilt: {reason}")
        snapshot = Check("snapshot-id", CheckStatus.NOT_JUDGED, f"not rebuilt: {reason}")
    return {
        "bundle-digests": digests,
        "design-guard": guard,
        "rebuilt-evidence": rebuilt,
        "snapshot-id": snapshot,
    }


def _check_bundle_digests(stored: StoredPackage, bundles: Sequence[Path]) -> Check:
    """The digests of the given run bundles are the digests the package lists.

    :implements: SEG-SREQ-242
    :implements: SEG-SREQ-243

    A bundle the package does not list is a mismatch, and a mismatch outranks
    a listed bundle that is not given: a different bundle is a different claim.
    """
    listed = set(stored.manifest.get("runBundles", ()))
    given = {bundle_digest(bundle): bundle for bundle in bundles}
    unlisted = sorted(set(given) - listed)
    if unlisted:
        names = [f"{digest} ({given[digest]})" for digest in unlisted]
        suffix = "" if listed else "; the package lists no digest"
        return Check(
            "bundle-digests",
            CheckStatus.FAILED,
            f"the package does not list: {_listed(names)}{suffix}",
        )
    missing = sorted(listed - set(given))
    if missing:
        return Check(
            "bundle-digests",
            CheckStatus.NOT_JUDGED,
            f"the package lists run bundles that are not given: {_listed(missing)}",
        )
    return Check(
        "bundle-digests", CheckStatus.PASSED, f"all {len(listed)} listed run bundles are given"
    )


def _check_design_guard(stored: StoredPackage, config: Config | None) -> Check:
    """The readers of the configuration supply the design the package records.

    :implements: SEG-SREQ-244

    Each node of the package needs the same node hash from the readers, and
    each design edge of the package needs to come from them. A change of
    requirement text since the package was made is a mismatch too. The check
    reads the configured sources by hash and runs no git command. It builds no
    evidence: it needs no run bundle.
    """
    if config is None:
        return Check("design-guard", CheckStatus.NOT_JUDGED, "no configuration is given")
    built = graph.build(composed.from_config(config))
    problems = []
    for node in stored.design["nodeManifest"]:
        try:
            supplied = built.node(node["id"])
        except KeyError:
            problems.append(f"{node['id']}: no reader supplies it")
            continue
        found = records.hex_digest(commitment.node_hash(supplied.kind, supplied.content_hashes))
        if supplied.kind != node["kind"] or found != node["hash"]:
            problems.append(f"{node['id']}: the readers supply another node hash than the package")
    held = {(edge.from_id, edge.to_id, edge.kind) for edge in built.edges}
    for edge in stored.design["designEdges"]:
        if (edge["from"], edge["to"], edge["kind"]) not in held:
            problems.append(
                f"{edge['from']} -> {edge['to']} ({edge['kind']}): no reader supplies it"
            )
    if problems:
        return Check(
            "design-guard",
            CheckStatus.NOT_JUDGED,
            f"the readers do not supply the design of the package: {_listed(problems)}",
        )
    return Check("design-guard", CheckStatus.PASSED, "the readers supply the design of the package")


@dataclass(frozen=True, slots=True)
class _AffirmedDesign:
    """A record source that gives the design edges of a package the state active.

    A package exists only for a scope the gate found ready, so each of its
    design edges was affirmed. The edge hash is made from the node hashes the
    package records. Every other edge passes through as the source supplies it.
    """

    source: RecordSource
    affirmed: Mapping[tuple[str, str, str], bytes]

    def nodes(self) -> Iterator[records.NodeRecord]:
        return self.source.nodes()

    def edges(self) -> Iterator[EdgeRecord]:
        for edge in self.source.edges():
            digest = self.affirmed.get((edge.from_id, edge.to_id, edge.kind))
            if digest is None:
                yield edge
            else:
                yield EdgeRecord(
                    from_id=edge.from_id,
                    to_id=edge.to_id,
                    kind=edge.kind,
                    state=LinkState.ACTIVE,
                    edge_hash=digest,
                )


def _rebuild(
    stored: StoredPackage, config: Config | None, bundles: Sequence[Path]
) -> tuple[Check, Check]:
    """Rebuild the evidence from the run bundles and compare it with the record.

    :implements: SEG-SREQ-245
    :implements: SEG-SREQ-246

    The rebuild judges at the revision the package records, and at the date
    of the snapshot timestamp that the recorded identifier carries. It takes
    the design edges of the package as affirmed. The snapshot identifier is
    minted again from the rebuilt scope with the same timestamp.
    """
    design = stored.design
    recorded_id = str(design["snapshotId"])
    try:
        timestamp = datetime.strptime(recorded_id.split("-")[0], _TIMESTAMP_FORMAT).replace(
            tzinfo=UTC
        )
    except ValueError:
        return (
            Check(
                "rebuilt-evidence",
                CheckStatus.NOT_JUDGED,
                f"the identifier {recorded_id} carries no timestamp, so no date to judge at",
            ),
            Check(
                "snapshot-id",
                CheckStatus.FAILED,
                f"the identifier {recorded_id} is not one that the tool mints",
            ),
        )
    assert config is not None  # the design guard passed, so a configuration was given
    hashes = {node["id"]: records.digest_from_hex(node["hash"]) for node in design["nodeManifest"]}
    affirmed = {
        (edge["from"], edge["to"], edge["kind"]): commitment.edge_hash(
            edge["from"], edge["to"], edge["kind"], hashes[edge["from"]], hashes[edge["to"]]
        )
        for edge in design["designEdges"]
    }
    rebuilt_graph = graph.build(
        _AffirmedDesign(composed.from_config(config, bundles=bundles), affirmed)
    )
    try:
        scope = collect_scope(rebuilt_graph, design["scope"], snapshot_timestamp=timestamp)
        report = gates.package_gate(
            scope.subgraph, evaluation_date=timestamp.date(), current_revision=design["revision"]
        )
        record_document = _package.execution_coverage_record_document(scope, report)
    except (ScopeError, ValueError) as error:
        reason = f"the rebuild is not possible: {error}"
        return (
            Check("rebuilt-evidence", CheckStatus.NOT_JUDGED, reason),
            Check("snapshot-id", CheckStatus.NOT_JUDGED, reason),
        )
    differing = [
        label
        for label, rebuilt, recorded in (
            ("execution coverage record", record_document, stored.record),
            ("coverage report", _package.coverage_report_document(report), stored.report),
        )
        if _plain(rebuilt) != _plain(recorded)
    ]
    if differing:
        evidence = Check(
            "rebuilt-evidence",
            CheckStatus.FAILED,
            f"the rebuilt {' and the rebuilt '.join(differing)} differ from the recorded ones",
        )
    else:
        evidence = Check(
            "rebuilt-evidence",
            CheckStatus.PASSED,
            "the outcomes and findings rebuilt from the run bundles equal the recorded ones",
        )
    if scope.snapshot_id == recorded_id:
        snapshot = Check(
            "snapshot-id", CheckStatus.PASSED, f"the rebuilt scope mints the snapshot {recorded_id}"
        )
    else:
        snapshot = Check(
            "snapshot-id",
            CheckStatus.FAILED,
            f"the rebuilt scope mints {scope.snapshot_id}, and the package records {recorded_id}",
        )
    return evidence, snapshot


def _plain(document: Mapping[str, object]) -> object:
    """A document as plain JSON values, so that two spellings of one value compare equal."""
    return json.loads(json.dumps(document))


def _listed(names: Sequence[str]) -> str:
    """The first few names, and how many more there are."""
    shown = ", ".join(names[:_LISTED_LIMIT])
    rest = len(names) - _LISTED_LIMIT
    return f"{shown} and {rest} more" if rest > 0 else shown


def _joined(problems: Sequence[str]) -> str:
    return "; ".join(problems)


__all__ = ["CHECK_NAMES", "Check", "CheckStatus", "Verification", "verify"]
