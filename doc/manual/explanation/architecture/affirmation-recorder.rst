The affirmation recorder
========================

Drift derivation ends with a worklist: the directly and doubly outdated edges
are where a human judgement is owed. The recorder is what turns one such
judgement into records — and the deliberate smallness of that sentence is the
page's subject. The recorder composes; it persists nothing, decides nothing,
and derives nothing. An operator runs it.

One judgement composes a pair
-----------------------------

An affirmation has two effects on the case: a review event joins the record
of judgements, and the affirmed edge's record changes to active, carrying the
hash the judgement binds. Both are composed by the recorder, in one call,
from the same endpoint hashes:

.. code-block:: python

   composed = affirmation.compose(
       outdated_edge,                      # a derived record, from drift.derive
       from_node=current_nodes[outdated_edge.from_id],
       to_node=current_nodes[outdated_edge.to_id],
       role="SoftwareEngineer",
       reason="reviewed the change; the binding still holds",
       from_source_revision=impl_revision,  # supplied by the operator —
       to_source_revision=req_revision,     # the tool never runs git
   )
   store.append_review_events([composed.event])
   store.write_edges([composed.edge])

The pair exists because the store computes no hashes: it persists what it is
handed, and the commitment layer is deliberately out of its reach. The
affirmation's effect on the edge record therefore has to be composed *above*
the store, and composing it beside the event means record and event cannot
disagree about what was affirmed — both fold the same two node hashes. A
workflow that affirms calls one component and hands the store both halves.

Those are the *current* node hashes — what the reviewer judged today — never
the hashes the edge was last affirmed against, which would re-sign the past.
The recorder derives them from the endpoint records it is handed and
originates nothing itself: every judgement field is the operator's, required,
with no default. Even an empty reason must be given, never assumed.

What the recorder trusts, and what it refuses
---------------------------------------------

The edge handed to ``compose`` is a *derived* record — the suspect detector's
output, carrying the state the recorded and current streams imply. The
recorder reads that state and does not recompute it; a recorder that
re-derived would be a second telling of link state, and the import layering
forbids it the suspect detector for exactly that reason.

Of the six states, three are affirmable — pending, directly outdated, doubly
outdated — because there a judgement about the edge's own content is what is
missing (SEG-SREQ-027). The refusals each point at the act that would
actually resolve the edge: an active edge has nothing to affirm; a
transitively suspect edge clears by recomputation once the change sites below
it are re-affirmed (see :doc:`drift-derivation`); a broken edge needs its
endpoint back before a judgement could bind anything. The recorder also
refuses endpoint records that are not the named edge's endpoints — hashes of
some other node would compose a record about an edge nobody reviewed.

Source revisions are opaque strings here. The tool never runs git, so the
operator supplies each endpoint's revision, and their format is judged where
the record is persisted — against the case's own schema — not by the
recorder.

Only a strong edge can be affirmed
-----------------------------------

The state gate above is a companion, not the whole test: ``affirmable`` and
``compose`` also gate on the edge's *kind*, via
:func:`~affirmatrix.taxonomy.propagating_edge_kinds` (SEG-SREQ-056).
``Confirms``, ``Witnesses``, ``Excuses`` and ``Calls`` are refused whatever
their state, because they are machine-derived evidence, not something a
human judgement is about. A ``Confirms`` or ``Witnesses`` edge is resolved by
re-running the test that produced it; an ``Excuses`` edge (Waiver to
TestOutcome, per ``case/schema/edge-excuses.schema.json``) records a
producer's excusal claim, not a reviewer's — and the state gate alone would
not have caught this, since an evidence edge sits pending exactly like a
strong edge genuinely awaiting its first affirmation. The refusal names the
distinction directly: an evidence edge cannot be affirmed because
re-execution, not judgement, is what would resolve it.

``affirmable`` therefore takes both the state and the kind::

   affirmation.affirmable(edge.state, edge.kind)

and ``compose`` checks the kind before it ever asks about state, so the
message an operator sees for an evidence edge names the actual reason
(machine-derived, re-execution resolves it) rather than borrowing the
state gate's language. This is a companion to SEG-SREQ-027, not an amendment
of it: every strong kind — ``Refines``, ``Verifies``, ``Implements`` — is
governed by state exactly as before.

Composing is not affirming
--------------------------

``compose`` is pure: same inputs, same values, no store touched, no
identifier and no timestamp minted (position in the store is identity, and
who/when/authority belong to the commit that introduces the record). The
bytes the store then writes are a proposal on the working tree; they become
an affirmation when a maintainer reviews and commits them. That boundary is
the guarantee-boundary page's subject; this component is built and tested as
capability only.
