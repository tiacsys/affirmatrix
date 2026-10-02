Record Source
=============

The record source is the input interface — the role every supplier of node
and edge records fills, whether a stream describes today's content or brings
back what the case recorded. Its requirements bind what any supplier must put
on the records it supplies, so a datum the rest of the engine depends on
cannot be present in one stream and missing from another.

.. sreq:: Test outcomes carry their result
   :id: SEG-SREQ-055
   :refines: SEG-SYS-002

   The record source shall supply, in every test outcome record, the result of
   the test execution that outcome records.

What the gate judges by
-----------------------

.. sreq:: The record source supplies what the gate judges by
   :id: SEG-SREQ-132
   :refines: SEG-SYS-006

   The record source shall supply, on every waiver record and every test
   outcome record, each datum the gate evaluator judges that record's
   validity or currency by.

.. sreq:: Waivers carry their expiry
   :id: SEG-SREQ-057
   :refines: SEG-SREQ-132

   The record source shall supply, in every waiver record, the date on which
   the waiver expires.

.. sreq:: Waivers carry their approver
   :id: SEG-SREQ-058
   :refines: SEG-SREQ-132

   The record source shall supply, in every waiver record, the name of the
   approver who granted it.

.. sreq:: Test outcomes carry the revision they ran against
   :id: SEG-SREQ-062
   :refines: SEG-SREQ-132

   The record source shall supply, in every test outcome record, the
   revision of the implementation repository the test execution ran
   against.

Anchors
-------

.. sreq:: An anchor names a repository by configured name
   :id: SEG-SREQ-134
   :refines: SEG-SYS-007

   Where the anchored content was read from a repository, the record source
   shall name that repository in the content anchor by its configured name,
   never by a path.

.. sreq:: Every content hash is supplied with an anchor
   :id: SEG-SREQ-143
   :refines: SEG-SYS-007

   The record source shall supply, with every content hash it supplies, an
   anchor from which the content the hash covers can be found again.

Content behind a hash
---------------------

A record source that reads content can also hand that content back, so an
operator can compare it with what the case recorded. The outcome reader
supplies no content: the record it hashes is built from a run bundle.

.. sreq:: A record source supplies the bytes it hashed
   :id: SEG-SREQ-311
   :refines: SEG-SYS-015

   Where a record source reads the content that a content hash it supplies
   covers, the record source shall supply, for a node and the name of one of
   its content hashes, the bytes from which it computed that hash.
