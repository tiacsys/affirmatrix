"""Verification suite for the keys that the configuration loader does not know.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A key
that is mistyped, or that belongs to another block, must stop the run. A
dropped key would give a full run that the user did not ask for. Each test
writes a configuration file to a temporary directory and loads it with the
configuration loader, as the command line does before any verb runs. The test
for the command line runs the verb ``case check``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from affirmatrix import config
from affirmatrix.cli import main

from . import capture_support as support

#: The reader blocks, with the keys each block needs to load.
BLOCKS: dict[str, dict[str, Any]] = {
    "requirements": {"export": "needs/requirements.json", "types": ["req"], "source": "reqs"},
    "specifications": {"export": "needs/test-cases.json", "doxygen": "xml/tests"},
    "implementations": {"export": "needs/implementations.json", "doxygen": "xml/impl"},
}

#: Every key that each block knows, with a value that loads.
KNOWN: dict[str, dict[str, Any]] = {
    "requirements": {
        **BLOCKS["requirements"],
        "parent-field": "trace",
        "repository": "docs",
    },
    "specifications": {
        **BLOCKS["specifications"],
        "types": ["test_case"],
        "doxygen-prefix": "vendor/",
        "path-root": "tests/",
        "repository": "suite",
    },
    "implementations": {
        **BLOCKS["implementations"],
        "types": ["impl"],
        "doxygen-prefix": "vendor/",
        "path-root": "include/",
        "need-ids": ["IMPL-ONE"],
        "repository": "lib",
    },
}


def _write(tmp_path: Path, document: dict[str, Any], name: str = "affirmatrix.yaml") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _document(**producer: Any) -> dict[str, Any]:
    return {"producer": {"repository": "lib", **producer}}


def _refused_for(path: Path, key: str, block: str | None = None) -> None:
    """Loading ``path`` raises a configuration error that names the key, and the block if given.

    The key is found as a whole word, so ``need-id`` is not found in a message
    that names ``need-ids``, and ``implementation`` is not found in
    ``producer.implementations``. How the message quotes the key is not read.
    """
    with pytest.raises(config.ConfigError) as refused:
        config.load(path)
    message = str(refused.value)
    assert re.search(rf"(?<![\w.-]){re.escape(key)}(?![\w-])", message), (key, message)
    if block is not None:
        assert block in message, (block, message)


@pytest.mark.parametrize("key", ["cases", "implementations", "Case", "repository"])
def test_a_key_at_the_top_of_the_file_that_is_not_known_is_refused(
    key: str, tmp_path: Path
) -> None:
    """A key at the top of the file that the loader does not know is refused, naming the key.

    A file holds the known top-level keys case and implementation, and one more
    key at the top: cases, implementations, Case or repository, one at a time.
    Of these, repository is known only inside the producer block, and Case
    differs from case by its capital letter. Loading each file raises a
    configuration error that names the key. A control without the extra key
    loads.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-419
    """
    document = {"case": "./case", "implementation": "lib"}
    assert config.load(_write(tmp_path / "control", document)) is not None

    bad = _write(tmp_path / "bad", {**document, key: "x"})
    _refused_for(bad, key)


@pytest.mark.parametrize("key", ["roots", "outputs", "implementation", "Repository", "types"])
def test_a_key_of_the_producer_block_that_is_not_known_is_refused(key: str, tmp_path: Path) -> None:
    """A key of the producer block that the loader does not know is refused.

    A file holds a producer block with the known keys root and repository, and one
    more key: roots, outputs, implementation, Repository or types, one at a time.
    Loading each file raises a configuration error that names the block producer
    and the key. A control without the extra key loads.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-420
    """
    assert config.load(_write(tmp_path / "control", _document(root="./store"))) is not None

    bad = _write(tmp_path / "bad", _document(root="./store", **{key: "x"}))
    _refused_for(bad, key, "producer")


#: A mistyped key of each block, and a key that another block knows.
MISTYPED = {
    "requirements": ["source_map", "parent_field", "doxygen-prefix", "path-root", "need-ids"],
    "specifications": ["doxygen_prefix", "path_root", "need-ids", "source", "parent-field"],
    "implementations": ["doxygen_prefix", "path_root", "need_ids", "need-id", "source-map"],
}


@pytest.mark.parametrize(
    ("block", "key"),
    [(block, key) for block, keys in MISTYPED.items() for key in keys],
)
def test_a_key_of_a_reader_block_that_is_not_known_is_refused(
    block: str, key: str, tmp_path: Path
) -> None:
    """A key of a reader block that the loader does not know is refused, naming block and key.

    A file holds one reader block, the requirements block, the specifications
    block or the implementations block, with the keys that it needs to load and one
    more key. The extra key is either a mistyped name, such as doxygen_prefix or
    need_ids, or the name of a key that only another block knows, such as need-ids
    in the specifications block or doxygen-prefix in the requirements block.
    Loading each file raises a configuration error that names the block, as
    producer.<block>, and the key. A control without the extra key loads.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-421
    """
    assert config.load(_write(tmp_path / "control", _document(**{block: BLOCKS[block]})))

    bad = _write(tmp_path / "bad", _document(**{block: {**BLOCKS[block], key: "x"}}))
    _refused_for(bad, key, f"producer.{block}")


def test_a_file_that_holds_only_known_keys_loads(tmp_path: Path) -> None:
    """A file that holds only known keys loads, whatever blocks it holds.

    A file holds every key that the loader knows: at the top, case, implementation,
    repositories, roles and producer; in producer, root, repository, and the
    three reader blocks; in each reader block, every key of that block, including
    path-root, need-ids (in the implementations block only) and either source
    or source-map in the requirements block. The file loads. A second file
    that differs in the requirements block, which holds source-map and no
    source, loads too. Neither load raises a configuration error.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-422
    """
    top = {
        "case": "./case",
        "implementation": "lib",
        "repositories": {"docs": "./docs", "suite": "./suite", "lib": "./lib"},
        "roles": ["reviewer"],
    }
    producer = {"root": "./store", "repository": "lib"}

    with_source = {**top, "producer": {**producer, **KNOWN}}
    assert config.load(_write(tmp_path / "source", with_source)).producer is not None

    requirements = {k: v for k, v in KNOWN["requirements"].items() if k != "source"}
    requirements["source-map"] = {"reqs/alpha": "./docs/alpha.sdoc"}
    with_map = {**top, "producer": {**producer, **KNOWN, "requirements": requirements}}
    assert config.load(_write(tmp_path / "map", with_map)).producer is not None


@pytest.mark.parametrize("run", [[], [{"bundle": "a", "digest": "x"}], "nope"])
def test_a_producer_that_names_a_run_keeps_its_own_refusal(run: Any, tmp_path: Path) -> None:
    """A producer block that holds the key outcomes is refused for that key, whatever it holds.

    A file holds a producer block with the key outcomes, whose value is an empty
    list, a list of one run or a text, one at a time. Loading each file raises a
    configuration error that names the key outcomes and says that run bundles
    are named on the command line with --bundle. The refusal is the one the loader
    gave before it refused unknown keys, and it does not say that the key is
    unknown.

    :verifies: SEG-SREQ-234
    :test-id: SEG-TS-423
    """
    path = _write(tmp_path, _document(outcomes=run))

    with pytest.raises(config.ConfigError) as refused:
        config.load(path)

    message = str(refused.value)
    assert "outcomes" in message
    assert "--bundle" in message
    assert not re.search(r"\bunknown\b|not known", message)


def test_a_mistyped_key_stops_the_command_line_with_exit_status_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mistyped key stops a verb of the command line with exit status 2, naming the key.

    A configuration holds an implementations block over the fixture, with the
    types {impl}, the prefix of its Doxygen output and the list of need
    identifiers I-LIB-MAX. Running the verb case sync with that file, with the
    list spelled need-ids, exits with status 0. The same file with the key
    spelled need_ids exits with status 2 and prints a message that names the key
    need_ids. The case holds no record after the second run.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-424
    """

    def sync(key: str) -> tuple[int, str, Path]:
        directory = tmp_path / key
        directory.mkdir()
        export = support.export_of(
            directory,
            [
                n
                for n in support.needs_of(
                    support.document_of(support.IMPLEMENTATIONS_EXPORT)
                ).values()
                if n["type"] == "impl"
            ],
            "impls",
        )
        block = support.implementations_block(
            "prefixed-impl",
            export=str(export),
            **{support.KEY_TYPES: ["impl"], support.KEY_PREFIX: "lib-src/", key: ["I-LIB-MAX"]},
        )
        path = support.configuration(directory, implementations=block, default_repository="lib")
        case = directory / "case"
        assert main(["case", "init", "--case", str(case)]) == 0
        capsys.readouterr()
        status = main(["case", "sync", "--case", str(case), "--config", str(path)])
        captured = capsys.readouterr()
        return status, captured.out + captured.err, case

    status, text, _ = sync(support.KEY_NEED_IDS)
    assert status == 0, text

    status, text, case = sync("need_ids")
    assert status == 2, text
    assert "need_ids" in text
    assert not list((case / "nodes").iterdir())
