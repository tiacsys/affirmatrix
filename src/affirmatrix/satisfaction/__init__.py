"""The satisfaction evaluator — requirement coverage by transitive closure.

A pure, deterministic, side-effect-free predicate over the typed graph, behind
one interface: evaluation repeats (SEG-SREQ-009) and leaves the graph unchanged
(SEG-SREQ-010). The leaf and non-leaf rules (SEG-SREQ-006, SEG-SREQ-007) are
written as small named predicates rather than woven into imperative gate code,
so that a user-definable satisfaction rule would be a substitution here rather
than a rewrite everywhere.

Coverage is evaluated over the whole graph, never a partial scope
(SEG-SREQ-008): a parent cannot be declared satisfied while a child sits
outside the window being examined. The answer is a :class:`Verdict` — a value,
not a view — mapping every requirement to satisfied or not, alongside the
outcomes that were discarded on the way there.

Two boundaries worth stating, because the prototype crossed both:

* **Staleness is not a satisfaction concern.** A stale outcome is *discarded*
  when a package is generated, and blocks only if its removal opens a gap; it
  is not a coverage gap here.
* **An outcome counts as evidence only if it both confirms a specification and
  witnesses an implementation**; an incomplete outcome is discarded, not
  failed. Discarding is not forgiving — it becomes a gap wherever it leaves a
  specification uncovered — and it is not silent: every discarded outcome is
  named in the verdict.

The evaluator may assume an acyclic refines relation: cycle *reporting* is the
graph builder's (SEG-SREQ-004), so the recursion terminates by precondition.

Iteration-0 backlog item B12 (SEG-SYS-002 and its decomposition).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from affirmatrix.graph import Graph
from affirmatrix.records import EdgeRecord, LinkState, TestResult

_REQUIREMENT = "Requirement"
_TEST_OUTCOME = "TestOutcome"
_REFINES = "Refines"
_VERIFIES = "Verifies"
_IMPLEMENTS = "Implements"
_CONFIRMS = "Confirms"
_WITNESSES = "Witnesses"


@dataclass(frozen=True, slots=True)
class Verdict:
    """One evaluation's answer for every requirement in the graph.

    ``satisfaction`` maps each requirement's local identifier to its verdict —
    every requirement node, never a subset (SEG-SREQ-008). It carries no
    per-requirement reasons: attributing a gap to the leaf where coverage is
    missing is the gate evaluator's report to build, and a second telling of
    it here could disagree with the first.

    ``discarded_outcomes`` names every outcome set aside as incomplete, so the
    gap a discard opens is visible in the verdict rather than inferred from a
    leaf that went unsatisfied for no stated reason.
    """

    satisfaction: Mapping[str, bool]
    discarded_outcomes: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "satisfaction", MappingProxyType(dict(self.satisfaction)))
        object.__setattr__(self, "discarded_outcomes", frozenset(self.discarded_outcomes))

    def is_satisfied(self, local_id: str) -> bool:
        """This requirement's verdict, or ``KeyError`` if there is no such requirement.

        Raising is deliberate: answering ``False`` for an identifier the graph
        never held would make a typo indistinguishable from a real gap.
        """
        return self.satisfaction[local_id]


def evaluate(graph: Graph) -> Verdict:
    """Every requirement's satisfaction, decided over the whole graph.

    :implements: SEG-SREQ-008
    :implements: SEG-SREQ-009
    :implements: SEG-SREQ-010

    Iterative post-order over the refines relation, memoised across roots: a
    shared child is judged once, and a deep decomposition cannot exhaust the
    interpreter stack — the depth here is the caller's decomposition, not
    ours. Termination rests on the builder's acyclicity guarantee
    (SEG-SREQ-004). The function only reads: determinism and graph
    immutability are consequences of there being nothing else it does.

    A graph with no requirement nodes yields an empty verdict rather than a
    refusal — an empty scope is the gate evaluator's alarm to raise
    (SEG-SREQ-045), not this component's.
    """
    requirement_ids = frozenset(node.local_id for node in graph.nodes_of_kind(_REQUIREMENT))
    verdicts: dict[str, bool] = {}
    for root_id in sorted(requirement_ids):
        _judge_subtree(graph, root_id, requirement_ids, verdicts)
    return Verdict(satisfaction=verdicts, discarded_outcomes=_discarded(graph))


def leaf_satisfied(graph: Graph, local_id: str) -> bool:
    """The leaf rule: a requirement nothing refines is satisfied when, and
    only when, it carries at least one active verifies edge, at least one
    active implements edge, and every test specification verifying it has a
    passing outcome.

    :implements: SEG-SREQ-006

    Every specification a verifies edge names is a verifying specification,
    whatever the edge's state: the state gates whether the edge counts as
    coverage, not whether the specification it names owes evidence. Releasing
    a specification because its edge went suspect would let suspicion quietly
    shrink what the leaf must show.
    """
    verifying = graph.incoming(local_id, _VERIFIES)
    if not _any_active(verifying):
        return False
    if not _any_active(graph.incoming(local_id, _IMPLEMENTS)):
        return False
    specifications = {edge.from_id for edge in verifying}
    return all(_has_passing_outcome(graph, spec_id) for spec_id in specifications)


def non_leaf_satisfied(
    graph: Graph, local_id: str, child_satisfaction: Mapping[str, bool]
) -> bool:
    """The non-leaf rule: a requirement something refines is satisfied when,
    and only when, every requirement refining it is satisfied and every
    verifies or implements edge it carries is active.

    :implements: SEG-SREQ-007

    The children's verdicts are taken as given, which is what keeps this a
    predicate rather than a traversal. A refiner absent from those verdicts —
    a node that is not a requirement, say — counts as unsatisfied, never as
    skipped: a parent must not come out green because one of its declared
    children could not be judged.
    """
    children = _refiners(graph, local_id)
    if not all(child_satisfaction.get(child, False) for child in children):
        return False
    direct = graph.incoming(local_id, _VERIFIES) + graph.incoming(local_id, _IMPLEMENTS)
    return all(_active(edge) for edge in direct)


def _judge_subtree(
    graph: Graph,
    root_id: str,
    requirement_ids: frozenset[str],
    verdicts: dict[str, bool],
) -> None:
    """Judge one requirement and everything under it, iteratively, into ``verdicts``."""
    stack = [root_id]
    while stack:
        current = stack[-1]
        if current in verdicts:
            stack.pop()
            continue
        waiting = [
            child
            for child in _refiners(graph, current)
            if child in requirement_ids and child not in verdicts
        ]
        if waiting:
            stack.extend(sorted(waiting))
            continue
        stack.pop()
        if _refiners(graph, current):
            verdicts[current] = non_leaf_satisfied(graph, current, verdicts)
        else:
            verdicts[current] = leaf_satisfied(graph, current)


def _refiners(graph: Graph, local_id: str) -> frozenset[str]:
    """The nodes that declare themselves refinements of this requirement."""
    return frozenset(edge.from_id for edge in graph.incoming(local_id, _REFINES))


def _any_active(edges: Iterable[EdgeRecord]) -> bool:
    return any(_active(edge) for edge in edges)


def _active(edge: EdgeRecord) -> bool:
    """Whether this edge counts as coverage: active, and nothing else.

    Every other state fails the same test the same way — pending blocks
    satisfaction exactly like suspicion, by not being active.
    """
    return edge.state is LinkState.ACTIVE


def _has_passing_outcome(graph: Graph, spec_id: str) -> bool:
    """Whether some evidence-valid outcome confirming this spec passed."""
    return any(
        _is_evidence(graph, edge.from_id) and _passing(graph, edge.from_id)
        for edge in graph.incoming(spec_id, _CONFIRMS)
    )


def _is_evidence(graph: Graph, outcome_id: str) -> bool:
    """Whether an outcome is complete: it confirms a specification *and*
    witnesses an implementation.

    Presence of both edges, whatever their state: the evidence edges are
    machine-derived rather than affirmed, and suspicion deliberately stops at
    the evidence boundary, so an activeness test here would demand
    affirmations nothing in the process produces.
    """
    return bool(graph.outgoing(outcome_id, _CONFIRMS)) and bool(
        graph.outgoing(outcome_id, _WITNESSES)
    )


def _passing(graph: Graph, outcome_id: str) -> bool:
    """Whether this outcome records a pass.

    An outcome the graph has no node for — a confirms edge dangling from an
    absent record — is a claim with no result to read, and not passing.
    """
    try:
        node = graph.node(outcome_id)
    except KeyError:
        return False
    return node.result is TestResult.PASSED


def _discarded(graph: Graph) -> frozenset[str]:
    """Every incomplete outcome in the graph, wherever it hangs.

    Whole-graph like the verdict itself: an incomplete outcome on a
    specification nobody verifies yet is still worth naming, because the next
    verifies edge would otherwise inherit an invisible gap.
    """
    return frozenset(
        node.local_id
        for node in graph.nodes_of_kind(_TEST_OUTCOME)
        if not _is_evidence(graph, node.local_id)
    )


__all__ = ["Verdict", "evaluate", "leaf_satisfied", "non_leaf_satisfied"]
