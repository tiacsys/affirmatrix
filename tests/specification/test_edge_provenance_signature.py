"""Verification suite for the signature status and the label of the provenance.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
status of a signature is the status that git gives. The tool runs no cryptography
of its own. The identity and the time are what the history records, and edge show
presents them so.

A signed commit in these tests is signed by a stand-in for the ``gpg`` program,
which is a script in ``tmp_path``. The settings that make git use it are in the
environment, never in a global configuration. The stand-in needs no key, and it
reaches no key ring and no agent of the machine. It lets each status of git be
made on any machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import provenance_support as support
from .provenance_support import ALICE, moment

pytestmark = support.requires_git


def test_edge_show_reports_an_unsigned_commit_as_signature_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports that the recording commit is not signed, with the status none.

    One commit adds the review event of an edge, and it carries no signature. edge
    show exits with status 0. The JSON signature is the word none. The text has one
    line that starts with "signature:", and it says none.

    :verifies: SEG-SREQ-297
    :test-id: SEG-TS-273
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build(tmp_path)
    support.affirmed_and_committed(fixture, committer=ALICE, committed=moment(3))
    shown = support.show(support.where(fixture), capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[support.KEY_STATUS] == support.FOUND
    assert entry[support.KEY_SIGNATURE] == "none"
    (line,) = shown.labelled(support.LABEL_SIGNATURE)
    assert support.normal("none") in support.normal(line.partition(":")[2])


def test_edge_show_reports_each_signature_status_as_git_gives_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports the status of a signature as git gives it, for each status.

    A stand-in for the gpg program lets git make and check a signature of each
    kind. For each of seven letters of git, a case is built. One signed commit adds
    the review event of an edge. The letters are G, B, U, X, Y, R and E. edge show
    exits with status 0. The JSON signature and the text line that starts with
    "signature:" give one word. G is good. B is bad. U is unknownValidity. X and Y are
    expired. R is revoked. E is cannotCheck. The text gives that word, with or
    without spaces, and no other word of the set.

    :verifies: SEG-SREQ-297
    :test-id: SEG-TS-274
    """
    support.isolate(monkeypatch, tmp_path)
    support.sign_with_stand_in(monkeypatch, tmp_path)
    words = {one: support.normal(word) for one, word in support.SIGNATURE_WORDS.items()}
    for letter in "GBUXYRE":
        word = support.SIGNATURE_WORDS[letter]
        fixture, commit_id = support.case_committed(tmp_path / letter, signature=letter)
        shown = support.show(support.where(fixture), capsys)
        assert shown.status == 0, letter
        entry = shown.provenance()
        assert entry[support.KEY_COMMIT] == commit_id, letter
        assert entry[support.KEY_SIGNATURE] == word, letter
        (line,) = shown.labelled(support.LABEL_SIGNATURE)
        said = support.normal(line.partition(":")[2])
        assert support.normal(word) in said, (letter, line)
        others = {words[one] for one in words if words[one] != support.normal(word)}
        assert not [other for other in others if other in said], (letter, line)


def test_edge_show_presents_the_identity_as_recorded_and_never_as_verified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show presents the identity as what the case history records, and never as verified.

    Three cases are built. In the first, a commit with a good signature adds the
    event. In the second, the event is in the working tree and in no commit. In the
    third, the case has no history. For each, edge show exits with status 0. The
    text has one line with the words "recorded in the case history". In the first
    case, that line has the words "recorded in the case history as". The JSON has
    the key recordedInCaseHistory. Nothing that edge show prints, in text or in
    JSON, holds the words "affirmed by", "verified" or "authenticated".

    :verifies: SEG-SREQ-298
    :test-id: SEG-TS-275
    """
    support.isolate(monkeypatch, tmp_path)
    support.sign_with_stand_in(monkeypatch, tmp_path)
    signed, _ = support.case_committed(tmp_path / "signed", signature="G")
    draft = support.case_draft(tmp_path / "draft")
    copied, _ = support.case_copied(tmp_path / "copied")
    cases = (
        ("signed", support.where(signed)),
        ("draft", support.where(draft)),
        ("copied", copied),
    )
    for name, place in cases:
        shown = support.show(place, capsys)
        assert shown.status == 0, name
        assert support.KEY_PROVENANCE in shown.row(), name
        line = shown.recorded_line()
        assert support.LABEL_RECORDED in line.lower(), name
        if name == "signed":
            assert support.LABEL_RECORDED_AS in line.lower()
        for word in support.FORBIDDEN_WORDS:
            assert word not in shown.text.lower(), (name, word)
            assert word not in shown.raw.lower(), (name, word)
