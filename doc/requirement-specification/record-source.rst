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

.. sreq:: An anchor names its repository by configured name
   :id: SEG-SREQ-134
   :refines: SEG-SYS-007

   The record source shall name, in every content anchor it supplies, the
   repository the anchored content was read from by that repository's
   configured name, never by a path.
