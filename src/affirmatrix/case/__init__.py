"""The affirmation store — persistence of the graph, both directions.

The only component that touches persisted graph artifacts: node and edge hash
records, review events, and sealed evidence packages under ``case/``
(SEG-SYS-007). It persists hashes and references only — the content those
hashes cover never reaches it (SEG-SREQ-018) — and it is the single point at
which schema validation is applied, rejecting an invalid record rather than
writing it (SEG-SREQ-019) and reproducing every record it wrote unchanged when
that record is read back (SEG-SREQ-020).

Its **read face is a record source** (ADR-0004): persisted edge records
carrying their stored edge hash and link state enter the engine through the
record-source protocol, so drift detection takes two record sources in and
gives one derived state out, and the graph builder never learns whether a hash
came from disk or from a producer. Its write face is exclusive.

Write policy (ADR-0008): writes land in place in the working ``case/`` by
default, each record appearing only once it is complete (SEG-SREQ-022), never
removing a record unless removal was requested (SEG-SREQ-023), never letting a
write strip an edge record of the hash it was affirmed against unless demotion
of that edge was requested (SEG-SREQ-051), and never outside the write root it
was given (SEG-SREQ-021). An output directory can relocate that root. The tool
performs no version-control operations of its own — the review surface is the
working tree, and a maintainer records it.

**The write face, as built.** One class over one write root. The root is always
a parameter and never a default, so relocating the whole store is passing a
different path and nothing else; the store never learns whether it is writing
the working case or a scratch copy. Records are written in batches because a
per-kind collection document is the unit of atomicity: one call rewrites one
document per kind it touches, whole, by rename. A rewrite carries through every
entry the call did not mention, so a short input stream cannot prune the case;
removal is a separate operation that names what it removes.

A case is self-describing. The store seeds a fresh root with the schemas and
the shared JSON-LD context it carries as package data, and thereafter validates
against the copy in the case rather than the copy in the package, so the tool
and an auditor reading the same directory reach the same verdict. It never
writes over a schema a case already has, except through
:meth:`AffirmationStore.refresh_schemas`, which a maintainer requests and then
commits as a store act.

**The read face, as built.** The same class presents the case back as a record
source: ``nodes()`` and ``edges()`` satisfy the protocol structurally and
supply the *recorded* stream, and ``review_events()`` — outside the protocol —
returns the recorded judgements in the order they were appended. Every call
re-reads the case, validates each entry against the case's own schemas, and
reconstructs records carrying case-local identifiers again — the minting of
ADR-0007 undone at the one boundary that performed it. Reading writes nothing.
Write creates, read refuses: a root that is not a self-describing case is
refused rather than answered with an empty stream, because an empty recorded
stream is a claim that nothing was ever affirmed; within a readable case, a
collection document that does not exist yet is simply a kind with no records.
An entry that cannot be read back as written — malformed, invalid against the
case's schemas, or failing reconstruction — raises rather than being skipped,
never a short stream.

**The proof document faces.** ``write_proof_document`` and
``read_proof_document`` are the same discipline over a different shape: one
whole document rather than a stream of entries, sealed under a snapshot
directory rather than a per-kind collection. The same asymmetry holds —
writing seeds the layout a fresh case needs, reading refuses a case that is
not self-describing — and the same refusal-over-skipping holds for a
document kind the case's own schemas do not declare, whichever side asks for
it. ``read_package`` reads all four of one snapshot's documents at once,
refusing the whole package if any one is missing or invalid, because a
package short one document is not a smaller package.

The module keeps the name ``case`` for one-word symmetry with the directory it
owns; module names denote the artifact, component names the actor.

Iteration-0 backlog items B10 (write), B11 (read-back), and B17 (the proof
document faces).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType

from affirmatrix.case import _atomic, _documents, _layout, _validation
from affirmatrix.case._errors import AffirmationStoreError, DemotionNotRequestedError
from affirmatrix.identity import edge_iri, node_iri
from affirmatrix.records import EdgeRecord, EdgeReference, NodeRecord, ReviewEvent

_PACKAGE_DATA = resources.files(__package__)


@dataclass(frozen=True, slots=True)
class AffirmationStore:
    """The affirmation store — both faces of persistence under one case root.

    Nothing is read or created when the store is constructed, deliberately
    unlike the would-be store's loader. A mistyped path there yields a silently
    empty record stream and so must be caught at once; here the ordinary case
    is a root that does not exist yet, and creating it is the job. Every write
    is self-sufficient: it brings the layout into being, seeds whatever
    self-describing files are missing, and only then looks at records.

    The read face is a record source, supplying the *recorded* stream
    (``records.SourceRole.RECORDED``): edge records re-enter carrying the state
    and hash they were last left with, and every identifier is case-local
    again. Reading is the one direction that refuses a missing case instead of
    creating it — an absent root read as empty would tell drift detection that
    nothing was ever affirmed, and a mistyped path deserves a message about a
    path, not an empty graph.
    """

    root: Path

    def initialize(self) -> None:
        """Bring an empty case into being without writing a record to it."""
        self._ensure_layout()

    def nodes(self) -> Iterator[NodeRecord]:
        """The node records the case holds, kind by kind, as they were written.

        :implements: SEG-SREQ-020
        """
        return self._node_records(self._readable())

    def edges(self) -> Iterator[EdgeRecord]:
        """The edge records the case holds, each with its stored state and hash.

        :implements: SEG-SREQ-020

        This is the recorded stream drift detection compares against a current
        one: what an edge was last affirmed with is a fact about the past, read
        from the record and never recomputed.
        """
        return self._edge_records(self._readable())

    def review_events(self) -> Iterator[ReviewEvent]:
        """The recorded judgements, in the order they were appended.

        :implements: SEG-SREQ-020

        Deliberately outside the record-source protocol, which carries nodes
        and edges only. Position is identity for a review event, so order is
        the one thing this stream must preserve — and the one thing a consumer
        needing the next ordinal has to count; the record type carries no
        ordinal field, because that would be a second spelling of position.
        """
        return self._review_event_records(self._readable())

    def latest_review_event(self, edge: EdgeReference) -> ReviewEvent | None:
        """The most recently appended review event naming this edge, if any.

        A read-face query over :meth:`review_events`, not a new stream: which
        event is "the affirming one" for an edge is a question about this
        store's own append order, so it is answered here rather than by a
        caller re-deriving it. ``None`` when the edge has never been
        affirmed — the same absence :meth:`edges` reports as a pending edge
        carrying no stored hash.
        """
        latest: ReviewEvent | None = None
        for event in self.review_events():
            if (event.kind, event.from_id, event.to_id) == (edge.kind, edge.from_id, edge.to_id):
                latest = event
        return latest

    def layout(self) -> frozenset[str]:
        """The directories this case's root already has, of the five it should.

        Report-only: unlike :meth:`initialize` and every write face, this
        never creates what is missing — a case's layout is exactly what
        ``case check`` needs to see, seeded or not.
        """
        return frozenset(
            name for name in _layout.DIRECTORIES if _layout.resolved_under(self.root, name).is_dir()
        )

    def missing_schemas(self) -> frozenset[str]:
        """Every schema this case's own ``schema/`` directory is missing.

        Named against the full declared set — every node, edge, review-event
        and proof-document schema the package itself carries — never seeded
        by asking; seeding is a write face's job, this one only looks.
        """
        declared = (
            frozenset(_layout.NODE_SCHEMAS.values())
            | frozenset(_layout.EDGE_SCHEMAS.values())
            | {_layout.EVENT_SCHEMA}
            | frozenset(_layout.PROOF_DOCUMENT_SCHEMAS.values())
        )
        directory = _layout.schema_directory(self.root)
        present = (
            frozenset(path.name for path in directory.glob("*.json"))
            if directory.is_dir()
            else frozenset()
        )
        return declared - present

    def _node_records(self, schemas: _validation.SchemaSet) -> Iterator[NodeRecord]:
        for kind in sorted(_layout.NODE_DOCUMENTS):
            document = _layout.node_document(self.root, kind)
            for entry in _documents.read_entries(document):
                _validation.validate_entry(
                    schemas,
                    entry,
                    _layout.node_schema(kind),
                    f"{document} holds {entry['id']}, which",
                )
                yield _documents.node_record(entry, kind, document)

    def _edge_records(self, schemas: _validation.SchemaSet) -> Iterator[EdgeRecord]:
        for kind in sorted(_layout.EDGE_DOCUMENTS):
            document = _layout.edge_document(self.root, kind)
            for entry in _documents.read_entries(document):
                _validation.validate_entry(
                    schemas,
                    entry,
                    _layout.edge_schema(kind),
                    f"{document} holds {entry['id']}, which",
                )
                yield _documents.edge_record(entry, kind, document)

    def _review_event_records(self, schemas: _validation.SchemaSet) -> Iterator[ReviewEvent]:
        document = _layout.events_document(self.root)
        for entry in _documents.read_entries(document):
            _validation.validate_entry(
                schemas, entry, _layout.EVENT_SCHEMA, f"{document} holds {entry['id']}, which"
            )
            yield _documents.review_event_record(entry, document)

    def write_nodes(self, records: Iterable[NodeRecord]) -> None:
        """Persist node records, one document rewritten per kind touched."""
        schemas = self._prepared()
        batch: dict[str, list[_documents.Entry]] = {}
        for record in records:
            entry = _documents.node_entry(record)
            _validation.validate_entry(
                schemas, entry, _layout.node_schema(record.kind), f"node {record.local_id!r}"
            )
            batch.setdefault(record.kind, []).append(entry)
        for kind, entries in batch.items():
            self._rewrite(_layout.node_document(self.root, kind), entries)

    def write_edges(
        self, records: Iterable[EdgeRecord], *, demote: Iterable[EdgeReference] = ()
    ) -> None:
        """Persist edge records, one document rewritten per kind touched.

        :implements: SEG-SREQ-051

        A record that would replace an incumbent carrying the hash it was
        affirmed against with one carrying none is a demotion, and a demotion
        happens only when ``demote`` names that edge. The stream itself is
        never the request — a current stream, every edge pending, must not be
        able to reset what the case says was affirmed — and naming is per
        edge, never a flag over the write. A name that licenses nothing is
        refused too: a request that silently did nothing would be
        indistinguishable from one that worked. Either disagreement refuses
        the whole batch before a byte lands, as validation already does.
        """
        schemas = self._prepared()
        batch: dict[str, list[tuple[EdgeRecord, _documents.Entry]]] = {}
        for record in records:
            entry = _documents.edge_entry(record)
            _validation.validate_entry(
                schemas,
                entry,
                _layout.edge_schema(record.kind),
                f"edge {record.from_id!r} -> {record.to_id!r}",
            )
            batch.setdefault(record.kind, []).append((record, entry))
        self._check_demotions(batch, frozenset(demote))
        for kind, pairs in batch.items():
            self._rewrite(
                _layout.edge_document(self.root, kind), [entry for _, entry in pairs]
            )

    def _check_demotions(
        self,
        batch: Mapping[str, list[tuple[EdgeRecord, _documents.Entry]]],
        requested: frozenset[EdgeReference],
    ) -> None:
        """Refuse a write whose demotions and demotion request disagree.

        Both directions are collected across the whole batch before either
        raises, so one refusal is one complete diagnosis — the shape removal
        and validation refusals already have.
        """
        demoted: set[EdgeReference] = set()
        unrequested: list[str] = []
        for kind, pairs in batch.items():
            document = _layout.edge_document(self.root, kind)
            incumbents = {entry["id"]: entry for entry in _documents.read_entries(document)}
            for record, entry in pairs:
                incumbent = incumbents.get(entry["id"])
                if incumbent is None or "seg:edgeHash" not in incumbent:
                    continue
                if "seg:edgeHash" in entry:
                    continue
                reference = EdgeReference(kind=kind, from_id=record.from_id, to_id=record.to_id)
                demoted.add(reference)
                if reference not in requested:
                    unrequested.append(_edge_label(reference))
        unused = sorted(_edge_label(reference) for reference in requested - demoted)
        problems = []
        if unrequested:
            problems.append(
                f"would strip the affirmed hash from {', '.join(sorted(unrequested))}, "
                "and demotion of those edges was not requested"
            )
        if unused:
            problems.append(f"does not demote {', '.join(unused)}, whose demotion was requested")
        if problems:
            raise DemotionNotRequestedError(f"this write {'; and it '.join(problems)}")

    def append_review_events(self, events: Iterable[ReviewEvent]) -> None:
        """Add review events to the case, after the ones already recorded.

        :implements: SEG-SREQ-033

        Append-only. An event already in the document is never rewritten and
        never re-numbered, so a recorded affirmation changes only when someone
        asks for the change — and the one operation that could quietly reword
        one does not exist.
        """
        schemas = self._prepared()
        document = _layout.events_document(self.root)
        existing = _documents.read_entries(document)
        recorded = {entry["id"] for entry in existing}
        entries: list[_documents.Entry] = []
        for ordinal, event in enumerate(events, start=len(existing) + 1):
            entry = _documents.event_entry(event, ordinal)
            if entry["id"] in recorded:
                raise AffirmationStoreError(
                    f"{document} already holds an event at position {ordinal}; its events are "
                    "not numbered as they were appended and appending would overwrite one"
                )
            _validation.validate_entry(
                schemas, entry, _layout.EVENT_SCHEMA, f"review event {entry['id']}"
            )
            entries.append(entry)
        if entries:
            self._rewrite(document, entries)

    def remove_nodes(self, kind: str, local_ids: Iterable[str]) -> None:
        """Remove the named node records, and only those.

        :implements: SEG-SREQ-023
        """
        self._ensure_layout()
        document = _layout.node_document(self.root, kind)
        self._remove(document, {node_iri(local_id): local_id for local_id in local_ids})

    def remove_edges(self, kind: str, endpoints: Iterable[tuple[str, str]]) -> None:
        """Remove the edge records between the named endpoint pairs, and only those.

        :implements: SEG-SREQ-023

        Endpoints, never an identifier: an identifier is an opaque key, so an
        interface that took one would be inviting the caller to build it by
        splitting another one apart (ADR-0007).
        """
        self._ensure_layout()
        document = _layout.edge_document(self.root, kind)
        self._remove(
            document,
            {
                edge_iri(kind, from_id, to_id): f"{from_id} -> {to_id}"
                for from_id, to_id in endpoints
            },
        )

    def write_proof_document(
        self, snapshot_id: str, document_name: str, document: Mapping[str, object]
    ) -> Path:
        """Write one document of the evidence package sealed under a snapshot.

        :implements: SEG-SREQ-019
        :implements: SEG-SREQ-021
        :implements: SEG-SREQ-022

        The mechanism only: it validates, confines the path, and writes
        atomically, exactly as every other write here does — but it does not
        decide what a document contains. It refuses every document kind with
        no schema registered for it, because a document with no schema cannot
        be shown to be valid and writing it anyway would put an unvalidated
        file in a case that claims all of them are.

        Returns the path written, which is the one thing a caller cannot derive
        for itself: the package directory is the store's to name.
        """
        schemas = self._prepared()
        path = _layout.proof_document(self.root, snapshot_id, document_name)
        try:
            schema_name = _layout.PROOF_DOCUMENT_SCHEMAS[document_name]
        except KeyError:
            raise AffirmationStoreError(
                f"no schema is registered for the proof document kind {document_name!r}"
            ) from None
        _validation.validate_entry(
            schemas, document, schema_name, f"proof document {document_name!r}"
        )
        _atomic.replace_file(path, _documents.serialized(document, _layout.PROOF_CONTEXT))
        return path

    def read_proof_document(self, snapshot_id: str, document_name: str) -> Mapping[str, object]:
        """Read one document of an evidence package back, as it was written.

        :implements: SEG-SREQ-020

        Validated against the case's own schemas, like every other read here
        (SEG-SREQ-053's discipline): a document that cannot be read as
        written, or a kind the case's own ``schema/`` directory declares no
        schema for, is refused rather than skipped. The second case is what a
        case initialized before its schema directory carried these four kinds
        hits if asked to read one before its next write has seeded them.
        """
        schemas = self._readable()
        path = _layout.proof_document(self.root, snapshot_id, document_name)
        try:
            schema_name = _layout.PROOF_DOCUMENT_SCHEMAS[document_name]
        except KeyError:
            raise AffirmationStoreError(
                f"no schema is registered for the proof document kind {document_name!r}"
            ) from None
        document = _documents.read_document(path)
        _validation.validate_entry(
            schemas, document, schema_name, f"proof document {document_name!r}"
        )
        return MappingProxyType(document)

    def read_package(self, snapshot_id: str) -> Mapping[str, Mapping[str, object]]:
        """Every document of one evidence package, keyed by document name.

        :implements: SEG-SREQ-020

        Reads all four of :data:`~affirmatrix.case._layout.PROOF_DOCUMENT_SCHEMAS`'
        kinds; missing or invalid in any one of them refuses the whole
        package rather than handing back the three that were fine — a
        package short one document is not a smaller package, it is not one.
        """
        return MappingProxyType(
            {
                document_name: self.read_proof_document(snapshot_id, document_name)
                for document_name in sorted(_layout.PROOF_DOCUMENT_SCHEMAS)
            }
        )

    def refresh_schemas(self) -> tuple[str, ...]:
        """Rewrite the case's schema copy from the packaged schemas, naming what differed.

        :implements: SEG-SREQ-139
        :implements: SEG-SREQ-140

        Every schema the package carries whose copy in the case differs in
        bytes, or is missing, is rewritten and its name returned, in file-name
        order; nothing else in the case is written — not a record, not the
        context, not a schema file the package does not carry. Bytes are what
        is compared, never parsed content: the copy an auditor reads is bytes,
        so a copy differing only in formatting counts as differing. A root
        that is not a directory is refused before anything is created, so a
        mistyped path cannot mint a case.
        """
        if not self.root.is_dir():
            raise AffirmationStoreError(
                f"{self.root} is not a case: there is no directory to refresh a schema copy in"
            )
        directory = _layout.schema_directory(self.root)
        refreshed = []
        for source in _packaged_schemas():
            payload = source.read_bytes()
            target = directory / source.name
            if not target.exists() or target.read_bytes() != payload:
                _atomic.replace_file(target, payload)
                refreshed.append(source.name)
        return tuple(refreshed)

    def _ensure_layout(self) -> None:
        """Create the case's directories and seed the files it is missing.

        Idempotent, and the first thing every operation does. A file that is
        already there is left exactly as it is — not compared, not refreshed —
        so writing to a case never touches anything the write was not about,
        and a maintainer reviewing the change sees only records.
        """
        for name in _layout.DIRECTORIES:
            _layout.resolved_under(self.root, name).mkdir(parents=True, exist_ok=True)
        _seed(_layout.context_file(self.root), _PACKAGE_DATA / _layout.CONTEXT_FILE)
        schema_directory = _layout.schema_directory(self.root)
        for source in _packaged_schemas():
            _seed(schema_directory / source.name, source)

    def _readable(self) -> _validation.SchemaSet:
        """The case as it stands and the schemas it is read by — or a refusal.

        The read counterpart of :meth:`_prepared`, with the asymmetry stated
        rather than smoothed: write creates, read refuses. Bringing a missing
        case into being is the write face's job; reading one as empty would
        give a mistyped path the same recorded stream as a case holding no
        affirmations, and nothing downstream could tell the two apart. Reading
        touches nothing — no directory is created, no file is seeded — because
        a read that changed the case would be a store act nobody asked for.

        The discriminator is the self-describing minimum every write creates:
        a case carries its context and its schemas, or it is not a case.
        """
        if not self.root.is_dir():
            raise AffirmationStoreError(
                f"{self.root} is not a readable case: there is no directory to read"
            )
        missing = [
            name
            for name, present in (
                (_layout.CONTEXT_FILE, _layout.context_file(self.root).is_file()),
                (_layout.SCHEMA_DIRECTORY, _layout.schema_directory(self.root).is_dir()),
            )
            if not present
        ]
        if missing:
            raise AffirmationStoreError(
                f"{self.root} is not a readable case: it is missing its self-describing "
                f"{' and '.join(missing)}; initialize() or any write creates them"
            )
        return _validation.load(_layout.schema_directory(self.root))

    def _prepared(self) -> _validation.SchemaSet:
        """The case, ready to be written to, and the schemas it is judged by.

        Removal does not go through here: it takes nothing that needs
        validating, and a case whose schemas have been damaged should still be
        one a maintainer can take a record out of.
        """
        self._ensure_layout()
        return _validation.load(_layout.schema_directory(self.root))

    def _rewrite(self, document: Path, entries: Iterable[_documents.Entry]) -> None:
        """Replace one collection document with itself plus these entries."""
        existing = _documents.read_entries(document)
        payload = _documents.collection(
            _documents.merged(existing, entries), _layout.COLLECTION_CONTEXT
        )
        _atomic.replace_file(document, payload)

    def _remove(self, document: Path, targets: Mapping[str, str]) -> None:
        """Drop the named entries from one collection document.

        A target that is not there raises. Answering "removed" for a record the
        case never held would make the two ways of being absent — retired, and
        never written — indistinguishable at exactly the moment somebody is
        relying on the difference.
        """
        existing = _documents.read_entries(document)
        present = {entry["id"] for entry in existing}
        missing = sorted(label for iri, label in targets.items() if iri not in present)
        if missing:
            raise AffirmationStoreError(
                f"{document} holds no record for {', '.join(repr(name) for name in missing)}, "
                "so there is nothing there to remove"
            )
        remaining = [entry for entry in existing if entry["id"] not in targets]
        _atomic.replace_file(
            document, _documents.collection(remaining, _layout.COLLECTION_CONTEXT)
        )


def _packaged_schemas() -> list[Traversable]:
    """The schema files the package carries, in file-name order."""
    directory = _PACKAGE_DATA / _layout.SCHEMA_DIRECTORY
    return sorted(directory.iterdir(), key=lambda source: source.name)


def _seed(target: Path, source: Traversable) -> None:
    """Give a case a self-describing file it does not have yet."""
    if not target.exists():
        _atomic.replace_file(target, source.read_bytes())


def _edge_label(reference: EdgeReference) -> str:
    """One edge, named for a refusal message."""
    return f"{reference.from_id!r} -> {reference.to_id!r} ({reference.kind})"


__all__ = ["AffirmationStore", "AffirmationStoreError", "DemotionNotRequestedError"]
