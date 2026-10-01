Drift derivation
================

The read face's page ends where this one begins: the affirmation store
supplies a *recorded* stream — edge records carrying the state and hash they
were last affirmed with — and comparing it against a *current* stream is the
whole of drift detection. This page describes that comparison: where the
suspect detector sits in the pipeline, and what "the strong edges it depends
on" concretely means.

Two record sources in, one record source out
--------------------------------------------

The suspect detector takes exactly two inputs and its output is itself a
record source (:need:`SEG-SREQ-015`):

.. code-block:: python

   from pathlib import Path
   from affirmatrix import drift, graph, satisfaction
   from affirmatrix.case import AffirmationStore
   from affirmatrix.sources.store import StoreLoader

   derivation = drift.derive(
       recorded=AffirmationStore(root=Path("case")),   # SEG-SREQ-054
       current=StoreLoader(root=Path("tests/fixtures/would_be_store")),
   )
   built = graph.build(derivation)
   verdict = satisfaction.evaluate(built)

The derivation replaces both inputs as the graph builder's input: the current
nodes pass through unchanged, and every current edge comes out carrying its
derived state and the hash it was affirmed against, where there was one. The
builder consumes it through the same protocol as any producer, so nothing
downstream — satisfaction, the gates — handles derived states as a special
case, and the builder never learns whether a state was read from disk or
derived a moment ago. States are derived on every run and stored nowhere,
which is why suspicion needs no act to clear (see below) and why derivation
leaves the case untouched (:need:`SEG-SREQ-034`): the function only reads.

The roles are named, not policed. ``recorded=`` and ``current=`` are
keyword-only because swapping them inverts every verdict; what a current edge
claims about its own state or hash is ignored, because affirmed state is the
recorded stream's to supply.

The truth table, over two axes
------------------------------

An affirmed edge's state is decided by two independent questions:

* **Did the edge's content move?** Its hash is recomputed from today's node
  hashes and compared with the hash it was affirmed against. The stored edge
  hash is the only faithful baseline: it is the one datum recorded at that
  edge's affirmation, whereas the case's node records are rewritten by later
  writes. The comparison is two-sided by construction, so it cannot say
  *which* endpoint moved — that attribution lives in the review events, which
  record what each endpoint looked like when the judgement was made.
* **Is every strong edge it depends on active?** — in the derived sense, over
  the current run.

Matching content with dependencies active is ``active``; content differing
alone is ``directlyOutdated``; a non-active dependency alone is
``transitivelySuspect``; both at once is ``doublyOutdated`` — outdated on
both counts, the edge's own content *and* its dependencies, never a count of
endpoints (:need:`SEG-SREQ-011` through :need:`SEG-SREQ-014`).

Pending and broken sit outside the table. An edge with no stored hash was
never affirmed, and the absence of a stored hash is a state, not a mismatch —
this covers a brand-new current edge the case has never seen. An edge
touching a node absent from the current records is broken (:need:`SEG-SREQ-017`),
whatever its kind and whether or not it was affirmed: with an endpoint gone
there is no content to compare, so broken takes precedence over everything.
The graph builder keeps that verdict for an edge that was never affirmed
(:doc:`graph-builder`); it does not reset it to pending.

The dependency relation
-----------------------

All three strong kinds — refines, verifies, implements — point up the
V-model, so "below" an edge is what is reachable *backwards* along strong
edges from its source endpoint. The strong edges an edge depends on are the
strong edges incoming to its own source node, and theirs, recursively. A
sibling edge into the same target is not a dependency: a drifted
implementation unsettles the refines edge above its requirement and leaves
the neighbouring verifies edge alone, which is what keeps affirmation owed at
the change site rather than across the neighbourhood.

The recursion grounds out at nodes nothing strong points into —
implementations, test specifications, outcomes, waivers, and leaf
requirements — where "every strong edge it depends on is active" holds over
the empty set. It terminates because the structure is acyclic: on the
declared kinds, only requirements have strong in-edges, so any strong cycle
would be a refines cycle, and the graph builder has already refused those.
The computation is a memoised post-order walk, not a fixed point; a strong
cycle that ill-kinded records smuggle past the refines gate is refused
loudly, never converged over.

Suspicion stops at the evidence boundary. Confirms, witnesses and excuses
edges receive derived states like every other edge — pending in the ordinary
machine-derived case, broken when dangling — but they are never anyone's
dependency and never anyone's carrier: a stale outcome outdates its own
confirms edge and nothing above it, because re-execution is what it needs,
and marking the specification suspect would invite a re-affirmation instead.
The edges come from the current stream only. The case stores no evidence edge,
so the recorded stream holds none (except in a case written before that rule,
whose evidence edges the derivation treats like any recorded edge that the
current stream does not supply: see the section on vanished edges below, and
``case sync``, which removes them). A dangling evidence edge is counted by
``graph status`` and gives it exit status 1.

Suspicion clears by recomputation
---------------------------------

A transitively suspect edge's own endpoints did not move; only something
below it did. Re-affirming it would be a signature on something that did not
change, so no such act exists: once the outdated edges at the change site are
re-affirmed, the next derivation finds their hashes matching again and the
ancestors come out active — cleared by recomputation, with no event recorded
against them. Affirmation resolves only the directly and doubly outdated
cases.

A recorded edge with no current counterpart
-------------------------------------------

The derived stream is today's topology, so a recorded edge whose declaration
vanished from source is not in it — and it receives no state, because the
requirement set does not yet say what such an edge *is*. It is carried
untouched on the derivation's ``vanished`` field instead, so an affirmed edge
that silently disappeared is visible rather than inferred from an unexplained
coverage gap. Retiring its record from the case remains a maintainer's
explicit removal, never derivation's.
