"""Verification suite for the content extractor over inputs that differ from the first fixture.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests read the small synthetic fixture under ``tests/fixtures/capture_shape/``.
It holds three repositories, a test-case export with a need of another type and
an implementation export. It also holds Doxygen trees. The paths in some trees
carry a prefix. Some trees name one test in several directories. The extractor is
reached through the configuration file, the way the command line reaches it. Each
expected digest is the SHA-256 of a run of whole lines of a fixture source. The
test finds the run by the tag that the comment carries. Each variant of an input
is built in the test, in a temporary directory.
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

SPEC_REPOSITORY = "suite"
SPEC_FILE_A = "tests/mod_a/src/main.c"
SPEC_FILE_B = "tests/mod_b/src/main.c"


def _specifications(tmp_path: Path, export: Path | None = None, doxygen: str = "modules", **keys):
    block = support.specifications_block(doxygen, **keys)
    if export is not None:
        block["export"] = str(export)
    return support.configuration(tmp_path, specifications=block, default_repository=SPEC_REPOSITORY)


def _typed_only(export: Path, type_: str, tmp_path: Path, name: str) -> Path:
    """A copy of an export that holds only the needs of one type."""
    needs = support.needs_of(support.document_of(export)).values()
    return support.export_of(tmp_path, [n for n in needs if n["type"] == type_], name)


def _alpha_export(tmp_path: Path) -> Path:
    return support.export_of(
        tmp_path, [support.case_need("T-ALPHA", "test_alpha", "tests/mod_a")], "alpha"
    )


def _two_streams(tmp_path: Path, *, with_requirements: bool = False) -> Path:
    """Tests and implementations, each in a repository of its own and behind a prefix."""
    own = {support.KEY_REPOSITORY: "docs"}
    requirements = support.requirements_block(**own) if with_requirements else None
    specifications = support.specifications_block(
        export=str(_typed_only(support.TEST_CASES_EXPORT, "test_case", tmp_path, "cases")),
        **{support.KEY_PREFIX: "suite/", support.KEY_REPOSITORY: "suite"},
    )
    implementations = support.implementations_block(
        export=str(_typed_only(support.IMPLEMENTATIONS_EXPORT, "impl", tmp_path, "impls")),
        **{support.KEY_PREFIX: "lib-src/", support.KEY_REPOSITORY: "lib"},
    )
    return support.configuration(
        tmp_path,
        requirements=requirements,
        specifications=specifications,
        implementations=implementations,
    )


def _shared_need(module: str | None, ident: str = "T-SHARED") -> dict[str, Any]:
    need = support.case_need(ident, "test_shared", module or "")
    if module is None:
        del need["test_module"]
    return need


def _refused(path: Path, ident: str) -> None:
    with pytest.raises(SourceError, match=re.escape(ident)):
        support.records(path)


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


def test_configured_need_types_and_only_those_supply_records(tmp_path: Path) -> None:
    """Configured need types, and only those, supply records.

    The test-case export holds needs of the type test_case. It also holds T-OTHER,
    a need of the type test_other, whose symbol the Doxygen tree locates. The types
    {test_case} are configured. The extractor supplies records for T-ALPHA and
    T-GAMMA and for no other need. It supplies no Verifies edge from T-OTHER.

    :verifies: SEG-SREQ-275
    :test-id: SEG-TS-164
    """
    other = support.case_need("T-OTHER", "test_alpha", "tests/mod_a", type="test_other")
    needs = support.needs_of(support.document_of(support.TEST_CASES_EXPORT)).values()
    export = support.export_of(
        tmp_path, [n for n in needs if n["type"] == "test_case"] + [other], "typed"
    )
    path = _specifications(tmp_path, export, "modules", **{support.KEY_TYPES: ["test_case"]})
    nodes, edges = support.records(path)
    assert set(nodes) == {"T-ALPHA", "T-GAMMA"}
    assert not [edge for edge in edges if edge.from_id == "T-OTHER"]


def test_without_configured_types_every_need_supplies_a_record(tmp_path: Path) -> None:
    """Without configured types, every need supplies a record.

    No type is configured. The test-case export holds T-ALPHA of the type
    test_case and T-GAMMA of the type test_other, both with a symbol the Doxygen
    tree locates. The extractor supplies a record for each of them.

    :verifies: SEG-SREQ-276
    :test-id: SEG-TS-165
    """
    export = support.export_of(
        tmp_path,
        [
            support.case_need("T-ALPHA", "test_alpha", "tests/mod_a"),
            support.case_need("T-GAMMA", "test_gamma", "tests/mod_b", type="test_other"),
        ],
        "untyped",
    )
    nodes, _ = support.records(_specifications(tmp_path, export, "modules"))
    assert set(nodes) == {"T-ALPHA", "T-GAMMA"}


def test_a_need_of_another_type_is_not_refused(tmp_path: Path) -> None:
    """A need of another type is not refused.

    The types {test_case} are configured. The test-case export holds a need of
    the type test_procedure that has no symbol field, and one of the type
    test_other with an empty symbol. Building the extractor and taking every
    record raises no error, and the records are those of the needs of the type
    test_case.

    :verifies: SEG-SREQ-277
    :test-id: SEG-TS-166
    """
    needs = list(support.needs_of(support.document_of(support.TEST_CASES_EXPORT)).values())
    needs.append(support.case_need("T-EMPTY", "", "tests/mod_a", type="test_other"))
    export = support.export_of(tmp_path, needs, "mixed")
    path = _specifications(tmp_path, export, "modules", **{support.KEY_TYPES: ["test_case"]})
    nodes, _ = support.records(path)
    assert set(nodes) == {"T-ALPHA", "T-GAMMA"}


def test_a_shared_symbol_is_narrowed_by_the_test_module(tmp_path: Path) -> None:
    """A symbol that several members share is narrowed by the test module.

    The Doxygen tree holds three members named test_shared, in tests/mod_a,
    tests/mod_ab and tests/mod_b. The need T-SHARED-A names the test module
    tests/mod_a. The need T-SHARED-B names tests/mod_b. Each need is located
    through the member inside its module. Its specHash equals the SHA-256 of the
    comment above that member, and its anchor names that member's file. The
    directory tests/mod_ab is not inside tests/mod_a.

    A second tree holds the name only in tests/mod_ab and tests/mod_b. There, a
    need that names tests/mod_a is an error, because no member lies inside it.

    :verifies: SEG-SREQ-278
    :test-id: SEG-TS-167
    """
    export = support.export_of(
        tmp_path,
        [_shared_need("tests/mod_a", "T-SHARED-A"), _shared_need("tests/mod_b", "T-SHARED-B")],
        "shared",
    )
    nodes, _ = support.records(_specifications(tmp_path, export))
    for ident, tag, file in (
        ("T-SHARED-A", "T-SHARED-A", SPEC_FILE_A),
        ("T-SHARED-B", "T-SHARED-B", SPEC_FILE_B),
    ):
        anchor = nodes[ident].content_anchors["specHash"]
        lines = support.file_lines(support.REPOS / "suite", file)
        assert anchor.digest == support.sha(support.comment_run(lines, tag))
        assert anchor.path == file
    narrow = support.export_of(tmp_path, [_shared_need("tests/mod_a", "T-NONE")], "none")
    _refused(_specifications(tmp_path, narrow, "modules-component"), "T-NONE")


def test_the_test_module_is_compared_with_the_path_after_the_prefix(tmp_path: Path) -> None:
    """The test module is compared with the file's path after the prefix is removed.

    The Doxygen tree names three members test_shared, in the files
    suite/tests/mod_a/src/main.c, suite/tests/mod_ab/src/main.c and
    suite/tests/mod_b/src/main.c. The prefix suite/ is configured. The need
    T-SHARED-A names the test module tests/mod_a. It is located through the member
    in mod_a: its specHash equals the SHA-256 of the comment above that member, and
    its anchor names tests/mod_a/src/main.c. A need that names the module
    suite/tests/mod_a is an error, because no path inside the repository lies in it.

    :verifies: SEG-SREQ-278
    :test-id: SEG-TS-194
    """
    prefix = {support.KEY_PREFIX: "suite/"}
    export = support.export_of(tmp_path, [_shared_need("tests/mod_a", "T-SHARED-A")], "after")
    nodes, _ = support.records(_specifications(tmp_path, export, "prefixed-modules", **prefix))
    anchor = nodes["T-SHARED-A"].content_anchors["specHash"]
    lines = support.file_lines(support.REPOS / "suite", SPEC_FILE_A)
    assert anchor.digest == support.sha(support.comment_run(lines, "T-SHARED-A"))
    assert anchor.path == SPEC_FILE_A
    before = support.export_of(tmp_path, [_shared_need("suite/tests/mod_a", "T-WITH")], "before")
    _refused(_specifications(tmp_path, before, "prefixed-modules", **prefix), "T-WITH")


def test_a_doxygen_path_is_mapped_into_the_repository_by_the_prefix(tmp_path: Path) -> None:
    """A Doxygen path is mapped into the repository by a configured prefix.

    The Doxygen tree for tests names the file suite/tests/mod_a/src/main.c, and
    the tree for implementations names lib-src/include/lib.h. The prefixes suite/
    and lib-src/ are configured, one for each tree. The specHash of T-ALPHA equals
    the SHA-256 of the comment above test_alpha in tests/mod_a/src/main.c of the
    repository suite. The apiHash of I-LIB-MAX equals the digest of the comment
    and the define line of LIB_MAX in include/lib.h of the repository lib.

    :verifies: SEG-SREQ-279
    :test-id: SEG-TS-168
    """
    path = _two_streams(tmp_path)
    nodes, _ = support.records(path)
    suite = support.file_lines(support.REPOS / "suite", SPEC_FILE_A)
    assert nodes["T-ALPHA"].content_anchors["specHash"].digest == support.sha(
        support.comment_run(suite, "T-ALPHA")
    )
    header = support.file_lines(support.REPOS / "lib", "include/lib.h")
    (define,) = [n for n, text in enumerate(header, 1) if b"#define LIB_MAX" in text]
    assert nodes["I-LIB-MAX"].content_anchors["apiHash"].digest == support.sha(
        support.run_of(header, define - 3, define)
    )


def test_a_path_outside_the_prefix_is_an_error_and_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that does not begin with the prefix is an error, and the file is not read.

    The prefix suite/ is configured. In a copy of the Doxygen tree, the path of
    test_alpha begins with other/. That text has as many characters as the prefix.
    A readable file stands at other/tests/mod_a/src/main.c in the repository.
    Taking the records raises a source error that names T-ALPHA. The file under
    other/ is not opened. The file tests/mod_a/src/main.c is not opened either. Removing
    the first six characters reaches it.

    :verifies: SEG-SREQ-280
    :test-id: SEG-TS-169
    """
    repositories = support.copied_repositories(tmp_path)
    decoy = repositories["suite"] / "other" / "tests" / "mod_a" / "src" / "main.c"
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes((support.REPOS / "suite" / SPEC_FILE_A).read_bytes())
    tree = support.rewritten(tmp_path, "prefixed-spec", "suite/tests", "other/tests", "outside")
    block = support.specifications_block(**{support.KEY_PREFIX: "suite/"})
    block.update(doxygen=str(tree), export=str(_alpha_export(tmp_path)))
    path = support.configuration(
        tmp_path, specifications=block, default_repository="suite", repositories=repositories
    )
    opened = _opened(monkeypatch)
    _refused(path, "T-ALPHA")
    assert os.path.realpath(decoy) not in opened
    real = repositories["suite"] / SPEC_FILE_A
    assert os.path.realpath(real) not in opened


def test_an_anchor_names_the_repository_of_its_stream_and_the_path_inside_it(
    tmp_path: Path,
) -> None:
    """An anchor names the repository of its stream and the path inside it.

    The readers name three repositories: docs, suite and lib, and no default
    repository is configured. Each anchor of T-ALPHA names the repository suite
    and the path tests/mod_a/src/main.c, with no prefix in it. Each anchor of
    I-LIB-MAX names the repository lib and the path include/lib.h. Each anchor of
    R-1 names the repository docs.

    :verifies: SEG-SREQ-281
    :test-id: SEG-TS-170
    """
    path = _two_streams(tmp_path, with_requirements=True)
    nodes, _ = support.records(path)
    for name in ("specHash", "implHash"):
        anchor = nodes["T-ALPHA"].content_anchors[name]
        assert (anchor.repository, anchor.path) == ("suite", SPEC_FILE_A)
    for name in ("apiHash", "bodyHash"):
        anchor = nodes["I-LIB-MAX"].content_anchors[name]
        assert (anchor.repository, anchor.path) == ("lib", "include/lib.h")
    assert nodes["R-1"].content_anchors[support.CONTENT_HASH].repository == "docs"


def test_after_the_module_choice_not_exactly_one_member_is_an_error(tmp_path: Path) -> None:
    """After the choice by test module, anything but exactly one member is an error.

    Three needs name the symbol test_shared, and each extraction is refused with
    an error that names the need. T-TWICE names the module tests/mod_a, where the
    Doxygen tree holds two members of that name. T-NO-MODULE names no module, and
    the tree holds three members. T-ELSEWHERE names the module tests/other, which
    holds none.

    :verifies: SEG-SREQ-161
    :test-id: SEG-TS-188
    """
    twice = support.export_of(tmp_path, [_shared_need("tests/mod_a", "T-TWICE")], "twice")
    _refused(_specifications(tmp_path, twice, "modules-twice"), "T-TWICE")
    bare = support.export_of(tmp_path, [_shared_need(None, "T-NO-MODULE")], "bare")
    _refused(_specifications(tmp_path, bare, "modules"), "T-NO-MODULE")
    elsewhere = support.export_of(tmp_path, [_shared_need("tests/other", "T-ELSEWHERE")], "else")
    _refused(_specifications(tmp_path, elsewhere, "modules"), "T-ELSEWHERE")


def test_a_path_outside_the_repository_of_the_stream_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path outside the repository configured for the node's stream is an error.

    The default repository is docs and the test stream names the repository
    suite. In a copy of the Doxygen tree the path of test_alpha is
    ../docs/reqs/alpha.sdoc, a readable file in the repository docs and outside the
    repository suite. Taking the records raises a source error that names T-ALPHA,
    and the file is not opened.

    :verifies: SEG-SREQ-162
    :test-id: SEG-TS-189
    """
    tree = support.rewritten(
        tmp_path, "prefixed-spec", "suite/tests/mod_a/src/main.c", "../docs/reqs/alpha.sdoc", "out"
    )
    block = support.specifications_block(**{support.KEY_REPOSITORY: "suite"})
    block.update(doxygen=str(tree), export=str(_alpha_export(tmp_path)))
    path = support.configuration(tmp_path, specifications=block, default_repository="docs")
    outside = support.REPOS / "docs" / "reqs" / "alpha.sdoc"
    opened = _opened(monkeypatch)
    _refused(path, "T-ALPHA")
    assert os.path.realpath(outside) not in opened
