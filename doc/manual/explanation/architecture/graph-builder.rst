The graph builder
=================

The builder turns record streams into the typed graph the rest of the engine
reads. It is the narrow gate every record passes through, so most of what it
does is refuse: a kind the vocabulary does not declare, a cycle or a self-loop
in the refines relation, a local identifier used twice. Everything else it
carries as it is given. It does not derive states: the suspect detector does
that (:doc:`drift-derivation`).

The state of an edge that was never affirmed
--------------------------------------------

An edge record carries a state and, once it was affirmed, the hash it was
affirmed against. The builder judges whether an edge was ever affirmed by the
hash, not by the state the record claims (:need:`SEG-SREQ-016`):

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - The record
     - The builder reports
     - Why
   * - no hash, state pending
     - pending
     - never affirmed
   * - no hash, state directly outdated, transitively suspect, doubly outdated
       or active
     - pending
     - a claim of history that never happened
   * - no hash, state broken
     - **broken**
     - the verdict needs no affirmation
   * - a hash, any state
     - the state of the record
     - affirmed; the detector derived the state

The third row is the rule that changed. An edge that touches a node absent from
the records is broken, whether or not it was ever affirmed
(:need:`SEG-SREQ-017`). The detector reaches that verdict; the builder used to
turn it back into pending when the edge had no hash. So a dangling strong edge
that nobody had affirmed read as pending, and ``graph status`` listed it as
pending and exited with status 0. Now the builder keeps ``broken``. The
consequences:

* ``graph status`` lists such an edge as broken and exits with status 1;
* the package gate lists it among the unready edges with the detail ``broken``;
* ``case sync`` already stored such an edge as broken, and writes it as pending
  again, without a hash, once the node returns.

What the builder does not do is decide that an endpoint is absent. That needs
both streams, which the detector has and the builder does not.
