"""Verification suite for the environment that a repository read runs in.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
variable such as GIT_NAMESPACE changes no answer of the four reads, so a decoy
cannot show that the command removes it. These tests look at the environment that
each call of git gets instead.

Each test puts a stand-in ``git`` first on ``PATH``. The stand-in is a small
script in ``tmp_path``. It writes the arguments of each call to a log, with the
names of the seven variables that the call had, and then runs the real git without
them. The test sets all seven variables, and each one names a repository. The command
runs as an operator runs it. A test passes when the log holds the calls that
the verb has to make, and no call had one of the seven variables.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import evidence_support as evidence
from . import extraction_support as base
from . import node_show_support as nodes
from . import provenance_support as prov
from . import repository_reads_support as support

pytestmark = support.requires_git


def test_case_sync_runs_git_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """case sync runs every call of git without the seven variables that name a repository.

    A configuration maps a content repository. A second repository exists. All
    seven variables GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY,
    GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_COMMON_DIR and GIT_NAMESPACE are set, and
    each names the second repository. A stand-in git logs the environment of each
    call. Running case sync exits with status 0. The log holds calls for the
    revision, the status and the tree. In no call is one of the seven variables
    present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-302
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert {"rev-parse", "status", "ls-tree"} <= stand_in.subcommands()
    assert stand_in.leaks() == []


def test_edge_affirm_runs_git_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge affirm runs every call of git without the seven variables that name a repository.

    A configuration maps a content repository. A second repository exists. All
    seven variables are set, and each names the second repository. A stand-in git
    logs the environment of each call. Running edge affirm for the edge from REQ-B
    to REQ-A, with no revision given, exits with status 0. The log holds calls for
    the revision, the status and the tree. In no call is one of the seven variables
    present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-303
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    status, _ = support.affirm(fixture, capsys)
    assert status == 0
    assert {"rev-parse", "status", "ls-tree"} <= stand_in.subcommands()
    assert stand_in.leaks() == []


def test_node_show_runs_git_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show runs every call of git without the seven variables that name a repository.

    A case holds three requirements. A second repository exists. All seven
    variables are set, and each names the second repository. A stand-in git logs the
    environment of each call. Running node show for REQ-B exits with status 0. The
    log holds calls for the revision, the status and the tree. In no call is one of
    the seven variables present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-304
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    assert support.sync(fixture, capsys)[0] == 0
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    shown = nodes.show(nodes.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    assert {"rev-parse", "status", "ls-tree"} <= stand_in.subcommands()
    assert stand_in.leaks() == []


def test_edge_show_runs_the_before_content_read_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show runs the before-content read of git without the seven variables.

    An edge from REQ-B to REQ-A is affirmed, and then the text of both requirements
    changes and is committed. A second repository exists. All seven variables are
    set, and each names the second repository. A stand-in git logs the environment
    of each call. Running edge show with the options for verbose JSON exits with
    status 0. The log holds a call of the subcommand show. In no call is one of the
    seven variables present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-305
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    assert support.affirm(fixture, capsys)[0] == 0
    fixture.rewrite(prov.FROM, "a later statement of REQ-B\n")
    base.commit_all(fixture.repository, "change REQ-B")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    status, _ = support.show_before_content(nodes.place(fixture), capsys)
    assert status == 0
    assert "show" in stand_in.subcommands()
    assert stand_in.leaks() == []


def test_edge_show_runs_the_case_history_reads_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show runs every read of the history of the case without the seven variables.

    A case is a git repository, and one commit adds the review event of an edge. A
    second repository exists. All seven variables are set, and each names the second
    repository. A stand-in git logs the environment of each call. Running edge show
    exits with status 0, and the provenance of the edge is found. The log holds calls
    of the subcommands rev-parse, log and show. In no call is one of the seven
    variables present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-306
    """
    support.isolate(monkeypatch, tmp_path)
    fixture, recording = prov.case_committed(tmp_path / "world")
    decoy = support.make_case_decoy(fixture.case, tmp_path / "decoy")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    shown = prov.show(prov.where(fixture), capsys)
    assert shown.status == 0
    assert prov.is_found_at(shown, recording)
    assert {"rev-parse", "log", "show"} <= stand_in.subcommands()
    assert stand_in.leaks() == []


def test_a_repository_read_keeps_the_ceiling_and_the_config_variables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repository read keeps GIT_CEILING_DIRECTORIES and the GIT_CONFIG_COUNT settings.

    GIT_CEILING_DIRECTORIES names a directory, and GIT_CONFIG_COUNT with its key and
    value variables sets a git option. A stand-in git logs the environment of each
    call. Running case sync exits with status 0. The log holds calls. In each call,
    GIT_CEILING_DIRECTORIES and GIT_CONFIG_COUNT are still present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-307
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert stand_in.calls()
    assert stand_in.lacking() == []


def test_proof_check_reads_the_gate_revision_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """proof check reads the revision of the implementation repository without the seven variables.

    A configuration maps the implementation repository, which is clean. A second
    repository exists. All seven variables are set, and each names the second
    repository. A stand-in git logs the environment of each call. Running proof check
    for the scope SREQ-1, with no revision given, does not refuse the run. The log holds
    calls of the subcommands rev-parse and status. In no call is one of the seven
    variables present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-315
    """
    support.isolate(monkeypatch, tmp_path)
    world = evidence.make_world(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    support.point_all(monkeypatch, decoy)
    status, _ = evidence.run(capsys, "proof", "check", *world.args(), "--scope", "SREQ-1")
    assert status != 2
    assert {"rev-parse", "status"} <= stand_in.subcommands()
    assert stand_in.leaks() == []
