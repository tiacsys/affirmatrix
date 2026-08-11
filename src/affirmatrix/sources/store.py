"""The store loader — iteration 0's record source over the would-be store.

Reads the hand-authored fixture under ``tests/fixtures/would_be_store/`` and
produces the *current* record stream: node records whose content hashes are the
digests of the content the store holds, and the edges declared alongside them.

**Test scaffolding.** No requirements attach to this adapter; it exists so the
engine has an input before record production is built, and it retires when the
real extractors and the requirements reader land. It is the "would-be store" —
it holds content and is deliberately not schema-validated, unlike the
affirmation store, which holds hashes and references and always is.

The layout it reads is described in the store's own README, which is the
authority on the format. Three properties of the reading are the loader's:

* **Content is hashed verbatim** — the bytes on disk, with no stripping and no
  normalization. A loader that tidied content on the way in would make the hash
  a function of the loader rather than of what the store holds.
* **Every edge is pending.** The store holds content, not affirmations, so no
  edge in it carries a hash it was affirmed against. Affirmed state belongs to
  the recorded stream, which is the affirmation store's to supply.
* **A store that cannot be read raises.** Never a short record stream: a
  truncated stream builds a smaller graph that seals to a perfectly valid root
  over content nobody meant to omit.

Each hash is anchored to where its content lives, and the anchor is a stated
substitution rather than a fabrication: the would-be store is an unversioned
directory of content files, so the ``content/`` directory plays the repository,
the manifest's declared path is the path, and the locator is ``file`` — the
whole file, which is literally what was hashed. The triple genuinely resolves
to the hashed bytes on this machine, and claims nothing more; no revision
exists here to anchor to. The real extractors supply true repositories.

What it does not do is judge the records. A duplicate identifier, an undeclared
kind, an edge to a node that is not there — each is somebody's error, but not
this component's to report: the graph builder refuses the first two and the
suspect detector decides the third. A producer says what the store holds.

Iteration-0 backlog item B9.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord

_NODES = "nodes"
_EDGES = "edges"
_CONTENT = "content"
_MANIFEST_GLOB = "*.toml"


class StoreError(Exception):
    """The would-be store cannot be read as a record stream.

    Raised rather than collected, and raised for a missing store rather than
    answered with an empty one, because every condition it reports would
    otherwise reach the engine as content that simply is not there.
    """


@dataclass(frozen=True, slots=True)
class StoreLoader:
    """A would-be store presented as a record source.

    Reads on demand and keeps nothing: each call to :meth:`nodes` or
    :meth:`edges` re-reads the store, so the stream reflects the content as it
    is now. That is what makes the store editable between two workflow runs —
    the drift-detection exercise depends on it.

    The root is checked when the loader is constructed. A mistyped path caught
    here is a message about a path; caught nowhere it is a graph with no nodes
    in it, and nothing downstream can tell that apart from a store that is
    genuinely empty.
    """

    root: Path

    def __post_init__(self) -> None:
        for name in (_NODES, _EDGES, _CONTENT):
            directory = self.root / name
            if not directory.is_dir():
                raise StoreError(
                    f"{self.root} is not a would-be store: it has no {name!r} directory"
                )

    def nodes(self) -> Iterator[NodeRecord]:
        """The node records the store declares, manifest by manifest."""
        for manifest in _manifests(self.root / _NODES):
            document = _read_manifest(manifest)
            kind = _declared_kind(document, manifest)
            for local_id, declaration in _table(document, _NODES, manifest).items():
                yield NodeRecord(
                    local_id=local_id,
                    kind=kind,
                    content_anchors=self._content_anchors(local_id, declaration, manifest),
                )

    def edges(self) -> Iterator[EdgeRecord]:
        """The edge records the store declares, grouped by kind in each manifest.

        Every one is pending: see the module docstring.
        """
        for manifest in _manifests(self.root / _EDGES):
            document = _read_manifest(manifest)
            for kind, pairs in _table(document, _EDGES, manifest).items():
                for pair in _endpoint_pairs(pairs, kind, manifest):
                    yield EdgeRecord(
                        from_id=pair[0],
                        to_id=pair[1],
                        kind=kind,
                        state=LinkState.PENDING,
                    )

    def _content_anchors(
        self, local_id: str, declaration: Any, manifest: Path
    ) -> Mapping[str, ContentAnchor]:
        """Hash and locate the content files one entry declares, keyed by field name.

        The field names are not checked against the vocabulary here. The graph
        builder already refuses a node carrying names its kind does not declare,
        and stating the same rule twice invites two spellings of it.

        The location per hash is the module docstring's stated substitution:
        the content directory as repository, the declared path, the whole file
        as span.
        """
        if not isinstance(declaration, dict) or not declaration:
            raise StoreError(
                f"{manifest}: entry {local_id!r} declares no content files; a node with "
                "no content hash has nothing for the graph to anchor to"
            )
        return {
            field: ContentAnchor(
                digest=content_hash(self._content_bytes(local_id, field, path, manifest)),
                repository=str(self.root / _CONTENT),
                path=str(path),
                locator="file",
            )
            for field, path in declaration.items()
        }

    def _content_bytes(self, local_id: str, field: str, declared: Any, manifest: Path) -> bytes:
        """The bytes of one content file, exactly as stored."""
        if not isinstance(declared, str):
            raise StoreError(
                f"{manifest}: entry {local_id!r} gives {declared!r} for {field!r}, which is "
                "not a path to a content file"
            )
        base = (self.root / _CONTENT).resolve()
        path = (base / declared).resolve()
        if not path.is_relative_to(base):
            raise StoreError(
                f"{manifest}: entry {local_id!r} declares the content path {declared!r}, "
                f"which resolves outside the store's content directory"
            )
        try:
            return path.read_bytes()
        except OSError as error:
            raise StoreError(
                f"{manifest}: entry {local_id!r} declares the content path {declared!r}, "
                f"which cannot be read: {error}"
            ) from error


def _manifests(directory: Path) -> list[Path]:
    """The manifests in one directory, in filename order.

    Sorted, so the record stream is reproducible across machines and across
    filesystems — a design root sealed over an unordered stream would still be
    valid, and would still differ from the one the next run computed.
    """
    return sorted(directory.glob(_MANIFEST_GLOB))


def _read_manifest(manifest: Path) -> dict[str, Any]:
    try:
        with manifest.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise StoreError(f"{manifest} is not readable as a manifest: {error}") from error
    except OSError as error:
        raise StoreError(f"{manifest} cannot be read: {error}") from error


def _declared_kind(document: dict[str, Any], manifest: Path) -> str:
    """The one node kind a node manifest's entries share."""
    kind = document.get("kind")
    if not isinstance(kind, str) or not kind:
        raise StoreError(f"{manifest} declares no 'kind' for the entries it contains")
    return kind


def _table(document: dict[str, Any], name: str, manifest: Path) -> dict[str, Any]:
    """One manifest's table of entries, empty if it declares none."""
    table = document.get(name, {})
    if not isinstance(table, dict):
        raise StoreError(f"{manifest}: {name!r} must be a table of entries")
    return table


def _endpoint_pairs(pairs: Any, kind: str, manifest: Path) -> list[list[str]]:
    """Validate one edge kind's list of ``[from, to]`` pairs."""
    if not isinstance(pairs, list):
        raise StoreError(f"{manifest}: edge kind {kind!r} must list its endpoint pairs")
    for pair in pairs:
        if not (
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(endpoint, str) for endpoint in pair)
        ):
            raise StoreError(
                f"{manifest}: edge kind {kind!r} declares {pair!r}, which is not a pair "
                "of endpoint identifiers"
            )
    return pairs


__all__ = ["StoreError", "StoreLoader"]
