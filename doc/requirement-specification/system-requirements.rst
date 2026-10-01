System Requirements
===================

The system requirements are blackbox claims about affirmatrix as a whole:
each says what the tool does, never how or by which part. Every software
requirement refines one of them. None of them carries an implementation or a
test of its own — a system requirement is discharged by the requirements
beneath it, wherever those live in this document.

.. sys:: Content-anchored evidence graph
   :id: SEG-SYS-001

   affirmatrix shall build the evidence graph from node and edge records,
   deriving every node hash, edge hash, and design root solely from the nodes'
   declared types and their content in each type's canonical form, and from
   the edges' declared endpoints and types, reproducibly across runs.

.. sys:: Transitive requirement satisfaction
   :id: SEG-SYS-002

   affirmatrix shall determine the satisfaction of every requirement in the
   graph by transitive closure over the refines relation.

.. sys:: Suspicion derived from current content
   :id: SEG-SYS-003

   affirmatrix shall derive whether each strong edge is active or suspect from
   its endpoints' current content measured against the content it was affirmed
   against, and from the states of the strong edges it depends on.

.. sys:: Affirmation is a recorded human judgement
   :id: SEG-SYS-004

   affirmatrix shall record each affirmation as a human judgement bound to the
   content of both edge endpoints at the moment the judgement was made.

.. sys:: Self-verifiable evidence packages
   :id: SEG-SYS-005

   affirmatrix shall generate, for a defined scope and without altering the
   graph, an evidence package whose claims are verifiable by recomputation
   from the package's own contents.

.. sys:: Gates block on unmet conditions
   :id: SEG-SYS-006

   While any condition of a gate is unmet, affirmatrix shall report the action
   that gate guards as blocked.

.. sys:: The graph persists as hashes and references
   :id: SEG-SYS-007

   affirmatrix shall persist the evidence graph as hashes and references,
   never as the content those hashes cover.

.. sys:: Blocked scopes are refused
   :id: SEG-SYS-008

   If the proof gate reports a scope as blocked, then affirmatrix shall refuse
   to generate an evidence package for that scope.

.. sys:: One built-in graph vocabulary
   :id: SEG-SYS-009

   affirmatrix shall determine node kinds, edge kinds, and which edges
   propagate suspicion from a single built-in vocabulary that no configuration
   redefines.

.. sys:: Operable from the command line
   :id: SEG-SYS-010

   affirmatrix shall make every workflow it performs operable from its command
   line, with the outcome of each invocation distinguishable by its exit
   status.

.. sys:: Affirmation state changes only by the operator's act
   :id: SEG-SYS-011

   affirmatrix shall change the recorded affirmation state only as the direct
   result of an act the operator performs.

.. sys:: Evidence currency against a revision
   :id: SEG-SYS-012

   affirmatrix shall derive whether each evidence edge is current or stale from
   the revision carried by the test outcome it touches, measured against the
   current revision of the implementation repository.
