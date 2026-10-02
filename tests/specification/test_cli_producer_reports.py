"""Verification suite for what the command line reports about a configured producer.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test runs ``affirmatrix.cli.main`` in the working directory ``tmp_path`` with
a configuration file written there, and reads the exit status and the output.
A producer that the library cannot read is made by naming an export that does
not exist. The expected reason is the message the library itself gives, taken
in the test by building the same producer.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.sources import SourceError

from . import capture_support as support

WOULD_BE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "would_be_store"


def _case(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    return root


def _tree(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _strings(value: Any) -> list[str]:
    """Every string in a parsed JSON value, keys and values."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in (*_strings(key), *_strings(item))]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _unreadable(tmp_path: Path) -> Path:
    """A configuration whose requirement export is absent."""
    block = support.requirements_block(export=str(tmp_path / "absent" / "needs.json"))
    return support.configuration(tmp_path, requirements=block, default_repository="docs")


def _store(tmp_path: Path, name: str = "store") -> Path:
    target = tmp_path / name
    shutil.copytree(WOULD_BE_STORE, target)
    return target


def test_case_sync_over_a_stream_that_cannot_be_built_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """case sync cannot judge a stream that cannot be built, or a graph that cannot be built.

    The case is initialized. A configured producer names a requirement export that
    does not exist. Running case sync with it exits with status 2 and leaves every
    file of the case as it was. Running case sync with a current stream that holds
    a refines cycle does the same.

    :verifies: SEG-SREQ-136
    :test-id: SEG-TS-183
    """
    monkeypatch.chdir(tmp_path)
    root = _case(tmp_path)
    before = _tree(root)
    cfg = _unreadable(tmp_path)
    assert main(["case", "sync", "--case", str(root), "--config", str(cfg)]) == 2
    assert _tree(root) == before
    store = _store(tmp_path)
    refines = store / "edges" / "refines.toml"
    refines.write_text(
        refines.read_text(encoding="utf-8").replace(
            "Refines = [\n", 'Refines = [\n    ["SEG-SYS-001", "SEG-SREQ-001"],\n', 1
        ),
        encoding="utf-8",
    )
    assert main(["case", "sync", "--case", str(root), "--current", str(store)]) == 2
    assert _tree(root) == before


def test_case_check_says_why_the_producer_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """case check says why a producer cannot be read, in both renderings.

    The configured producer names a requirement export that does not exist. The
    reason is the message the library gives when it builds that producer. The
    output of case check holds that message in full. The output of case check with
    the machine-readable rendering is a JSON object with that message in one of
    its string values.

    :verifies: SEG-SREQ-290
    :test-id: SEG-TS-180
    """
    monkeypatch.chdir(tmp_path)
    root = _case(tmp_path)
    cfg = _unreadable(tmp_path)
    with pytest.raises(SourceError) as library:
        support.producer_of(cfg)
    reason = str(library.value)
    capsys.readouterr()
    main(["case", "check", "--case", str(root), "--config", str(cfg)])
    assert reason in capsys.readouterr().out
    main(["case", "check", "--case", str(root), "--config", str(cfg), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert any(reason in text for text in _strings(report))


def test_graph_check_says_which_stream_it_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """graph check names what it checked by its location, in both renderings.

    A case is synced from a current stream. So the case and the stream hold the
    same graph, and every count in the two outputs is the same. The output of
    graph check over the case holds the root of the case. The output of graph check
    with the current stream holds the location given to --current. In the
    machine-readable rendering, each location is in one of the string values of the
    JSON object. The two outputs differ, and running either command twice gives the
    same output twice.

    :verifies: SEG-SREQ-291
    :test-id: SEG-TS-181
    """
    monkeypatch.chdir(tmp_path)
    root = _case(tmp_path)
    store = _store(tmp_path)
    assert main(["case", "sync", "--case", str(root), "--current", str(store)]) == 0
    capsys.readouterr()

    def run(*extra: str) -> str:
        main(["graph", "check", "--case", str(root), *extra])
        return capsys.readouterr().out

    stream = ("--current", str(store))
    of_case, of_stream = run(), run(*stream)
    assert run() == of_case and run(*stream) == of_stream
    assert of_case != of_stream
    assert str(root) in of_case
    assert str(store) in of_stream
    json_case = json.loads(run("--json"))
    json_stream = json.loads(run("--json", *stream))
    assert any(str(root) in text for text in _strings(json_case))
    assert any(str(store) in text for text in _strings(json_stream))
    counts = {"nodesByKind", "edgesByKind", "pending"}
    assert {key: json_case[key] for key in counts} == {key: json_stream[key] for key in counts}


def test_a_reader_with_no_usable_repository_cannot_be_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reader with no usable repository cannot be judged, and the reader is named.

    The requirements and test readers name usable repositories. In one file the
    implementation reader names none and the file names no default repository. In
    another file the implementation reader names the repository ghost, which the
    repository map lacks. For each file, case sync and graph status exit with
    status 2 and their output names the reader implementations. The case is
    unchanged.

    :verifies: SEG-SREQ-292
    :test-id: SEG-TS-182
    """
    monkeypatch.chdir(tmp_path)
    root = _case(tmp_path)
    before = _tree(root)
    prefix = {support.KEY_PREFIX: "suite/", support.KEY_REPOSITORY: "suite"}
    lib = {support.KEY_PREFIX: "lib-src/"}
    files = {
        "none": support.implementations_block(**lib),
        "ghost": support.implementations_block(**lib, **{support.KEY_REPOSITORY: "ghost"}),
    }
    for name, implementations in files.items():
        cfg = support.configuration(
            tmp_path,
            requirements=support.requirements_block(**{support.KEY_REPOSITORY: "docs"}),
            specifications=support.specifications_block(**prefix),
            implementations=implementations,
            name=f"{name}.yaml",
        )
        for verb in (["case", "sync"], ["graph", "status"]):
            capsys.readouterr()
            status = main([*verb, "--case", str(root), "--config", str(cfg)])
            assert status == 2, (name, verb)
            assert "implementations" in capsys.readouterr().out, (name, verb)
    assert _tree(root) == before
