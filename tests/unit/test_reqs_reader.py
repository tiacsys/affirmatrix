"""Developer tests for the requirements reader's canonical form and refusals.

The acceptance tests read the frozen requirement export; these build small
exports in a temporary directory, so each property is pinned on a need small
enough to read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from affirmatrix.records import LinkState
from affirmatrix.sources.reqs import ReaderError, RequirementsReader, canonical_form


def _need(need_id: str, **fields: Any) -> dict[str, Any]:
    need: dict[str, Any] = {
        "id": need_id,
        "type": "requirement",
        "title": "A title",
        "content": "A statement.",
        "docname": "doc",
        "doctype": ".rst",
        "refines": [],
        "status": "approved",
        "tags": [],
        "refines_back": [],
    }
    need.update(fields)
    return need


def _export(tmp_path: Path, *needs: dict[str, Any], versions: int = 1) -> Path:
    body = {"needs": {need["id"]: need for need in needs}}
    document = {"versions": {f"v{index}": dict(body) for index in range(versions)}}
    path = tmp_path / "needs.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _reader(export: Path) -> RequirementsReader:
    return RequirementsReader(
        export=export,
        types=frozenset({"requirement"}),
        repository="sample",
        source_directory=Path("doc"),
    )


def test_the_canonical_form_of_a_literal_need_is_exactly_these_bytes() -> None:
    """The canonical form is compact sorted-key JSON of content, refines, title."""
    need = _need("REQ-1", refines=["REQ-0"], content="Line one\nline two", title="T")
    assert canonical_form(need) == (
        b'{"content":"Line one\\nline two","refines":["REQ-0"],"title":"T"}'
    )


def test_the_digest_is_the_sha256_of_the_canonical_form(tmp_path: Path) -> None:
    """The anchored digest is the SHA-256 of the canonical form's bytes."""
    need = _need("REQ-1")
    (node,) = _reader(_export(tmp_path, need)).nodes()
    expected = hashlib.sha256(canonical_form(need)).digest()
    assert node.content_anchors["contentHash"].digest == expected


def test_the_canonical_form_sorts_refines_and_orders_keys() -> None:
    """Parents are sorted and the members appear in key order."""
    form = canonical_form(_need("REQ-1", refines=["B", "A"])).decode("utf-8")
    assert '"refines":["A","B"]' in form
    assert form.index('"content"') < form.index('"refines"') < form.index('"title"')


def test_absent_null_and_empty_refines_hash_alike() -> None:
    """A need with no refines, null refines or an empty list has one form."""
    empty = _need("REQ-1", refines=[])
    null = _need("REQ-1", refines=None)
    absent = _need("REQ-1")
    del absent["refines"]
    assert canonical_form(empty) == canonical_form(null) == canonical_form(absent)
    assert b'"refines":[]' in canonical_form(absent)


def test_non_ascii_content_is_hashed_as_utf8_not_as_escapes() -> None:
    """A non-ASCII character enters the form as its UTF-8 bytes."""
    form = canonical_form(_need("REQ-1", content="café — done"))
    assert "café — done".encode() in form
    assert b"\\u" not in form


def test_fields_outside_the_authored_three_do_not_reach_the_form() -> None:
    """Identifier, status, tags and derived fields leave the form unchanged."""
    plain = canonical_form(_need("REQ-1"))
    other = canonical_form(
        _need("REQ-2", status="draft", tags=["x"], refines_back=["REQ-9"], lineno=7)
    )
    assert plain == other


def test_an_export_with_two_versions_is_refused(tmp_path: Path) -> None:
    """More than one version is an error: the reader serves one build."""
    with pytest.raises(ReaderError, match="exactly one"):
        _reader(_export(tmp_path, _need("REQ-1"), versions=2))


def test_an_export_without_needs_is_refused(tmp_path: Path) -> None:
    """A version without a needs object is an error naming the key."""
    path = tmp_path / "needs.json"
    path.write_text(json.dumps({"versions": {"v": {}}}), encoding="utf-8")
    with pytest.raises(ReaderError, match="needs"):
        _reader(path)


def test_a_need_without_a_title_is_refused_naming_the_need(tmp_path: Path) -> None:
    """A configured need lacking its title is refused, and the message names it."""
    need = _need("REQ-7")
    del need["title"]
    with pytest.raises(ReaderError, match="REQ-7"):
        _reader(_export(tmp_path, need))


def test_a_need_without_content_is_refused_naming_the_need(tmp_path: Path) -> None:
    """A configured need lacking its content is refused, and the message names it."""
    need = _need("REQ-8")
    del need["content"]
    with pytest.raises(ReaderError, match="REQ-8"):
        _reader(_export(tmp_path, need))


def test_a_refines_target_missing_from_the_export_is_still_an_edge(tmp_path: Path) -> None:
    """A dangling parent is emitted as a pending edge, not refused."""
    (edge,) = _reader(_export(tmp_path, _need("REQ-1", refines=["REQ-404"]))).edges()
    assert (edge.from_id, edge.to_id, edge.kind) == ("REQ-1", "REQ-404", "Refines")
    assert edge.state == LinkState.PENDING


def test_an_unreadable_or_non_json_export_is_refused_not_raised_raw(tmp_path: Path) -> None:
    """Neither a missing file nor a non-JSON file escapes as a raw error."""
    with pytest.raises(ReaderError):
        _reader(tmp_path / "absent.json")
    text = tmp_path / "text.json"
    text.write_text("not json", encoding="utf-8")
    with pytest.raises(ReaderError):
        _reader(text)
