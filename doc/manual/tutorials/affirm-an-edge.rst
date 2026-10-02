Affirming an edge
=================

.. admonition:: Prerequisites

   - The synced, checked and committed graph from :doc:`build-the-graph` —
     279 edges under ``case/``, all pending.

An affirmation is a content-bound human judgement: *I reviewed this edge,
between exactly these two pieces of content, and I stand behind it.* The
tool prepares every part of that sentence except the standing-behind. This
tutorial reviews one subtree of the graph — the vocabulary the tool is
built on — and affirms it in a single act, with a reason that says what
was reviewed.

Choose a selection
------------------

Every edge command addresses edges through one grammar of narrowing
fields: ``--kind``, ``--from``, ``--to`` and ``--below <node>``, the
subtree of requirements refining a node. Each field restricts the set the
others admit (:need:`SEG-SREQ-100`); a kind together with both endpoints
names at most one edge (:need:`SEG-SREQ-101`), and the three are always
separate values, never one joined token (:need:`SEG-SREQ-102`). A selector
that matches nothing is a request the tool could not judge, exit 2
(:need:`SEG-SREQ-103`); so is an ``affirm`` with no selector at all
(:need:`SEG-SREQ-104`) — there is no "affirm everything" by omission.

Start small. The vocabulary — the node kinds, edge kinds, propagating
kinds and content-hash names of the graph type — hangs below
``SEG-SYS-009``. Look at what that selects:

.. code-block:: console

   $ affirmatrix edge show --below SEG-SYS-009
   affirmatrix.graph.build --[Implements]--> SEG-SREQ-031 (pending) [needs affirmation]
   affirmatrix.taxonomy.content_hash_names --[Implements]--> SEG-SREQ-032 (pending) [needs affirmation]
   affirmatrix.taxonomy.edge_kinds --[Implements]--> SEG-SREQ-029 (pending) [needs affirmation]
   affirmatrix.taxonomy.node_kinds --[Implements]--> SEG-SREQ-029 (pending) [needs affirmation]
   affirmatrix.taxonomy.propagates --[Implements]--> SEG-SREQ-030 (pending) [needs affirmation]
   affirmatrix.taxonomy.propagating_edge_kinds --[Implements]--> SEG-SREQ-030 (pending) [needs affirmation]
   SEG-SREQ-029 --[Refines]--> SEG-SYS-009 (pending) [needs affirmation]
   SEG-SREQ-030 --[Refines]--> SEG-SYS-009 (pending) [needs affirmation]
   SEG-SREQ-031 --[Refines]--> SEG-SYS-009 (pending) [needs affirmation]
   SEG-SREQ-032 --[Refines]--> SEG-SYS-009 (pending) [needs affirmation]
   SEG-TS-001 --[Verifies]--> SEG-SREQ-029 (pending) [needs affirmation]
   SEG-TS-002 --[Verifies]--> SEG-SREQ-030 (pending) [needs affirmation]
   SEG-TS-003 --[Verifies]--> SEG-SREQ-032 (pending) [needs affirmation]
   SEG-TS-009 --[Verifies]--> SEG-SREQ-031 (pending) [needs affirmation]
   $ echo $?
   0

Fourteen edges: four ``Refines`` (the vocabulary requirements
``SEG-SREQ-029`` to ``032`` under ``SEG-SYS-009``), six ``Implements``
(the taxonomy module and the graph builder against those requirements),
and four ``Verifies`` (the verification tests against them). Why this
subtree and not all 279? A fresh graph affirmed wholesale is a rubber
stamp — and most of the other edges bind code
that nothing verifies yet. Affirm what you have actually read.

Review before affirming
-----------------------

``edge show`` is where the review starts. Narrowed to one edge — kind and
both endpoints — it reports that edge's state:

.. code-block:: console

   $ affirmatrix edge show --kind Implements --from affirmatrix.taxonomy.node_kinds --to SEG-SREQ-029
   affirmatrix.taxonomy.node_kinds --[Implements]--> SEG-SREQ-029 (pending) [needs affirmation]

A pending edge has no earlier affirmation to compare against, so there is
no per-hash comparison to show yet; those lines appear once an edge has
been affirmed, as below (:need:`SEG-SREQ-085`). What you review is the
content itself; the hashes only pin its exact bytes. Today the
would-be store's content files stand in for the source, so you read them
there — the requirement statement and the marked definition:

.. code-block:: console

   $ cat tests/fixtures/would_be_store/content/requirement/SEG-SREQ-029.txt
   The taxonomy provider shall declare exactly the node kinds and edge kinds
   of the built-in safety-evidence graph type.
   $ cat tests/fixtures/would_be_store/content/implementation/affirmatrix.taxonomy.node_kinds.api.txt
   def node_kinds() -> frozenset[str]:
       """The node kinds of the built-in safety-evidence graph type.
       :implements: SEG-SREQ-029
       """
   $ cat tests/fixtures/would_be_store/content/implementation/affirmatrix.taxonomy.node_kinds.body.txt
       return frozenset(_CONTENT_HASH_NAMES)

Read them side by side. Does the function do what the requirement says?
Repeat for the rest of the fourteen; the four tests are reviewed the same
way, against the requirements they cover. The review is the part no tool
does for you.

The judgement's inputs
----------------------

An affirmation needs three values, and the tool supplies none of them
silently (:need:`SEG-SREQ-105`):

- ``--role`` — the capacity you affirm in — and ``--reason`` — why. Both
  are required and never defaulted (:need:`SEG-SREQ-106`); no role
  vocabulary is configured, so the role is your own word. An empty reason
  (``--reason ""``) is legal and deliberate: the tool insists that you
  say it, not that you say something.
- ``--revision`` — the source revision each endpoint's content is
  recorded at. Where an endpoint's anchor names a repository, the tool
  discovers the revision from it (:need:`SEG-SREQ-107`) and refuses to
  record it if the anchored content differs from what is committed there,
  naming the differing paths (:need:`SEG-SREQ-108`). A revision you give
  is recorded exactly as given, neither discovered nor checked
  (:need:`SEG-SREQ-109`). And where no repository stands behind an
  anchor, it is required (:need:`SEG-SREQ-110`).

The last case is every anchor of the would-be store, whose anchors carry
a plain directory path rather than a repository. Ask without one:

.. code-block:: console

   $ affirmatrix edge affirm --below SEG-SYS-009 --role Maintainer --reason "Reviewed the vocabulary requirements SEG-SREQ-029 to 032 against the taxonomy module, and the verification tests SEG-TS-001, 002, 003 and 009 against the requirements they cover; all fourteen edges below SEG-SYS-009 hold."
   affirmatrix.graph.build: no repository is configured for this endpoint's anchor; a revision must be given explicitly (--revision)
   $ echo $?
   2

Nothing was written. The revision to give is ``678f72f``, in full: the
commit the would-be store was transcribed at. That is the point at which the content the
graph holds hashes of was true, so it is the revision an affirmation over
it is honest to record. The repository's current head would be wrong —
it names content the store does not carry.

(The dirty-anchor refusal, :need:`SEG-SREQ-108`, is not something this
tutorial can show: nothing in the would-be store has a repository to be
dirty against. It is what an anchor into a real repository would do.)

Affirm
------

.. code-block:: console

   $ affirmatrix edge affirm --below SEG-SYS-009 --role Maintainer --reason "Reviewed the vocabulary requirements SEG-SREQ-029 to 032 against the taxonomy module, and the verification tests SEG-TS-001, 002, 003 and 009 against the requirements they cover; all fourteen edges below SEG-SYS-009 hold." --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   affirmed: affirmatrix.graph.build -> SEG-SREQ-031 (Implements)
   affirmed: affirmatrix.taxonomy.content_hash_names -> SEG-SREQ-032 (Implements)
   affirmed: affirmatrix.taxonomy.edge_kinds -> SEG-SREQ-029 (Implements)
   affirmed: affirmatrix.taxonomy.node_kinds -> SEG-SREQ-029 (Implements)
   affirmed: affirmatrix.taxonomy.propagates -> SEG-SREQ-030 (Implements)
   affirmed: affirmatrix.taxonomy.propagating_edge_kinds -> SEG-SREQ-030 (Implements)
   affirmed: SEG-SREQ-029 -> SEG-SYS-009 (Refines)
   affirmed: SEG-SREQ-030 -> SEG-SYS-009 (Refines)
   affirmed: SEG-SREQ-031 -> SEG-SYS-009 (Refines)
   affirmed: SEG-SREQ-032 -> SEG-SYS-009 (Refines)
   affirmed: SEG-TS-001 -> SEG-SREQ-029 (Verifies)
   affirmed: SEG-TS-002 -> SEG-SREQ-030 (Verifies)
   affirmed: SEG-TS-003 -> SEG-SREQ-032 (Verifies)
   affirmed: SEG-TS-009 -> SEG-SREQ-031 (Verifies)
   no extraction revision: tests/fixtures/would_be_store/content: 15 node records
   $ echo $?
   0

One act, fourteen judgements, one reason. That is legitimate because the
reason says what the act covers; the selector, ``--below SEG-SYS-009``, is
the recorded query. For each affirmable edge the tool wrote a review
event, the affirmed edge record, and both endpoints' current node records
(:need:`SEG-SREQ-086`) — new files under ``case/``, still drafts:

.. code-block:: console

   $ ls case/events
   review_events.jsonld

A review event is one entry of that file, and the shape is the point: your
role and reason, the relation, both endpoints, every named content hash of
each together with its anchor, and the revision for each endpoint. Abridged,
the first of the fourteen reads:

.. code-block:: json

   {
     "id": "https://affirmatrix.dev/case/event/000001",
     "type": "seg:ReviewEvent",
     "seg:affirmingRole": "Maintainer",
     "seg:reason": "Reviewed the vocabulary requirements SEG-SREQ-029 to 032 …",
     "seg:relation": "seg:Implements",
     "seg:affirmedAt": {
       "seg:fromRevision": "678f72f5371cd69416adb9199ff0af54b706acdb",
       "seg:toRevision": "678f72f5371cd69416adb9199ff0af54b706acdb"
     },
     "seg:from": "https://affirmatrix.dev/case/node/affirmatrix.graph.build",
     "seg:fromNodeHash": "ef759197…7b6d2",
     "seg:fromContentAnchors": {
       "seg:apiHash": "fe64271f…73ebd",
       "seg:apiHashSource": {
         "seg:sourceLocator": "file",
         "seg:sourcePath": "implementation/affirmatrix.graph.build.api.txt",
         "seg:sourceRepo": "…/would_be_store/content"
       },
       "seg:bodyHash": "a6767470…8d61e",
       "seg:bodyHashSource": { "…": "the same three fields, for the body" }
     },
     "seg:to": "https://affirmatrix.dev/case/node/SEG-SREQ-031",
     "seg:toNodeHash": "e40f55dd…329bb",
     "seg:toContentAnchors": {
       "seg:contentHash": "d3751f3d…f38e6b",
       "seg:contentHashSource": { "…": "the same three fields, for the statement" }
     }
   }

An event recorded after the composite node hash was dropped from the event
omits the two ``NodeHash`` lines: the edge record's ``seg:edgeHash`` still
folds those hashes, and the named hashes above are what the event binds.

Nothing in it is content; everything in it is a hash or a reference. The
statement you read is not stored — only the SHA-256 of its bytes, and a
pointer to where those bytes live.

Now ask about one edge again:

.. code-block:: console

   $ affirmatrix edge show --kind Implements --from affirmatrix.taxonomy.node_kinds --to SEG-SREQ-029
   affirmatrix.taxonomy.node_kinds --[Implements]--> SEG-SREQ-029 (active)
     recorded in the case history: not committed
     from apiHash: fd33…a6e7 → fd33…a6e7 (matching)
     from bodyHash: edca…ab58 → edca…ab58 (matching)
     to contentHash: 82f6…7b65 → 82f6…7b65 (matching)

The second line says that no commit of the case holds the review event yet.
After the commit below, it names that commit, its committer and its date.
Active, and each named hash of each endpoint shown recorded → current,
matching. The digests are abbreviated; ``edge show -v`` prints them in
full. The next tutorial is about the day one of those pairs stops
matching.

The commit is the affirmation
-----------------------------

The tool has written drafts and stopped. Nothing is affirmed yet: the
graph's state is its committed state, and ``case/`` holds files no commit
has yet named. Affirming is the commit, made by you, in the case's own
lineage (:doc:`../explanation/decisions/0009-store-as-repository`):

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

Before the commit, those bytes are a proposal. After it, they are an
affirmation: the commit supplies who, when, and that it was deliberate,
checkable against the authorised committer list. The message is yours; the
tool neither drafts nor runs it. The commit carries the fourteen
affirmations — the review events, the affirmed edge records and the
endpoints' current node records — the synced records having been
committed on the previous page.

Check where the graph stands:

.. code-block:: console

   $ affirmatrix graph status | head -3
   affirmatrix.affirmation.affirmable --[Implements]--> SEG-SREQ-027 (pending)
   affirmatrix.affirmation.affirmable --[Implements]--> SEG-SREQ-056 (pending)
   affirmatrix.affirmation.compose --[Implements]--> SEG-SREQ-024 (pending)
   $ affirmatrix graph status | grep -c '(active)'
   14
   $ affirmatrix graph status | tail -1
   evidence: 0 at the current revision, 0 at another revision, 0 dangling

``graph status`` lists every strong edge with the state derived from the
recorded and the current stream — 279 lines, of which the head is quoted
here; fourteen are active, the other 265 remain pending. Pending edges do not
fail the verdict, so it exits 0 (:need:`SEG-SREQ-082`). The last line is not
an edge. It reports the test evidence apart from the edges, with its counts
(:need:`SEG-SREQ-210`); no run bundle is named here (a bundle is named with ``--bundle``),
so all three are zero.

What is not affirmable
----------------------

Ask again over the same selection, and everything in it is already
active:

.. code-block:: console

   $ affirmatrix edge affirm --below SEG-SYS-009 --role Maintainer --reason "again" --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   not affirmed: affirmatrix.graph.build -> SEG-SREQ-031 (Implements) (it is active — nothing to affirm)
   not affirmed: affirmatrix.taxonomy.content_hash_names -> SEG-SREQ-032 (Implements) (it is active — nothing to affirm)
   not affirmed: affirmatrix.taxonomy.edge_kinds -> SEG-SREQ-029 (Implements) (it is active — nothing to affirm)
   not affirmed: affirmatrix.taxonomy.node_kinds -> SEG-SREQ-029 (Implements) (it is active — nothing to affirm)
   not affirmed: affirmatrix.taxonomy.propagates -> SEG-SREQ-030 (Implements) (it is active — nothing to affirm)
   not affirmed: affirmatrix.taxonomy.propagating_edge_kinds -> SEG-SREQ-030 (Implements) (it is active — nothing to affirm)
   not affirmed: SEG-SREQ-029 -> SEG-SYS-009 (Refines) (it is active — nothing to affirm)
   not affirmed: SEG-SREQ-030 -> SEG-SYS-009 (Refines) (it is active — nothing to affirm)
   not affirmed: SEG-SREQ-031 -> SEG-SYS-009 (Refines) (it is active — nothing to affirm)
   not affirmed: SEG-SREQ-032 -> SEG-SYS-009 (Refines) (it is active — nothing to affirm)
   not affirmed: SEG-TS-001 -> SEG-SREQ-029 (Verifies) (it is active — nothing to affirm)
   not affirmed: SEG-TS-002 -> SEG-SREQ-030 (Verifies) (it is active — nothing to affirm)
   not affirmed: SEG-TS-003 -> SEG-SREQ-032 (Verifies) (it is active — nothing to affirm)
   not affirmed: SEG-TS-009 -> SEG-SREQ-031 (Verifies) (it is active — nothing to affirm)
   $ echo $?
   1

A selection with no affirmable member lists every edge with its reason and
exits 1 (:need:`SEG-SREQ-088`). Had one member been affirmable, the tool
would have affirmed it, listed the others with their reasons the same way,
and exited 0 (:need:`SEG-SREQ-087`).

The other class is the evidence edges, ``Confirms`` and ``Witnesses``. The
case stores none of them: test evidence is built from run bundles when a
verdict is made, never kept (:need:`SEG-SREQ-227`). So there is nothing to
select:

.. code-block:: console

   $ affirmatrix edge affirm --kind Confirms --from run-0001/SEG-TS-001 --role Maintainer --reason "x" --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   the selector matched no edge
   $ echo $?
   2

An evidence edge records that a run observed something; it is settled by
running the test again, not by anyone's judgement, so no reason of yours
could make it active. A ``broken`` edge — one with an endpoint that is gone
— needs the endpoint fixed, not an affirmation.

Bulk, or one at a time
----------------------

What you did here — one selector, one reason, fourteen judgements — is
one authorised act covering many. Whether an edge is important enough to
deserve an act of its own is a policy question for the operator, not a
mechanism question for the tool: the six ``Implements`` edges could each
have been affirmed by kind and both endpoints, each with its own reason,
and the tool records whichever you choose honestly. The only thing it
asks is that the reason be true of what the act covers.

What the tool will never do
---------------------------

There is no flag that commits for you, and no way to run any of the above
headlessly to completion. The recorder originates no affirmation of its
own (:doc:`../explanation/architecture/affirmation-recorder`); a pipeline
that affirmed on your behalf would hollow out the one mechanism the whole
graph rests on.

Next: :doc:`detect-drift` — what all this bookkeeping buys you the day
the content moves.
