"""The gate evaluator — reporting a guarded action as blocked.

While any condition of a gate is unmet, the action that gate guards is blocked
(SEG-SYS-006). Iteration 0 implements the **package gate** only, whose output
is the coverage report: structural gaps reported at the leaf where coverage is
actually missing rather than up the ancestor chain, the worklist of every
in-scope strong edge that is not active — including pending and broken, which
affirmation cannot resolve — and the overall status. A stale-outcomes listing
joins the report once the proof generator's staleness exclusion
(SEG-SREQ-040) is realized; the record vocabulary does not yet carry what
staleness would be computed from, so there is nothing this gate could compute
one against today.

The commit gate and the release gate are deferred past iteration 0: the commit
gate's conditions are all extraction conditions and record production is
deferred, and the release gate needs a sealed package and a release to check.

The gate judges and reports; it does not enforce. It takes the graph the
caller built as its scope and does no scope collection of its own — walking
strong edges to decide what is reachable is the proof generator's item
(SEG-SREQ-036); iteration 0 hands it the whole graph. Every finding becomes a
:class:`~affirmatrix.diagnostics.Diagnostic`, and :class:`CoverageReport`'s
``diagnostics`` and ``blocked`` are derived views over the same four typed
findings — never a second telling that could disagree with the first. Every
gate condition here — an unready edge, a coverage gap, an empty design set —
is a warning: it blocks the package, never a commit, because a
commit-blocking error arrives only with the extractors. A discarded outcome is
informational: visible in the report, blocking nothing.

A coverage gap is attributed to the requirement whose *own* direct coverage
fails, never to an ancestor because a descendant failed, by re-asking
:mod:`affirmatrix.satisfaction`'s leaf and non-leaf predicates with a
requirement's own refiners forced satisfied — which isolates exactly the
edges that requirement itself carries. A scope whose design set is empty — no
Requirement node in it at all — is reported blocked rather than vacuously
ready (SEG-SREQ-045): sealing emptiness is a gate decision, not a hashing one.

**The honesty gap, named.** A failed-but-unwaived test outcome alone does not
block this gate yet. SEG-SREQ-042 through SEG-SREQ-045 say nothing about
waivers or outcome freshness, and no ratified requirement yet names what a
waiver must carry or who may grant one. Coverage here means only what
:func:`affirmatrix.satisfaction.leaf_satisfied` already means — an evidence
outcome recorded as passing — so a failing outcome behind an otherwise active
edge is invisible to this report until that vocabulary exists.

Iteration-0 backlog item B15.
"""

from __future__ import annotations

from dataclasses import dataclass

from affirmatrix import satisfaction, taxonomy
from affirmatrix.diagnostics import Diagnostic, Severity
from affirmatrix.graph import Graph
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord

_REQUIREMENT = "Requirement"
_REFINES = "Refines"


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """The package gate's report: four typed findings, and two derived views.

    ``unready_edges``, ``coverage_gaps``, ``discarded_outcomes`` and
    ``design_set_empty`` are what :func:`package_gate` actually found.
    ``diagnostics`` and ``blocked`` are computed from those four and nothing
    else, so the report cannot disagree with itself about what blocks: there
    is only one place severity is decided, and both views read it from there.
    """

    unready_edges: tuple[EdgeRecord, ...]
    coverage_gaps: frozenset[str]
    discarded_outcomes: frozenset[str]
    design_set_empty: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "unready_edges", tuple(self.unready_edges))
        object.__setattr__(self, "coverage_gaps", frozenset(self.coverage_gaps))
        object.__setattr__(self, "discarded_outcomes", frozenset(self.discarded_outcomes))

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Every typed finding, as one flat sequence of diagnostics.

        Gate conditions — an unready edge, a coverage gap, an empty design
        set — are all :attr:`~affirmatrix.diagnostics.Severity.WARNING`. A
        discarded outcome is :attr:`~affirmatrix.diagnostics.Severity.INFO`.
        """
        return (
            tuple(
                Diagnostic(
                    severity=Severity.WARNING,
                    condition=f"strong edge is {edge.state.value}, not active",
                    subject=_edge_subject(edge),
                )
                for edge in self.unready_edges
            )
            + tuple(
                Diagnostic(
                    severity=Severity.WARNING,
                    condition="the requirement's own coverage is incomplete",
                    subject=local_id,
                )
                for local_id in sorted(self.coverage_gaps)
            )
            + (
                (
                    Diagnostic(
                        severity=Severity.WARNING,
                        condition="the design set is empty",
                        subject="the scope",
                    ),
                )
                if self.design_set_empty
                else ()
            )
            + tuple(
                Diagnostic(
                    severity=Severity.INFO,
                    condition="outcome discarded as incomplete evidence",
                    subject=local_id,
                )
                for local_id in sorted(self.discarded_outcomes)
            )
        )

    @property
    def blocked(self) -> bool:
        """Whether this scope is blocked: any diagnostic whose severity blocks the package.

        :implements: SEG-SREQ-042
        """
        return any(diagnostic.severity.blocks_package for diagnostic in self.diagnostics)


def package_gate(graph: Graph) -> CoverageReport:
    """Evaluate the package gate over a scope, judging and reporting only.

    :implements: SEG-SREQ-043
    :implements: SEG-SREQ-044
    :implements: SEG-SREQ-045

    ``graph`` is the scope the caller built; the gate does no scope collection
    of its own, so an iteration-0 caller hands it the whole graph and a later
    caller a reachability subset through the same function — scope collection
    (SEG-SREQ-036) is the proof generator's to build, not this one's.
    """
    requirements = graph.nodes_of_kind(_REQUIREMENT)
    verdict = satisfaction.evaluate(graph)
    return CoverageReport(
        unready_edges=_unready_edges(graph),
        coverage_gaps=_coverage_gaps(graph, requirements),
        discarded_outcomes=verdict.discarded_outcomes,
        design_set_empty=not requirements,
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


def _edge_subject(edge: EdgeRecord) -> str:
    """One edge, named for a diagnostic's subject."""
    return f"{edge.from_id} -> {edge.to_id} ({edge.kind})"


__all__ = ["CoverageReport", "package_gate"]
