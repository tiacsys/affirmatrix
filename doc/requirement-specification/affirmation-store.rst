Affirmation Store
=================

The affirmation store is the only component that persists graph data and
the only one that reads it back. Its requirements govern what may be persisted
— hashes and references, never the content those hashes cover — and the
qualities that make persistence trustworthy: validated on write, faithful on
read-back, confined to one write root, never visible half-written, never
silently removed, and never changed unless a change was asked for.

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
