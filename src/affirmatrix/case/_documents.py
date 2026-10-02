"""Records as JSON-LD entries, and the documents that collect them.

Two responsibilities, one file, because they are two halves of one rule: an
entry carries exactly the fields of the record it serializes — no more, because
a field that could carry covered content must not exist (SEG-SREQ-018), and no
less, because a field the store drops is a field read-back cannot reproduce.

Each entry builder has its inverse beside it, so the pair can be read as one
statement of what a record's persisted form is. An inverse only ever sees an
entry the store has already validated against the case's schemas, but it does
not lean on that: it re-establishes every record invariant itself and refuses
an entry it cannot turn back into the record that would have produced it —
never repairing, never skipping, because a recorded record that quietly went
missing reads downstream as an affirmation that never happened.

The envelope is the store's, not the record's. ``@context`` and ``@graph`` are
how a case describes itself; the schemas describe the entries inside.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from operator import itemgetter
from pathlib import Path

from affirmatrix import identity
from affirmatrix.case._errors import AffirmationStoreError
from affirmatrix.records import (
    ContentAnchor,
    EdgeRecord,
    LinkState,
    NodeRecord,
    ReviewEvent,
    TestResult,
    digest_from_hex,
    hex_digest,
)

Entry = dict[str, object]

_GRAPH = "@graph"
_CONTEXT = "@context"
_ID = "id"
_PREFIX = "seg:"
_RESULT = "seg:result"
_EXPIRY = "seg:expiry"
_APPROVER = "seg:approver"
_REVISION = "seg:revision"
_EXTRACTED_FROM = "seg:extractedFrom"
_NODE_FIXED_FIELDS = frozenset(
    {_ID, "type", "seg:localId", _RESULT, _EXPIRY, _APPROVER, _REVISION, _EXTRACTED_FROM}
)
_SOURCE_SUFFIX = "Source"
_SOURCE_MEMBERS = ("seg:sourceRepo", "seg:sourcePath", "seg:sourceLocator")


def _anchor_fields(anchors: Mapping[str, ContentAnchor]) -> Entry:
    """Every named content hash as its paired ``seg:{name}``/``seg:{name}Source`` fields.

    The pairing rule stated once, used everywhere a set of named content
    hashes is serialized: a node's own content, and the two endpoints a
    review event binds (SEG-SREQ-127).
    """
    fields: Entry = {}
    for name, anchor in sorted(anchors.items()):
        fields[f"seg:{name}"] = hex_digest(anchor.digest)
        fields[f"seg:{name}{_SOURCE_SUFFIX}"] = {
            "seg:sourceRepo": anchor.repository,
            "seg:sourcePath": anchor.path,
            "seg:sourceLocator": anchor.locator,
        }
    return fields


def node_entry(record: NodeRecord) -> Entry:
    """One node record as a JSON-LD entry.

    :implements: SEG-SREQ-018
    :implements: SEG-SREQ-050
    :implements: SEG-SREQ-304
    :implements: SEG-SREQ-326

    Every value is an identifier, a kind token, a digest, the source location
    of what a digest covers, a revision, or a test outcome's recorded result.
    The content itself has no field to travel in, which is the structural half
    of the guarantee; the schema's refusal of any undeclared property is the
    other. Each digest's location is written beside it under the digest's own
    name plus ``Source``, so the pairing is a spelling rule a reader can apply
    without a table.

    The extraction revisions are written as one object, from repository name
    to revision, with its keys in order. A record with no extraction revision
    gets no such field. An empty object is a second way to say the same thing,
    and the store does not write it.
    """
    entry: Entry = {
        _ID: identity.node_iri(record.local_id),
        "type": f"seg:{record.kind}",
        "seg:localId": record.local_id,
    }
    if record.result is not None:
        entry[_RESULT] = record.result.value
    if record.expiry is not None:
        entry[_EXPIRY] = record.expiry.isoformat()
    if record.approver is not None:
        entry[_APPROVER] = record.approver
    if record.revision is not None:
        entry[_REVISION] = record.revision
    if record.extracted_from:
        entry[_EXTRACTED_FROM] = dict(sorted(record.extracted_from.items()))
    entry.update(_anchor_fields(record.content_anchors))
    return entry


def node_record(entry: Entry, kind: str, document: Path) -> NodeRecord:
    """One persisted entry back as the node record it serializes.

    :implements: SEG-SREQ-020
    :implements: SEG-SREQ-055
    :implements: SEG-SREQ-057
    :implements: SEG-SREQ-058
    :implements: SEG-SREQ-062
    :implements: SEG-SREQ-305

    A test outcome's result is read back through the closed vocabulary, so a
    hand-edited spelling the vocabulary does not contain is refused here even
    before the schema is consulted — the recorded stream supplies a result in
    every test outcome record or refuses to be a stream at all. A waiver's
    expiry and approver are read back the same way, through the vocabulary's
    own construction: an expiry that is not an ISO 8601 calendar date, or a
    waiver missing either claim, is refused by :class:`~affirmatrix.records.NodeRecord`
    itself before the schema is consulted. A test outcome's revision is read
    back as the plain string it was written as — its spelling is deliberately
    unconstrained (SEG-SREQ-062) — but a test outcome missing it is refused
    the same way a test outcome missing its result is.

    The kind comes from the document being read, never from the entry: the
    schema has already pinned the entry's ``type`` to the document's kind, so
    reading it out again would be stating one fact twice. The identifier is
    read from ``seg:localId`` and then verified by re-minting: an entry whose
    ``id`` and local identifier disagree carries two identities, and reading
    back either one silently would let the record move on its next rewrite.

    Digests and source locations are paired by the ``Source`` spelling rule and
    the pairing is re-established here, not leaned on the schema: a digest
    without its location, or a location without its digest, is half a record,
    and half a record is refused rather than guessed at.
    """
    local_id = str(entry["seg:localId"])
    minted = identity.node_iri(local_id)
    if entry[_ID] != minted:
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, but its local identifier {local_id!r} mints "
            f"{minted}; two spellings of one identity must agree"
        )
    content_anchors = _read_named_anchors(
        entry, _NODE_FIXED_FIELDS, f"{document} holds {entry[_ID]}, whose"
    )
    result: TestResult | None = None
    if _RESULT in entry:
        try:
            result = TestResult(str(entry[_RESULT]))
        except ValueError as error:
            raise AffirmationStoreError(
                f"{document} holds {entry[_ID]}, whose {_RESULT} cannot be read back: {error}"
            ) from error
    expiry: date | None = None
    if _EXPIRY in entry:
        try:
            expiry = date.fromisoformat(str(entry[_EXPIRY]))
        except ValueError as error:
            raise AffirmationStoreError(
                f"{document} holds {entry[_ID]}, whose {_EXPIRY} cannot be read back: {error}"
            ) from error
    approver = str(entry[_APPROVER]) if _APPROVER in entry else None
    revision = str(entry[_REVISION]) if _REVISION in entry else None
    extracted_from = {
        str(repository): str(extracted)
        for repository, extracted in dict(entry.get(_EXTRACTED_FROM) or {}).items()
    }
    return _reconstructed(
        lambda: NodeRecord(
            local_id=local_id,
            kind=kind,
            result=result,
            expiry=expiry,
            approver=approver,
            revision=revision,
            content_anchors=content_anchors,
            extracted_from=extracted_from,
        ),
        entry,
        document,
    )


def edge_entry(record: EdgeRecord) -> Entry:
    """One edge record as a JSON-LD entry.

    :implements: SEG-SREQ-018

    The endpoints are written as their own fields rather than left to be read
    out of the entry's identifier. An identifier is an opaque key (ADR-0007),
    and a reader that split one would be relying on a separator that either
    part may itself contain.
    """
    entry: Entry = {
        _ID: identity.edge_iri(record.kind, record.from_id, record.to_id),
        "type": f"seg:{record.kind}",
        "seg:from": identity.node_iri(record.from_id),
        "seg:to": identity.node_iri(record.to_id),
        "seg:linkState": record.state.value,
    }
    if record.edge_hash is not None:
        entry["seg:edgeHash"] = hex_digest(record.edge_hash)
    return entry


def edge_record(entry: Entry, kind: str, document: Path) -> EdgeRecord:
    """One persisted entry back as the edge record it serializes.

    :implements: SEG-SREQ-020

    The endpoints are read from ``seg:from`` and ``seg:to`` — the record's own
    fields, exactly as ADR-0007 instructs — and those values are node IRIs, so
    each is undone by the one inverse that exists. The recovery is then
    verified by re-minting the edge's identifier from the recovered parts: a
    parse this module cannot reproduce is a parse it refuses to trust.

    The record type re-establishes its own invariants on construction, so an
    entry hand-edited into a pending edge that carries a hash, or an active one
    that lacks it, fails here even before the schema is consulted.
    """
    from_id = _read_endpoint(entry, "seg:from", document)
    to_id = _read_endpoint(entry, "seg:to", document)
    edge_hash = (
        _read_digest(entry, "seg:edgeHash", f"{document} holds {entry[_ID]}, whose")
        if "seg:edgeHash" in entry
        else None
    )
    minted = identity.edge_iri(kind, from_id, to_id)
    if entry[_ID] != minted:
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, but its endpoints mint {minted}; "
            "two spellings of one identity must agree"
        )
    return _reconstructed(
        lambda: EdgeRecord(
            from_id=from_id,
            to_id=to_id,
            kind=kind,
            state=LinkState(str(entry["seg:linkState"])),
            edge_hash=edge_hash,
        ),
        entry,
        document,
    )


def event_entry(event: ReviewEvent, ordinal: int) -> Entry:
    """One review event as a JSON-LD entry, at the position it was appended to.

    :implements: SEG-SREQ-018

    A review event carries nothing that identifies it — the same edge may be
    affirmed more than once — so its identity is where it sits in the case's
    sequence of events. That is available because events are only ever
    appended.

    The revisions inside ``seg:affirmedAt`` are named apart from the endpoint
    fields rather than repeating ``seg:from`` and ``seg:to`` inside a nested
    object. A term in the shared context is defined once for the whole
    document, and the endpoint term is defined as holding an identifier — so
    reusing the name here would tell a reader that a git revision is one, and
    it would be resolved as such against the context's base.

    Each endpoint's named content hashes travel under their own nested
    object, ``seg:fromContentAnchors``/``seg:toContentAnchors``
    (SEG-SREQ-127), paired the same ``Source``-suffix way a node's own
    entry pairs them — nested rather than flattened into the event's
    own fields, because the two endpoints' hash-name sets would
    otherwise share one flat namespace and a name common to both kinds
    could not tell them apart.
    """
    entry = {
        _ID: identity.review_event_iri(ordinal),
        "type": "seg:ReviewEvent",
        "seg:from": identity.node_iri(event.from_id),
        "seg:to": identity.node_iri(event.to_id),
        "seg:relation": f"seg:{event.kind}",
        "seg:fromContentAnchors": _anchor_fields(event.from_content_anchors),
        "seg:toContentAnchors": _anchor_fields(event.to_content_anchors),
        "seg:affirmedAt": {
            "seg:fromRevision": event.from_source_revision,
            "seg:toRevision": event.to_source_revision,
        },
        "seg:affirmingRole": event.role,
        "seg:reason": event.reason,
    }
    if event.from_node_hash is not None:
        entry["seg:fromNodeHash"] = hex_digest(event.from_node_hash)
    if event.to_node_hash is not None:
        entry["seg:toNodeHash"] = hex_digest(event.to_node_hash)
    return entry


def review_event_record(entry: Entry, document: Path) -> ReviewEvent:
    """One persisted entry back as the review event it serializes.

    :implements: SEG-SREQ-020

    The event's position is not read back into the record: identity-by-position
    is the events document's rule, and the record type deliberately has no
    field for it. The edge kind is recovered from ``seg:relation`` by the
    prefix-only mapping of ADR-0007 — one rule, no translation table.
    """
    relation = str(entry["seg:relation"])
    if not relation.startswith(_PREFIX):
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, whose relation {relation!r} is not in the "
            "case's vocabulary"
        )
    revisions = entry["seg:affirmedAt"]
    if not isinstance(revisions, Mapping):
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, whose seg:affirmedAt is not the pair of "
            "revisions the judgement was made at"
        )
    label = f"{document} holds {entry[_ID]}, whose"
    return _reconstructed(
        lambda: ReviewEvent(
            from_id=_read_endpoint(entry, "seg:from", document),
            to_id=_read_endpoint(entry, "seg:to", document),
            kind=relation.removeprefix(_PREFIX),
            from_node_hash=_read_optional_digest(entry, "seg:fromNodeHash", label),
            to_node_hash=_read_optional_digest(entry, "seg:toNodeHash", label),
            from_source_revision=str(revisions["seg:fromRevision"]),
            to_source_revision=str(revisions["seg:toRevision"]),
            from_content_anchors=_read_content_anchor_object(
                entry, "seg:fromContentAnchors", document
            ),
            to_content_anchors=_read_content_anchor_object(
                entry, "seg:toContentAnchors", document
            ),
            role=str(entry["seg:affirmingRole"]),
            reason=str(entry["seg:reason"]),
        ),
        entry,
        document,
    )


def _read_endpoint(entry: Entry, field: str, document: Path) -> str:
    """One endpoint field back as a case-local identifier."""
    try:
        return identity.node_local_id(str(entry[field]))
    except ValueError as error:
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, whose {field} cannot be read back: {error}"
        ) from error


def _read_source(container: Mapping[str, object], field: str, label: str) -> tuple[str, str, str]:
    """One source-location field back as its (repository, path, locator) triple.

    Exactly the three members, no more and no fewer: a member this module did
    not write is a member it cannot reproduce on the next rewrite, and a
    missing one is a location that cannot fetch. ``container`` is whatever
    object the field lives on — a node or edge entry, or one endpoint's
    nested content-anchor object — and ``label`` is the already-assembled
    context a caller wants every message about ``container`` to start with.
    """
    value = container[field]
    if not isinstance(value, Mapping) or set(value) != set(_SOURCE_MEMBERS):
        raise AffirmationStoreError(
            f"{label} {field} is not the source location of a content hash: it must carry "
            "exactly repository, path and locator"
        )
    repository, path, locator = (str(value[member]) for member in _SOURCE_MEMBERS)
    return repository, path, locator


def _read_digest(container: Mapping[str, object], field: str, label: str) -> bytes:
    """One digest field back as raw bytes; uppercase is refused, not folded."""
    try:
        return digest_from_hex(str(container[field]))
    except ValueError as error:
        raise AffirmationStoreError(f"{label} {field} cannot be read back: {error}") from error


def _read_optional_digest(
    container: Mapping[str, object], field: str, label: str
) -> bytes | None:
    """One digest field back as raw bytes, or ``None`` when the entry has none.

    Absent is a legitimate shape; present and malformed is still refused.
    """
    return _read_digest(container, field, label) if field in container else None


def _read_named_anchors(
    container: Mapping[str, object], excluded: frozenset[str], label: str
) -> dict[str, ContentAnchor]:
    """Every ``seg:{name}``/``seg:{name}Source`` pair in ``container`` as named anchors.

    The pairing rule stated once, used everywhere a serialized set of named
    content hashes is read back: a node entry's own fields, and one
    endpoint's nested content-anchor object on a review event
    (SEG-SREQ-127). ``excluded`` names fields that are not part of this set
    at all — a node entry's identity and its producer-recorded fields;
    empty for a review event's endpoint object, which carries nothing else.
    """
    digests: dict[str, bytes] = {}
    sources: dict[str, tuple[str, str, str]] = {}
    for name in container:
        if name in excluded:
            continue
        if not name.startswith(_PREFIX):
            raise AffirmationStoreError(f"{label} field {name!r} is not in the case's vocabulary")
        local = name.removeprefix(_PREFIX)
        if local.endswith(_SOURCE_SUFFIX):
            sources[local.removesuffix(_SOURCE_SUFFIX)] = _read_source(container, name, label)
        else:
            digests[local] = _read_digest(container, name, label)
    unpaired = sorted(set(digests) ^ set(sources))
    if unpaired:
        raise AffirmationStoreError(
            f"{label} content hashes and source locations do not pair up: "
            f"{', '.join(repr(name) for name in unpaired)}"
        )
    return {
        name: ContentAnchor(
            digest=digest,
            repository=sources[name][0],
            path=sources[name][1],
            locator=sources[name][2],
        )
        for name, digest in digests.items()
    }


def _read_content_anchor_object(
    entry: Entry, field: str, document: Path
) -> Mapping[str, ContentAnchor]:
    """One endpoint's nested content-anchor object back as named anchors.

    Reads back what SEG-SREQ-127 asks the affirmation recorder to record;
    this function discharges nothing of that requirement itself, since
    reading a record is not recording one. ``field`` is
    ``seg:fromContentAnchors`` or ``seg:toContentAnchors``; the
    pairing within it is the same rule :func:`_read_named_anchors` already
    applies to a node entry's own flat fields, applied here to the nested
    object instead of excluding nothing from it.
    """
    value = entry[field]
    if not isinstance(value, Mapping):
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, whose {field} is not the named content hashes "
            "an endpoint carried at judgement"
        )
    return _read_named_anchors(value, frozenset(), f"{document} holds {entry[_ID]}, whose {field}")


def _reconstructed[RecordT](build: Callable[[], RecordT], entry: Entry, document: Path) -> RecordT:
    """Run one record constructor, turning its refusal into the store's.

    The record types validate themselves on construction; what they raise is a
    producer-facing ``ValueError`` that does not know where the offending entry
    lives. Read-back knows, and the document is the reader's next stop.
    """
    try:
        return build()
    except ValueError as error:
        raise AffirmationStoreError(
            f"{document} holds {entry[_ID]}, which cannot be read back: {error}"
        ) from error


def merged(existing: Iterable[Entry], incoming: Iterable[Entry]) -> list[Entry]:
    """The document's entries after this write, keyed by identifier.

    :implements: SEG-SREQ-023

    An entry the call did not mention is carried through exactly as it was
    read. That is what makes a write of one record a write of one record: with
    the whole document as the unit of atomicity, anything not preserved here is
    silently deleted, and a producer that happened to yield a short stream
    would prune the case without saying so.

    Sorted by identifier, so the document is a function of what it holds rather
    than of the order a producer streamed it in, and two runs over an unchanged
    graph leave byte-identical files.
    """
    entries = {entry[_ID]: entry for entry in existing}
    entries.update({entry[_ID]: entry for entry in incoming})
    return sorted(entries.values(), key=itemgetter(_ID))


def read_entries(path: Path) -> list[Entry]:
    """The entries a document already holds, or none if it does not exist yet.

    A document that cannot be read as one raises rather than being replaced.
    Overwriting it would be precisely the silent removal that explicit deletion
    exists to rule out — and the records it holds may be the only place an
    affirmation survives.
    """
    if not path.exists():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AffirmationStoreError(
            f"{path} cannot be read as an instance document: {error}"
        ) from error
    entries = document.get(_GRAPH) if isinstance(document, Mapping) else None
    if not isinstance(entries, list):
        raise AffirmationStoreError(
            f"{path} is not an instance document: it declares no {_GRAPH!r} of entries"
        )
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get(_ID), str):
            raise AffirmationStoreError(
                f"{path} holds {entry!r}, which is not an entry with an identifier"
            )
    return entries


def read_document(path: Path) -> Entry:
    """One proof document's fields, without its ``@context`` envelope.

    :implements: SEG-SREQ-020

    Unlike :func:`read_entries`, a missing file is refused rather than
    answered with an empty reading: a collection document with nothing in it
    yet is a legitimate state a kind can be in, but there is no legitimate
    empty reading of *one* proof document — it either exists as written or it
    does not, and the difference matters to a caller asking for it by name.
    """
    if not path.exists():
        raise AffirmationStoreError(f"{path} does not hold a proof document")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AffirmationStoreError(f"{path} cannot be read as a document: {error}") from error
    if not isinstance(raw, dict) or _CONTEXT not in raw:
        raise AffirmationStoreError(
            f"{path} is not a proof document: it carries no {_CONTEXT!r}"
        )
    return {key: value for key, value in raw.items() if key != _CONTEXT}


def serialized(document: Mapping[str, object], context_reference: str) -> bytes:
    """One document's bytes: deterministic, sorted, newline-terminated.

    Indented and one field per line because the review surface for the whole
    store is somebody reading a diff of it, and a single-line document would
    show every change as the same change.
    """
    payload = {_CONTEXT: context_reference, **document}
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def collection(entries: Iterable[Entry], context_reference: str) -> bytes:
    """A per-kind collection document's bytes."""
    return serialized({_GRAPH: list(entries)}, context_reference)


__all__ = [
    "Entry",
    "collection",
    "edge_entry",
    "edge_record",
    "event_entry",
    "merged",
    "node_entry",
    "node_record",
    "read_document",
    "read_entries",
    "review_event_record",
    "serialized",
]
