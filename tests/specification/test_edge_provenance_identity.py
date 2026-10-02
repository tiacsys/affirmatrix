"""Verification suite for the identity that edge show reports for an affirmation.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
claim: for an affirmed edge, edge show reports who recorded the affirmation and
when, as the commit that added its review event records it.

Each test builds a case in ``tmp_path``. The case is a git repository, and the
test makes the commits, as a person makes a store act. The committer, the author
and their dates are set in the environment of each commit. The expected values
are the ones the test set. The names of the keys and the labels are in
``provenance_support``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import provenance_support as support
from .provenance_support import ALICE, BOB, CAROL, moment

pytestmark = support.requires_git

BODY = "Checked the new text of the requirement.\nThe link is sound.\n"


def test_edge_show_reports_the_committer_and_the_commit_date_as_the_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the committer of the recording commit, with its date, as the identity.

    A case is a git repository. One commit adds the review event of an edge. Its
    committer is Alice, with one commit date. Its author is Bob, with an earlier
    date. edge show exits with status 0, in text and in JSON. The JSON committer
    holds the name and the e-mail address of Alice, and a date that is the commit
    date as one instant. The text line "recorded in the case history as" holds the
    same name, the same e-mail address and the same instant. That line does not
    hold the e-mail address of Bob.

    :verifies: SEG-SREQ-294
    :test-id: SEG-TS-260
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(
        fixture, committer=ALICE, committed=moment(3), author=BOB, authored=moment(2)
    )
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[support.KEY_STATUS] == support.FOUND
    assert support.person_is(entry[support.KEY_COMMITTER], ALICE, moment(3))
    line = shown.recorded_line()
    assert support.LABEL_RECORDED_AS in line.lower()
    assert support.line_has(line, ALICE, moment(3))
    assert BOB.email not in line


def test_edge_show_reports_the_identifier_and_the_subject_of_the_recording_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the identifier and the subject line of the recording commit.

    A case is a git repository. One commit adds the review event of an edge. Its
    message has a subject line, an empty line and a body of two lines. edge show
    exits with status 0. The JSON commit is the identifier that git gives for the
    commit, and the JSON subject is the subject line alone. The text gives the
    first seven characters of the identifier at least. It gives the subject line
    in the same line as the identifier. It does not give the body.

    :verifies: SEG-SREQ-299
    :test-id: SEG-TS-261
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    subject = "affirm REQ-B after the review of 4 March"
    commit_id = support.affirmed_and_committed(fixture, f"{subject}\n\n{BODY}")
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[support.KEY_COMMIT] == commit_id
    assert entry[support.KEY_SUBJECT] == subject
    (line,) = [item.strip() for item in shown.block() if support.hex_prefix(commit_id) in item]
    assert subject in line
    assert "Checked the new text" not in shown.block_text()


def test_edge_show_reports_every_affirmed_edge_of_a_selection_with_no_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports who made the last affirmation of each affirmed edge in a selection.

    Two edges are affirmed. Alice adds the event of the first edge in one commit.
    Bob adds the event of the second edge in a later commit. edge show runs with a
    selector of the edge kind and with no other option. It exits with status 0.
    Both edges are in the report. In text and in JSON, each edge names the commit
    that added its own event, and the committer of that commit, with the commit
    date. Neither edge names the commit or the committer of the other.

    :verifies: SEG-SREQ-293
    :test-id: SEG-TS-262
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture)
    support.affirm(fixture)
    first = support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    support.affirm_other(fixture)
    second = support.commit(fixture.case, "affirm REQ-C", committer=BOB, committed=moment(4))
    shown = support.show(support.where(fixture), capsys, "--kind", support.KIND)
    assert shown.status == 0
    assert {row["from"] for row in shown.rows()} == {support.FROM, support.OTHER}
    for from_id, commit_id, person, other, hours in (
        (support.FROM, first, ALICE, BOB, 3),
        (support.OTHER, second, BOB, ALICE, 4),
    ):
        entry = shown.provenance(from_id)
        assert entry[support.KEY_COMMIT] == commit_id
        assert support.person_is(entry[support.KEY_COMMITTER], person, moment(hours))
        assert support.line_has(shown.recorded_line(from_id), person, moment(hours))
        assert other.email not in shown.block_text(from_id)


def test_edge_show_reports_an_author_that_is_not_the_committer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the author and the author date when the author is not the committer.

    One commit adds the review event of an edge. Its committer is Alice, with one
    date. Its author is Bob, with an earlier date. edge show exits with status 0.
    The JSON author holds the name and the e-mail address of Bob and the author
    date as one instant. The JSON committer is Alice. The text has one line that
    starts with "author:". That line holds the name, the e-mail address and the
    author date of Bob. The line "recorded in the case history as" still holds
    Alice.

    :verifies: SEG-SREQ-295
    :test-id: SEG-TS-263
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(
        fixture, committer=ALICE, committed=moment(3), author=BOB, authored=moment(2)
    )
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert support.person_is(entry[support.KEY_AUTHOR], BOB, moment(2))
    assert support.person_is(entry[support.KEY_COMMITTER], ALICE, moment(3))
    (line,) = shown.labelled(support.LABEL_AUTHOR)
    assert support.line_has(line, BOB, moment(2))
    assert support.line_has(shown.recorded_line(), ALICE, moment(3))


def test_edge_show_reports_no_author_when_the_author_is_the_committer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports no author when the author of the recording commit is its committer.

    One commit adds the review event of an edge. The author and the committer are
    the same person, with the same date. edge show exits with status 0. The JSON
    has the author key, and its value is null. The JSON committer is that person.
    The text has no line that starts with "author:". The line "recorded in the case
    history as" holds that person.

    :verifies: SEG-SREQ-295
    :test-id: SEG-TS-264
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert support.person_is(entry[support.KEY_COMMITTER], ALICE, moment(3))
    assert support.KEY_AUTHOR in entry
    assert entry[support.KEY_AUTHOR] is None
    assert shown.labelled(support.LABEL_AUTHOR) == []
    assert support.line_has(shown.recorded_line(), ALICE, moment(3))


def test_edge_show_reports_each_signed_off_by_line_as_written_in_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports each Signed-off-by line of the recording commit as written, in order.

    The message of the commit ends with two Signed-off-by lines. The first names
    Zed, and the second names Amy, so the order is not the order of the alphabet.
    edge show exits with status 0. The JSON list has two entries. They are the
    two values as written, with or without the word Signed-off-by, in the order of
    the message. The text has the two values in the same order, in lines that
    start with "signed-off-by:".

    :verifies: SEG-SREQ-296
    :test-id: SEG-TS-265
    """
    support.isolate(monkeypatch, tmp_path)
    zed = support.Person("Zed Second", "zed@example.invalid")
    amy = support.Person("Amy First", "amy@example.invalid")
    message = (
        f"affirm REQ-B\n\n{BODY}\nSigned-off-by: {zed.written}\nSigned-off-by: {amy.written}\n"
    )
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(fixture, message)
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert [support.signed_off_value(item) for item in entry[support.KEY_SIGNED_OFF_BY]] == [
        zed.written,
        amy.written,
    ]
    lines = shown.labelled(support.LABEL_SIGNED_OFF_BY)
    assert len(lines) >= 1
    joined = "\n".join(lines)
    assert zed.written in joined
    assert amy.written in joined
    assert joined.index(zed.written) < joined.index(amy.written)


def test_edge_show_reports_no_signed_off_by_line_when_the_message_has_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports no Signed-off-by line when the message of the recording commit has none.

    The message of the commit has a subject line and a body, and no Signed-off-by
    line. edge show exits with status 0. The JSON list of sign-offs is empty. The
    text has no line that starts with "signed-off-by:".

    :verifies: SEG-SREQ-296
    :test-id: SEG-TS-266
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(fixture, f"affirm REQ-B\n\n{BODY}")
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[support.KEY_STATUS] == support.FOUND
    assert entry[support.KEY_SIGNED_OFF_BY] == []
    assert shown.labelled(support.LABEL_SIGNED_OFF_BY) == []


def test_edge_show_reports_the_committer_as_recorded_and_applies_no_mailmap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the committer as the commit records it and applies no mailmap.

    The case holds a .mailmap file, in the commit that adds the event. The file
    maps the e-mail address of Alice to another name and another address. The
    committer of the commit is Alice. edge show exits with status 0. The JSON
    committer has the name and the e-mail address that the commit records. The
    mapped name and the mapped address are not in the text or in the JSON.

    :verifies: SEG-SREQ-294
    :test-id: SEG-TS-286
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.start_history(fixture, committer=CAROL)
    support.affirm(fixture)
    (fixture.case / ".mailmap").write_text(
        f"Mapped Name <mapped@example.invalid> <{ALICE.email}>\n", encoding="utf-8"
    )
    support.commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    assert support.person_is(shown.provenance()[support.KEY_COMMITTER], ALICE, moment(3))
    assert "Mapped Name" not in shown.text + shown.raw
    assert "mapped@example.invalid" not in shown.text + shown.raw


def test_edge_show_reports_no_author_for_the_same_person_with_another_author_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports no author when the author is the committer, even if the dates differ.

    One commit adds the review event of an edge. The author and the committer are
    the same person, by name and e-mail address. The author date is earlier than the
    commit date, as after an amend or a rebase. edge show exits with status 0. The
    JSON has the author key, and its value is null. The JSON committer is that person,
    with the commit date. The text has no line that starts with "author:".

    :verifies: SEG-SREQ-295
    :test-id: SEG-TS-291
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(
        fixture, committer=ALICE, committed=moment(3), author=ALICE, authored=moment(2)
    )
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert support.person_is(entry[support.KEY_COMMITTER], ALICE, moment(3))
    assert support.KEY_AUTHOR in entry
    assert entry[support.KEY_AUTHOR] is None
    assert shown.labelled(support.LABEL_AUTHOR) == []
