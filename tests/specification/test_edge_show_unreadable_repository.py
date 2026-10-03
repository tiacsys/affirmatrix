"""Verification suite for edge show over a content repository that cannot be read.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test builds a git repository in ``tmp_path``, with commits that the test makes,
affirms an edge while the repository is healthy, and then makes the repository
unreadable, in five ways (see ``unreadable_support``). Each way is one variant of
the same specification. Edge show with the verbose rendering recovers the
content of each endpoint at the revision of the last affirmation, so it reads
the repository. Every test also looks for a crash: a command that ends in a
traceback has no exit status of its own.

The edge is the one from REQ-B to REQ-A, or, over two repositories, the edge
that an implementation of one repository has to a requirement of the other. A
repository is named as the configuration names it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from . import extraction_support as base
from . import node_show_support as nodes
from . import provenance_support as prov
from . import repository_reads_support as reads
from . import unreadable_support as support
from .provenance_support import red

pytestmark = base.requires_git

_CRASH = "an unreadable repository ends edge show in a traceback, with exit status 1"
_VARIANTS = pytest.mark.parametrize("variant", support.VARIANTS)
_LINE = re.compile(
    r"^\s*before-content @ (?P<end>from|to) \(revision (?P<revision>[0-9a-f]{40})\)"
    r": not available: (?P<rest>.*)$"
)


def _affirmed_then_broken(
    variant: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> tuple[base.Fixture, str]:
    """A fixture whose edge is affirmed, then made unreadable. Give it and the affirmed revision."""
    reads.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    assert reads.affirm(fixture, capsys)[0] == 0
    revision = reads.head(fixture.repository)
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=fixture.repository,
        config=fixture.config,
        name=fixture.name,
    )
    return fixture, revision


def _show_text(fixture: base.Fixture, capsys, *extra: str) -> tuple[int, str]:
    arguments = ["edge", "show", "-v", *nodes.place(fixture).arguments(), *extra]
    return reads.attempt(arguments, capsys)


def _two_affirmed(
    which: str, variant: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> tuple[base.Shapes, str, dict[str, str]]:
    """Two repositories, an edge between them affirmed, and one repository made unreadable.

    Give the shapes, the configured name of the broken repository, and the
    revision that each end was affirmed at.
    """
    reads.isolate(monkeypatch, tmp_path)
    shapes = support.two_repositories(tmp_path)
    assert support.affirm_two(shapes, capsys)[0] == 0
    revisions = {
        "from": reads.head(shapes.implementations),
        "to": reads.head(shapes.requirements),
    }
    name = support.break_one_of_two(which, variant, monkeypatch, tmp_path, shapes)
    return shapes, name, revisions


@_VARIANTS
@red(365, _CRASH)
def test_edge_show_reports_before_content_it_cannot_read_as_not_available(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show reports before-content it cannot read as not available.

    The edge from REQ-B to REQ-A is affirmed. Then the content repository cannot
    be read, in each of the five ways of the variants. Running edge show with the
    verbose rendering exits with status 0 and writes no traceback. For each
    endpoint, one line has the word before-content, the name of the endpoint, the
    words not available, the name of the repository as the configuration names
    it, and a reason. For the path that does not exist, the reason says that it
    does not exist.

    :verifies: SEG-SREQ-365
    :test-id: SEG-TS-350
    """
    fixture, _ = _affirmed_then_broken(variant, monkeypatch, tmp_path, capsys)
    status, text = _show_text(fixture, capsys)
    assert status == 0
    assert support.TRACEBACK not in text
    for end in ("from", "to"):
        (line,) = [line for line in text.splitlines() if f"before-content @ {end}" in line]
        assert "not available" in line
        assert support.holds_reason(line, fixture.name, variant), line


@pytest.mark.parametrize("variant", ("objects", "stand-in"))
@pytest.mark.parametrize("which", ("to", "from"))
@red(365, _CRASH)
def test_edge_show_still_shows_the_content_of_the_endpoint_that_it_can_read(
    which: str,
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show shows the content of the readable endpoint, and says the other is not available.

    An implementation is in one repository and the requirement that it
    implements is in another. The edge between them is affirmed. Then the
    repository of the requirement cannot be read, or the repository of the
    implementation cannot be. It is made unreadable by the removal of its
    objects, or by a stand-in git that fails every call that runs in it. Running
    edge show with the verbose rendering exits with status 0. The endpoint in the
    readable repository shows the content that it had at its affirmation. The
    other endpoint has a line that says that its before-content is not available
    and names its repository.

    :verifies: SEG-SREQ-365
    :test-id: SEG-TS-351
    """
    shapes, name, _ = _two_affirmed(which, variant, monkeypatch, tmp_path, capsys)
    status, text = support.show_two(shapes, capsys)
    assert status == 0
    assert support.TRACEBACK not in text
    broken, readable = ("to", "from") if which == "to" else ("from", "to")
    (line,) = [line for line in text.splitlines() if f"before-content @ {broken}" in line]
    assert "not available" in line
    assert name in line
    (header,) = [line for line in text.splitlines() if f"before-content @ {readable}" in line]
    assert "not available" not in header
    marker = "#define LIB_MAX 8" if readable == "from" else "TITLE: alpha"
    assert marker in text


@_VARIANTS
@red(366, _CRASH)
def test_an_unreadable_before_content_does_not_change_the_exit_of_edge_show(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edge show gives the same exit status whether or not it can read the before-content.

    The edge from REQ-B to REQ-A is affirmed. Then the content of REQ-A changes
    in the working tree, so the edge is suspect. A first run of edge show with
    the verbose rendering reads the repository, and gives a status. Then the
    content repository cannot be read, in each of the five ways of the variants.
    Running edge show again with the verbose rendering gives the same status as
    the first run. So does running it with a subtree selection for REQ-A.

    :verifies: SEG-SREQ-366
    :test-id: SEG-TS-352
    """
    reads.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    assert reads.affirm(fixture, capsys)[0] == 0
    fixture.rewrite(prov.TO, "a later statement of REQ-A\n")
    control, _ = _show_text(fixture, capsys)
    control_below, _ = _show_text(fixture, capsys, "--below", prov.TO)
    assert control == 0
    assert control_below == 0
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=fixture.repository,
        config=fixture.config,
        name=fixture.name,
    )
    assert _show_text(fixture, capsys)[0] == control
    assert _show_text(fixture, capsys, "--below", prov.TO)[0] == control_below


@_VARIANTS
@red(365, _CRASH)
def test_the_machine_readable_report_gives_a_null_content_and_an_error_for_an_unreadable_end(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report of edge show has a null content and an error for an unreadable end.

    The edge from REQ-B to REQ-A is affirmed. Then the content repository cannot
    be read, in each of the five ways of the variants. Running edge show with
    the verbose rendering and the machine-readable report exits with status 0.
    For each endpoint, the entry of the before-content keeps the revision that the
    affirmation recorded, has a null content, and has an error key. The error is a
    text that holds the name of the repository as the configuration names it and a
    reason. For the path that does not exist, the reason says that it does not
    exist.

    :verifies: SEG-SREQ-365
    :test-id: SEG-TS-353
    """
    fixture, revision = _affirmed_then_broken(variant, monkeypatch, tmp_path, capsys)
    status, row = reads.show_before_content(nodes.place(fixture), capsys)
    assert status == 0
    assert row is not None
    for end in ("from", "to"):
        entry = row["beforeContent"][end]
        assert entry["revision"] == revision
        assert entry["content"] is None
        assert isinstance(entry.get("error"), str)
        assert support.holds_reason(entry["error"], fixture.name, variant), entry["error"]


@pytest.mark.parametrize("variant", ("objects", "stand-in"))
@pytest.mark.parametrize("which", ("to", "from"))
@red(365, _CRASH)
def test_the_machine_readable_report_keeps_the_content_of_the_readable_end_and_has_no_error(
    which: str,
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report of edge show has no error for the end that it could read.

    An implementation is in one repository and the requirement that it
    implements is in another, and the edge between them is affirmed. Then one
    of the two repositories cannot be read, in the two ways of the variants.
    Running edge show with the verbose rendering and the machine-readable
    report exits with status 0. The entry of the readable end holds its revision
    and its content as text, and it has no error, or an error that is null. The
    entry of the other end has a null content and an error that names its
    repository.

    :verifies: SEG-SREQ-365
    :test-id: SEG-TS-354
    """
    shapes, name, revisions = _two_affirmed(which, variant, monkeypatch, tmp_path, capsys)
    status, text = support.show_two(shapes, capsys, "--json")
    assert status == 0
    (row,) = json.loads(text)["edges"]
    broken, readable = ("to", "from") if which == "to" else ("from", "to")
    good = row["beforeContent"][readable]
    assert good["revision"] == revisions[readable]
    assert isinstance(good["content"], str)
    assert good["content"]
    assert good.get("error") is None
    bad = row["beforeContent"][broken]
    assert bad["revision"] == revisions[broken]
    assert bad["content"] is None
    assert name in bad["error"]


@_VARIANTS
@red(365, _CRASH)
def test_the_text_line_for_an_unreadable_end_has_the_form_of_the_page(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The text of edge show prints one line of a fixed form for an endpoint it cannot read.

    The edge from REQ-B to REQ-A is affirmed. Then the content repository cannot
    be read, in each of the five ways of the variants. Running edge show with the
    verbose rendering exits with status 0. For each endpoint, one line reads
    before-content, an at sign, the endpoint, the word revision with the
    revision of the affirmation in parentheses, a colon, the words not
    available, a colon, the repository, a colon and the reason. The repository
    is named as the configuration names it. The reason is not empty.

    :verifies: SEG-SREQ-365
    :test-id: SEG-TS-355
    """
    fixture, revision = _affirmed_then_broken(variant, monkeypatch, tmp_path, capsys)
    status, text = _show_text(fixture, capsys)
    assert status == 0
    found = {}
    for line in text.splitlines():
        matched = _LINE.match(line)
        if matched:
            found[matched["end"]] = matched
    assert sorted(found) == ["from", "to"]
    for matched in found.values():
        assert matched["revision"] == revision
        assert matched["rest"].startswith(f"{fixture.name}: ")
        assert matched["rest"][len(fixture.name) + 2 :].strip()


@_VARIANTS
def test_edge_show_without_the_verbose_rendering_reads_no_before_content(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the verbose rendering, edge show reads no before-content.

    The edge from REQ-B to REQ-A is affirmed, and a stand-in git logs each
    call. Running edge show without the verbose rendering exits with status 0,
    and the log holds no call of the subcommand show. The status and the text
    are kept. Then the content repository cannot be read, in each of the five
    ways of the variants. Running edge show without the verbose rendering again
    gives the same status and the same text, and no traceback.

    :verifies: SEG-SREQ-085
    :test-id: SEG-TS-356
    """
    reads.isolate(monkeypatch, tmp_path)
    fixture = base.build(tmp_path / "world")
    assert reads.affirm(fixture, capsys)[0] == 0
    arguments = ["edge", "show", *nodes.place(fixture).arguments()]
    stand_in = reads.install_stand_in(monkeypatch, tmp_path)
    healthy = reads.attempt(arguments, capsys)
    assert healthy[0] == 0
    assert "before-content" not in healthy[1]
    assert "show" not in stand_in.subcommands()
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=fixture.repository,
        config=fixture.config,
        name=fixture.name,
    )
    broken = reads.attempt(arguments, capsys)
    assert support.TRACEBACK not in broken[1]
    assert broken == healthy
