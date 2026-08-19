"""The satisfaction evaluator (SEG-SREQ-006, -007, -008, -009, -010).

The two rules under test answer, for every requirement in the graph, the one
question the rest of the engine asks about it. The edge cases are where the
honesty lives: an orphan is not vacuously satisfied, a pending edge blocks
exactly like a suspect one, a failing outcome is not a passing one, and an
incomplete outcome is discarded loudly — named in the verdict — rather than
counted quietly or dropped in silence.

Fixture graphs are built in memory from literal records; nothing here touches
a real store.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from affirmatrix import graph, records, satisfaction
from affirmatrix.records import LinkState, TestResult

AFFIRMED = hashlib.sha256(b"affirmed against this").digest()

NON_ACTIVE_STATES = (
    LinkState.PENDING,
    LinkState.DIRECTLY_OUTDATED,
    LinkState.TRANSITIVELY_SUSPECT,
    LinkState.DOUBLY_OUTDATED,
    LinkState.BROKEN,
)


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def build(nodes=(), edges=()) -> graph.Graph:
    return graph.build(Source(nodes, edges))


def anchors(names: tuple[str, ...]) -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(name.encode("utf-8")).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def requirement(local_id: str) -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors(("contentHash",)))


def implementation(local_id: str) -> records.NodeRecord:
    return records.NodeRecord(local_id, "Implementation", anchors(("apiHash", "bodyHash")))


def specification(local_id: str) -> records.NodeRecord:
    return records.NodeRecord(local_id, "TestSpecification", anchors(("specHash", "implHash")))


def outcome(local_id: str, result: TestResult = TestResult.PASSED) -> records.NodeRecord:
    return records.NodeRecord(local_id, "TestOutcome", anchors(("contentHash",)), result=result)


def waiver(
    local_id: str, expiry: date = date(2099, 1, 1), approver: str = "A. Reviewer"
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "Waiver", anchors(("contentHash",)), expiry=expiry, approver=approver
    )


def edge(
    kind: str, from_id: str, to_id: str, state: LinkState = LinkState.ACTIVE
) -> records.EdgeRecord:
    edge_hash = None if state is LinkState.PENDING else AFFIRMED
    return records.EdgeRecord(from_id, to_id, kind, state, edge_hash)


def refines(child: str, parent: str) -> records.EdgeRecord:
    return edge("Refines", child, parent, LinkState.PENDING)


def verifies(spec: str, req: str, state: LinkState = LinkState.ACTIVE) -> records.EdgeRecord:
    return edge("Verifies", spec, req, state)


def implements(impl: str, req: str, state: LinkState = LinkState.ACTIVE) -> records.EdgeRecord:
    return edge("Implements", impl, req, state)


def confirms(outcome_id: str, spec: str) -> records.EdgeRecord:
    return edge("Confirms", outcome_id, spec, LinkState.PENDING)


def witnesses(outcome_id: str, impl: str) -> records.EdgeRecord:
    return edge("Witnesses", outcome_id, impl, LinkState.PENDING)


def excuses(
    waiver_id: str, outcome_id: str, state: LinkState = LinkState.PENDING
) -> records.EdgeRecord:
    """An excusing edge: Waiver to TestOutcome (``edge-excuses.schema.json``).

    Evidence, like ``Confirms`` and ``Witnesses``: presence is what counts,
    never the state, which the ``state`` parameter exists to let a test vary.
    """
    return edge("Excuses", waiver_id, outcome_id, state)


def covered_leaf(
    local_id: str, result: TestResult = TestResult.PASSED
) -> tuple[list[records.NodeRecord], list[records.EdgeRecord]]:
    """A leaf with the full evidence chain: spec, implementation, outcome."""
    spec_id = f"{local_id}/spec"
    impl_id = f"{local_id}/impl"
    outcome_id = f"{local_id}/outcome"
    nodes = [
        requirement(local_id),
        specification(spec_id),
        implementation(impl_id),
        outcome(outcome_id, result),
    ]
    edges = [
        verifies(spec_id, local_id),
        implements(impl_id, local_id),
        confirms(outcome_id, spec_id),
        witnesses(outcome_id, impl_id),
    ]
    return nodes, edges


# ── The leaf rule (SEG-SREQ-006) ────────────────────────────────────────────


def test_a_fully_covered_leaf_is_satisfied() -> None:
    nodes, edges = covered_leaf("R")
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("R")


def test_a_leaf_with_no_verifies_edge_is_unsatisfied() -> None:
    nodes = [requirement("R"), implementation("I")]
    verdict = satisfaction.evaluate(build(nodes, [implements("I", "R")]))
    assert not verdict.is_satisfied("R")


def test_a_leaf_with_no_implements_edge_is_unsatisfied() -> None:
    nodes, edges = covered_leaf("R")
    without_implements = [e for e in edges if e.kind != "Implements"]
    verdict = satisfaction.evaluate(build(nodes, without_implements))
    assert not verdict.is_satisfied("R")


@pytest.mark.parametrize("state", NON_ACTIVE_STATES, ids=lambda state: state.value)
def test_every_non_active_verifies_edge_fails_the_active_test(state: LinkState) -> None:
    """Pending blocks satisfaction exactly like suspicion: by not being active."""
    nodes, edges = covered_leaf("R")
    demoted = [verifies("R/spec", "R", state) if e.kind == "Verifies" else e for e in edges]
    verdict = satisfaction.evaluate(build(nodes, demoted))
    assert not verdict.is_satisfied("R")


@pytest.mark.parametrize("state", NON_ACTIVE_STATES, ids=lambda state: state.value)
def test_every_non_active_implements_edge_fails_the_active_test(state: LinkState) -> None:
    nodes, edges = covered_leaf("R")
    demoted = [implements("R/impl", "R", state) if e.kind == "Implements" else e for e in edges]
    verdict = satisfaction.evaluate(build(nodes, demoted))
    assert not verdict.is_satisfied("R")


def test_a_verifying_spec_with_no_outcome_blocks_its_leaf() -> None:
    nodes, edges = covered_leaf("R")
    nodes.append(specification("S2"))
    edges.append(verifies("S2", "R"))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R")


@pytest.mark.parametrize(
    "result", (TestResult.FAILED, TestResult.ERROR, TestResult.SKIPPED), ids=lambda r: r.value
)
def test_an_outcome_that_did_not_pass_is_not_a_passing_outcome(result: TestResult) -> None:
    """The rule reads the recorded result; existence of an execution is not it."""
    nodes, edges = covered_leaf("R", result=result)
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R")


def test_a_spec_on_a_non_active_verifies_edge_still_owes_a_passing_outcome() -> None:
    """Every specification a verifies edge names is a verifying specification.

    The edge's state gates whether it counts as coverage; it does not release
    the named specification from the requirement's evidence. Releasing it would
    let a suspect edge quietly shrink what the leaf owes.
    """
    nodes, edges = covered_leaf("R")
    nodes.append(specification("S2"))
    edges.append(verifies("S2", "R", LinkState.PENDING))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R")


def test_an_orphan_requirement_is_unsatisfied_not_vacuously_satisfied() -> None:
    """No children and no coverage is a structural gap, not an empty obligation."""
    verdict = satisfaction.evaluate(build([requirement("R")]))
    assert not verdict.is_satisfied("R")


# ── Excusal by waiver — the universal that closed the existential hole ─────


def test_one_passing_outcome_beside_an_unwaived_failing_one_no_longer_satisfies() -> None:
    """The hole SEG-SREQ-006's amendment closes: the old existential wording
    ("at least one confirming outcome passed") let this pass; the universal
    does not."""
    nodes, edges = covered_leaf("R")
    nodes.append(outcome("R/outcome2", result=TestResult.FAILED))
    edges.append(confirms("R/outcome2", "R/spec"))
    edges.append(witnesses("R/outcome2", "R/impl"))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R")


def test_a_failing_outcome_excused_by_a_present_waiver_satisfies() -> None:
    nodes, edges = covered_leaf("R", result=TestResult.FAILED)
    nodes.append(waiver("WVR-1"))
    edges.append(excuses("WVR-1", "R/outcome"))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("R")


def test_excusal_is_counted_whatever_the_excusing_edges_own_state() -> None:
    """Excusal is presence of the waiver, never the excusal edge's state — an
    Excuses edge is evidence and can never be affirmed active, but nothing
    here should care either way."""
    nodes, edges = covered_leaf("R", result=TestResult.FAILED)
    nodes.append(waiver("WVR-1"))
    edges.append(excuses("WVR-1", "R/outcome", state=LinkState.ACTIVE))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("R")


def test_an_excusal_edge_whose_waiver_record_is_absent_excuses_nothing() -> None:
    """A dangling excusal: the edge exists, but no Waiver node backs it. The
    waiver itself must be present, reached through the edge, not the edge
    alone."""
    nodes, edges = covered_leaf("R", result=TestResult.FAILED)
    edges.append(excuses("WVR-MISSING", "R/outcome"))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R")


def test_a_direct_edges_outcome_never_governs_the_non_leaf_rule() -> None:
    """SEG-SREQ-007's amendment states what the code already did: verified
    here rather than assumed. A parent's own direct verifies edge names a
    specification whose only outcome failed unwaived — the non-leaf rule
    still only asks whether the edge is active, never whether that outcome
    passed. Calling the predicate directly, as
    ``test_the_non_leaf_rule_judges_against_the_verdicts_it_is_given`` already
    does, isolates the rule from ``evaluate``'s leaf/non-leaf dispatch."""
    sreq = requirement("P")
    spec = specification("P/spec")
    run = outcome("P/outcome", result=TestResult.FAILED)
    nodes = [sreq, spec, run]
    edges = [
        verifies("P/spec", "P"),
        confirms("P/outcome", "P/spec"),
    ]
    built = build(nodes, edges)
    assert satisfaction.non_leaf_satisfied(built, "P", {})


# ── The discard rule: incomplete outcomes ───────────────────────────────────


def test_an_outcome_that_confirms_without_witnessing_is_discarded() -> None:
    nodes, edges = covered_leaf("R")
    without_witnesses = [e for e in edges if e.kind != "Witnesses"]
    verdict = satisfaction.evaluate(build(nodes, without_witnesses))
    assert not verdict.is_satisfied("R")
    assert "R/outcome" in verdict.discarded_outcomes


def test_an_outcome_that_witnesses_without_confirming_is_discarded() -> None:
    nodes, edges = covered_leaf("R")
    without_confirms = [e for e in edges if e.kind != "Confirms"]
    verdict = satisfaction.evaluate(build(nodes, without_confirms))
    assert not verdict.is_satisfied("R")
    assert "R/outcome" in verdict.discarded_outcomes


def test_a_discarded_outcome_beside_a_complete_one_opens_no_gap() -> None:
    """Discarding is not failing: the complete outcome still carries the spec."""
    nodes, edges = covered_leaf("R")
    nodes.append(outcome("O2"))
    edges.append(confirms("O2", "R/spec"))  # confirms only — no witnesses edge
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("R")
    assert verdict.discarded_outcomes == frozenset({"O2"})


def test_every_incomplete_outcome_is_named_wherever_it_hangs() -> None:
    """Visibility does not depend on a requirement happening to need the outcome."""
    nodes = [specification("S"), outcome("O")]
    verdict = satisfaction.evaluate(build(nodes, [confirms("O", "S")]))
    assert verdict.discarded_outcomes == frozenset({"O"})


def test_a_complete_outcomes_evidence_is_not_discarded() -> None:
    nodes, edges = covered_leaf("R")
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.discarded_outcomes == frozenset()


# ── The non-leaf rule (SEG-SREQ-007) ────────────────────────────────────────


def test_a_parent_of_satisfied_children_is_satisfied() -> None:
    nodes_a, edges_a = covered_leaf("A")
    nodes_b, edges_b = covered_leaf("B")
    nodes = [requirement("P"), *nodes_a, *nodes_b]
    edges = [refines("A", "P"), refines("B", "P"), *edges_a, *edges_b]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("P")


def test_one_unsatisfied_child_poisons_the_parent() -> None:
    nodes_a, edges_a = covered_leaf("A")
    nodes = [requirement("P"), requirement("B"), *nodes_a]
    edges = [refines("A", "P"), refines("B", "P"), *edges_a]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("P")


def test_poison_reaches_every_ancestor() -> None:
    """Transitive closure in the failing direction: no ancestor may stay green."""
    nodes = [requirement(local_id) for local_id in ("TOP", "MID", "LEAF")]
    edges = [refines("MID", "TOP"), refines("LEAF", "MID")]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("LEAF")
    assert not verdict.is_satisfied("MID")
    assert not verdict.is_satisfied("TOP")


def test_a_deep_refines_chain_evaluates_without_exhausting_the_stack() -> None:
    """The depth is the caller's decomposition, not the interpreter's stack."""
    depth = 2000
    nodes = [requirement(f"R{index}") for index in range(depth)]
    edges = [refines(f"R{index + 1}", f"R{index}") for index in range(depth - 1)]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("R0")
    assert len(verdict.satisfaction) == depth


def test_a_pending_direct_edge_blocks_an_otherwise_satisfied_parent() -> None:
    """Enforce-if-present: a direct edge a parent carries must be active."""
    nodes_a, edges_a = covered_leaf("A")
    nodes = [requirement("P"), implementation("PI"), *nodes_a]
    edges = [refines("A", "P"), implements("PI", "P", LinkState.PENDING), *edges_a]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert not verdict.is_satisfied("P")


def test_an_active_direct_edge_leaves_the_parent_satisfied() -> None:
    nodes_a, edges_a = covered_leaf("A")
    nodes = [requirement("P"), implementation("PI"), *nodes_a]
    edges = [refines("A", "P"), implements("PI", "P"), *edges_a]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("P")


def test_a_diamond_child_serves_both_parents() -> None:
    nodes_a, edges_a = covered_leaf("A")
    nodes = [requirement("P1"), requirement("P2"), *nodes_a]
    edges = [refines("A", "P1"), refines("A", "P2"), *edges_a]
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert verdict.is_satisfied("P1")
    assert verdict.is_satisfied("P2")


def test_a_non_requirement_refiner_poisons_its_parent() -> None:
    """A refiner that cannot be satisfied is unsatisfied, never silently skipped."""
    nodes = [requirement("P"), implementation("I")]
    verdict = satisfaction.evaluate(build(nodes, [refines("I", "P")]))
    assert not verdict.is_satisfied("P")


# ── Whole graph (SEG-SREQ-008) ──────────────────────────────────────────────


def test_the_verdict_covers_every_requirement_and_only_requirements() -> None:
    """Never a subset: a disconnected requirement is judged, not overlooked."""
    nodes, edges = covered_leaf("R")
    nodes.append(requirement("ADRIFT"))
    verdict = satisfaction.evaluate(build(nodes, edges))
    assert set(verdict.satisfaction) == {"R", "ADRIFT"}
    assert not verdict.is_satisfied("ADRIFT")


# ── Verdicts repeat (SEG-SREQ-009) ──────────────────────────────────────────


def test_two_evaluations_of_one_graph_yield_equal_verdicts() -> None:
    nodes_a, edges_a = covered_leaf("A")
    nodes = [requirement("P"), *nodes_a]
    edges = [refines("A", "P"), *edges_a]
    built = build(nodes, edges)
    assert satisfaction.evaluate(built) == satisfaction.evaluate(built)


# ── Evaluation leaves the graph unchanged (SEG-SREQ-010) ────────────────────


def test_evaluation_leaves_the_graph_unchanged() -> None:
    nodes, edges = covered_leaf("R")
    built = build(nodes, edges)
    node_ids_before = built.node_ids()
    edges_before = built.edges
    states_before = [e.state for e in built.edges]
    satisfaction.evaluate(built)
    assert built.node_ids() == node_ids_before
    assert built.edges is edges_before
    assert [e.state for e in built.edges] == states_before


def test_the_verdict_is_a_value_not_a_handle_on_the_evaluation() -> None:
    verdict = satisfaction.evaluate(build([requirement("R")]))
    with pytest.raises(TypeError):
        verdict.satisfaction["R"] = True  # type: ignore[index]


# ── Posture: empty domains and unknown identifiers ──────────────────────────


def test_an_empty_graph_yields_an_empty_verdict() -> None:
    """Emptiness is the gate's alarm to raise, not the evaluator's refusal."""
    verdict = satisfaction.evaluate(build())
    assert verdict.satisfaction == {}
    assert verdict.discarded_outcomes == frozenset()


def test_a_graph_with_no_requirement_nodes_yields_an_empty_verdict() -> None:
    nodes = [specification("S"), implementation("I")]
    verdict = satisfaction.evaluate(build(nodes))
    assert verdict.satisfaction == {}


def test_an_unknown_identifier_is_reported_rather_than_answered() -> None:
    verdict = satisfaction.evaluate(build([requirement("R")]))
    with pytest.raises(KeyError):
        verdict.is_satisfied("NO-SUCH-REQUIREMENT")


# ── The rules stand alone as named predicates ───────────────────────────────


def test_the_leaf_rule_is_a_predicate_of_its_own() -> None:
    nodes, edges = covered_leaf("R")
    assert satisfaction.leaf_satisfied(build(nodes, edges), "R")


def test_the_non_leaf_rule_judges_against_the_verdicts_it_is_given() -> None:
    nodes = [requirement("P"), requirement("A")]
    built = build(nodes, [refines("A", "P")])
    assert satisfaction.non_leaf_satisfied(built, "P", {"A": True})
    assert not satisfaction.non_leaf_satisfied(built, "P", {"A": False})
    assert not satisfaction.non_leaf_satisfied(built, "P", {})
