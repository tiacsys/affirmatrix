"""Verification suite for the path root of the content extractor.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
Doxygen output can name its files relative to a directory other than the
repository root, as the API output of a project that keeps its headers in an
include directory does. The path root puts that directory in front of each path,
after any prefix is removed.

Every fixture is built by the test in a temporary directory: a header that has a
documentation comment with a satisfies tag and a macro of several lines with
continuation lines, a small test source, the Doxygen output that names them, and
the configuration file. The files are text for the extractor and are never
compiled. An expected digest is the SHA-256 of a run of whole lines of a file the
test wrote. The test finds the lines by scanning that file and never calls the
extractor for it.
"""

from __future__ import annotations

import builtins
import io
import os
import re
from pathlib import Path
from typing import Any

import pytest

from affirmatrix.sources import SourceError

from . import capture_support as support
from . import path_root_support as roots

NO_ROOT_YET = "SEG-SREQ-349: the extractor ignores the path root and reads the path as named"


def _repository(tmp_path: Path) -> Path:
    """A repository whose one header is at include/zephyr/queue.h."""
    repository = tmp_path / "repository"
    roots.header_in(repository)
    return repository


def _macro_configuration(tmp_path: Path, repository: Path, **keys: Any) -> Path:
    """An implementation stream over a Doxygen output that names zephyr/queue.h."""
    tree = roots.macro_tree(tmp_path / "xml")
    return roots.implementations(tmp_path, repository, tree, **keys)


def _macro(path: Path):
    nodes, _ = support.records(path)
    return nodes[roots.NEED]


def _refusal(path: Path) -> str:
    with pytest.raises(SourceError) as caught:
        support.records(path)
    return str(caught.value)


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


@pytest.mark.xfail(strict=True, reason=NO_ROOT_YET)
def test_a_path_root_is_put_in_front_of_the_path_the_doxygen_output_names(tmp_path: Path) -> None:
    """A path root is put in front of the path the Doxygen output names, and the file is read there.

    The Doxygen output names the macro QUEUE_MAKE in the file zephyr/queue.h. The
    repository holds the header at include/zephyr/queue.h and holds no file at
    zephyr/queue.h. No path prefix is configured. The header has a documentation
    comment with a satisfies tag, then a macro of five lines with continuation
    lines. With the path root include/ configured, the extractor supplies the
    record of the need I-QUEUE. Its apiHash equals the SHA-256 of the lines from
    the opener of the comment to the first line of the macro. Its bodyHash equals
    the SHA-256 of the five lines of the macro, to the last continuation line.

    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-379
    """
    repository = _repository(tmp_path)
    expected = roots.expected_macro(repository)
    path = _macro_configuration(tmp_path, repository, **{support.KEY_PATH_ROOT: roots.ROOT})

    anchors = _macro(path).content_anchors

    assert anchors["apiHash"].digest == expected.api
    assert anchors["bodyHash"].digest == expected.body


@pytest.mark.xfail(strict=True, reason=NO_ROOT_YET)
def test_the_prefix_is_removed_first_and_then_the_path_root_is_put_in_front(
    tmp_path: Path,
) -> None:
    """With a prefix and a path root, the prefix is removed first and the root is put in front.

    The Doxygen output names the macro QUEUE_MAKE in the file ext/zephyr/queue.h.
    The prefix ext/ and the path root include/ are configured. The repository
    holds the header at include/zephyr/queue.h. It also holds a decoy header, with
    other text, at each of three paths: zephyr/queue.h, ext/zephyr/queue.h and
    include/ext/zephyr/queue.h. The extractor supplies the record of I-QUEUE, and
    its apiHash and bodyHash equal the SHA-256 of the lines of the header at
    include/zephyr/queue.h, found as in the first specification.

    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-380
    """
    repository = _repository(tmp_path)
    for decoy in ("zephyr/queue.h", "ext/zephyr/queue.h", "include/ext/zephyr/queue.h"):
        roots.header_in(repository, decoy, roots.HEADER.replace("Define a queue", "Define a decoy"))
    expected = roots.expected_macro(repository)
    tree = roots.macro_tree(tmp_path / "xml", "ext/zephyr/queue.h")
    path = roots.implementations(
        tmp_path,
        repository,
        tree,
        **{support.KEY_PREFIX: "ext/", support.KEY_PATH_ROOT: roots.ROOT},
    )

    anchors = _macro(path).content_anchors

    assert anchors["apiHash"].digest == expected.api
    assert anchors["bodyHash"].digest == expected.body


@pytest.mark.xfail(strict=True, reason=NO_ROOT_YET)
def test_a_trailing_separator_of_the_path_root_is_optional(tmp_path: Path) -> None:
    """A path root with a trailing separator and one without it give the same record.

    The Doxygen output names the macro QUEUE_MAKE in the file zephyr/queue.h, and
    the repository holds the header at include/zephyr/queue.h. The extractor is
    run twice, once with the path root include/ and once with the path root
    include. Each run supplies the record of I-QUEUE. The two records have the same
    digests and the same anchors, and the path of each anchor is
    include/zephyr/queue.h, with no doubled separator.

    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-381
    """
    repository = _repository(tmp_path)
    records = []
    for name, root in (("with", "include/"), ("without", "include")):
        path = _macro_configuration(tmp_path / name, repository, **{support.KEY_PATH_ROOT: root})
        records.append(_macro(path).content_anchors)

    assert records[0] == records[1]
    assert {anchor.path for anchor in records[0].values()} == {roots.JOINED}


@pytest.mark.parametrize("empty", ["", None], ids=["empty-text", "null"])
def test_an_empty_path_root_is_the_same_as_none(empty: str | None, tmp_path: Path) -> None:
    """An empty path root and a null path root are the same as no path root.

    The Doxygen output names the macro QUEUE_MAKE in the file include/zephyr/queue.h,
    and the repository holds the header at that path. With no path root given, the
    extractor supplies the record of I-QUEUE. With the path root given as the empty
    text, or as null, it supplies a record with the same digests and the same
    anchors, and the path of each anchor is include/zephyr/queue.h. No
    separator is put in front of the path.

    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-382
    """
    repository = _repository(tmp_path)
    tree = roots.macro_tree(tmp_path / "xml", roots.JOINED)
    plain = _macro(roots.implementations(tmp_path / "plain", repository, tree))
    given = _macro(
        roots.implementations(
            tmp_path / "given", repository, tree, **{support.KEY_PATH_ROOT: empty}
        )
    )

    assert given.content_anchors == plain.content_anchors
    assert plain.content_anchors["apiHash"].digest == roots.expected_macro(repository).api
    assert {a.path for a in given.content_anchors.values()} == {roots.JOINED}


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-162: the extractor ignores the path root, so none is refused"
)
@pytest.mark.parametrize("shape", ["parent", "climbing", "absolute"])
def test_a_path_root_that_leads_outside_the_repository_is_an_error_for_the_node(
    shape: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path root that is absolute or leads outside the repository is an error for the node.

    The repository is a directory that holds a header at zephyr/queue.h. Next to it
    is a second directory, outside the repository, that holds a header at the same
    path. The Doxygen output names the macro QUEUE_MAKE in the file
    zephyr/queue.h. With no path root the extractor supplies the record of I-QUEUE.
    The path root then names the second directory in one of three ways: as a
    relative path that begins with .., as a relative path that begins inside the
    repository and climbs out with .., or as an absolute path.
    In each case taking the records raises a source error that names the need
    I-QUEUE. The header in the second directory is not opened.

    :verifies: SEG-SREQ-162
    :test-id: SEG-TS-383
    """
    repository = _repository(tmp_path)
    roots.header_in(repository, roots.NAMED)
    outside = tmp_path / "outside"
    roots.header_in(outside, roots.NAMED)
    root = {
        "parent": "../outside",
        "climbing": "include/../../outside",
        "absolute": str(outside),
    }[shape]
    assert roots.NEED in support.records(_macro_configuration(tmp_path / "control", repository))[0]
    path = _macro_configuration(tmp_path, repository, **{support.KEY_PATH_ROOT: root})

    opened = _opened(monkeypatch)
    message = _refusal(path)

    assert roots.NEED in message
    assert os.path.realpath(outside / roots.NAMED) not in opened


def _test_files(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A repository with the shared test in three directories under tests/."""
    repository = tmp_path / "repository"
    files = {
        "mod_a/src/main.c": "alpha",
        "mod_ab/src/main.c": "alpha-b",
        "mod_b/src/main.c": "beta",
    }
    for name, brief in files.items():
        roots.write_file(repository, f"tests/{name}", roots.source_with(brief))
    return repository, files


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-278: the module is compared with the path as named"
)
def test_the_test_module_is_compared_with_the_path_after_the_root_is_put_in_front(
    tmp_path: Path,
) -> None:
    """The directory of the test module is compared with the path after the root is put in front.

    The test source of the repository is in three files: tests/mod_a/src/main.c,
    tests/mod_ab/src/main.c and tests/mod_b/src/main.c. Each has the test
    test_shared with its own comment. The Doxygen output names the test in the
    files mod_a/src/main.c, mod_ab/src/main.c and mod_b/src/main.c. The need
    T-SHARED names the test module tests/mod_a. With the path root tests/ the
    extractor supplies the record of T-SHARED, and its specHash and implHash equal
    the SHA-256 of the comment and of the test in tests/mod_a/src/main.c. With no
    path root the extractor raises a source error that names T-SHARED, because
    none of the three paths lies within tests/mod_a.

    :verifies: SEG-SREQ-278
    :test-id: SEG-TS-384
    """
    repository, files = _test_files(tmp_path)
    tree = roots.shared_tree(tmp_path / "xml", files)
    needs = [roots.case_need_for("T-SHARED", "tests/mod_a")]
    expected = roots.expected_test(repository, "tests/mod_a/src/main.c")

    rooted = roots.specifications(
        tmp_path / "rooted", repository, tree, needs, **{support.KEY_PATH_ROOT: "tests/"}
    )
    nodes, _ = support.records(rooted)
    anchors = nodes["T-SHARED"].content_anchors
    assert anchors["specHash"].digest == expected.api
    assert anchors["implHash"].digest == expected.body

    unrooted = roots.specifications(tmp_path / "unrooted", repository, tree, needs)
    assert "T-SHARED" in _refusal(unrooted)


@pytest.mark.xfail(strict=True, reason=NO_ROOT_YET)
def test_a_path_root_on_the_specifications_block_locates_a_test(tmp_path: Path) -> None:
    """A path root on the specifications block locates a test by the joined path.

    The Doxygen output names the test test_shared in the file mod_a/src/main.c, and
    the repository holds the test source at tests/mod_a/src/main.c only. The
    need T-SHARED names no test module. With the path root tests/ configured on
    the specifications block, the extractor supplies the record of T-SHARED. Its
    specHash equals the SHA-256 of the comment of the test, from its opener to its
    closer, and its implHash equals the SHA-256 of the lines of the test, from the
    line that names it to its closing brace.

    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-385
    """
    repository = tmp_path / "repository"
    roots.write_file(repository, "tests/mod_a/src/main.c", roots.source_with("alpha"))
    tree = roots.shared_tree(tmp_path / "xml", {"mod_a/src/main.c": "alpha"})
    expected = roots.expected_test(repository, "tests/mod_a/src/main.c")
    path = roots.specifications(
        tmp_path,
        repository,
        tree,
        [roots.case_need_for("T-SHARED")],
        **{support.KEY_PATH_ROOT: "tests/"},
    )

    nodes, _ = support.records(path)
    anchors = nodes["T-SHARED"].content_anchors

    assert anchors["specHash"].digest == expected.api
    assert anchors["implHash"].digest == expected.body


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-281: the extractor cannot read the path without the root"
)
def test_an_anchor_names_the_path_inside_the_repository_after_the_root_is_put_in_front(
    tmp_path: Path,
) -> None:
    """An anchor names the repository and the joined path inside it.

    With the path root include/ and the prefix ext/, the Doxygen output names the
    macro QUEUE_MAKE in ext/zephyr/queue.h, and the repository named lib holds the
    header at include/zephyr/queue.h. Both anchors of I-QUEUE, the one of the
    apiHash and the one of the bodyHash, name the repository lib and the path
    include/zephyr/queue.h. With the path root tests/, the test test_shared that
    the Doxygen output names in mod_a/src/main.c gives anchors for specHash and
    implHash that name the repository suite and the path tests/mod_a/src/main.c.

    :verifies: SEG-SREQ-281
    :test-id: SEG-TS-386
    """
    repository = _repository(tmp_path / "lib")
    roots.header_in(repository, "ext/zephyr/queue.h", "decoy\n")
    tree = roots.macro_tree(tmp_path / "lib" / "xml", "ext/zephyr/queue.h")
    keys = {support.KEY_PREFIX: "ext/", support.KEY_PATH_ROOT: roots.ROOT}
    anchors = _macro(roots.implementations(tmp_path / "lib", repository, tree, **keys))
    for name in ("apiHash", "bodyHash"):
        anchor = anchors.content_anchors[name]
        assert (anchor.repository, anchor.path) == ("lib", roots.JOINED)

    suite = tmp_path / "suite"
    roots.write_file(suite, "tests/mod_a/src/main.c", roots.source_with("alpha"))
    cases = roots.shared_tree(suite / "xml", {"mod_a/src/main.c": "alpha"})
    path = roots.specifications(
        tmp_path / "suite",
        suite,
        cases,
        [roots.case_need_for("T-SHARED")],
        **{support.KEY_PATH_ROOT: "tests/"},
    )
    nodes, _ = support.records(path)
    for name in ("specHash", "implHash"):
        anchor = nodes["T-SHARED"].content_anchors[name]
        assert (anchor.repository, anchor.path) == ("suite", "tests/mod_a/src/main.c")


def test_the_prefix_rules_still_hold_when_a_path_root_is_configured(tmp_path: Path) -> None:
    """A path root does not change the errors of the prefix.

    The repository holds the header at include/zephyr/queue.h and a decoy at
    zephyr/queue.h. The path root include/ is configured. With the prefix ext/ and
    the Doxygen output naming the macro in zephyr/queue.h, which does not begin
    with the prefix, taking the records raises a source error that names I-QUEUE
    and the prefix. With the prefix ext and the path ext/zephyr/queue.h, whose
    remainder begins with a separator, the error names I-QUEUE and the path. With
    the whole path as the prefix, which leaves nothing, the error names I-QUEUE.
    In each case the root is not put in front of the unusable remainder.

    :verifies: SEG-SREQ-280
    :test-id: SEG-TS-387
    """
    repository = _repository(tmp_path)
    roots.header_in(repository, roots.NAMED, "decoy\n")
    cases = [
        ("outside", roots.NAMED, "ext/", "ext/"),
        ("separator", "ext/zephyr/queue.h", "ext", "ext/zephyr/queue.h"),
        ("whole", "ext/zephyr/queue.h", "ext/zephyr/queue.h", "ext/zephyr/queue.h"),
    ]
    for name, named, prefix, text in cases:
        tree = roots.macro_tree(tmp_path / name / "xml", named)
        keys = {support.KEY_PREFIX: prefix, support.KEY_PATH_ROOT: roots.ROOT}
        message = _refusal(roots.implementations(tmp_path / name, repository, tree, **keys))
        (line,) = [text for text in message.splitlines() if roots.NEED in text]
        assert re.search(re.escape(text), line), (name, line)


@pytest.mark.xfail(strict=True, reason=NO_ROOT_YET)
def test_the_bytes_behind_a_hash_are_read_from_the_joined_path(tmp_path: Path) -> None:
    """The bytes behind a hash are the lines of the joined path.

    The Doxygen output names the macro QUEUE_MAKE in the file zephyr/queue.h, and
    the repository holds the header at include/zephyr/queue.h only. With the path
    root include/ configured, the extractor supplies the record of I-QUEUE. Asking
    the content extractor, and asking the composed producer that holds it, for the
    bytes behind apiHash gives the lines of the header from the opener of the
    comment to the first line of the macro. Asking for the bytes behind bodyHash
    gives the five lines of the macro. Each answer equals the lines that the test
    cuts from its own header, and its SHA-256 is the digest in the anchor of the
    record.

    :verifies: SEG-SREQ-311
    :verifies: SEG-SREQ-349
    :test-id: SEG-TS-388
    """
    from affirmatrix.sources.content import CSourceExtractor

    repository = _repository(tmp_path)
    lines = support.file_lines(repository, roots.JOINED)
    opener = next(n for n, text in enumerate(lines, 1) if text.startswith(b"/**"))
    expected = {
        "apiHash": support.run_of(lines, opener, roots.HEADER_DEFINE),
        "bodyHash": support.run_of(lines, roots.HEADER_DEFINE, roots.HEADER_DEFINE_LAST),
    }
    path = _macro_configuration(tmp_path, repository, **{support.KEY_PATH_ROOT: roots.ROOT})
    producer = support.producer_of(path)
    (extractor,) = [m for m in producer.sources if isinstance(m, CSourceExtractor)]
    anchors = {n.local_id: n for n in producer.nodes()}[roots.NEED].content_anchors

    for source in (extractor, producer):
        for name, data in expected.items():
            given = source.content(roots.NEED, name)
            assert given == data, (type(source).__name__, name)
            assert support.sha(given) == anchors[name].digest
