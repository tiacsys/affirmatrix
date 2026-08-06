Building the graph
==================

.. warning::

   **This tutorial does not work yet.** The commands shown here document
   the target workflow; the command-line interface is being designed at
   this surface before it is built.

.. admonition:: Prerequisites

   - The repository installed and the case mounted (:doc:`installation`).

The graph does not exist until records do. Records come from *producers* —
readers and extractors that walk the repository's own documents and code
and emit node and edge records: a Requirement node per requirement in the
specification, an Implementation node per marked function, an edge per
``:implements:`` marker. This tutorial produces the records and runs the
first of the three workflows, the consistency check.

Extract the records
-------------------

.. code-block:: console

   $ affirmatrix records extract
   requirements     59 nodes   48 refines     doc/requirement-specification/
   implementations   8 nodes   10 implements  src/affirmatrix/
   test-specs        9 nodes    9 verifies    doc/test-specification/
   test-outcomes     8 nodes   17 confirms+witnesses   build/reports/
   wrote 84 node records, 84 edge records → case/nodes/ case/edges/  (drafts)

Three things worth noticing before the next command:

- The records carry **hashes and references, never content**. A
  Requirement node holds the SHA-256 of its statement's bytes, not the
  statement; the statement stays in the specification document where it
  lives. The graph measures content, it does not store it.
- Every count was **derived, not declared**. There is no manifest listing
  what the graph should contain; the extractors found 59 requirements
  because the specification contains 59.
- The files under ``case/`` are **drafts**. Nothing has been committed to
  the case lineage; the graph's real state is its committed state, and
  you have committed nothing yet.

Check consistency
-----------------

.. code-block:: console

   $ affirmatrix case check
   vocabulary   84 nodes, 84 edges — every kind declared            ok
   identifiers  84 unique local identifiers                         ok
   refines      48 edges, acyclic                                   ok
   endpoints    84 edges, none dangling                             ok

   link states  84 pending
   consistent — nothing is affirmed yet, and the graph says so

``check`` answers one question: *can this record set be a graph at all?*
A kind the vocabulary does not declare, a duplicate identifier, a cycle in
the refines relation — each of these is refused loudly, because the
alternative is a graph that looks complete and is wrong. What ``check``
does **not** judge is readiness: 84 pending edges is a perfectly
consistent state. Pending is not a defect; it is the truthful description
of a graph nobody has affirmed.

What a refusal looks like
-------------------------

Suppose a requirement edit accidentally makes ``SEG-SREQ-006`` refine
``SEG-SREQ-005`` while ``SEG-SREQ-005`` already refines ``SEG-SREQ-006``:

.. code-block:: console

   $ affirmatrix case check
   error: the refines relation contains a cycle:
     SEG-SREQ-005 -> SEG-SREQ-006 -> SEG-SREQ-005
   no graph was built; fix one of the edges above
   $ echo $?
   2

The check stops the build rather than skipping the offending records — a
graph silently missing records would still look valid downstream, and
nothing there could tell. The error names the cycle because a cycle is
fixed by editing one of its edges, so the report must say which.

.. admonition:: Decisions this page forces

   - Is extraction one verb over all producers, or per-kind
     (``records extract requirements``)? What does a partial run mean?
   - The tabular output shape: is per-producer one-line summary right,
     and what does ``--verbose`` add?
   - Exit codes: ``0`` structurally consistent (even all-pending), ``2``
     refused? What, if anything, is ``1``?
   - Does ``check`` re-extract, or check the drafts already under
     ``case/``? (This page assumes the latter — extraction and checking
     are separate acts.)
   - Where does the record-producer seam surface in the CLI, so that the
     fixture-backed store loader and the real extractors are
     interchangeable inputs?

Next: :doc:`affirm-an-edge` turns pending into active — which the tool
cannot do for you.
