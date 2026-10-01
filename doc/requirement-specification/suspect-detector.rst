Suspect Detector
================

The suspect detector compares what was recorded against what is current and
derives each edge's state from the difference. A strong edge takes one of four
states by that comparison. Its requirements enumerate those states, fix the
record sources it may derive them from — binding the recorded one to the
affirmation store — and cover the case where an endpoint has disappeared from
source entirely. Because the states are derived on every run rather than
stored, suspicion raised by a descendant clears itself once that descendant is
affirmed again — no separate act is needed, and none is offered.

An evidence edge carries a test outcome's evidence. Nobody affirms it. It is
current or stale, and the revision decides which. The edge kinds Confirms,
Witnesses and Excuses are the evidence edges. They are the edges that do not
propagate suspicion and have a test outcome at one end: the outcome is the
source of a Confirms or Witnesses edge and the target of an Excuses edge. For
an Excuses edge, current says only that the outcome carries the current
revision. It says nothing about whether the waiver is valid. Waiver expiry stays
with the gate. ADR-0012 gives the reasons.

.. sreq:: Direct outdatedness
   :id: SEG-SREQ-011
   :refines: SEG-SYS-003

   While an affirmed edge's endpoint content differs from the content recorded
   at its last affirmation and every strong edge it depends on is active, the
   suspect detector shall report that edge as directly outdated.

.. sreq:: Transitive suspicion
   :id: SEG-SREQ-012
   :refines: SEG-SYS-003

   While an affirmed edge's endpoint content matches the content recorded at
   its last affirmation and any strong edge it depends on is not active, the
   suspect detector shall report that edge as transitively suspect.

.. sreq:: Outdated on both counts
   :id: SEG-SREQ-013
   :refines: SEG-SYS-003

   While an affirmed edge's endpoint content differs from the content recorded
   at its last affirmation and any strong edge it depends on is not active,
   the suspect detector shall report that edge as doubly outdated.

.. sreq:: Active edges
   :id: SEG-SREQ-014
   :refines: SEG-SYS-003

   While an affirmed edge's endpoint content matches the content recorded at
   its last affirmation and every strong edge it depends on is active, the
   suspect detector shall report that edge as active.

.. sreq:: State derives from two record sources and a current revision
   :id: SEG-SREQ-015
   :refines: SEG-SYS-003

   The suspect detector shall derive each edge's state from a recorded record
   source, a current record source and a current revision alone.

.. sreq:: The recorded source is the affirmation store
   :id: SEG-SREQ-054
   :refines: SEG-SYS-003

   The suspect detector shall take its recorded record source from the
   affirmation store.

.. sreq:: Edges to absent nodes are broken
   :id: SEG-SREQ-017
   :refines: SEG-SYS-001

   The suspect detector shall report every edge touching a node that is absent
   from the current records as broken.

.. sreq:: Derivation leaves affirmations untouched
   :id: SEG-SREQ-034
   :refines: SEG-SYS-011

   The suspect detector shall leave recorded affirmations unchanged when it
   derives edge states.

.. sreq:: Per-hash endpoint comparison against the affirming review event
   :id: SEG-SREQ-128
   :refines: SEG-SYS-003

   For an edge that has been affirmed, the suspect detector shall report,
   for each named content hash of either endpoint, whether that hash's
   current digest matches the digest the affirming review event recorded
   for that endpoint, together with both digests' anchors and the source
   revision the review event recorded for that endpoint.

.. sreq:: An evidence edge is of kind Confirms, Witnesses, or Excuses
   :id: SEG-SREQ-203
   :refines: SEG-SYS-012

   The suspect detector shall treat an edge as an evidence edge when its kind is
   Confirms, Witnesses or Excuses.

.. sreq:: An evidence edge to the current revision is current
   :id: SEG-SREQ-204
   :refines: SEG-SYS-012

   While both endpoints of an evidence edge are present in the current records
   and the test outcome at one end carries the current revision the suspect
   detector is given, the suspect detector shall report that edge as current.

.. sreq:: An evidence edge to another revision is stale
   :id: SEG-SREQ-205
   :refines: SEG-SYS-012

   While both endpoints of an evidence edge are present in the current records
   and the test outcome at one end carries a revision that differs from the
   current revision the suspect detector is given, the suspect detector shall
   report that edge as stale.
