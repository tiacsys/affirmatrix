Sealing a proof
===============

.. warning::

   The console blocks on this page were taken before test evidence came from
   run bundles, and you cannot reproduce them now. This repository's own
   case has no test evidence until its own test run is read as a run bundle.
   So the proof over its scope is blocked (every requirement in it reports
   an incomplete coverage), and no package can be sealed here now. A later
   change will bring this page up to date. Read it as a description of the
   workflow, not as a transcript that you can repeat today.

.. admonition:: Prerequisites

   - The affirmed, committed graph from :doc:`affirm-an-edge` — fourteen
     edges active, the other 287 pending. Nothing from :doc:`detect-drift`
     carries over: that page worked on copies.

A green ``graph status`` is a private comfort; a proof is a public
artifact. The proof workflow packages a scope of the graph — recomputable
hashes, the run's outcomes, the gate's own report — into documents that
can be checked without trusting whoever wrote them. Between the graph and
the package stands a gate, and the gate is allowed to say no.

Note what the state above makes possible. Only fourteen of 301 edges are
active, and that is enough: a proof is made over a **scope**, one subtree
of the graph, and a scope whose edges are all affirmed and whose tests
have run can be sealed while the rest of the graph stays pending. The
proof will say how little it covers. This page shows all three: the scope
that seals, the scope that cannot, and what the package says about itself.

Ask the gate
------------

``proof check`` puts the gate's question — is there anything in this scope
that should stop a package being generated? — and generates nothing
(:need:`SEG-SREQ-090`). The scope is a requirement, and everything
reachable from it through strong edges comes with it
(:need:`SEG-SREQ-036`). Ask about the vocabulary subtree you affirmed:

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-009
   no implementation repository is configured; a revision must be given explicitly (--revision)
   $ echo $?
   2

Exit 2: the request could not be judged. The gate compares each recorded
test outcome with the revision of the implementation repository, and the
would-be store carries no repository to discover one from. The rule for
obtaining it is the affirmation's own (:need:`SEG-SREQ-112`): a revision
you give is recorded as given, and where none can be discovered it is
required. It is the same ``678f72f`` as on the last two pages, for the
same reason, and the next section says why it matters more here.

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-009 --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   blocked: False
   $ echo $?
   0

``blocked: False`` is the tool's own rendering of "ready"; there is no
report to read because there is nothing to report. ``--json`` prints the
same verdict as the coverage report itself (:need:`SEG-SREQ-091`), the
document a package will carry, and here every field of it is empty or
false:

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-009 --revision 678f72f5371cd69416adb9199ff0af54b706acdb --json
   {
     "blocked": false,
     "coverageGaps": [],
     "designSetEmpty": false,
     "diagnostics": [],
     "discardedOutcomes": [],
     "excusedOutcomes": [],
     "skippedOutcomes": [],
     "staleOutcomes": [],
     "unreadyEdges": [],
     "unwaivedOutcomes": []
   }

Every strong edge in the scope is active, every requirement is covered by
a passing test, and the gate finds nothing. What "ready" does **not** mean
is ready to be believed about the rest of the graph: it speaks for
``SEG-SYS-009`` and its subtree, and is silent about the other ten
top-level requirements. The package says so itself, as below.

A scope that cannot be sealed
-----------------------------

Ask the same question about ``SEG-SYS-001``, the content-anchored graph
you met on the first page. Its subtree was never affirmed:

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb | head -4
   blocked: True
     warning: strong edge not active (affirmatrix.commitment.design_root -> SEG-SREQ-003 (Implements))
     warning: strong edge not active (affirmatrix.commitment.edge_hash -> SEG-SREQ-002 (Implements))
     warning: strong edge not active (affirmatrix.commitment.node_hash -> SEG-SREQ-005 (Implements))
   $ affirmatrix proof check --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb > /dev/null; echo $?
   1

The report is longer than four lines, and this page will not print it
all. It counts:

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb | grep -c 'strong edge not active'
   19
   $ affirmatrix proof check --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb | grep -c 'own coverage is incomplete'
   7
   $ affirmatrix proof check --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb | grep 'own coverage is incomplete' | head -2
     warning: the requirement's own coverage is incomplete (SEG-SREQ-001)
     warning: the requirement's own coverage is incomplete (SEG-SREQ-002)

Twenty-six findings, of two kinds. Nineteen are the strong edges in scope
that are not active: the gate lists every one of them, not a sample
(:need:`SEG-SREQ-043`). Seven are coverage gaps, and each is reported at
the requirement that lacks the coverage — the seven leaves — never at
``SEG-SYS-001`` above them, which would only inherit the problem
(:need:`SEG-SREQ-044`). You fix the leaves, not the root. The severity
of a finding decides whether it counts: a warning or an error blocks, an
information finding does not (:need:`SEG-SREQ-042`).

The revision, and why it must be the run's
------------------------------------------

Every test outcome in the store was recorded against one revision of the
implementation repository. The gate compares that with the revision it is
given, and an outcome recorded against any other is not evidence: it is
treated as absent when the specification it confirms is judged
(:need:`SEG-SREQ-063`), and reported as information
(:need:`SEG-SREQ-067`). To see it, give the gate a revision that is
deliberately wrong — any other forty hex digits — over the scope that was
ready a moment ago:

.. code-block:: console

   $ affirmatrix proof check --scope SEG-SYS-009 --revision 0123456789abcdef0123456789abcdef01234567
   blocked: True
     warning: the requirement's own coverage is incomplete (SEG-SREQ-029)
     warning: the requirement's own coverage is incomplete (SEG-SREQ-030)
     warning: the requirement's own coverage is incomplete (SEG-SREQ-031)
     warning: the requirement's own coverage is incomplete (SEG-SREQ-032)
     info: outcome's recorded revision differs from the current revision (run-0001/SEG-TS-001)
     info: outcome's recorded revision differs from the current revision (run-0001/SEG-TS-002)
     info: outcome's recorded revision differs from the current revision (run-0001/SEG-TS-003)
     info: outcome's recorded revision differs from the current revision (run-0001/SEG-TS-009)
   $ echo $?
   1

Nothing in the scope changed. The four outcomes went stale, so the four
requirements lost the tests that covered them; the stale outcomes are
named as information, and the gaps they leave are the warnings that
block. This is why the revision is the run's, ``678f72f``, and not the
repository's head: a proof over a revision the tests never ran against
would claim coverage that no run observed. It is also why the check is
read-only and cheap to repeat — it is how you find out before generating.

Generate the package
--------------------

With a scope the gate passes, ``proof generate`` assembles the package
and writes it (:need:`SEG-SREQ-092`). It takes the same scope and the same
revision, and it writes under the case by default
(:need:`SEG-SREQ-093`):

.. code-block:: console

   $ affirmatrix proof generate --scope SEG-SYS-009 --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   snapshot: 20260929T094143Z-0fbcfe027e43
   wrote coverage_report: …/case/proofs/20260929T094143Z-0fbcfe027e43/coverage_report.jsonld
   wrote design_consistency_proof: …/case/proofs/20260929T094143Z-0fbcfe027e43/design_consistency_proof.jsonld
   wrote evidence_manifest: …/case/proofs/20260929T094143Z-0fbcfe027e43/evidence_manifest.jsonld
   wrote execution_coverage_record: …/case/proofs/20260929T094143Z-0fbcfe027e43/execution_coverage_record.jsonld
   $ echo $?
   0

The tool prints absolute paths; the leading part is cut here. The
snapshot identifier is a timestamp and a digest, joined by a hyphen, made
of characters that are valid in a file name on any filesystem
(:need:`SEG-SREQ-052`). Yours will differ in the timestamp, which is the
moment you ran it; the digest is a fingerprint of the scope's content, so
over the same graph it will match.

.. code-block:: console

   $ ls case/proofs
   20260929T094143Z-0fbcfe027e43
   $ ls case/proofs/20260929T094143Z-0fbcfe027e43
   coverage_report.jsonld
   design_consistency_proof.jsonld
   evidence_manifest.jsonld
   execution_coverage_record.jsonld

Four documents, every package (:need:`SEG-SREQ-035`), one job each:

- ``coverage_report.jsonld`` is the gate's report, frozen: the nine
  fields you saw with ``--json``, all empty. It is the verdict the
  package was generated under.
- ``design_consistency_proof.jsonld`` is what makes the design
  recomputable. It carries the design root, the revision and the scope, a
  manifest of the fifteen nodes in scope with a hash for each — the
  requirement ``SEG-SYS-009``, its four requirements, six implementations
  and four test specifications — and the fourteen strong edges among
  them (:need:`SEG-SREQ-037`). Anyone holding those can recompute the
  root without the graph that produced it.
- ``execution_coverage_record.jsonld`` is the run: the four passing
  outcomes of the four tests in scope, each with the revision it ran at.
  An outcome the gate reported stale is left out of it
  (:need:`SEG-SREQ-040`).
- ``evidence_manifest.jsonld`` binds them. It names the other three
  documents, the scope that was requested and the scope actually
  collected, the revision, and whether the scope is total:

.. code-block:: console

   $ cat case/proofs/20260929T094143Z-0fbcfe027e43/evidence_manifest.jsonld
   {
     "@context": "../../context.jsonld",
     "coverageReport": "coverage_report.jsonld",
     "designConsistencyProof": "design_consistency_proof.jsonld",
     "executionCoverageRecord": "execution_coverage_record.jsonld",
     "memberScope": [
       "SEG-SREQ-029",
       "SEG-SREQ-030",
       "SEG-SREQ-031",
       "SEG-SREQ-032",
       "SEG-SYS-009",
       "SEG-TS-001",
       …
       "run-0001/SEG-TS-009"
     ],
     "requestedScope": [
       "SEG-SYS-009"
     ],
     "revision": "678f72f5371cd69416adb9199ff0af54b706acdb",
     "snapshotId": "20260929T094143Z-0fbcfe027e43",
     "total": false
   }

The middle of the member list is cut here; it holds nineteen names in
all — the fifteen design nodes and the four outcomes that confirm the
tests, which travel with them (:need:`SEG-SREQ-066`). You asked for one
requirement; the scope holds what it reaches.

``"total": false`` is the package speaking for itself. A scope is total
when it includes every top-level requirement in the graph, and this one
includes one of eleven (:need:`SEG-SREQ-039`). The claim the package
makes is exactly the claim it covers, and anyone reading the manifest
sees the difference before they see anything else. A proof that publishes
its scope cannot be quietly waved at a larger claim than it makes.

Generation changed nothing in the graph: no node, edge or affirmation
moved (:need:`SEG-SREQ-041`). It is a read that leaves files behind.

Running it again
~~~~~~~~~~~~~~~~

Run the same command a second time and a second directory appears beside
the first, under a new snapshot identifier, because the timestamp part
is a new moment. The content is the same; the two identifiers differ, and
so does the design root, which is sealed together with the identifier.
Within the same second the identifier repeats and the same files are
written again. ``--timestamp`` names the instant yourself, if you want
the identifier to be one you can reproduce. Don't run it again on this
case: each run leaves a package, and the one you are about to commit
should be the only one.

``--output-dir <dir>`` writes the package somewhere other than the case
(:need:`SEG-SREQ-094`), for a package you want to look at without adding
it to the lineage.

Refusal is a feature
--------------------

Ask ``proof generate`` for the scope that cannot be sealed:

.. code-block:: console

   $ affirmatrix proof generate --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb | head -3
   refused: scope ['SEG-SYS-001'] (snapshot '20260929T094143Z-f0a195538008') is blocked: 26 blocking finding(s)
     warning: strong edge not active (affirmatrix.commitment.design_root -> SEG-SREQ-003 (Implements))
     warning: strong edge not active (affirmatrix.commitment.edge_hash -> SEG-SREQ-002 (Implements))
   $ affirmatrix proof generate --scope SEG-SYS-001 --revision 678f72f5371cd69416adb9199ff0af54b706acdb > /dev/null; echo $?
   1

The refusal is the gate's report, the same twenty-six findings, attached
to the refusal so the next action is obvious (:need:`SEG-SREQ-047`,
:need:`SEG-SREQ-097`). And nothing was written: a blocked scope yields no
part of a package — not a draft, not a partial directory, nothing a
hurried release process could mistake for evidence
(:need:`SEG-SREQ-046`). The snapshot identifier in the message was only
computed; no directory exists for it. Only blocked scopes are refused
(:need:`SEG-SREQ-048`): a tool that could refuse anything it disliked
would satisfy every other requirement by refusing everything.

The commit is the seal
----------------------

Like an affirmation, the package is a draft until it is committed. The
tool wrote four files under ``case/proofs/`` and stopped; nothing has
named them yet. Sealing is the commit, made by you in the case's own
lineage, as on :doc:`affirm-an-edge`:

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

The message is yours. The commit carries the four documents and nothing
else: the graph did not move. Once it exists, the package is a fact of the
lineage — who sealed it, when, and that it was deliberate.

What the package does not say
-----------------------------

It does not say the code is correct. It says what was designed, that the
design hashes to this root, that these tests passed at this revision, and
that the gate found nothing wrong with the scope; the boundary of that
statement is the one on :doc:`detect-drift`, and is set out in
:doc:`../explanation/architecture/guarantee-boundary`. What the tool made
is for someone else to check, which is the next page.

Next: :doc:`verify-a-proof` — the other side of the table.
