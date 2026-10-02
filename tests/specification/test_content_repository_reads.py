"""Verification suite for the reads that the command line makes in a content repository.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds a git repository in ``tmp_path`` whose index is out of date, and whose
working tree has a change that is not committed. A plain ``git status`` writes
a new index in such a repository. Each test takes the SHA-256 of every file
under the ``.git`` directory before and after the command. A test passes when the two are the same.

The last step of each test is a control. It runs a plain ``git status`` in the same
repository and checks that this changes the index. So the test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as support

pytestmark = support.requires_git


def _stale_checkout(tmp_path: Path):
    fixture = support.build(tmp_path)
    fixture.rewrite("REQ-C", "an edit that nobody committed\n")
    support.make_index_stale(fixture.repository)
    return fixture


def _control_writes_the_index(repository: Path) -> bool:
    before = support.snapshot(repository / ".git")
    support.git(repository, "status", "--porcelain=v1")
    return support.snapshot(repository / ".git") != before


def test_case_sync_writes_nothing_in_the_content_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync performs no write in the content repository, not even to its index.

    A content repository has an out-of-date index and a change that is not
    committed. Running case sync over it exits with status 0. Every file under
    the .git directory of the repository is the same after the command. The same
    holds for every file of the working tree.

    :verifies: SEG-SREQ-115
    :test-id: SEG-TS-216
    """
    fixture = _stale_checkout(tmp_path)
    git_before = support.snapshot(fixture.repository / ".git")
    tree_before = support.worktree(fixture.repository)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert support.snapshot(fixture.repository / ".git") == git_before
    assert support.worktree(fixture.repository) == tree_before
    assert _control_writes_the_index(fixture.repository)


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-115: the status read of edge affirm can refresh the index"
)
def test_edge_affirm_writes_nothing_in_the_content_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm performs no write in the content repository, not even to its index.

    A content repository has an out-of-date index and a change that is not
    committed. The change is in a file that the edge does not anchor. Running
    edge affirm over it exits with status 0. Every file under the .git directory
    of the repository is the same after the command. The same holds for every
    file of the working tree.

    :verifies: SEG-SREQ-115
    :test-id: SEG-TS-217
    """
    fixture = _stale_checkout(tmp_path)
    git_before = support.snapshot(fixture.repository / ".git")
    tree_before = support.worktree(fixture.repository)
    status, _ = support.affirm(fixture, capsys)
    assert status == 0
    assert support.snapshot(fixture.repository / ".git") == git_before
    assert support.worktree(fixture.repository) == tree_before
    assert _control_writes_the_index(fixture.repository)
