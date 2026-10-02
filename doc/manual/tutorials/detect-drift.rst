Detecting drift
===============

.. admonition:: Prerequisites

   - The affirmed, committed graph from :doc:`affirm-an-edge` — fourteen
     edges active, the other 265 pending.

An affirmation binds a judgement to content *as it stood*. The moment the
content moves, the judgement is stale — and the point of this tool is that
staleness is detected, not remembered. This tutorial moves some content
and watches the graph notice. It does so on copies, for a reason the page
gives before the first edit.

Where the graph stands
----------------------

Start from the state your last act left. ``graph status`` derives every
edge's state from the two streams it compares — what the case recorded,
what the producer supplies now (:need:`SEG-SREQ-080`) — and lists all of
them, one line per edge:

.. code-block:: console

   $ affirmatrix graph status | head -3
   affirmatrix.affirmation.affirmable --[Implements]--> SEG-SREQ-027 (pending)
   affirmatrix.affirmation.affirmable --[Implements]--> SEG-SREQ-056 (pending)
   affirmatrix.affirmation.compose --[Implements]--> SEG-SREQ-024 (pending)
   $ affirmatrix graph status | grep -c '(active)'
   14
   $ affirmatrix graph status | grep -c '(pending)'
   265
   $ affirmatrix graph status > /dev/null; echo $?
   0

The line shape is the one ``edge show`` prints: source, the kind between
``--[`` and ``]-->``, target, and the derived state in parentheses. That
is 279 lines and a last line of evidence counts, and this page never prints
them all; where it needs the interesting ones it filters, and says so. The graph you have affirmed is
clean in the only sense that matters here: no edge line is anything but
``active`` or ``pending``, and pending is not drift. An edge nobody has
affirmed has nothing to have drifted from, so it does not fail the verdict
(:need:`SEG-SREQ-082`). The exit code is the contract, and ``--json``
renders the same report as ``{"edges": [...]}``, one object per edge with
its ``from``, ``kind``, ``to`` and ``state``, for whatever reads it next.

Move some content, on a copy
----------------------------

Why a copy? The graph reads its current content from the producer, and
today that producer is the would-be store — a transcription of this
repository taken at one commit and *not kept in step with the source tree*
(its own ``README.md`` says so). Editing a function under ``src/`` now
moves nothing the graph hashes, because the graph reads the store, not the
tree. Until the extractors exist, drift is demonstrated by editing the
store's content. And the committed store under ``tests/fixtures/`` is not
yours to edit: other tests stand on it. So copy it, and name the copy with
``--current``, the option that says which producer supplies the current
stream:

.. code-block:: console

   $ cp -r tests/fixtures/would_be_store ./store-copy

Edit the body of ``affirmatrix.taxonomy.propagates`` in the copy — reword
the message of its error, behaviour untouched:

.. code-block:: console

   $ sed -i 's/is not a declared edge kind/is not an edge kind of this graph type/' store-copy/content/implementation/affirmatrix.taxonomy.propagates.body.txt
   $ diff tests/fixtures/would_be_store/content/implementation/affirmatrix.taxonomy.propagates.body.txt store-copy/content/implementation/affirmatrix.taxonomy.propagates.body.txt
   2c2
   <         raise ValueError(f"{edge_kind!r} is not a declared edge kind")
   ---
   >         raise ValueError(f"{edge_kind!r} is not an edge kind of this graph type")

One reworded string; the file's bytes are different, so its hash is.
Ask the graph — and to keep the answer short, drop the two states that
mean nothing has moved:

.. code-block:: console

   $ affirmatrix graph status --current ./store-copy | grep -v -e '(active)' -e '(pending)'
   affirmatrix.taxonomy.propagates --[Implements]--> SEG-SREQ-030 (directlyOutdated)
   SEG-SREQ-030 --[Refines]--> SEG-SYS-009 (transitivelySuspect)
   $ affirmatrix graph status --current ./store-copy > /dev/null; echo $?
   1
   $ affirmatrix graph status --current ./store-copy | grep -c '(active)'
   12

Two edges, out of fourteen once-active ones. The verdict is now negative:
exit 1 whenever any edge is ``directlyOutdated``, ``transitivelySuspect``,
``doublyOutdated`` or ``broken`` (:need:`SEG-SREQ-083`). The other twelve
are untouched and still active, and nothing was deleted or repaired.
Suspicion is precise, not panicked.

Read the two states apart, because they make different claims:

- **directlyOutdated** — recomputing the endpoint hashes no longer
  reproduces what the edge was affirmed against, and the edges it depends
  on are all active (:need:`SEG-SREQ-011`). The judgement pointed at bytes
  that are gone; someone must look again.
- **transitivelySuspect** — this edge's own endpoints are untouched, but
  it sits downstream of an edge that is not active, along a kind that
  propagates suspicion (:need:`SEG-SREQ-012`). Nobody claimed this edge is
  wrong; the graph refuses to let it stand as evidence while its
  foundation is in question.

``edge show`` says which is which, hash by hash. The directly outdated
edge:

.. code-block:: console

   $ affirmatrix edge show --current ./store-copy --kind Implements --from affirmatrix.taxonomy.propagates --to SEG-SREQ-030
   affirmatrix.taxonomy.propagates --[Implements]--> SEG-SREQ-030 (directlyOutdated) [needs re-affirmation]
     recorded in the case history as: <your name> <your e-mail>, committed <date>
       commit <id> "<your message>"
       signature: none
     from apiHash: f6bd…9ccc → f6bd…9ccc (matching)
     from bodyHash: dab9…6301 → fc00…cd4c (differing)
     to contentHash: 9068…2c04 → 9068…2c04 (matching)

Each named hash of each endpoint is compared with the digest the
affirming review event recorded (:need:`SEG-SREQ-128`): the signature,
``apiHash``, matches; the body, ``bodyHash``, differs; the requirement it
implements has not moved. That is the edit you made, named. And the
transitively suspect one:

.. code-block:: console

   $ affirmatrix edge show --current ./store-copy --kind Refines --from SEG-SREQ-030 --to SEG-SYS-009
   SEG-SREQ-030 --[Refines]--> SEG-SYS-009 (transitivelySuspect)
     recorded in the case history as: <your name> <your e-mail>, committed <date>
       commit <id> "<your message>"
       signature: none
     from contentHash: 9068…2c04 → 9068…2c04 (matching)
     to contentHash: 21c4…90a7 → 21c4…90a7 (matching)

Every hash matches, and the state is still suspect: the edge inherited
it. ``-v`` prints the digests in full, on ``edge show`` and on
``graph status`` alike.

Affirm the cause again
----------------------

If the edit was benign — an error message's wording does not change what
the function implements — the remedy is a fresh judgement over the new
bytes. But an affirmation is a write into the case's lineage, and this
demonstration must not bind scratch content into your case. So make the
copy of the case too, and leave behind the link that ties the real case
to its repository, so that nothing done in the copy can reach it:

.. code-block:: console

   $ cp -r case ./case-copy
   $ rm -f ./case-copy/.git

Everything that writes from here on names both copies. Affirm the one
edge that moved:

.. code-block:: console

   $ affirmatrix edge affirm --case ./case-copy --current ./store-copy --kind Implements --from affirmatrix.taxonomy.propagates --to SEG-SREQ-030 --role Maintainer --reason "Error message reworded; behaviour unchanged." --revision 678f72f5371cd69416adb9199ff0af54b706acdb
   affirmed: affirmatrix.taxonomy.propagates -> SEG-SREQ-030 (Implements)
   no extraction revision: store-copy/content: 2 node records
   $ echo $?
   0

The revision is required (:need:`SEG-SREQ-110`) because no repository
stands behind the store's anchors, and the one given is the same
``678f72f`` as on the previous page — a shortcut, and this page calls it
one. Nothing stands behind a scratch copy, so the tool records exactly
what it is given, neither discovering nor checking it
(:need:`SEG-SREQ-109`): the revision on this review event is true only
because you say it is. Over an anchor into a real repository the tool
would discover the revision itself (:need:`SEG-SREQ-107`) and refuse to
record it while the anchored content differs from what is committed
there (:need:`SEG-SREQ-108`), which is the check a copied store can never
have.

Now ask again, over the same two copies:

.. code-block:: console

   $ affirmatrix graph status --case ./case-copy --current ./store-copy | grep -v -e '(active)' -e '(pending)'
   $ affirmatrix graph status --case ./case-copy --current ./store-copy | grep -c '(active)'
   14
   $ affirmatrix graph status --case ./case-copy --current ./store-copy > /dev/null; echo $?
   0
   $ affirmatrix edge show --case ./case-copy --current ./store-copy --kind Refines --from SEG-SREQ-030 --to SEG-SYS-009
   SEG-SREQ-030 --[Refines]--> SEG-SYS-009 (active)
     recorded in the case history: not available
     from contentHash: 9068…2c04 → 9068…2c04 (matching)
     to contentHash: 21c4…90a7 → 21c4…90a7 (matching)

Fourteen active again, exit 0. You affirmed one edge, and the
transitively suspect edge cleared without being touched. Derived
suspicion is never stored, only computed on every run
(:need:`SEG-SREQ-034`); once its cause holds again, there is nothing left
to derive it from. You never affirm a transitively suspect edge; you cure
the cause, never the symptom.

Outdated on both counts
-----------------------

The third suspect state needs an edge that is itself stale *and* sits on
stale ground. Start over with fresh copies:

.. code-block:: console

   $ rm -rf store-copy case-copy
   $ cp -r tests/fixtures/would_be_store ./store-copy
   $ cp -r case ./case-copy
   $ rm -f ./case-copy/.git

Reword the statement of ``SEG-SREQ-029``, the requirement the node kinds
and edge kinds are implemented against:

.. code-block:: console

   $ sed -i 's/exactly the node kinds/precisely the node kinds/' store-copy/content/requirement/SEG-SREQ-029.txt
   $ affirmatrix graph status --case ./case-copy --current ./store-copy | grep -v -e '(active)' -e '(pending)'
   affirmatrix.taxonomy.node_kinds --[Implements]--> SEG-SREQ-029 (directlyOutdated)
   affirmatrix.taxonomy.edge_kinds --[Implements]--> SEG-SREQ-029 (directlyOutdated)
   SEG-TS-001 --[Verifies]--> SEG-SREQ-029 (directlyOutdated)
   SEG-SREQ-029 --[Refines]--> SEG-SYS-009 (doublyOutdated)
   $ affirmatrix graph status --case ./case-copy --current ./store-copy > /dev/null; echo $?
   1

Three edges point at the requirement that moved, and each is directly
outdated. The fourth is the requirement's own edge upward: its own content
moved, *and* the edges it depends on are no longer active, so it is
outdated on both counts (:need:`SEG-SREQ-013`). The states share the
listing and the line shape; the state in the parentheses is the only
difference. You cure it from the bottom: affirm the three edges
pointing at the requirement again, and the fourth loses its second count
and reads ``directlyOutdated``; affirm it again too and the listing is
clean.

Vanished edges
--------------

Content moving is one way a producer changes underneath a case. The other
is the producer no longer supplying an edge the case recorded. Start over
again, and delete from the copy of the store the pair
``SEG-TS-003 → SEG-SREQ-032`` — the test that verifies the content-hash
names — from its coverage manifest:

.. code-block:: console

   $ rm -rf store-copy case-copy
   $ cp -r tests/fixtures/would_be_store ./store-copy
   $ cp -r case ./case-copy
   $ rm -f ./case-copy/.git
   $ sed -i '/^    \["SEG-TS-003", "SEG-SREQ-032"\],$/d' store-copy/edges/coverage.toml

``case sync`` writes the derived stream into the case, and it reports what
it found:

.. code-block:: console

   $ affirmatrix case sync --case ./case-copy --current ./store-copy
   synced case-copy
   no extraction revision: store-copy/content: 228 node records
   vanished: SEG-TS-003 -> SEG-SREQ-032 (Verifies)
   $ echo $?
   0

A vanished edge is one the case holds and the current stream no longer
does. Sync reports it and leaves it where it is (:need:`SEG-SREQ-074`): a
sync that silently dropped what had been affirmed would be a way to lose a
judgement without anyone deciding to. ``graph status`` shows it too — as
a line with no state, because the current stream has said nothing that a
state could be derived from (:need:`SEG-SREQ-137`) — and keeps it out of
the verdict (:need:`SEG-SREQ-138`):

.. code-block:: console

   $ affirmatrix graph status --case ./case-copy --current ./store-copy | grep '^SEG-TS-003 --'
   SEG-TS-003 --[Verifies]--> SEG-SREQ-032  vanished from the current stream
   $ affirmatrix graph status --case ./case-copy --current ./store-copy | wc -l
   280
   $ affirmatrix graph status --case ./case-copy --current ./store-copy | grep -c '(active)'
   13
   $ affirmatrix graph status --case ./case-copy --current ./store-copy > /dev/null; echo $?
   0
   $ affirmatrix edge show --case ./case-copy --current ./store-copy --kind Verifies --from SEG-TS-003 --to SEG-SREQ-032
   the selector matched no edge
   $ echo $?
   2

The vanished edge is listed last, outside the parentheses that hold a
state: 280 lines: the 278 edges the current stream supplies, the one it does not,
and the last line of evidence counts. One active edge is fewer. Its listing does not turn the verdict,
which reads only the edges that have a state. ``edge show`` does not
select it, since it is no edge of the current stream. Removal is your
decision, and it is by name
(:need:`SEG-SREQ-075`), taking only what the selector names:

.. code-block:: console

   $ affirmatrix case remove --case ./case-copy --kind Verifies --from SEG-TS-003 --to SEG-SREQ-032
   removed: SEG-TS-003 -> SEG-SREQ-032 (Verifies)
   $ echo $?
   0
   $ affirmatrix case sync --case ./case-copy --current ./store-copy
   synced case-copy
   no extraction revision: store-copy/content: 228 node records

The edge's record is gone from the case and the next sync has nothing to
report. The review event that once affirmed it stays in the events file:
removing an edge does not rewrite what was judged.

What status will not catch
--------------------------

Drift detection recomputes hashes over the **content the producer
supplies**, and today that is the would-be store: a change to the source
tree that the store does not carry moves nothing that is hashed, and the
graph stays green while the code has changed. The same holds one level
further in, when the extractors exist: a change to an unmarked helper
that a marked function calls moves nothing that is hashed, and the
behaviour behind a marked surface has moved. A clean ``graph status``
therefore means *every hashed span still holds the content it was
affirmed against*, and exactly that. The boundary is stated in full in
:doc:`../explanation/architecture/guarantee-boundary`; the test suite,
ordinary engineering, covers the gap without closing it.

Next: :doc:`seal-and-prove` — turning a green graph into something you
can hand to someone who does not trust you.
