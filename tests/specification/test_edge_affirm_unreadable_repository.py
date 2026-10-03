"""Verification suite for edge affirm over a content repository that cannot be read.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds a git repository in ``tmp_path``, with commits that the test makes,
and runs ``affirmatrix.cli.main`` over it. The repository is made unreadable
after the commits, in five ways (see ``unreadable_support``), and each way is
one variant of the same specification. Every test also looks for a crash: a
command that ends in a traceback has no exit status of its own.

The edge is the one from REQ-C to REQ-A, or, over two repositories, the edge
that an implementation of one repository has to a requirement of the other. A
repository is named as the configuration names it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import extraction_support as base
from . import repository_reads_support as reads
from . import unreadable_support as support
from .provenance_support import red

pytestmark = base.requires_git

_NOT_REFUSED = "an unreadable repository ends the command in a traceback, with exit status 1"
_NAME_LOST = "the refusal does not name the repository that the configuration names"
_VARIANTS = pytest.mark.parametrize("variant", support.VARIANTS)


def _affirm_c(fixture: base.Fixture, capsys: pytest.CaptureFixture[str], *extra: str):
    """Affirm the edge from REQ-C to REQ-A. ``extra`` are more arguments."""
    arguments = [
        "edge", "affirm", "--case", str(fixture.case), "--config", str(fixture.config),
        "--current", str(fixture.current), "--kind", "Refines", "--from", "REQ-C",
        "--to", "REQ-A", "--role", "Reviewer", "--reason", "checked", *extra,
    ]  # fmt: skip
    return reads.attempt(arguments, capsys)


def _broken(variant: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> base.Fixture:
    reads.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=fixture.repository,
        config=fixture.config,
        name=fixture.name,
    )
    return fixture


@_VARIANTS
@red(363, _NOT_REFUSED)
def test_edge_affirm_refuses_when_the_repository_cannot_be_read(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge affirm refuses, naming the repository and the reason, when it cannot read it.

    The content repository of both endpoints cannot be read. It is made so in
    five ways, and each is a variant: its objects are removed, a stand-in git
    fails every call, the configuration maps it to a directory that holds no
    repository, the configuration maps it to a path that does not exist, and no
    git is on the path. No revision is given, so edge affirm has to discover
    one. Running edge affirm for the edge from REQ-C to REQ-A exits with status
    2. A line of the output names the repository as the configuration names it,
    and gives a reason. For the path that does not exist, the reason says that
    it does not exist. The output holds no traceback.

    :verifies: SEG-SREQ-363
    :test-id: SEG-TS-345
    """
    fixture = _broken(variant, monkeypatch, tmp_path)
    status, text = _affirm_c(fixture, capsys)
    assert status == 2
    assert support.TRACEBACK not in text
    assert fixture.name in text
    assert support.holds_reason(text, fixture.name, variant), text


@_VARIANTS
@red(364, _NOT_REFUSED)
def test_a_refused_edge_affirm_writes_nothing(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused edge affirm writes no review event, no edge record and no node record.

    A case is empty, and the content repository cannot be read, in each of the
    five ways of the variants. Running edge affirm for the edge from REQ-C to
    REQ-A, with no revision given, exits with status 2. Every file of the case
    has the same bytes after the command as before it, and the case holds no
    review event, no edge record and no node record.

    :verifies: SEG-SREQ-364
    :test-id: SEG-TS-346
    """
    fixture = _broken(variant, monkeypatch, tmp_path)
    before = base.tree(fixture.case)
    status, _ = _affirm_c(fixture, capsys)
    assert status == 2
    assert base.tree(fixture.case) == before
    assert base.held(fixture.case) == {}


@pytest.mark.parametrize("variant", ("objects", "stand-in"))
@pytest.mark.parametrize("which", ("to", "from"))
@red(364, _NOT_REFUSED)
def test_a_refused_edge_affirm_over_two_repositories_writes_nothing(
    which: str,
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When one endpoint is readable and one is not, edge affirm refuses and writes nothing.

    An implementation is in one repository and the requirement that it
    implements is in another. A first edge of the same kind is affirmed, so the
    run shows that the two repositories can be read. Then the repository of
    the requirement is made unreadable, or the repository of the implementation
    is. The repository is made unreadable by the removal of its objects, or by a
    stand-in git that fails every call that runs in it and passes every other.
    Running edge affirm for the second edge, with no revision given, exits with
    status 2 and names the repository that cannot be read. Every file of the case has the
    same bytes after the command as before it. The other repository, the
    readable one, is not named as the one that cannot be read.

    :verifies: SEG-SREQ-364
    :test-id: SEG-TS-347
    """
    reads.isolate(monkeypatch, tmp_path)
    shapes = support.two_repositories(tmp_path)
    status, _ = support.affirm_two(shapes, capsys, support.CONTROL_FROM, support.CONTROL_TO)
    assert status == 0
    name = support.break_one_of_two(which, variant, monkeypatch, tmp_path, shapes)
    other = (
        base.IMPLEMENTATIONS_REPOSITORY if name == base.REQUIREMENTS_REPOSITORY
        else base.REQUIREMENTS_REPOSITORY
    )  # fmt: skip
    before = base.tree(shapes.case)
    status, text = support.affirm_two(shapes, capsys)
    assert status == 2
    assert support.TRACEBACK not in text
    assert name in text
    assert other not in text
    assert base.tree(shapes.case) == before


@_VARIANTS
def test_edge_affirm_with_a_given_revision_reads_nothing_and_affirms(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A given revision is neither discovered nor checked, so edge affirm goes on.

    The content repository cannot be read, in each of the five ways of the
    variants, and a case holds no extraction revision. A revision is given on the
    command line. Running edge affirm for the edge from REQ-C to REQ-A exits
    with status 0 and prints the affirmed line for the edge. It writes the node
    records of the two endpoints, and neither carries an extraction revision.
    The output has a line that names the repository and gives the number 2, the
    count of node records written without a revision. The output holds no
    traceback.

    :verifies: SEG-SREQ-109
    :test-id: SEG-TS-348
    """
    fixture = _broken(variant, monkeypatch, tmp_path)
    status, text = _affirm_c(fixture, capsys, "--revision", base.GIVEN)
    assert status == 0
    assert support.TRACEBACK not in text
    assert "affirmed: REQ-C -> REQ-A (Refines)" in text
    records = base.held(fixture.case)
    assert sorted(records) == ["REQ-A", "REQ-C"]
    for local_id in records:
        assert base.held_map(fixture.case, local_id) == {}
    assert base.reported_counts(text, fixture.name) == [2]


@_VARIANTS
def test_edge_affirm_with_a_given_revision_keeps_a_held_extraction_revision(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A held extraction revision stays when the repository cannot be read.

    A case sync records the revision of the repository for every node. Then the
    repository is made unreadable, in each of the five ways of the variants. The
    content of the endpoints does not change. A revision is given on the command
    line. Running edge affirm for the edge from REQ-C to REQ-A exits with status
    0. The node record of each endpoint keeps the revision that case sync
    recorded. The output has no line that reports node records without a
    revision for the repository.

    :verifies: SEG-SREQ-308
    :test-id: SEG-TS-349
    """
    reads.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    assert reads.sync(fixture, capsys)[0] == 0
    recorded = reads.head(fixture.repository)
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=fixture.repository,
        config=fixture.config,
        name=fixture.name,
    )
    status, text = _affirm_c(fixture, capsys, "--revision", base.GIVEN)
    assert status == 0
    for local_id in ("REQ-A", "REQ-C"):
        assert base.held_map(fixture.case, local_id) == {fixture.name: recorded}
    assert reads.report_lines(text, fixture.name) == []
