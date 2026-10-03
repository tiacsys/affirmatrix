"""Verification suite for the error about a repository path of the content extractor.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
repository path in the configuration can be wrong as a whole: the directory
does not exist, or the path is a file. The content extractor must say so once,
by the name the configuration gives the repository and with the path, and not
with one line for each need that reads through it. Two readers of the project
read through a repository: the implementation stream and the test stream of the
content extractor. The requirements reader names a repository too, but it opens
no file in it.

Every fixture is built by the test, in ``tmp_path`` (``every_need_support.World``):
three plain directories with the files of three streams of three needs each,
and a configuration file that gives each repository a name that is not part of
its path. None of the directories is a version-control repository, so a path
that is wrong is the only fault. Which call raises the error, the one that builds
the producer or the one that takes its records, is not specified; a test reads
both. A test that goes through the command line runs ``case sync`` over an
initialized case and compares the files of the case before and after.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.cli import main

from . import every_need_support as support

_STRICT = pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-373: a bad repository path is reported per need, not once by name"
)

#: The configured names of the repositories, none of them part of any path.
DOCS, LIB, SUITE = "docs-config-name", "lib-config-name", "suite-config-name"
NAMES = {"requirements": DOCS, "library": LIB, "suite": SUITE}
#: The need identifiers and symbols of the streams, between quotes as an error writes them.
#: No line about a path holds one. A bare name would also match the name of a test directory.
NEEDS = tuple(
    f"'{name}'"
    for name in (
        "I-M_ONE",
        "I-M_TWO",
        "I-M_THREE",
        "T-ONE",
        "T-TWO",
        "T-THREE",
        "M_ONE",
        "M_TWO",
        "M_THREE",
        "test_one",
        "test_two",
        "test_three",
    )
)
SYMBOLS = ()


def _error(world: support.World, **choices):
    cfg = world.write(names=choices.pop("names", NAMES), **choices)
    error = support.drained(cfg)
    assert error is not None
    return error


def _naming(error: BaseException, name: str) -> list[str]:
    return [line for line in support.lines_of(error) if name in line]


def _once(error: BaseException, name: str) -> str:
    """The one line that names the repository ``name``; fail, and show the error, if not one."""
    named = _naming(error, name)
    assert len(named) == 1, f"{len(named)} lines name {name!r}:\n{error}"
    return named[0]


def _about_needs(error: BaseException) -> list[str]:
    """The lines that hold the identifier or the symbol of any need of the streams."""
    return [
        line for line in support.lines_of(error) if any(item in line for item in (*NEEDS, *SYMBOLS))
    ]


def _case(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    return root


def _files(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_world_with_three_plain_directories_is_the_control(tmp_path: Path) -> None:
    """A producer over three plain directories that hold the files is read without an error.

    The three repositories of the fixtures are plain directories, with no
    version-control data, and each holds the files its stream reads. Building the
    producer and taking its nodes and edges raises no error. The producer supplies
    nine nodes. This is the control for the specifications that follow, so each of
    them fails for the repository path alone.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-403
    """
    cfg = support.World(tmp_path).write(names=NAMES)
    assert support.drained(cfg) is None
    assert len(list(support.producer_of(cfg).nodes())) == 9


@_STRICT
def test_a_repository_path_that_does_not_exist_is_reported_once(tmp_path: Path) -> None:
    """A repository path that does not exist is reported once, by its name and with its path.

    The configuration maps the repository of the test stream to a path that does
    not exist. Three needs read through it. The producer is built and its records
    are taken. One source error is raised. Exactly one of its lines holds the
    configured name of the repository. That line also holds the configured path and
    says that the path does not exist. No line holds the identifier or the symbol of
    a need of that stream, and the other two repositories are not named.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-404
    """
    missing = tmp_path / "no-such-directory-one"
    error = _error(support.World(tmp_path), paths={"suite": missing})
    line = _once(error, SUITE)
    assert str(missing) in line and "does not exist" in line
    assert _about_needs(error) == []
    assert _naming(error, LIB) == [] and _naming(error, DOCS) == []


@_STRICT
def test_a_repository_path_that_is_a_file_is_reported_once(tmp_path: Path) -> None:
    """A repository path that is a file is reported once, by its name and with its path.

    The configuration maps the repository of the implementation stream to a path
    that is a file. Three needs read through it. The producer is built and its
    records are taken. One source error is raised. Exactly one of its lines holds
    the configured name of the repository. That line also holds the configured path
    and says that the path is not a directory. No line holds the identifier or the
    symbol of a need of that stream.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-405
    """
    plain = tmp_path / "plain-file-one"
    plain.write_text("text\n", encoding="utf-8")
    error = _error(support.World(tmp_path), paths={"library": plain})
    line = _once(error, LIB)
    assert str(plain) in line and "not a directory" in line
    assert _about_needs(error) == []


@_STRICT
def test_one_repository_that_both_streams_read_through_is_reported_once(tmp_path: Path) -> None:
    """A repository that both streams read through is reported once.

    The configuration gives the implementation stream and the test stream one
    repository name, and maps it to a path that does not exist. Six needs read
    through it. One source error is raised. Exactly one of its lines holds the
    configured name, and that line holds the path. No line holds the identifier or
    the symbol of a need.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-406
    """
    missing = tmp_path / "no-such-directory-shared"
    shared = "shared-config-name"
    error = _error(
        support.World(tmp_path),
        paths={"suite": missing},
        names={**NAMES, "library": shared, "suite": shared},
    )
    line = _once(error, shared)
    assert str(missing) in line
    assert _about_needs(error) == []


@_STRICT
def test_two_repositories_that_cannot_be_used_are_both_reported_in_one_error(
    tmp_path: Path,
) -> None:
    """Two repositories whose paths cannot be used are both reported in one error.

    The configuration maps the repository of the implementation stream to a path
    that does not exist, and the repository of the test stream to a path that is a
    file. The requirements repository is fine. One source error is raised. It has
    one line that holds the name of the first repository and its path, and one line
    that holds the name of the second repository and its path. No line holds the
    name of the requirements repository or the identifier or the symbol of any need.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-407
    """
    missing = tmp_path / "no-such-directory-two"
    plain = tmp_path / "plain-file-two"
    plain.write_text("text\n", encoding="utf-8")
    error = _error(support.World(tmp_path), paths={"library": missing, "suite": plain})
    library = _once(error, LIB)
    suite = _once(error, SUITE)
    assert str(missing) in library and str(plain) in suite
    assert library != suite
    assert _naming(error, DOCS) == []
    assert _about_needs(error) == []


def test_a_directory_that_is_not_a_version_control_repository_is_a_valid_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plain directory that holds the files is a valid repository path.

    The three repositories are plain directories that hold the files the streams
    read and no version-control data. Case sync over an initialized case exits with
    status 0 and prints the sync line. It prints, for each of the three configured
    names, a line that says that node records were written without an extraction
    revision. The case holds nine nodes, three for each stream.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-408
    """
    cfg = support.World(tmp_path).write(names=NAMES)
    root = _case(tmp_path)
    capsys.readouterr()
    status = main(["case", "sync", "--case", str(root), "--config", str(cfg)])
    lines = capsys.readouterr().out.splitlines()
    assert status == 0
    assert any(line.startswith("synced ") for line in lines)
    for name in (DOCS, LIB, SUITE):
        assert [line for line in lines if name in line and "no extraction revision" in line]
    assert len(list(case.AffirmationStore(root=root).nodes())) == 9


def test_a_repository_that_only_the_requirements_reader_names_is_not_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repository path that only the requirements reader reads through is not refused.

    The configuration maps the repository of the requirements reader to a path that
    does not exist. The other two repositories are fine. Building the producer and
    taking its records raises no error, and the producer supplies the three
    requirements. Case sync over an initialized case exits with status 0 and its
    output says nothing about a path that does not exist.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-409
    """
    missing = tmp_path / "no-such-directory-docs"
    cfg = support.World(tmp_path).write(names=NAMES, paths={"requirements": missing})
    assert support.drained(cfg) is None
    nodes = list(support.producer_of(cfg).nodes())
    assert [n.local_id for n in nodes if n.kind == "Requirement"] == ["R-1", "R-2", "R-3"]
    root = _case(tmp_path)
    capsys.readouterr()
    status = main(["case", "sync", "--case", str(root), "--config", str(cfg)])
    text = capsys.readouterr().out
    assert status == 0
    assert "does not exist" not in text and "not a directory" not in text


@_STRICT
def test_case_sync_over_a_missing_repository_exits_2_names_it_once_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case sync over a repository path that does not exist exits with status 2 and writes nothing.

    The configuration maps the repository of the test stream to a path that does not
    exist. Case sync over an initialized case exits with status 2. Its output has
    exactly one line that holds the configured name of the repository, and that line
    holds the path. No line holds the identifier or the symbol of a need. The files
    of the case are the same after the command as before it. The output holds no
    traceback.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-410
    """
    missing = tmp_path / "no-such-directory-sync"
    cfg = support.World(tmp_path).write(names=NAMES, paths={"suite": missing})
    root = _case(tmp_path)
    before = _files(root)
    capsys.readouterr()
    status = main(["case", "sync", "--case", str(root), "--config", str(cfg)])
    captured = capsys.readouterr()
    lines = (captured.out + captured.err).splitlines()
    assert status == 2
    named = [line for line in lines if SUITE in line]
    assert len(named) == 1, "\n".join(lines)
    assert str(missing) in named[0]
    assert [line for line in lines if any(item in line for item in (*NEEDS, *SYMBOLS))] == []
    assert "Traceback" not in captured.out + captured.err
    assert _files(root) == before


@_STRICT
def test_the_repository_line_comes_before_any_line_about_a_need(tmp_path: Path) -> None:
    """The line about a repository path comes before any line about a need.

    The configuration maps the repository of the implementation stream to a path
    that does not exist. The test stream reads through a repository that is a
    directory but lacks the test source file its Doxygen output names, so each of
    its needs has a fault of its own. One source error is raised. It has a line
    that holds the configured name of the first repository, and every line that
    holds the identifier or the symbol of a need comes after that line.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-411
    """
    world = support.World(tmp_path)
    (world.suite / "tests" / "cases.c").unlink()
    error = _error(world, paths={"library": tmp_path / "no-such-directory-first"})
    lines = support.lines_of(error)
    named = [n for n, line in enumerate(lines) if LIB in line]
    assert named, str(error)
    first = named[0]
    needs = [n for n, line in enumerate(lines) if any(i in line for i in (*NEEDS, *SYMBOLS))]
    assert all(n > first for n in needs)


@_STRICT
def test_several_bad_repositories_are_listed_sorted_by_configured_name(tmp_path: Path) -> None:
    """Several repositories whose paths cannot be used are listed sorted by configured name.

    The configuration names the repository of the implementation stream zeta-name
    and the repository of the test stream alpha-name, and maps both to a path that
    does not exist. The implementation stream comes first in the order of the
    streams, but the error lists the line of alpha-name before the line of
    zeta-name. Building the producer a second time gives an error with the same
    lines.

    :verifies: SEG-SREQ-373
    :test-id: SEG-TS-414
    """
    names = {**NAMES, "library": "zeta-name", "suite": "alpha-name"}
    paths = {"library": tmp_path / "no-such-zeta", "suite": tmp_path / "no-such-alpha"}
    world = support.World(tmp_path)
    error = _error(world, names=names, paths=paths)
    lines = support.lines_of(error)
    order = [name for line in lines for name in ("alpha-name", "zeta-name") if name in line]
    assert order == ["alpha-name", "zeta-name"]
    assert support.lines_of(_error(world, names=names, paths=paths)) == lines
