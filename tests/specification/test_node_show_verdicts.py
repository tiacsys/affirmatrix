"""Verification suite for the exit status of ``node show`` and its inputs.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
exit status has three values. 0 is the positive verdict: every hash matches. 1 is
the negative verdict: a hash differs, a hash is on one side only, or the current
stream holds no such node. 2 means that the request could not be judged: the case
does not hold the identifier, or the current stream cannot be read.

Each test builds its repositories in ``tmp_path`` and runs ``affirmatrix.cli.main``.
Every test that expects status 1 or 2 starts with a control that is accepted and
exits with status 0. So a test fails for the claim, and not because the command
cannot be run. The command runs for the text report and for the JSON
report, and both must give the same status.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.cli import main

from . import evidence_support as evidence
from . import extraction_support as base
from . import node_show_support as support

pytestmark = support.requires_git


def _reason(claim: str) -> str:
    return f"{claim}: there is no node show verb, so the command gives no verdict"


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-320"))
def test_node_show_exits_with_status_0_while_every_hash_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 0 while every named hash of the node matches.

    The case holds a requirement, a test specification and an implementation,
    synced from one repository. Nothing has changed. For each node, node show
    exits with status 0, and every hash is matching in the text and in the JSON.
    A file that no node anchors is then added to the repository and not
    committed. The repository differs from its commit, and node show still exits
    with status 0 for each node.

    :verifies: SEG-SREQ-320
    :test-id: SEG-TS-242
    """
    fixture = support.build_multi(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    for step in ("clean", "with an untracked file"):
        if step != "clean":
            base.write(fixture.repository, "notes.txt", "a file that no node anchors\n")
        for local_id, files in support.MULTI_FILES.items():
            shown = support.show(where, local_id, capsys)
            assert shown.status == 0, (step, local_id)
            for name in files:
                assert shown.entry(name)[support.KEY_STATUS] == support.MATCHING
                assert shown.block_status(name) == support.MATCHING


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-320"))
def test_node_show_exits_with_status_0_for_a_matching_hash_on_a_dirty_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 0, and names the dirty path, for a matching hash on it.

    A file of a requirement changes in the working tree and is not committed.
    Then the case is synced, so the case holds the hash of the changed content.
    The case holds no extraction revision for the node, because the path is
    dirty. node show for that requirement exits with status 0. Its hash is
    matching. The worktree line names the path that differs, and the JSON dirty
    paths are that one path.

    :verifies: SEG-SREQ-320
    :test-id: SEG-TS-243
    """
    fixture = base.build(tmp_path)
    fixture.rewrite("REQ-B", "an edit that nobody committed\n")
    support.sync(fixture, capsys)
    assert base.held_map(fixture.case, "REQ-B") == {}
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    assert shown.entry("contentHash")[support.KEY_STATUS] == support.MATCHING
    path = fixture.file("REQ-B")
    checkout = shown.entry("contentHash")[support.KEY_CHECKOUT]
    assert checkout[support.KEY_CHECKOUT_DIRTY] == [path]
    (line,) = shown.labelled("contentHash", support.LABEL_WORKTREE)
    assert path in line and support.CLEAN not in line.lower()


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-321"))
def test_node_show_exits_with_status_1_while_a_hash_differs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 1 while a named hash of the node differs.

    The case holds a test specification with the hashes specHash and implHash.
    A control run exits with status 0. Then the file of implHash changes in the
    working tree. The file of specHash does not change. node show exits with
    status 1, in the text and in the JSON, although specHash still matches.

    :verifies: SEG-SREQ-321
    :test-id: SEG-TS-244
    """
    fixture = support.build_multi(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    assert support.show(where, "TS-1", capsys).status == 0
    support.rewrite_hash_file(fixture, "TS-1", "implHash", "a changed implementation\n")
    shown = support.show(where, "TS-1", capsys)
    assert shown.status == 1
    assert shown.entry("specHash")[support.KEY_STATUS] == support.MATCHING
    assert shown.entry("implHash")[support.KEY_STATUS] == support.DIFFERING


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-321"))
def test_node_show_exits_with_status_1_while_a_hash_is_on_one_side_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show exits with status 1 while a named hash exists on one side only.

    The case holds two test specification records, each with the hashes specHash
    and implHash. A control run, over a current stream that supplies the same two
    records, exits with status 0 for each. Then the current record of the first
    node loses implHash. node show for it exits with status 1, and implHash is
    recorded only. Then the current record of the second node gains the hash
    apiHash. node show for it exits with status 1, and apiHash is current only.

    :verifies: SEG-SREQ-321
    :test-id: SEG-TS-245
    """
    fixture = base.build(tmp_path)
    first = support.node("TestSpecification", "TS-1", specHash="one", implHash="one impl")
    second = support.node("TestSpecification", "TS-2", specHash="two", implHash="two impl")
    case.AffirmationStore(root=fixture.case).write_nodes([first, second])
    where = support.place(fixture)
    base.supply(monkeypatch, support.listed(first, second))
    assert support.show(where, "TS-1", capsys).status == 0
    assert support.show(where, "TS-2", capsys).status == 0
    lost = support.node("TestSpecification", "TS-1", specHash="one")
    gained = support.node(
        "TestSpecification", "TS-2", specHash="two", implHash="two impl", apiHash="two api"
    )
    base.supply(monkeypatch, support.listed(lost, gained))
    shown = support.show(where, "TS-1", capsys)
    assert shown.status == 1
    assert shown.entry("implHash")[support.KEY_STATUS] == support.RECORDED_ONLY
    shown = support.show(where, "TS-2", capsys)
    assert shown.status == 1
    assert shown.entry("apiHash")[support.KEY_STATUS] == support.CURRENT_ONLY


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-321"))
def test_node_show_exits_with_status_1_while_the_current_stream_holds_no_such_node(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 1 while the current stream holds no node with the identifier.

    The case holds three requirements. A control run for REQ-C exits with status
    0. Then REQ-C is removed from the current store. node show for REQ-C exits
    with status 1, and not with status 2. Its hash is recorded only. The other
    requirements are not affected: node show for REQ-B still exits with status 0.

    :verifies: SEG-SREQ-321
    :test-id: SEG-TS-246
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    assert support.show(where, "REQ-C", capsys).status == 0
    support.drop_requirement(fixture, "REQ-C")
    shown = support.show(where, "REQ-C", capsys)
    assert shown.status == 1
    assert shown.entry("contentHash")[support.KEY_STATUS] == support.RECORDED_ONLY
    assert support.show(where, "REQ-B", capsys).status == 0


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-322"))
def test_node_show_exits_with_status_2_for_an_identifier_the_case_does_not_hold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 2 and names the identifier when the case holds no such node.

    The case holds three requirements. A control run for REQ-B exits with status
    0. The current store gains a fourth requirement, REQ-NEW, that the case does
    not hold. node show for REQ-NEW exits with status 2, although the current
    stream holds it. node show for UNKNOWN-9, which no side holds, also exits
    with status 2. In the text and in the JSON, the message names the identifier,
    and the report has no hash.

    :verifies: SEG-SREQ-322
    :test-id: SEG-TS-247
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    support.add_requirement(fixture, "REQ-NEW")
    where = support.place(fixture)
    assert support.show(where, "REQ-B", capsys).status == 0
    for local_id in ("REQ-NEW", "UNKNOWN-9"):
        shown = support.show(where, local_id, capsys)
        assert shown.status == 2, local_id
        assert local_id in shown.text
        assert local_id in shown.document[support.KEY_ERROR]
        assert support.KEY_HASHES not in shown.document


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-323"))
def test_node_show_exits_with_status_2_when_it_cannot_read_the_current_stream(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 2 when it cannot read the current stream it is given.

    The case holds three requirements. A control run for REQ-B exits with status
    0. Then node show is given, as the current stream, a directory that does not
    exist. It exits with status 2. It is then given a copy of the store whose
    manifest of requirements is not valid. It exits with status 2. In both cases
    the text and the JSON give a message and no hash.

    :verifies: SEG-SREQ-323
    :test-id: SEG-TS-248
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    assert support.show(where, "REQ-B", capsys).status == 0
    broken = tmp_path / "broken"
    shutil.copytree(fixture.root, broken)
    (broken / "nodes" / "requirements.toml").write_text("this is [not valid", encoding="utf-8")
    for unreadable in (tmp_path / "absent", broken):
        shown = support.show(where, "REQ-B", capsys, current=unreadable)
        assert shown.status == 2, unreadable.name
        assert shown.text.strip()
        assert support.KEY_ERROR in shown.document
        assert support.KEY_HASHES not in shown.document


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-230"))
def test_node_show_takes_no_run_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """node show takes no run bundle.

    The case holds three requirements. node show works without any option for a
    bundle and exits with status 0. The help of node show does not list the
    option --bundle. Given --bundle and the directory of a run bundle, node show
    ends with an argument error and exit status 2. It changes no file of the
    case.

    :verifies: SEG-SREQ-230
    :test-id: SEG-TS-249
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    assert support.show(where, "REQ-B", capsys).status == 0
    with pytest.raises(SystemExit) as stopped:
        main([*support.VERB, "--help"])
    assert stopped.value.code == 0
    assert "--bundle" not in support.output(capsys)
    bundle = evidence.copy_bundle(tmp_path)
    before = base.snapshot(fixture.case)
    with pytest.raises(SystemExit) as stopped:
        main([*support.VERB, "REQ-B", *where.arguments(), "--bundle", str(bundle)])
    assert stopped.value.code == 2
    assert base.snapshot(fixture.case) == before


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-142"))
def test_node_show_without_a_current_stream_or_a_producer_cannot_be_judged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show exits with status 2 when no current stream is given and no producer is configured.

    The case holds three requirements, and the configuration names no producer.
    A control run that is given a current stream exits with status 0. node show
    for REQ-B, given no current stream, exits with status 2 and gives a message.
    It changes no file of the case.

    :verifies: SEG-SREQ-142
    :test-id: SEG-TS-250
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    where = support.place(fixture)
    assert support.show(where, "REQ-B", capsys).status == 0
    before = base.snapshot(fixture.case)
    shown = support.show(where, "REQ-B", capsys, current=False)
    assert shown.status == 2
    assert shown.text.strip()
    assert support.KEY_HASHES not in shown.document
    assert base.snapshot(fixture.case) == before
