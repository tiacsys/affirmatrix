"""Verification suite for the reads in a content repository, with a variable that names another.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds two git repositories in ``tmp_path``: the content repository that the
configuration maps, and a decoy with a history of its own. Before the command
runs, the test sets one variable of the environment so that it names the decoy
(``GIT_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``, ``GIT_OBJECT_DIRECTORY`` or
``GIT_COMMON_DIR``). Then it runs ``affirmatrix.cli.main`` as an operator runs it.

The expected values come from git, called by the test with none of the seven
variables set. Each test also holds a control. The control calls git directly,
with the variable set, and checks that the variable changes an answer that the
command reads. So the decoy works, and the test can fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as base
from . import node_show_support as nodes
from . import provenance_support as prov
from . import repository_reads_support as support

pytestmark = support.requires_git

#: The variables that can change an answer of a read in a content repository.
VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
)
#: The variables that can change what ``git show`` gives for a revision of the fixture.
SHOW_VARIABLES = ("GIT_DIR", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")


@support.red(
    332, "case sync answers from the repository the variable names, not the one at the path"
)
@pytest.mark.parametrize("variable", VARIABLES)
def test_case_sync_records_the_revision_of_the_repository_at_the_path(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """case sync records the revision of the repository at the path, whatever the environment names.

    A case is empty. A configuration maps the content repository, which holds the
    committed content of three requirements. A second repository has other
    commits. One variable of the environment names it: GIT_DIR, GIT_WORK_TREE,
    GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY or GIT_COMMON_DIR. Running case sync
    exits with status 0 and prints no line about a missing extraction revision.
    Each node record carries the revision of the content repository, as git gives
    it with no such variable. It never carries a revision of the second
    repository. A control, without the variable, gives the same records. Git, called
    with the variable, answers differently, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-292
    """
    support.isolate(monkeypatch, tmp_path)
    plain = base.build(tmp_path / "plain")
    assert support.sync(plain, capsys)[0] == 0
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    expected = {fixture.name: support.head(fixture.repository)}
    assert support.decoy_changes(fixture.repository, variable, decoy, "revision", "status", "tree")
    support.point(monkeypatch, variable, decoy)
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert not support.report_lines(text, fixture.name), text
    for local_id in base.IDS:
        assert base.held_map(plain.case, local_id) == {plain.name: support.head(plain.repository)}
        assert base.held_map(fixture.case, local_id) == expected


@support.red(332, "git reads objects from the store that GIT_ALTERNATE_OBJECT_DIRECTORIES names")
def test_case_sync_does_not_borrow_objects_from_a_repository_the_environment_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """case sync gives no revision for a repository without objects, whatever the environment names.

    The content repository has lost every object file, so git cannot read a commit
    in it. A second repository holds a copy of those objects. A first case sync,
    without a variable, exits with status 0 and records no revision. It prints one
    line that names the repository and the count 3. Then GIT_ALTERNATE_OBJECT_DIRECTORIES
    names the object store of the second repository, and case sync runs again. It
    exits with status 0 and records no revision. It prints the same line. Git, called
    with the variable, can read the commit, so the variable changes the answer of git.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-293
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path)
    donor = tmp_path / "donor"
    support.break_objects(fixture.repository, donor)
    assert support.run_git(fixture.repository, "status", "--porcelain=v1").returncode != 0
    borrowed = support.environment_with("GIT_ALTERNATE_OBJECT_DIRECTORIES", donor)
    assert (
        support.run_git(fixture.repository, "status", "--porcelain=v1", extra=borrowed).returncode
        == 0
    )
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert base.reported_counts(text, fixture.name) == [3]
    support.point(monkeypatch, "GIT_ALTERNATE_OBJECT_DIRECTORIES", donor)
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert base.reported_counts(text, fixture.name) == [3]
    for local_id in base.IDS:
        assert base.held_map(fixture.case, local_id) == {}


@support.red(332, "edge affirm answers from the repository the variable names, or refuses or fails")
@pytest.mark.parametrize("variable", VARIABLES)
def test_edge_affirm_records_the_revision_of_the_repository_at_the_path(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge affirm records the revision of the repository at the path, not an environment one.

    A configuration maps the content repository, which holds the committed content
    of three requirements. A second repository has other commits. One variable of
    the environment names it: GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE,
    GIT_OBJECT_DIRECTORY or GIT_COMMON_DIR. Running edge affirm for the edge from
    REQ-B to REQ-A, with no revision given, exits with status 0 and refuses nothing.
    The review event holds the revision of the content repository for both
    endpoints, and no other revision. Each of the two node records carries that
    revision. A control, without the variable, gives the same event revisions. Git,
    called with the variable, answers differently, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-294
    """
    support.isolate(monkeypatch, tmp_path)
    plain = base.build(tmp_path / "plain")
    assert support.affirm(plain, capsys)[0] == 0
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    revision = support.head(fixture.repository)
    assert support.decoy_changes(fixture.repository, variable, decoy, "revision", "status")
    support.point(monkeypatch, variable, decoy)
    status, text = support.affirm(fixture, capsys)
    assert status == 0, text
    assert support.event_revisions(plain.case) == {support.head(plain.repository)}
    assert support.event_revisions(fixture.case) == {revision}
    for local_id in (prov.FROM, prov.TO):
        assert base.held_map(fixture.case, local_id) == {fixture.name: revision}


@support.red(332, "node show reports the repository the variable names, or an error")
@pytest.mark.parametrize("variable", VARIABLES)
def test_node_show_reports_the_state_of_the_repository_at_the_path(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """node show reports the revision and the cleanliness of the repository at the path.

    A case holds three requirements, written by a case sync. The content repository
    is clean. A second repository has other commits. One variable of the environment
    names it: GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY or
    GIT_COMMON_DIR. Running node show for REQ-B exits with status 0. The checkout
    of its hash names the revision of the content repository, as git gives it with
    no such variable. It lists no dirty path and reports no error. Git, called with
    the variable, answers differently, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-295
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    assert support.sync(fixture, capsys)[0] == 0
    revision = support.head(fixture.repository)
    assert support.decoy_changes(fixture.repository, variable, decoy, "revision", "status")
    support.point(monkeypatch, variable, decoy)
    shown = nodes.show(nodes.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    checkout = shown.entry("contentHash")[nodes.KEY_CHECKOUT]
    assert checkout[nodes.KEY_CHECKOUT_REVISION] == revision
    assert checkout[nodes.KEY_CHECKOUT_DIRTY] == []
    assert not checkout.get(nodes.KEY_CHECKOUT_ERROR)


@support.red(
    332, "edge show reads the before-content from the repository the variable names, or fails"
)
@pytest.mark.parametrize("variable", SHOW_VARIABLES)
def test_edge_show_reads_the_before_content_from_the_repository_at_the_path(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show recovers the before-content from the repository at the path.

    An edge from REQ-B to REQ-A is affirmed. Then the text of both requirements
    changes, and the change is committed in the content repository. A second
    repository has other commits. One variable of the environment names it:
    GIT_DIR, GIT_OBJECT_DIRECTORY or GIT_COMMON_DIR. Running edge show with the
    options for verbose JSON exits with status 0. The before-content of each
    endpoint is the text that the content repository held when the edge was
    affirmed. A control, without the variable, gives the same text. Git, called with
    the variable, answers differently, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-296
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    decoy = support.make_decoy(tmp_path / "decoy")
    assert support.affirm(fixture, capsys)[0] == 0
    fixture.rewrite(prov.FROM, "a later statement of REQ-B\n")
    fixture.rewrite(prov.TO, "a later statement of REQ-A\n")
    base.commit_all(fixture.repository, "change both requirements")
    expected = (f"statement of {prov.FROM}\n", f"statement of {prov.TO}\n")
    place = nodes.place(fixture)
    _, control = support.show_before_content(place, capsys)
    assert (support.before_text(control, "from"), support.before_text(control, "to")) == expected
    assert support.decoy_changes(fixture.repository, variable, decoy, "show")
    support.point(monkeypatch, variable, decoy)
    status, row = support.show_before_content(place, capsys)
    assert status == 0
    assert (support.before_text(row, "from"), support.before_text(row, "to")) == expected


_HIDES = "a dirty repository looks clean, and edge affirm records a revision"


@pytest.mark.parametrize(
    "variable",
    (
        pytest.param("GIT_DIR", marks=support.red(332, _HIDES)),
        pytest.param("GIT_WORK_TREE", marks=support.red(332, _HIDES)),
        "GIT_INDEX_FILE",
    ),
)
def test_edge_affirm_still_refuses_a_dirty_repository_with_a_variable_set(
    variable: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge affirm refuses a dirty content repository, whatever repository the environment names.

    The content repository holds an uncommitted change in the file of REQ-B. A second
    repository is made so that it hides the change from a read of the wrong
    repository. One variable of the environment names it: GIT_DIR, GIT_WORK_TREE or
    GIT_INDEX_FILE. Running edge affirm for the edge from REQ-B to REQ-A, with no
    revision given, exits with status 2 and names the file of REQ-B. It writes no review
    event. A control, without the variable, gives the same. Git, called with the variable,
    reports no change in that file for GIT_DIR and GIT_WORK_TREE, so the decoy works.

    :verifies: SEG-SREQ-332
    :test-id: SEG-TS-316
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    changed = f"requirement/{prov.FROM}.txt"
    dirty_text = "a change nobody committed\n"
    base.write(fixture.repository, changed, dirty_text)
    decoy = support.make_decoy(tmp_path / "decoy", same_text=True)
    if variable != "GIT_WORK_TREE":
        base.write(decoy, changed, dirty_text)
        prov.commit(decoy, "decoy: the same change")
    status, text = support.affirm(fixture, capsys)
    assert status == 2
    assert changed in text
    if variable != "GIT_INDEX_FILE":
        hidden = support.run_git(
            fixture.repository,
            "status",
            "--porcelain=v1",
            "--",
            changed,
            extra=support.environment_with(variable, decoy),
        )
        assert hidden.stdout == b""
    support.point(monkeypatch, variable, decoy)
    status, text = support.affirm(fixture, capsys)
    assert status == 2, text
    assert changed in text
    assert not (fixture.case / prov.EVENTS_FILE).exists() or not prov.event_ids(fixture.case)
