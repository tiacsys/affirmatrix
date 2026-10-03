"""Verification suite for the need types that a configuration names.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
reader block of the configuration can name the need types of its export. A user
who wants every need leaves the key out. Each test writes a configuration file
to a temporary directory and loads it with the configuration loader, as the
command line does before any verb runs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from affirmatrix import config

from .need_types_support import red

#: The three reader blocks that name need types, with the keys each block needs.
BLOCKS: dict[str, dict[str, str]] = {
    "requirements": {"export": "needs/requirements.json", "source": "reqs"},
    "specifications": {"export": "needs/test-cases.json", "doxygen": "xml/tests"},
    "implementations": {"export": "needs/implementations.json", "doxygen": "xml/impl"},
}


def _load(tmp_path: Path, block: str, types: Any) -> config.Config:
    """Write a configuration whose one reader block names ``types``, and load it."""
    document = {"producer": {"repository": "suite", block: {**BLOCKS[block], "types": types}}}
    path = tmp_path / block / "affirmatrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return config.load(path)


def _refused(tmp_path: Path, block: str, types: Any) -> None:
    """Loading is refused with an error that names the block."""
    with pytest.raises(config.ConfigError, match=re.escape(f"producer.{block}")):
        _load(tmp_path / re.sub(r"\W", "_", repr(types)), block, types)


@red(341, "an empty list of need types loads")
@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_an_empty_list_of_need_types_is_refused_naming_the_block(
    block: str, tmp_path: Path
) -> None:
    """A configuration that names an empty list of need types is refused, naming the block.

    A file gives the types of one reader block as an empty list. This is tried for
    the requirements block, the specifications block and the implementations
    block, one at a time. Loading the file raises a configuration error that names
    the block. A control that gives the list [kind] for the same block loads, and
    the loaded inputs carry the type kind.

    :verifies: SEG-SREQ-341
    :test-id: SEG-TS-325
    """
    loaded = _load(tmp_path / "control", block, ["kind"])
    assert loaded.producer is not None
    assert getattr(loaded.producer, block).types == {"kind"}

    _refused(tmp_path, block, [])


@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_need_types_that_are_not_a_list_of_text_are_refused_naming_the_block(
    block: str, tmp_path: Path
) -> None:
    """A configuration whose need types are not a list of text is refused, naming the block.

    A file gives the types of one reader block as a list that holds a number, [1],
    or as a text that is no list, test_case. This is tried for the requirements
    block, the specifications block and the implementations block, one at a time.
    Loading each file raises a configuration error that names the block. A
    control that gives the list [kind] for the same block loads.

    :verifies: SEG-SREQ-341
    :test-id: SEG-TS-326
    """
    assert _load(tmp_path / "control", block, ["kind"]).producer is not None

    _refused(tmp_path, block, [1])
    _refused(tmp_path, block, "test_case")
