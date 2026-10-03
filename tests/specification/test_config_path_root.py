"""Verification suite for the path root and the need types of the configuration loader.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
specifications block or an implementations block can carry a path root: a
directory inside the repository that is put in front of each Doxygen path. A
reader block can also name need types, and the loader refuses a type that is empty
text and treats a null list of types as not given. Each test writes a
configuration file to a temporary directory and loads it with the configuration
loader, as the command line does before any verb runs.
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
    "requirements": {"export": "needs/requirements.json", "source": "reqs"},
    "specifications": {"export": "needs/test-cases.json", "doxygen": "xml/tests"},
    "implementations": {"export": "needs/implementations.json", "doxygen": "xml/impl"},
}
DOXYGEN_BLOCKS = ("specifications", "implementations")


def _load(tmp_path: Path, block: str, **keys: Any) -> config.Config:
    """Write a configuration whose one reader block holds ``keys``, and load it."""
    document = {"producer": {"repository": "suite", block: {**BLOCKS[block], **keys}}}
    path = tmp_path / block / "affirmatrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return config.load(path)


def _inputs(loaded: config.Config, block: str) -> Any:
    assert loaded.producer is not None
    return getattr(loaded.producer, block)


def _root(loaded: config.Config, block: str) -> Any:
    return getattr(_inputs(loaded, block), support.ATTR_PATH_ROOT)


@pytest.mark.parametrize("block", DOXYGEN_BLOCKS)
def test_the_loader_carries_the_path_root_of_a_doxygen_block(block: str, tmp_path: Path) -> None:
    """The loader carries the path root of a specifications block and of an implementations block.

    A file gives the key path-root as include/ in one block, the specifications
    block or the implementations block, one at a time. The loaded inputs of that
    block carry a path root that is the text include, with or without its
    trailing separator. The text is the one the file gives. It does not begin with
    the directory of the file, so it is not resolved against it. A file that does
    not give the key, one that gives it as the empty text and one that gives it
    as null load, and the loaded path root is then empty or none, the same in
    each of the three cases.

    :verifies: SEG-SREQ-348
    :test-id: SEG-TS-374
    """
    given = _load(tmp_path / "given", block, **{support.KEY_PATH_ROOT: "include/"})
    root = _root(given, block)
    assert isinstance(root, str)
    assert root.rstrip("/") == "include"
    assert str(tmp_path) not in root

    absent = _root(_load(tmp_path / "absent", block), block)
    empty = _root(_load(tmp_path / "empty", block, **{support.KEY_PATH_ROOT: ""}), block)
    null = _root(_load(tmp_path / "null", block, **{support.KEY_PATH_ROOT: None}), block)
    assert not absent and not empty and not null


@pytest.mark.parametrize("block", DOXYGEN_BLOCKS)
@pytest.mark.parametrize("value", [7, ["include"], {"dir": "include"}, True])
def test_a_path_root_that_is_not_text_is_refused_naming_the_block(
    block: str, value: Any, tmp_path: Path
) -> None:
    """A path root that is not text is refused, naming the block.

    A file gives the key path-root as a number, a list, an object or a boolean in
    one block, the specifications block or the implementations block, one at a
    time. Loading the file raises a configuration error that names the block. A
    control that gives the text include/ for the same block loads.

    :verifies: SEG-SREQ-348
    :test-id: SEG-TS-375
    """
    assert _load(tmp_path / "control", block, **{support.KEY_PATH_ROOT: "include/"}) is not None

    with pytest.raises(config.ConfigError, match=re.escape(f"producer.{block}")):
        _load(tmp_path / "bad", block, **{support.KEY_PATH_ROOT: value})


@pytest.mark.parametrize("block", sorted(BLOCKS))
@pytest.mark.parametrize("types", [[""], ["impl", ""]])
def test_a_need_type_that_is_empty_text_is_refused_naming_the_block(
    block: str, types: list[str], tmp_path: Path
) -> None:
    """A configuration whose need types hold an empty text is refused, naming the block.

    A file gives the types of one reader block as the list that holds only the
    empty text, or as the list impl and the empty text. This is tried for the
    requirements block, the specifications block and the implementations block,
    one at a time. Loading each file raises a configuration error that names the
    block. A control that gives the list impl for the same block loads, and the
    loaded inputs carry the type impl.

    :verifies: SEG-SREQ-341
    :test-id: SEG-TS-376
    """
    control = _load(tmp_path / "control", block, types=["impl"])
    assert _inputs(control, block).types == {"impl"}

    with pytest.raises(config.ConfigError, match=re.escape(f"producer.{block}")):
        _load(tmp_path / "bad", block, types=types)


@pytest.mark.parametrize("block", DOXYGEN_BLOCKS)
def test_null_need_types_of_a_doxygen_block_are_not_given(block: str, tmp_path: Path) -> None:
    """Null need types on a specifications block or an implementations block are not given.

    A file gives the key types of one block, the specifications block or the
    implementations block, with no value, so that it is null. Loading the file
    succeeds, and the loaded inputs carry no need types: the same as the inputs
    loaded from a file that does not give the key. A control that gives the list
    impl carries the type impl.

    :verifies: SEG-SREQ-369
    :test-id: SEG-TS-377
    """
    null = _inputs(_load(tmp_path / "null", block, types=None), block)
    absent = _inputs(_load(tmp_path / "absent", block), block)
    assert null.types is None
    assert absent.types is None
    assert _inputs(_load(tmp_path / "control", block, types=["impl"]), block).types == {"impl"}


def test_null_need_types_of_the_requirements_block_are_still_refused(tmp_path: Path) -> None:
    """Null need types on the requirements block are refused, naming the block.

    A file gives the key types of the requirements block with no value, so that it
    is null. Loading the file raises a configuration error that names the block,
    because the requirements block needs its types. A control that gives the list
    req loads.

    :verifies: SEG-SREQ-341
    :test-id: SEG-TS-378
    """
    assert _inputs(_load(tmp_path / "control", "requirements", types=["req"]), "requirements")

    with pytest.raises(config.ConfigError, match=re.escape("producer.requirements")):
        _load(tmp_path / "null", "requirements", types=None)
