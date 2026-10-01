Satisfaction Evaluator
======================

The satisfaction evaluator answers one question about every requirement in
the graph: is it satisfied? Its requirements give the two rules that answer it
— one for a requirement nothing refines, one for a requirement something
refines — together with the properties that make the answer worth having. It
reads the whole graph rather than a scope, it repeats, and it changes
nothing.

A skipped outcome is the runner's statement that the test did not run under
one configuration. It adds no evidence and takes none away. A specification
that every run skipped has no evidence, so its leaf is not satisfied.

The evaluator does not read the state of an evidence edge. The gate has already
cut the stale outcomes from the graph it hands over.

.. sreq:: Leaf satisfaction rule
   :id: SEG-SREQ-006
   :refines: SEG-SYS-002

   The satisfaction evaluator shall report a leaf requirement as satisfied
   when, and only when, it carries at least one active verifies edge, at least
   one active implements edge, and every test specification named by a
   verifies edge — whatever that edge's own state — has at least one
   confirming outcome whose result is not skipped, and every confirming
   outcome whose result is not skipped either passed or is excused by a
   waiver.

.. sreq:: Non-leaf satisfaction rule
   :id: SEG-SREQ-007
   :refines: SEG-SYS-002

   The satisfaction evaluator shall report a non-leaf requirement as satisfied
   when, and only when, every requirement refining it is satisfied and every
   verifies or implements edge it carries is active, regardless of whether the
   outcomes of the specifications those edges name have passed.

.. sreq:: Satisfaction is evaluated over the whole graph
   :id: SEG-SREQ-008
   :refines: SEG-SYS-002

   The satisfaction evaluator shall determine satisfaction from the whole
   graph, never from a subset of it.

.. sreq:: Verdicts repeat
   :id: SEG-SREQ-009
   :refines: SEG-SYS-002

   The satisfaction evaluator shall produce the same verdict for the same
   graph on every evaluation.

.. sreq:: Evaluation leaves the graph unchanged
   :id: SEG-SREQ-010
   :refines: SEG-SYS-002

   The satisfaction evaluator shall leave the graph unchanged when evaluating
   it.
