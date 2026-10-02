"""Verification suite for what ``node show`` reports about one node.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds git repositories in ``tmp_path``, with commits that the test makes.
It writes a case with ``case sync`` or through the library. Then it runs
``affirmatrix.cli.main`` as an operator would. The command runs twice for each
check: once for the text report and once for the JSON report with full digests.
Both runs must give the same exit status and the same facts.

The expected values come from git, from the files of the repositories and from
``hashlib``. The revision is ``git rev-parse HEAD``. A digest is the SHA-256 of
the file that a hash covers. The content is the text of that file. The names of
the options, the keys of the JSON report and the labels of the text report are
in ``node_show_support``.

Two stores serve the tests. The first holds three requirements in one repository.
The second holds a requirement, a test specification (two hashes) and an
implementation (two hashes), also in one repository. A third world has two
repositories with different revisions, built from the capture-shape fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.records import NodeRecord

from . import extraction_support as base
from . import node_show_support as support

pytestmark = support.requires_git


def _reason(claim: str, what: str) -> str:
    return f"{claim}: there is no node show verb, so the command does not {what}"


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-313", "show a node"))
def test_node_show_resolves_a_node_by_its_identifier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show shows the node that has the identifier it is given, as its own verb.

    The case holds three requirements. The help of the noun node lists the verb
    show. Running node show with the identifier REQ-B exits with status 0. Its
    text report names REQ-B and the kind Requirement. Its JSON report has the
    identifier REQ-B, the kind Requirement and one entry for contentHash. Running
    it with REQ-C names REQ-C and not REQ-B.

    :verifies: SEG-SREQ-313
    :test-id: SEG-TS-233
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    with pytest.raises(SystemExit) as stopped:
        main([support.VERB[0], "--help"])
    assert stopped.value.code == 0
    assert support.VERB[1] in support.output(capsys)
    where = support.place(fixture)
    shown = support.show(where, "REQ-B", capsys)
    assert shown.status == 0
    assert "REQ-B" in shown.text and "Requirement" in shown.text
    assert shown.document[support.KEY_ID] == "REQ-B"
    assert shown.document[support.KEY_KIND] == "Requirement"
    assert set(shown.hashes()) == {"contentHash"}
    other = support.show(where, "REQ-C", capsys)
    assert other.document[support.KEY_ID] == "REQ-C"
    assert "REQ-C" in other.text and "REQ-B" not in other.text


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-314", "compare each hash"))
def test_node_show_compares_every_named_hash_of_the_node(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports the comparison of the current and the recorded digest of each hash.

    The case holds a test specification with the hashes specHash and implHash.
    Then the file that implHash covers changes and is committed. The file of
    specHash does not change. The report has one block for each of the two hash
    names. specHash is matching and implHash is differing, in the text and in the
    JSON. In the JSON, each entry gives the recorded digest the case holds and
    the current digest of the file, in full.

    :verifies: SEG-SREQ-314
    :test-id: SEG-TS-234
    """
    fixture = support.build_multi(tmp_path)
    support.sync(fixture, capsys)
    support.rewrite_hash_file(fixture, "TS-1", "implHash", "a new implementation\n")
    base.commit_all(fixture.repository, "change the implementation")
    shown = support.show(support.place(fixture), "TS-1", capsys)
    assert set(shown.hashes()) == {"specHash", "implHash"}
    for name, status in (("specHash", support.MATCHING), ("implHash", support.DIFFERING)):
        entry = shown.entry(name)
        assert entry[support.KEY_STATUS] == status
        assert shown.block_status(name) == status
        assert entry[support.KEY_RECORDED] == support.recorded_hex(fixture, "TS-1", name)
        assert entry[support.KEY_CURRENT] == support.current_hex(fixture, "TS-1", name)
    assert support.recorded_hex(fixture, "TS-1", "implHash") != support.current_hex(
        fixture, "TS-1", "implHash"
    )


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-315", "show the current content"))
def test_node_show_shows_the_current_content_of_every_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports, for each named hash, the bytes that the current stream supplies.

    The case holds a test specification and an implementation, each with two
    hashes. Then the file of specHash changes in the working tree and is not
    committed. For the test specification, the text of the specHash block shows
    the new text of the file. The text of the implHash block shows the text that
    the file still has. The JSON content of each hash is the text of its file,
    and the SHA-256 of that text is the current digest of the hash. The same
    holds for each hash of the implementation. No block says that no content is
    supplied.

    :verifies: SEG-SREQ-315
    :test-id: SEG-TS-235
    """
    fixture = support.build_multi(tmp_path)
    support.sync(fixture, capsys)
    support.rewrite_hash_file(fixture, "TS-1", "specHash", "the new first line\nthe new second\n")
    where = support.place(fixture)
    for local_id in ("TS-1", "IMP-1"):
        shown = support.show(where, local_id, capsys)
        assert set(shown.hashes()) == set(support.MULTI_FILES[local_id])
        for name in support.MULTI_FILES[local_id]:
            expected = support.current_text(fixture, local_id, name)
            entry = shown.entry(name)
            assert entry[support.KEY_CONTENT] == expected
            assert (
                support.hex_of(entry[support.KEY_CONTENT].encode("utf-8"))
                == entry[support.KEY_CURRENT]
            )
            assert shown.shown_content(name) == expected.splitlines()
            assert support.NONE_SUPPLIED not in shown.block_text(name).lower()


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-316", "say that no content is supplied"))
def test_node_show_says_when_the_source_supplies_no_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show reports that none is supplied for a hash when the source supplies no content.

    The case holds a waiver and a requirement. The current stream is a record
    source that reads no content and supplies the same two records. For each of
    the two nodes, node show exits with status 0, because the hash matches. The
    block of the hash says that no content is supplied. The JSON content is
    null. The report does not show any content.

    :verifies: SEG-SREQ-316
    :test-id: SEG-TS-236
    """
    fixture = base.build(tmp_path)
    waiver = NodeRecord(
        local_id="WAIVER-1",
        kind="Waiver",
        content_anchors={"contentHash": support.anchor("a waiver", repository="waivers")},
        expiry="2030-01-01",
        approver="Approver",
    )
    requirement = support.node("Requirement", "REQ-W", contentHash="a statement")
    case.AffirmationStore(root=fixture.case).write_nodes([waiver, requirement])
    base.supply(monkeypatch, support.listed(waiver, requirement))
    where = support.place(fixture)
    for local_id in ("WAIVER-1", "REQ-W"):
        shown = support.show(where, local_id, capsys)
        assert shown.status == 0, local_id
        assert support.NONE_SUPPLIED in shown.block_text("contentHash").lower()
        assert shown.entry("contentHash")[support.KEY_CONTENT] is None
        assert shown.shown_content("contentHash") == []


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-317", "show the recorded revision"))
def test_node_show_reports_the_recorded_revision_of_the_recorded_anchors_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports the extraction revision the case records for the anchor's repository.

    A case is synced over two repositories that are at different revisions. A
    requirement anchors in the first and an implementation in the second. For the
    requirement, node show gives the revision of the first repository as the
    extraction revision, in the text and in the JSON. It does not give the
    revision of the second. For the implementation, in both of its
    hashes, it gives the revision of the second repository and not the first.

    :verifies: SEG-SREQ-317
    :test-id: SEG-TS-237
    """
    shapes = base.build_shapes(tmp_path, held_paths=True)
    status, out = base.sync_shapes(shapes, capsys)
    assert status == 0, out
    required = base.head(shapes.requirements)
    implemented = base.head(shapes.implementations)
    assert required != implemented
    where = support.place_shapes(shapes)
    shown = support.show(where, "R-1", capsys)
    assert shown.entry("contentHash")[support.KEY_RECORDED_REVISION] == required
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert required in line and implemented not in line
    shown = support.show(where, "I-LIB-MAX", capsys)
    for name in ("apiHash", "bodyHash"):
        assert shown.entry(name)[support.KEY_RECORDED_REVISION] == implemented
        (line,) = shown.labelled(name, support.LABEL_EXTRACTED)
        assert implemented in line and required not in line


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-317", "say that no revision is recorded"))
def test_node_show_says_when_the_case_records_no_extraction_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports that none is recorded for a node record that has no extraction revision.

    The case holds three requirement records written with no extraction revision,
    as a case written by an older version holds them. The content has not
    changed. node show exits with status 0. The text says that none is recorded,
    and the JSON revision is null. After a case sync adds the revision, the text
    gives the revision and no longer says that none is recorded.

    :verifies: SEG-SREQ-317
    :test-id: SEG-TS-238
    """
    fixture = base.build(tmp_path)
    base.seed_without_revisions(fixture)
    assert base.held_map(fixture.case, "REQ-B") == {}
    where = support.place(fixture)
    shown = support.show(where, "REQ-B", capsys)
    assert shown.status == 0
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert support.NONE_RECORDED in line.lower()
    assert shown.entry("contentHash")[support.KEY_RECORDED_REVISION] is None
    support.sync(fixture, capsys)
    revision = base.head(fixture.repository)
    shown = support.show(where, "REQ-B", capsys)
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert revision in line and support.NONE_RECORDED not in line.lower()
    assert shown.entry("contentHash")[support.KEY_RECORDED_REVISION] == revision


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-318", "show the checkout's revision"))
def test_node_show_reports_the_revision_the_current_anchors_repository_is_at(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports the revision of the repository the current anchor names.

    A case sync records the revision of the repository. Then a commit changes a
    file that no node anchors, so the repository is at a new revision. node show
    for a requirement gives the new revision as the revision of the checkout,
    in the text and in the JSON. It gives the first revision, and only that
    one, as the revision the node was extracted from.

    :verifies: SEG-SREQ-318
    :test-id: SEG-TS-239
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    first = base.head(fixture.repository)
    base.write(fixture.repository, "unrelated.txt", "a file that no node anchors\n")
    second = base.commit_all(fixture.repository, "add an unrelated file")
    assert second != first
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    checkout = shown.entry("contentHash")[support.KEY_CHECKOUT]
    assert checkout[support.KEY_CHECKOUT_REVISION] == second
    assert checkout[support.KEY_CHECKOUT_CONFIGURED] is True
    (line,) = shown.labelled("contentHash", support.LABEL_CHECKOUT)
    assert second in line and first not in line
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert first in line and second not in line


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-318", "say that none is configured"))
def test_node_show_says_when_no_repository_is_configured_for_the_current_anchor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports that no repository is configured for a current anchor that names none.

    A case sync records the revision of the repository. Then the configuration
    maps no repository for the name that the anchors carry. node show exits with
    status 0 and the hash matches. The checkout line says that no repository is
    configured. It gives no revision, and the JSON checkout has no revision.
    The extraction revision is still the one the case records.

    :verifies: SEG-SREQ-318
    :test-id: SEG-TS-240
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    recorded = base.head(fixture.repository)
    base.configure(fixture, mapped=False)
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    (line,) = shown.labelled("contentHash", support.LABEL_CHECKOUT)
    assert support.NOT_CONFIGURED in line.lower()
    assert recorded not in line
    checkout = shown.entry("contentHash")[support.KEY_CHECKOUT]
    assert checkout[support.KEY_CHECKOUT_CONFIGURED] is False
    assert checkout[support.KEY_CHECKOUT_REVISION] is None
    assert shown.entry("contentHash")[support.KEY_RECORDED_REVISION] == recorded


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-319", "name the paths that differ"))
def test_node_show_names_each_anchored_path_that_differs_from_its_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show reports whether the anchored paths match their commit, naming each that differs.

    The case holds a requirement, a test specification and an implementation,
    in one repository. After the sync, the two files of the test specification
    and one file of the implementation change in the working tree and are not
    committed. For the test specification, the worktree line names its two
    paths and no other, and the JSON dirty paths are those two. For the
    implementation, they are its one changed path. For the requirement, the line
    says clean, names no path, and the JSON dirty paths are empty.

    :verifies: SEG-SREQ-319
    :test-id: SEG-TS-241
    """
    fixture = support.build_multi(tmp_path)
    support.sync(fixture, capsys)
    changed = {
        ("TS-1", "specHash"): "changed spec\n",
        ("TS-1", "implHash"): "changed impl\n",
        ("IMP-1", "apiHash"): "changed api\n",
    }
    for (local_id, name), text in changed.items():
        support.rewrite_hash_file(fixture, local_id, name, text)
    where = support.place(fixture)
    expected = {
        "TS-1": sorted(support.MULTI_FILES["TS-1"].values()),
        "IMP-1": [support.MULTI_FILES["IMP-1"]["apiHash"]],
        "REQ-A": [],
    }
    for local_id, paths in expected.items():
        shown = support.show(where, local_id, capsys)
        for name in support.MULTI_FILES[local_id]:
            entry = shown.entry(name)
            assert sorted(entry[support.KEY_CHECKOUT][support.KEY_CHECKOUT_DIRTY]) == paths
            (line,) = shown.labelled(name, support.LABEL_WORKTREE)
            for path in sorted(support.MULTI_FILES["IMP-1"].values()) + sorted(
                support.MULTI_FILES["TS-1"].values()
            ):
                assert (path in line) == (path in paths), (local_id, name, path)
            assert (support.CLEAN in line.lower()) == (paths == [])
