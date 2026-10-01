Graph Builder
=============

The graph builder turns node and edge records into the graph every other
component reads. Its requirements cover what it must refuse — a cycle in the
refines relation, a record of a kind the vocabulary does not contain — and the
state an edge carries before anyone has affirmed it.

.. sreq:: Refines cycles are a graph-level error
   :id: SEG-SREQ-004
   :refines: SEG-SYS-001

   If the refines edges form a cycle or a self-loop, then the graph builder
   shall report a graph-level error.

.. sreq:: Unaffirmed edges are pending, and a broken edge stays broken
   :id: SEG-SREQ-016
   :refines: SEG-SYS-001

   The graph builder shall report an edge that has never been affirmed as
   pending, except an edge its record reports as broken, which it shall
   report as broken.

.. sreq:: Unrecognized kinds are rejected
   :id: SEG-SREQ-031
   :refines: SEG-SYS-009

   If a record declares a kind the taxonomy provider does not declare, then
   the graph builder shall reject that record.
