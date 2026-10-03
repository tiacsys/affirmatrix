"""Verification suite for the gate's rule for skipped outcomes.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
skipped outcome is absence of evidence: it never blocks the gate, it never
covers a specification, and the report lists it. A failing outcome, that is
one whose result is failed or error, still blocks unless a valid waiver
excuses it.

Every graph is built in memory from literal records: one leaf requirement,
one test specification, one implementation, and outcomes that confirm the
specification and witness the implementation. The tests read a finding's
severity and subject, never the text of its condition, except where a test
pins a member of the condition vocabulary by name.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from affirmatrix import diagnostics, gates, graph, records, satisfaction
from affirmatrix.records import LinkState, TestResult

EVALUATION_DATE = date(2026, 6, 1)
CURRENT_REVISION = "r1"
OTHER_REVISION = "r0"
AFFIRMED = hashlib.sha256(b"an edge hash, not recomputed here").digest()
LEAF = "SREQ-1"


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def _anchors(names: tuple[str, ...]) -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(name.encode("utf-8")).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def _node(local_id: str, kind: str, names: tuple[str, ...], **fields) -> records.NodeRecord:
    return records.NodeRecord(local_id, kind, _anchors(names), **fields)


def _edge(kind: str, from_id: str, to_id: str) -> records.EdgeRecord:
    """A strong edge, active; an evidence edge is present, and its state is not read."""
    return records.EdgeRecord(from_id, to_id, kind, LinkState.ACTIVE, AFFIRMED)


def _leaf_graph(
    results: dict[str, TestResult],
    *,
    waived: tuple[str, ...] = (),
    revisions: dict[str, str] | None = None,
) -> graph.Graph:
    """One covered leaf. Each outcome in ``results`` confirms the specification
    and witnesses the implementation. A waiver that never expires excuses
    each outcome named in ``waived``."""
    revisions = revisions or {}
    nodes = [
        _node(LEAF, "Requirement", ("contentHash",)),
        _node("TS-1", "TestSpecification", ("specHash", "implHash")),
        _node("pkg.fn", "Implementation", ("apiHash", "bodyHash")),
    ]
    edges = [_edge("Verifies", "TS-1", LEAF), _edge("Implements", "pkg.fn", LEAF)]
    for outcome_id, result in results.items():
        nodes.append(
            _node(
                outcome_id,
                "TestOutcome",
                ("contentHash",),
                result=result,
                revision=revisions.get(outcome_id, CURRENT_REVISION),
            )
        )
        edges.append(_edge("Confirms", outcome_id, "TS-1"))
        edges.append(_edge("Witnesses", outcome_id, "pkg.fn"))
    for outcome_id in waived:
        nodes.append(
            _node(
                "WVR-1", "Waiver", ("contentHash",), expiry=date(2099, 1, 1), approver="A. Reviewer"
            )
        )
        edges.append(records.EdgeRecord("WVR-1", outcome_id, "Excuses", LinkState.PENDING))
    return graph.build(Source(nodes, edges))


def _gate(built: graph.Graph) -> gates.CoverageReport:
    return gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )


def _findings(report: gates.CoverageReport, subject: str) -> list[diagnostics.Diagnostic]:
    return [d for d in report.diagnostics if d.subject == subject]


def test_a_failing_outcome_without_a_valid_waiver_blocks() -> None:
    """A failing outcome without a valid waiver blocks the gate.

    One leaf has one test specification. One outcome confirms the
    specification and witnesses the implementation. Its result is failed, and
    no waiver excuses it. The package gate reports one finding with the
    outcome as its subject. The severity of that finding blocks. The report is
    blocked. The same holds when the result is error.

    :verifies: SEG-SREQ-060
    :test-id: SEG-TS-045
    """
    for result in (TestResult.FAILED, TestResult.ERROR):
        report = _gate(_leaf_graph({"run-1/TS-1": result}))

        (finding,) = _findings(report, "run-1/TS-1")
        assert finding.severity.blocks_package
        assert report.unwaived_outcomes == {"run-1/TS-1"}
        assert report.blocked


def test_a_failing_outcome_excused_by_a_valid_waiver_only_informs() -> None:
    """A failing outcome excused by a valid waiver only informs.

    One leaf has one test specification. One outcome confirms the
    specification and witnesses the implementation. Its result is failed. A
    waiver that has not expired excuses the outcome. The package gate reports
    one finding with the outcome as its subject. The severity of that finding
    is information. The report is not blocked. The same holds when the result
    is error.

    :verifies: SEG-SREQ-061
    :test-id: SEG-TS-046
    """
    for result in (TestResult.FAILED, TestResult.ERROR):
        report = _gate(_leaf_graph({"run-1/TS-1": result}, waived=("run-1/TS-1",)))

        (finding,) = _findings(report, "run-1/TS-1")
        assert finding.severity is diagnostics.Severity.INFO
        assert report.excused_outcomes == {"run-1/TS-1"}
        assert report.unwaived_outcomes == frozenset()
        assert not report.blocked


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-129: the gate does not judge skipped outcomes yet")
def test_a_valid_waiver_changes_nothing_for_a_skipped_outcome() -> None:
    """A waiver does not excuse a skipped outcome.

    Two graphs are the same leaf with one outcome that confirms the
    specification, witnesses the implementation and was skipped. In the second
    graph a waiver that has not expired excuses that outcome. The package gate
    gives an equal report for both graphs. The report holds no excused finding.
    It still lists the skipped outcome. The leaf has the same verdict in both
    graphs.

    :verifies: SEG-SREQ-129
    :test-id: SEG-TS-047
    """
    results = {"run-1/TS-1": TestResult.SKIPPED}
    without_waiver = _leaf_graph(results)
    with_waiver = _leaf_graph(results, waived=("run-1/TS-1",))

    report = _gate(with_waiver)

    assert report == _gate(without_waiver)
    assert report.excused_outcomes == frozenset()
    assert report.skipped_outcomes == {"run-1/TS-1"}
    assert satisfaction.leaf_satisfied(with_waiver, LEAF) == satisfaction.leaf_satisfied(
        without_waiver, LEAF
    )


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-199: the gate does not judge skipped outcomes yet")
def test_a_skipped_outcome_is_reported_as_information() -> None:
    """A skipped outcome is reported as information and does not block.

    One leaf has one test specification. Two outcomes confirm the
    specification and witness the implementation. One passed and one was
    skipped. The report lists the skipped outcome and not the passed one. The
    report holds one finding, with the skipped outcome as its subject and the
    skipped-outcome condition. The severity of that finding is information.
    No failing outcome is listed. The report is not blocked.

    :verifies: SEG-SREQ-199
    :test-id: SEG-TS-048
    """
    report = _gate(_leaf_graph({"run-1/TS-1": TestResult.PASSED, "run-2/TS-1": TestResult.SKIPPED}))

    assert report.skipped_outcomes == {"run-2/TS-1"}
    assert [(d.severity, d.condition, d.subject) for d in report.diagnostics] == [
        (diagnostics.Severity.INFO, gates.Condition.SKIPPED_OUTCOME, "run-2/TS-1")
    ]
    assert report.unwaived_outcomes == frozenset()
    assert report.excused_outcomes == frozenset()
    assert not report.blocked


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-006: the gate does not judge skipped outcomes yet")
def test_a_skipped_outcome_beside_a_passed_one_leaves_the_leaf_satisfied() -> None:
    """A skipped outcome does not stop a leaf from being satisfied.

    One leaf carries an active verifies edge and an active implements edge.
    Its one test specification has two confirming outcomes. One passed and one
    was skipped. The satisfaction evaluator reports the leaf as satisfied.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-049
    """
    built = _leaf_graph({"run-1/TS-1": TestResult.PASSED, "run-2/TS-1": TestResult.SKIPPED})

    assert satisfaction.leaf_satisfied(built, LEAF)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-006: the gate does not judge skipped outcomes yet")
def test_a_leaf_whose_only_outcome_was_skipped_is_not_satisfied() -> None:
    """A leaf whose only outcome was skipped is not satisfied.

    One leaf carries an active verifies edge and an active implements edge.
    Its one test specification has one confirming outcome, and that outcome
    was skipped. The satisfaction evaluator reports the leaf as not satisfied.
    The package gate reports the leaf as a coverage gap. The report is
    blocked, and that coverage gap is the only finding that blocks.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-050
    """
    built = _leaf_graph({"run-1/TS-1": TestResult.SKIPPED})

    report = _gate(built)

    assert not satisfaction.leaf_satisfied(built, LEAF)
    assert report.coverage_gaps == {LEAF}
    assert report.blocked
    assert [(d.condition, d.subject) for d in report.diagnostics if d.severity.blocks_package] == [
        (gates.Condition.COVERAGE_GAP, LEAF)
    ]


def test_a_failed_outcome_excused_by_a_valid_waiver_satisfies_the_leaf() -> None:
    """A failed outcome excused by a valid waiver counts for the leaf.

    One leaf carries an active verifies edge and an active implements edge.
    Its one test specification has one confirming outcome. That outcome
    failed, and a waiver that has not expired excuses it. The satisfaction
    evaluator reports the leaf as satisfied.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-051
    """
    built = _leaf_graph({"run-1/TS-1": TestResult.FAILED}, waived=("run-1/TS-1",))

    assert satisfaction.leaf_satisfied(built, LEAF)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-067: the gate does not judge skipped outcomes yet")
def test_a_stale_skipped_outcome_is_reported_once_as_stale() -> None:
    """A skipped outcome from another revision is reported once, as stale.

    One leaf has one test specification. One outcome passed at the current
    revision. Another outcome was skipped, and it was recorded at a different
    revision. The package gate reports the second outcome as stale, with one
    finding of information severity. The report does not list it among the
    skipped outcomes. The report is not blocked.

    :verifies: SEG-SREQ-067
    :test-id: SEG-TS-052
    """
    report = _gate(
        _leaf_graph(
            {"run-1/TS-1": TestResult.PASSED, "run-2/TS-1": TestResult.SKIPPED},
            revisions={"run-2/TS-1": OTHER_REVISION},
        )
    )

    assert report.stale_outcomes == {"run-2/TS-1"}
    assert [(d.severity, d.condition) for d in _findings(report, "run-2/TS-1")] == [
        (diagnostics.Severity.INFO, gates.Condition.STALE_OUTCOME)
    ]
    assert report.skipped_outcomes == frozenset()
    assert not report.blocked
