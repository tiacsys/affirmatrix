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

Where need types are configured for an export, only the needs of those types
are read: a need of another type supplies no record and is never refused, even
when it has no symbol. Where none are configured, every need in the
implementation export is an Implementation and every need in the test-case
export a TestSpecification. The symbol a need names is its ``title`` on an
implementation need and its ``test_function`` on a test-case need.

Each stream names its own repository and, optionally, the prefix that every
path of its Doxygen output begins with, and a path root. The prefix is removed,
and then the root is put in front, to give the path inside the repository; that
path is what is read, what an anchor names, and what a test's module is
compared with.

**When an error is raised.** What the exports and the Doxygen trees alone can
show is checked when the extractor is constructed, before any record is
supplied, and the first such failure is raised: an unreadable export, one with
several versions or a build timestamp (SEG-SREQ-158), a need that lacks its
symbol, a Doxygen tree that is missing or does not parse. What needs a location
or a source is checked for every node as :meth:`CSourceExtractor.nodes` reaches
it. A node that fails does not stop the pass and is never skipped: the records
of the other nodes are supplied as they are reached, and at the end of the
stream one :class:`UnsuppliedNodesError` names every node it cannot supply, each
on one line with its need, its symbol and its reason (SEG-SREQ-282). A consumer
may rely on the stream never being silently short only because it consumes the
whole stream before it writes anything, as the drift derivation consumes both
record streams completely.

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
from pathlib import Path, PurePosixPath
from typing import Any

from affirmatrix import config
from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources import SourceError, _exports

__all__ = [
    "CSourceExtractor",
    "ExtractorError",
    "NodeFailure",
    "Placement",
    "UnsuppliedNodesError",
    "declaration_end",
    "find_comment",
    "find_test_comment",
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

#: A line whose first non-blank text is any conditional directive. The search
#: above a test steps over it as well as over blank lines and plain comments (ADR-0011).
_CONDITIONAL_LINE = re.compile(rb"^[ \t]*#[ \t]*(if(n?def)?|elif|else|endif)\b")


class ExtractorError(SourceError):
    """A node, or an input, cannot be turned into content the extractor may hash.

    Raised at construction for what the exports and the Doxygen trees alone
    show, and for one node while it is located and cut. The message of a
    per-node error names the need once it reaches the caller of
    :meth:`CSourceExtractor.nodes`, as a line of :class:`UnsuppliedNodesError`.
    """


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a stream's sources are: the repository's configured name and its path.

    The name is what an anchor carries (never a path); the path is the directory
    the source files of the stream are read from.
    """

    repository: str
    root: Path


@dataclass(frozen=True, slots=True)
class NodeFailure:
    """One node the extractor cannot supply: its need, its symbol and the reason."""

    label: str
    need_id: str
    symbol: str
    reason: str

    def line(self) -> str:
        """The failure as one line."""
        return f"{self.label} need {self.need_id!r} (symbol {self.symbol!r}): {self.reason}"


class UnsuppliedNodesError(ExtractorError):
    """Every node of a pass that cannot be supplied, each with its reason.

    The message has a header line and then one line for each failure, so a
    reader finds one need on one line. :attr:`failures` holds the same facts in
    stream order, implementations before test specifications.

    :implements: SEG-SREQ-282
    """

    def __init__(self, failures: Sequence[NodeFailure]) -> None:
        self.failures = tuple(failures)
        super().__init__(
            _exports.itemized(
                f"{len(self.failures)} node(s) cannot be supplied",
                [failure.line() for failure in self.failures],
            )
        )


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
    opener = _opener_line(lines, closer)
    if not _documents(lines[opener - 1]):
        raise ExtractorError(
            f"the comment opening on line {opener} is not a documentation comment "
            "(it must start with /** or /*!)"
        )
    return opener, closer


def find_test_comment(lines: Sequence[bytes], located: int) -> tuple[int, int]:
    """The opener and the closer of the documentation comment above the test at ``located``.

    Starting at the line above, step upward over blank lines, conditional lines
    (``#if``, ``#ifdef``, ``#ifndef``, ``#elif``, ``#else``, ``#endif``) and
    plain block comments, those being block comments that are not documentation
    comments and that have only white space before their opener on its line. The
    first line that is none of these must end with ``*/``: it is the closer, and
    its opener must be ``/**`` or ``/*!``. Anything else is an error, never an
    empty run: code, any other directive (``#include``, ``#define``,
    ``#pragma``), a line comment (``//``, ``///``, ``//!``), a block comment
    that follows code on its line, or the top of the file.

    Returns the two line numbers, 1-based. The lines stepped over lie outside
    the run from opener to closer, so a blank line, a plain comment or a
    conditional line added or removed there changes no hash. The Implementation
    search, :func:`find_comment`, is narrower and stays as it is.

    :implements: SEG-SREQ-166
    :implements: SEG-SREQ-283
    """
    if not 1 <= located <= len(lines):
        raise ExtractorError(f"line {located} is not inside a file of {len(lines)} lines")
    line = located - 1
    while line >= 1:
        text = lines[line - 1]
        if not text.strip() or _CONDITIONAL_LINE.match(text):
            line -= 1
            continue
        if not text.rstrip().endswith(b"*/"):
            break
        opener = _opener_line(lines, line)
        if _documents(lines[opener - 1]):
            return opener, line
        opening = lines[opener - 1]
        if opening[: opening.index(b"/*")].strip():
            break
        line = opener - 1
    raise ExtractorError(
        f"no documentation comment above line {located}, past blank lines, "
        "plain comments and conditional lines"
    )


def _opener_line(lines: Sequence[bytes], closer: int) -> int:
    """The nearest line at or above ``closer`` that holds a comment opener."""
    opener = closer
    while opener >= 1 and b"/*" not in lines[opener - 1]:
        opener -= 1
    if opener < 1:
        raise ExtractorError(f"the comment closing on line {closer} has no opener")
    return opener


def _documents(opening: bytes) -> bool:
    """Whether the comment opened on this line is a documentation comment.

    It must start with ``/**`` or ``/*!``; ``/**/`` and ``/***`` are plain.
    """
    start = opening.index(b"/*")
    token = opening[start : start + 4]
    return token[:3] in (b"/**", b"/*!") and token not in (b"/**/", b"/***")


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
    placement: Placement
    prefix: str | None
    path_root: str | None
    module_field: str | None


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


def _inside_repository(path: str, prefix: str | None, root: str | None = None) -> str:
    """The path inside the repository: the Doxygen path, prefix removed, root in front.

    The prefix is removed first, and then ``root`` is put in front of what is
    left, with one separator between them whether or not ``root`` ends with
    one. An empty or absent root puts nothing in front. The joined path is not
    normalised: a root that is absolute or leads out of the repository gives a
    path that the later resolution refuses, naming the node.

    The prefix is text and is removed as written. A path that does not begin
    with it is an error, so a path is never read as it stands when a prefix says
    where Doxygen's paths come from. A remainder that is empty or begins with a
    separator is an error too: it is no path inside the repository, and it would
    read as the root of the file system or as the repository itself.

    :implements: SEG-SREQ-279
    :implements: SEG-SREQ-280
    :implements: SEG-SREQ-342
    :implements: SEG-SREQ-349
    """
    rest = _after_prefix(path, prefix)
    return f"{root.rstrip('/')}/{rest}" if root else rest


def _after_prefix(path: str, prefix: str | None) -> str:
    """The Doxygen path with the prefix removed, or an error for a path it does not fit."""
    if not prefix:
        return path
    if not path.startswith(prefix):
        raise ExtractorError(f"the path {path!r} does not begin with the prefix {prefix!r}")
    rest = path[len(prefix) :]
    if not rest:
        raise ExtractorError(f"the path {path!r} is the whole prefix {prefix!r}; nothing is left")
    if rest.startswith("/"):
        raise ExtractorError(
            f"the path {path!r} has a remainder that begins with a separator "
            f"after the prefix {prefix!r}"
        )
    return rest


def _lies_within(
    member: _Member, prefix: str | None, directory: PurePosixPath, root: str | None = None
) -> bool:
    """Whether the member's file, inside the repository, lies within ``directory``.

    A file that does not begin with the prefix lies within no directory. A file
    whose remainder after the prefix is no relative path is an error, as it is
    when the file is read.
    """
    named = member.location.get("file")
    if named is None or (prefix and not named.startswith(prefix)):
        return False
    return PurePosixPath(_inside_repository(named, prefix, root)).is_relative_to(directory)


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
    return find_test_comment(lines, located)


@dataclass(frozen=True, slots=True)
class CSourceExtractor:
    """Implementation and TestSpecification records for C, from exports and located source.

    ``root`` is the directory the source files are read from, ``repository`` the
    configured name of the repository they belong to (a name, never a path);
    together they are the default place of a stream that has none of its own.
    ``implementation_placement`` and ``specification_placement`` give a stream
    its own repository and root. ``implementations`` and ``specifications`` each
    name a need export and the Doxygen output that locates its symbols; a stream
    that is ``None`` supplies nothing. Identity and edges come from the exports;
    content comes from the lines the Doxygen output locates in the files under
    the stream's root.

    The exports and the Doxygen trees are read and checked once, here; no source
    file is opened until :meth:`nodes` needs it.

    :implements: SEG-SREQ-152
    """

    root: Path | None = None
    _: KW_ONLY
    repository: str | None = None
    implementations: config.ImplementationInputs | None
    specifications: config.SpecificationInputs | None
    implementation_placement: Placement | None = None
    specification_placement: Placement | None = None
    _streams: tuple[_Stream, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Read and check every configured stream, refusing an export that carries a timestamp.

        :implements: SEG-SREQ-158
        :implements: SEG-SREQ-373
        """
        self._check_repositories()
        streams = []
        if self.implementations is not None:
            streams.append(
                self._read_stream(
                    self.implementations,
                    self._placement(self.implementation_placement, "implementations"),
                    kind=_IMPLEMENTATION,
                    label="implementation",
                    symbol_field="title",
                    hash_names=("apiHash", "bodyHash"),
                    link_field="satisfies",
                    edge_kind=_IMPLEMENTS,
                    module_field=None,
                )
            )
        if self.specifications is not None:
            streams.append(
                self._read_stream(
                    self.specifications,
                    self._placement(self.specification_placement, "specifications"),
                    kind=_TEST_SPECIFICATION,
                    label="test-case",
                    symbol_field="test_function",
                    hash_names=("specHash", "implHash"),
                    link_field="verifies",
                    edge_kind=_VERIFIES,
                    module_field="test_module",
                )
            )
        object.__setattr__(self, "_streams", tuple(streams))

    def _check_repositories(self) -> None:
        """Refuse each repository path of a configured stream that is not a directory.

        A repository is named once, whatever number of streams read through it.
        The error starts with a line that counts the repositories, and one line
        for each follows, sorted by the configured name, so the same
        configuration always gives the same text. The line holds the configured
        name and the path, and says whether the path does not exist or is not a
        directory. A plain directory with the files is valid. The requirements
        reader opens no file here, so its repository is not checked. The refusal
        comes before any stream is read, so no need is named for this cause.

        :implements: SEG-SREQ-373
        """
        placed = []
        if self.implementations is not None:
            placed.append(self._placement(self.implementation_placement, "implementations"))
        if self.specifications is not None:
            placed.append(self._placement(self.specification_placement, "specifications"))
        faults: dict[str, str] = {}
        for placement in placed:
            if placement.repository in faults:
                continue
            if not placement.root.exists():
                reason = "the path does not exist"
            elif not placement.root.is_dir():
                reason = "the path is not a directory"
            else:
                continue
            faults[placement.repository] = (
                f"repository {placement.repository!r} at {placement.root}: {reason}"
            )
        if faults:
            raise ExtractorError(
                _exports.itemized(
                    f"{len(faults)} repository path(s) cannot be used",
                    [faults[name] for name in sorted(faults)],
                )
            )

    def _placement(self, own: Placement | None, block: str) -> Placement:
        """The stream's own place, else the default place, else a refusal."""
        if own is not None:
            return own
        if self.root is None or self.repository is None:
            raise ExtractorError(f"the {block} stream has no repository and no default is given")
        return Placement(self.repository, self.root)

    @staticmethod
    def _read_stream(
        inputs: config.ImplementationInputs | config.SpecificationInputs,
        placement: Placement,
        *,
        kind: str,
        label: str,
        symbol_field: str,
        hash_names: tuple[str, str],
        link_field: str,
        edge_kind: str,
        module_field: str | None,
    ) -> _Stream:
        """One stream: the export's needs of the configured types, checked, and the tree indexed.

        A need whose type is not one of the configured types is dropped before
        any check, so it can neither supply a record nor be refused. Without
        configured types every need is read.

        :implements: SEG-SREQ-153
        :implements: SEG-SREQ-275
        :implements: SEG-SREQ-276
        :implements: SEG-SREQ-277
        """
        export = inputs.export
        every = _exports.read_needs(export, f"{label} export", ExtractorError)
        needs = {
            key: need
            for key, need in every.items()
            if inputs.types is None or need.get("type") in inputs.types
        }
        _exports.check_needs(
            export,
            f"{label} export",
            ExtractorError,
            needs,
            ("id", symbol_field),
            link_field,
            lambda key, need: (
                f"need {key!r} has an empty symbol" if not need[symbol_field] else None
            ),
        )
        return _Stream(
            kind=kind,
            label=label,
            export=export,
            needs=needs,
            members=_index_members(inputs.doxygen, label),
            symbol_field=symbol_field,
            hash_names=hash_names,
            link_field=link_field,
            edge_kind=edge_kind,
            placement=placement,
            prefix=inputs.doxygen_prefix,
            path_root=inputs.path_root,
            module_field=module_field,
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
        second call reads again. A node that fails is not skipped and does not
        stop the pass: every node is tried, the records of the good ones are
        given as they are reached, and at the end of the stream one
        :class:`UnsuppliedNodesError` names every node that failed. A consumer
        must therefore take the whole stream before it writes, and the stream is
        never silently short.

        :implements: SEG-SREQ-170
        :implements: SEG-SREQ-282
        """
        files: dict[Path, list[bytes]] = {}
        failures: list[NodeFailure] = []
        for stream in self._streams:
            for need in stream.needs.values():
                need_id = self._identifier(need)
                symbol = need[stream.symbol_field]
                try:
                    node = self._node(stream, need, need_id, symbol, files)
                except ExtractorError as error:
                    failures.append(
                        NodeFailure(stream.label, need_id, symbol, " ".join(str(error).split()))
                    )
                else:
                    yield node
        if failures:
            raise UnsuppliedNodesError(failures)

    def _locate(self, stream: _Stream, need: Mapping[str, Any], symbol: str) -> _Member:
        """The one Doxygen member whose name is the symbol.

        Where several members share the name and the need names a test module,
        the members whose file lies within the module's directory are the
        candidates. The path compared is the one inside the repository, with the
        prefix removed, and containment is by whole path components, so
        ``tests/a`` does not contain ``tests/ab``. After that choice, anything
        but exactly one member is an error.

        :implements: SEG-SREQ-159
        :implements: SEG-SREQ-160
        :implements: SEG-SREQ-161
        :implements: SEG-SREQ-278
        :implements: SEG-SREQ-343
        :implements: SEG-SREQ-344
        """
        module = need.get(stream.module_field) if stream.module_field else None
        if module is not None and not isinstance(module, str):
            raise ExtractorError(f"the test module is {module!r}, which is neither null nor text")
        found = list(stream.members.get(symbol, {}).values())
        if not found:
            raise ExtractorError("no member of the Doxygen output has this name")
        if len(found) > 1 and module:
            directory = PurePosixPath(module)
            candidates = [
                m for m in found if _lies_within(m, stream.prefix, directory, stream.path_root)
            ]
            if len(candidates) != 1:
                raise ExtractorError(
                    f"the Doxygen output defines {len(found)} members with this name, "
                    f"and {len(candidates)} of them lie within the test module {module!r}"
                )
            return candidates[0]
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

    def content(self, local_id: str, hash_name: str) -> bytes | None:
        """The bytes of the span that one hash of one node covers.

        :implements: SEG-SREQ-311

        The same span :meth:`nodes` hashed. It is located in the Doxygen index that
        the extractor holds since it was constructed. Then it is cut from the
        source files as they are now. Each call reads the source files that the
        node's two spans need (at most three) and keeps nothing, so a call is as
        current as the files. The answer is ``None`` for an unknown identifier
        and for a name that is not one of the stream's two hashes. A node that
        cannot be located or cut raises :class:`UnsuppliedNodesError`. It holds
        the one failure and its reason, as :meth:`nodes` does for the whole pass.
        """
        for stream in self._streams:
            need = stream.needs.get(local_id)
            if need is None:
                continue
            if hash_name not in stream.hash_names:
                return None
            symbol = need[stream.symbol_field]
            try:
                return self._spans(stream, need, symbol, {})[hash_name][1]
            except ExtractorError as error:
                failure = NodeFailure(stream.label, local_id, symbol, " ".join(str(error).split()))
                raise UnsuppliedNodesError([failure]) from error
        return None

    def _node(
        self,
        stream: _Stream,
        need: Mapping[str, Any],
        need_id: str,
        symbol: str,
        files: dict[Path, list[bytes]],
    ) -> NodeRecord:
        """The record of one need: its spans, hashed and anchored."""
        return NodeRecord(
            local_id=need_id,
            kind=stream.kind,
            content_anchors=self._anchors(stream, symbol, self._spans(stream, need, symbol, files)),
        )

    def _spans(
        self,
        stream: _Stream,
        need: Mapping[str, Any],
        symbol: str,
        files: dict[Path, list[bytes]],
    ) -> dict[str, tuple[str, bytes]]:
        """The two spans of one need, by hash name: locate, resolve, check, cut.

        Each value is the path inside the repository that the span was read from,
        and its bytes. Both :meth:`nodes` and :meth:`content` read through this
        one function, so a hash and the bytes behind it cannot come from two rules.
        """
        member = self._locate(stream, need, symbol)
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
        inside = {
            name: _inside_repository(location[name], stream.prefix, stream.path_root)
            for name in paths
        }
        resolved = {name: _resolve(stream.placement.root, inside[name]) for name in paths}
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
        return {
            api_name: (inside[api_path], span(api_lines, api_first, api_last)),
            body_name: (inside["bodyfile"], span(body_lines, body_first, body_last)),
        }

    @staticmethod
    def _anchors(
        stream: _Stream, symbol: str, spans: Mapping[str, tuple[str, bytes]]
    ) -> dict[str, ContentAnchor]:
        """Each named hash, anchored at the file its span was read from.

        The repository is the configured name of the stream's repository; the
        path is the file's path inside that repository, as Doxygen names it with
        the prefix removed; the locator names the symbol and the hash, never a line.

        :implements: SEG-SREQ-171
        :implements: SEG-SREQ-172
        :implements: SEG-SREQ-173
        :implements: SEG-SREQ-174
        :implements: SEG-SREQ-134
        :implements: SEG-SREQ-281
        """
        return {
            name: ContentAnchor(
                digest=content_hash(data),
                repository=stream.placement.repository,
                path=path,
                locator=f"symbol:{symbol}#{_LOCATOR_SUFFIX[name]}",
            )
            for name, (path, data) in spans.items()
        }
