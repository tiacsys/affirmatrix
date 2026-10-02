"""Verification suite for the cases in which the history gives no answer, or a weaker one.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
cases: an affirmation that no commit holds, a case that is not a repository of its
own, a history that cannot be read, a case that is a worktree of another repository,
and a shallow history. In each case the report says what holds. It never fills the
gap with the identity of a commit that did not record the affirmation.

Each test builds its cases in ``tmp_path``. Git cannot climb above the parent of
``tmp_path``. A control in each test shows that the same case, with its history,
gives an identity. So the test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case

from . import extraction_support as base
from . import provenance_support as support
from .provenance_support import ALICE, BOB, CAROL, DAN, moment

pytestmark = support.requires_git

IDENTITY_KEYS = (
    support.KEY_COMMIT,
    support.KEY_SUBJECT,
    support.KEY_COMMITTER,
    support.KEY_AUTHOR,
)


def _says_nothing_of_the_history(shown: support.Shown, *absent: str) -> bool:
    """Whether no identity and no time is in the JSON, and none of ``absent`` is in the output."""
    entry = shown.provenance()
    if any(entry.get(key) is not None for key in IDENTITY_KEYS):
        return False
    if support.instants(shown.recorded_line()):
        return False
    return not [item for item in absent if item in shown.text or item in shown.raw]


def test_edge_show_reports_a_draft_event_as_not_committed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports an event that no commit holds as not committed, with no identity or time.

    A case is a git repository. Its only commit, by Carol, holds no review event.
    Then edge affirm records an event, and nobody commits it. edge show exits with
    status 0. The JSON status is notCommitted. The JSON commit, subject, committer
    and author are null. The text line "recorded in the case history" says not
    committed and holds no date. Neither the e-mail address of Carol nor her commit
    is anywhere in the output.

    :verifies: SEG-SREQ-300
    :test-id: SEG-TS-276
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    start = support.start_history(fixture)
    support.affirm(fixture)
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[support.KEY_STATUS] == support.NOT_COMMITTED
    assert support.WORD_NOT_COMMITTED in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown, CAROL.email, support.hex_prefix(start))


def test_edge_show_does_not_fall_back_to_an_earlier_affirmation_of_a_draft_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports a last affirmation that no commit holds as not committed.

    An edge is affirmed, and a commit by Alice adds its event. The text of the
    target requirement then changes, and the change is committed in the content
    repository. The edge is affirmed again, and nobody commits the second event.
    edge show exits with status 0. The JSON status is notCommitted, with no commit,
    no committer and no author. The text says not committed. The commit and the
    e-mail address of Alice are not in the output.

    :verifies: SEG-SREQ-300
    :test-id: SEG-TS-277
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    first = support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    fixture.rewrite(support.TO, "a new statement of REQ-A\n")
    base.commit_all(fixture.repository, "change REQ-A")
    support.affirm(fixture)
    assert len(support.event_ids(fixture.case)) == 2
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert shown.provenance()[support.KEY_STATUS] == support.NOT_COMMITTED
    assert support.WORD_NOT_COMMITTED in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown, ALICE.email, support.hex_prefix(first))


def test_edge_show_reports_the_history_of_a_case_with_no_repository_as_not_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the history as not available for a case that has no repository.

    A case with one committed event is copied to another directory with no .git
    directory. edge show for the copy exits with status 0. The JSON status is
    unavailable, with no commit, committer and author. The text line "recorded in
    the case history" says not available and holds no date. Alice, the committer of
    the original, is not in the output. A control run on the original case names her.

    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-278
    """
    support.isolate(monkeypatch, tmp_path)
    copied, original = support.case_copied(tmp_path)
    shown = support.show(copied, capsys)
    assert shown.status == 0
    assert shown.provenance()[support.KEY_STATUS] == support.UNAVAILABLE
    assert support.WORD_NOT_AVAILABLE in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown, ALICE.email, support.hex_prefix(original))
    control = support.show(
        support.nodes.Place(tmp_path / "source" / "case", copied.config, copied.current), capsys
    )
    assert support.is_found_at(control, original)


def test_edge_show_never_answers_from_the_repository_that_holds_the_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the history as not available for a case inside another repository.

    The files of a case with one event are added, in one commit by Dan, to another
    repository. The case is a directory of that repository, and its root is not the
    top level of the repository. edge show for the case exits with status 0. The JSON
    status is unavailable, with no commit, committer and author. The text says not
    available. The commit of the enclosing repository and the e-mail address of
    Dan are not in the output.

    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-279
    """
    support.isolate(monkeypatch, tmp_path)
    place, outer = support.case_nested(tmp_path)
    assert support.git(place.case, "rev-parse", "--show-toplevel") != str(place.case)
    shown = support.show(place, capsys)
    assert shown.status == 0
    assert shown.provenance()[support.KEY_STATUS] == support.UNAVAILABLE
    assert support.WORD_NOT_AVAILABLE in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown, DAN.email, support.hex_prefix(outer))


def test_edge_show_reports_a_history_that_cannot_be_read_as_not_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the history as not available when git cannot read the history.

    A case is a git repository, and a commit by Alice adds the event of an edge. The
    test deletes the object file of that commit from the repository. edge show exits
    with status 0, and it prints no traceback. The JSON status is unavailable, with
    no commit, committer and author. The text says not available. The e-mail address
    of Alice and the commit are not in the output.

    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-280
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.case_unreadable(tmp_path)
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert "Traceback" not in shown.text + shown.raw
    assert shown.provenance()[support.KEY_STATUS] == support.UNAVAILABLE
    assert support.WORD_NOT_AVAILABLE in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown, ALICE.email)


def test_edge_show_reads_the_history_of_a_case_that_is_a_worktree_of_another_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reads the history of a case that is a worktree of another repository.

    A repository has one commit by Dan. A worktree of it, on a branch of its own, is
    the case. A commit by Carol starts the case. A commit by Alice adds the event of
    an edge. The top level of the worktree is the root of the case. edge show exits
    with status 0. The JSON status is found, with the commit of the worktree and
    Alice as the committer. The commit of the first repository and Dan are not in
    the output.

    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-281
    """
    support.isolate(monkeypatch, tmp_path)
    host = tmp_path / "host"
    worktree = tmp_path / "worktree"
    support.make_worktree(host, worktree)
    host_commit = support.head(host)
    fixture = support.build(tmp_path / "fixture")
    case.AffirmationStore(root=worktree).initialize()
    support.commit(worktree, "start the case", committer=CAROL, committed=moment(0))
    support.affirm(fixture, case=worktree)
    recorded = support.commit(worktree, "affirm REQ-B", committer=ALICE, committed=moment(3))
    assert support.git(worktree, "rev-parse", "--show-toplevel") == str(worktree.resolve())
    shown = support.show(support.where(fixture, worktree), capsys)
    assert shown.status == 0
    assert support.is_found_at(shown, recorded)
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], ALICE, moment(3))
    assert DAN.email not in shown.text + shown.raw
    assert support.hex_prefix(host_commit) not in shown.text + shown.raw


def test_edge_show_reports_a_shallow_history_with_the_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports that the history is shallow, beside the identity it reports.

    A case has three commits. Carol starts it. Alice adds the event of the first edge.
    Bob adds the event of the second edge. A clone of depth one holds only the commit
    by Bob. edge show on the clone exits with status 0. For each edge, the JSON status
    is found, with the commit by Bob and Bob as the committer, and the JSON shallow is
    true. In the text, the block of each edge holds the word shallow. A control run on
    the full history gives the commit by Alice for the first edge, with shallow
    false, and no block holds the word shallow.

    :verifies: SEG-SREQ-302
    :test-id: SEG-TS-282
    """
    support.isolate(monkeypatch, tmp_path)
    clone, source, second, third = support.case_shallow(tmp_path)
    shown = support.show(clone, capsys, "--kind", support.KIND)
    assert shown.status == 0
    for from_id in (support.FROM, support.OTHER):
        entry = shown.provenance(from_id)
        assert entry[support.KEY_STATUS] == support.FOUND
        assert entry[support.KEY_COMMIT] == third
        assert support.person_is(entry[support.KEY_COMMITTER], BOB, moment(4))
        assert entry[support.KEY_SHALLOW] is True
        assert support.WORD_SHALLOW in shown.block_text(from_id).lower()
    full = support.show(source, capsys, "--kind", support.KIND)
    assert support.is_found_at(full, second, support.FROM)
    for from_id in (support.FROM, support.OTHER):
        assert full.provenance(from_id)[support.KEY_SHALLOW] is False
        assert support.WORD_SHALLOW not in full.block_text(from_id).lower()


def test_edge_show_reports_the_provenance_of_an_edge_that_is_no_longer_active(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the provenance of the last affirmation of an edge that is not active.

    An edge is affirmed, and one commit by Alice adds its event. The text of the
    target requirement then changes, so the edge is no longer active. edge show
    exits with status 0. The state of the edge in the report is not active. The JSON
    status is found, with the commit and Alice as the committer, and the text names
    the same commit and Alice.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-288
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    recorded = support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    fixture.rewrite(support.TO, "a new statement of REQ-A\n")
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert shown.row()["state"] != "active"
    assert support.is_found_at(shown, recorded)
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], ALICE, moment(3))
    assert ALICE.email in shown.block_text()


def test_edge_show_reports_an_event_in_a_repository_with_no_commit_as_not_committed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports an event as not committed when the case repository has no commit.

    The case is a git repository with no commit. Then edge affirm records an event.
    edge show exits with status 0, and it prints no traceback. The JSON status is
    notCommitted, with no commit, subject, committer and author. The text line
    "recorded in the case history" says not committed and holds no date.

    :verifies: SEG-SREQ-300
    :test-id: SEG-TS-289
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.init_repository(fixture.case)
    support.affirm(fixture)
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert "Traceback" not in shown.text + shown.raw
    assert shown.provenance()[support.KEY_STATUS] == support.NOT_COMMITTED
    assert support.WORD_NOT_COMMITTED in shown.recorded_line().lower()
    assert _says_nothing_of_the_history(shown)


def test_edge_show_gives_no_signature_and_no_shallow_flag_without_a_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show gives a null signature and a null shallow flag when no commit is reported.

    Two cases are built. In the first, the event is in the working tree and in no
    commit. In the second, the case was copied with no history. For each, edge show
    exits with status 0. The JSON status is notCommitted in the first case and
    unavailable in the second. In both, the JSON signature is null, and the JSON
    shallow flag is null. Both keys are present.

    :verifies: SEG-SREQ-300
    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-290
    """
    support.isolate(monkeypatch, tmp_path)
    draft = support.where(support.case_draft(tmp_path / "draft"))
    copied, _ = support.case_copied(tmp_path / "copied")
    for place, status in ((draft, support.NOT_COMMITTED), (copied, support.UNAVAILABLE)):
        shown = support.show(place, capsys)
        assert shown.status == 0, status
        entry = shown.provenance()
        assert entry[support.KEY_STATUS] == status
        assert support.KEY_SIGNATURE in entry, status
        assert support.KEY_SHALLOW in entry, status
        assert entry[support.KEY_SIGNATURE] is None, status
        assert entry[support.KEY_SHALLOW] is None, status
