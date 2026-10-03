"""Verification suite for the path prefix and the test module of the content extractor.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
configured path prefix is text and is removed as written, so a prefix with no
trailing separator leaves a remainder that begins with one. The test module of a
test-case need narrows the members that share a symbol; its value can be absent,
null, empty or wrong.

The tests read the small synthetic fixture under ``tests/fixtures/capture_shape/``
and reach the extractor through the configuration file. The prefix ``inc`` is
unlike the name of any fixture directory, so a message that holds it names the
prefix and not a directory. Each variant of an input is built in the test, in a
temporary directory.
"""

from __future__ import annotations

import builtins
import io
import os
import re
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.sources import SourceError

from . import capture_support as support
from .need_types_support import red

PREFIX = "inc"
LIBRARY_PREFIX = "libsrc"
ALPHA_PATH = "inc/tests/mod_a/src/main.c"
GAMMA_PATH = "inc/tests/mod_b/src/main.c"
LIBRARY_PATH = "libsrc/include/lib.h"
REAL_FILE = support.REPOS / "suite" / "tests" / "mod_a" / "src" / "main.c"


def _alpha(tmp_path: Path) -> Path:
    return support.export_of(
        tmp_path, [support.case_need("T-ALPHA", "test_alpha", "tests/mod_a")], "alpha"
    )


def _prefixed_tree(tmp_path: Path) -> Path:
    """The Doxygen tree of the tests, with the prefix ``inc`` where the fixture has ``suite``."""
    return support.rewritten(tmp_path, "prefixed-spec", "suite/tests", "inc/tests", "inc-tree")


def _alone(prefix: str) -> str:
    """A pattern for the prefix as a text of its own: not inside a longer word or path."""
    return rf"(?<![\w/.-]){re.escape(prefix)}(?![\w/.-])"


def _specifications(tmp_path: Path, export: Path, prefix: str, tree: Path | None = None) -> Path:
    block = support.specifications_block(
        export=str(export), doxygen=str(tree or _prefixed_tree(tmp_path))
    )
    block[support.KEY_PREFIX] = prefix
    return support.configuration(tmp_path, specifications=block, default_repository="suite")


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


def _refusal(path: Path) -> str:
    """The message of the source error that taking every record raises."""
    with pytest.raises(SourceError) as caught:
        support.records(path)
    return str(caught.value)


@red(342, "the error names neither the path nor the prefix")
def test_a_path_whose_remainder_after_the_prefix_is_not_a_relative_path_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path whose remainder after the prefix is empty or begins with a separator is an error.

    The Doxygen tree names test_alpha in the file inc/tests/mod_a/src/main.c. With
    the prefix inc/ configured, the extractor locates T-ALPHA. With the prefix inc
    configured, the remainder is /tests/mod_a/src/main.c. With the whole path
    inc/tests/mod_a/src/main.c as the prefix, the remainder is empty. In each of
    those two cases taking the records raises a source error that names T-ALPHA,
    the path inc/tests/mod_a/src/main.c and the prefix. The file
    tests/mod_a/src/main.c of the repository is not opened.

    :verifies: SEG-SREQ-342
    :test-id: SEG-TS-327
    """
    export = _alpha(tmp_path)
    nodes, _ = support.records(_specifications(tmp_path / "control", export, "inc/"))
    assert set(nodes) == {"T-ALPHA"}

    opened = _opened(monkeypatch)
    separator = _refusal(_specifications(tmp_path / "separator", export, PREFIX))
    whole = _refusal(_specifications(tmp_path / "whole", export, ALPHA_PATH))

    assert "T-ALPHA" in separator and "T-ALPHA" in whole
    assert ALPHA_PATH in separator and ALPHA_PATH in whole
    assert re.search(_alone(PREFIX), separator), separator
    assert os.path.realpath(REAL_FILE) not in opened


def _both_streams(tmp_path: Path, tests: str, library: str) -> Path:
    """A configuration of the two streams with the prefixes given, over trees that use them."""
    tests_tree = _prefixed_tree(tmp_path)
    library_tree = support.rewritten(tmp_path, "prefixed-impl", "lib-src/", "libsrc/", "lib-tree")
    specifications = support.specifications_block(
        doxygen=str(tests_tree),
        **{
            support.KEY_PREFIX: tests,
            support.KEY_REPOSITORY: "suite",
            support.KEY_TYPES: ["test_case"],
        },
    )
    implementations = support.implementations_block(
        doxygen=str(library_tree),
        **{support.KEY_PREFIX: library, support.KEY_REPOSITORY: "lib", support.KEY_TYPES: ["impl"]},
    )
    return support.configuration(
        tmp_path, specifications=specifications, implementations=implementations
    )


@red(342, "the line of a node holds neither its path nor the prefix")
def test_case_sync_names_every_node_whose_path_does_not_fit_the_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync names every node whose path does not fit its prefix, with the path and the prefix.

    The configuration gives the test stream the prefix inc and the
    implementation stream the prefix libsrc, each with no trailing separator. The
    paths of the Doxygen trees are inc/tests/mod_a/src/main.c,
    inc/tests/mod_b/src/main.c and libsrc/include/lib.h. Running case sync exits
    with status 2. Its output names the four needs T-ALPHA, T-GAMMA, I-LIB-MAX and
    I-LIB-MIN, each on a line of its own. The line of each holds the path of its
    node and the prefix of its stream. A control with the prefixes inc/ and
    libsrc/ exits with status 0.

    :verifies: SEG-SREQ-342
    :test-id: SEG-TS-328
    """
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    arguments = ["case", "sync", "--case", str(root), "--config"]
    control = _both_streams(tmp_path / "control", "inc/", "libsrc/")
    assert main([*arguments, str(control)]) == 0
    capsys.readouterr()

    status = main([*arguments, str(_both_streams(tmp_path / "bad", PREFIX, LIBRARY_PREFIX))])
    lines = capsys.readouterr().out.splitlines()

    assert status == 2
    expected = {
        "T-ALPHA": (ALPHA_PATH, PREFIX),
        "T-GAMMA": (GAMMA_PATH, PREFIX),
        "I-LIB-MAX": (LIBRARY_PATH, LIBRARY_PREFIX),
        "I-LIB-MIN": (LIBRARY_PATH, LIBRARY_PREFIX),
    }
    for need, (path, prefix) in expected.items():
        (line,) = [text for text in lines if need in text]
        assert path in line, line
        assert re.search(_alone(prefix), line), line


def _module_need(module: Any, ident: str = "T-ALPHA", symbol: str = "test_alpha") -> dict[str, Any]:
    """A test-case need whose test module is ``module``; ``"absent"`` leaves the key out."""
    need = support.case_need(ident, symbol)
    if module == "absent":
        del need["test_module"]
    else:
        need["test_module"] = module
    return need


def _modules(tmp_path: Path, needs: list[dict[str, Any]], name: str) -> Path:
    """A configuration over the Doxygen tree that names test_shared in three directories."""
    export = support.export_of(tmp_path, needs, name)
    block = support.specifications_block("modules", export=str(export))
    return support.configuration(tmp_path / name, specifications=block, default_repository="suite")


def test_a_test_module_that_is_absent_null_or_empty_names_no_module(tmp_path: Path) -> None:
    """A test module that is absent, null or empty text names no test module.

    The Doxygen tree names test_alpha once and test_shared in three directories.
    For each of the three forms, a need with no test_module key, a need whose
    test_module is null and a need whose test_module is the empty text, the
    extractor locates the need that names test_alpha, with no narrowing. It
    refuses the need that names test_shared with an error that names that need, and
    the error is the same for the three forms.

    :verifies: SEG-SREQ-343
    :test-id: SEG-TS-329
    """
    refusals = []
    for form in ("absent", None, ""):
        label = f"form-{form}"
        located = _modules(tmp_path, [_module_need(form, "T-ALPHA")], f"{label}-alpha")
        nodes, _ = support.records(located)
        assert set(nodes) == {"T-ALPHA"}, form

        shared = _modules(tmp_path, [_module_need(form, "T-SHARED", "test_shared")], f"{label}-s")
        message = _refusal(shared)
        (line,) = [text for text in message.splitlines() if "T-SHARED" in text]
        refusals.append(line)
    assert len(set(refusals)) == 1


@red(344, "a test module that is not text counts as none and the need is located")
@pytest.mark.parametrize("module", [7, ["tests/mod_a"], {"path": "tests/mod_a"}, True])
def test_a_test_module_that_is_not_text_is_an_error_for_that_need(
    module: Any, tmp_path: Path
) -> None:
    """A test module that is present and is neither null nor text is an error for that need.

    The Doxygen tree names test_alpha in one file. The test-case export holds T-BAD,
    a need that names test_alpha and whose test_module is a number, a list, an
    object or a boolean, and T-GOOD, a need whose module is the text tests/mod_b. For
    each value, the extractor supplies the record of T-GOOD and then raises a source
    error that names T-BAD and does not name T-GOOD. A control whose test_module
    is the text tests/mod_a supplies a record for T-BAD.

    :verifies: SEG-SREQ-344
    :test-id: SEG-TS-330
    """
    good = support.case_need("T-GOOD", "test_gamma", "tests/mod_b")
    control = _modules(tmp_path, [_module_need("tests/mod_a", "T-BAD"), good], "control")
    assert {n.local_id for n in support.producer_of(control).nodes()} == {"T-BAD", "T-GOOD"}

    path = _modules(tmp_path, [_module_need(module, "T-BAD"), good], "bad")
    supplied = []
    with pytest.raises(SourceError) as caught:
        for node in support.producer_of(path).nodes():
            supplied.append(node.local_id)
    assert supplied == ["T-GOOD"]
    assert "T-BAD" in str(caught.value)
    assert "T-GOOD" not in str(caught.value)


@red(342, "a shared symbol with a bad prefix gets the module error and not the prefix error")
def test_a_shared_symbol_with_a_prefix_that_leaves_no_path_gets_the_prefix_error(
    tmp_path: Path,
) -> None:
    """A shared symbol with a prefix that leaves no relative path gets the prefix error.

    The Doxygen tree names test_shared in three files, one in each of the
    directories tests/mod_a, tests/mod_ab and tests/mod_b. The need T-SHARED
    names the test module tests/mod_a. With the prefix tests configured, the
    remainder of each path begins with a separator. With the whole path
    tests/mod_a/src/main.c as the prefix, the remainder of that path is empty. In
    each case taking the records raises a source error that names T-SHARED, a path
    of the tree and the prefix. The error does not say how many members lie within
    the test module.

    :verifies: SEG-SREQ-342
    :test-id: SEG-TS-334
    """
    export = support.export_of(
        tmp_path, [support.case_need("T-SHARED", "test_shared", "tests/mod_a")], "shared"
    )
    for prefix in ("tests", "tests/mod_a/src/main.c"):
        block = support.specifications_block("modules", export=str(export))
        block[support.KEY_PREFIX] = prefix
        path = support.configuration(
            tmp_path / re.sub(r"\W", "_", prefix),
            specifications=block,
            default_repository="suite",
        )
        message = _refusal(path)
        (line,) = [text for text in message.splitlines() if "T-SHARED" in text]
        assert re.search(r"tests/mod_a?b?/src/main\.c", line), line
        if prefix == "tests":
            assert re.search(_alone(prefix), line), line
        assert "lie within" not in line, line
