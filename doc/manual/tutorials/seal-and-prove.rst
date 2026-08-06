Sealing a proof
===============

.. warning::

   **This tutorial does not work yet.** The commands shown here document
   the target workflow; the command-line interface is being designed at
   this surface before it is built.

.. admonition:: Prerequisites

   - The re-affirmed, all-active graph from :doc:`detect-drift`.

A green ``status`` is a private comfort; a proof is a public artifact. The
proof workflow packages a scope of the graph — recomputable hashes, the
affirmation trail, the coverage story — into documents an outsider can
check without trusting you. Between the graph and the package stands a
gate, and the gate is allowed to say no.

Ask the gate
------------

Scope the proof to the commitment-layer subtree:

.. code-block:: console

   $ affirmatrix proof gate --scope SEG-SYS-009
   scope SEG-SYS-009: 5 requirements, 3 implementations, 4 test specs
   coverage:
     SEG-SREQ-034   no TestOutcome for SEG-TS-003 in the current run
   blocked — 1 gap
   exit 1

The gate reports the gap **at the requirement that lacks coverage**, not
at some parent that inherits the problem — you fix ``SEG-TS-003``'s
missing run, not ``SEG-SYS-009``. Run the missing test, extract the
fresh outcome, and ask again:

.. code-block:: console

   $ affirmatrix records extract test-outcomes
   test-outcomes   9 nodes   19 confirms+witnesses   build/reports/
   $ affirmatrix proof gate --scope SEG-SYS-009
   scope SEG-SYS-009: 5 requirements, 3 implementations, 4 test specs
   coverage: complete
   ready — scope is partial: 5 of 59 requirements
   exit 0

``ready`` comes with a qualifier that will follow the package everywhere:
**partial**. This proof will speak for five requirements and stay silent
on fifty-four, and it says so itself, because a proof that publishes its
scope cannot be quietly waved at a larger claim than it makes.

Generate the package
--------------------

.. code-block:: console

   $ affirmatrix proof generate --scope SEG-SYS-009 --output-dir ./package
   design_consistency_proof.json    scope recomputation, design root 9f3c…e21
   execution_coverage_record.json   4 specs, 4 fresh outcomes
   coverage_report.json             complete over scope; scope partial 5/59
   evidence_manifest.json           binds the three above by hash
   4 documents → ./package   (nothing committed; placement is yours)

Four documents, one job each: design consistency (the hashes recompute),
execution coverage (which tests witnessed what), the coverage report (the
gate's verdict, frozen), and the manifest that seals the other three
together. Generation changed nothing in the graph — generating a proof
is a read, and running it twice produces the same package.

Placement is a store act like any other: you review the package, place it
under ``case/proofs/``, and commit the lineage.

Refusal is a feature
--------------------

Try the scope that cannot work — ``SEG-SYS-001`` depends on components
that do not exist yet:

.. code-block:: console

   $ affirmatrix proof generate --scope SEG-SYS-001 --output-dir ./package2
   refused: scope SEG-SYS-001 is blocked
     SEG-SREQ-001   no implementation on record
     SEG-SREQ-017   no implementation on record
   no part of a package was written
   exit 1

A blocked scope yields **no part** of a package — not a draft, not a
partial directory, nothing a hurried release process could mistake for
evidence. The refusal carries the gate's report so the next action is
obvious. And only blocked scopes are refused: a tool that could refuse
anything it disliked would satisfy every other requirement by refusing
everything.

.. admonition:: Decisions this page forces

   - ``gate`` and ``generate`` as separate verbs (ask first, then act) —
     or should ``generate`` be the only entry, with the gate implicit?
   - Scope language: a single subtree root shown here — are unions,
     explicit lists, or named scope labels needed in v1?
   - Where does the run identity come from (``--run-id`` in the old
     prototype) — CLI flag, config, or derived from the outcome records?
   - Output naming and format of the four documents; JSON here, and the
     schema under ``case/schema/`` is the authority.
   - Exit codes: is ``blocked`` (``1``) distinct from ``refused``
     (``1``?) distinct from structural error (``2``)?

Next: :doc:`verify-a-proof` — the other side of the table.
