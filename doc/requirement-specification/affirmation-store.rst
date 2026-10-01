Affirmation Store
=================

The affirmation store is the only component that persists graph data and the
only one that reads it back. Its requirements govern what may be persisted —
hashes and references, never the content those hashes cover — and the
qualities that make persistence trustworthy: validated on write, faithful on
read-back — and refused outright when faithful read-back is impossible —
confined to one write root, never visible half-written, never silently
removed, and never changed unless a change was asked for — including the
case's own copy of the schemas.

.. sreq:: Covered content is never persisted
   :id: SEG-SREQ-018
   :refines: SEG-SYS-007

   The affirmation store shall never persist the content that a hash it
   stores covers.

.. sreq:: Only valid records are written
   :id: SEG-SREQ-019
   :refines: SEG-SYS-007

   If a record does not validate against its schema, then the affirmation
   store shall reject it instead of writing it.

.. sreq:: Records read back as written
   :id: SEG-SREQ-020
   :refines: SEG-SYS-007

   The affirmation store shall reproduce each record it has written unchanged
   when that record is read back.

.. sreq:: Writes stay under the write root
   :id: SEG-SREQ-021
   :refines: SEG-SYS-007

   The affirmation store shall write every record beneath the write root it
   was given, and no record outside it.

.. sreq:: Records appear only when complete
   :id: SEG-SREQ-022
   :refines: SEG-SYS-007

   The affirmation store shall make a record readable only once it has been
   written completely.

.. sreq:: Deletion is explicit
   :id: SEG-SREQ-023
   :refines: SEG-SYS-007

   The affirmation store shall remove a persisted record only when removal of
   that record is requested.

.. sreq:: Every persisted content hash locates its content
   :id: SEG-SREQ-050
   :refines: SEG-SYS-007

   The affirmation store shall persist, for each content hash a node record
   carries, the source location of the content that hash covers.

.. sreq:: Unreadable records are never skipped
   :id: SEG-SREQ-053
   :refines: SEG-SYS-007

   If a persisted record cannot be read back as written, then the affirmation
   store shall refuse the read instead of supplying a record stream without
   that record.

.. sreq:: Persisted affirmations change only on request
   :id: SEG-SREQ-033
   :refines: SEG-SYS-011

   The affirmation store shall change a persisted affirmation record only when
   that change is requested.

.. sreq:: Affirmed standing is never lost by omission
   :id: SEG-SREQ-051
   :refines: SEG-SYS-011

   If a write would replace an edge record carrying the hash it was affirmed
   against with a record carrying no such hash, and demotion of that edge was
   not requested, then the affirmation store shall refuse the write.

.. sreq:: A case's schema copy is rewritten from the packaged schemas, and its stored evidence edges migrate, on request
   :id: SEG-SREQ-139
   :refines: SEG-SYS-007

   When the refresh of a case's schema copy is requested, the affirmation
   store shall rewrite that copy from the packaged schemas and, apart from the
   migration of stored evidence edges, write nothing else in the case.

.. sreq:: A refresh reports each schema that differed
   :id: SEG-SREQ-140
   :refines: SEG-SYS-007

   When the affirmation store refreshes a case's schema copy, it shall
   report each schema whose copy differed from the packaged one.

.. sreq:: Refresh sets every stored pending evidence edge to stale
   :id: SEG-SREQ-215
   :refines: SEG-SREQ-139

   When the affirmation store refreshes a case's schema copy, it shall rewrite
   every evidence edge it holds in the state pending to the state stale.

.. sreq:: Refresh leaves strong edges and hashed edges as they are
   :id: SEG-SREQ-216
   :refines: SEG-SREQ-139

   When the affirmation store refreshes a case's schema copy, it shall leave
   unchanged every strong edge and every edge record that carries an edge hash.

.. sreq:: A refresh that cannot validate changes nothing
   :id: SEG-SREQ-217
   :refines: SEG-SREQ-139

   If any node, edge or review event of the case, or any edge the refresh would
   rewrite, does not validate against the refreshed schema copy, then the
   affirmation store shall refuse the refresh and change nothing in the case.

.. sreq:: The refresh report counts the migrated edges
   :id: SEG-SREQ-218
   :refines: SEG-SREQ-139

   When the affirmation store refreshes a case's schema copy, it shall report
   the number of evidence edges it rewrote.
