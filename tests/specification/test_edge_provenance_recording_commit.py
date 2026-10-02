"""Verification suite for the commit that edge show names as the recording commit.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
recording commit of an affirmation is the earliest commit of the history of the
case whose tree holds the review event of the affirmation. Every event sits in one
file, so the commit that created the file is not the answer.

Each test builds a case in ``tmp_path``. The case is a git repository, and the
test makes the commits. Each expected commit is the identifier that git gave when
the test made the commit. The expected identity is the one the test set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as base
from . import provenance_support as support
from .provenance_support import ALICE, BOB, moment

pytestmark = support.requires_git


def test_edge_show_names_the_earliest_commit_that_holds_the_event_not_the_one_that_made_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show names the earliest commit that holds the event, not the one that made the file.

    An early commit by Alice creates the file of review events, with the event of
    a first edge. A later commit by Bob adds the event of a second edge to the file.
    edge show for the second edge names the later commit and Bob, in text and in
    JSON. It does not name the early commit or Alice. edge show for the first edge
    names the early commit and Alice.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-267
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture)
    support.affirm(fixture)
    early = support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.affirm_other(fixture)
    later = support.commit(fixture.case, "affirm REQ-C", committer=BOB, committed=moment(4))
    shown = support.show(support.where(fixture), capsys, "--kind", support.KIND)
    assert shown.status == 0
    assert support.is_found_at(shown, later, support.OTHER)
    assert support.person_is(shown.provenance(support.OTHER)[support.KEY_COMMITTER], BOB, moment(4))
    assert support.hex_prefix(early) not in shown.block_text(support.OTHER)
    assert ALICE.email not in shown.block_text(support.OTHER)
    assert support.is_found_at(shown, early, support.FROM)
    assert support.person_is(
        shown.provenance(support.FROM)[support.KEY_COMMITTER], ALICE, moment(3)
    )


def test_edge_show_names_one_commit_for_every_event_that_the_commit_adds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show names one commit as the recording commit of each event that the commit adds.

    A commit by Carol starts the case. One run of edge affirm then records two
    events, for two edges. One commit by Alice adds both. edge show for each edge
    names that commit and Alice, in text and in JSON. It does not name the commit
    by Carol.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-268
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    start = support.start_history(fixture)
    support.affirm(fixture, "--kind", support.KIND)
    both = support.commit(fixture.case, "affirm both edges", committer=ALICE, committed=moment(3))
    assert len(support.event_ids(fixture.case)) == 2
    shown = support.show(support.where(fixture), capsys, "--kind", support.KIND)
    assert shown.status == 0
    for from_id in (support.FROM, support.OTHER):
        assert support.is_found_at(shown, both, from_id)
        assert support.person_is(shown.provenance(from_id)[support.KEY_COMMITTER], ALICE, moment(3))
        assert support.hex_prefix(start) not in shown.block_text(from_id)


def test_edge_show_matches_the_whole_identifier_of_an_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show matches the whole identifier of an event, not one that begins the same way.

    The file of review events holds two events. The identifier of one ends with
    /event/1 and the identifier of the other ends with /event/10, so the first is
    the beginning of the second. The store gives each event a number of six digits,
    so the test writes both identifiers into the file as text. An early commit by
    Alice adds the event /event/10, of the first edge. A later commit by Bob adds
    the event /event/1, of the second edge. edge show for the second edge names
    the later commit and Bob. edge show for the first edge names the early commit
    and Alice.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-269
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture)
    support.affirm(fixture)
    (first,) = support.event_ids(fixture.case)
    stem = first.rpartition("/")[0]
    support.rename_event(fixture.case, first, f"{stem}/10")
    early = support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.affirm_other(fixture)
    (added,) = [item for item in support.event_ids(fixture.case) if not item.endswith("/10")]
    support.rename_event(fixture.case, added, f"{stem}/1")
    later = support.commit(fixture.case, "affirm REQ-C", committer=BOB, committed=moment(4))
    assert sorted(item.rpartition("/")[2] for item in support.event_ids(fixture.case)) == [
        "1",
        "10",
    ]
    shown = support.show(support.where(fixture), capsys, "--kind", support.KIND)
    assert shown.status == 0
    assert support.is_found_at(shown, later, support.OTHER)
    assert support.is_found_at(shown, early, support.FROM)
    assert support.hex_prefix(early) not in shown.block_text(support.OTHER)


def test_edge_show_does_not_take_a_reason_that_names_an_event_for_the_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show does not name a commit only because its reason quotes the identifier of the event.

    The reason of the first event is free text, and it ends with the identifier of
    the second event. The second event does not exist yet. An early commit by Alice
    adds the first event. A later commit by Bob adds the second event. edge show
    for the second edge names the later commit and Bob. In text and in JSON it does
    not name the early commit. Only an event holds the identifier of the event as
    its own identifier. A reason that quotes the identifier does not hold the event.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-270
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture)
    support.affirm(fixture, reason="placeholder")
    (first,) = support.event_ids(fixture.case)
    second = support.next_identifier(first)
    support.edit_events(
        fixture.case, '"seg:reason": "placeholder"', f'"seg:reason": "replaces {second}"'
    )
    early = support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.affirm_other(fixture)
    assert second in support.event_ids(fixture.case)
    later = support.commit(fixture.case, "affirm REQ-C", committer=BOB, committed=moment(4))
    shown = support.show(support.where(fixture), capsys, "--kind", support.KIND)
    assert shown.status == 0
    assert support.is_found_at(shown, later, support.OTHER)
    assert support.hex_prefix(early) not in shown.block_text(support.OTHER)
    assert support.is_found_at(shown, early, support.FROM)


def test_edge_show_names_the_earliest_commit_for_an_event_removed_and_added_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show names the earliest commit for an event that was removed and added again.

    A commit by Alice adds the event of an edge. A later commit by Bob removes the
    event from the file. A third commit by Dan puts the event back, with the same
    text. The file is then the same as after the first commit. edge show names the
    first commit and Alice, in text and in JSON. It does not name the commit by Bob
    or the commit by Dan.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-287
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture)
    support.affirm(fixture)
    text = support.events_text(fixture.case)
    first = support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.write_events_text(fixture.case, support.events_text_without_entries(text))
    removed = support.commit(fixture.case, "remove it", committer=BOB, committed=moment(4))
    support.write_events_text(fixture.case, text)
    back = support.commit(fixture.case, "put it back", committer=support.DAN, committed=moment(5))
    assert support.events_text(fixture.case) == text
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert support.is_found_at(shown, first)
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], ALICE, moment(3))
    assert support.hex_prefix(removed) not in shown.block_text()
    assert support.hex_prefix(back) not in shown.block_text()


def test_edge_show_names_the_commit_of_the_last_affirmation_of_an_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show names the commit of the last affirmation of an edge that was affirmed twice.

    An edge is affirmed, and one commit by Alice adds its event. The text of the
    target requirement then changes in the content repository, and the change is
    committed there. The edge is affirmed again, and a second commit by Bob adds the
    second event. edge show names the second commit and Bob, in text and in JSON.
    It does not name the first commit or Alice.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-271
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    first = support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    fixture.rewrite(support.TO, "a new statement of REQ-A\n")
    base.commit_all(fixture.repository, "change REQ-A")
    support.affirm(fixture)
    second = support.commit(fixture.case, "affirm REQ-B again", committer=BOB, committed=moment(6))
    assert len(support.event_ids(fixture.case)) == 2
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert support.is_found_at(shown, second)
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], BOB, moment(6))
    assert support.hex_prefix(first) not in shown.block_text()
    assert ALICE.email not in shown.block_text()


def test_edge_show_names_the_new_commit_after_an_amend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show names the commit as it stands after an amend, with the new identifier.

    One commit by Alice adds the event of an edge. edge show names that commit. Dan
    then amends the commit with a later commit date. The identifier of the commit
    changes. A second run of edge show names the new identifier and Dan as the
    committer, in text and in JSON. It does not name the old identifier.

    :verifies: SEG-SREQ-299
    :test-id: SEG-TS-272
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    old = support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    where = support.where(fixture)
    assert support.is_found_at(support.show(where, capsys), old)
    new = support.commit(fixture.case, "", committer=support.DAN, committed=moment(9), amend=True)
    assert new != old
    shown = support.show(where, capsys)
    assert shown.status == 0
    assert support.is_found_at(shown, new)
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], support.DAN, moment(9))
    assert support.hex_prefix(old) not in shown.block_text()
