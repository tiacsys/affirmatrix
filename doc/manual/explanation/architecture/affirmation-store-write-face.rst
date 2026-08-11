The affirmation store's write face
==================================

The affirmation store is the only component that writes into a case. This page
describes the writing half of it — what a case looks like on disk, what one
write does, and which of its behaviours are guarantees rather than conveniences.
The reading half, which presents a case as a record source, has its own page:
:doc:`affirmation-store-read-face`.

One store, one root
-------------------

A store is constructed over a write root and owns everything below it:

.. code-block:: python

   from pathlib import Path
   from affirmatrix.case import AffirmationStore

   store = AffirmationStore(root=Path("case"))
   store.initialize()

The root is always a parameter and never a default. Relocating the whole store —
for a dry run, a comparison, or an inspection in continuous integration — is
passing a different path and nothing else, and the store never learns which of
the two it is writing. That is what keeps the write policy of ADR-0008 (writes
land in place; an output directory relocates the root) a decision made above
this component rather than inside it.

Nothing is read or created when the store is constructed. The ordinary case is a
root that does not exist yet, and bringing it into being is the job: every write
first creates the layout and seeds whatever self-describing files are missing.
``initialize()`` is that step on its own, for a case with no records in it yet.

What a case looks like
----------------------

.. code-block:: text

   case/
     context.jsonld
     schema/*.json
     nodes/{requirements,implementations,test_specifications,test_outcomes,waivers}.jsonld
     edges/{refines,verifies,implements,confirms,witnesses,excuses,calls}.jsonld
     events/review_events.jsonld
     proofs/{snapshotId}/*.jsonld

The mapping from a record kind to the document that holds it is written out
explicitly rather than derived from the kind's spelling, and the suite checks
its keys against the taxonomy. A derived rule would let a newly declared kind
acquire a home by accident; this way, giving it one is a deliberate edit.

Documents are created when something is written to them. A kind nothing produces
yet — a waiver, a call — has a name and a schema but no empty file.

A case describes itself
-----------------------

The package carries the schemas and the shared JSON-LD context as data, and a
fresh root is seeded with them. Thereafter the store validates against the copy
**in the case**, not the copy in the package, so the tool and someone auditing
the directory with ordinary tooling reach the same verdict by construction.

A file the case already has is never written over — not compared, not
refreshed. Replacing a case's schemas would be a store act, and the tool takes
none unbidden. It also means a write touches nothing the write was not about,
which matters because the review surface for the whole store is a maintainer
reading the diff.

Instance documents reference the context relatively (``../context.jsonld``), so
a case is readable offline and survives being moved as a whole.

One write, one document per kind
--------------------------------

The unit of atomicity is the whole collection document. A write is batch-shaped
for that reason — one call rewrites one document per kind it touches:

.. code-block:: python

   store.write_nodes(node_records)
   store.write_edges(edge_records)
   store.append_review_events(events)

A rewrite reads what the document already holds, replaces the entries this call
produced, keeps every other entry exactly as it was, sorts by identifier and
renames the result into place. Three properties follow, and each is load
bearing:

*Nothing disappears by omission* (SEG-SREQ-023). A producer that yields a short
stream — because a source was unreadable, or a filter was too narrow — rewrites
a smaller set of records, not a smaller case. Removal is a separate operation
that names what it removes, and refuses a record the case does not hold, because
"retired" and "never written" are different and somebody is relying on which.

*A document is a function of what it holds*, not of the order a producer
streamed it in. Two runs over an unchanged graph leave byte-identical files, so
a diff shows real change only.

*A record appears when its document does* (SEG-SREQ-022). The new contents are
written to a temporary file in the target's own directory, flushed to the
device, and renamed over the target. The directory matters: a rename is atomic
only within one filesystem, and a temporary file elsewhere would degrade it into
a copy and reintroduce the half-written document. On any failure the temporary
file is removed, so an interrupted run leaves neither a partial document nor a
stray file.

Affirmations are appended, never rewritten
------------------------------------------

Review events are added after the ones already recorded and are never
re-numbered (SEG-SREQ-033). A review event carries nothing that identifies it —
the same edge may be affirmed more than once — so its identity is its position
in the case's sequence of events, which is available precisely because events
are only ever appended.

An edge's state and the hash it was affirmed against change only when that edge
is named in a write. Writing a different edge, or any node document, leaves an
affirmed edge exactly as it was.

Validation, and what it is against
----------------------------------

Every entry is validated before any document is opened (SEG-SREQ-019) — the
whole batch, not record by record, so a batch containing one invalid record
writes nothing at all. A refusal names the record, the schema and the field,
because a batch is the usual size of a write and "something was invalid" is no
help.

The schemas are draft 2020-12, one per record kind. The node schemas pin the
content-hash field names each kind carries; the edge schemas compose from shared
definitions and state, as the record types do, that a pending edge has no hash
it was affirmed against and an active one must have. Stating the rule in both
places is deliberate: the record type guards the producer, the schema guards the
document somebody reads without our code.

Every schema forbids the properties it does not declare, and every digest field
is pinned to sixty-four lowercase hexadecimal characters. That is the structural
half of "covered content is never persisted" (SEG-SREQ-018): there is no field
for content to travel in, and no digest field it could be smuggled through. The
other half is the API, which takes record types and never text.

A case's schemas are read at the moment of the write rather than cached for the
process. They are data on disk that anything may have changed since the last
write, and a validator held over from an earlier one would be judging records
against rules the case no longer states.

Every path stays under the root
-------------------------------

Each path the store opens is assembled in one place and passes one check
(SEG-SREQ-021): segment rules that refuse an empty name, a parent reference, an
embedded separator, a null byte or a leading dot; then resolution of both the
candidate and the root, requiring the first to lie under the second. The
resolution is what catches the case no lexical rule can see, where a directory
along the path is a symbolic link out of the case.

The only caller-supplied path segment the store ever takes is the snapshot
identifier of an evidence package, which is why the rule is written for it.

Identifiers
-----------

Absolute IRIs are minted at serialization time and only there (ADR-0007). A node
is ``{base}/node/{localId}``; an edge is ``{base}/edge/{kind}/{from}/{to}``, with
every segment percent-encoded. There is no kind segment on a node identifier,
and there cannot be: an edge record carries its endpoints' identifiers and not
their kinds, and a broken edge's endpoint is by definition no longer in the graph
to be asked — yet such an edge must still be persistable.

Minted identifiers are opaque keys. An edge record writes its endpoints as
fields of their own, and nothing reads them back out of an identifier.

What is not here yet
--------------------

*The evidence package's document types.* The write path under
``proofs/{snapshotId}/`` is complete — validated, atomic, root-confined — but
the four document types and their schemas arrive with the generator that
computes them. Until then the store refuses every proof document kind, because
a document with no schema cannot be shown to be valid, and writing it anyway
would put an unvalidated file in a case that claims all of them are.

*Version control.* The tool runs no git (ADR-0008). It writes files; a
maintainer reviews the working tree and records it, and that commit is what
turns a proposed affirmation into an affirmed one (ADR-0009).
