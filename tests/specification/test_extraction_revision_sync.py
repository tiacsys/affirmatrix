"""Verification suite for the extraction revisions that case sync records.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds git repositories in ``tmp_path``, with commits that the test makes,
and runs ``affirmatrix.cli.main`` over them. The expected revision is always the
one git gives for the repository: ``git rev-parse HEAD``.

An extraction revision is held in the node records of the case. A test reads it
back through the store. A test that needs a case with a held revision makes it
with a first case sync, so that a failure points at the rule under test. A test
that needs a case without one writes the records through the library.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.records import ContentAnchor, NodeRecord

from . import extraction_support as support

pytestmark = support.requires_git


def _reason(claim: str) -> str:
    return f"{claim}: a node record has no extraction revision, and case sync records none"


def test_a_node_the_case_does_not_hold_gets_the_discovered_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync records the discovered revision for a node the case does not hold.

    A case is empty. A repository is configured and holds the committed content
    of three requirements. Running case sync exits with status 0. Each node
    record in the case carries the revision of the repository, as git gives it,
    for that repository.

    :verifies: SEG-SREQ-306
    :test-id: SEG-TS-199
    """
    fixture = support.build(tmp_path)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    for local_id in support.IDS:
        assert support.held_map(fixture.case, local_id) == {
            fixture.name: support.head(fixture.repository)
        }


def test_a_changed_hash_replaces_the_held_revision_with_the_discovered_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync replaces a held revision with the discovered one when the hash changes.

    A first case sync records the revision of the repository. Then the content of
    one requirement changes and the change is committed, so the repository is at
    a new revision. Running case sync again changes the content hash of that
    node record. It also changes the revision of the node record to the new
    revision of the repository.

    :verifies: SEG-SREQ-306
    :test-id: SEG-TS-200
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    first = support.head(fixture.repository)
    digests = support.held_digests(fixture.case, "REQ-B")
    fixture.rewrite("REQ-B", "a new statement of REQ-B\n")
    second = support.commit_all(fixture.repository, "change REQ-B")
    assert second != first
    assert support.sync(fixture, capsys)[0] == 0
    assert support.held_digests(fixture.case, "REQ-B") != digests
    assert support.held_map(fixture.case, "REQ-B") == {fixture.name: second}


def test_an_unchanged_hash_with_no_revision_held_gets_the_discovered_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync adds the discovered revision to a node record that holds none.

    The case holds three node records written with no extraction revision. The
    content has not changed, so running case sync writes the same content hashes.
    Each node record then carries the revision of the repository, as git gives
    it, for that repository.

    :verifies: SEG-SREQ-307
    :test-id: SEG-TS-201
    """
    fixture = support.build(tmp_path)
    support.seed_without_revisions(fixture)
    digests = {local_id: support.held_digests(fixture.case, local_id) for local_id in support.IDS}
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    for local_id in support.IDS:
        assert support.held_digests(fixture.case, local_id) == digests[local_id]
        assert support.held_map(fixture.case, local_id) == {
            fixture.name: support.head(fixture.repository)
        }


def test_an_unchanged_hash_keeps_the_held_revision_after_the_repository_moves_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync keeps a held revision while the content hashes are unchanged.

    A first case sync records the revision of the repository. Then a commit
    changes a file that no node anchors, so the repository is at a new revision
    and the content hashes are the same. Running case sync again keeps, in each
    node record, the first revision. It does not record the current revision of
    the repository, which is not the first one.

    :verifies: SEG-SREQ-308
    :test-id: SEG-TS-202
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    first = support.head(fixture.repository)
    support.write(fixture.repository, "unrelated.txt", "a file that no node anchors\n")
    assert support.commit_all(fixture.repository, "add an unrelated file") != first
    assert support.head(fixture.repository) != first
    assert support.sync(fixture, capsys)[0] == 0
    for local_id in support.IDS:
        assert support.held_map(fixture.case, local_id) == {fixture.name: first}


def test_an_unchanged_hash_keeps_the_held_revision_when_the_repository_is_not_configured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync keeps a held revision when no repository is configured any more.

    A first case sync records the revision of the repository. Then the
    configuration names no repository for the anchors, and the content is
    unchanged. Running case sync again exits with status 0. Each node record
    keeps the revision it held.

    :verifies: SEG-SREQ-308
    :test-id: SEG-TS-203
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    first = support.head(fixture.repository)
    support.configure(fixture, mapped=False)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    for local_id in support.IDS:
        assert support.held_map(fixture.case, local_id) == {fixture.name: first}


def test_a_changed_hash_over_an_uncommitted_change_drops_the_held_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync drops a held revision when the changed content is not committed.

    A first case sync records the revision of the repository. Then the content of
    one requirement changes in the working tree and is not committed. Running case
    sync again exits with status 0. It writes the new content hash for that node
    record. The node record carries no revision for the repository. The first
    revision is not kept.

    :verifies: SEG-SREQ-309
    :test-id: SEG-TS-204
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    assert support.held_map(fixture.case, "REQ-B") != {}
    digests = support.held_digests(fixture.case, "REQ-B")
    fixture.rewrite("REQ-B", "an edit that nobody committed\n")
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert support.held_digests(fixture.case, "REQ-B") != digests
    assert support.held_map(fixture.case, "REQ-B") == {}


def test_a_changed_hash_for_a_repository_that_is_not_configured_drops_the_held_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync drops a held revision when the repository is not configured.

    A first case sync records the revision of the repository. Then the content of
    one requirement changes and is committed, and the configuration names no
    repository for the anchors. Running case sync again exits with status 0, and
    does not refuse. It writes the new content hash for that node record. The node
    record carries no revision for the repository.

    :verifies: SEG-SREQ-309
    :test-id: SEG-TS-205
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    assert support.held_map(fixture.case, "REQ-B") != {}
    digests = support.held_digests(fixture.case, "REQ-B")
    fixture.rewrite("REQ-B", "a committed edit of REQ-B\n")
    support.commit_all(fixture.repository, "change REQ-B")
    support.configure(fixture, mapped=False)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert support.held_digests(fixture.case, "REQ-B") != digests
    assert support.held_map(fixture.case, "REQ-B") == {}


def test_a_changed_hash_for_a_directory_that_is_not_a_repository_drops_the_held_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync drops a held revision when the configured directory is not a repository.

    A first case sync records the revision of the repository. Then the content of
    one requirement changes and is committed. The configuration now maps the
    repository name to a directory that is not a git repository. Running case sync
    again exits with status 0, and does not refuse. It writes the new content hash
    for that node record. The node record carries no revision for the repository.

    :verifies: SEG-SREQ-309
    :test-id: SEG-TS-219
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    assert support.held_map(fixture.case, "REQ-B") != {}
    digests = support.held_digests(fixture.case, "REQ-B")
    fixture.rewrite("REQ-B", "a committed edit of REQ-B\n")
    support.commit_all(fixture.repository, "change REQ-B")
    plain = tmp_path / "plain-directory"
    plain.mkdir()
    support.configure(fixture, mapped=True, directory=plain)
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    assert support.held_digests(fixture.case, "REQ-B") != digests
    assert support.held_map(fixture.case, "REQ-B") == {}


def test_a_path_the_repository_does_not_hold_gives_no_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync records no revision for a node whose anchored path the repository lacks.

    Two repositories are configured and committed, and neither has a change that
    is not committed. The requirement reader anchors each requirement at a source
    file that the first repository does not hold at its revision. The
    implementation reader anchors at files that the second repository holds.
    Running case sync exits with status 0. Each requirement record carries no
    revision. Each implementation record carries the revision of the second
    repository.

    :verifies: SEG-SREQ-309
    :test-id: SEG-TS-206
    """
    shapes = support.build_shapes(tmp_path, held_paths=False)
    status, _ = support.sync_shapes(shapes, capsys)
    assert status == 0
    for local_id in ("R-1", "R-2", "R-3"):
        assert support.held_map(shapes.case, local_id) == {}
    for local_id in ("I-LIB-MAX", "I-LIB-MIN"):
        assert support.held_map(shapes.case, local_id) == {
            support.IMPLEMENTATIONS_REPOSITORY: support.head(shapes.implementations)
        }


def test_the_report_names_the_repository_and_the_count_of_records_without_a_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync reports each repository and the number of records written without a revision.

    A first case sync, with every anchored file committed, prints no line that
    names the repository. Then the content of two of the three requirements
    changes in the working tree and is not committed. Running case sync again
    exits with status 0. Its output has a line that names the repository and
    gives the number 2, which is the number of node records written without a
    revision for it.

    :verifies: SEG-SREQ-310
    :test-id: SEG-TS-207
    """
    fixture = support.build(tmp_path)
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert support.reported_counts(text, fixture.name) == []
    fixture.rewrite("REQ-A", "an edit that nobody committed\n")
    fixture.rewrite("REQ-B", "another edit that nobody committed\n")
    status, text = support.sync(fixture, capsys)
    assert status == 0
    assert support.reported_counts(text, fixture.name) == [2]


def test_the_report_counts_the_records_without_a_revision_for_each_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync reports the count of records without a revision for each repository.

    Two repositories are configured. The requirement reader anchors its three
    records at paths that the first repository does not hold. The implementation
    reader anchors at paths that the second repository holds. Running case sync
    exits with status 0. Its output has a line that names the first repository
    and gives the number 3. No line names the second repository.

    :verifies: SEG-SREQ-310
    :test-id: SEG-TS-208
    """
    shapes = support.build_shapes(tmp_path, held_paths=False)
    status, text = support.sync_shapes(shapes, capsys)
    assert status == 0
    assert support.reported_counts(text, support.REQUIREMENTS_REPOSITORY) == [3]
    assert support.reported_counts(text, support.IMPLEMENTATIONS_REPOSITORY) == []


def test_each_node_gets_the_revision_of_the_repository_its_anchors_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync records one revision for each repository that the anchors name.

    Two repositories are configured, committed and unchanged. The two have
    different revisions. The requirement reader anchors at source files in the
    first repository. The implementation reader anchors at files in the second
    repository. Running case sync exits with status 0. Each requirement record
    carries the revision of the first repository for that repository only. Each
    implementation record carries the revision of the second repository for
    that repository only.

    :verifies: SEG-SREQ-306
    :test-id: SEG-TS-209
    """
    shapes = support.build_shapes(tmp_path, held_paths=True)
    first, second = support.head(shapes.requirements), support.head(shapes.implementations)
    assert first != second
    status, _ = support.sync_shapes(shapes, capsys)
    assert status == 0
    for local_id in ("R-1", "R-2", "R-3"):
        assert support.held_map(shapes.case, local_id) == {support.REQUIREMENTS_REPOSITORY: first}
    for local_id in ("I-LIB-MAX", "I-LIB-MIN"):
        assert support.held_map(shapes.case, local_id) == {
            support.IMPLEMENTATIONS_REPOSITORY: second
        }


def test_a_node_whose_anchors_name_two_repositories_gets_a_revision_for_each(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """case sync records a revision for each repository that one node's anchors name.

    Two repositories are configured and committed. One implementation anchors its
    api hash in the first repository and its body hash in the second. Another
    implementation anchors the same way, but the file it names in the second
    repository has a change that is not committed. Running case sync exits with
    status 0. The first node record carries the revision of each repository. The
    second node record carries the revision of the first repository only.

    :verifies: SEG-SREQ-306
    :test-id: SEG-TS-210
    """
    monkeypatch.chdir(tmp_path)
    left = support.init_repository(tmp_path / "left")
    right = support.init_repository(tmp_path / "right")
    support.write(left, "api.txt", "the api\n")
    support.write(right, "first.txt", "the first body\n")
    support.write(right, "second.txt", "the second body\n")
    support.commit_all(left, "left")
    support.commit_all(right, "right")
    support.write(right, "second.txt", "a second body nobody committed\n")

    def anchor(repository: str, path: str, root: Path) -> ContentAnchor:
        digest = hashlib.sha256((root / path).read_bytes()).digest()
        return ContentAnchor(digest=digest, repository=repository, path=path, locator="file")

    def node(local_id: str, body: str) -> NodeRecord:
        return NodeRecord(
            local_id=local_id,
            kind="Implementation",
            content_anchors={
                "apiHash": anchor("leftrepo", "api.txt", left),
                "bodyHash": anchor("rightrepo", body, right),
            },
        )

    source = support.ListedSource(
        (node("IMPL-CLEAN", "first.txt"), node("IMPL-DIRTY", "second.txt"))
    )
    support.supply(monkeypatch, source)
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    configuration = tmp_path / "two-repositories.yaml"
    configuration.write_text(
        json.dumps({"repositories": {"leftrepo": str(left), "rightrepo": str(right)}}),
        encoding="utf-8",
    )
    capsys.readouterr()
    arguments = ["case", "sync", "--case", str(case_root), "--config", str(configuration)]
    assert main(arguments) == 0
    assert support.held_map(case_root, "IMPL-CLEAN") == {
        "leftrepo": support.head(left),
        "rightrepo": support.head(right),
    }
    assert support.held_map(case_root, "IMPL-DIRTY") == {"leftrepo": support.head(left)}


def test_a_held_revision_for_a_repository_the_anchors_no_longer_name_is_not_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync keeps no held revision for a repository that the anchors no longer name.

    Two repositories are configured and committed. A first case sync records, in
    each requirement record, the revision of the first repository. Then the
    configuration moves the requirement reader to a new repository name that maps
    to the same directory. The paths and the content hashes are the same. Running
    case sync again exits with status 0. Each requirement record carries the
    revision for the new name only. It carries none for the old name.

    :verifies: SEG-SREQ-308
    :test-id: SEG-TS-222
    """
    shapes = support.build_shapes(tmp_path, held_paths=True)
    revision = support.head(shapes.requirements)
    assert support.sync_shapes(shapes, capsys)[0] == 0
    for local_id in ("R-1", "R-2", "R-3"):
        assert support.held_map(shapes.case, local_id) == {
            support.REQUIREMENTS_REPOSITORY: revision
        }
    digests = {local_id: support.held_digests(shapes.case, local_id) for local_id in ("R-1", "R-3")}
    support.move_requirements_to(shapes, "movedrepo")
    assert support.sync_shapes(shapes, capsys)[0] == 0
    for local_id in ("R-1", "R-2", "R-3"):
        assert support.held_map(shapes.case, local_id) == {"movedrepo": revision}
    for local_id, before in digests.items():
        assert support.held_digests(shapes.case, local_id) == before


def test_a_schema_copy_without_the_field_refuses_the_sync_until_it_is_refreshed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """case sync writes nothing when the schema copy of the case predates the field.

    The schema copy of a case has the extraction revision property removed from
    every node schema. Running case sync, which records revisions, exits with
    status 2 and changes no file of the case. After case refresh, the same case
    sync exits with status 0 and records the revision of the repository in each
    node record.

    :verifies: SEG-SREQ-212
    :test-id: SEG-TS-215
    """
    fixture = support.build(tmp_path)
    for schema_path in sorted((fixture.case / "schema").glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema.get("properties", {}).pop(support.JSON_KEY, None)
        schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    before = support.tree(fixture.case)
    status, _ = support.sync(fixture, capsys)
    assert status == 2
    assert support.tree(fixture.case) == before
    assert main(["case", "refresh", "--case", str(fixture.case)]) == 0
    status, _ = support.sync(fixture, capsys)
    assert status == 0
    for local_id in support.IDS:
        assert support.held_map(fixture.case, local_id) == {
            fixture.name: support.head(fixture.repository)
        }
