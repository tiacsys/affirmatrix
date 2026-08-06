Verifying a proof
=================

.. warning::

   **This tutorial does not work yet.** The commands shown here document
   the target workflow; the command-line interface is being designed at
   this surface before it is built.

.. admonition:: Prerequisites

   - The ``./package`` directory from :doc:`seal-and-prove` — and nothing
     else. That is the point.

Change seats. You are no longer the maintainer; you are an assessor at a
certification body, handed a directory of four JSON documents by a company
whose word you are professionally required not to take. What can you check
with only the package and the tool?

Recompute
---------

.. code-block:: console

   $ affirmatrix proof verify ./package
   manifest        binds 3 documents         4/4 hashes match
   design root     recomputed from package   9f3c…e21   match
   coverage        report internally consistent with the record
   scope           partial — 5 of 59 requirements, declared
   affirmations    12 review events referenced, committer identities recorded
                   attestation not checkable from the package alone → REPORTED

   verified: integrity   REPORTED: affirmation authority
   exit 0

Every line above ``affirmations`` was **recomputed, not believed**: the
manifest's hashes were recalculated over the documents in the directory,
the design root re-derived from the node and edge hashes the proof
carries, the coverage report cross-checked against the execution record.
If anyone had edited a single byte of the package, the recomputation
would not match, and no assertion inside the package could talk its way
around that.

The honest last line
--------------------

The ``affirmations`` line is deliberately weaker, and the tool says so
rather than rounding up. The package *names* twelve review events, each
bound to content hashes — but whether each was really enacted by an
authorised committer at the recorded moment is attested by the store
lineage, a git history the package does not contain. From the package
alone that claim is **REPORTED**: self-describing, not self-verifying.

.. code-block:: console

   $ affirmatrix proof verify ./package --lineage <repository-url>
   affirmations    12/12 events found on the case lineage
                   committers checked against the authorised list   PASS

Given the lineage, the claim upgrades to a checked one. A verifier who is
not given the lineage keeps the REPORTED verdict — never a false PASS,
never a silent omission. (Where exactly the line between recomputable and
attested *should* sit is a live design question; this page states the
current boundary rather than wishing it away.)

Tamper with it
--------------

Verification you cannot watch fail is theatre. Edit one hash inside
``design_consistency_proof.json`` and re-run:

.. code-block:: console

   $ affirmatrix proof verify ./package
   manifest        binds 3 documents         3/4 hashes match
     design_consistency_proof.json: sha256 mismatch
       manifest says 55ab…c03, document hashes to 88f1…d9e
   verification failed — the package is not the one that was sealed
   exit 1

The failure names the document and both hashes. Which side is lying is
not the tool's to guess; that the two sides disagree is mechanical.

.. admonition:: Decisions this page forces

   - The verdict vocabulary: ``verified`` / ``REPORTED`` / ``failed`` —
     three levels, or is REPORTED a WARN in disguise?
   - What must a package carry so an assessor needs nothing else — and is
     the answer a *specification* (any implementation can verify) rather
     than this tool?
   - ``--lineage``: fetch a remote, read a local clone, or both? What is
     checked — event presence, committer list, non-rewritten history?
   - Does ``verify`` have a machine-readable report for the assessor's
     own records, and is *that* the real interface?
   - Exit codes: integrity failure is clearly ``1``; is REPORTED-only
     (no lineage given) ``0``, and does a strict mode make it ``1``?

This closes the story: content became records, records became a graph,
judgements bound the graph, drift was caught and cured, and a scope of it
was sealed into a package that just survived an adversarial read. That
loop — measure, judge, seal, verify — is the whole tool.
