The affirmation store's read face
=================================

The write face's page describes how records land in a case; this one describes
how they come back. The same component serves both directions — the affirmation
store is the only writer under a case root and the only reader of what it wrote
— and the read face is where the guarantee that a record reads back as written
(:need:`SEG-SREQ-020`) lives.

A case presented as a record source
-----------------------------------

The store's read face is a record source: it satisfies the same protocol as
every producer, structurally, by having the two methods. It is not a
:class:`~affirmatrix.records.ContentSource`: the case holds hashes and never the
content behind them.

.. code-block:: python

   from pathlib import Path
   from affirmatrix.case import AffirmationStore

   store = AffirmationStore(root=Path("case"))
   nodes = list(store.nodes())
   edges = list(store.edges())
   events = list(store.review_events())

The stream it supplies is the *recorded* one: edge records re-enter the engine
carrying the link state and edge hash they were last left with, read from the
record and never recomputed, because what an edge was affirmed with is a fact
about the past. Comparing that stream against a *current* one — what a producer
derives from today's content — is the whole of drift detection, and the graph
builder never learns whether a hash came from disk or from a producer.

``review_events()`` sits deliberately outside the protocol, which carries nodes
and edges only. Review events are still records the store has written, so they
are still covered by read-back; they return in the order they were appended,
because position is a review event's identity and order is therefore the one
thing the stream must preserve. The record type carries no ordinal field — that
would be a second spelling of position.

Two read-face queries serve ``edge show``. ``latest_review_event(edge)`` gives the
last event of one edge. ``latest_review_event_identifiers()`` gives, for every
edge that has an event, the identifier that the events document holds for its
last event. The identifier is the text as written. It is not minted again from
the position of the event. A search of the history of the case needs the text
that the document holds. The method reads the document once and validates each
entry like every other read.
``review_events_path()`` gives the name of the events document under the case
root, in the form that a repository uses for a path. It reads nothing.

Every call re-reads the case and keeps nothing, so the stream reflects the case
as it stands now, and a case edited between two reads is seen as edited. Kinds
are read in sorted order and entries in their stored order, so two reads of an
unchanged case yield identical sequences.

Reading undoes minting
----------------------

Persisted entries carry absolute IRIs; records carry case-local identifiers —
the strings that enter hash preimages. Read-back is where minting is undone.

A node's local identifier is read from its own field, then verified by
re-minting: an entry whose ``id`` and ``seg:localId`` disagree carries two
identities and is refused, because reading back either one silently would let
the record move on its next rewrite.

An edge's endpoints are read from ``seg:from`` and ``seg:to`` — the record's
own fields, never parsed out of the edge's ``id``. Those values are node IRIs,
and a node IRI carries exactly one fully percent-encoded segment, so it has a
well-defined inverse. That inverse lives in the identity module, beside the
minting, because that module is the only place that knows the base: nothing
else could even strip the prefix. It is defined for the node IRI space and
nothing else — every other identifier stays an opaque key. The recovered
endpoints are then verified by re-minting the edge's identifier: a parse the
reader cannot reproduce is a parse it refuses to trust.

Validated on read-back
----------------------

The store is the single point at which schema validation is applied, in both
directions. Each entry is validated against the case's own schema copy — the
same files an auditor reads — before it is reconstructed, and the schemas are
read at the moment of the read, not cached. Reconstruction then re-establishes
the record types' own invariants: digests must be lowercase hex and are refused
rather than folded, a pending edge must not carry a hash, an active one must.

Write creates, read refuses
---------------------------

The two faces answer a missing case differently, and the asymmetry is the
point. For a write, a root that does not exist yet is the ordinary starting
state, and bringing it into being is the job. For a read it is not: an absent
root answered with an empty stream would tell drift detection that nothing was
ever affirmed, and a mistyped path would be indistinguishable from a case
holding no affirmations. So a read refuses a root that is not a
self-describing case — no directory, or missing its context and schemas — and
the refusal is a message about a path, delivered when the read is asked for.

Within a readable case, absence means what it should: a collection document
that does not exist yet is a kind nothing has produced, and contributes zero
records. An initialized, record-free case reads as empty streams — which is
what the first drift comparison of a fresh project sees, after the one
``initialize()`` call that makes the root a case.

Reading writes nothing. The read path creates no directory and seeds no file;
a case is byte-identical before and after any read, because a read that
changed the case would be a store act nobody asked for.

An unreadable case raises, never a short stream
-----------------------------------------------

Every failure to read a case as written is a refusal: a malformed document, a
document without its ``@graph`` of entries, an entry that fails validation, an
entry that fails reconstruction, a schema the case carries but that cannot be
read. Nothing is skipped and nothing is repaired, because a recorded record
that quietly went missing reads downstream as an affirmation that never
happened — the one outcome the recorded stream exists to rule out. A refusal
names the document and the entry, since the document is the reader's next
stop.
