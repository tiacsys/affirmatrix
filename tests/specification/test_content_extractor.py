"""Verification suite for the content extractor over C located by Doxygen.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests read the frozen evidence fixture under ``tests/fixtures/toolbox_evidence/``:
two need exports, two Doxygen XML trees and the three located sources. An
expected digest is computed in the test as the SHA-256 of a run of whole lines
of a fixture source, ``b"".join(lines[first - 1:last])`` over
``read_bytes().splitlines(keepends=True)``, and never by calling the extractor.
The last line of a span, or both lines, come from the ``<location>`` of the
Doxygen member the test reads itself; where the XML does not give a boundary (the
opening of a documentation comment, the semicolon ending a declaration) the
line comes from the worked examples of ADR-0011 and the test checks it against
the location it does have. Every variant of an input is built in the test, in a
temporary directory, by copying the whole fixture tree (the test cannot know
which of its files the extractor opens) and editing the copy. The extractor is
imported inside the helper that builds it, so an extractor that does not exist
yet is an expected failure of the test, not of the collection.

An error for one node surfaces while the node stream is consumed and is raised,
never skipped, so the stream is never short; a consumer may rely on that only
because the drift derivation consumes both record streams completely before it
writes anything.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config
from affirmatrix.records import LinkState

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "toolbox_evidence"
IMPLEMENTATION_EXPORT = FIXTURE / "needs" / "api-traceability" / "needs.json"
SPECIFICATION_EXPORT = FIXTURE / "needs" / "test-specification" / "needs.json"
IMPLEMENTATION_XML = FIXTURE / "xml" / "dox-safe-data-api"
SPECIFICATION_XML = FIXTURE / "xml" / "dox-safe-data-testspec"
SOURCES = FIXTURE / "sources"
HEADER = "include/safe_data/safe_data.h"
BODY_FILE = "src/safe_data.c"
TEST_FILE = "tests/safe_data/src/main.c"
REPOSITORY = "toolbox"
INIT = "IMPL-safe_data_init"
INIT_AND_VERIFY = "TC_SAFE_DATA_INIT_AND_VERIFY"

Inputs = tuple[Path, Path]


def _version_needs(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (version,) = document["versions"].values()
    return version["needs"]


def _needs(export: Path) -> dict[str, dict[str, Any]]:
    return _version_needs(json.loads(export.read_text(encoding="utf-8")))


def _symbols(export: Path, field: str) -> dict[str, str]:
    """The symbol each need of an export names, by need identifier."""
    return {need_id: need[field] for need_id, need in _needs(export).items()}


def _extractor(
    root: Path = SOURCES,
    *,
    implementations: Inputs | None = (IMPLEMENTATION_EXPORT, IMPLEMENTATION_XML),
    specifications: Inputs | None = (SPECIFICATION_EXPORT, SPECIFICATION_XML),
):
    """A content extractor over the fixture; ``None`` drops a stream."""
    from affirmatrix.sources.content import CSourceExtractor

    return CSourceExtractor(
        root,
        repository=REPOSITORY,
        implementations=(
            None
            if implementations is None
            else config.ImplementationInputs(export=implementations[0], doxygen=implementations[1])
        ),
        specifications=(
            None
            if specifications is None
            else config.SpecificationInputs(export=specifications[0], doxygen=specifications[1])
        ),
    )


def _nodes(**inputs: Any) -> dict[str, Any]:
    """Construct, then drain ``nodes()``; keyed by local identifier.

    One call, so that ``pytest.raises`` around it does not depend on whether an
    error surfaces at construction or while the stream runs.
    """
    return {node.local_id: node for node in _extractor(**inputs).nodes()}


def _edges(**inputs: Any) -> list[Any]:
    return list(_extractor(**inputs).edges())


def _error() -> type[Exception]:
    from affirmatrix.sources.content import ExtractorError

    return ExtractorError


def _refused(need_id: str, **inputs: Any) -> None:
    with pytest.raises(_error(), match=re.escape(need_id)):
        _nodes(**inputs)


def _members(doxygen: Path, symbol: str) -> list[ET.Element]:
    return [
        member
        for path in sorted(doxygen.glob("*.xml"))
        for member in ET.parse(path).getroot().iter("memberdef")
        if member.findtext("name") == symbol
    ]


def _location(doxygen: Path, symbol: str) -> dict[str, str]:
    """The ``<location>`` attributes of the one member named ``symbol``."""
    (member,) = _members(doxygen, symbol)
    location = member.find("location")
    assert location is not None
    return dict(location.attrib)


def _lines(root: Path, path: str, first: int, last: int) -> bytes:
    lines = (root / path).read_bytes().splitlines(keepends=True)
    return b"".join(lines[first - 1 : last])


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _anchor(nodes: Mapping[str, Any], need_id: str, name: str):
    return nodes[need_id].content_anchors[name]


def _hashes(nodes: Mapping[str, Any]) -> dict[str, dict[str, bytes]]:
    return {
        need_id: {name: anchor.digest for name, anchor in node.content_anchors.items()}
        for need_id, node in nodes.items()
    }


def _export_variant(
    tmp_path: Path, export: Path, edit: Callable[[dict[str, Any]], None], name: str = "needs"
) -> Path:
    """The export with ``edit`` applied to its document, written under ``tmp_path``."""
    document = json.loads(export.read_text(encoding="utf-8"))
    edit(document)
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _sources_variant(
    tmp_path: Path, edits: Mapping[str, Callable[[bytes], bytes]], name: str = "root"
) -> Path:
    """A copy of the fixture sources with each named file rewritten through its edit."""
    root = tmp_path / name
    shutil.copytree(SOURCES, root)
    for relative, edit in edits.items():
        target = root / relative
        target.write_bytes(edit(target.read_bytes()))
    return root


def _line_edit(number: int, old: bytes, new: bytes) -> Callable[[bytes], bytes]:
    """An edit replacing ``old`` by ``new`` in line ``number``, every other byte kept."""

    def edit(data: bytes) -> bytes:
        lines = data.splitlines(keepends=True)
        assert old in lines[number - 1]
        lines[number - 1] = lines[number - 1].replace(old, new)
        return b"".join(lines)

    return edit


def _blanked(first: int, last: int) -> Callable[[bytes], bytes]:
    """An edit blanking lines ``first`` to ``last``, every line number kept."""

    def edit(data: bytes) -> bytes:
        lines = data.splitlines(keepends=True)
        lines[first - 1 : last] = [b"\n"] * (last - first + 1)
        return b"".join(lines)

    return edit


def _xml_block(copy: Path, symbol: str) -> tuple[Path, str, re.Match[str]]:
    """The file of a copied tree, its text and the one ``<memberdef>`` block named ``symbol``."""
    found = []
    for path in sorted(copy.glob("*.xml")):
        text = path.read_text(encoding="utf-8")
        for block in re.finditer(r"<memberdef\b.*?</memberdef>", text, re.DOTALL):
            if f"<name>{symbol}</name>" in block.group(0):
                found.append((path, text, block))
    assert len(found) == 1
    return found[0]


def _relocated(
    tmp_path: Path, doxygen: Path, symbol: str, name: str = "dox", **attributes: str
) -> Path:
    """A copy of the tree in which the location of ``symbol``'s member has the given attributes."""
    copy = tmp_path / name
    shutil.copytree(doxygen, copy)
    path, text, block = _xml_block(copy, symbol)
    tag = re.search(r"<location [^>]*/>", block.group(0))
    assert tag is not None
    new_tag = tag.group(0)
    for key, value in attributes.items():
        new_tag, count = re.subn(rf'(?<=\s){key}="[^"]*"', f'{key}="{value}"', new_tag)
        assert count == 1
    block_text = block.group(0).replace(tag.group(0), new_tag)
    path.write_text(text[: block.start()] + block_text + text[block.end() :], encoding="utf-8")
    return copy


def _duplicated(tmp_path: Path, doxygen: Path, symbol: str, name: str = "dox") -> Path:
    """A copy of the tree in which ``symbol``'s member is defined twice.

    The definition is repeated under a new id in its file, and its listing in the
    index is repeated with the new id, so the copy holds a duplicate whether the
    extractor follows the index or scans the compounds.
    """
    copy = tmp_path / name
    shutil.copytree(doxygen, copy)
    path, text, block = _xml_block(copy, symbol)
    old_id = re.search(r'<memberdef\b[^>]*\bid="([^"]+)"', block.group(0))
    assert old_id is not None
    new_id = old_id.group(1) + "_second"
    clone = block.group(0).replace(f'id="{old_id.group(1)}"', f'id="{new_id}"', 1)
    path.write_text(text[: block.end()] + "\n" + clone + text[block.end() :], encoding="utf-8")
    index = copy / "index.xml"
    listed = index.read_text(encoding="utf-8")
    listing = re.search(
        rf'<member refid="{re.escape(old_id.group(1))}" kind="[^"]+">'
        rf"<name>{symbol}</name></member>",
        listed,
    )
    assert listing is not None
    line = listing.group(0)
    twin = line.replace(old_id.group(1), new_id)
    index.write_text(listed.replace(line, line + twin, 1), encoding="utf-8")
    return copy


def _reworded(tmp_path: Path, doxygen: Path, name: str) -> Path:
    """A copy of the tree in which the text of every description element is one word."""
    copy = tmp_path / name
    shutil.copytree(doxygen, copy)
    for path in copy.glob("*.xml"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r"<(briefdescription|detaileddescription|inbodydescription)>.*?</\1>",
            r"<\1><para>reworded</para></\1>",
            text,
            flags=re.DOTALL,
        )
        path.write_text(text, encoding="utf-8")
    return copy


def _opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the real path of every file opened through ``open`` or ``io.open``."""
    opened: list[str] = []
    real = builtins.open

    def spy(file: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(file, str | bytes | os.PathLike):
            opened.append(os.path.realpath(file))
        return real(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    return opened


def _configured(tmp_path: Path) -> config.ProducerConfig:
    path = tmp_path / "repo" / "affirmatrix.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "producer:\n"
        "  repository: sample-repo\n"
        "  specifications:\n"
        "    export: needs/test-specification/needs.json\n"
        "    doxygen: xml/dox-testspec\n"
        "  implementations:\n"
        "    export: needs/api-traceability/needs.json\n"
        "    doxygen: xml/dox-api\n",
        encoding="utf-8",
    )
    producer = config.load(path).producer
    assert producer is not None
    return producer


def _renamed(old: str, new: str) -> Callable[[dict[str, Any]], None]:
    def edit(document: dict[str, Any]) -> None:
        needs = _version_needs(document)
        need = needs.pop(old)
        need["id"] = new
        needs[new] = need

    return edit


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-154: the content extractor is not built yet")
def test_an_implementation_is_identified_by_its_need_identifier_verbatim(tmp_path: Path) -> None:
    """An Implementation is identified by its implementation need's identifier, verbatim.

    Extracting from the fixture supplies exactly 12 Implementation records whose
    local identifiers equal, byte for byte, the ids of the implementation
    export's needs, among them IMPL-safe_data_init and IMPL-SAFE_CONTAINER_DEFINE.
    In a copy of the export where the need IMPL-safe_data_init is renamed
    ZZ-init-1 and names the same symbol, the records carry ZZ-init-1 and no
    identifier derived from the symbol.

    :verifies: SEG-SREQ-154
    :test-id: SEG-TS-022
    """
    needs = _needs(IMPLEMENTATION_EXPORT)
    ids = [i.encode("utf-8") for i, n in _nodes().items() if n.kind == "Implementation"]
    assert len(ids) == 12
    assert sorted(ids) == sorted(i.encode("utf-8") for i in needs)
    assert b"IMPL-safe_data_init" in ids
    assert b"IMPL-SAFE_CONTAINER_DEFINE" in ids

    variant = _export_variant(tmp_path, IMPLEMENTATION_EXPORT, _renamed(INIT, "ZZ-init-1"))
    renamed = _nodes(implementations=(variant, IMPLEMENTATION_XML), specifications=None)
    assert set(renamed) == (set(needs) - {INIT}) | {"ZZ-init-1"}


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-155: the content extractor is not built yet")
def test_a_test_specification_is_identified_by_its_need_identifier_verbatim(
    tmp_path: Path,
) -> None:
    """A TestSpecification is identified by its test-case need's identifier, verbatim.

    Extracting from the fixture supplies exactly 19 TestSpecification records
    whose local identifiers equal, byte for byte, the ids of the test-case
    export's needs, among them TC_SAFE_DATA_INIT_AND_VERIFY. In a copy of the
    export where that need is renamed TC-renamed-1 and names the same test
    function, the records carry TC-renamed-1 and no identifier derived from the
    function's name.

    :verifies: SEG-SREQ-155
    :test-id: SEG-TS-023
    """
    needs = _needs(SPECIFICATION_EXPORT)
    ids = [i.encode("utf-8") for i, n in _nodes().items() if n.kind == "TestSpecification"]
    assert len(ids) == 19
    assert sorted(ids) == sorted(i.encode("utf-8") for i in needs)
    assert b"TC_SAFE_DATA_INIT_AND_VERIFY" in ids

    variant = _export_variant(
        tmp_path, SPECIFICATION_EXPORT, _renamed(INIT_AND_VERIFY, "TC-renamed-1")
    )
    renamed = _nodes(implementations=None, specifications=(variant, SPECIFICATION_XML))
    assert set(renamed) == (set(needs) - {INIT_AND_VERIFY}) | {"TC-renamed-1"}


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-156: the content extractor is not built yet")
def test_implements_edges_come_from_satisfies_links(tmp_path: Path) -> None:
    """Implements edges come from the implementation needs' satisfies links.

    Extracting from the fixture supplies exactly the 16 (implementation need,
    requirement) pairs the export's needs declare in satisfies, among them
    (IMPL-safe_data_update, SD-REQ-008), each an edge of kind Implements in the
    pending state, running from the implementation to the requirement. In a copy
    of the header whose @satisfies tag in the comment of safe_data_init names
    SD-REQ-999, and with a root holding no source at all, the edge set is
    unchanged.

    :verifies: SEG-SREQ-156
    :test-id: SEG-TS-024
    """
    needs = _needs(IMPLEMENTATION_EXPORT)
    declared = {(k, r) for k, need in needs.items() for r in need["satisfies"]}
    assert len(declared) == 16
    assert ("IMPL-safe_data_update", "SD-REQ-008") in declared

    edges = _edges(specifications=None)
    assert {(e.from_id, e.to_id) for e in edges} == declared
    assert len(edges) == 16
    assert all(e.kind == "Implements" and e.state == LinkState.PENDING for e in edges)

    retagged = _sources_variant(tmp_path, {HEADER: _line_edit(260, b"SD-REQ-001", b"SD-REQ-999")})
    assert {(e.from_id, e.to_id) for e in _edges(root=retagged, specifications=None)} == declared
    empty = tmp_path / "empty"
    empty.mkdir()
    assert {(e.from_id, e.to_id) for e in _edges(root=empty, specifications=None)} == declared


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-157: the content extractor is not built yet")
def test_verifies_edges_come_from_verifies_links(tmp_path: Path) -> None:
    """Verifies edges come from the test-case needs' verifies links.

    Extracting from the fixture supplies exactly the 24 (test-case need,
    requirement) pairs the export's needs declare in verifies, among them
    (TC_SAFE_DATA_INIT_AND_VERIFY, SD-REQ-003), each an edge of kind Verifies in
    the pending state, running from the test specification to the requirement. In
    a copy of the test source whose @verifies tag in the comment of
    test_init_and_verify names SD-REQ-999, the edge set is unchanged.

    :verifies: SEG-SREQ-157
    :test-id: SEG-TS-025
    """
    needs = _needs(SPECIFICATION_EXPORT)
    declared = {(k, r) for k, need in needs.items() for r in need["verifies"]}
    assert len(declared) == 24
    assert (INIT_AND_VERIFY, "SD-REQ-003") in declared

    edges = _edges(implementations=None)
    assert {(e.from_id, e.to_id) for e in edges} == declared
    assert len(edges) == 24
    assert all(e.kind == "Verifies" and e.state == LinkState.PENDING for e in edges)

    retagged = _sources_variant(tmp_path, {TEST_FILE: _line_edit(40, b"SD-REQ-001", b"SD-REQ-999")})
    assert {(e.from_id, e.to_id) for e in _edges(root=retagged, implementations=None)} == declared


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-158: the content extractor is not built yet")
def test_a_need_export_carrying_a_build_timestamp_is_refused_by_the_extractor(
    tmp_path: Path,
) -> None:
    """A need export carrying a build timestamp is refused.

    Constructing the extractor over a copy of the implementation export that adds
    a created stamp to its version entry, and separately over a copy of the
    test-case export that adds it at the top level, raises the extractor's error
    before any record is supplied; constructing it over the exports as frozen,
    whose every timestamp field is null, does not.

    :verifies: SEG-SREQ-158
    :test-id: SEG-TS-026
    """

    def stamp_version(document: dict[str, Any]) -> None:
        (version,) = document["versions"].values()
        version["created"] = "2026-09-29T10:00:00"

    def stamp_top(document: dict[str, Any]) -> None:
        document["created"] = "2026-09-29T10:00:00"

    _extractor()
    stamped_impl = _export_variant(tmp_path, IMPLEMENTATION_EXPORT, stamp_version, "impl")
    stamped_spec = _export_variant(tmp_path, SPECIFICATION_EXPORT, stamp_top, "spec")
    with pytest.raises(_error()):
        _extractor(implementations=(stamped_impl, IMPLEMENTATION_XML), specifications=None)
    with pytest.raises(_error()):
        _extractor(implementations=None, specifications=(stamped_spec, SPECIFICATION_XML))


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-160: the content extractor is not built yet")
def test_a_node_is_located_through_the_member_its_symbol_names(tmp_path: Path) -> None:
    """A node is located through the Doxygen member whose name is its symbol.

    For each of the 12 implementations the bodyHash equals the SHA-256 of the run
    of lines that the location of the member named by its symbol gives (bodyfile,
    bodystart to bodyend, read by the test from the Doxygen output), and for each
    of the 19 test specifications the implHash equals the same for its test
    function; the 12 bodyHash digests are pairwise distinct. In a copy of the
    Doxygen output where only the bodyend of safe_data_init is one line smaller,
    the bodyHash of IMPL-safe_data_init is the digest of that shorter run and the
    other eleven are unchanged.

    :verifies: SEG-SREQ-160
    :test-id: SEG-TS-027
    """

    def run(xml: Path, symbol: str) -> bytes:
        where = _location(xml, symbol)
        first, last = int(where["bodystart"]), int(where["bodyend"])
        return _digest(_lines(SOURCES, where["bodyfile"], first, last))

    nodes = _nodes()
    implementations = _symbols(IMPLEMENTATION_EXPORT, "title")
    for need_id, symbol in implementations.items():
        assert _anchor(nodes, need_id, "bodyHash").digest == run(IMPLEMENTATION_XML, symbol)
    assert len({_anchor(nodes, i, "bodyHash").digest for i in implementations}) == 12
    for need_id, symbol in _symbols(SPECIFICATION_EXPORT, "test_function").items():
        assert _anchor(nodes, need_id, "implHash").digest == run(SPECIFICATION_XML, symbol)

    shorter = _relocated(tmp_path, IMPLEMENTATION_XML, "safe_data_init", bodyend="236")
    changed = _nodes(implementations=(IMPLEMENTATION_EXPORT, shorter), specifications=None)
    shorter_run = _digest(_lines(SOURCES, BODY_FILE, 224, 236))
    assert _anchor(changed, INIT, "bodyHash").digest == shorter_run
    for need_id in implementations.keys() - {INIT}:
        before = _anchor(nodes, need_id, "bodyHash").digest
        assert _anchor(changed, need_id, "bodyHash").digest == before


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-161: the content extractor is not built yet")
def test_an_unlocatable_or_ambiguous_symbol_is_an_error_for_its_node(tmp_path: Path) -> None:
    """An unlocatable or ambiguous symbol is an error for its node, not an omission.

    Extracting from a copy of the implementation export in which
    IMPL-safe_data_init names the symbol safe_data_absent, which no member of the
    Doxygen output carries, raises the extractor's error naming
    IMPL-safe_data_init; extracting from a copy of the Doxygen output in which a
    second member named safe_data_init is defined raises it likewise; extracting
    from the fixture as frozen supplies all 12 Implementation records.

    :verifies: SEG-SREQ-161
    :test-id: SEG-TS-028
    """

    def absent(document: dict[str, Any]) -> None:
        _version_needs(document)[INIT]["title"] = "safe_data_absent"

    variant = _export_variant(tmp_path, IMPLEMENTATION_EXPORT, absent)
    _refused(INIT, implementations=(variant, IMPLEMENTATION_XML), specifications=None)
    twice = _duplicated(tmp_path, IMPLEMENTATION_XML, "safe_data_init")
    _refused(INIT, implementations=(IMPLEMENTATION_EXPORT, twice), specifications=None)
    nodes = _nodes(specifications=None)
    assert len([n for n in nodes.values() if n.kind == "Implementation"]) == 12


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-162: the content extractor is not built yet")
def test_a_location_outside_the_root_is_an_error_and_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A location outside the root is an error, and the file outside is not read.

    With a readable file x.c beside the root, in a copy of the Doxygen output
    where the declaration file of safe_data_init is ../x.c, and separately in one
    where its body file is ../x.c, extracting raises the extractor's error naming
    IMPL-safe_data_init, and x.c is not opened.

    :verifies: SEG-SREQ-162
    :test-id: SEG-TS-029
    """
    root = _sources_variant(tmp_path, {})
    outside = tmp_path / "x.c"
    outside.write_bytes((SOURCES / HEADER).read_bytes())
    opened = _opened(monkeypatch)
    variants = {
        "declaration": {"file": "../x.c", "declfile": "../x.c"},
        "body": {"bodyfile": "../x.c"},
    }
    for name, attributes in variants.items():
        xml = _relocated(tmp_path, IMPLEMENTATION_XML, "safe_data_init", name, **attributes)
        _refused(INIT, root=root, implementations=(IMPLEMENTATION_EXPORT, xml), specifications=None)
    assert os.path.realpath(outside) not in opened


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-163: the content extractor is not built yet")
def test_an_apihash_covers_a_declaration_and_the_comment_above_it() -> None:
    """An Implementation's apiHash covers its declaration and the comment above it.

    The apiHash of IMPL-safe_data_init equals the SHA-256 of lines 247 to 263 of
    include/safe_data/safe_data.h: from the opening of its documentation comment
    through the line holding the semicolon that ends the declaration. That of
    IMPL-safe_data_commit equals the digest of lines 378 to 399, the guard line
    above the opening of its comment lying outside.

    :verifies: SEG-SREQ-163
    :test-id: SEG-TS-030
    """
    nodes = _nodes(specifications=None)
    assert int(_location(IMPLEMENTATION_XML, "safe_data_init")["declline"]) == 262
    assert _anchor(nodes, INIT, "apiHash").digest == _digest(_lines(SOURCES, HEADER, 247, 263))
    assert int(_location(IMPLEMENTATION_XML, "safe_data_commit")["declline"]) == 398
    assert _anchor(nodes, "IMPL-safe_data_commit", "apiHash").digest == _digest(
        _lines(SOURCES, HEADER, 378, 399)
    )


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-164: the content extractor is not built yet")
def test_a_macros_apihash_covers_its_definition_head_and_its_comment() -> None:
    """A macro's apiHash covers its definition head and the comment above it.

    The apiHash of IMPL-SAFE_CONTAINER_DEFINE equals the SHA-256 of lines 477 to
    498 of include/safe_data/safe_data.h, from the opening of its comment through
    the #define line, and that of IMPL-SAFE_SECTION equals the digest of lines 595
    to 633, the guard line between its comment and its #define lying inside.

    :verifies: SEG-SREQ-164
    :test-id: SEG-TS-031
    """
    nodes = _nodes(specifications=None)
    container = int(_location(IMPLEMENTATION_XML, "SAFE_CONTAINER_DEFINE")["line"])
    assert container == 498
    assert _anchor(nodes, "IMPL-SAFE_CONTAINER_DEFINE", "apiHash").digest == _digest(
        _lines(SOURCES, HEADER, 477, container)
    )
    section = int(_location(IMPLEMENTATION_XML, "SAFE_SECTION")["line"])
    assert section == 633
    span = _lines(SOURCES, HEADER, 595, section)
    assert b"#if defined(CONFIG_SAFE_DATA_GNU_EXTENSIONS)" in span
    assert _anchor(nodes, "IMPL-SAFE_SECTION", "apiHash").digest == _digest(span)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-165: the content extractor is not built yet")
def test_a_bodyhash_covers_the_located_body() -> None:
    """An Implementation's bodyHash covers the lines its body occupies in the source.

    The bodyHash of IMPL-safe_data_init equals the SHA-256 of lines 224 to 237 of
    src/safe_data.c, the run its member's location gives, and that of
    IMPL-SAFE_CONTAINER_DEFINE equals the digest of lines 498 to 506 of
    include/safe_data/safe_data.h.

    :verifies: SEG-SREQ-165
    :test-id: SEG-TS-032
    """
    nodes = _nodes(specifications=None)
    where = _location(IMPLEMENTATION_XML, "safe_data_init")
    assert (where["bodyfile"], where["bodystart"], where["bodyend"]) == (BODY_FILE, "224", "237")
    assert _anchor(nodes, INIT, "bodyHash").digest == _digest(_lines(SOURCES, BODY_FILE, 224, 237))
    where = _location(IMPLEMENTATION_XML, "SAFE_CONTAINER_DEFINE")
    assert (where["bodyfile"], where["bodystart"], where["bodyend"]) == (HEADER, "498", "506")
    assert _anchor(nodes, "IMPL-SAFE_CONTAINER_DEFINE", "bodyHash").digest == _digest(
        _lines(SOURCES, HEADER, 498, 506)
    )


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-166: the content extractor is not built yet")
def test_a_spechash_covers_the_tests_documentation_comment() -> None:
    """A TestSpecification's specHash covers the documentation comment above the test.

    The specHash of TC_SAFE_DATA_INIT_AND_VERIFY equals the SHA-256 of lines 33
    to 43 of tests/safe_data/src/main.c: the comment carrying its @testid,
    @verifies and @active tags, from its opening to its closing line, and not the
    ZTEST line that follows.

    :verifies: SEG-SREQ-166
    :test-id: SEG-TS-033
    """
    nodes = _nodes(implementations=None)
    assert int(_location(SPECIFICATION_XML, "test_init_and_verify")["line"]) == 43 + 1
    assert _anchor(nodes, INIT_AND_VERIFY, "specHash").digest == _digest(
        _lines(SOURCES, TEST_FILE, 33, 43)
    )


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-167: the content extractor is not built yet")
def test_an_implhash_covers_the_tests_located_body() -> None:
    """A TestSpecification's implHash covers the lines the test's body occupies.

    The implHash of TC_SAFE_DATA_INIT_AND_VERIFY equals the SHA-256 of lines 44
    to 48 of tests/safe_data/src/main.c, from the ZTEST line through the closing
    brace, the run its member's location gives.

    :verifies: SEG-SREQ-167
    :test-id: SEG-TS-034
    """
    nodes = _nodes(implementations=None)
    where = _location(SPECIFICATION_XML, "test_init_and_verify")
    assert (where["bodyfile"], where["bodystart"], where["bodyend"]) == (TEST_FILE, "44", "48")
    assert _anchor(nodes, INIT_AND_VERIFY, "implHash").digest == _digest(
        _lines(SOURCES, TEST_FILE, 44, 48)
    )


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-168: the content extractor is not built yet")
def test_spans_are_whole_lines_with_their_terminators(tmp_path: Path) -> None:
    """Every span is a run of whole lines, each with its terminator.

    The apiHash of IMPL-safe_data_init equals the SHA-256 of lines 247 to 263 of
    the header including the line feed that ends line 263, and equals neither the
    digest of that run without its final line feed nor that of the run starting
    one byte after its first line's start. In a copy of src/safe_data.c whose
    every line ends in CR LF, the bodyHash of IMPL-safe_data_init equals the
    digest of lines 224 to 237 with their CR LF terminators.

    :verifies: SEG-SREQ-168
    :test-id: SEG-TS-035
    """
    span = _lines(SOURCES, HEADER, 247, 263)
    assert span.endswith(b"\n")
    actual = _anchor(_nodes(specifications=None), INIT, "apiHash").digest
    assert actual == _digest(span)
    assert actual != _digest(span[:-1])
    assert actual != _digest(span[1:])

    root = _sources_variant(tmp_path, {BODY_FILE: lambda data: data.replace(b"\n", b"\r\n")})
    crlf = _lines(root, BODY_FILE, 224, 237)
    assert crlf.endswith(b"\r\n")
    nodes = _nodes(root=root, specifications=None)
    assert _anchor(nodes, INIT, "bodyHash").digest == _digest(crlf)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-169: the content extractor is not built yet")
def test_a_missing_documentation_comment_is_an_error_for_its_node(tmp_path: Path) -> None:
    """A missing documentation comment is an error for its node, never a hash over another comment.

    In a copy of the header where the lines of the comment above safe_data_init
    are blank, and separately in a copy of the test source where the lines of the
    comment above test_init_and_verify are blank, with every line number
    unchanged, extracting raises the extractor's error naming IMPL-safe_data_init
    and TC_SAFE_DATA_INIT_AND_VERIFY respectively.

    :verifies: SEG-SREQ-169
    :test-id: SEG-TS-036
    """
    header = _sources_variant(tmp_path, {HEADER: _blanked(247, 261)}, "blanked-header")
    _refused(INIT, root=header, specifications=None)
    tests = _sources_variant(tmp_path, {TEST_FILE: _blanked(33, 43)}, "blanked-test")
    _refused(INIT_AND_VERIFY, root=tests, implementations=None)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-170: the content extractor is not built yet")
def test_no_hashed_byte_comes_from_the_doxygen_output_text(tmp_path: Path) -> None:
    """No hashed byte comes from the Doxygen output's text.

    The apiHash of IMPL-safe_data_init, IMPL-SAFE_CONTAINER_DEFINE and
    IMPL-SAFE_SECTION and the specHash of TC_SAFE_DATA_INIT_AND_VERIFY each equal
    the SHA-256 of source lines and none equals the SHA-256 of the UTF-8 text of
    that member's brief description in the Doxygen output, raw or with its
    whitespace collapsed. In a copy of the Doxygen output where the text of every
    description element is replaced by one word, every hash of every record is
    unchanged.

    :verifies: SEG-SREQ-170
    :test-id: SEG-TS-037
    """
    nodes = _nodes()
    cases = [
        (INIT, "apiHash", IMPLEMENTATION_XML, "safe_data_init", HEADER, 247, 263),
        (
            "IMPL-SAFE_CONTAINER_DEFINE",
            "apiHash",
            IMPLEMENTATION_XML,
            "SAFE_CONTAINER_DEFINE",
            HEADER,
            477,
            498,
        ),
        ("IMPL-SAFE_SECTION", "apiHash", IMPLEMENTATION_XML, "SAFE_SECTION", HEADER, 595, 633),
        (INIT_AND_VERIFY, "specHash", SPECIFICATION_XML, "test_init_and_verify", TEST_FILE, 33, 43),
    ]
    for need_id, name, xml, symbol, path, first, last in cases:
        digest = _anchor(nodes, need_id, name).digest
        assert digest == _digest(_lines(SOURCES, path, first, last))
        (member,) = _members(xml, symbol)
        brief = member.find("briefdescription")
        assert brief is not None
        raw = "".join(brief.itertext())
        assert raw.strip()
        for text in (raw, raw.strip(), " ".join(raw.split())):
            assert digest != _digest(text.encode("utf-8"))

    reworded = _nodes(
        implementations=(IMPLEMENTATION_EXPORT, _reworded(tmp_path, IMPLEMENTATION_XML, "impl")),
        specifications=(SPECIFICATION_EXPORT, _reworded(tmp_path, SPECIFICATION_XML, "spec")),
    )
    assert _hashes(reworded) == _hashes(nodes)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-171: the content extractor is not built yet")
def test_an_implementations_api_anchor_names_the_declaration_file_and_symbol() -> None:
    """An Implementation's api anchor names the declaration file and the symbol.

    For each of the 12 implementations the apiHash anchor names the repository
    "toolbox", a name and not a path, the file holding the symbol's declaration
    as its member's location gives it (include/safe_data/safe_data.h for
    safe_data_init), and the locator symbol:<symbol>#api, for safe_data_init
    symbol:safe_data_init#api.

    :verifies: SEG-SREQ-171
    :test-id: SEG-TS-038
    """
    nodes = _nodes(specifications=None)
    for need_id, symbol in _symbols(IMPLEMENTATION_EXPORT, "title").items():
        where = _location(IMPLEMENTATION_XML, symbol)
        anchor = _anchor(nodes, need_id, "apiHash")
        assert anchor.repository == REPOSITORY
        assert anchor.path == where.get("declfile", where["file"])
        assert anchor.locator == f"symbol:{symbol}#api"
    init = _anchor(nodes, INIT, "apiHash")
    assert (init.path, init.locator) == (HEADER, "symbol:safe_data_init#api")


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-172: the content extractor is not built yet")
def test_an_implementations_body_anchor_names_the_body_file_and_symbol() -> None:
    """An Implementation's body anchor names the body file and the symbol.

    For each of the 12 implementations the bodyHash anchor names the file holding
    the symbol's body as its member's location gives it (src/safe_data.c for
    safe_data_init, include/safe_data/safe_data.h for the macro
    SAFE_CONTAINER_DEFINE) and the locator symbol:<symbol>#body.

    :verifies: SEG-SREQ-172
    :test-id: SEG-TS-039
    """
    nodes = _nodes(specifications=None)
    for need_id, symbol in _symbols(IMPLEMENTATION_EXPORT, "title").items():
        anchor = _anchor(nodes, need_id, "bodyHash")
        assert anchor.repository == REPOSITORY
        assert anchor.path == _location(IMPLEMENTATION_XML, symbol)["bodyfile"]
        assert anchor.locator == f"symbol:{symbol}#body"
    assert _anchor(nodes, INIT, "bodyHash").path == BODY_FILE
    assert _anchor(nodes, "IMPL-SAFE_CONTAINER_DEFINE", "bodyHash").path == HEADER


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-173: the content extractor is not built yet")
def test_a_test_specifications_spec_anchor_names_the_test_file_and_function() -> None:
    """A TestSpecification's spec anchor names the test file and the function.

    For each of the 19 test specifications the specHash anchor names the
    repository "toolbox", the file tests/safe_data/src/main.c, and the locator
    symbol:<function>#spec, for test_init_and_verify
    symbol:test_init_and_verify#spec.

    :verifies: SEG-SREQ-173
    :test-id: SEG-TS-040
    """
    nodes = _nodes(implementations=None)
    for need_id, symbol in _symbols(SPECIFICATION_EXPORT, "test_function").items():
        anchor = _anchor(nodes, need_id, "specHash")
        assert anchor.repository == REPOSITORY
        assert anchor.path == _location(SPECIFICATION_XML, symbol)["file"] == TEST_FILE
        assert anchor.locator == f"symbol:{symbol}#spec"
    assert _anchor(nodes, INIT_AND_VERIFY, "specHash").locator == "symbol:test_init_and_verify#spec"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-174: the content extractor is not built yet")
def test_a_test_specifications_impl_anchor_names_the_test_file_and_function() -> None:
    """A TestSpecification's impl anchor names the test file and the function.

    For each of the 19 test specifications the implHash anchor names the file
    tests/safe_data/src/main.c and the locator symbol:<function>#impl, for
    test_init_and_verify symbol:test_init_and_verify#impl.

    :verifies: SEG-SREQ-174
    :test-id: SEG-TS-041
    """
    nodes = _nodes(implementations=None)
    for need_id, symbol in _symbols(SPECIFICATION_EXPORT, "test_function").items():
        anchor = _anchor(nodes, need_id, "implHash")
        assert anchor.path == _location(SPECIFICATION_XML, symbol)["bodyfile"] == TEST_FILE
        assert anchor.locator == f"symbol:{symbol}#impl"
    assert _anchor(nodes, INIT_AND_VERIFY, "implHash").locator == "symbol:test_init_and_verify#impl"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-175: the content extractor is not built yet")
def test_a_location_that_does_not_name_its_symbol_is_an_error_for_its_node(
    tmp_path: Path,
) -> None:
    """A location whose source line lacks its symbol is an error for its node.

    In a copy of the Doxygen output where the declaration line of safe_data_init
    is that of safe_data_verify, and separately in one where its body start and
    end are those of safe_data_verify, extracting raises the extractor's error
    naming IMPL-safe_data_init, although each run of lines is well formed.

    :verifies: SEG-SREQ-175
    :test-id: SEG-TS-042
    """
    verify = _location(IMPLEMENTATION_XML, "safe_data_verify")
    declaration = _relocated(
        tmp_path,
        IMPLEMENTATION_XML,
        "safe_data_init",
        "declaration",
        line=verify["line"],
        declline=verify["declline"],
    )
    _refused(INIT, implementations=(IMPLEMENTATION_EXPORT, declaration), specifications=None)
    body = _relocated(
        tmp_path,
        IMPLEMENTATION_XML,
        "safe_data_init",
        "body",
        bodystart=verify["bodystart"],
        bodyend=verify["bodyend"],
    )
    _refused(INIT, implementations=(IMPLEMENTATION_EXPORT, body), specifications=None)


def test_the_specification_inputs_are_loaded_relative_to_the_file(tmp_path: Path) -> None:
    """The test-specification inputs are loaded, resolved against the file.

    Loading a configuration file in a subdirectory whose producer block names
    specifications with the export "needs/test-specification/needs.json" and the
    Doxygen output "xml/dox-testspec" yields specification inputs whose export and
    Doxygen output are that subdirectory joined with each relative path.

    :verifies: SEG-SREQ-195
    :test-id: SEG-TS-043
    """
    specifications = _configured(tmp_path).specifications
    assert specifications == config.SpecificationInputs(
        export=tmp_path / "repo" / "needs/test-specification/needs.json",
        doxygen=tmp_path / "repo" / "xml/dox-testspec",
    )


def test_the_implementation_inputs_are_loaded_relative_to_the_file(tmp_path: Path) -> None:
    """The implementation inputs are loaded, resolved against the file.

    Loading a configuration file in a subdirectory whose producer block names
    implementations with the export "needs/api-traceability/needs.json" and the
    Doxygen output "xml/dox-api" yields implementation inputs whose export and
    Doxygen output are that subdirectory joined with each relative path.

    :verifies: SEG-SREQ-196
    :test-id: SEG-TS-044
    """
    implementations = _configured(tmp_path).implementations
    assert implementations == config.ImplementationInputs(
        export=tmp_path / "repo" / "needs/api-traceability/needs.json",
        doxygen=tmp_path / "repo" / "xml/dox-api",
    )
