"""Verification suite for the writes that a repository read must not make, with a variable set.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds repositories in ``tmp_path`` whose index is out of date. A plain
``git status`` writes a new index in such a repository. One variable of the
environment names a decoy, and the command runs. A test takes the SHA-256 of every
file under the ``.git`` directories before and after the command, and of every file
of the working trees. A test passes when the two are the same.

The last step of each test is a control. It runs a plain ``git status`` with the same
variable set, and checks that this changes a file under a watched directory. So the
test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as base
from . import node_show_support as nodes
from . import provenance_support as prov
from . import repository_reads_support as support

pytestmark = support.requires_git

#: The variables with which a plain ``git status`` still runs and writes an index.
VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


def _stale_world(tmp_path: Path) -> tuple[base.Fixture, Path]:
    fixture = base.build(tmp_path / "world")
    fixture.rewrite("REQ-C", "an edit that nobody committed\n")
    decoy = support.make_decoy(tmp_path / "decoy", same_text=True)
    base.make_index_stale(fixture.repository)
    base.make_index_stale(decoy)
    return fixture, decoy


def _watched(fixture: base.Fixture, decoy: Path) -> dict[str, dict]:
    return {
        "content git": base.snapshot(fixture.repository / ".git"),
        "decoy git": base.snapshot(decoy / ".git"),
        "content tree": base.worktree(fixture.repository),
        "decoy tree": base.worktree(decoy),
    }


@pytest.mark.parametrize("variable", VARIABLES)
def test_case_sync_writes_nothing_in_either_repository_with_a_variable_set(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """case sync writes nothing in the content repository or in the decoy, with a variable set.

    A content repository has an out-of-date index and a change that is not
    committed. A second repository has an out-of-date index too. One variable of
    the environment names it: GIT_DIR, GIT_WORK_TREE or GIT_INDEX_FILE. Running case
    sync exits with status 0. Every file under the .git directory of each repository
    is the same after the command, and so is every file of each working tree.

    :verifies: SEG-SREQ-115
    :test-id: SEG-TS-299
    """
    support.isolate(monkeypatch, tmp_path)
    fixture, decoy = _stale_world(tmp_path)
    watched = [fixture.repository / ".git", decoy / ".git"]
    before = _watched(fixture, decoy)
    support.point(monkeypatch, variable, decoy)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert _watched(fixture, decoy) == before
    assert support.plain_status_writes(fixture.repository, variable, decoy, watched)


@pytest.mark.parametrize("variable", VARIABLES)
def test_edge_affirm_and_node_show_write_nothing_in_either_repository_with_a_variable_set(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge affirm and node show write nothing in the content repository or in the decoy.

    A content repository has an out-of-date index and a change that is not
    committed, in a file that the edge does not anchor. A second repository has an
    out-of-date index too. One variable of the environment names it: GIT_DIR,
    GIT_WORK_TREE or GIT_INDEX_FILE. The test runs node show for REQ-B. Then it runs
    edge affirm for the edge from REQ-B to REQ-A. Every file under the .git
    directory of each repository is the same after both commands. So is every file
    of each working tree.

    :verifies: SEG-SREQ-115
    :test-id: SEG-TS-300
    """
    support.isolate(monkeypatch, tmp_path)
    fixture, decoy = _stale_world(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    base.make_index_stale(fixture.repository)
    watched = [fixture.repository / ".git", decoy / ".git"]
    before = _watched(fixture, decoy)
    support.point(monkeypatch, variable, decoy)
    nodes.show(nodes.place(fixture), "REQ-B", capsys)
    support.affirm(fixture, capsys)
    assert _watched(fixture, decoy) == before
    assert support.plain_status_writes(fixture.repository, variable, decoy, watched)


@pytest.mark.parametrize("variable", ("GIT_DIR", "GIT_WORK_TREE"))
def test_edge_show_writes_nothing_under_the_git_directory_of_the_case_with_a_variable_set(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show writes nothing under the git directory of the case or of the decoy.

    A case is a git repository with an out-of-date index, and a commit holds the
    review event of an edge. A second repository holds a copy of the case, with an
    out-of-date index too. GIT_DIR or GIT_WORK_TREE names it. Running edge show
    exits with status 0. Every file under the .git directory of the case is the
    same after the command. So is every file under the .git directory of the second
    repository, and every file of both working trees.

    :verifies: SEG-SREQ-116
    :test-id: SEG-TS-301
    """
    support.isolate(monkeypatch, tmp_path)
    fixture, _ = prov.case_committed(tmp_path / "world")
    decoy = support.make_case_decoy(fixture.case, tmp_path / "decoy")
    base.make_index_stale(fixture.case)
    base.make_index_stale(decoy)
    watched = [fixture.case / ".git", decoy / ".git"]
    before = [base.snapshot(path) for path in watched]
    trees = [base.worktree(fixture.case), base.worktree(decoy)]
    support.point(monkeypatch, variable, decoy)
    shown = prov.show(prov.where(fixture), capsys)
    assert shown.status == 0
    assert [base.snapshot(path) for path in watched] == before
    assert [base.worktree(fixture.case), base.worktree(decoy)] == trees
    assert support.plain_status_writes(fixture.case, variable, decoy, watched)
