Proof scope
===========

The package gate's page describes a function that takes whatever graph its
caller hands it and judges that graph alone. This page describes the caller:
:func:`affirmatrix.proof.collect_scope`, which turns a set of requested
requirements into the graph the gate was always meant to receive — a scope,
built once a requester says which requirements they are asking about, before
any evidence package exists to carry it.

One function, one scope
------------------------

.. code-block:: python

   from datetime import UTC, datetime

   from affirmatrix import gates, proof

   scope = proof.collect_scope(
       built, {"SEG-SREQ-014"}, snapshot_timestamp=datetime.now(UTC)
   )
   report = gates.package_gate(scope.subgraph, evaluation_date=today)

``collect_scope`` never calls the gate itself — wiring the two together, and
deciding what happens when the gate reports a scope blocked, belongs to a
later slice. What it hands forward is a :class:`~affirmatrix.proof.Scope`:
the requested ids, the collected member ids, the induced subgraph the gate
receives, the partial-vs-total signal, and the scope's own snapshot
identifier. ``snapshot_timestamp`` is required and never defaulted, the same
purity :func:`~affirmatrix.gates.package_gate`'s ``evaluation_date`` already
commits to — a function that read the clock itself could not repeat its own
answer on a later call over an unchanged graph.

The expansion order, and why it must be total
-----------------------------------------------

Requesting a requirement is a claim about more than that one node. Judging it
faithfully needs everything its own coverage actually depends on, collected in
one pass:

1. **Every transitive refiner**, to a fixed point. A requirement's own
   coverage is incomplete without its children's, so refiners are pulled in
   however deep the decomposition goes.
2. **Every specification and implementation** that verifies or implements one
   of the requirements now collected.
3. **Every outcome** that confirms one of the specifications now collected —
   evidence riding in on top of the design set.
4. **Every waiver** that excuses one of the outcomes now collected.

A missing hop does not fail loudly — it silently narrows the scope, which is
the more dangerous outcome of the two. A subgraph cut at the first two hops
alone would carry specifications with no outcomes attached at all, and the
gate would report gaps and discarded evidence the whole graph does not
actually have; a package whose expansion quietly stopped one hop early would
read as covering less trouble than it does, or more coverage than it earns,
depending on which hop went missing. Totality is what keeps the gate's
judgement over a scope equal to what the same judgement would say about that
scope inside the whole graph.

Refiners, never an ancestor
-----------------------------

The refines hop only ever climbs toward a requested requirement's *children*
— the nodes that declare themselves its refinements — never toward its
*parent*. The reason is not a matter of taste: the package gate isolates a
requirement's own direct coverage by forcing every one of its refiners
satisfied before asking whether the requirement's own verifies and implements
edges are active. Pulling a parent into scope without every one of its
other children — nobody asked for those — would let that same forcing rule
report the parent clean on a subtree this scope never actually checked. A
package about one requirement asserts something about that requirement and
what it depends on; it never gets to imply something about its parent's other
children for free.

The subgraph is the full induced cut
--------------------------------------

Once the member set is settled, :meth:`affirmatrix.graph.Graph.restricted_to`
builds the scope's subgraph as every edge — of *any* kind — whose two
endpoints are both members, not only the edges the expansion above used to
discover them. ``Witnesses`` edges show why this matters: they never decide
membership (an outcome's witnessed implementation is already reachable
through ``implements`` whenever that matters), but once an outcome and an
implementation are both members for other reasons, their ``Witnesses`` edge
belongs in the cut too — dropping it would make a genuinely complete piece of
evidence read as incomplete to the gate for a reason that never happened.

The flip side is a deliberate reading, not an oversight. An outcome that
confirms an in-scope specification but witnesses an implementation this scope
never reached loses that ``Witnesses`` edge when the cut is taken. Within this
scope alone, such an outcome satisfies only one of the two questions
:mod:`affirmatrix.satisfaction` asks of it, so the gate discards it exactly as
it would discard any other incomplete outcome — even though the very same
outcome, judged against the whole graph, is complete evidence. That
divergence is truthful *for the scope requested*: the scope is a deliberate
cut, chosen by whoever asked for it, and a test outcome may always carry more
results than one particular scope needs. Nothing here tries to widen a
narrow request after the fact to make an outcome look more complete than the
requester asked to see.

The partial-vs-total signal
------------------------------

A package that does not say how much of the whole picture it covers invites
being read as covering all of it. ``Scope.total`` answers exactly that: does
this scope's member set include every *top-level* requirement in the whole
graph — one that is never the source of a ``refines`` edge? The question is
asked of the whole graph, never of the subgraph a scope already cut down,
because a cut has no way to know what it excludes.

A graph with no requirements at all reports every scope total, vacuously —
there is nothing to leave out, so nothing is left out. That vacuous truth
never gets read as "safe to trust": an empty scope's design set is empty too,
and the package gate blocks an empty design set outright, on its own
authority, regardless of what the totality signal says about it. The two
signals answer different questions and neither substitutes for the other:
totality says whether a scope is missing something the graph currently
claims to have; the gate's block says whether a scope, total or not, has
anything to seal at all.

The snapshot identifier
--------------------------

A scope mints its own snapshot identifier the moment it is collected, well
before any package exists to carry it forward. Two parts, joined by a hyphen:

* a portable timestamp — the caller-supplied instant, rendered without the
  separators an ordinary spelling carries, since a colon is not valid in a
  Windows path segment;
* a content fingerprint of the scope itself, folding every member's node hash
  and every edge the induced subgraph keeps — evidence included, so a scope
  that differs only in an outcome or a waiver mints a different identifier.

The fingerprint is produced by calling
:func:`affirmatrix.commitment.design_root` with an explicitly empty metadata
value: this is not a package's sealed root, only a way to fold a node/edge
set into one digest before any package or its real metadata exists, using the
one commitment primitive general enough to do it. Nothing here re-implements
hashing of its own — the whole point of routing through the commitment layer
is that this module never has to.

What still waits
--------------------

One thing this page cannot yet claim:

* **Recording a scope into a package, and the purity of doing so.** A
  package's obligation to state the scope it was built for, and to leave
  every node, edge and affirmation untouched while it does, are both
  requirements stated over *a package* — and no package exists yet. What
  this page describes is the value a later package will carry and the
  purity a test already enforces on the collection step alone; the act of
  recording that value, and generating a package around it without side
  effects, is a later page's to describe.

Stale outcomes are no longer unrealizable, but they are also not this
module's to exclude. :func:`~affirmatrix.gates.package_gate` now judges
staleness — given the current revision of the implementation repository as
an explicit input, exactly as it is given ``evaluation_date`` — and cuts a
stale outcome out of the graph it judges before computing anything else (see
the package gate's page). This module's own collection hands the gate an
unfiltered subgraph: hop 3 above still collects every outcome confirming an
in-scope specification, fresh or stale alike, because the comparison needs a
current revision this module is never given, and because a scope's
membership and a gate's judgement over that scope are different questions. A
*package's* exclusion of what the gate reports stale (:need:`SEG-SREQ-040`) is the
next slice's, once a package exists to exclude anything from.
