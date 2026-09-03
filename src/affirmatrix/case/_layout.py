"""The layout the affirmation store owns, and the confinement rule over it.

ADR-0008 makes the store the only writer under the write root and gives it the
directory names, the file naming and the mapping from a record kind to the
document that holds it. All of that lives here, so a path is assembled in one
place and every path the store opens passes through one check.

The kind-to-document mappings are written out rather than derived from the kind
spelling. A derived rule would let a new kind acquire a home by accident; an
explicit map makes giving it one a deliberate edit, and the suite checks the
map's keys against the taxonomy so the two cannot drift apart.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from affirmatrix.case._errors import AffirmationStoreError

#: The self-describing files a case carries beside its records.
CONTEXT_FILE = "context.jsonld"
SCHEMA_DIRECTORY = "schema"

NODES_DIRECTORY = "nodes"
EDGES_DIRECTORY = "edges"
EVENTS_DIRECTORY = "events"
PROOFS_DIRECTORY = "proofs"

#: Every directory a case has, whether or not anything has been written to it.
DIRECTORIES = (
    SCHEMA_DIRECTORY,
    NODES_DIRECTORY,
    EDGES_DIRECTORY,
    EVENTS_DIRECTORY,
    PROOFS_DIRECTORY,
)

DOCUMENT_SUFFIX = ".jsonld"
EVENTS_DOCUMENT = "review_events"

#: An instance document references the shared context relatively, so a case
#: describes itself with no network and survives being moved as a whole.
COLLECTION_CONTEXT = f"../{CONTEXT_FILE}"
PROOF_CONTEXT = f"../../{CONTEXT_FILE}"

#: Node kind -> the document that holds every node of that kind.
NODE_DOCUMENTS: MappingProxyType[str, str] = MappingProxyType(
    {
        "Requirement": "requirements",
        "Implementation": "implementations",
        "TestSpecification": "test_specifications",
        "TestOutcome": "test_outcomes",
        "Waiver": "waivers",
    }
)

#: Edge kind -> the document that holds every edge of that kind.
EDGE_DOCUMENTS: MappingProxyType[str, str] = MappingProxyType(
    {
        "Refines": "refines",
        "Verifies": "verifies",
        "Implements": "implements",
        "Confirms": "confirms",
        "Witnesses": "witnesses",
        "Excuses": "excuses",
        "Calls": "calls",
    }
)

#: Node kind -> the schema one of its entries validates against.
NODE_SCHEMAS: MappingProxyType[str, str] = MappingProxyType(
    {
        "Requirement": "requirement.schema.json",
        "Implementation": "implementation.schema.json",
        "TestSpecification": "test_specification.schema.json",
        "TestOutcome": "test_outcome.schema.json",
        "Waiver": "waiver.schema.json",
    }
)

#: Edge kind -> the schema one of its entries validates against.
EDGE_SCHEMAS: MappingProxyType[str, str] = MappingProxyType(
    {kind: f"edge-{stem}.schema.json" for kind, stem in EDGE_DOCUMENTS.items()}
)

EVENT_SCHEMA = "review_event.schema.json"

#: Proof document kind -> its schema. The evidence package's four document
#: types, seeded into a fresh case exactly like the record schemas. A case
#: initialized before this mapping held these kinds has none of them under its
#: own ``schema/`` until its next write, which seeds whatever it is missing;
#: reading one of these kinds from such a case before that refuses through
#: the same "no schema declared for this kind" path the write side already
#: used while this mapping was empty.
PROOF_DOCUMENT_SCHEMAS: MappingProxyType[str, str] = MappingProxyType(
    {
        "design_consistency_proof": "design_consistency_proof.schema.json",
        "execution_coverage_record": "execution_coverage_record.schema.json",
        "coverage_report": "coverage_report.schema.json",
        "evidence_manifest": "evidence_manifest.schema.json",
    }
)

#: The separators a single path segment may not contain. The forward slash is
#: listed whatever the platform, and so is the backslash: a case is written on
#: one machine and read on another, so a name that is one segment here must be
#: one segment there too.
_SEPARATORS = frozenset({"/", "\\", os.sep} | ({os.altsep} if os.altsep else set()))

#: Characters invalid in a file name on Windows though legal on POSIX. Control
#: characters are refused with them (see :func:`resolved_under`).
_WINDOWS_INVALID = frozenset('<>:"|?*')


def resolved_under(root: Path, *parts: str) -> Path:
    """A path built from ``parts`` and proven to lie under ``root``.

    :implements: SEG-SREQ-021

    Two checks, because either alone is escapable. The segment rules stop the
    obvious constructions — a parent reference, an absolute path, a separator
    smuggled into what should be one name — and the resolution catches the case
    no lexical rule can see, where a directory in the path is a symlink out of
    the root.

    A character invalid in a file name on Windows is refused on every platform,
    control characters with it. A published case must be checkable out on
    either filesystem; the proof generator's minting rule (SEG-SREQ-052) is the
    primary guard, and this is the store's defense in depth at its one path
    choke point, so no caller-supplied name can put an uncheckoutable file in a
    case. Windows's reserved device names and trailing dots or spaces remain
    the minting rule's concern — this rule is about characters only.

    A leading dot is refused as well. It is not an escape, but it would let a
    caller-supplied name hide a document from an ordinary listing of the case,
    and the review surface for the whole store is somebody reading that listing.
    """
    for part in parts:
        if not part or part in {os.curdir, os.pardir}:
            raise AffirmationStoreError(
                f"{part!r} is not a name a path under the write root can be built from"
            )
        if any(separator in part for separator in _SEPARATORS):
            raise AffirmationStoreError(
                f"{part!r} contains a path separator, so it names more than one place"
            )
        if any(character in _WINDOWS_INVALID or ord(character) < 0x20 for character in part):
            raise AffirmationStoreError(
                f"{part!r} contains a character that is not valid in a file name on every "
                "filesystem a case must be checkable out on"
            )
        if part.startswith("."):
            raise AffirmationStoreError(f"{part!r} starts with a dot, which would hide it")
    base = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(base):
        raise AffirmationStoreError(
            f"{candidate} resolves outside the write root {base}, and every write stays under it"
        )
    return candidate


def node_document(root: Path, kind: str) -> Path:
    """The document that holds the node records of one kind."""
    stem = _declared(NODE_DOCUMENTS, kind, "node")
    return resolved_under(root, NODES_DIRECTORY, f"{stem}{DOCUMENT_SUFFIX}")


def edge_document(root: Path, kind: str) -> Path:
    """The document that holds the edge records of one kind."""
    stem = _declared(EDGE_DOCUMENTS, kind, "edge")
    return resolved_under(root, EDGES_DIRECTORY, f"{stem}{DOCUMENT_SUFFIX}")


def events_document(root: Path) -> Path:
    """The document that holds the case's review events."""
    return resolved_under(root, EVENTS_DIRECTORY, f"{EVENTS_DOCUMENT}{DOCUMENT_SUFFIX}")


def proof_document(root: Path, snapshot_id: str, document_name: str) -> Path:
    """One document of the evidence package sealed under a snapshot.

    The snapshot identifier is the only caller-supplied path segment the store
    ever takes, which is why it is the one the confinement rule is written for.
    """
    return resolved_under(
        root, PROOFS_DIRECTORY, snapshot_id, f"{document_name}{DOCUMENT_SUFFIX}"
    )


def schema_directory(root: Path) -> Path:
    """The case's own copy of the schemas — the copy an auditor verifies with."""
    return resolved_under(root, SCHEMA_DIRECTORY)


def context_file(root: Path) -> Path:
    """The case's own copy of the shared JSON-LD context."""
    return resolved_under(root, CONTEXT_FILE)


def node_schema(kind: str) -> str:
    """The schema a node record of this kind validates against."""
    return _declared(NODE_SCHEMAS, kind, "node")


def edge_schema(kind: str) -> str:
    """The schema an edge record of this kind validates against."""
    return _declared(EDGE_SCHEMAS, kind, "edge")


def _declared(mapping: Mapping[str, str], kind: str, what: str) -> str:
    """One kind's entry in a layout map, or a refusal naming the kind.

    The maps above are the store's copy of the vocabulary, so a kind missing
    from one is a kind the store has nowhere to put — which is a refusal, not a
    default location.
    """
    try:
        return mapping[kind]
    except KeyError:
        raise AffirmationStoreError(f"{kind!r} is not a declared {what} kind") from None


__all__ = [
    "COLLECTION_CONTEXT",
    "CONTEXT_FILE",
    "DIRECTORIES",
    "EDGE_DOCUMENTS",
    "EDGE_SCHEMAS",
    "EVENTS_DOCUMENT",
    "EVENT_SCHEMA",
    "NODE_DOCUMENTS",
    "NODE_SCHEMAS",
    "PROOF_CONTEXT",
    "PROOF_DOCUMENT_SCHEMAS",
    "SCHEMA_DIRECTORY",
    "context_file",
    "edge_document",
    "edge_schema",
    "events_document",
    "node_document",
    "node_schema",
    "proof_document",
    "resolved_under",
    "schema_directory",
]
