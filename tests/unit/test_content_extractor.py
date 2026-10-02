"""Developer tests for the content extractor's span rules, refusals and streams.

The acceptance tests read the frozen toolbox evidence fixture; these pin each
rule on literal lines or on a tree small enough to read in the test: one export,
one Doxygen compound and one or two source files written into a temporary
directory. The same-file function, which no member of the fixture exercises, is
pinned here.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config
from affirmatrix.sources.content import (
    CSourceExtractor,
    ExtractorError,
    declaration_end,
    find_comment,
    head_end,
    span,
    split_lines,
)
from affirmatrix.sources.reqs import ReaderError, RequirementsReader

NEED = "IMPL-DBL"


def _lines(text: str) -> list[bytes]:
    return split_lines(text.encode("utf-8"))


def _digest(lines: list[bytes], first: int, last: int) -> bytes:
    return hashlib.sha256(b"".join(lines[first - 1 : last])).digest()


# --- span and split_lines ---------------------------------------------------


def test_a_span_joins_whole_lines_with_their_line_feeds() -> None:
    assert span(_lines("a\nb\nc\nd\n"), 2, 3) == b"b\nc\n"


def test_a_span_keeps_crlf_terminators() -> None:
    assert span(split_lines(b"a\r\nb\r\nc\r\n"), 1, 2) == b"a\r\nb\r\n"


def test_a_span_ending_on_an_unterminated_last_line_adds_no_terminator() -> None:
    assert span(_lines("a\nb"), 1, 2) == b"a\nb"


def test_a_span_past_the_last_line_is_refused() -> None:
    with pytest.raises(ExtractorError):
        span(_lines("a\nb\n"), 2, 3)


def test_a_span_ending_before_it_starts_is_refused() -> None:
    with pytest.raises(ExtractorError):
        span(_lines("a\nb\nc\n"), 3, 2)


def test_a_span_starting_below_line_one_is_refused() -> None:
    with pytest.raises(ExtractorError):
        span(_lines("a\nb\n"), 0, 1)


def test_splitting_keeps_every_terminator_so_the_lines_rejoin_to_the_file() -> None:
    data = b"one\r\ntwo\n\nthree"
    assert b"".join(split_lines(data)) == data
    assert len(split_lines(data)) == 4


def test_a_lone_carriage_return_is_not_a_line_break() -> None:
    assert split_lines(b"a\rb\nc\n") == [b"a\rb\n", b"c\n"]


# --- find_comment -----------------------------------------------------------


def test_a_comment_closing_directly_above_the_line_is_found() -> None:
    lines = _lines("int x;\n/**\n * Doc.\n */\nint f(void);\n")
    assert find_comment(lines, 5) == (2, 4)


def test_a_guard_line_of_each_kind_is_stepped_over() -> None:
    for guard in ("#if A", "#ifdef A", "#ifndef A", "  #  if A"):
        lines = _lines(f"/** Doc. */\n{guard}\nint f(void);\n")
        assert find_comment(lines, 3) == (1, 1), guard


def test_two_guard_lines_are_stepped_over() -> None:
    lines = _lines("/** Doc. */\n#ifdef A\n#if B\nint f(void);\n")
    assert find_comment(lines, 4) == (1, 1)


def test_a_guard_line_above_the_opener_is_not_part_of_the_comment() -> None:
    lines = _lines("#if A\n/**\n * Doc.\n */\nint f(void);\n")
    assert find_comment(lines, 5) == (2, 4)


def test_a_blank_line_between_the_closer_and_the_line_ends_the_search() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("/** Doc. */\n\nint f(void);\n"), 3)


def test_a_blank_line_above_a_guard_line_ends_the_search() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("/** Doc. */\n\n#if A\nint f(void);\n"), 4)


def test_a_directive_that_is_not_a_guard_ends_the_search() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("/** Doc. */\n#endif\nint f(void);\n"), 3)


def test_a_plain_block_comment_is_not_a_documentation_comment() -> None:
    with pytest.raises(ExtractorError, match="not a documentation comment"):
        find_comment(_lines("/* Plain. */\nint f(void);\n"), 2)


def test_code_above_the_line_means_no_documentation_comment() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("int y;\nint f(void);\n"), 2)


def test_the_top_of_the_file_means_no_documentation_comment() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("int f(void);\n"), 1)


def test_a_bang_opener_is_a_documentation_comment() -> None:
    assert find_comment(_lines("/*!\n * Doc.\n */\nint f(void);\n"), 4) == (1, 3)


def test_slash_line_comments_are_not_documentation_comments() -> None:
    with pytest.raises(ExtractorError, match="no documentation comment"):
        find_comment(_lines("/// Doc.\n/// More.\nint f(void);\n"), 3)


def test_a_one_line_documentation_comment_is_its_own_opener_and_closer() -> None:
    assert find_comment(_lines("/** Doc. */\nint f(void);\n"), 2) == (1, 1)


def test_a_closer_with_trailing_whitespace_or_crlf_is_found() -> None:
    assert find_comment(split_lines(b"/**\r\n * Doc.\r\n */  \r\nint f(void);\r\n"), 4) == (1, 3)


def test_the_nearest_of_two_documentation_comments_is_found() -> None:
    lines = _lines("/** Old. */\nint g(void);\n/** New. */\nint f(void);\n")
    assert find_comment(lines, 4) == (3, 3)


def test_the_empty_comment_is_plain() -> None:
    with pytest.raises(ExtractorError, match="not a documentation comment"):
        find_comment(_lines("/**/\nint f(void);\n"), 2)


def test_a_banner_of_stars_is_plain() -> None:
    with pytest.raises(ExtractorError, match="not a documentation comment"):
        find_comment(_lines("/*****\n * Banner.\n */\nint f(void);\n"), 4)


# --- declaration_end --------------------------------------------------------


def test_a_declaration_ending_on_its_first_line_ends_there() -> None:
    assert declaration_end(_lines("int f(void);\nint g(void);\n"), 1) == 1


def test_a_declaration_ends_on_the_line_of_its_semicolon_after_continuations() -> None:
    assert declaration_end(_lines("int f(int a,\n      int b,\n      int c);\n"), 1) == 3


def test_a_semicolon_inside_parentheses_does_not_end_the_declaration() -> None:
    assert declaration_end(_lines("int f(a; b,\n      c);\n"), 1) == 2


def test_a_semicolon_in_a_block_comment_is_skipped() -> None:
    assert declaration_end(_lines("int f(int a /* ; */,\n      int b);\n"), 1) == 2


def test_a_semicolon_in_a_multi_line_block_comment_is_skipped() -> None:
    assert declaration_end(_lines("int f(int a /* one\n ; two */,\n int b);\n"), 1) == 3


def test_a_semicolon_in_a_line_comment_is_skipped() -> None:
    assert declaration_end(_lines("int f(int a, // ;\n      int b);\n"), 1) == 2


def test_a_declaration_with_no_semicolon_is_refused() -> None:
    with pytest.raises(ExtractorError, match="no semicolon"):
        declaration_end(_lines("int f(int a,\n      int b)\n"), 1)


def test_a_brace_before_the_semicolon_refuses_the_declaration() -> None:
    with pytest.raises(ExtractorError, match="before the semicolon"):
        declaration_end(_lines("static inline int f(void) {\n  return 1;\n}\n"), 1)


# --- head_end ---------------------------------------------------------------


def test_a_head_ends_on_the_line_before_a_brace_alone_on_its_line() -> None:
    assert head_end(_lines("int f(void)\n{\n  return 0;\n}\n"), 1, 4) == 1


def test_a_head_of_several_lines_ends_before_the_brace_line() -> None:
    assert head_end(_lines("int f(int a,\n      int b)\n\t{\n  return a;\n}\n"), 1, 5) == 2


def test_a_brace_on_a_head_line_is_refused() -> None:
    with pytest.raises(ExtractorError, match="holds a"):
        head_end(_lines("int f(void) {\n  return 0;\n}\n"), 1, 3)


def test_no_brace_line_by_the_end_of_the_body_is_refused() -> None:
    with pytest.raises(ExtractorError, match="no line"):
        head_end(_lines("int f(int a,\n      int b)\n{\n}\n"), 1, 2)


def test_a_brace_line_that_is_the_first_line_leaves_no_head_and_is_refused() -> None:
    with pytest.raises(ExtractorError, match="no head"):
        head_end(_lines("{\n}\n"), 1, 2)


# --- a tree small enough to read --------------------------------------------

MACRO = "/** Doubles. */\n#define DBL(x) \\\n\t((x) * 2)\n"
SAME_FILE = (
    "#include <x.h>\n\n/** Adds. */\nint add(int a,\n        int b)\n{\n\treturn a + b;\n}\n"
)


def _member(name: str, kind: str, ident: str, **location: str) -> str:
    attributes = " ".join(f'{key}="{value}"' for key, value in location.items())
    return (
        f'<memberdef kind="{kind}" id="{ident}"><name>{name}</name>'
        f"<briefdescription><para>text</para></briefdescription><location {attributes}/>"
        "</memberdef>"
    )


def _macro(name: str = "DBL", ident: str = "m1", **location: str) -> str:
    where = {"file": "m.h", "line": "2", "bodyfile": "m.h", "bodystart": "2", "bodyend": "3"}
    where.update(location)
    return _member(name, "define", ident, **where)


def _add(**location: str) -> str:
    where = {"file": "f.c", "line": "4", "bodyfile": "f.c", "bodystart": "4", "bodyend": "8"}
    where.update(location)
    return _member("add", "function", "f1", **where)


def _need(need_id: str, symbol: str, stream: str) -> dict[str, Any]:
    if stream == "impl":
        return {"id": need_id, "title": symbol, "satisfies": ["REQ-1"]}
    return {"id": need_id, "test_function": symbol, "verifies": ["REQ-1"]}


def _export(path: Path, needs: dict[str, dict[str, Any]]) -> Path:
    document = {"versions": {"v1": {"needs": needs}}}
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _doxygen(directory: Path, compounds: dict[str, list[str]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, members in compounds.items():
        body = "".join(members)
        (directory / name).write_text(
            f"<doxygen><compounddef><sectiondef>{body}</sectiondef></compounddef></doxygen>",
            encoding="utf-8",
        )
    return directory


def _build(
    tmp_path: Path,
    members: list[str],
    files: dict[str, bytes | str],
    symbols: tuple[str, ...] = ("DBL",),
    stream: str = "impl",
    compounds: dict[str, list[str]] | None = None,
) -> CSourceExtractor:
    """An extractor over a tree built in ``tmp_path``; its needs are ``IMPL-<symbol>``."""
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    for relative, content in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        (root / relative).write_bytes(data)
    needs = {f"IMPL-{symbol}": _need(f"IMPL-{symbol}", symbol, stream) for symbol in symbols}
    export = _export(tmp_path / "needs.json", needs)
    dox = _doxygen(tmp_path / "dox", compounds or {"c.xml": members})
    if stream == "impl":
        return CSourceExtractor(
            root,
            repository="sample",
            implementations=config.ImplementationInputs(export=export, doxygen=dox),
            specifications=None,
        )
    return CSourceExtractor(
        root,
        repository="sample",
        implementations=None,
        specifications=config.SpecificationInputs(export=export, doxygen=dox),
    )


def _one(extractor: CSourceExtractor, name: str = "IMPL-DBL"):
    return {node.local_id: node for node in extractor.nodes()}[name]


def test_a_macros_api_span_runs_from_its_comment_through_the_define_line(tmp_path: Path) -> None:
    node = _one(_build(tmp_path, [_macro()], {"m.h": MACRO}))
    anchor = node.content_anchors["apiHash"]
    assert anchor.digest == _digest(_lines(MACRO), 1, 2)
    assert (anchor.repository, anchor.path, anchor.locator) == ("sample", "m.h", "symbol:DBL#api")


def test_a_macros_body_span_is_its_located_lines(tmp_path: Path) -> None:
    node = _one(_build(tmp_path, [_macro()], {"m.h": MACRO}))
    assert node.content_anchors["bodyHash"].digest == _digest(_lines(MACRO), 2, 3)


def test_a_same_file_functions_api_span_ends_before_its_brace_line(tmp_path: Path) -> None:
    node = _one(_build(tmp_path, [_add()], {"f.c": SAME_FILE}, ("add",)), "IMPL-add")
    anchor = node.content_anchors["apiHash"]
    assert anchor.digest == _digest(_lines(SAME_FILE), 3, 5)
    assert (anchor.path, anchor.locator) == ("f.c", "symbol:add#api")


def test_a_same_file_functions_body_span_is_its_located_lines(tmp_path: Path) -> None:
    node = _one(_build(tmp_path, [_add()], {"f.c": SAME_FILE}, ("add",)), "IMPL-add")
    assert node.content_anchors["bodyHash"].digest == _digest(_lines(SAME_FILE), 4, 8)


def test_a_same_file_head_holding_a_brace_is_an_error_naming_the_need(tmp_path: Path) -> None:
    source = "/** Adds. */\nint add(int a) {\n\treturn a;\n}\n"
    extractor = _build(
        tmp_path, [_add(line="2", bodystart="2", bodyend="4")], {"f.c": source}, ("add",)
    )
    with pytest.raises(ExtractorError, match="IMPL-add"):
        list(extractor.nodes())


def test_a_body_ending_at_minus_one_is_an_error_naming_the_need(tmp_path: Path) -> None:
    extractor = _build(tmp_path, [_macro(bodyend="-1")], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=NEED):
        list(extractor.nodes())


def test_a_symbol_defined_twice_is_an_error_naming_the_need(tmp_path: Path) -> None:
    extractor = _build(tmp_path, [_macro(ident="m1"), _macro(ident="m2")], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=NEED):
        list(extractor.nodes())


def test_a_duplicate_of_a_symbol_no_need_names_is_ignored(tmp_path: Path) -> None:
    members = [_macro(), _macro("OTHER", "o1"), _macro("OTHER", "o2")]
    assert _one(_build(tmp_path, members, {"m.h": MACRO})).local_id == NEED


def test_one_definition_listed_twice_with_one_id_is_not_ambiguous(tmp_path: Path) -> None:
    compounds = {"a.xml": [_macro()], "b.xml": [_macro()]}
    extractor = _build(tmp_path, [], {"m.h": MACRO}, compounds=compounds)
    assert _one(extractor).local_id == NEED


def test_a_symbol_the_doxygen_output_lacks_is_an_error_naming_the_need(tmp_path: Path) -> None:
    extractor = _build(tmp_path, [_macro("OTHER", "o1")], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=NEED):
        list(extractor.nodes())


def test_a_relative_path_leaving_the_root_is_refused_before_the_file_is_read(
    tmp_path: Path,
) -> None:
    extractor = _build(tmp_path, [_macro(bodyfile="../gone.h")], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=rf"{NEED}.*outside the root"):
        list(extractor.nodes())


def test_an_absolute_path_is_outside_the_root(tmp_path: Path) -> None:
    outside = tmp_path / "abs.h"
    outside.write_text(MACRO, encoding="utf-8")
    extractor = _build(tmp_path, [_macro(file=str(outside))], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match="outside the root"):
        list(extractor.nodes())


def test_a_symlink_leading_out_of_the_root_is_outside_it(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "m.h").write_text(MACRO, encoding="utf-8")
    extractor = _build(tmp_path, [_macro(bodyfile="link/m.h")], {"m.h": MACRO})
    os.symlink(elsewhere, tmp_path / "root" / "link")
    with pytest.raises(ExtractorError, match="outside the root"):
        list(extractor.nodes())


def test_a_missing_source_inside_the_root_is_an_error_naming_the_need(tmp_path: Path) -> None:
    extractor = _build(tmp_path, [_macro(file="absent.h")], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=rf"{NEED}.*cannot be read"):
        list(extractor.nodes())


def test_a_symbol_only_inside_a_longer_name_is_not_on_its_line(tmp_path: Path) -> None:
    source = "/** Doubles. */\n#define DBL2(x) \\\n\t((x) * 2)\n"
    extractor = _build(tmp_path, [_macro()], {"m.h": source})
    with pytest.raises(ExtractorError, match=NEED):
        list(extractor.nodes())


def test_a_test_whose_located_line_is_not_its_body_start_is_an_error(tmp_path: Path) -> None:
    source = "/** Test. */\nZTEST(s, t)\n{\n}\n"
    member = _member(
        "t", "function", "t1", file="t.c", line="2", bodyfile="t.c", bodystart="3", bodyend="4"
    )
    extractor = _build(tmp_path, [member], {"t.c": source}, ("t",), stream="spec")
    with pytest.raises(ExtractorError, match="IMPL-t"):
        list(extractor.nodes())


def test_a_member_that_is_neither_a_function_nor_a_define_is_an_error(tmp_path: Path) -> None:
    member = _member("DBL", "variable", "v1", file="m.h", line="2")
    extractor = _build(tmp_path, [member], {"m.h": MACRO})
    with pytest.raises(ExtractorError, match=rf"{NEED}.*variable"):
        list(extractor.nodes())


# --- construction -----------------------------------------------------------


def _inputs(tmp_path: Path, export: Path) -> CSourceExtractor:
    dox = _doxygen(tmp_path / "dox", {"c.xml": []})
    return CSourceExtractor(
        tmp_path,
        repository="sample",
        implementations=config.ImplementationInputs(export=export, doxygen=dox),
        specifications=None,
    )


def _text_export(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "raw.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_an_export_with_two_versions_is_refused(tmp_path: Path) -> None:
    text = json.dumps({"versions": {"a": {"needs": {}}, "b": {"needs": {}}}})
    with pytest.raises(ExtractorError, match="exactly one"):
        _inputs(tmp_path, _text_export(tmp_path, text))


def test_an_export_without_needs_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ExtractorError, match="needs"):
        _inputs(tmp_path, _text_export(tmp_path, json.dumps({"versions": {"a": {}}})))


def test_an_unreadable_or_non_json_export_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ExtractorError, match="cannot be read"):
        _inputs(tmp_path, _text_export(tmp_path, "{not json"))
    with pytest.raises(ExtractorError, match="cannot be read"):
        _inputs(tmp_path, tmp_path / "absent.json")


def test_a_need_whose_id_differs_from_its_key_is_refused_naming_the_need(tmp_path: Path) -> None:
    export = _export(tmp_path / "e.json", {"IMPL-A": _need("IMPL-B", "a", "impl")})
    with pytest.raises(ExtractorError, match="IMPL-A"):
        _inputs(tmp_path, export)


def test_a_need_without_its_symbol_is_refused_naming_the_need(tmp_path: Path) -> None:
    need = {"id": "IMPL-A", "satisfies": []}
    with pytest.raises(ExtractorError, match="IMPL-A"):
        _inputs(tmp_path, _export(tmp_path / "e.json", {"IMPL-A": need}))


def test_a_missing_doxygen_directory_is_refused(tmp_path: Path) -> None:
    export = _export(tmp_path / "e.json", {})
    with pytest.raises(ExtractorError, match="not a directory"):
        CSourceExtractor(
            tmp_path,
            repository="sample",
            implementations=config.ImplementationInputs(export=export, doxygen=tmp_path / "nope"),
            specifications=None,
        )


def test_a_doxygen_file_that_does_not_parse_is_refused(tmp_path: Path) -> None:
    export = _export(tmp_path / "e.json", {})
    dox = _doxygen(tmp_path / "dox", {"c.xml": []})
    (dox / "broken.xml").write_text("<doxygen><unclosed>", encoding="utf-8")
    with pytest.raises(ExtractorError, match="broken.xml"):
        CSourceExtractor(
            tmp_path,
            repository="sample",
            implementations=config.ImplementationInputs(export=export, doxygen=dox),
            specifications=None,
        )


def test_the_extractor_and_the_reader_refuse_the_same_exports(tmp_path: Path) -> None:
    stamped = {"a": {"needs": {}, "created": "2026-09-29T10:00:00"}}
    exports = [
        json.dumps({"versions": {"a": {"needs": {}}, "b": {"needs": {}}}}),
        json.dumps({"versions": {"a": {}}}),
        json.dumps({"versions": {"a": {"needs": {"x": 1}}}}),
        json.dumps({"versions": stamped}),
        json.dumps({"created": "2026-09-29T10:00:00", "versions": {"a": {"needs": {}}}}),
        "{not json",
        "[]",
    ]
    for text in exports:
        path = _text_export(tmp_path, text)
        with pytest.raises(ReaderError):
            RequirementsReader(
                export=path, types=frozenset(), repository="r", source_directory=Path(".")
            )
        with pytest.raises(ExtractorError):
            _inputs(tmp_path, path)


def test_an_extractor_with_no_streams_supplies_nothing(tmp_path: Path) -> None:
    extractor = CSourceExtractor(
        tmp_path, repository="sample", implementations=None, specifications=None
    )
    assert list(extractor.nodes()) == []
    assert list(extractor.edges()) == []


# --- the stream -------------------------------------------------------------


def test_an_error_is_raised_when_the_stream_reaches_its_node_and_earlier_nodes_were_supplied(
    tmp_path: Path,
) -> None:
    extractor = _build(tmp_path, [_macro()], {"m.h": MACRO}, symbols=("DBL", "GONE"))
    stream = extractor.nodes()
    assert next(stream).local_id == NEED
    with pytest.raises(ExtractorError, match="IMPL-GONE"):
        next(stream)


def test_a_second_pass_reads_the_source_again(tmp_path: Path) -> None:
    extractor = _build(tmp_path, [_macro()], {"m.h": MACRO})
    before = _one(extractor).content_anchors["bodyHash"].digest
    (tmp_path / "root" / "m.h").write_text(MACRO.replace("2", "3"), encoding="utf-8")
    assert _one(extractor).content_anchors["bodyHash"].digest != before


def test_a_source_file_is_opened_once_per_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = _macro("TWO", "m2", line="5", bodystart="5", bodyend="6")
    source = MACRO + "/** Triples. */\n#define TWO(x) \\\n\t((x) * 3)\n"
    extractor = _build(tmp_path, [_macro(), second], {"m.h": source}, symbols=("DBL", "TWO"))
    opened: list[str] = []
    real = builtins.open

    def spy(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(os.path.realpath(file))
        return real(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    assert len(list(extractor.nodes())) == 2
    assert opened.count(os.path.realpath(tmp_path / "root" / "m.h")) == 1
