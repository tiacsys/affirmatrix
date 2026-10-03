"""Verification suite for a repository read of very many paths, made in parts.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A call
of git accepts only so many paths. The interface in ``repository_reads_support``
is a module constant, the most paths one call takes. A test lowers it with
``monkeypatch``, so that a small store needs several calls. This pins the logic of
the parts on every machine.

One test makes a real call that is too long. It builds a repository with so many long
path names that the arguments are larger than the limit of the operating system, and
it runs case sync over it. It needs no constant.

A stand-in ``git`` on ``PATH`` logs the arguments of each call, and can fail one call.
Every expected value comes from git, called by the test.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.records import ContentAnchor, NodeRecord

from . import extraction_support as base
from . import node_show_support as nodes
from . import repository_reads_support as support

pytestmark = support.requires_git

COUNT = 9
DIRTY = (2, 8)
UNCOMMITTED = (5,)
LIMIT = 2


def _expected(fixture: base.Fixture) -> dict[str, dict[str, str]]:
    revision = support.head(fixture.repository)
    broken = {support.many_ids(COUNT)[number] for number in (*DIRTY, *UNCOMMITTED)}
    return {
        local_id: {} if local_id in broken else {fixture.name: revision}
        for local_id in support.many_ids(COUNT)
    }


@support.red(334, "a read of more paths than one call takes is made in one call")
def test_a_read_of_more_paths_than_one_call_takes_gives_the_answer_of_one_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read of more paths than one call takes gives the answer that one call gives.

    A repository holds nine requirements, each in a file of its own. The change of
    two files is not committed, and a third file was never committed. One call of
    git takes at most two paths. A stand-in git logs the calls. Running case sync
    exits with status 0. Git status is called more than once. The six requirements
    with clean, committed files carry the revision of the repository. The three
    others carry none. One line names the repository and the count 3. A control
    makes the same store with no limit, and gives the same records and the same
    line.

    :verifies: SEG-SREQ-334
    :test-id: SEG-TS-308
    """
    support.isolate(monkeypatch, tmp_path)
    control = support.build_many(tmp_path / "control", COUNT, dirty=DIRTY, uncommitted=UNCOMMITTED)
    status, control_text = support.sync(control, capsys)
    assert status == 0
    assert support.revisions_by_node(control, COUNT) == _expected(control)
    assert base.reported_counts(control_text, control.name) == [3]
    fixture = support.build_many(tmp_path / "parts", COUNT, dirty=DIRTY, uncommitted=UNCOMMITTED)
    support.lower_limit(monkeypatch, LIMIT)
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert len(stand_in.calls_of("status")) > 1
    assert support.revisions_by_node(fixture, COUNT) == _expected(fixture)
    assert base.reported_counts(text, fixture.name) == [3]


@support.red(334, "a read of more paths than one call takes is made in one call")
def test_a_read_in_parts_gives_every_path_to_exactly_one_call_and_no_call_too_many(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read in parts names every path in exactly one call, and no call names too many.

    A repository holds nine requirements, each in a file of its own. One call of git
    takes at most two paths. A stand-in git logs each call. Running case sync exits
    with status 0. The calls of git status are more than one, and so are the calls of
    git ls-tree. In each call, the paths number at most two. Taken together, the calls
    of each subcommand name each of the nine paths once and name no other path.

    :verifies: SEG-SREQ-334
    :test-id: SEG-TS-309
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build_many(tmp_path, COUNT)
    support.lower_limit(monkeypatch, LIMIT)
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    wanted = sorted(f"requirement/{local_id}.txt" for local_id in support.many_ids(COUNT))
    for subcommand in ("status", "ls-tree"):
        calls = stand_in.calls_of(subcommand)
        assert len(calls) > 1, subcommand
        assert max(stand_in.path_counts(subcommand)) <= LIMIT, subcommand
        named = sorted(
            item
            for call in calls
            for item in call["arguments"][call["arguments"].index("--") + 1 :]
        )
        assert named == wanted, subcommand


@support.red(334, "a read of more paths than one call takes is made in one call")
def test_node_show_reads_the_paths_of_one_node_in_parts_and_reports_the_same_dirty_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show reads the paths of a node in parts and reports the dirty path one call reports.

    A node, TS-1, hashes two files in one repository. The change of the second file
    in the order of the names is not committed. One call of git takes at most one
    path. Running node show for TS-1 exits with status 0. The checkout lists the
    second file as its one dirty path, and names the revision of the repository. A
    control, with no limit, gives the same checkout.

    :verifies: SEG-SREQ-334
    :test-id: SEG-TS-310
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = nodes.build_multi(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    changed = "test-specification/TS-1.spec.txt"
    base.write(fixture.repository, changed, "a change nobody committed\n")
    place = nodes.place(fixture)
    control_status, control = support.show_node_once(place, "TS-1", capsys)
    checkout = control["specHash"][nodes.KEY_CHECKOUT]
    assert checkout[nodes.KEY_CHECKOUT_DIRTY] == [changed]
    support.lower_limit(monkeypatch, 1)
    stand_in = support.install_stand_in(monkeypatch, tmp_path)
    status, shown = support.show_node_once(place, "TS-1", capsys)
    assert status == control_status
    assert shown["specHash"][nodes.KEY_CHECKOUT] == checkout
    assert len(stand_in.calls_of("status")) > 1
    assert max(stand_in.path_counts("status")) <= 1


@support.red(334, "the system refuses the one long call, and the repository counts as unreadable")
def test_a_read_of_so_many_paths_that_the_system_refuses_the_call_still_gives_revisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read of so many paths that the system refuses one call gives the answer of one call.

    A repository holds a committed file for each of very many requirements. The names
    of the files are long. The paths together are larger than the limit of the
    operating system for the arguments of one program. Running case sync exits with
    status 0. Each node record carries the revision of the repository. No line reports a
    missing extraction revision.

    :verifies: SEG-SREQ-334
    :test-id: SEG-TS-311
    """
    support.isolate(monkeypatch, tmp_path)
    limit = os.sysconf("SC_ARG_MAX")
    if limit > 8 * 1024 * 1024:
        pytest.skip(f"the limit of {limit} bytes needs more files than this test makes")
    name_length = 120
    count = math.ceil(limit * 1.15 / (name_length + 1))
    repository = base.init_repository(tmp_path / "big")
    paths = []
    for number in range(count):
        path = f"d{number % 50:02d}/" + "n" * (name_length - 12) + f"{number:07d}.txt"
        base.write(repository, path, f"text {number}\n")
        paths.append(path)
    base.commit_all(repository, "every file")
    records = tuple(
        NodeRecord(
            local_id=f"REQ-{number}",
            kind="Requirement",
            content_anchors={
                "contentHash": ContentAnchor(
                    digest=hashlib.sha256((repository / path).read_bytes()).digest(),
                    repository="big",
                    path=path,
                    locator="file",
                )
            },
        )
        for number, path in enumerate(paths)
    )
    base.supply(monkeypatch, base.ListedSource(records))
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    configuration = tmp_path / "big.yaml"
    configuration.write_text(json.dumps({"repositories": {"big": str(repository)}}), "utf-8")
    capsys.readouterr()
    status = support.main(
        ["case", "sync", "--case", str(case_root), "--config", str(configuration)]
    )
    text = capsys.readouterr().out
    assert status == 0
    assert "no extraction revision" not in text, text[-200:]
    revision = support.head(repository)
    assert base.held_map(case_root, "REQ-0") == {"big": revision}
    assert base.held_map(case_root, f"REQ-{count - 1}") == {"big": revision}


def test_a_failing_call_fails_the_read_of_a_repository_that_one_call_reads(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A call of git that fails makes the repository one that cannot be read.

    A repository holds six requirements. In one run, a stand-in git fails the first
    call of git status. In a second run, it fails the first call of git ls-tree. In
    both runs, case sync exits with status 0. No node record carries a revision, and
    one line names the repository and the count 6. The same run without a failure
    gives all six records the revision.

    :verifies: SEG-SREQ-335
    :test-id: SEG-TS-312
    """
    support.isolate(monkeypatch, tmp_path)
    control = support.build_many(tmp_path / "control", 6)
    assert support.sync(control, capsys)[0] == 0
    assert all(support.revisions_by_node(control, 6).values())
    for subcommand in ("status", "ls-tree"):
        fixture = support.build_many(tmp_path / subcommand, 6)
        with monkeypatch.context() as patch:
            support.install_stand_in(patch, tmp_path / subcommand, fail=(subcommand, 1))
            status, text = support.sync(fixture, capsys)
        assert status == 0, subcommand
        assert not any(support.revisions_by_node(fixture, 6).values()), subcommand
        assert base.reported_counts(text, fixture.name) == [6], subcommand


@support.red(335, "no read is made in parts, so no later part exists to fail")
@pytest.mark.parametrize("subcommand", ("status", "ls-tree"))
def test_case_sync_counts_the_repository_as_unreadable_when_a_later_part_fails(
    subcommand: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """case sync gives no revision for any node of a repository when a later part fails.

    A repository holds six requirements, all clean and committed. One call of git takes at
    most two paths. A stand-in git fails the second call of git status in one run, and the
    second call of git ls-tree in the other. Running case sync exits with status 0. No node
    record carries a revision, not even the records of the paths in the parts that were read.
    One line names the repository and the count 6.

    :verifies: SEG-SREQ-335
    :test-id: SEG-TS-313
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = support.build_many(tmp_path, 6)
    support.lower_limit(monkeypatch, LIMIT)
    stand_in = support.install_stand_in(monkeypatch, tmp_path, fail=(subcommand, 2))
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert not any(support.revisions_by_node(fixture, 6).values())
    assert base.reported_counts(text, fixture.name) == [6]
    assert len(stand_in.calls_of(subcommand)) >= 2


@support.red(335, "no read is made in parts, so no later part exists to fail")
def test_node_show_reports_the_repository_as_unreadable_when_a_later_part_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show reports a repository that cannot be read when a later part fails.

    A node, TS-1, hashes two files in one repository. One call of git takes at most one
    path. A stand-in git fails the second call of git status. Running node show for TS-1
    exits with status 0. The checkout names no revision, and it gives an error.

    :verifies: SEG-SREQ-335
    :test-id: SEG-TS-314
    """
    support.isolate(monkeypatch, tmp_path)
    fixture = nodes.build_multi(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    support.lower_limit(monkeypatch, 1)
    stand_in = support.install_stand_in(monkeypatch, tmp_path, fail=("status", 2))
    status, shown = support.show_node_once(nodes.place(fixture), "TS-1", capsys)
    assert status == 0
    checkout = shown["specHash"][nodes.KEY_CHECKOUT]
    assert checkout.get(nodes.KEY_CHECKOUT_REVISION) is None
    assert checkout.get(nodes.KEY_CHECKOUT_ERROR)
    assert len(stand_in.calls_of("status")) >= 2
