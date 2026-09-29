"""The requirements reader — a thin reader over the built ``needs.json``.

Turns the requirement specification's reproducible export into Requirement
records: the need ID verbatim as the case-local identifier (ADR-0007), the
canonical content form as the hash input, and the ``refines`` declarations as
edges.

Two disciplines it carries:

* **Forward links only.** Back-link fields (``*_back``) are derived by
  sphinx-needs and can go stale in an incremental build; this reader consumes
  the forward ``refines`` and never reads a back-link field.
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
* **A dangling parent is emitted, not refused.** A ``refines`` target that the
  export does not hold, or holds as a need of an unconfigured type, still
  becomes an edge; the graph reports it as a broken edge. Refusing would hide
  the whole graph from the operator over one stale link. The gap this leaves
  open: with only some types configured, every edge to a parent of another type
  is broken, and the reader does not say so.
* **An anchor names the source, not a span.** Each content hash is anchored at
  the need's source file, with the locator ``need:<id>``. The hashed form is
  built from the export's fields, not sliced from that file's bytes, so
  recomputing the hash needs the build.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord

_REQUIREMENT = "Requirement"
_REFINES = "Refines"
_CONTENT_HASH = "contentHash"
_TIMESTAMP_KEY = "created"
_TEXT_FIELDS = ("id", "title", "content", "docname", "doctype")


class ReaderError(Exception):
    """The requirement export cannot be read as a record source.

    Raised at construction, before any record is supplied.
    """


def canonical_form(need: Mapping[str, Any]) -> bytes:
    """The canonical serialization of a need's authored fields, as bytes.

    RFC 8785 canonical JSON, in UTF-8, of an object holding the need's
    ``title``, ``content`` and ``refines`` and nothing else: the identifier,
    the status, the tags and every derived field are left out because the
    object is built from these three keys, not filtered from the need. A need
    with no ``refines`` (absent or null) serializes an empty array.

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
        "refines": sorted(need.get("refines") or []),  # the sort: link order is not content
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
    the requirement document lives in (a name, never a path);
    ``source_directory`` the directory of the document's sources *relative to
    that repository*. The path an anchor carries is a pure join of that
    directory with the need's docname and doctype; no filesystem is consulted.

    The export is read and checked once, here.

    :implements: SEG-SREQ-144
    """

    export: Path
    types: frozenset[str]
    repository: str
    source_directory: Path
    _needs: Mapping[str, Mapping[str, Any]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Read and check the export, refusing one that cannot serve a build.

        :implements: SEG-SREQ-150
        """
        try:
            document = json.loads(self.export.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ReaderError(
                f"requirement export {self.export}: cannot be read: {error}"
            ) from error
        if not isinstance(document, dict):
            raise ReaderError(f"requirement export {self.export}: the top level is not an object")
        self._refuse_timestamps(document, "the top level")
        versions = document.get("versions")
        if not isinstance(versions, dict):
            raise ReaderError(f"requirement export {self.export}: has no 'versions' object")
        if len(versions) != 1:
            raise ReaderError(
                f"requirement export {self.export}: holds {len(versions)} versions "
                f"({', '.join(map(repr, versions)) or 'none'}); the reader serves one build, "
                "so an export must hold exactly one"
            )
        ((name, version),) = versions.items()
        if not isinstance(version, dict):
            raise ReaderError(
                f"requirement export {self.export}: version {name!r} is not an object"
            )
        self._refuse_timestamps(version, f"version {name!r}")
        needs = version.get("needs")
        if not isinstance(needs, dict):
            raise ReaderError(
                f"requirement export {self.export}: version {name!r} has no 'needs' object"
            )
        for key, need in needs.items():
            if not isinstance(need, dict):
                raise ReaderError(
                    f"requirement export {self.export}: need {key!r} is not an object"
                )
            if need.get("type") in self.types:
                self._check_need(key, need)
        object.__setattr__(self, "_needs", needs)

    def _refuse_timestamps(self, holder: Mapping[str, Any], where: str) -> None:
        """Refuse an export whose ``where`` carries a build timestamp.

        :implements: SEG-SREQ-150
        """
        if _TIMESTAMP_KEY in holder:
            raise ReaderError(
                f"requirement export {self.export}: carries a build timestamp "
                f"({_TIMESTAMP_KEY!r}) in {where}; the reader consumes only a reproducible export"
            )

    def _check_need(self, key: str, need: Mapping[str, Any]) -> None:
        """Refuse a configured-type need missing an authored or locating field."""
        for name in _TEXT_FIELDS:
            if not isinstance(need.get(name), str):
                raise ReaderError(
                    f"requirement export {self.export}: need {key!r} has no text field {name!r}"
                )
        if need["id"] != key:
            raise ReaderError(
                f"requirement export {self.export}: need {key!r} declares the id {need['id']!r}"
            )
        refines = need.get("refines")
        if refines is not None and not (
            isinstance(refines, list) and all(isinstance(parent, str) for parent in refines)
        ):
            raise ReaderError(
                f"requirement export {self.export}: need {key!r} has a 'refines' "
                "that is not a list of identifiers"
            )

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

        The repository is named by its configured name, and the path is the
        need's docname and doctype under the source directory.

        :implements: SEG-SREQ-151
        :implements: SEG-SREQ-134
        """
        path = (self.source_directory / f"{need['docname']}{need['doctype']}").as_posix()
        return ContentAnchor(
            digest=content_hash(canonical_form(need)),
            repository=self.repository,
            path=path,
            locator=f"need:{self._identifier(need)}",
        )

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

        Only the forward ``refines`` field is read; a target the export does
        not hold is emitted all the same (see the module docstring).

        :implements: SEG-SREQ-149
        """
        for need in self._configured():
            for parent in need.get("refines") or []:
                yield EdgeRecord(
                    from_id=self._identifier(need),
                    to_id=parent,
                    kind=_REFINES,
                    state=LinkState.PENDING,
                )
