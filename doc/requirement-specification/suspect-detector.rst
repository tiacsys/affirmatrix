Suspect Detector
================

The suspect detector compares what was recorded against what is current and
derives each edge's state from the difference. Its requirements enumerate the
four states that comparison yields, fix the two record sources it may derive
them from — binding the recorded one to the affirmation store — and cover the
case where an endpoint has disappeared from source entirely. Because the
states are derived on every run rather than stored, suspicion raised by a
descendant clears itself once that descendant is affirmed again — no separate
act is needed, and none is offered.

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

.. sreq:: State derives from a recorded and a current record source
   :id: SEG-SREQ-015
   :refines: SEG-SYS-003

   The suspect detector shall derive each edge's state from a recorded record
   source and a current record source alone.

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
