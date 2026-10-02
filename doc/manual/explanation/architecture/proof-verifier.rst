The proof verifier
===================

A package is sealed by its design root, and the other three documents are
not. A package that goes to an assessor comes without its case, its run bundles
and the readers that made it. So the proof verifier makes a fixed list of named
checks, and each check says what it found. It names every check it did not make.
A pass then never says more than the package supports (:need:`SEG-SREQ-236`).

:func:`affirmatrix.proof.verify` reads one package directory and returns a
:class:`~affirmatrix.proof.Verification` with ten
:class:`~affirmatrix.proof.Check` values, always in the same order. The command
line page shows how ``proof verify`` prints them (:doc:`command-line-interface`).

Four statuses
--------------

``passed`` and ``failed``
   The verifier reached a verdict.

``not judged``
   The operator asked for the check, and the verifier could not reach a verdict.
   A run bundle that the package does not list the partner of, or a design that
   the readers do not supply, gives this status.

``not made``
   The operator did not ask for the check, so nothing was tried.

A check that fails or is not judged has a ``detail`` that names the subject: a
digest, a node, or both ends of an edge. The verifier raises no error for a
package that reads but fails a check.

The ten checks
---------------

======================  ==========================  ===============================================
Check                   Needs                       What it asks
======================  ==========================  ===============================================
``root``                the package                 Does the design recompute to the recorded root?
                                                    (:need:`SEG-SREQ-237`)
``identity``            the package                 Do the documents and the directory name one
                                                    package? (:need:`SEG-SREQ-238`,
                                                    :need:`SEG-SREQ-264`)
``agreement``           the package                 Do the documents agree on members, set-aside,
                                                    skipped and excused outcomes, and revision?
                                                    (:need:`SEG-SREQ-239`, :need:`SEG-SREQ-265`,
                                                    :need:`SEG-SREQ-266`, :need:`SEG-SREQ-267`)
``unblocked``           the package                 Does the report record an unblocked scope?
                                                    (:need:`SEG-SREQ-240`, :need:`SEG-SREQ-268`,
                                                    :need:`SEG-SREQ-269`)
``affirmations``        a case                      Does a review event bind each design edge?
                                                    (:need:`SEG-SREQ-241`)
``bundle-digests``      run bundles                 Are the given bundles the listed ones?
                                                    (:need:`SEG-SREQ-242`, :need:`SEG-SREQ-243`)
``design-guard``        run bundles, configuration  Do the readers supply the design of the package?
                                                    (:need:`SEG-SREQ-244`)
``rebuilt-evidence``    run bundles, configuration  Do the outcomes and findings rebuilt from the
                                                    bundles equal the recorded ones?
                                                    (:need:`SEG-SREQ-245`)
``snapshot-id``         run bundles, configuration  Does the rebuilt scope mint the recorded
                                                    identifier? (:need:`SEG-SREQ-246`)
``sibling-digests``     nothing                     Always ``not made``: a package records no digest
                                                    of its sibling documents.
======================  ==========================  ===============================================

The first four checks need nothing but the package. They are always made, with no
configuration, no case and no run bundle (:need:`SEG-SREQ-270`). Without a case,
``affirmations`` is not made. Without run bundles, the four bundle checks are
not made.

The root
---------

``root`` calls :func:`affirmatrix.proof._package.sealed_root`, the same function
that seals a package at generation. It takes the scope, the revision, the node
hashes and the design edges from the design consistency proof and from nothing
else. The generator and the verifier share this one function, so they cannot
drift apart. The hand recipe of the tutorial gives the same value.

The other three documents are not sealed. A whole new set of consistent siblings
passes the four package checks. The checks that need the case or the bundles are
there for this reason.

Affirmations
-------------

A review event binds an edge when the node hash of each end, derived from the
content hashes that the event holds, equals the node hash that the package
records for that end. The edge needs one such event. The check asks whether these
hashes were ever affirmed. The store has no event that revokes an affirmation, so
one binding event is enough, and an older event made against other content does
not count against a later one.

A pass shows that the case holds an affirmation for each edge at the recorded
hashes. It does not show who made it. The case is not sealed.

The run bundles and the rebuild
---------------------------------

With run bundles, the verifier works in this order.

1. ``bundle-digests`` computes the digest of each given bundle. A bundle that the
   package does not list is a mismatch and fails the check. If every given
   bundle is listed but a listed bundle is not given, the check is not judged.
   A mismatch outranks a missing bundle.
2. ``design-guard`` builds the design from the readers that the configuration
   names, with no run bundle, and compares it with the package. Each design node
   needs the same node hash, and each design edge needs to come from a reader. A
   change of requirement text since the package was made is a mismatch. The check
   reads the configured sources by hash and runs no git command.
3. Only when both passed, the rebuild runs. Otherwise ``rebuilt-evidence`` and
   ``snapshot-id`` are not judged, and nothing is rebuilt.

The rebuild reads the run bundles through the readers, collects the scope of the
package, and judges it with the package gate. It judges at the revision that the
package records and at the date of the snapshot timestamp that the recorded
identifier carries. It does not use today's date. It then compares the rebuilt
execution coverage record and the rebuilt coverage report with the recorded ones.
It mints the snapshot identifier again from the rebuilt scope, with the recorded
timestamp, and compares that too.

The rebuild takes the design edges of the package as affirmed. A package exists
only for a scope that the gate found ready, so each design edge was affirmed when
the package was sealed. A strong edge that the readers supply and the package does
not record keeps the state the readers give it. It shows as an unready edge, and
the rebuilt report then differs from the recorded one. ``affirmations`` shows the
affirmations separately, against the case.

A run bundle that the outcome extractor refuses ends the verb with exit status 2
and no report.

Where it lives
---------------

``affirmatrix.proof._verify`` holds the checks. ``affirmatrix.proof._stored``
holds the reader of a package directory and the summary for ``proof show``. The
reader is :func:`affirmatrix.case.read_package_directory`. It validates each
document with the schemas that the tool carries, so a package outside any case
reads the same way as one inside a case.

The verifier calls the configured readers. For this reason the proof component
may import the sources package, and ``tests/unit/test_import_layering.py`` lists
it. The sources package imports nothing above the records, so there is no cycle.
The verifier reads no repository, takes no current revision, and writes nothing.
