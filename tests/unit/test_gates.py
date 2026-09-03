"""The gate evaluator (SEG-SREQ-042…045, SEG-SREQ-060…067) and the severity
and condition vocabularies it reads and closes.

The package gate is a pure function over a built graph: no store access, no
refusal, no enforcement — it judges and reports. The report's two derived
views, ``diagnostics`` and ``blocked``, are computed from the same seven typed
findings, so the tests that matter most are the ones proving the views cannot
disagree: an info-only report never blocks, any warning does, and the
worklist and the gap attribution each land on exactly the node the
requirement names — the worklist at the edge (SEG-SREQ-043), the gap at the
leaf where coverage is actually missing, never an ancestor (SEG-SREQ-044). An
empty design set is blocked outright (SEG-SREQ-045), and a scope with nothing
wrong in it is not. A non-passing outcome is a finding whether or not a
waiver excuses it, judged against an explicit, caller-supplied
``evaluation_date`` (SEG-SREQ-059's expiry half) rather than the system
clock. A stale outcome — recorded revision differing from an explicit,
caller-supplied ``current_revision`` — is cut from the graph before every
other finding is computed, so it is absent from coverage and from the waiver
seam alike and is reported exactly once, informationally.

Fixture graphs are built in memory from literal records, like
``test_drift.py`` and ``test_affirmation.py``; the one end-to-end test builds
its case under ``tmp_path``. Nothing here touches the repository's own case,
and composing affirmations here is a capability test, never an affirmation
act.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from affirmatrix import (
    affirmation,
    case,
    commitment,
    diagnostics,
    drift,
    gates,
    graph,
    records,
    satisfaction,
)
from affirmatrix.records import LinkState

#: A fixed "today" for every gate evaluation in this file — repeatability
#: (SEG-SREQ-009's ethos, applied to the gate) would otherwise depend on which
#: day the suite happened to run.
EVALUATION_DATE = date(2026, 6, 1)

#: A fixed "current revision" for every gate evaluation in this file that does
#: not itself test staleness — every fixture outcome below is built fresh
#: against this same value, so no existing test's outcomes read as stale by
#: accident.
CURRENT_REVISION = "r1"

#: A digest that satisfies the vocabulary's shape check without needing to
#: recompute to anything real — these tests build graphs directly and never
#: ask the gate to recompute a hash, so any 32-byte value will do.
STALE = hashlib.sha256(b"a stored edge hash, not recomputed here").digest()

#: An operator's judgement, as keyword arguments. Revisions are 40-hex so the
#: same judgement passes the case schema in the end-to-end test.
JUDGEMENT = {
    "role": "SoftwareEngineer",
    "reason": "B15 capability test: composing, not affirming",
    "from_source_revision": "1" * 40,
    "to_source_revision": "2" * 40,
}


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def anchors(names: tuple[str, ...], seed: str = "v1") -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(f"{name}:{seed}".encode()).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def requirement(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors(("contentHash",), seed))


def implementation(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Implementation", anchors(("apiHash", "bodyHash"), seed))


def specification(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "TestSpecification", anchors(("specHash", "implHash"), seed)
    )


def outcome(
    local_id: str,
    seed: str = "v1",
    result: records.TestResult = records.TestResult.PASSED,
    revision: str = CURRENT_REVISION,
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "TestOutcome", anchors(("contentHash",), seed), result=result, revision=revision
    )


def waiver(
    local_id: str, seed: str = "v1", expiry: date = date(2099, 1, 1), approver: str = "A. Reviewer"
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "Waiver", anchors(("contentHash",), seed), expiry=expiry, approver=approver
    )


def _affirmed(
    kind: str, from_node: records.NodeRecord, to_node: records.NodeRecord
) -> records.EdgeRecord:
    """A recorded edge affirmed against exactly these two nodes' content.

    Real commitment hashes, unlike ``edge``'s ``STALE`` placeholder: needed
    wherever a graph goes through ``drift.derive`` rather than being built
    directly, since drift recomputes and compares.
    """
    from_hash = commitment.node_hash(from_node.kind, from_node.content_hashes)
    to_hash = commitment.node_hash(to_node.kind, to_node.content_hashes)
    return records.EdgeRecord(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        state=LinkState.ACTIVE,
        edge_hash=commitment.edge_hash(
            from_node.local_id, to_node.local_id, kind, from_hash, to_hash
        ),
    )


def excuses(waiver_id: str, outcome_id: str) -> records.EdgeRecord:
    """An excusing edge: Waiver to TestOutcome (``edge-excuses.schema.json``).

    Evidence, like ``Confirms`` and ``Witnesses``: always pending, never
    affirmed.
    """
    return edge("Excuses", waiver_id, outcome_id, LinkState.PENDING)


def edge(
    kind: str, from_id: str, to_id: str, state: LinkState, edge_hash: bytes | None = STALE
) -> records.EdgeRecord:
    """A literal edge in the given state.

    ``edge_hash`` defaults to a placeholder digest, which every non-pending
    state needs merely to be *present* — the gate reads a declared state, it
    never recomputes one. Pending must override it with ``None``.
    """
    return records.EdgeRecord(
        from_id=from_id,
        to_id=to_id,
        kind=kind,
        state=state,
        edge_hash=None if state is LinkState.PENDING else edge_hash,
    )


def leaf_fixture() -> tuple[list[records.NodeRecord], list[records.EdgeRecord]]:
    """A single fully covered leaf requirement: active edges, a passing outcome."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl, run = implementation("pkg.fn"), outcome("run-1/TS-1")
    edges = [
        edge("Verifies", "TS-1", "SREQ-1", LinkState.ACTIVE),
        edge("Implements", "pkg.fn", "SREQ-1", LinkState.ACTIVE),
        edge("Confirms", "run-1/TS-1", "TS-1", LinkState.ACTIVE),
        edge("Witnesses", "run-1/TS-1", "pkg.fn", LinkState.ACTIVE),
    ]
    return [sreq, spec, impl, run], edges


# --- the severity vocabulary --------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "blocks_commit", "blocks_package"),
    [
        (diagnostics.Severity.ERROR, True, True),
        (diagnostics.Severity.WARNING, False, True),
        (diagnostics.Severity.INFO, False, False),
    ],
)
def test_severity_blocking_table(
    severity: diagnostics.Severity, blocks_commit: bool, blocks_package: bool
) -> None:
    """SEG-SREQ-042: error and warning block, info never does; the meaning
    lives on the severity so no two gates can read it differently."""
    assert severity.blocks_commit is blocks_commit
    assert severity.blocks_package is blocks_package


def test_diagnostic_refuses_an_empty_condition() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        diagnostics.Diagnostic(severity=diagnostics.Severity.WARNING, condition="", subject="x")


def test_diagnostic_refuses_an_empty_subject() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        diagnostics.Diagnostic(severity=diagnostics.Severity.WARNING, condition="x", subject="")


# --- the report's two derived views --------------------------------------------


def test_a_report_with_only_info_findings_is_not_blocked() -> None:
    """SEG-SREQ-042: information never blocks, even when it is the only finding."""
    report = gates.CoverageReport(
        unready_edges=(),
        coverage_gaps=frozenset(),
        stale_outcomes=frozenset({"run-3/TS-1"}),
        discarded_outcomes=frozenset({"run-1/TS-1"}),
        unwaived_outcomes=frozenset(),
        excused_outcomes=frozenset({"run-2/TS-1"}),
        design_set_empty=False,
    )
    assert report.diagnostics
    assert all(d.severity is diagnostics.Severity.INFO for d in report.diagnostics)
    assert not report.blocked


@pytest.mark.parametrize(
    "report",
    [
        gates.CoverageReport(
            unready_edges=(edge("Implements", "pkg.fn", "SREQ-1", LinkState.PENDING),),
            coverage_gaps=frozenset(),
            stale_outcomes=frozenset(),
            discarded_outcomes=frozenset(),
            unwaived_outcomes=frozenset(),
            excused_outcomes=frozenset(),
            design_set_empty=False,
        ),
        gates.CoverageReport(
            unready_edges=(),
            coverage_gaps=frozenset({"SREQ-1"}),
            stale_outcomes=frozenset(),
            discarded_outcomes=frozenset(),
            unwaived_outcomes=frozenset(),
            excused_outcomes=frozenset(),
            design_set_empty=False,
        ),
        gates.CoverageReport(
            unready_edges=(),
            coverage_gaps=frozenset(),
            stale_outcomes=frozenset(),
            discarded_outcomes=frozenset(),
            unwaived_outcomes=frozenset(),
            excused_outcomes=frozenset(),
            design_set_empty=True,
        ),
        gates.CoverageReport(
            unready_edges=(),
            coverage_gaps=frozenset(),
            stale_outcomes=frozenset(),
            discarded_outcomes=frozenset(),
            unwaived_outcomes=frozenset({"run-1/TS-1"}),
            excused_outcomes=frozenset(),
            design_set_empty=False,
        ),
    ],
    ids=["unready-edge", "coverage-gap", "empty-design-set", "unwaived-outcome"],
)
def test_any_warning_finding_blocks(report: gates.CoverageReport) -> None:
    """SEG-SREQ-042: each of the four gate conditions is a warning, and a
    warning blocks the package on its own."""
    assert any(d.severity is diagnostics.Severity.WARNING for d in report.diagnostics)
    assert report.blocked


def test_any_warning_finding_blocks_the_stale_outcome_included() -> None:
    """The stale finding is informational on its own (covered above); this
    pins that its presence never masks an unrelated warning finding."""
    report = gates.CoverageReport(
        unready_edges=(),
        coverage_gaps=frozenset({"SREQ-1"}),
        stale_outcomes=frozenset({"run-1/TS-1"}),
        discarded_outcomes=frozenset(),
        unwaived_outcomes=frozenset(),
        excused_outcomes=frozenset(),
        design_set_empty=False,
    )
    assert report.blocked


def test_diagnostics_and_blocked_never_disagree() -> None:
    """The two views are computed from the same seven fields; ``blocked`` is
    exactly "some diagnostic blocks the package", never a second opinion."""
    empty: frozenset[str] = frozenset()
    reports = [
        gates.CoverageReport((), empty, empty, empty, empty, empty, design_set_empty=False),
        gates.CoverageReport(
            (), empty, empty, frozenset({"run-1/TS-1"}), empty, empty, design_set_empty=False
        ),
        gates.CoverageReport(
            (), frozenset({"SREQ-1"}), empty, empty, empty, empty, design_set_empty=False
        ),
        gates.CoverageReport((), empty, empty, empty, empty, empty, design_set_empty=True),
        gates.CoverageReport(
            (), empty, empty, empty, frozenset({"run-1/TS-1"}), empty, design_set_empty=False
        ),
        gates.CoverageReport(
            (), empty, empty, empty, empty, frozenset({"run-1/TS-1"}), design_set_empty=False
        ),
        gates.CoverageReport(
            (), empty, frozenset({"run-1/TS-1"}), empty, empty, empty, design_set_empty=False
        ),
    ]
    for report in reports:
        assert report.blocked == any(d.severity.blocks_package for d in report.diagnostics)


# --- the closed condition vocabulary (SEG-SREQ-064, SEG-SREQ-065) --------------


def test_every_diagnostics_condition_is_a_member_of_the_closed_vocabulary() -> None:
    """SEG-SREQ-064: whatever a report finds, every diagnostic's condition is
    one of the seven fixed :class:`gates.Condition` members — never a
    sentence assembled for the occurrence."""
    nodes, edges = leaf_fixture()
    failed = outcome("run-1/TS-1", result=records.TestResult.FAILED)
    stray = outcome("run-2/TS-1", revision="stale-revision")
    stray_spec = specification("TS-2")
    all_nodes = [n if n.local_id != "run-1/TS-1" else failed for n in nodes] + [stray, stray_spec]
    all_edges = [*edges, edge("Confirms", "run-2/TS-1", "TS-2", LinkState.PENDING)]
    built = graph.build(Source(all_nodes, all_edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.diagnostics
    assert {d.condition for d in report.diagnostics} <= {member.value for member in gates.Condition}


def test_the_unready_edge_condition_carries_no_interpolated_state_the_detail_field_does() -> None:
    """SEG-SREQ-065: an edge's own state varies by occurrence and lives on
    ``detail``, never folded into ``condition``."""
    sreq = requirement("SREQ-1")
    impls = {state: implementation(f"pkg.{state.value}") for state in LinkState}
    strong_edges = [
        edge("Implements", impls[state].local_id, "SREQ-1", state) for state in LinkState
    ]
    built = graph.build(Source([sreq, *impls.values()], strong_edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    unready = [d for d in report.diagnostics if d.condition == gates.Condition.UNREADY_EDGE]
    assert unready
    assert {d.condition for d in unready} == {gates.Condition.UNREADY_EDGE}
    assert {d.detail for d in unready} == {
        state.value for state in LinkState if state is not LinkState.ACTIVE
    }


def test_a_diagnostic_allows_an_empty_detail() -> None:
    """Not every condition varies by occurrence: a coverage gap names only
    the requirement, with nothing further to add."""
    built = graph.build(Source([requirement("ORPHAN-1")]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    gap = next(d for d in report.diagnostics if d.condition == gates.Condition.COVERAGE_GAP)
    assert gap.detail == ""


# --- the worklist (SEG-SREQ-043) -----------------------------------------------


def test_worklist_lists_every_non_active_state_and_omits_active_and_evidence() -> None:
    """All five non-active states are listed — pending and broken included,
    neither resolvable by affirmation — and evidence edges never appear."""
    sreq = requirement("SREQ-1")
    impls = {state: implementation(f"pkg.{state.value}") for state in LinkState}
    spec, run = specification("TS-1"), outcome("run-1/TS-1")
    strong_edges = [
        edge("Implements", impls[state].local_id, "SREQ-1", state) for state in LinkState
    ]
    evidence_edge = edge("Confirms", "run-1/TS-1", "TS-1", LinkState.DIRECTLY_OUTDATED)
    nodes = [sreq, spec, run, *impls.values()]
    built = graph.build(Source(nodes, [*strong_edges, evidence_edge]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    non_active_states = {state for state in LinkState if state is not LinkState.ACTIVE}
    assert {e.state for e in report.unready_edges} == non_active_states
    assert all(e.kind == "Implements" for e in report.unready_edges)
    assert all(e.to_id == "SREQ-1" for e in report.unready_edges)


def test_worklist_is_sorted_by_kind_then_endpoints() -> None:
    top, sys_req, sreq = requirement("TOP-1"), requirement("SYS-1"), requirement("SREQ-1")
    impl_b, impl_a = implementation("pkg.b"), implementation("pkg.a")
    edges = [
        edge("Refines", "SYS-1", "TOP-1", LinkState.PENDING),
        edge("Implements", "pkg.b", "SREQ-1", LinkState.PENDING),
        edge("Implements", "pkg.a", "SREQ-1", LinkState.PENDING),
    ]
    built = graph.build(Source([top, sys_req, sreq, impl_a, impl_b], edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert [(e.kind, e.from_id, e.to_id) for e in report.unready_edges] == [
        ("Implements", "pkg.a", "SREQ-1"),
        ("Implements", "pkg.b", "SREQ-1"),
        ("Refines", "SYS-1", "TOP-1"),
    ]


# --- gap attribution (SEG-SREQ-044) --------------------------------------------


def test_gap_lands_at_the_leaf_never_at_an_unsatisfied_ancestor() -> None:
    """A three-level chain, no coverage anywhere. The verdict shows every
    level unsatisfied, but the report names only the leaf: an ancestor with
    no direct edges of its own has nothing of its own to fail."""
    top, sys_req, sreq = requirement("TOP-1"), requirement("SYS-1"), requirement("SREQ-1")
    edges = [
        edge("Refines", "SYS-1", "TOP-1", LinkState.ACTIVE),
        edge("Refines", "SREQ-1", "SYS-1", LinkState.ACTIVE),
    ]
    built = graph.build(Source([top, sys_req, sreq], edges))

    verdict = satisfaction.evaluate(built)
    assert not verdict.is_satisfied("SREQ-1")
    assert not verdict.is_satisfied("SYS-1")
    assert not verdict.is_satisfied("TOP-1")

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert report.coverage_gaps == {"SREQ-1"}


def test_non_leaf_gap_from_its_own_edge_is_not_shielded_by_satisfied_children() -> None:
    """The parent carries its own direct implements edge, pending; its child
    is fully, genuinely satisfied. The gap still lands on the parent, and the
    satisfied leaf is not listed."""
    nodes, edges = leaf_fixture()  # LEAF-1 stands in for a fully covered child
    leaf = requirement("LEAF-1")
    parent = requirement("PARENT-1")
    parent_impl = implementation("pkg.parent")
    renamed_edges = [
        records.EdgeRecord(
            from_id=e.from_id if e.from_id != "SREQ-1" else "LEAF-1",
            to_id=e.to_id if e.to_id != "SREQ-1" else "LEAF-1",
            kind=e.kind,
            state=e.state,
            edge_hash=e.edge_hash,
        )
        for e in edges
    ]
    all_edges = [
        *renamed_edges,
        edge("Refines", "LEAF-1", "PARENT-1", LinkState.ACTIVE),
        edge("Implements", "pkg.parent", "PARENT-1", LinkState.PENDING),
    ]
    all_nodes = [n for n in nodes if n.local_id != "SREQ-1"] + [leaf, parent, parent_impl]

    built = graph.build(Source(all_nodes, all_edges))
    verdict = satisfaction.evaluate(built)
    assert verdict.is_satisfied("LEAF-1")

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert report.coverage_gaps == {"PARENT-1"}


def test_orphan_requirement_is_its_own_gap() -> None:
    orphan = requirement("ORPHAN-1")
    built = graph.build(Source([orphan], []))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.coverage_gaps == {"ORPHAN-1"}


# --- the empty design set (SEG-SREQ-045) ---------------------------------------


def test_no_requirement_nodes_means_the_design_set_is_empty_and_blocked() -> None:
    """A scope of implementations and specs with zero requirements is
    blocked, not vacuously ready."""
    impl = implementation("pkg.fn")
    built = graph.build(Source([impl], []))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.design_set_empty
    assert report.blocked
    assert report.coverage_gaps == frozenset()


def test_an_entirely_empty_graph_is_blocked() -> None:
    built = graph.build(Source([], []))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.design_set_empty
    assert report.blocked


# --- a scope with nothing wrong -------------------------------------------------


def test_fully_covered_fully_affirmed_scope_is_ready() -> None:
    nodes, edges = leaf_fixture()
    built = graph.build(Source(nodes, edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert not report.blocked
    assert report.diagnostics == ()
    assert report.unready_edges == ()
    assert report.coverage_gaps == frozenset()
    assert not report.design_set_empty


def test_a_discarded_outcome_that_opens_no_gap_is_info_only() -> None:
    """A stray, incomplete outcome on a specification nothing verifies yet
    is named in the report but blocks nothing: no requirement's coverage
    rests on it."""
    nodes, edges = leaf_fixture()
    stray_spec = specification("TS-2")
    stray_run = outcome("run-2/TS-2")
    incomplete = edge("Confirms", "run-2/TS-2", "TS-2", LinkState.PENDING)
    built = graph.build(Source([*nodes, stray_spec, stray_run], [*edges, incomplete]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.discarded_outcomes == {"run-2/TS-2"}
    assert report.coverage_gaps == frozenset()
    assert not report.blocked
    assert {d.severity for d in report.diagnostics} == {diagnostics.Severity.INFO}


# --- staleness (SEG-SREQ-063, SEG-SREQ-067) -------------------------------------


def test_a_fresh_outcome_is_not_reported_stale() -> None:
    nodes, edges = leaf_fixture()
    built = graph.build(Source(nodes, edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == frozenset()


def test_a_stale_outcome_is_reported_as_an_info_finding() -> None:
    nodes, edges = leaf_fixture()
    stale = [
        outcome("run-1/TS-1", revision="a-different-revision") if n.local_id == "run-1/TS-1" else n
        for n in nodes
    ]
    built = graph.build(Source(stale, edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == {"run-1/TS-1"}
    assert any(
        d.condition == gates.Condition.STALE_OUTCOME
        and d.severity is diagnostics.Severity.INFO
        and d.subject == "run-1/TS-1"
        for d in report.diagnostics
    )


def test_a_stale_only_specification_is_a_coverage_gap() -> None:
    """SEG-SREQ-063: a stale outcome is absent when the gate judges the
    specification it confirms — the same reading as an outcome that was
    never recorded at all."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl = implementation("pkg.fn")
    stale_run = outcome("run-1/TS-1", revision="a-different-revision")
    edges = [
        edge("Verifies", "TS-1", "SREQ-1", LinkState.ACTIVE),
        edge("Implements", "pkg.fn", "SREQ-1", LinkState.ACTIVE),
        edge("Confirms", "run-1/TS-1", "TS-1", LinkState.ACTIVE),
        edge("Witnesses", "run-1/TS-1", "pkg.fn", LinkState.ACTIVE),
    ]
    built = graph.build(Source([sreq, spec, impl, stale_run], edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == {"run-1/TS-1"}
    assert report.coverage_gaps == {"SREQ-1"}
    assert report.blocked


def test_a_fresh_sibling_outcome_keeps_a_specification_covered_despite_a_stale_outcome() -> None:
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl = implementation("pkg.fn")
    stale_run = outcome("run-1/TS-1", revision="a-different-revision")
    fresh_run = outcome("run-2/TS-1")
    edges = [
        edge("Verifies", "TS-1", "SREQ-1", LinkState.ACTIVE),
        edge("Implements", "pkg.fn", "SREQ-1", LinkState.ACTIVE),
        edge("Confirms", "run-1/TS-1", "TS-1", LinkState.ACTIVE),
        edge("Witnesses", "run-1/TS-1", "pkg.fn", LinkState.ACTIVE),
        edge("Confirms", "run-2/TS-1", "TS-1", LinkState.ACTIVE),
        edge("Witnesses", "run-2/TS-1", "pkg.fn", LinkState.ACTIVE),
    ]
    built = graph.build(Source([sreq, spec, impl, stale_run, fresh_run], edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == {"run-1/TS-1"}
    assert report.coverage_gaps == frozenset()
    assert not report.blocked


def test_a_stale_outcome_is_never_also_reported_discarded() -> None:
    """A stale outcome is cut from the graph before discard is even asked
    about it, whether or not it would otherwise have been evidence-complete."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    stale_run = outcome("run-1/TS-1", revision="a-different-revision")
    incomplete = edge("Confirms", "run-1/TS-1", "TS-1", LinkState.PENDING)
    built = graph.build(Source([sreq, spec, stale_run], [incomplete]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == {"run-1/TS-1"}
    assert report.discarded_outcomes == frozenset()
    assert sum(d.subject == "run-1/TS-1" for d in report.diagnostics) == 1


def test_a_stale_non_passing_outcome_is_never_also_reported_unwaived_or_excused() -> None:
    """A stale, failing outcome is reported once, as stale — never doubled
    with a waiver-seam finding for the same underlying reason."""
    nodes, edges = failing_leaf_fixture()
    stale = [
        outcome("run-1/TS-1", result=records.TestResult.FAILED, revision="a-different-revision")
        if n.local_id == "run-1/TS-1"
        else n
        for n in nodes
    ]
    built = graph.build(Source(stale, edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.stale_outcomes == {"run-1/TS-1"}
    assert report.unwaived_outcomes == frozenset()
    assert report.excused_outcomes == frozenset()
    assert sum(d.subject == "run-1/TS-1" for d in report.diagnostics) == 1


def test_stale_exclusion_does_not_affect_the_unready_edge_worklist() -> None:
    """Stale outcomes are never endpoints of a strong edge, so cutting them
    out changes nothing about which strong edges are unready."""
    nodes, edges = leaf_fixture()
    pending_impl = edge("Implements", "pkg.fn", "SREQ-1", LinkState.PENDING)
    edges_with_pending = [e for e in edges if e.kind != "Implements"] + [pending_impl]
    stale = [
        outcome("run-1/TS-1", revision="a-different-revision") if n.local_id == "run-1/TS-1" else n
        for n in nodes
    ]
    built = graph.build(Source(stale, edges_with_pending))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert {(e.kind, e.from_id, e.to_id) for e in report.unready_edges} == {
        ("Implements", "pkg.fn", "SREQ-1")
    }


def test_current_revision_is_required_and_keyword_only() -> None:
    nodes, edges = leaf_fixture()
    built = graph.build(Source(nodes, edges))
    with pytest.raises(TypeError):
        gates.package_gate(built, evaluation_date=EVALUATION_DATE)  # type: ignore[call-arg]


# --- the waiver seam (SEG-SREQ-060, SEG-SREQ-061) -------------------------------


def failing_leaf_fixture() -> tuple[list[records.NodeRecord], list[records.EdgeRecord]]:
    """A leaf fixture like :func:`leaf_fixture`, but its one outcome failed."""
    nodes, edges = leaf_fixture()
    failed_outcome = outcome("run-1/TS-1", result=records.TestResult.FAILED)
    failed = [failed_outcome if n.local_id == "run-1/TS-1" else n for n in nodes]
    return failed, edges


def test_a_non_passing_outcome_with_no_excusing_waiver_is_a_blocking_warning() -> None:
    nodes, edges = failing_leaf_fixture()
    built = graph.build(Source(nodes, edges))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.unwaived_outcomes == {"run-1/TS-1"}
    assert report.excused_outcomes == frozenset()
    assert report.blocked
    assert any(
        d.severity is diagnostics.Severity.WARNING and d.subject == "run-1/TS-1"
        for d in report.diagnostics
    )


def test_a_non_passing_outcome_excused_by_a_valid_waiver_is_informational_only() -> None:
    nodes, edges = failing_leaf_fixture()
    excuse = waiver("WVR-1", expiry=date(2099, 1, 1))
    built = graph.build(Source([*nodes, excuse], [*edges, excuses("WVR-1", "run-1/TS-1")]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.excused_outcomes == {"run-1/TS-1"}
    assert report.unwaived_outcomes == frozenset()
    assert not report.blocked
    assert any(
        d.severity is diagnostics.Severity.INFO and d.subject == "run-1/TS-1"
        for d in report.diagnostics
    )


def test_a_non_passing_outcome_excused_by_an_expired_waiver_still_blocks() -> None:
    """SEG-SREQ-059's expiry half: an excusing waiver past its date is invalid."""
    nodes, edges = failing_leaf_fixture()
    expired = waiver("WVR-1", expiry=date(2020, 1, 1))
    built = graph.build(Source([*nodes, expired], [*edges, excuses("WVR-1", "run-1/TS-1")]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.unwaived_outcomes == {"run-1/TS-1"}
    assert report.excused_outcomes == frozenset()
    assert report.blocked


def test_a_non_passing_outcome_with_a_dangling_excusal_still_blocks() -> None:
    """An Excuses edge whose Waiver record is absent excuses nothing — the
    waiver itself must be present, not merely declared, exactly as at
    satisfaction's own excusal reading."""
    nodes, edges = failing_leaf_fixture()
    built = graph.build(Source(nodes, [*edges, excuses("WVR-MISSING", "run-1/TS-1")]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.unwaived_outcomes == {"run-1/TS-1"}
    assert report.excused_outcomes == frozenset()
    assert report.blocked


def test_a_passing_outcome_is_never_a_waiver_finding_even_with_an_excusal_edge() -> None:
    nodes, edges = leaf_fixture()
    excuse = waiver("WVR-1")
    built = graph.build(Source([*nodes, excuse], [*edges, excuses("WVR-1", "run-1/TS-1")]))

    report = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert report.unwaived_outcomes == frozenset()
    assert report.excused_outcomes == frozenset()


def test_evaluation_date_is_not_inert() -> None:
    """The same graph, judged before and after a waiver's expiry, disagrees —
    proof the parameter is load-bearing rather than decorative."""
    nodes, edges = failing_leaf_fixture()
    excuse = waiver("WVR-1", expiry=date(2026, 6, 1))
    built = graph.build(Source([*nodes, excuse], [*edges, excuses("WVR-1", "run-1/TS-1")]))

    before_expiry = gates.package_gate(
        built, evaluation_date=date(2026, 5, 1), current_revision=CURRENT_REVISION
    )
    after_expiry = gates.package_gate(
        built, evaluation_date=date(2026, 6, 2), current_revision=CURRENT_REVISION
    )

    assert not before_expiry.blocked
    assert after_expiry.blocked


# --- purity and repeatability ---------------------------------------------------


def test_evaluation_is_pure_and_repeatable() -> None:
    nodes, edges = leaf_fixture()
    built = graph.build(Source(nodes, edges))

    first = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    second = gates.package_gate(
        built, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )

    assert first == second
    assert first.diagnostics == second.diagnostics


# --- the operator's path, end to end --------------------------------------------


def test_operators_path_from_bootstrap_blocked_to_ready(tmp_path: Path) -> None:
    """The B14 join, now visible at the gate: a store bootstrapped with every
    strong edge pending evaluates blocked with the worklist naming exactly
    those edges; composing an affirmation per worklist edge (capability, a
    throwaway root — never an affirmation act) and re-deriving turns the same
    scope ready."""
    sys_req, sreq = requirement("SYS-1"), requirement("SREQ-1")
    spec, impl, run = specification("TS-1"), implementation("pkg.fn"), outcome("run-1/TS-1")
    nodes = [sys_req, sreq, spec, impl, run]
    strong_edges = [
        edge("Refines", "SREQ-1", "SYS-1", LinkState.PENDING),
        edge("Verifies", "TS-1", "SREQ-1", LinkState.PENDING),
        edge("Implements", "pkg.fn", "SREQ-1", LinkState.PENDING),
    ]
    evidence_edges = [
        edge("Confirms", "run-1/TS-1", "TS-1", LinkState.PENDING),
        edge("Witnesses", "run-1/TS-1", "pkg.fn", LinkState.PENDING),
    ]
    all_edges = [*strong_edges, *evidence_edges]

    store = case.AffirmationStore(root=tmp_path / "case")
    store.write_nodes(nodes)
    store.write_edges(all_edges)

    current = Source(nodes, all_edges)
    node_by_id = {node.local_id: node for node in nodes}

    bootstrapped = graph.build(drift.derive(recorded=store, current=current))
    blocked_report = gates.package_gate(
        bootstrapped, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert blocked_report.blocked
    assert {(e.kind, e.from_id, e.to_id) for e in blocked_report.unready_edges} == {
        (e.kind, e.from_id, e.to_id) for e in strong_edges
    }

    composed_events = []
    composed_edges = []
    for worklist_edge in blocked_report.unready_edges:
        composed = affirmation.compose(
            worklist_edge,
            from_node=node_by_id[worklist_edge.from_id],
            to_node=node_by_id[worklist_edge.to_id],
            **JUDGEMENT,
        )
        composed_events.append(composed.event)
        composed_edges.append(composed.edge)
    store.append_review_events(composed_events)
    store.write_edges(composed_edges)

    settled = graph.build(drift.derive(recorded=store, current=current))
    ready_report = gates.package_gate(
        settled, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert not ready_report.blocked
    assert ready_report.unready_edges == ()
    assert ready_report.coverage_gaps == frozenset()


def test_operators_path_from_unwaived_failure_to_excused_via_waiver(tmp_path: Path) -> None:
    """The join the waiver seam adds: an unwaived failing outcome blocks the
    gate; recording a Waiver node and its excusing edge in the same store and
    re-deriving turns the finding informational, never blocking, without
    touching anything about the strong edges above it.

    The strong edges are properly affirmed (real commitment hashes, via
    ``_affirmed``) rather than built with ``edge``'s ``STALE`` placeholder,
    because this graph goes through ``drift.derive`` — which recomputes and
    compares — and not straight through ``graph.build``.
    """
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl, run = implementation("pkg.fn"), outcome("run-1/TS-1", result=records.TestResult.FAILED)
    nodes = [sreq, spec, impl, run]
    strong_edges = [_affirmed("Verifies", spec, sreq), _affirmed("Implements", impl, sreq)]
    evidence_edges = [
        edge("Confirms", "run-1/TS-1", "TS-1", LinkState.PENDING),
        edge("Witnesses", "run-1/TS-1", "pkg.fn", LinkState.PENDING),
    ]
    all_edges = [*strong_edges, *evidence_edges]

    store = case.AffirmationStore(root=tmp_path / "case")
    store.write_nodes(nodes)
    store.write_edges(all_edges)

    current = Source(nodes, all_edges)
    blocked = graph.build(drift.derive(recorded=store, current=current))
    blocked_report = gates.package_gate(
        blocked, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert blocked_report.blocked
    assert blocked_report.unready_edges == ()
    assert blocked_report.unwaived_outcomes == {"run-1/TS-1"}

    excuse = waiver("WVR-1", expiry=date(2099, 1, 1))
    excusal_edge = excuses("WVR-1", "run-1/TS-1")
    store.write_nodes([excuse])
    store.write_edges([excusal_edge])

    current_with_waiver = Source([*nodes, excuse], [*all_edges, excusal_edge])
    settled = graph.build(drift.derive(recorded=store, current=current_with_waiver))
    settled_report = gates.package_gate(
        settled, evaluation_date=EVALUATION_DATE, current_revision=CURRENT_REVISION
    )
    assert not settled_report.blocked
    assert settled_report.unready_edges == ()
    assert settled_report.excused_outcomes == {"run-1/TS-1"}
    assert settled_report.unwaived_outcomes == frozenset()
