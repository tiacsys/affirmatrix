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

   from datetime import date

   from affirmatrix import drift, gates, graph
   from affirmatrix.case import AffirmationStore
   from affirmatrix.sources.store import StoreLoader

   built = graph.build(
       drift.derive(
           recorded=AffirmationStore(root="case"),
           current=StoreLoader(root="tests/fixtures/would_be_store"),
       )
   )
   report = gates.package_gate(
       built, evaluation_date=date.today(), current_revision=current_repository_revision
   )

   if report.blocked:
       for diagnostic in report.diagnostics:
           print(
               diagnostic.severity.value,
               diagnostic.condition,
               diagnostic.subject,
               diagnostic.detail,
           )

``evaluation_date`` is the caller's, not the gate's: ``package_gate`` never
reads the system clock itself, so a waiver's expiry is judged against
whatever "today" the caller supplies. That is what keeps the function pure —
the same caller-supplied-metadata shape the commitment layer already uses for
its snapshot metadata — and it is why the parameter is required and never
defaulted: a default of "now" would make two calls over an unchanged graph
disagree the moment a day turned over. ``current_revision`` is the same kind
of explicit input, one section below.

``package_gate`` takes the graph the caller already built and does no scope
collection of its own: it neither walks strong edges to decide what is
reachable nor filters the graph down to a requested root. Deciding what is
*in scope* before the gate ever sees it — SEG-SREQ-036's reachability walk —
is the proof generator's item; iteration 0 has no proof generator yet, so the
gate is simply handed the whole graph. The same function will serve a
reachability subset once that lands, unchanged.

Seven findings, two derived views
---------------------------------

:class:`~affirmatrix.gates.CoverageReport` stores exactly seven things it
found — the non-active worklist, the coverage gaps, the stale outcomes, the
discarded outcomes, the non-passing outcomes not excused by a valid waiver,
the non-passing outcomes that are, and whether the design set is empty — and
computes two views from them: ``diagnostics``, every finding turned into a
:class:`~affirmatrix.diagnostics.Diagnostic`, and ``blocked``, whether any of
them has a severity that blocks a package. Both are properties, not stored
fields, so there is exactly one place severity is decided and the report
cannot disagree with itself about what it means: a test asserting
``blocked == any(d.severity.blocks_package for d in report.diagnostics)``
is asserting something the types make true by construction, not a
coincidence to protect.

Every gate condition here — an unready edge, a coverage gap, an empty design
set, a non-passing outcome not validly excused — is a
:attr:`~affirmatrix.diagnostics.Severity.WARNING`: it blocks generating a
package, never a commit. A commit-blocking
:attr:`~affirmatrix.diagnostics.Severity.ERROR` arrives only with the
extractors, which is where the conditions that are actually about content
production live; this gate produces none in iteration 0. A discarded
outcome, a stale outcome, and a validly excused non-passing outcome are all
:attr:`~affirmatrix.diagnostics.Severity.INFO` — named in the report, never
blocking anything by themselves: all three are visible so a reader is never
left inferring why an outcome went unmentioned. The discard and waiver
findings can coincide on one outcome — an incomplete outcome that is also
non-passing and unwaived earns both a discard finding and a blocking one —
which is intended, not double-counting: each finding states a different fact
that happens to be true of the same subject. A stale outcome is the one
exception to that rule: see "Staleness" below for why it is never doubled
with any other finding on the same subject.

Every diagnostic's ``condition`` is one member of
:class:`~affirmatrix.gates.Condition`, a closed, seven-member vocabulary
(SEG-SREQ-064) — never a sentence assembled for the occurrence. What varies
from one occurrence of a condition to the next travels on ``detail`` instead
(SEG-SREQ-065): an unready edge's own state, the one condition here with
anything occurrence-specific to say. Every other finding's diagnostic
carries an empty ``detail`` — the stale finding included: the two revisions
being compared are not repeated there, since one already lives on the
outcome record and the other is the caller's own input to this call. The
vocabulary lives on :class:`~affirmatrix.gates.Condition`, in this
component, not on :mod:`affirmatrix.diagnostics`: that module is shared,
occurrence-free vocabulary with no component's conditions in it.

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

Staleness (SEG-SREQ-063, SEG-SREQ-067)
------------------------------------------

``package_gate`` takes the current revision of the implementation repository
as an explicit keyword, exactly like ``evaluation_date`` — never read from
the graph, never inferred from the outcomes it judges. A ``TestOutcome``
whose recorded revision differs from it is stale, and the gate cuts it out of
the graph *before* asking anything else: :meth:`~affirmatrix.graph.Graph.restricted_to`
removes the node and, with it, every edge that touched it — the same
operation the proof generator's scope collection already uses to cut a
graph down to a member set. :mod:`affirmatrix.satisfaction` never sees a
stale outcome and never learns what a revision is; the gate hands it a
*view*, not a revision-aware question.

The consequence reads the same way an absent outcome always would: a
specification whose only confirming outcome is stale is an ordinary
coverage gap, exactly as if that outcome had never been recorded; a fresh
sibling outcome keeps the specification covered. And because the cut happens
before every other finding, not only the coverage-facing ones, a stale
outcome is equally invisible to the waiver seam below — a stale, failing
outcome is never also reported as an unwaived or excused non-passing
outcome, and never also as a discarded one. It is reported exactly once, as
the stale finding. This reads past SEG-SREQ-063's own words, which speak
only of judging the specification a stale outcome confirms — deliberate, so
one telling of "does not count" never disagrees with another.

The seam: two questions, not three
------------------------------------

:mod:`affirmatrix.satisfaction` is built to stay swappable for a
configurable rule engine: the leaf and non-leaf rules are small named
predicates rather than logic woven into this gate, so a replacement
evaluator is a substitution, not a rewrite. What makes that swap mechanical
is a contract on how few questions this gate is allowed to ask across the
seam. There are exactly **two**:

1. *The whole-graph verdict* — :func:`affirmatrix.satisfaction.evaluate`,
   consumed above for ``discarded_outcomes`` and nothing else.
2. *A requirement's own-direct-coverage question* — re-asking
   :func:`~affirmatrix.satisfaction.leaf_satisfied` or
   :func:`~affirmatrix.satisfaction.non_leaf_satisfied` with a requirement's
   own refiners forced satisfied, which is how "Gaps land at the leaf" above
   isolates one requirement's direct edges from its descendants'.

Every rule-content change belongs inside satisfaction's own named
predicates, never restated imperatively here. That includes excusal: whether
a waiver excuses an outcome is presence of a Waiver record reached through an
incoming ``Excuses`` edge, and satisfaction already answers exactly that
question for its own universal (SEG-SREQ-006). This gate does **not** call
into that private answer as a third borrowed predicate — doing so would grow
the seam to three questions and make a future Datalog swap-in responsible for
exposing internals it has no reason to expose. Instead, the waiver seam below
is the gate's *own* declarative predicate over graph facts (an edge kind, a
node's presence and kind, an explicit date), independently arriving at the
same reading satisfaction already commits to. A replacement satisfaction
engine only ever has to answer the two questions above; everything the gate
computes about waiver validity is this component's own, and stays so when
that engine changes.

The waiver seam: non-passing outcomes (SEG-SREQ-060, SEG-SREQ-061)
----------------------------------------------------------------------

Every ``TestOutcome`` node whose recorded result is not ``PASSED`` — failed,
error, or skipped alike, uniformly, whatever the outcome's own evidentiary
completeness — is judged for an excusing waiver. Excusal is resolved by
walking the outcome's incoming ``Excuses`` edges (Waiver to TestOutcome, per
``case/schema/edge-excuses.schema.json``) to the Waiver record each names:
presence of that record is what counts, never the edge's own state, which an
excusal edge — evidence, like ``Confirms`` and ``Witnesses`` — can never
carry as anything but pending. An excusing edge whose Waiver record is
absent from the graph excuses nothing.

A non-passing outcome with no valid excusing waiver is
:attr:`~affirmatrix.diagnostics.Severity.WARNING` (SEG-SREQ-060); one validly
excused is :attr:`~affirmatrix.diagnostics.Severity.INFO` (SEG-SREQ-061).
"Valid" is where this pass stops short of the full requirement: SEG-SREQ-059
asks for a waiver that has **not expired and whose approver is authorised**.
This gate checks only the first half — an explicit, caller-supplied
``evaluation_date`` against the waiver's own recorded ``expiry``
(SEG-SREQ-057) — because the second half needs a roster of authorised
approvers that no ratified requirement yet names. Realizing the expiry half
now, rather than deferring the whole of SEG-SREQ-059, was the deliberate
choice: it catches the common failure (a stale waiver excusing forever) and
leaves the residual risk stated here rather than hidden — **an unexpired
waiver from an approver nobody has authorised reads as validly excused
today.** SEG-SREQ-059 itself carries no ``:implements:`` marker anywhere in
this codebase for exactly that reason: marking it would claim a check this
gate does not perform. When an authorisation roster exists, the approver
half joins this predicate and the marker follows.

The coverage report as a persisted document
------------------------------------------------

An evidence package's coverage report document (see :doc:`proof-package`) is
this ``CoverageReport`` serialized whole — the same seven typed findings and
the same two derived views, restated in the shape a schema can validate.
The generator that assembles a package adds nothing to it: a reader
comparing the persisted document against a fresh call to ``package_gate``
over the same inputs sees the same answer twice, never a second opinion.
