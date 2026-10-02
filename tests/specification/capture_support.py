"""Shared helpers for the specifications of producers that differ from the first fixture.

This module holds the one place that names the configuration keys and the
configuration attributes of the new reader options. The names are the ones the
requirement pages suggest. When the final names differ, this module changes
and no test does.

Every expected value in a test is computed from the fixture files with the
standard library, never by calling the reader or the extractor.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml

from affirmatrix import config
from affirmatrix.records import EdgeRecord, NodeRecord
from affirmatrix.sources.composed import from_config

# --- the names of the new options: the one place ---------------------------

KEY_REPOSITORY = "repository"
KEY_PREFIX = "doxygen-prefix"
KEY_PARENT = "parent-field"
KEY_MAP = "source-map"
KEY_TYPES = "types"

ATTR_REPOSITORY = "repository"
ATTR_PREFIX = "doxygen_prefix"
ATTR_PARENT = "parent_field"
ATTR_MAP = "source_map"
ATTR_TYPES = "types"

# --- the fixture ------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "capture_shape"
NEEDS = FIXTURE / "needs"
REPOS = FIXTURE / "repos"
XML = FIXTURE / "xml"
REQUIREMENTS_EXPORT = NEEDS / "requirements.json"
TEST_CASES_EXPORT = NEEDS / "test-cases.json"
IMPLEMENTATIONS_EXPORT = NEEDS / "implementations.json"

SOURCE_MAP = {
    "docs/alpha": str(REPOS / "docs" / "reqs" / "alpha.sdoc"),
    "docs/beta": str(REPOS / "docs" / "reqs" / "beta.sdoc"),
}
REFERENCE_PARENTS = {"R-1": [], "R-2": ["R-1"], "R-3": ["R-1", "R-2"]}
CONTENT_HASH = "contentHash"


def requirements_block(**keys: Any) -> dict[str, Any]:
    """The requirements block over the fixture export, with the source directory form."""
    block: dict[str, Any] = {
        "export": str(REQUIREMENTS_EXPORT),
        KEY_TYPES: ["req"],
        "source": str(REPOS / "docs" / "reqs"),
    }
    block.update(keys)
    return block


def specifications_block(doxygen: str = "prefixed-spec", **keys: Any) -> dict[str, Any]:
    block: dict[str, Any] = {"export": str(TEST_CASES_EXPORT), "doxygen": str(XML / doxygen)}
    block.update(keys)
    return block


def implementations_block(doxygen: str = "prefixed-impl", **keys: Any) -> dict[str, Any]:
    block: dict[str, Any] = {"export": str(IMPLEMENTATIONS_EXPORT), "doxygen": str(XML / doxygen)}
    block.update(keys)
    return block


def without(block: Mapping[str, Any], *names: str) -> dict[str, Any]:
    return {key: value for key, value in block.items() if key not in names}


def configuration(
    directory: Path,
    *,
    requirements: Mapping[str, Any] | None = None,
    specifications: Mapping[str, Any] | None = None,
    implementations: Mapping[str, Any] | None = None,
    default_repository: str | None = None,
    repositories: Mapping[str, Path] | None = None,
    name: str = "affirmatrix.yaml",
) -> Path:
    """Write a configuration file naming the fixture repositories; return its path."""
    mapped = repositories or {
        "docs": REPOS / "docs",
        "suite": REPOS / "suite",
        "lib": REPOS / "lib",
    }
    producer: dict[str, Any] = {}
    if default_repository is not None:
        producer["repository"] = default_repository
    for key, block in (
        ("requirements", requirements),
        ("specifications", specifications),
        ("implementations", implementations),
    ):
        if block is not None:
            producer[key] = dict(block)
    document = {
        "repositories": {key: str(path) for key, path in mapped.items()},
        "implementation": "suite",
        "producer": producer,
    }
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def producer_of(path: Path):
    return from_config(config.load(path))


def records(path: Path) -> tuple[dict[str, NodeRecord], list[EdgeRecord]]:
    """Build the producer a file describes and drain both streams."""
    producer = producer_of(path)
    nodes = {node.local_id: node for node in producer.nodes()}
    return nodes, list(producer.edges())


def loaded(path: Path) -> config.ProducerConfig:
    producer = config.load(path).producer
    assert producer is not None
    return producer


def attribute(owner: object, name: str) -> Any:
    return getattr(owner, name)


# --- exports ----------------------------------------------------------------


def document_of(export: Path) -> dict[str, Any]:
    return json.loads(export.read_text(encoding="utf-8"))


def needs_of(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (version,) = document["versions"].values()
    return version["needs"]


def variant(
    tmp_path: Path, export: Path, edit: Callable[[dict[str, dict[str, Any]]], None], name: str
) -> Path:
    """The export with ``edit`` applied to its needs, written under ``tmp_path``."""
    document = copy.deepcopy(document_of(export))
    edit(needs_of(document))
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def export_of(tmp_path: Path, needs: list[dict[str, Any]], name: str) -> Path:
    """An export holding exactly the given needs."""
    document = {
        "current_version": "v0",
        "versions": {"v0": {"needs": {entry["id"]: entry for entry in needs}}},
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def case_need(ident: str, symbol: str, module: str = "tests/spans", **more: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": ident,
        "type": "test_case",
        "title": ident.lower(),
        "content": f"Checks {symbol}.",
        "docname": "suite/test-spec",
        "doctype": ".rst",
        "verifies": ["R-1"],
        "test_function": symbol,
        "test_module": module,
    }
    entry.update(more)
    return entry


def implementation_need(ident: str, symbol: str, **more: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": ident,
        "type": "impl",
        "title": symbol,
        "content": f"Provides {symbol}.",
        "docname": "lib/design",
        "doctype": ".rst",
        "satisfies": ["R-1"],
    }
    entry.update(more)
    return entry


# --- expected digests, computed from files ---------------------------------


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def file_lines(root: Path, relative: str) -> list[bytes]:
    return (root / relative).read_bytes().splitlines(keepends=True)


def run_of(lines: list[bytes], first: int, last: int) -> bytes:
    return b"".join(lines[first - 1 : last])


def comment_run(lines: list[bytes], tag: str) -> bytes:
    """The documentation comment that carries ``@testid{tag}``, opener to closer."""
    (hit,) = [n for n, text in enumerate(lines, 1) if f"@testid{{{tag}}}".encode() in text]
    opener = hit
    while b"/**" not in lines[opener - 1]:
        opener -= 1
    closer = hit
    while not lines[closer - 1].rstrip().endswith(b"*/"):
        closer += 1
    return run_of(lines, opener, closer)


def canonical_digest(content: str, parents: list[str], title: str) -> bytes:
    """SHA-256 of the canonical form of a requirement; the key stays ``refines``."""
    form = {"content": content, "refines": sorted(parents), "title": title}
    text = json.dumps(form, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha(text.encode("utf-8"))


def copied_repositories(tmp_path: Path) -> dict[str, Path]:
    """A private copy of the fixture repositories, safe to edit."""
    target = tmp_path / "repos"
    shutil.copytree(REPOS, target)
    return {name: target / name for name in ("docs", "suite", "lib")}


def rewritten(tmp_path: Path, doxygen: str, old: str, new: str, name: str) -> Path:
    """A copy of a Doxygen tree in which ``old`` becomes ``new`` in every file."""
    target = tmp_path / name
    shutil.copytree(XML / doxygen, target)
    for path in target.glob("*.xml"):
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return target
