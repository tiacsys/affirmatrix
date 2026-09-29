"""The shared outcome vocabulary (SEG-SREQ-095…098)."""

from __future__ import annotations

import io
import json

import pytest

from affirmatrix.cli import _outcome


def test_exit_status_is_one_of_the_three_members() -> None:
    """SEG-SREQ-096."""
    assert _outcome.exit_for(_outcome.POSITIVE) == 0
    assert _outcome.exit_for(_outcome.NEGATIVE) == 1
    assert _outcome.exit_for(_outcome.INDETERMINATE) == 2


def test_a_fourth_value_is_refused() -> None:
    with pytest.raises(ValueError, match="exit status"):
        _outcome.exit_for(3)


def test_render_json_is_sorted_and_stable() -> None:
    """SEG-SREQ-098."""
    stream = io.StringIO()
    _outcome.render_json({"b": 1, "a": 2}, stream)
    parsed = json.loads(stream.getvalue())
    assert parsed == {"a": 2, "b": 1}
    assert stream.getvalue().index('"a"') < stream.getvalue().index('"b"')


def test_render_refusal_prints_the_librarys_message_verbatim() -> None:
    """SEG-SREQ-097."""
    stream = io.StringIO()
    _outcome.render_refusal("the library's own message", as_json=False, stream=stream)
    assert stream.getvalue() == "the library's own message\n"


def test_render_refusal_as_json_structures_the_same_message() -> None:
    stream = io.StringIO()
    _outcome.render_refusal("refused", as_json=True, stream=stream)
    assert json.loads(stream.getvalue()) == {"error": "refused"}


def test_hash_display_truncates_unless_verbose() -> None:
    digest = "abcd" + "0" * 56 + "ef12"
    assert _outcome.hash_display(digest, verbose=False) == "abcd…ef12"
    assert _outcome.hash_display(digest, verbose=True) == digest


def test_counts_display_joins_name_and_count_pairs() -> None:
    assert _outcome.counts_display({"nodes": 3, "review events": 0}) == "nodes 3, review events 0"


def test_counts_display_of_no_counts_says_none() -> None:
    assert _outcome.counts_display({}) == "(none)"


def test_anchor_display_of_no_anchor_is_none() -> None:
    assert _outcome.anchor_display(None, verbose=False) is None


def test_anchor_display_truncates_unless_verbose() -> None:
    from affirmatrix.records import ContentAnchor

    anchor = ContentAnchor(bytes.fromhex("abcd" + "00" * 28 + "ef12"), "r", "p", "file")
    assert _outcome.anchor_display(anchor, verbose=False) == "abcd…ef12"
    assert _outcome.anchor_display(anchor, verbose=True) == anchor.digest.hex()
