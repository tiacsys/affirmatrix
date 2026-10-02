"""Verification suite for the claim that ``node show`` writes nothing.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
command reads the case, the current stream and the content repositories. The
tests compare the files before and after the command, for every exit status that
the command gives.

The first test takes the SHA-256 of every file of the case. The second builds a
git repository in ``tmp_path``. The index of the repository is out of date. Its
working tree has a change that is not committed, as in the tests of ``case sync``.
A plain ``git status`` writes a new index in such a repository. The test takes the
SHA-256 of every file under the ``.git`` directory before and after the command.
Its last step is a control: a plain ``git status`` in the same repository changes
the index. So the test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as base
from . import node_show_support as support

pytestmark = support.requires_git


def test_node_show_changes_no_file_of_the_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show changes no file of the case, for each exit status it gives.

    The case holds three requirements. The test takes the SHA-256 of every file of
    the case. Then node show runs for four nodes. A matching node exits with status
    0. A differing node exits with status 1. A node that the current stream no
    longer holds exits with status 1. An identifier that the case does not hold
    exits with status 2. After each command, the files of the case are the same.
    No file is added or removed.

    :verifies: SEG-SREQ-324
    :test-id: SEG-TS-251
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    fixture.rewrite("REQ-B", "a changed statement\n")
    support.drop_requirement(fixture, "REQ-C")
    before = base.snapshot(fixture.case)
    outcomes = {"REQ-A": 0, "REQ-B": 1, "REQ-C": 1, "REQ-NONE": 2}
    for local_id, status in outcomes.items():
        assert support.show(where, local_id, capsys).status == status, local_id
        assert base.snapshot(fixture.case) == before, local_id


def test_node_show_writes_nothing_in_the_content_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show performs no write in the content repository, not even to its index.

    A content repository has an out-of-date index and a change that is not
    committed. The change is in a file that one node anchors. Running node show
    for that node and for a node that anchors another file exits with status 1
    and with status 0. Every file under the .git directory of the repository is
    the same after the commands. The same holds for every file of the working tree.

    :verifies: SEG-SREQ-324
    :test-id: SEG-TS-252
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    support.stale_checkout(fixture, "REQ-C")
    git_before = base.snapshot(fixture.repository / ".git")
    tree_before = base.worktree(fixture.repository)
    where = support.place(fixture)
    assert support.show(where, "REQ-C", capsys).status == 1
    assert support.show(where, "REQ-B", capsys).status == 0
    assert base.snapshot(fixture.repository / ".git") == git_before
    assert base.worktree(fixture.repository) == tree_before
    assert support.control_writes_the_index(fixture.repository)
