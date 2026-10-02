"""The requirements reader — a thin reader over the built ``needs.json``.

Turns the requirement specification's reproducible export into Requirement
records: the need ID verbatim as the case-local identifier (ADR-0007), the
canonical content form as the hash input, and the parent links as edges.

Two disciplines it carries:

* **Forward links only.** Back-link fields (``*_back``) are derived by
  sphinx-needs and can go stale in an incremental build; this reader consumes
  the one forward field it is configured with, ``refines`` unless told
  otherwise, and never reads a back-link field itself.
* **Clean build.** ``needs.json`` is consumed from a clean build; a stale
  export is a wrong input, not a tolerable one. The reader cannot see how an
  export was built, but it refuses the one mark of a non-reproducible build it
  can see, a build timestamp (``created``).

Three further properties are the reader's:

* **An export that cannot be read raises.** Every check runs when the reader is
  constructed, so :meth:`RequirementsReader.nodes` and
  :meth:`RequirementsReader.edges` can never yield a short stream: a
  truncated stream builds a smaller graph that seals to a valid root over
  requirements nobody meant to omit. An export must hold exactly one version,
  because the reader serves one build; choosing between two builds' hashes
  would be a silent decision.
* **A dangling parent is emitted, not refused.** A parent target that the
  export does not hold, or holds as a need of an unconfigured type, still
  becomes an edge; the graph reports it as a broken edge. Refusing would hide
  the whole graph from the operator over one stale link. The gap this leaves
  open: with only some types configured, every edge to a parent of another type
  is broken, and the reader does not say so.
* **An anchor names the source, not a span.** Each content hash is anchored at
  the need's source file, with the locator ``need:<id>``. The source file is
  the one a source map names for the need's docname, or else the need's docname
  and doctype under the source directory. The hashed form is built from the
  export's fields, not sliced from that file's bytes, so recomputing the hash
  needs the build.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affirmatrix import config
from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources import SourceError, _exports

_REQUIREMENT = "Requirement"
_REFINES = "Refines"
_CONTENT_HASH = "contentHash"
_LABEL = "requirement export"
_TEXT_FIELDS = ("id", "title", "content", "docname", "doctype")

#: The key a need's parents have in the canonical form, whatever need field holds them.
_PARENTS_KEY = "refines"


class ReaderError(SourceError):
    """The requirement export cannot be read as a record source.

    Raised at construction, before any record is supplied.
    """


def canonical_form(
    need: Mapping[str, Any], parent_field: str = config.DEFAULT_PARENT_FIELD
) -> bytes:
    """The canonical serialization of a need's authored fields, as bytes.

    RFC 8785 canonical JSON, in UTF-8, of an object holding the need's
    ``title``, ``content`` and parent links and nothing else: the identifier,
    the status, the tags and every derived field are left out because the
    object is built from these three keys, not filtered from the need. The
    parent links are read from the need field ``parent_field`` and always
    carry the key ``refines``, so the same parents give the same bytes whatever
    the field is called. A need with no parent links (the field absent or null)
    serializes an empty array.

    The standard library encoder produces RFC 8785's form for these value
    types: the members are strings and one array of strings, so sorted keys
    (all ASCII, where code-point and UTF-16 order agree), no insignificant
    whitespace, minimal string escaping and unescaped non-ASCII text (hence
    ``ensure_ascii=False``) are all the standard asks for; RFC 8785's number
    rule never applies because no number is in the object. A number joining
    the form would need this encoding revisited. ``proof/_package.py`` carries
    the same reasoning for its own metadata; the two are not shared because
    ``sources`` may not import ``proof`` and ``proof`` may not import the
    hashing module, so no module both may reach is the right home.

    :implements: SEG-SREQ-147
    :implements: SEG-SREQ-148
    """
    form = {
        "content": need["content"],
        _PARENTS_KEY: sorted(need.get(parent_field) or []),  # the sort: link order is not content
        "title": need["title"],
    }
    return json.dumps(form, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


@dataclass(frozen=True, slots=True)
class RequirementsReader:
    """The requirement export presented as a record source.

    ``export`` is the ``needs.json`` of a clean build; ``types`` the need types
    that are requirements; ``repository`` the configured name of the repository
    the requirement document lives in (a name, never a path). Exactly one of
    ``source_directory`` and ``source_map`` says where a need's source file is,
    both *relative to that repository*. The path an anchor carries is a pure
    join of the source directory with the need's docname and doctype, or the
    file the map names for the need's docname; no filesystem is consulted.
    ``parent_field`` is the need field that holds the parent links.

    The export is read and checked once, here.

    :implements: SEG-SREQ-144
    :implements: SEG-SREQ-271
    :implements: SEG-SREQ-272
    """

    export: Path
    types: frozenset[str]
    repository: str
    source_directory: Path | None = None
    source_map: Mapping[str, Path] | None = None
    parent_field: str = config.DEFAULT_PARENT_FIELD
    _needs: Mapping[str, Mapping[str, Any]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Read and check the export, refusing one that cannot serve a build.

        :implements: SEG-SREQ-150
        :implements: SEG-SREQ-274
        """
        if (self.source_directory is None) == (self.source_map is None):
            raise ReaderError("a reader needs exactly one of a source directory and a source map")
        needs = _exports.read_needs(self.export, _LABEL, ReaderError)
        for key, need in needs.items():
            if need.get("type") in self.types:
                _exports.check_need(
                    self.export, _LABEL, ReaderError, key, need, _TEXT_FIELDS, self.parent_field
                )
        if self.source_map is not None:
            uncovered = sorted(
                {
                    need["docname"]
                    for need in needs.values()
                    if need.get("type") in self.types and need["docname"] not in self.source_map
                }
            )
            if uncovered:
                raise ReaderError(
                    _exports.itemized(
                        f"{_LABEL} {self.export}: the source map names no source file for "
                        f"{len(uncovered)} docname(s) of configured needs",
                        uncovered,
                    )
                )
        object.__setattr__(self, "_needs", needs)

    def _configured(self) -> Iterator[Mapping[str, Any]]:
        """The needs whose type is one of the configured requirement types.

        :implements: SEG-SREQ-145
        """
        for need in self._needs.values():
            if need.get("type") in self.types:
                yield need

    @staticmethod
    def _identifier(need: Mapping[str, Any]) -> str:
        """The need's identifier, verbatim: never prefixed, re-cased or normalised.

        :implements: SEG-SREQ-146
        """
        return need["id"]

    def _anchor(self, need: Mapping[str, Any]) -> ContentAnchor:
        """The content hash of ``need``, anchored at its source file in the repository.

        The repository is named by its configured name. The path is the file
        the source map names for the need's docname, or else the need's
        docname and doctype under the source directory.

        :implements: SEG-SREQ-151
        :implements: SEG-SREQ-134
        :implements: SEG-SREQ-273
        """
        if self.source_map is not None:
            path = self.source_map[need["docname"]].as_posix()
        else:
            assert self.source_directory is not None  # checked when the reader is built
            path = (self.source_directory / f"{need['docname']}{need['doctype']}").as_posix()
        return ContentAnchor(
            digest=content_hash(canonical_form(need, self.parent_field)),
            repository=self.repository,
            path=path,
            locator=f"need:{self._identifier(need)}",
        )

    def content(self, local_id: str, hash_name: str) -> bytes | None:
        """The canonical form from which the reader computed the hash of one requirement.

        :implements: SEG-SREQ-311

        The bytes are the canonical form of :func:`canonical_form`, verbatim
        (not a readable rendering of the need): the exact input of the hash.
        They are built from the export that the reader holds since it was
        constructed, so the call opens no file. ``None`` for an identifier that
        is not a need of a configured type, and for any name but ``contentHash``.
        """
        need = self._needs.get(local_id)
        if hash_name != _CONTENT_HASH or need is None or need.get("type") not in self.types:
            return None
        return canonical_form(need, self.parent_field)

    def nodes(self) -> Iterator[NodeRecord]:
        """A Requirement record per need of a configured type, in export order."""
        for need in self._configured():
            yield NodeRecord(
                local_id=self._identifier(need),
                kind=_REQUIREMENT,
                content_anchors={_CONTENT_HASH: self._anchor(need)},
            )

    def edges(self) -> Iterator[EdgeRecord]:
        """A pending Refines edge per link a configured need declares, child to parent.

        Only the configured parent field is read, and never a back-link field
        of the export; a target the export does not hold is emitted all the
        same (see the module docstring).

        :implements: SEG-SREQ-149
        """
        for need in self._configured():
            for parent in need.get(self.parent_field) or []:
                yield EdgeRecord(
                    from_id=self._identifier(need),
                    to_id=parent,
                    kind=_REFINES,
                    state=LinkState.PENDING,
                )
