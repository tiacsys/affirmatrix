The package gate
=================

The affirmation recorder's page ends with a proposal on the working tree; this
page is where that proposal is judged. The package gate answers one question
over a scope — is there anything here that should stop an evidence package
from being generated? — and answers it by producing a report, never by acting
on it. It judges and reports; it does not enforce (SEG-SYS-006). Enforcement —
refusing to generate for a blocked scope — is a later component's, and above
that, the operator's.

One function, one report
-------------------------

.. code-block:: python

   from affirmatrix import drift, gates, graph
   from affirmatrix.case import AffirmationStore
   from affirmatrix.sources.store import StoreLoader

   built = graph.build(
       drift.derive(
           recorded=AffirmationStore(root="case"),
           current=StoreLoader(root="tests/fixtures/would_be_store"),
       )
   )
   report = gates.package_gate(built)

   if report.blocked:
       for diagnostic in report.diagnostics:
           print(diagnostic.severity.value, diagnostic.condition, diagnostic.subject)

``package_gate`` takes the graph the caller already built and does no scope
collection of its own: it neither walks strong edges to decide what is
reachable nor filters the graph down to a requested root. Deciding what is
*in scope* before the gate ever sees it — SEG-SREQ-036's reachability walk —
is the proof generator's item; iteration 0 has no proof generator yet, so the
gate is simply handed the whole graph. The same function will serve a
reachability subset once that lands, unchanged.

Four findings, two derived views
---------------------------------

:class:`~affirmatrix.gates.CoverageReport` stores exactly four things it
found — the non-active worklist, the coverage gaps, the discarded outcomes,
and whether the design set is empty — and computes two views from them:
``diagnostics``, every finding turned into a
:class:`~affirmatrix.diagnostics.Diagnostic`, and ``blocked``, whether any of
them has a severity that blocks a package. Both are properties, not stored
fields, so there is exactly one place severity is decided and the report
cannot disagree with itself about what it means: a test asserting
``blocked == any(d.severity.blocks_package for d in report.diagnostics)``
is asserting something the types make true by construction, not a
coincidence to protect.

Every gate condition here — an unready edge, a coverage gap, an empty design
set — is a :attr:`~affirmatrix.diagnostics.Severity.WARNING`: it blocks
generating a package, never a commit. A commit-blocking
:attr:`~affirmatrix.diagnostics.Severity.ERROR` arrives only with the
extractors, which is where the conditions that are actually about content
production live; this gate produces none in iteration 0. A discarded outcome
is :attr:`~affirmatrix.diagnostics.Severity.INFO` — named in the report,
never blocking anything by itself: discards are visible so a gap never
appears unexplained.

The worklist: every non-active strong edge
--------------------------------------------

SEG-SREQ-043 asks for every strong edge in scope that is not active, and the
gate means *every*: all five non-active states appear, pending and broken
included, neither of which affirmation can resolve — a pending edge needs a
first affirmation, a broken one needs its endpoint restored. The worklist
never lists an evidence edge: only :func:`~affirmatrix.taxonomy.propagating_edge_kinds`
counts, because an unaffirmed confirms or witnesses edge is not something a
reviewer signs — it is resolved by re-running the test, not by judgement. The
list is sorted by kind, then source, then target, so two evaluations of the
same graph produce the same worklist in the same order.

Gaps land at the leaf
-----------------------

SEG-SREQ-044 says a coverage gap is reported at the requirement that lacks
coverage, never at one it refines. :mod:`affirmatrix.satisfaction`'s
``Verdict`` deliberately carries no per-requirement reasons — it says *which*
requirements are unsatisfied, not *why* — precisely so this attribution has
one owner. The gate re-asks the leaf and non-leaf predicates directly, with a
twist: for a requirement that has refiners, it forces every refiner's
satisfaction to ``True`` before asking
:func:`~affirmatrix.satisfaction.non_leaf_satisfied`. Forcing the children
green isolates exactly what that one requirement carries on its own — its
direct verifies and implements edges — from what its descendants carry. A
requirement whose only problem is an unsatisfied child comes out covered by
this question and is not listed; a requirement with its own inactive direct
edge is listed whether or not its children are actually fine. The result: a
failure three levels down produces exactly one gap, at the bottom, and an
ancestor with nothing of its own to fail is never blamed for it — even though
the plain ``Verdict`` would show every level above it unsatisfied too.

An empty design set cannot be sealed
--------------------------------------

SEG-SREQ-045: if a scope holds no ``Requirement`` node at all, the gate
reports it blocked. A graph of implementations and test specifications with
zero requirements is not vacuously ready — refusing to seal emptiness is a
judgement about what a package is for, not a property the commitment layer's
flat-sealed root could refuse on its own (the root is deliberately total: it
hashes whatever canonical set it is given). ``design_set_empty`` is this
report's own field for exactly that judgement.

The honesty gap
-----------------

Coverage, throughout this component, means only what
:func:`affirmatrix.satisfaction.leaf_satisfied` already means: an active
verifies edge, an active implements edge, and a passing outcome for every
specification the verifies edge names. A **failed**-but-unwaived outcome
behind edges that are otherwise active does not block this gate. That is not
an oversight this page is smoothing over — it is a real gap, named so it does
not read as a guarantee the gate does not make.

The design record's wider Gate-2 condition list (in-scope outcomes
PASS-or-validly-waived, a waiver carrying a named authorised approver,
per-specification outcome freshness) has no requirement anchor yet. Nothing
in the ratified requirement set — SEG-SREQ-042 through SEG-SREQ-045 — says
what a waiver must carry or who may grant one, and the record vocabulary
carries no ``Waiver`` consumption anywhere in the graph the gate reads. Per-
specification freshness fares no better: staleness is anchored only on the
proof generator (SEG-SREQ-040), on a document this gate does not build, and
the record vocabulary does not yet carry the timestamps or revisions staleness
would be computed from. Inventing either mechanism here, ahead of a ratified
requirement, would be design freelancing dressed up as thoroughness — so
until that requirement set grows, a scope whose only defect is a failed,
unwaived test is one this gate calls ready.
