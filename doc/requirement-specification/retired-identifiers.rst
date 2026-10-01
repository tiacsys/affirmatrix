Retired Identifiers
===================

A retired identifier is never issued again. Each row names the need that left
the specification, the date it left, the reason, and what replaced it. The
needs of this table have no entry on any other page. Git holds their old text.

.. list-table::
   :header-rows: 1
   :widths: 14 30 12 24 20

   * - Identifier
     - Former title
     - Withdrawn
     - Reason
     - Pointer
   * - SEG-SYS-012
     - Evidence currency against a revision
     - 2026-10-01
     - No evidence state exists any more.
     - SEG-SYS-013
   * - SEG-SREQ-203
     - An evidence edge is of kind Confirms, Witnesses, or Excuses
     - 2026-10-01
     - The detector needs no evidence edge concept.
     - SEG-SREQ-227, SEG-SREQ-228
   * - SEG-SREQ-204
     - An evidence edge to the current revision is current
     - 2026-10-01
     - No evidence state exists.
     - SEG-SREQ-210, ADR-0013
   * - SEG-SREQ-205
     - An evidence edge to another revision is stale
     - 2026-10-01
     - No evidence state exists.
     - SEG-SREQ-210, ADR-0013
   * - SEG-SREQ-206
     - The builder keeps an evidence edge's state
     - 2026-10-01
     - The builder never sees an evidence state.
     - ADR-0013
   * - SEG-SREQ-207
     - The current revision of edge-state derivation is given or discovered
     - 2026-10-01
     - One rule serves every verb that builds the evidence.
     - SEG-SREQ-112
   * - SEG-SREQ-209
     - One revision serves the derivation and the gate
     - 2026-10-01
     - No second derivation needs the revision.
     - ADR-0013
   * - SEG-SREQ-213
     - A dirty implementation repository refuses a discovered revision for the recording verbs
     - 2026-10-01
     - One dirty-tree rule replaces the split.
     - SEG-SREQ-112
   * - SEG-SREQ-214
     - A dirty implementation repository does not refuse the display verbs
     - 2026-10-01
     - One dirty-tree rule replaces the split.
     - SEG-SREQ-112
   * - SEG-SREQ-215
     - Refresh sets every stored pending evidence edge to stale
     - 2026-10-01
     - No migration to a stale state exists.
     - SEG-SREQ-228
   * - SEG-SREQ-216
     - Refresh leaves strong edges and hashed edges as they are
     - 2026-10-01
     - Refresh changes no record.
     - SEG-SREQ-139
   * - SEG-SREQ-217
     - A refresh that cannot validate changes nothing
     - 2026-10-01
     - Refresh changes no record.
     - SEG-SREQ-139
   * - SEG-SREQ-218
     - The refresh report counts the migrated edges
     - 2026-10-01
     - Refresh migrates no edge.
     - SEG-SREQ-228
   * - SEG-SREQ-197
     - Each run's bundle and its digest are carried
     - 2026-10-01
     - The configuration holds no run entries.
     - SEG-SREQ-234
   * - SEG-SREQ-221
     - A digest that differs from the configured one is refused
     - 2026-10-01
     - No expected digest exists. The proof fixes the identity of a bundle.
     - ADR-0013
