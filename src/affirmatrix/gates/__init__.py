"""The gate evaluator — reporting a guarded action as blocked.

While any condition of a gate is unmet, the action that gate guards is blocked
(SEG-SYS-006). Iteration 0 implements the **package gate** only, whose output
is the coverage report: structural gaps reported at the leaf where coverage is
actually missing rather than up the ancestor chain, the worklist of every
in-scope strong edge that is not active — including pending and broken, which
affirmation cannot resolve — a stale-outcomes listing, and the overall status.

The commit gate and the release gate are deferred past iteration 0: the commit
gate's conditions are all extraction conditions and record production is
deferred, and the release gate needs a sealed package and a release to check.

The gate judges and reports; it does not enforce. It takes the graph the
caller built as its scope and does no scope collection of its own — walking
strong edges to decide what is reachable is the proof generator's item
(SEG-SREQ-036); iteration 0 hands it the whole graph. Every finding becomes a
:class:`~affirmatrix.diagnostics.Diagnostic`, and :class:`CoverageReport`'s
``diagnostics`` and ``blocked`` are derived views over the same seven typed
findings — never a second telling that could disagree with the first. Every
gate condition here — an unready edge, a coverage gap, an empty design set —
is a warning: it blocks the package, never a commit, because a
commit-blocking error arrives only with the extractors. A discarded outcome
and a stale one are both informational: visible in the report, blocking
nothing by themselves.

**The closed condition vocabulary (SEG-SREQ-064, SEG-SREQ-065).** Every
diagnostic this gate reports carries one of seven fixed :class:`Condition`
values — never an occurrence-specific sentence built on the fly. Anything
that varies from one occurrence of the same condition to the next — which
state an edge is in, say — travels on
:attr:`~affirmatrix.diagnostics.Diagnostic.detail` instead, kept apart so the
condition itself stays a member of a set a reader can enumerate once and
recognise everywhere. Not every finding has such a detail to give: the stale
finding names only the outcome, because the two revisions being compared
live elsewhere already — the recorded one on the outcome record, the current
one in the caller's own input — and repeating either here would be a second
telling of a fact this report does not otherwise hold. The set lives here,
in the component the two requirements name, rather than in
:mod:`affirmatrix.diagnostics`: that module is shared, occurrence-free
vocabulary with no component's conditions in it, never a requirement
subject, and declaring a gate's own closed set there would make it one.

A coverage gap is attributed to the requirement whose *own* direct coverage
fails, never to an ancestor because a descendant failed, by re-asking
:mod:`affirmatrix.satisfaction`'s leaf and non-leaf predicates with a
requirement's own refiners forced satisfied — which isolates exactly the
edges that requirement itself carries. A scope whose design set is empty — no
Requirement node in it at all — is reported blocked rather than vacuously
ready (SEG-SREQ-045): sealing emptiness is a gate decision, not a hashing one.

**Staleness (SEG-SREQ-063, SEG-SREQ-067).** ``package_gate`` takes the
current revision of the implementation repository as an explicit keyword,
exactly like ``evaluation_date`` — an external input, never read from the
graph. A ``TestOutcome`` whose recorded revision differs is stale, and is cut
out of the graph before any other finding is computed: :meth:`Graph.restricted_to`
(already built for exactly this — the proof generator's scope cuts use it the
same way) removes the node and, with it, every edge that touched it, so
:mod:`affirmatrix.satisfaction` sees a graph with no stale outcome in it at
all and stays exactly as pure and revision-unaware as before — this gate
supplies it a *view*, not a revision-aware question. A stale-only
specification therefore reads as an ordinary coverage gap; a fresh sibling
outcome keeps it covered. The cut is uniform, not limited to coverage: a
stale outcome is equally absent from the waiver seam below, so it is reported
exactly once, as the stale finding, never doubled with a discard or a
non-passing finding for the same underlying reason. (Reading past
SEG-SREQ-063's own words, which speak only of judging the specification a
stale outcome confirms — deliberate, so one telling never disagrees with
another.)

**The waiver seam.** A non-passing outcome (the ``TestResult`` non-``PASSED``
set, uniformly — failed, error and skipped alike) is now a finding of its own
(SEG-SREQ-060, SEG-SREQ-061), independent of whether that outcome is
otherwise evidence-complete: it can double up with a
:attr:`~affirmatrix.diagnostics.Severity.INFO` discard finding on the same
outcome, which is deliberate rather than an oversight — the two findings
report different things that both happen to be true of one subject. Excusal
is resolved the way :mod:`affirmatrix.satisfaction` resolves it — presence of
a Waiver record reached through an incoming ``Excuses`` edge (Waiver to
TestOutcome, per ``case/schema/edge-excuses.schema.json``), never the edge's
own state — but this module asks the question itself rather than reusing
satisfaction's private predicate, so that a swappable satisfaction engine
never has to answer more than the two questions this gate actually borrows
(see the module's read for what those are).

**SEG-SREQ-059, only half realized.** A waiver is valid only when unexpired
*and* its approver is authorised — this gate checks only the first half. The
second needs a roster of authorised approvers that does not exist yet in any
ratified requirement, so this gate is not entitled to check it, and
SEG-SREQ-059 itself carries no ``:implements:`` marker anywhere in this
codebase: marking it would claim a check this code does not perform. Until an
authorisation roster is realized, an outcome excused by an unexpired waiver
from an unauthorised approver reads here as validly excused; that is the
residue, stated rather than hidden.

Iteration-0 backlog item B15.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from affirmatrix import satisfaction, taxonomy
from affirmatrix.diagnostics import Diagnostic, Severity
from affirmatrix.graph import Graph
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord, TestResult

_REQUIREMENT = "Requirement"
_REFINES = "Refines"
_TEST_OUTCOME = "TestOutcome"
_WAIVER = "Waiver"
_EXCUSES = "Excuses"


class Condition(StrEnum):
    """The closed vocabulary of every condition this gate can report (SEG-SREQ-064).

    One member per gate condition, occurrence-independent by construction —
    the varying part of an occurrence, an edge's own state, lives on
    :attr:`~affirmatrix.diagnostics.Diagnostic.detail` instead (SEG-SREQ-065);
    not every condition has such a detail to give. Declared here, not in
    :mod:`affirmatrix.diagnostics`: see the module docstring for why owning
    the set is this component's, not the shared vocabulary's.
    """

    UNREADY_EDGE = "strong edge not active"
    COVERAGE_GAP = "the requirement's own coverage is incomplete"
    EMPTY_DESIGN_SET = "the design set is empty"
    UNWAIVED_NON_PASSING_OUTCOME = "non-passing outcome is not excused by a valid waiver"
    EXCUSED_NON_PASSING_OUTCOME = "non-passing outcome is excused by a valid waiver"
    DISCARDED_OUTCOME = "outcome discarded as incomplete evidence"
    STALE_OUTCOME = "outcome's recorded revision differs from the current revision"


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """The package gate's report: seven typed findings, and two derived views.

    ``unready_edges``, ``coverage_gaps``, ``stale_outcomes``,
    ``discarded_outcomes``, ``unwaived_outcomes``, ``excused_outcomes`` and
    ``design_set_empty`` are what :func:`package_gate` actually found.
    ``diagnostics`` and ``blocked`` are computed from those seven and nothing
    else, so the report cannot disagree with itself about what blocks: there
    is only one place severity is decided, and both views read it from there.
    """

    unready_edges: tuple[EdgeRecord, ...]
    coverage_gaps: frozenset[str]
    stale_outcomes: frozenset[str]
    discarded_outcomes: frozenset[str]
    unwaived_outcomes: frozenset[str]
    excused_outcomes: frozenset[str]
    design_set_empty: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "unready_edges", tuple(self.unready_edges))
        object.__setattr__(self, "coverage_gaps", frozenset(self.coverage_gaps))
        object.__setattr__(self, "stale_outcomes", frozenset(self.stale_outcomes))
        object.__setattr__(self, "discarded_outcomes", frozenset(self.discarded_outcomes))
        object.__setattr__(self, "unwaived_outcomes", frozenset(self.unwaived_outcomes))
        object.__setattr__(self, "excused_outcomes", frozenset(self.excused_outcomes))

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Every typed finding, as one flat sequence of diagnostics.

        Gate conditions — an unready edge, a coverage gap, an empty design
        set, an unwaived non-passing outcome — are all
        :attr:`~affirmatrix.diagnostics.Severity.WARNING`. A discarded
        outcome, a stale outcome, and a validly excused non-passing outcome
        are all :attr:`~affirmatrix.diagnostics.Severity.INFO`. Every
        diagnostic's condition is one member of :class:`Condition`
        (SEG-SREQ-064); whatever varies by occurrence travels on ``detail``
        instead (SEG-SREQ-065).

        :implements: SEG-SREQ-060
        :implements: SEG-SREQ-061
        :implements: SEG-SREQ-064
        :implements: SEG-SREQ-065
        :implements: SEG-SREQ-067
        """
        return (
            tuple(
                Diagnostic(
                    severity=Severity.WARNING,
                    condition=Condition.UNREADY_EDGE,
                    subject=_edge_subject(edge),
                    detail=edge.state.value,
                )
                for edge in self.unready_edges
            )
            + tuple(
                Diagnostic(
                    severity=Severity.WARNING,
                    condition=Condition.COVERAGE_GAP,
                    subject=local_id,
                )
                for local_id in sorted(self.coverage_gaps)
            )
            + (
                (
                    Diagnostic(
                        severity=Severity.WARNING,
                        condition=Condition.EMPTY_DESIGN_SET,
                        subject="the scope",
                    ),
                )
                if self.design_set_empty
                else ()
            )
            + tuple(
                Diagnostic(
                    severity=Severity.WARNING,
                    condition=Condition.UNWAIVED_NON_PASSING_OUTCOME,
                    subject=local_id,
                )
                for local_id in sorted(self.unwaived_outcomes)
            )
            + tuple(
                Diagnostic(
                    severity=Severity.INFO,
                    condition=Condition.DISCARDED_OUTCOME,
                    subject=local_id,
                )
                for local_id in sorted(self.discarded_outcomes)
            )
            + tuple(
                Diagnostic(
                    severity=Severity.INFO,
                    condition=Condition.EXCUSED_NON_PASSING_OUTCOME,
                    subject=local_id,
                )
                for local_id in sorted(self.excused_outcomes)
            )
            + tuple(
                Diagnostic(
                    severity=Severity.INFO,
                    condition=Condition.STALE_OUTCOME,
                    subject=local_id,
                )
                for local_id in sorted(self.stale_outcomes)
            )
        )

    @property
    def blocked(self) -> bool:
        """Whether this scope is blocked: any diagnostic whose severity blocks the package.

        :implements: SEG-SREQ-042
        """
        return any(diagnostic.severity.blocks_package for diagnostic in self.diagnostics)


def package_gate(graph: Graph, *, evaluation_date: date, current_revision: str) -> CoverageReport:
    """Evaluate the package gate over a scope, judging and reporting only.

    :implements: SEG-SREQ-043
    :implements: SEG-SREQ-044
    :implements: SEG-SREQ-045
    :implements: SEG-SREQ-063

    ``graph`` is the scope the caller built; the gate does no scope collection
    of its own, so an iteration-0 caller hands it the whole graph and a later
    caller a reachability subset through the same function — scope collection
    (SEG-SREQ-036) is the proof generator's to build, not this one's.

    ``evaluation_date`` is the caller-supplied "today" a waiver's expiry is
    judged against (SEG-SREQ-059's expiry half). Required and never defaulted:
    a gate that read the system clock itself could not repeat its own verdict
    on a later call over the same graph, and the caller-supplied-metadata
    precedent the commitment layer already sets — an opaque value the caller
    provides rather than the layer discovering it — is exactly what keeps
    this function pure.

    ``current_revision`` is the same kind of explicit external input, never
    read from the graph: the current revision of the implementation
    repository, against which every ``TestOutcome``'s own recorded revision
    is compared. A stale outcome — recorded revision differing from this one
    — is cut out of ``graph`` before every other finding is computed, so it
    is absent for coverage and for the waiver seam alike and surfaces exactly
    once, as the stale finding (see the module docstring's staleness
    section).
    """
    stale = _stale_outcomes(graph, current_revision)
    judged = graph.restricted_to(graph.node_ids() - stale)
    requirements = judged.nodes_of_kind(_REQUIREMENT)
    verdict = satisfaction.evaluate(judged)
    unwaived, excused = _non_passing_outcomes(judged, evaluation_date)
    return CoverageReport(
        unready_edges=_unready_edges(judged),
        coverage_gaps=_coverage_gaps(judged, requirements),
        stale_outcomes=stale,
        discarded_outcomes=verdict.discarded_outcomes,
        unwaived_outcomes=unwaived,
        excused_outcomes=excused,
        design_set_empty=not requirements,
    )


def _stale_outcomes(graph: Graph, current_revision: str) -> frozenset[str]:
    """Every test outcome whose recorded revision differs from ``current_revision``.

    :implements: SEG-SREQ-063

    Asked of the full, unjudged graph — this is what :func:`package_gate`
    cuts *out* before it asks anything else, so the function must see the
    outcomes it is about to remove.
    """
    return frozenset(
        outcome.local_id
        for outcome in graph.nodes_of_kind(_TEST_OUTCOME)
        if outcome.revision != current_revision
    )


def _unready_edges(graph: Graph) -> tuple[EdgeRecord, ...]:
    """Every strong edge in scope that is not active, deterministically ordered.

    Evidence edges never appear: only :func:`taxonomy.propagating_edge_kinds`
    counts, and every one of the five non-active states is listed — pending
    and broken included, neither of which affirmation can resolve.
    """
    strong = taxonomy.propagating_edge_kinds()
    unready = [
        edge for edge in graph.edges if edge.kind in strong and edge.state is not LinkState.ACTIVE
    ]
    unready.sort(key=lambda edge: (edge.kind, edge.from_id, edge.to_id))
    return tuple(unready)


def _coverage_gaps(graph: Graph, requirements: tuple[NodeRecord, ...]) -> frozenset[str]:
    """Every requirement whose own direct coverage fails.

    Each requirement is judged on its own edges alone: a requirement with
    refiners has its children forced satisfied before asking
    :func:`~affirmatrix.satisfaction.non_leaf_satisfied`, which isolates
    exactly the direct verifies/implements edges this requirement itself
    carries — a descendant's own failure surfaces as that descendant's own
    gap and never climbs to an ancestor that carries none of its own.
    """
    gaps: set[str] = set()
    for requirement in requirements:
        refiners = _refiners(graph, requirement.local_id)
        covered = (
            satisfaction.non_leaf_satisfied(
                graph, requirement.local_id, dict.fromkeys(refiners, True)
            )
            if refiners
            else satisfaction.leaf_satisfied(graph, requirement.local_id)
        )
        if not covered:
            gaps.add(requirement.local_id)
    return frozenset(gaps)


def _refiners(graph: Graph, local_id: str) -> tuple[str, ...]:
    """The nodes that declare themselves refinements of this requirement."""
    return tuple(edge.from_id for edge in graph.incoming(local_id, _REFINES))


def _non_passing_outcomes(
    graph: Graph, evaluation_date: date
) -> tuple[frozenset[str], frozenset[str]]:
    """Every non-passing outcome, split by whether a valid waiver excuses it.

    "Non-passing" is the ``TestResult`` non-``PASSED`` set, uniformly — failed,
    error and skipped alike, whatever the outcome's own evidentiary
    completeness; that boundary belongs to :mod:`affirmatrix.satisfaction`'s
    discard rule, not to this one, so an outcome can appear here and among
    ``discarded_outcomes`` at once.
    """
    unwaived: set[str] = set()
    excused: set[str] = set()
    for outcome in graph.nodes_of_kind(_TEST_OUTCOME):
        if outcome.result is TestResult.PASSED:
            continue
        waiver = _excusing_waiver(graph, outcome.local_id)
        if waiver is not None and _waiver_unexpired(waiver, evaluation_date):
            excused.add(outcome.local_id)
        else:
            unwaived.add(outcome.local_id)
    return frozenset(unwaived), frozenset(excused)


def _excusing_waiver(graph: Graph, outcome_id: str) -> NodeRecord | None:
    """The Waiver record excusing this outcome, present in the graph, if any.

    Walks the outcome's incoming ``Excuses`` edges (Waiver to TestOutcome, per
    ``case/schema/edge-excuses.schema.json``) to the Waiver record each names.
    Presence through the edge, not the edge alone: an excusing edge whose
    Waiver record is absent from the graph excuses nothing, and the edge's own
    state is never read — it is evidence and can never be affirmed active.
    """
    for edge in graph.incoming(outcome_id, _EXCUSES):
        try:
            waiver = graph.node(edge.from_id)
        except KeyError:
            continue
        if waiver.kind == _WAIVER:
            return waiver
    return None


def _waiver_unexpired(waiver: NodeRecord, evaluation_date: date) -> bool:
    """SEG-SREQ-059's expiry half: valid only while not yet expired.

    Valid through its expiry date, inclusive: a waiver expiring on
    ``evaluation_date`` still excuses that day's evaluation.

    The approver-authorisation half is deferred until an authorisation roster
    exists; see the module's read. SEG-SREQ-059 stays unmarked here because
    this checks only half of what it demands.
    """
    return waiver.expiry >= evaluation_date


def _edge_subject(edge: EdgeRecord) -> str:
    """One edge, named for a diagnostic's subject."""
    return f"{edge.from_id} -> {edge.to_id} ({edge.kind})"


__all__ = ["Condition", "CoverageReport", "package_gate"]
