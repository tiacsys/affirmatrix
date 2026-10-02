"""The content extractor — Implementation and TestSpecification records.

Turns source into content hashes: one principle, two bindings. The parser only
*locates* a span; the hashed bytes are the verbatim bytes of the source file
(SEG-SREQ-001), never text a tool has normalized or reflowed. That rules out
hashing ``ast.get_docstring(clean=True)`` for Python, whose output normalizes
indentation, and Doxygen's own description text for C (SEG-SREQ-170). In both
bindings a node carries ``apiHash`` and ``bodyHash`` (an implementation) or
``specHash`` and ``implHash`` (a test specification), and the marker that
states an edge sits inside a hashed span, so re-pointing it changes the hash
and correctly trips the edge suspect.

**C, located by Doxygen.** Structure comes from the need exports, content from
the source (SEG-SREQ-152): an Implementation's or TestSpecification's identity
and edges are taken from the exports, verbatim, and never from the source
files (SEG-SREQ-153). The Doxygen XML then locates each node through the
member its symbol names (SEG-SREQ-159 to SEG-SREQ-162), and the extractor reads
the lines it names from the source file. Every span is a run of whole lines,
terminators included, so ``sed -n 'a,bp' <file> | sha256sum`` reproduces the
hash; where each span starts and ends, per construct and per hash, is fixed in
ADR-0011. A record's locator names the symbol (``symbol:<name>#api``,
``#body``, ``#spec``, ``#impl``), never a line. No text from the Doxygen
output is ever hashed: the XML is asked for names, kinds and locations only
(SEG-SREQ-170).

Every need in the implementation export is an Implementation and every need in
the test-case export a TestSpecification: no type filter is configured for
them. The symbol a need names is its ``title`` on an implementation need and its
``test_function`` on a test-case need.

**When an error is raised.** What the exports and the Doxygen trees alone can
show is checked when the extractor is constructed, before any record is
supplied: an unreadable export, one with several versions or a build timestamp
(SEG-SREQ-158), a need that lacks its symbol, a Doxygen tree that is missing or
does not parse. What needs a location or a source is checked when
:meth:`CSourceExtractor.nodes` reaches the node, and it raises there: it never
skips a node, so the stream is never short, and the records supplied before
the failing node have already been supplied. A consumer may rely on that only
because it consumes the whole stream before it writes anything, as the drift
derivation consumes both record streams completely. Every message names the
need.

**Python, located by ``ast``.** The docstring-field markers declare identity
and edges: ``:implements:`` on an implementation, ``:verifies:`` and
``:test-id:`` on a test. Both ``:implements:`` and ``:verifies:`` name a
requirement, so a ``Verifies`` edge runs from a test specification to the
requirement, never to another specification. A test carries ``:test-id:`` as
well, because implementation identity is the dotted path and needs no marker,
whereas a specification identity is manual and deliberately independent of the
test function's name and location, so for tests it has to be stated rather than
derived. Span boundaries are defined parser-independently, and the canonical
content form is the verbatim byte span.

The Python binding is not yet built: this section is documentation only.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any

from affirmatrix import config
from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources import _exports

__all__ = [
    "CSourceExtractor",
    "ExtractorError",
    "declaration_end",
    "find_comment",
    "head_end",
    "span",
    "split_lines",
]

_IMPLEMENTATION = "Implementation"
_TEST_SPECIFICATION = "TestSpecification"
_IMPLEMENTS = "Implements"
_VERIFIES = "Verifies"
_LOCATOR_SUFFIX = {"apiHash": "api", "bodyHash": "body", "specHash": "spec", "implHash": "impl"}

#: A line whose first non-blank text opens a conditional: it may sit between a
#: documentation comment and the line it documents (ADR-0011).
_GUARD_LINE = re.compile(rb"^[ \t]*#[ \t]*if(n?def)?\b")


class ExtractorError(Exception):
    """A node, or an input, cannot be turned into content the extractor may hash.

    Raised at construction for what the exports and the Doxygen trees alone
    show, and while the node stream is consumed for what needs a location or a
    source. The message of a per-node error names the need.
    """


def split_lines(data: bytes) -> list[bytes]:
    """The lines of ``data``, each with its terminator.

    Lines end at a line feed and nowhere else, so a CR before the line feed is
    part of the line and a lone CR is not a line break: the numbering is that of
    Doxygen and of ``sed``. A last line without a terminator is kept as it is.
    """
    return io.BytesIO(data).readlines()


def span(lines: Sequence[bytes], first: int, last: int) -> bytes:
    """The bytes of lines ``first`` to ``last``, 1-based and inclusive.

    Each line is included whole with its terminator, the last line's included;
    nothing is trimmed or normalized, and a last line that has no terminator
    gets none. A run outside the file is an error rather than a shorter run.

    :implements: SEG-SREQ-168
    """
    if not 1 <= first <= last <= len(lines):
        raise ExtractorError(
            f"lines {first} to {last} are not a run inside a file of {len(lines)} lines"
        )
    return b"".join(lines[first - 1 : last])


def find_comment(lines: Sequence[bytes], located: int) -> tuple[int, int]:
    """The opener and the closer of the documentation comment above line ``located``.

    Starting at the line above, step upward over guard lines only (``#if``,
    ``#ifdef``, ``#ifndef``); a blank line is not one and ends the search. The
    line reached must end with ``*/`` (trailing whitespace ignored): the closer.
    The opener is the nearest line at or above the closer holding a comment
    opener, which must be ``/**`` or ``/*!``; ``/**/`` and ``/***`` are plain
    comments. Anything else means the node has no documentation comment, an
    error, never an empty run.

    Returns the two line numbers, 1-based. The lines between the closer and
    ``located`` are guard lines, and a span from the opener to ``located`` holds
    them; a guard line above the opener is outside.

    :implements: SEG-SREQ-169
    """
    if not 1 <= located <= len(lines):
        raise ExtractorError(f"line {located} is not inside a file of {len(lines)} lines")
    closer = located - 1
    while closer >= 1 and _GUARD_LINE.match(lines[closer - 1]):
        closer -= 1
    if closer < 1 or not lines[closer - 1].rstrip().endswith(b"*/"):
        raise ExtractorError(f"no documentation comment directly above line {located}")
    opener = closer
    while opener >= 1 and b"/*" not in lines[opener - 1]:
        opener -= 1
    if opener < 1:
        raise ExtractorError(f"the comment closing on line {closer} has no opener")
    text = lines[opener - 1]
    start = text.index(b"/*")
    token = text[start : start + 4]
    documenting = token[:3] in (b"/**", b"/*!") and token not in (b"/**/", b"/***")
    if not documenting:
        raise ExtractorError(
            f"the comment opening on line {opener} is not a documentation comment "
            "(it must start with /** or /*!)"
        )
    return opener, closer


def declaration_end(lines: Sequence[bytes], located: int) -> int:
    """The number of the line holding the semicolon that ends the declaration at ``located``.

    The first ``;`` at parenthesis depth zero, scanning from the start of line
    ``located``, with the text of comments (block, across lines, and line
    comments) skipped. A ``{`` at depth zero before it, a ``)`` with no ``(``, or
    no semicolon at all is an error: the declaration is not one this rule can
    end.
    """
    depth = 0
    in_comment = False
    for number in range(located, len(lines) + 1):
        text = lines[number - 1]
        index = 0
        while index < len(text):
            pair = text[index : index + 2]
            if in_comment:
                if pair == b"*/":
                    in_comment = False
                    index += 1
            elif pair == b"/*":
                in_comment = True
                index += 1
            elif pair == b"//":
                break
            else:
                char = text[index : index + 1]
                if char == b"(":
                    depth += 1
                elif char == b")":
                    depth -= 1
                    if depth < 0:
                        raise ExtractorError(
                            f"line {number}: a ')' closes no '(' in the declaration at {located}"
                        )
                elif char == b"{" and depth == 0:
                    raise ExtractorError(
                        f"line {number}: a '{{' comes before the semicolon ending the "
                        f"declaration at {located}"
                    )
                elif char == b";" and depth == 0:
                    return number
            index += 1
    raise ExtractorError(f"no semicolon ends the declaration at line {located}")


def head_end(lines: Sequence[bytes], first: int, last: int) -> int:
    """The last line of the head of a definition whose lines are ``first`` to ``last``.

    The line before the first line, from ``first`` on, whose first non-blank
    character is ``{``. An error if a line of the head holds a ``{``, if no such
    line lies at or before ``last``, or if it is ``first`` itself, which would
    leave no head.
    """
    if not 1 <= first <= last <= len(lines):
        raise ExtractorError(
            f"lines {first} to {last} are not a run inside a file of {len(lines)} lines"
        )
    for number in range(first, last + 1):
        text = lines[number - 1]
        if text.lstrip().startswith(b"{"):
            if number == first:
                raise ExtractorError(f"the definition at line {first} has no head before its '{{'")
            return number - 1
        if b"{" in text:
            raise ExtractorError(f"line {number}: the head of a definition holds a '{{'")
    raise ExtractorError(f"no line from {first} to {last} opens the body with a '{{'")


def _names(symbol: str, line: bytes) -> bool:
    """Whether ``symbol`` occurs in ``line`` as a whole identifier."""
    pattern = rb"(?<![A-Za-z0-9_])" + re.escape(symbol.encode("utf-8")) + rb"(?![A-Za-z0-9_])"
    return re.search(pattern, line) is not None


@dataclass(frozen=True, slots=True)
class _Member:
    """A Doxygen member: its kind and the attributes of its ``<location>``."""

    kind: str
    location: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _Stream:
    """One kind of node: the export it comes from and the tree that locates it."""

    kind: str
    label: str
    export: Path
    needs: Mapping[str, Mapping[str, Any]]
    members: Mapping[str, Mapping[tuple[Any, ...], _Member]]
    symbol_field: str
    hash_names: tuple[str, str]
    link_field: str
    edge_kind: str


def _index_members(directory: Path, label: str) -> dict[str, dict[tuple[Any, ...], _Member]]:
    """Every member of a Doxygen tree by name, one entry per distinct definition.

    A definition is distinct by its ``id`` and its location: one definition
    listed in two compounds is one, an ``id`` at two locations or two ``id``\\ s
    are two.
    """
    if not directory.is_dir():
        raise ExtractorError(f"{label} Doxygen output {directory}: is not a directory")
    members: dict[str, dict[tuple[Any, ...], _Member]] = {}
    for path in sorted(directory.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as cause:
            raise ExtractorError(
                f"{label} Doxygen output {path}: cannot be read: {cause}"
            ) from cause
        for element in root.iter("memberdef"):
            name = element.findtext("name")
            if not name:
                continue
            location = element.find("location")
            attributes = dict(location.attrib) if location is not None else {}
            key = (element.get("id"), tuple(sorted(attributes.items())))
            members.setdefault(name, {})[key] = _Member(element.get("kind", ""), attributes)
    return members


def _resolve(root: Path, relative: str) -> Path:
    """The path a Doxygen location names, under ``root``; outside it is an error.

    Nothing is opened: the path is resolved (symbolic links included) and
    compared with the resolved root, so ``..``, an absolute path and a link that
    leads out are all outside.

    :implements: SEG-SREQ-162
    """
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ExtractorError(f"the path {relative!r} lies outside the root {root}")
    return target


def _check_symbol(symbol: str, lines: Sequence[bytes], number: int, what: str) -> None:
    """Refuse a location whose source line does not contain the symbol.

    :implements: SEG-SREQ-175
    """
    if not 1 <= number <= len(lines):
        raise ExtractorError(f"{what} is line {number}, outside a file of {len(lines)} lines")
    if not _names(symbol, lines[number - 1]):
        raise ExtractorError(f"{what} is line {number}, which does not contain {symbol!r}")


def _number(location: Mapping[str, str], name: str) -> int:
    """A location attribute that must be a positive line number."""
    text = location.get(name)
    if text is None:
        raise ExtractorError(f"the location has no {name!r}")
    try:
        value = int(text)
    except ValueError:
        raise ExtractorError(f"the location's {name} {text!r} is not a line number") from None
    if value < 1:
        raise ExtractorError(f"the location's {name} is {value}: the member has no such lines")
    return value


def _body_span(location: Mapping[str, str]) -> tuple[int, int]:
    """The lines the located body occupies, ``bodystart`` to ``bodyend``.

    Used for an Implementation's bodyHash and a TestSpecification's implHash.

    :implements: SEG-SREQ-165
    :implements: SEG-SREQ-167
    """
    first = _number(location, "bodystart")
    last = _number(location, "bodyend")
    if last < first:
        raise ExtractorError(f"the body ends on line {last}, before it starts on line {first}")
    return first, last


def _declared_api(lines: Sequence[bytes], located: int) -> tuple[int, int]:
    """The api span of a function declared in a header: comment through declaration end.

    :implements: SEG-SREQ-163
    """
    return find_comment(lines, located)[0], declaration_end(lines, located)


def _same_file_api(lines: Sequence[bytes], first: int, last: int) -> tuple[int, int]:
    """The api span of a function declared and defined in one file: comment through its head.

    :implements: SEG-SREQ-163
    """
    return find_comment(lines, first)[0], head_end(lines, first, last)


def _macro_api(lines: Sequence[bytes], located: int) -> tuple[int, int]:
    """The api span of a macro: comment, guard lines included, through the definition line.

    :implements: SEG-SREQ-164
    """
    return find_comment(lines, located)[0], located


def _spec_span(lines: Sequence[bytes], located: int) -> tuple[int, int]:
    """The specHash span of a test: its documentation comment, opener through closer.

    :implements: SEG-SREQ-166
    """
    return find_comment(lines, located)


@dataclass(frozen=True, slots=True)
class CSourceExtractor:
    """Implementation and TestSpecification records for C, from exports and located source.

    ``root`` is the directory the source files are read from, ``repository`` the
    configured name of the repository they belong to (a name, never a path).
    ``implementations`` and ``specifications`` each name a need export and the
    Doxygen output that locates its symbols; a stream that is ``None`` supplies
    nothing. Identity and edges come from the exports; content comes from the
    lines the Doxygen output locates in the files under ``root``.

    The exports and the Doxygen trees are read and checked once, here; no source
    file is opened until :meth:`nodes` needs it.

    :implements: SEG-SREQ-152
    """

    root: Path
    _: KW_ONLY
    repository: str
    implementations: config.ImplementationInputs | None
    specifications: config.SpecificationInputs | None
    _streams: tuple[_Stream, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Read and check every configured stream, refusing an export that carries a timestamp.

        :implements: SEG-SREQ-158
        """
        streams = []
        if self.implementations is not None:
            streams.append(
                self._read_stream(
                    self.implementations.export,
                    self.implementations.doxygen,
                    kind=_IMPLEMENTATION,
                    label="implementation",
                    symbol_field="title",
                    hash_names=("apiHash", "bodyHash"),
                    link_field="satisfies",
                    edge_kind=_IMPLEMENTS,
                )
            )
        if self.specifications is not None:
            streams.append(
                self._read_stream(
                    self.specifications.export,
                    self.specifications.doxygen,
                    kind=_TEST_SPECIFICATION,
                    label="test-case",
                    symbol_field="test_function",
                    hash_names=("specHash", "implHash"),
                    link_field="verifies",
                    edge_kind=_VERIFIES,
                )
            )
        object.__setattr__(self, "_streams", tuple(streams))

    @staticmethod
    def _read_stream(
        export: Path,
        doxygen: Path,
        *,
        kind: str,
        label: str,
        symbol_field: str,
        hash_names: tuple[str, str],
        link_field: str,
        edge_kind: str,
    ) -> _Stream:
        """One stream: the export's needs, checked, and the tree's members, indexed.

        :implements: SEG-SREQ-153
        """
        needs = _exports.read_needs(export, f"{label} export", ExtractorError)
        for key, need in needs.items():
            _exports.check_need(
                export,
                f"{label} export",
                ExtractorError,
                key,
                need,
                ("id", symbol_field),
                link_field,
            )
            if not need[symbol_field]:
                raise ExtractorError(f"{label} export {export}: need {key!r} has an empty symbol")
        return _Stream(
            kind=kind,
            label=label,
            export=export,
            needs=needs,
            members=_index_members(doxygen, label),
            symbol_field=symbol_field,
            hash_names=hash_names,
            link_field=link_field,
            edge_kind=edge_kind,
        )

    @staticmethod
    def _identifier(need: Mapping[str, Any]) -> str:
        """The need's identifier, verbatim: never derived from the symbol or the source.

        :implements: SEG-SREQ-154
        :implements: SEG-SREQ-155
        """
        return need["id"]

    def edges(self) -> Iterator[EdgeRecord]:
        """A pending edge per link a need declares, from the need to the requirement.

        An Implements edge per ``satisfies`` link of an implementation need and a
        Verifies edge per ``verifies`` link of a test-case need, in export order.
        Needs no Doxygen output and no source, and cannot fail: the exports were
        checked at construction. A target the export does not hold is emitted all
        the same; the graph reports it as a broken edge.

        :implements: SEG-SREQ-156
        :implements: SEG-SREQ-157
        """
        for stream in self._streams:
            for need in stream.needs.values():
                for target in need.get(stream.link_field) or []:
                    yield EdgeRecord(
                        from_id=self._identifier(need),
                        to_id=target,
                        kind=stream.edge_kind,
                        state=LinkState.PENDING,
                    )

    def nodes(self) -> Iterator[NodeRecord]:
        """A record per need of each configured stream, in export order.

        Each hash is the SHA-256 of a run of whole lines of a source file and of
        nothing the Doxygen output says in words (SEG-SREQ-170). A source file is
        read once per call, so every node of one pass sees the same bytes, and a
        second call reads again. An error for a node is raised when the stream
        reaches it, never skipped; the consumer must take the whole stream before
        it writes (see the module docstring).

        :implements: SEG-SREQ-170
        """
        files: dict[Path, list[bytes]] = {}
        for stream in self._streams:
            for need in stream.needs.values():
                need_id = self._identifier(need)
                symbol = need[stream.symbol_field]
                try:
                    node = self._node(stream, need_id, symbol, files)
                except ExtractorError as error:
                    raise ExtractorError(
                        f"{stream.label} need {need_id!r} (symbol {symbol!r}): {error}"
                    ) from error
                yield node

    def _locate(self, stream: _Stream, symbol: str) -> _Member:
        """The one Doxygen member whose name is the symbol.

        :implements: SEG-SREQ-159
        :implements: SEG-SREQ-160
        :implements: SEG-SREQ-161
        """
        found = list(stream.members.get(symbol, {}).values())
        if not found:
            raise ExtractorError("no member of the Doxygen output has this name")
        if len(found) > 1:
            raise ExtractorError(f"the Doxygen output defines {len(found)} members with this name")
        return found[0]

    def _lines(self, files: dict[Path, list[bytes]], path: Path) -> list[bytes]:
        """The lines of a file under the root, read once per pass."""
        if path not in files:
            try:
                files[path] = split_lines(path.read_bytes())
            except OSError as cause:
                raise ExtractorError(f"{path} cannot be read: {cause}") from cause
        return files[path]

    def _node(
        self, stream: _Stream, need_id: str, symbol: str, files: dict[Path, list[bytes]]
    ) -> NodeRecord:
        """The record of one need: locate, resolve, check, cut, hash, anchor."""
        member = self._locate(stream, symbol)
        location = member.location
        kind = member.kind
        if stream.kind == _IMPLEMENTATION and kind == "define":
            paths = ("file", "bodyfile")
        elif stream.kind == _IMPLEMENTATION and kind == "function":
            paths = ("declfile", "file", "bodyfile") if "declfile" in location else ("bodyfile",)
        elif stream.kind == _TEST_SPECIFICATION and kind == "function":
            paths = ("file", "bodyfile")
        else:
            raise ExtractorError(f"a member of kind {kind!r} has no rule for a {stream.kind}")
        for name in paths:
            if name not in location:
                raise ExtractorError(f"the location has no {name!r}")
        resolved = {name: _resolve(self.root, location[name]) for name in paths}
        body_first, body_last = _body_span(location)
        body_lines = self._lines(files, resolved["bodyfile"])
        _check_symbol(symbol, body_lines, body_first, "the body start")

        if stream.kind == _TEST_SPECIFICATION:
            located = _number(location, "line")
            if located != body_first:
                raise ExtractorError(
                    f"the test is located at line {located} but its body starts at {body_first}"
                )
            api_path = "file"
            api_lines = self._lines(files, resolved["file"])
            _check_symbol(symbol, api_lines, located, "the located line")
            api_first, api_last = _spec_span(api_lines, located)
        elif kind == "define":
            located = _number(location, "line")
            api_path = "file"
            api_lines = self._lines(files, resolved["file"])
            _check_symbol(symbol, api_lines, located, "the located line")
            api_first, api_last = _macro_api(api_lines, located)
        elif "declfile" in location:
            located = _number(location, "declline")
            api_path = "declfile"
            api_lines = self._lines(files, resolved["declfile"])
            _check_symbol(symbol, api_lines, located, "the declaration line")
            _check_symbol(
                symbol,
                self._lines(files, resolved["file"]),
                _number(location, "line"),
                "the located line",
            )
            api_first, api_last = _declared_api(api_lines, located)
        else:
            api_path = "bodyfile"
            api_lines = body_lines
            api_first, api_last = _same_file_api(api_lines, body_first, body_last)

        api_name, body_name = stream.hash_names
        spans = {
            api_name: (location[api_path], span(api_lines, api_first, api_last)),
            body_name: (location["bodyfile"], span(body_lines, body_first, body_last)),
        }
        return NodeRecord(
            local_id=need_id,
            kind=stream.kind,
            content_anchors=self._anchors(symbol, spans),
        )

    def _anchors(
        self, symbol: str, spans: Mapping[str, tuple[str, bytes]]
    ) -> dict[str, ContentAnchor]:
        """Each named hash, anchored at the file its span was read from.

        The repository is the configured name; the path is the file as Doxygen
        names it; the locator names the symbol and the hash, never a line.

        :implements: SEG-SREQ-171
        :implements: SEG-SREQ-172
        :implements: SEG-SREQ-173
        :implements: SEG-SREQ-174
        :implements: SEG-SREQ-134
        """
        return {
            name: ContentAnchor(
                digest=content_hash(data),
                repository=self.repository,
                path=path,
                locator=f"symbol:{symbol}#{_LOCATOR_SUFFIX[name]}",
            )
            for name, (path, data) in spans.items()
        }
