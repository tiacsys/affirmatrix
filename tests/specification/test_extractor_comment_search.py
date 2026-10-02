"""Verification suite for the search for a documentation comment above a test or an implementation.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests read the synthetic sources under ``tests/fixtures/capture_shape/``. One C
file holds one test for each case of the search. A comment stands directly above
one test. A blank line, a conditional line or a plain comment stands between the
comment and the test in other cases. Some lines stop the search. A header holds
some of the same cases for macros. The files are text for the extractor.
They are never compiled.

An expected digest is the SHA-256 of a run of whole lines of a fixture source.
The test finds the first and the last line of the comment by the tag that the
comment carries. It never calls the extractor for that. Each variant of a source
is built in the test, in a temporary directory, with every line number kept.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from affirmatrix.sources import SourceError

from . import capture_support as support

SPANS_FILE = "tests/spans/src/main.c"
HEADER_FILE = "include/impl_spans.h"
BLANK_AND_CONDITIONAL = (
    "blank",
    "blank_two",
    "blank_if",
    "ifdef",
    "ifndef",
    "elif",
    "else",
    "endif",
)
PLAIN_COMMENTS = ("plain", "plain_multi", "plain_indented", "mixed")
STOPS = ("code", "include", "define", "linecomment", "doxline", "codecloser")
NO_COMMENT = ("nodoc_code", "top")
ONLY_PLAIN = ("nodoc_plain", "nodoc_banner", "nodoc_blank_if")


def _tests(tmp_path: Path, cases, repositories=None, name: str = "cases") -> Path:
    needs = [support.case_need(f"S-{case}", f"test_{case}") for case in cases]
    export = support.export_of(tmp_path, needs, name)
    block = support.specifications_block("spans", export=str(export))
    return support.configuration(
        tmp_path, specifications=block, default_repository="suite", repositories=repositories
    )


def _macros(tmp_path: Path, names) -> Path:
    needs = [support.implementation_need(f"I-{name}", name) for name in names]
    block = support.implementations_block(
        "spans-impl", export=str(support.export_of(tmp_path, needs, "macros"))
    )
    return support.configuration(tmp_path, implementations=block, default_repository="lib")


def _refused(path: Path, ident: str) -> None:
    with pytest.raises(SourceError, match=re.escape(ident)):
        support.records(path)


def _spec_digests(path: Path, cases) -> dict[str, bytes]:
    nodes, _ = support.records(path)
    return {case: nodes[f"S-{case}"].content_anchors["specHash"].digest for case in cases}


def _expected(root: Path, cases) -> dict[str, bytes]:
    lines = support.file_lines(root / "suite", SPANS_FILE)
    return {case: support.sha(support.comment_run(lines, f"S-{case}")) for case in cases}


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-166: a blank line, #elif, #else, #endif stop it")
def test_a_spechash_steps_over_blank_lines_and_conditional_lines(tmp_path: Path) -> None:
    """A specHash steps over blank lines and conditional lines above the test.

    In the test source, eight tests have a documentation comment above them. Lines
    of one kind stand between the comment and the test. The first test has one
    blank line, and the second has two. The third has a blank line and an #if line.
    The others have one line each: #ifdef, #ifndef, #elif, #else or #endif. For
    each test the specHash equals the SHA-256 of the comment, from its opening
    line to its closing line. The lines in between are not in the run.

    :verifies: SEG-SREQ-166
    :test-id: SEG-TS-190
    """
    cases = BLANK_AND_CONDITIONAL
    assert _spec_digests(_tests(tmp_path, cases), cases) == _expected(support.REPOS, cases)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-166: a plain comment stops the search")
def test_a_spechash_steps_over_plain_comments(tmp_path: Path) -> None:
    """A specHash steps over plain block comments above the test.

    In the test source, four tests have a documentation comment above them. Lines
    of one kind stand between the comment and the test. The first has a plain
    block comment of one line. The second has one of three lines. The third has one
    of one line behind white space. The fourth has a plain comment, a blank line,
    an #if line and a blank line, in that order. For each test the specHash equals
    the SHA-256 of the documentation comment, from its opening line to its closing
    line. No byte of the plain comment is in the run.

    :verifies: SEG-SREQ-166
    :test-id: SEG-TS-191
    """
    cases = PLAIN_COMMENTS
    assert _spec_digests(_tests(tmp_path, cases), cases) == _expected(support.REPOS, cases)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-166: the lines between are not stepped over")
def test_the_lines_stepped_over_are_outside_the_spechash(tmp_path: Path) -> None:
    """The lines stepped over lie outside the specHash.

    In a copy of the test source, the blank line below the comment of test_blank
    becomes an #ifndef line. The plain comment below the comment of test_plain
    reads another text. The specHash of both tests equals the digest of the
    comment, as before. In a second copy, the word Direct in the comment of
    test_direct reads DIRECT. Its specHash changes. It equals the SHA-256 of the
    changed comment.

    :verifies: SEG-SREQ-166
    :test-id: SEG-TS-192
    """
    cases = ("blank", "plain", "direct")
    before = _expected(support.REPOS, cases)
    repositories = support.copied_repositories(tmp_path)
    source = repositories["suite"] / SPANS_FILE
    lines = source.read_bytes().splitlines(keepends=True)
    (blank,) = [n for n, text in enumerate(lines) if b"test_blank)" in text]
    assert lines[blank - 1] == b"\n"
    lines[blank - 1] = b"#ifndef CONFIG_Z\n"
    (plain,) = [n for n, text in enumerate(lines) if b"/* a plain comment */" in text]
    lines[plain] = lines[plain].replace(b"a plain comment", b"another text")
    source.write_bytes(b"".join(lines))
    first = _spec_digests(_tests(tmp_path, cases, repositories, "first"), cases)
    assert first == before
    changed = repositories["suite"] / SPANS_FILE
    changed.write_bytes(changed.read_bytes().replace(b"Case direct", b"Case DIRECT"))
    second = _spec_digests(_tests(tmp_path, cases, repositories, "second"), cases)
    assert second["direct"] != before["direct"]
    assert second["direct"] == _expected(repositories["suite"].parent, ("direct",))["direct"]
    assert second["blank"] == before["blank"]


def test_a_missing_comment_above_a_test_is_an_error_for_its_node(tmp_path: Path) -> None:
    """A test with no documentation comment above it is an error for its node.

    In the test source, six tests have a documentation comment above them. One
    line of a stopping kind stands between the comment and the test. The kinds are
    a code line, an #include line and a #define line. They are also a line comment,
    a line that starts with three slashes, and a code line that ends in a block
    comment. A
    seventh test has code directly above it. An eighth test stands on the first
    line of its file. For each of the eight, taking the records raises a source
    error that names the test's need. No hash is supplied.

    :verifies: SEG-SREQ-283
    :test-id: SEG-TS-172
    """
    for case in (*STOPS, *NO_COMMENT):
        _refused(_tests(tmp_path, (case,), name=f"case-{case}"), f"S-{case}")


def test_a_plain_comment_is_no_documentation_comment(tmp_path: Path) -> None:
    """Plain comments, blank lines and conditional lines alone do not make a comment.

    In the test source, one test has only a plain block comment above it. One has
    a banner comment that starts with three stars. One has a blank line and an #if
    line. Code lies above each of them. For each test, taking the records raises a
    source error that names the test's need. No hash is supplied.

    :verifies: SEG-SREQ-283
    :test-id: SEG-TS-173
    """
    for case in ONLY_PLAIN:
        _refused(_tests(tmp_path, (case,), name=f"case-{case}"), f"S-{case}")


def test_the_search_for_an_implementation_comment_is_not_widened(tmp_path: Path) -> None:
    """The search for the comment above an Implementation allows guard lines only.

    In the header, the comment of IMP_DIRECT is directly above its define line.
    One #if line stands between the comment and the define line of IMP_GUARD. The
    apiHash of each equals the SHA-256 of the lines from the comment opening to the
    define line. Three macros have another kind of line between the comment and
    the define line. IMP_BLANK has a blank line. IMP_ELSE has an #else line.
    IMP_PLAIN has a plain comment. Each of the three is an error that names its
    need.

    :verifies: SEG-SREQ-169
    :test-id: SEG-TS-193
    """
    lines = support.file_lines(support.REPOS / "lib", HEADER_FILE)

    def run(name: str) -> bytes:
        (define,) = [n for n, text in enumerate(lines, 1) if f"#define {name} ".encode() in text]
        opener = define
        while b"/**" not in lines[opener - 1]:
            opener -= 1
        return support.run_of(lines, opener, define)

    nodes, _ = support.records(_macros(tmp_path, ("IMP_DIRECT", "IMP_GUARD")))
    for name in ("IMP_DIRECT", "IMP_GUARD"):
        assert nodes[f"I-{name}"].content_anchors["apiHash"].digest == support.sha(run(name))
    for name in ("IMP_BLANK", "IMP_ELSE", "IMP_PLAIN"):
        _refused(_macros(tmp_path, (name,)), f"I-{name}")
