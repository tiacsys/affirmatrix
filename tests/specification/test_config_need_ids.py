"""Verification suite for the list of need identifiers of the implementations block.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
implementations block of the configuration can list the identifiers of the
implementation needs that the readers use. A user who wants every need leaves
the key out. Each test writes a configuration file to a temporary directory and
loads it with the configuration loader, as the command line does before any
verb runs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from affirmatrix import config

from . import capture_support as support

#: The three reader blocks, with the keys each block needs.
BLOCKS: dict[str, dict[str, str]] = {
    "requirements": {"export": "needs/requirements.json", "types": ["req"], "source": "reqs"},
    "specifications": {"export": "needs/test-cases.json", "doxygen": "xml/tests"},
    "implementations": {"export": "needs/implementations.json", "doxygen": "xml/impl"},
}

_STRICT = pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-357: the loader drops the list of need identifiers"
)
_STRICT_SHAPE = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-362: the loader does not look at the list of need identifiers",
)
_STRICT_NULL = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-357 and 370: the loaded inputs have no place for the list, null or not",
)
_STRICT_UNKNOWN = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-376: the loader drops a key it does not know, so the file loads",
)


def _load(tmp_path: Path, block: str = "implementations", **keys: Any) -> config.Config:
    """Write a configuration whose one reader block holds ``keys``, and load it."""
    document = {"producer": {"repository": "lib", block: {**BLOCKS[block], **keys}}}
    path = tmp_path / block / "affirmatrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return config.load(path)


def _need_ids(loaded: config.Config) -> Any:
    assert loaded.producer is not None
    assert loaded.producer.implementations is not None
    return getattr(loaded.producer.implementations, support.ATTR_NEED_IDS)


@_STRICT
def test_the_loader_carries_the_list_of_need_identifiers(tmp_path: Path) -> None:
    """The loader carries the list of need identifiers of the implementations block.

    A file gives the key need-ids in the implementations block as the list
    IMPL-ONE, IMPL-TWO. The loaded inputs of the implementations block carry the
    identifiers IMPL-ONE and IMPL-TWO and no others. A file that gives the same
    list in another order, and one that gives an identifier twice, carry the same
    identifiers. A file that does not give the key loads, and its loaded inputs
    carry no list at all, which is not the same as an empty list.

    :verifies: SEG-SREQ-357
    :test-id: SEG-TS-415
    """
    absent = _need_ids(_load(tmp_path / "absent"))
    assert absent is None

    given = _load(tmp_path / "given", **{support.KEY_NEED_IDS: ["IMPL-ONE", "IMPL-TWO"]})
    assert set(_need_ids(given)) == {"IMPL-ONE", "IMPL-TWO"}

    for name, ids in (
        ("reversed", ["IMPL-TWO", "IMPL-ONE"]),
        ("twice", ["IMPL-ONE", "IMPL-TWO", "IMPL-ONE"]),
    ):
        other = _load(tmp_path / name, **{support.KEY_NEED_IDS: ids})
        assert set(_need_ids(other)) == {"IMPL-ONE", "IMPL-TWO"}, name


@_STRICT_SHAPE
@pytest.mark.parametrize(
    "value",
    [[], [1], [""], ["IMPL-ONE", ""], ["IMPL-ONE", 2], "IMPL-ONE", {"IMPL-ONE": 1}, 7, True],
    ids=[
        "empty",
        "number",
        "empty-text",
        "text-and-empty",
        "text-and-number",
        "bare",
        "map",
        "int",
        "bool",
    ],
)
def test_need_identifiers_that_are_empty_or_not_text_are_refused_naming_the_block(
    value: Any, tmp_path: Path
) -> None:
    """A list of need identifiers that is empty or not a list of non-empty text is refused.

    A file gives the key need-ids in the implementations block as the empty
    list, as a list that holds a number, as a list that holds the empty text,
    as a list of one good identifier and the empty text, as a list of one good
    identifier and a number, as one text that is no list, as an object, as a
    number or as a boolean, one at a time. Loading each file raises a
    configuration error that names the block producer.implementations. A control
    that gives the list IMPL-ONE loads.

    :verifies: SEG-SREQ-362
    :test-id: SEG-TS-416
    """
    assert _load(tmp_path / "control", **{support.KEY_NEED_IDS: ["IMPL-ONE"]}) is not None

    with pytest.raises(config.ConfigError, match=re.escape("producer.implementations")):
        _load(tmp_path / "bad", **{support.KEY_NEED_IDS: value})


@_STRICT_NULL
def test_a_null_list_of_need_identifiers_is_a_list_that_is_not_given(tmp_path: Path) -> None:
    """A null list of need identifiers is the same as a list that is not given.

    A file gives the key need-ids in the implementations block with no value, so
    that the value is null. The file loads, and its loaded inputs carry what the
    inputs of a file without the key carry. A control that gives the list
    IMPL-ONE carries that identifier. The null key does not narrow the
    needs: it is not read as an empty list, which would be refused.

    :verifies: SEG-SREQ-370
    :test-id: SEG-TS-417
    """
    absent = _need_ids(_load(tmp_path / "absent"))
    null = _need_ids(_load(tmp_path / "null", **{support.KEY_NEED_IDS: None}))
    assert null == absent
    assert null is None

    control = _load(tmp_path / "control", **{support.KEY_NEED_IDS: ["IMPL-ONE"]})
    assert _need_ids(control) is not None


@_STRICT_UNKNOWN
@pytest.mark.parametrize("block", ["requirements", "specifications"])
def test_the_list_of_need_identifiers_is_refused_outside_the_implementations_block(
    block: str, tmp_path: Path
) -> None:
    """The key need-ids is refused in the requirements block and in the specifications block.

    A file gives the key need-ids with the list IMPL-ONE in the requirements
    block, or in the specifications block, one at a time. The key is known only
    in the implementations block, so loading each file raises a configuration
    error that names the block that holds the key and names the key need-ids. A
    control that gives the same list in the implementations block loads.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-418
    """
    assert _load(tmp_path / "control", **{support.KEY_NEED_IDS: ["IMPL-ONE"]}) is not None

    with pytest.raises(config.ConfigError) as refused:
        _load(tmp_path / "bad", block, **{support.KEY_NEED_IDS: ["IMPL-ONE"]})
    assert f"producer.{block}" in str(refused.value)
    assert support.KEY_NEED_IDS in str(refused.value)
