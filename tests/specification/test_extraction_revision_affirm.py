"""Verification suite for the extraction revisions that edge affirm records.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds a git repository in ``tmp_path``, with commits that the test makes,
and runs ``affirmatrix.cli.main`` over it. Edge affirm writes the node records of
the two endpoints of the edge, and it writes them under the same rule as case
sync. The edge is the one from REQ-B to REQ-A.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as support

pytestmark = support.requires_git


def _reason(claim: str) -> str:
    return f"{claim}: a node record has no extraction revision, and edge affirm records none"


def test_edge_affirm_records_the_discovered_revision_in_both_endpoint_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm records the discovered revision in the node record of each endpoint.

    A case is empty. A repository is configured and holds the committed content
    of both endpoints. Running edge affirm exits with status 0. The case then
    holds the node records of the two endpoints and no other. Each of the two
    records carries the revision of the repository, as git gives it, for that
    repository.

    :verifies: SEG-SREQ-306
    :test-id: SEG-TS-211
    """
    fixture = support.build(tmp_path)
    status, _ = support.affirm(fixture, capsys)
    assert status == 0
    records = support.held(fixture.case)
    assert sorted(records) == ["REQ-A", "REQ-B"]
    for local_id in records:
        assert support.held_map(fixture.case, local_id) == {
            fixture.name: support.head(fixture.repository)
        }


def test_edge_affirm_keeps_the_held_revision_of_an_unchanged_endpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm keeps a held revision while the content hashes are unchanged.

    A case sync records the revision of the repository. Then a commit changes a
    file that no node anchors, so the repository is at a new revision and the
    content hashes are the same. Running edge affirm exits with status 0. The
    node record of each endpoint keeps the first revision. It does not carry the
    current revision of the repository, which is not the first one.

    :verifies: SEG-SREQ-308
    :test-id: SEG-TS-212
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    first = support.head(fixture.repository)
    support.write(fixture.repository, "unrelated.txt", "a file that no node anchors\n")
    assert support.commit_all(fixture.repository, "add an unrelated file") != first
    status, _ = support.affirm(fixture, capsys)
    assert status == 0
    for local_id in ("REQ-A", "REQ-B"):
        assert support.held_map(fixture.case, local_id) == {fixture.name: first}


def test_edge_affirm_drops_the_held_revision_of_an_endpoint_changed_and_not_committed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm drops a held revision when the changed content is not committed.

    A case sync records the revision of the repository. Then the content of one
    endpoint changes in the working tree and is not committed. A revision is
    given on the command line, so that edge affirm does not refuse. Running edge
    affirm exits with status 0. The node record of the changed endpoint holds the
    new content hash and carries no revision for the repository. The given
    revision is in no node record.

    :verifies: SEG-SREQ-309
    :test-id: SEG-TS-213
    """
    fixture = support.build(tmp_path)
    assert support.sync(fixture, capsys)[0] == 0
    assert support.held_map(fixture.case, "REQ-B") != {}
    digests = support.held_digests(fixture.case, "REQ-B")
    fixture.rewrite("REQ-B", "an edit that nobody committed\n")
    status, _ = support.affirm(fixture, capsys, "--revision", support.GIVEN)
    assert status == 0
    assert support.held_digests(fixture.case, "REQ-B") != digests
    assert support.held_map(fixture.case, "REQ-B") == {}
    for node in support.held(fixture.case).values():
        assert support.GIVEN not in support.extracted_from(node).values()


def test_a_revision_given_on_the_command_line_is_never_an_extraction_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm never records a revision that the operator gives as an extraction revision.

    A revision that is not the revision of the repository is given on the command
    line. In a first case, the repository is configured and committed. Running
    edge affirm exits with status 0. The node records of the endpoints carry the
    revision of the repository, not the given one. In a second case, the
    configuration names no repository for the anchors. Running edge affirm exits
    with status 0, and the node records carry no revision at all.

    :verifies: SEG-SREQ-327
    :test-id: SEG-TS-214
    """
    first = support.build(tmp_path / "first")
    assert support.head(first.repository) != support.GIVEN
    status, _ = support.affirm(first, capsys, "--revision", support.GIVEN)
    assert status == 0
    for local_id in ("REQ-A", "REQ-B"):
        assert support.held_map(first.case, local_id) == {
            first.name: support.head(first.repository)
        }
    second = support.build(tmp_path / "second", mapped=False)
    status, _ = support.affirm(second, capsys, "--revision", support.GIVEN)
    assert status == 0
    for local_id in ("REQ-A", "REQ-B"):
        assert support.held_map(second.case, local_id) == {}


def test_edge_affirm_reports_the_repository_and_the_count_of_records_without_a_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """edge affirm reports each repository and the number of records written without a revision.

    The content of both endpoints changes in the working tree and is not
    committed. A revision is given on the command line, so that edge affirm does
    not refuse. A case is empty. Running edge affirm exits with status 0. Its
    output has a line that names the repository and gives the number 2.

    :verifies: SEG-SREQ-310
    :test-id: SEG-TS-218
    """
    fixture = support.build(tmp_path)
    fixture.rewrite("REQ-A", "an edit that nobody committed\n")
    fixture.rewrite("REQ-B", "another edit that nobody committed\n")
    status, text = support.affirm(fixture, capsys, "--revision", support.GIVEN)
    assert status == 0
    assert support.reported_counts(text, fixture.name) == [2]
