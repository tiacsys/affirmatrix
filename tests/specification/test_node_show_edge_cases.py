"""Verification suite for four edge cases of ``node show`` (SEG-SREQ-328 to 331).

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
cases are: the encoding of content in the JSON report, an identifier that the
current stream holds twice, a hash that only the case records, and a configured
repository that cannot be read.

Each test builds its repositories in ``tmp_path`` and runs ``affirmatrix.cli.main``
as an operator would. Each test starts with a control that is accepted. The
command runs for the text report and for the JSON report, and both must give the
same exit status. The names of the keys and the words of the report are in
``node_show_support``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case

from . import extraction_support as base
from . import node_show_support as support

pytestmark = support.requires_git


def _reason(claim: str) -> str:
    return f"{claim}: there is no node show verb, so the command cannot be run"


def _synced_with_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], data: bytes
) -> base.Fixture:
    """A synced case whose requirement REQ-B has ``data`` as the bytes of its file."""
    fixture = base.build(tmp_path)
    (fixture.repository / fixture.file("REQ-B")).write_bytes(data)
    base.commit_all(fixture.repository, "give REQ-B other bytes")
    support.sync(fixture, capsys)
    return fixture


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-328"))
def test_node_show_gives_valid_utf8_content_as_text_in_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show gives content that is valid UTF-8 as text in the JSON report.

    The file of a requirement holds text with characters outside ASCII, and the
    case is synced. node show exits with status 0. The JSON content of the hash
    is the text of the file. The entry does not name the base64 encoding. The
    SHA-256 of the bytes that the content stands for is the current digest.

    :verifies: SEG-SREQ-328
    :test-id: SEG-TS-255
    """
    text = "größe ✓ of REQ-B\nsecond line\n"
    fixture = _synced_with_file(tmp_path, capsys, text.encode("utf-8"))
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    entry = shown.entry("contentHash")
    assert entry[support.KEY_CONTENT] == text
    assert entry.get(support.KEY_ENCODING) != support.ENCODING_BASE64
    assert support.hex_of(support.content_bytes(entry)) == entry[support.KEY_CURRENT]


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-328"))
def test_node_show_gives_other_content_as_base64_in_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show gives content that is not valid UTF-8 as base64, with the encoding named.

    The file of a requirement holds bytes that are not valid UTF-8, and the case
    is synced. node show exits with status 0. The JSON entry names the base64
    encoding. Decoding the JSON content from base64 gives exactly the bytes of the
    file. The SHA-256 of those bytes is the current digest.

    :verifies: SEG-SREQ-328
    :test-id: SEG-TS-256
    """
    data = b"caf\xe9 \xff\xfe\nsecond line\n"
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    fixture = _synced_with_file(tmp_path, capsys, data)
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    assert shown.status == 0
    entry = shown.entry("contentHash")
    assert entry[support.KEY_ENCODING] == support.ENCODING_BASE64
    assert support.content_bytes(entry) == data
    assert support.hex_of(data) == entry[support.KEY_CURRENT]


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-329"))
def test_node_show_exits_with_status_2_for_an_identifier_the_current_stream_holds_twice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show exits with status 2 and names the identifier when the stream holds it twice.

    The case holds a requirement record. A control run, over a current stream that
    holds the record once, exits with status 0. Then the current stream holds two
    records with that identifier and different content. node show exits with status
    2. In the text and in the JSON, the message names the identifier, and the
    report has no hash. No file of the case changes.

    :verifies: SEG-SREQ-329
    :test-id: SEG-TS-257
    """
    fixture = base.build(tmp_path)
    first = support.node("Requirement", "REQ-D", contentHash="one statement")
    second = support.node("Requirement", "REQ-D", contentHash="another statement")
    case.AffirmationStore(root=fixture.case).write_nodes([first])
    where = support.place(fixture)
    base.supply(monkeypatch, support.listed(first))
    assert support.show(where, "REQ-D", capsys).status == 0
    before = base.snapshot(fixture.case)
    base.supply(monkeypatch, support.listed(first, second))
    shown = support.show(where, "REQ-D", capsys)
    assert shown.status == 2
    assert "REQ-D" in shown.text
    assert "REQ-D" in shown.document[support.KEY_ERROR]
    assert support.KEY_HASHES not in shown.document
    assert base.snapshot(fixture.case) == before


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-330"))
def test_node_show_reports_no_current_content_for_a_hash_only_the_case_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show reports no current content and no checkout for a hash only the case records.

    The case holds a test specification record with the hashes specHash and
    implHash. The current record of the node has specHash alone. For implHash, the
    text block says that there is no current content, and it has no checkout line
    and no worktree line. The JSON content and the JSON checkout of implHash are
    null. The block of specHash still has its checkout line and its content.

    :verifies: SEG-SREQ-330
    :test-id: SEG-TS-258
    """
    fixture = base.build(tmp_path)
    recorded = support.node("TestSpecification", "TS-1", specHash="spec", implHash="impl")
    current = support.node("TestSpecification", "TS-1", specHash="spec")
    case.AffirmationStore(root=fixture.case).write_nodes([recorded])
    base.supply(monkeypatch, support.listed(current))
    shown = support.show(support.place(fixture), "TS-1", capsys)
    assert shown.entry("implHash")[support.KEY_STATUS] == support.RECORDED_ONLY
    assert support.NO_CURRENT_CONTENT in shown.block_text("implHash").lower()
    assert shown.labelled("implHash", support.LABEL_CHECKOUT) == []
    assert shown.labelled("implHash", support.LABEL_WORKTREE) == []
    assert shown.entry("implHash")[support.KEY_CONTENT] is None
    assert shown.entry("implHash")[support.KEY_CHECKOUT] is None
    assert len(shown.labelled("specHash", support.LABEL_CHECKOUT)) == 1
    assert support.NO_CURRENT_CONTENT not in shown.block_text("specHash").lower()


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-331"))
def test_node_show_reports_a_repository_that_cannot_be_read_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """node show reports a repository that cannot be read, with the reason, and keeps the status.

    The case is synced. With the repository readable, node show exits with status
    0 for a matching hash, and with status 1 after the file of the requirement
    changes. Then the configuration maps the repository name to a directory that
    is not a git repository. For the same two comparisons, node show exits with the
    same two statuses. The checkout line says that the
    repository cannot be read, and gives a reason after it. The JSON checkout has
    no revision, and has a reason that is text and not empty. Git does not look
    for a repository above the test's directory, so a checkout that holds the
    temporary directory cannot make the plain directory readable.

    :verifies: SEG-SREQ-331
    :test-id: SEG-TS-259
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    plain = tmp_path / "plain"
    plain.mkdir()
    where = support.place(fixture)
    assert support.show(where, "REQ-B", capsys).status == 0
    base.configure(fixture, mapped=True, directory=plain)
    shown = support.show(where, "REQ-B", capsys)
    assert shown.status == 0
    (line,) = shown.labelled("contentHash", support.LABEL_CHECKOUT)
    assert support.CANNOT_READ in line.lower()
    assert line.lower().split(support.CANNOT_READ, 1)[1].strip(" :;,.-")
    checkout = shown.entry("contentHash")[support.KEY_CHECKOUT]
    assert checkout[support.KEY_CHECKOUT_REVISION] is None
    assert checkout[support.KEY_CHECKOUT_ERROR].strip()
    base.configure(fixture, mapped=True)
    fixture.rewrite("REQ-B", "a changed statement\n")
    assert support.show(where, "REQ-B", capsys).status == 1
    base.configure(fixture, mapped=True, directory=plain)
    shown = support.show(where, "REQ-B", capsys)
    assert shown.status == 1
    assert support.CANNOT_READ in shown.block_text("contentHash").lower()
