Gate Evaluator
==============

A gate is a set of conditions that must hold before an action may proceed.
The gate evaluator judges those conditions and reports the result; it does not
enforce it. Its requirements fix which findings block and which merely inform,
what a blocked report must contain for anyone to act on it, and one condition
that would otherwise pass in silence — a scope with nothing in it to seal.

.. sreq:: Severity decides what blocks
   :id: SEG-SREQ-042
   :refines: SEG-SYS-006

   The gate evaluator shall treat a condition reported as an error or a
   warning as blocking, and a condition reported as information as not
   blocking.

.. sreq:: Every unready edge is listed
   :id: SEG-SREQ-043
   :refines: SEG-SYS-006

   The gate evaluator shall list in its report every strong edge in scope that
   is not active.

.. sreq:: Gaps are reported where coverage is missing
   :id: SEG-SREQ-044
   :refines: SEG-SYS-006

   The gate evaluator shall report a coverage gap at the requirement that
   lacks coverage, never at a requirement that it refines.

.. sreq:: An empty design set cannot be sealed
   :id: SEG-SREQ-045
   :refines: SEG-SYS-006

   If a scope's design set is empty, then the gate evaluator shall report that
   scope as blocked.

.. sreq:: A waiver is valid only when unexpired and its approver is authorised
   :id: SEG-SREQ-059
   :refines: SEG-SYS-006

   The gate evaluator shall treat an excusing waiver as valid only when it has
   not expired and its recorded approver is authorised to grant it.

.. sreq:: An unexcused or invalidly waived failure blocks
   :id: SEG-SREQ-060
   :refines: SEG-SYS-006

   If a non-passing outcome is not excused by a valid waiver, then the gate
   evaluator shall report that outcome as blocking.

.. sreq:: A validly excused failure only informs
   :id: SEG-SREQ-061
   :refines: SEG-SYS-006

   If a non-passing outcome is excused by a valid waiver, then the gate
   evaluator shall report that outcome as informational.

.. sreq:: A stale outcome is not evidence
   :id: SEG-SREQ-063
   :refines: SEG-SYS-006

   The gate evaluator shall treat an outcome whose recorded revision differs
   from the current revision it is given as absent when it judges the
   specification that outcome confirms.

.. sreq:: Diagnostic conditions are a closed vocabulary
   :id: SEG-SREQ-064
   :refines: SEG-SYS-006

   The gate evaluator shall report the condition of every diagnostic as one
   member of a fixed set of named conditions.

.. sreq:: A diagnostic's condition carries no occurrence-specific detail
   :id: SEG-SREQ-065
   :refines: SEG-SYS-006

   The gate evaluator shall keep every diagnostic's condition free of detail
   that varies by occurrence, such as which state an edge is in.

.. sreq:: A stale outcome is reported
   :id: SEG-SREQ-067
   :refines: SEG-SYS-006

   The gate evaluator shall report an outcome whose recorded revision
   differs from the current revision it is given as an informational
   finding in its report.
