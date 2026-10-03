"""Verification suite for the reads of the case history, with a variable that names a repository.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
case is a git repository, and the test makes its commits. A decoy is a second
repository that holds a copy of the files of the case, in a commit by someone
else. Before the command runs, the test sets one variable of the environment so
that it names the decoy. Then it runs ``edge show``.

The expected commit is the identifier that git gave when the test made the commit.
Each test also holds a control. The control calls git directly, with the variable
set, and checks that the variable changes an answer that the command reads. So
the decoy works, and the test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import provenance_support as prov
from . import repository_reads_support as support
from .provenance_support import ALICE, DAN, moment

pytestmark = support.requires_git

#: The variables that can change an answer of a read of the history of the case.
VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")


@support.red(332, "the history of the case is read from the repository the variable names")
@pytest.mark.parametrize("variable", VARIABLES)
def test_edge_show_names_the_recording_commit_of_the_case_whatever_the_environment_names(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show names the commit of the case itself, whatever repository the environment names.

    A case is a git repository. One commit by Alice adds the review event of an
    edge. A second repository holds a copy of the files of the case, in a commit by
    Dan. One variable of the environment names it: GIT_DIR, GIT_WORK_TREE,
    GIT_OBJECT_DIRECTORY or GIT_COMMON_DIR. edge show exits with status 0. In text
    and in JSON, the provenance of the edge is found, and it names the commit by
    Alice and her identity. It does not name the commit by Dan, or his e-mail
    address. A control, without the variable, gives the same. Git, called with the
    variable, answers differently, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-297
    """
    prov_root = tmp_path / "world"
    support.isolate(monkeypatch, tmp_path)
    fixture, recording = prov.case_committed(prov_root)
    decoy = support.make_case_decoy(fixture.case, tmp_path / "decoy")
    decoy_commit = support.head(decoy)
    place = prov.where(fixture)
    control = prov.show(place, capsys)
    assert control.status == 0
    assert prov.is_found_at(control, recording)
    assert support.case_decoy_changes(fixture.case, variable, decoy)
    support.point(monkeypatch, variable, decoy)
    shown = prov.show(place, capsys)
    assert shown.status == 0
    assert prov.is_found_at(shown, recording)
    assert prov.person_is(shown.provenance()[prov.KEY_COMMITTER], ALICE, moment(3))
    assert DAN.email not in shown.text + shown.raw
    assert prov.hex_prefix(decoy_commit) not in shown.text + shown.raw


@support.red(301, "GIT_DIR makes the enclosing repository pass as the repository of the case")
def test_edge_show_does_not_take_an_enclosing_repository_for_the_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """edge show reports a case inside another repository as not available, whatever GIT_DIR names.

    A case lies inside another repository, which holds it in a commit of its own.
    edge show for an edge of that case exits with status 0. It reports the history
    as not available: the JSON status is unavailable, and no commit, committer or
    author is named. The same holds when GIT_DIR names the git directory of the
    enclosing repository. Git, called with that variable, takes the case for the
    top level of that repository, so the variable changes the answer of git.

    :verifies: SEG-SREQ-301
    :test-id: SEG-TS-298
    """
    support.isolate(monkeypatch, tmp_path)
    place, outer_commit = prov.case_nested(tmp_path)
    outer = tmp_path / "outer"
    control = prov.show(place, capsys)
    assert control.provenance()[prov.KEY_STATUS] == prov.UNAVAILABLE
    assert support.case_decoy_changes(place.case, "GIT_DIR", outer)
    support.point(monkeypatch, "GIT_DIR", outer)
    shown = prov.show(place, capsys)
    assert shown.status == 0
    entry = shown.provenance()
    assert entry[prov.KEY_STATUS] == prov.UNAVAILABLE
    assert entry[prov.KEY_COMMIT] is None
    assert entry[prov.KEY_COMMITTER] is None
    assert prov.hex_prefix(outer_commit) not in shown.text + shown.raw
