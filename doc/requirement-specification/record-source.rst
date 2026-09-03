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

.. sreq:: Waivers carry their expiry
   :id: SEG-SREQ-057
   :refines: SEG-SYS-006

   The record source shall supply, in every waiver record, the date on which
   the waiver expires.

.. sreq:: Waivers carry their approver
   :id: SEG-SREQ-058
   :refines: SEG-SYS-006

   The record source shall supply, in every waiver record, the name of the
   approver who granted it.

.. sreq:: Test outcomes carry the revision they ran against
   :id: SEG-SREQ-062
   :refines: SEG-SYS-006

   The record source shall supply, in every test outcome record, the
   revision of the implementation repository the test execution ran
   against.
