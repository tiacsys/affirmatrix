Building the graph
==================

.. admonition:: Prerequisites

   - The repository installed and the case mounted (:doc:`installation`).

The graph does not exist until records do. In this repository, right now,
those records come from a stand-in: the **would-be store**, under
``tests/fixtures/``, a verbatim transcription of this repository taken at
one commit — its 139 requirements as the specification exported them, its
79 definitions carrying an ``:implements:`` field, and the ten-function
verification suite together with that suite's own run. It is read through
the same seam a real content extractor and outcome extractor will use
once they exist, so nothing about this page changes when they land — only
where the records come from.

Sync the records
----------------

There is no separate extraction command; ``case sync`` writes the derived
stream straight into the case (:need:`SEG-SREQ-072`):

.. code-block:: console

   $ affirmatrix case sync
   synced case
   $ echo $?
   0

.. code-block:: console

   $ ls case/nodes case/edges
   case/edges:
   confirms.jsonld
   implements.jsonld
   refines.jsonld
   verifies.jsonld
   witnesses.jsonld

   case/nodes:
   implementations.jsonld
   requirements.jsonld
   test_outcomes.jsonld
   test_specifications.jsonld

Three things worth noticing before the next command:

- The records carry **hashes and references, never content**. A
  Requirement node holds the SHA-256 of its statement's bytes, not the
  statement; the statement stays where it lives — today, the would-be
  store's own content files. The graph measures content, it does not
  store it.
- Every count is **derived, not declared**. There is no manifest listing
  what the graph should contain; the would-be store carries 139
  requirements because that is how many the specification's export held
  at the commit it was transcribed from.
- The files under ``case/`` are **drafts**. ``case sync`` wrote them, but
  the graph's real state is its committed state: the layout was committed
  on the previous page, and the records are drafts until the commit below.

Check the graph
---------------

.. code-block:: console

   $ affirmatrix graph check
   nodes by kind: Implementation 79, Requirement 139, TestOutcome 10, TestSpecification 10
   edges by kind: Confirms 10, Implements 141, Refines 128, Verifies 10, Witnesses 12
   pending: 301
   $ echo $?
   0

``graph check`` answers one question: *can this record set be a graph at
all?* It reports node and edge counts by kind and the count of pending
edges — never a count of dangling endpoints (:need:`SEG-SREQ-077`). A kind
the vocabulary does not declare, a duplicate identifier, a cycle in the
refines relation — each of these is refused loudly, because the
alternative is a graph that looks complete and is wrong. What
``graph check`` does **not** judge is readiness: 301 pending edges is a
perfectly consistent state. Pending is not a defect; it is the truthful
description of a graph nobody has affirmed.

The same report, structured rather than rendered for a person to read:

.. code-block:: console

   $ affirmatrix graph check --json
   {
     "edgesByKind": {
       "Confirms": 10,
       "Implements": 141,
       "Refines": 128,
       "Verifies": 10,
       "Witnesses": 12
     },
     "nodesByKind": {
       "Implementation": 79,
       "Requirement": 139,
       "TestOutcome": 10,
       "TestSpecification": 10
     },
     "pending": 301
   }

The exit code is the contract either way; ``--json`` only changes how the
same verdict is rendered.

Commit the records
------------------

Same shape as before — a store act, yours alone
(:doc:`../explanation/decisions/0009-store-as-repository`):

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

It sits after the check: commit a graph you have checked, so the store act
records a record set that builds.

What a refusal looks like
-------------------------

Take a copy of the would-be store and add one more ``Refines`` pair to the
copy's ``edges/refines.toml``: ``["SEG-SYS-001", "SEG-SREQ-001"]``, closing
a cycle against the ``["SEG-SREQ-001", "SEG-SYS-001"]`` pair already
there. Point ``graph check`` at the copy directly:

.. code-block:: console

   $ affirmatrix graph check --current ./would-be-store-with-a-cycle
   the refines relation contains a cycle: SEG-SREQ-001 -> SEG-SYS-001 -> SEG-SREQ-001
   $ echo $?
   1

The check refuses rather than building around the offending records — a
graph silently missing edges would still look valid downstream, and
nothing there could tell (:need:`SEG-SREQ-078`). Notice what is absent
from this output: no node count, no edge count, no pending count. A
refused check prints no count of anything (:need:`SEG-SREQ-079`) — the one
place its report is *narrower* than a success's rather than merely
present. The error names the cycle because a cycle is fixed by editing one
of its edges, so the report has to say which.

Next: :doc:`affirm-an-edge` turns pending into active — which the tool
cannot do for you.
