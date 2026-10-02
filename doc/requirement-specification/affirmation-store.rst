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

.. sreq:: A case's schema copy is rewritten from the packaged schemas on request
   :id: SEG-SREQ-139
   :refines: SEG-SYS-007

   When the refresh of a case's schema copy is requested, the affirmation
   store shall rewrite that copy from the packaged schemas and write
   nothing else in the case.

.. sreq:: A refresh reports each schema that differed
   :id: SEG-SREQ-140
   :refines: SEG-SYS-007

   When the affirmation store refreshes a case's schema copy, it shall
   report each schema whose copy differed from the packaged one.

.. sreq:: The case persists no test evidence
   :id: SEG-SREQ-227
   :refines: SEG-SYS-013

   If a write names a test outcome node or an edge of kind Confirms, Witnesses
   or Excuses, then the affirmation store shall refuse the write.

Extraction revisions
--------------------

An *extraction revision* is the revision of a repository at which the content
behind a node record's content hashes was read. A node record can carry one for
each repository its content anchors name. It is a reference, like an anchor.
It never enters a hash.

.. sreq:: A node record keeps the extraction revisions it is given
   :id: SEG-SREQ-304
   :refines: SEG-SYS-007

   Where an extraction revision is supplied for a repository that a node
   record's content anchors name, the affirmation store shall persist that
   revision with the node record.

.. sreq:: A node record without an extraction revision is read back as written
   :id: SEG-SREQ-305
   :refines: SEG-SYS-007

   The affirmation store shall read back a node record that carries no
   extraction revision as written.

.. sreq:: A malformed extraction revision is refused
   :id: SEG-SREQ-325
   :refines: SEG-SREQ-304

   If an extraction revision supplied with a node record is not 40 or 64
   lowercase hexadecimal characters, then the affirmation store shall refuse
   the write.

.. sreq:: No extraction revision is persisted as no field
   :id: SEG-SREQ-326
   :refines: SEG-SREQ-304

   The affirmation store shall persist a node record that carries no
   extraction revision with no extraction revision field, never with an empty
   map.
