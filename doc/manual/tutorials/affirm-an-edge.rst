Affirming an edge
=================

.. warning::

   **This tutorial does not work yet.** The commands shown here document
   the target workflow; the command-line interface is being designed at
   this surface before it is built.

.. admonition:: Prerequisites

   - The extracted, checked graph from :doc:`build-the-graph` — 84 records
     under ``case/``, all edges pending.

An affirmation is a content-bound human judgement: *I reviewed this edge,
between exactly these two pieces of content, and I stand behind it.* The
tool prepares every part of that sentence except the standing-behind. This
tutorial affirms one edge properly, then bootstraps the rest in bulk.

Review one edge
---------------

Pick the edge binding the graph builder to the cycle requirement:

.. code-block:: console

   $ affirmatrix edge show affirmatrix.graph.build Implements SEG-SREQ-004
   from    affirmatrix.graph.build       Implementation
           apiHash  41d0…9c2   bodyHash 7c9e…4b1
   to      SEG-SREQ-004                  Requirement
           contentHash  9d1f…07a
   kind    Implements    (strong: suspicion propagates here)
   state   pending — no affirmation on record

Everything you need for the review is one hop away: the requirement text
lives in the specification, the function lives in ``src/``, and the hashes
above pin the exact bytes of both. Read them side by side. If the function
really does what the requirement says, affirm it:

.. code-block:: console

   $ affirmatrix edge affirm affirmatrix.graph.build Implements SEG-SREQ-004 \
       --role maintainer \
       --comment "cycle refusal verified against the requirement and its tests"
   wrote case/events/2026-08-06-a41c.json   (ReviewEvent, draft)
   updated edge record: state active, edgeHash bound to both endpoints
   nothing is affirmed yet — the affirmation is your commit:

     git -C case add -A
     git -C case commit

The tool wrote a ReviewEvent naming the edge, both endpoints' content
hashes, your role, and your reasoning — and then stopped. Before the
commit, those bytes are a proposal. After it, they are an affirmation:
the commit supplies who, when, and that it was deliberate, checkable
against the authorised committer list. Nothing about the record changes;
its standing does.

.. code-block:: console

   $ git -C case add -A && git -C case commit \
       -m "affirm: graph builder implements SEG-SREQ-004"

The bootstrap sweep
-------------------

Affirming 84 edges one review at a time is the discipline for edges that
matter; a fresh graph also has a long tail. A bulk affirmation is one
authorised act covering many judgements, with the selecting query recorded
so the act says what it covered:

.. code-block:: console

   $ affirmatrix edge affirm --kind Implements --below SEG-SYS-009 \
       --role maintainer \
       --comment "bootstrap sweep: commitment-layer subtree reviewed together"
   4 edges selected, 4 ReviewEvents written (drafts)
   $ git -C case add -A && git -C case commit \
       -m "affirm: bootstrap sweep over the commitment-layer subtree"

One commit, four review events, one recorded query. Whether an edge is
important enough to forbid this shortcut is a policy question for the
maintainer, not a mechanism question for the tool — the mechanism only
guarantees that whichever you choose is recorded honestly.

What the tool will never do
---------------------------

There is no ``--commit`` flag, no batch mode that ends in an affirmation,
and no way to run any of the above headlessly to completion. The recorder
originates no affirmation of its own; a pipeline that affirmed on your
behalf would hollow out the one mechanism the whole graph rests on.

.. admonition:: Decisions this page forces

   - Edge addressing: the positional triple ``FROM KIND TO`` — right, or
     should edges carry short stable identifiers of their own?
   - Where does the role vocabulary come from, and is ``--role``
     mandatory?
   - The bulk selector language: ``--kind`` plus ``--below <node>``
     (scope by subtree)? What else may select — state, path, producer?
   - Should the tool draft the lineage commit message (it printed the
     commands above — one step short of preparing the commit)? That is
     the store design's stage 2, and it is deliberately unscheduled.
   - ``edge show`` content: should it render the actual requirement text
     and function source inline for the review, or only point at them?

Next: :doc:`detect-drift` — what all this bookkeeping buys you the day
the content moves.
