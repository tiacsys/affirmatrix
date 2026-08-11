Proof Generator
===============

The proof generator assembles an evidence package for a defined scope: what
the package contains, what it must carry so a reader can recompute its claims
without the graph in hand, and what it must leave untouched while doing so.
Its requirements also cover the refusal path — when the proof gate reports a
scope blocked, no part of a package for that scope comes into existence, and
the refusal arrives with the gate's report attached.

.. sreq:: An evidence package has four parts
   :id: SEG-SREQ-035
   :refines: SEG-SYS-005

   The proof generator shall assemble every evidence package from a design
   consistency proof, an execution coverage record, a coverage report, and an
   evidence manifest.

.. sreq:: Scope is collected over strong edges
   :id: SEG-SREQ-036
   :refines: SEG-SYS-005

   The proof generator shall include in a package's scope every node reachable
   from the requested requirements through strong edges.

.. sreq:: Packages carry what their root recomputes from
   :id: SEG-SREQ-037
   :refines: SEG-SYS-005

   The proof generator shall record in every evidence package the node hashes
   needed to recompute that package's design root.

.. sreq:: Packages state their scope
   :id: SEG-SREQ-038
   :refines: SEG-SYS-005

   The proof generator shall record in every evidence package the scope for
   which it was generated.

.. sreq:: Packages say whether their scope is total
   :id: SEG-SREQ-039
   :refines: SEG-SYS-005

   The proof generator shall report in every evidence package whether that
   package's scope includes every requirement that refines no other
   requirement.

.. sreq:: Stale outcomes are excluded
   :id: SEG-SREQ-040
   :refines: SEG-SYS-005

   The proof generator shall exclude from an evidence package every outcome
   that was not produced against the current implementation content.

.. sreq:: Generation changes nothing
   :id: SEG-SREQ-041
   :refines: SEG-SYS-005

   The proof generator shall leave node, edge and affirmation state unchanged
   when it generates an evidence package.

.. sreq:: Snapshot identifiers are portable path names
   :id: SEG-SREQ-052
   :refines: SEG-SYS-005

   The proof generator shall mint every snapshot identifier using only
   characters that are valid in a file name on both POSIX and Windows
   filesystems.

.. sreq:: A blocked scope yields no package at all
   :id: SEG-SREQ-046
   :refines: SEG-SYS-008

   If the proof gate reports a scope as blocked, then the proof generator
   shall produce no part of an evidence package for that scope.

.. sreq:: Refusals are explained
   :id: SEG-SREQ-047
   :refines: SEG-SYS-008

   The proof generator shall accompany every refusal with the gate's report
   for the refused scope.

.. sreq:: Only blocked scopes are refused
   :id: SEG-SREQ-048
   :refines: SEG-SYS-008

   The proof generator shall refuse only those scopes the proof gate reports
   as blocked.
