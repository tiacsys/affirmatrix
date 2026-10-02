Proof Verifier
==============

The proof verifier reads an evidence package and checks it. A package is
sealed by its design root, and the other three documents are not. So the
verifier makes several checks and names each one. A check that needs more than
the package, such as the run bundles or the case, is made only when the
operator gives them. The verifier names every check it did not make, so a pass
never says more than the package supports.

The verifier judges a package at the revision the package records. It reads no
repository and needs no current revision.

When it rebuilds the evidence from run bundles, the verifier first checks that
the readers the configuration names supply the design the package records
(:need:`SEG-SREQ-244`). It then takes the design edges of the package as
affirmed. A package exists only for a scope that the gate found ready, so every
design edge was affirmed when the package was sealed. The check of the
affirmations (:need:`SEG-SREQ-241`) checks that separately, against the case.

.. sreq:: The verifier reports each check it makes
   :id: SEG-SREQ-236
   :refines: SEG-SYS-005

   The proof verifier shall report, for every check it makes of an evidence
   package, whether the package passes that check.

.. sreq:: The design root is recomputed
   :id: SEG-SREQ-237
   :refines: SEG-SREQ-236

   The proof verifier shall recompute the design root of an evidence package
   from the node hashes, the design edges, the scope and the revision that the
   package's design consistency proof records, and report whether it equals
   the recorded root.

.. sreq:: The documents agree on what the package is
   :id: SEG-SREQ-238
   :refines: SEG-SREQ-236

   The proof verifier shall report whether the documents of an evidence
   package agree on the snapshot, the requested scope and the revision.

.. sreq:: The documents agree on the evidence
   :id: SEG-SREQ-239
   :refines: SEG-SREQ-236

   The proof verifier shall report whether every outcome and every finding
   that the documents of an evidence package name is a member of the
   package's scope, and whether the execution coverage record and the
   coverage report agree on which outcomes are set aside, skipped and
   excused.

.. sreq:: A package records an unblocked scope
   :id: SEG-SREQ-240
   :refines: SEG-SREQ-236

   The proof verifier shall report whether the coverage report of an
   evidence package records the scope as not blocked.

.. sreq:: Affirmations stand behind the design edges
   :id: SEG-SREQ-241
   :refines: SEG-SREQ-236

   While it is given a case, the proof verifier shall report, for every
   strong edge of an evidence package's design set, whether the case holds a
   review event that binds the edge's endpoints to the node hashes the
   package records for them.

.. sreq:: A bundle the package does not list is a mismatch
   :id: SEG-SREQ-242
   :refines: SEG-SREQ-236

   If a run bundle given to the proof verifier has a digest that the
   evidence package does not list, then the proof verifier shall report a
   mismatch.

.. sreq:: A listed bundle that is not given leaves the evidence unjudged
   :id: SEG-SREQ-243
   :refines: SEG-SREQ-236

   If an evidence package lists the digest of a run bundle and the proof
   verifier is given run bundles but none with that digest, then the proof
   verifier shall report that the evidence cannot be judged.

.. sreq:: The configured design must be the package's design
   :id: SEG-SREQ-244
   :refines: SEG-SREQ-236

   If the readers the configuration names do not supply a design node of an
   evidence package with the node hash the package records, or do not supply
   a design edge the package records, then the proof verifier shall report
   that the evidence cannot be judged.

.. sreq:: The evidence follows from the bundles
   :id: SEG-SREQ-245
   :refines: SEG-SREQ-236

   While it is given run bundles whose digests the package lists, the proof
   verifier shall report whether the outcomes and findings it rebuilds from
   those run bundles at the revision the package records, judged at the date
   of the snapshot timestamp that the recorded snapshot identifier carries,
   equal the outcomes and findings the package records.

.. sreq:: The snapshot identifier follows from the scope
   :id: SEG-SREQ-246
   :refines: SEG-SREQ-236

   While it rebuilds the evidence of an evidence package, the proof verifier
   shall report whether the snapshot identifier minted from the rebuilt
   scope, with the timestamp the recorded identifier carries, equals the
   recorded identifier.
