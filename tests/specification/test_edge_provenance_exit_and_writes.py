"""Verification suite for the exit status of edge show and for its reads of a case.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Two
rules hold for every case, with or without a history. What the history records
never changes the exit status. The reads of the history change nothing in the
case: not a file of the case, not its history, not its index.

These rules already hold today, because edge show reads no history yet. The tests
are guards. They keep the rules true when the read of the history is built. The
tests of the write rule use an index that is out of date, and a control step that
shows that a plain ``git status`` changes the index of the same case. So the test
can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case

from . import extraction_support as base
from . import provenance_support as support
from .provenance_support import ALICE, CAROL, moment

pytestmark = support.requires_git


def test_the_history_never_changes_the_exit_status_of_edge_show(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exit status of edge show is the same for every history that the case can have.

    The same affirmed edge is shown in eight cases. The first has no history, as a
    control. The others have a commit that holds the event, a commit with a bad
    signature, an event that no commit holds, a case copied with no history, a case
    inside another repository, a repository that cannot be read, and a shallow
    history. In every case, edge show gives the same exit status as in the control,
    in text and in JSON. The status of the control is 0.

    :verifies: SEG-SREQ-303
    :test-id: SEG-TS-283
    """
    support.isolate(monkeypatch, tmp_path)
    support.sign_with_stand_in(monkeypatch, tmp_path)
    control, _ = support.case_copied(tmp_path / "control")
    expected = support.show(control, capsys).status
    assert expected == 0
    committed, _ = support.case_committed(tmp_path / "committed")
    bad, _ = support.case_committed(tmp_path / "bad", signature="B")
    draft = support.case_draft(tmp_path / "draft")
    copied, _ = support.case_copied(tmp_path / "copied")
    nested, _ = support.case_nested(tmp_path / "nested")
    unreadable = support.case_unreadable(tmp_path / "unreadable")
    shallow, _, _, _ = support.case_shallow(tmp_path / "shallow")
    places = {
        "committed": support.where(committed),
        "bad signature": support.where(bad),
        "draft": support.where(draft),
        "copied": copied,
        "nested": nested,
        "unreadable": support.where(unreadable),
        "shallow": shallow,
    }
    for name, place in places.items():
        assert support.show(place, capsys).status == expected, name


def test_edge_show_changes_nothing_in_a_case_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show performs no version-control write against the case, not even to its index.

    A case is a git repository with one committed event. The recorded modification
    time of every file of the case is changed, so the index of the repository is out
    of date. A plain git status writes a new index in such a repository. edge show
    runs, in text and in JSON, and exits with status 0. Every file under the .git
    directory of the case is the same after the command. The same holds for every
    file of the working tree. The last step is a control: a plain git status in the
    same repository changes a file under .git.

    :verifies: SEG-SREQ-116
    :test-id: SEG-TS-284
    """
    support.isolate(monkeypatch, tmp_path)
    fixture, _ = support.case_committed(tmp_path)
    support.make_stale_index(fixture.case)
    git_before = base.snapshot(fixture.case / ".git")
    tree_before = base.worktree(fixture.case)
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert base.snapshot(fixture.case / ".git") == git_before
    assert base.worktree(fixture.case) == tree_before
    assert support.control_writes_the_index(fixture.case, fixture.case / ".git")


def test_edge_show_changes_nothing_in_a_case_that_is_a_worktree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show performs no version-control write against a case that is a worktree.

    A case is a worktree of another repository, on a branch of its own, with one
    committed event. The recorded modification time of every file of the case is
    changed, so its index is out of date. The index of a worktree is under the .git
    directory of the first repository. edge show runs, in text and in JSON, and exits
    with status 0. Every file under the .git directory of the first repository is the
    same after the command. The same holds for every file of the worktree. The last
    step is a control: a plain git status in the worktree changes a file under that
    .git directory.

    :verifies: SEG-SREQ-116
    :test-id: SEG-TS-285
    """
    support.isolate(monkeypatch, tmp_path)
    host = tmp_path / "host"
    worktree = tmp_path / "worktree"
    support.make_worktree(host, worktree)
    fixture = support.build(tmp_path / "fixture")
    case.AffirmationStore(root=worktree).initialize()
    support.commit(worktree, "start the case", committer=CAROL, committed=moment(0))
    support.affirm(fixture, case=worktree)
    support.commit(worktree, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.make_stale_index(worktree)
    git_before = base.snapshot(host / ".git")
    tree_before = base.worktree(worktree)
    shown = support.show(support.where(fixture, worktree), capsys)
    assert shown.status == 0
    assert base.snapshot(host / ".git") == git_before
    assert base.worktree(worktree) == tree_before
    assert support.control_writes_the_index(worktree, host / ".git")
