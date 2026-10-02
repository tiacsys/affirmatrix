"""Shared helpers for the specifications of the extraction revision.

This module is the one place that names the interface the specifications call:
the record field, the key in a stored node record, and the form of the report
line. When the final names differ, this module changes and no test does.

Every fixture is built by the test, inside ``tmp_path``. A git repository is made
with ``git init`` and commits that the test makes. No test reads a real case.
Every expected value is read from the repository or from the case with git or
the standard library, never by calling the code under test.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.records import NodeRecord
from affirmatrix.sources.store import StoreLoader

from . import capture_support as shape

# --- the interface: the one place ------------------------------------------

#: The field of a node record that holds the map from repository name to revision.
ATTRIBUTE = "extracted_from"
#: The key of that map in a stored node record.
JSON_KEY = "seg:extractedFrom"
#: The document of each node kind in a case, below ``nodes/``.
NODE_DOCUMENTS = {
    "Requirement": "requirements",
    "Implementation": "implementations",
    "TestSpecification": "test_specifications",
    "Waiver": "waivers",
}
#: The packaged schema file of each node kind a case can hold.
NODE_SCHEMAS = {
    "Requirement": "requirement.schema.json",
    "Implementation": "implementation.schema.json",
    "TestSpecification": "test_specification.schema.json",
    "TestOutcome": "test_outcome.schema.json",
    "Waiver": "waiver.schema.json",
}
#: The draft form of the report line of SEG-SREQ-310. Only a reference
#: implementation prints it. A specification reads a line loosely: a line that
#: names the repository, with the count as the one whole number left in it.
REPORT_FORM = "no extraction revision: {repository}: {count} node records"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def extracted_from(node: NodeRecord) -> dict[str, str]:
    """The map a node record carries; empty when it carries none."""
    return dict(getattr(node, ATTRIBUTE, None) or {})


def with_extracted_from(node: NodeRecord, revisions: Mapping[str, str]) -> NodeRecord:
    """A copy of ``node`` that carries ``revisions`` as its map."""
    return dataclasses.replace(node, **{ATTRIBUTE: dict(revisions)})


def reported_counts(text: str, repository: str) -> list[int]:
    """The whole numbers in each line of ``text`` that names ``repository``.

    The repository name is cut out of the line first, so a digit inside a
    name never counts. A line with one whole number gives that number.
    """
    counts: list[int] = []
    for line in text.splitlines():
        if repository in line:
            numbers = re.findall(r"\b\d+\b", line.replace(repository, ""))
            counts.extend(int(number) for number in numbers)
    return counts


# --- git ---------------------------------------------------------------------


def _environment() -> dict[str, str]:
    """The environment of the test's own git calls: no user or system settings."""
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        env=_environment(),
    )
    return completed.stdout.strip()


def init_repository(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    return path


def head(repository: Path) -> str:
    return git(repository, "rev-parse", "HEAD")


def commit_all(repository: Path, message: str) -> str:
    """Commit every change in ``repository`` and return the new revision."""
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", message)
    return head(repository)


def write(repository: Path, relative: str, text: str) -> None:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot(directory: Path) -> dict[str, str]:
    """The SHA-256 of every file under ``directory``, by relative path."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def worktree(repository: Path) -> dict[str, bytes]:
    """The bytes of every file of the working tree, without the .git directory."""
    return {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in sorted(repository.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repository).parts
    }


def make_index_stale(repository: Path) -> None:
    """Change the recorded modification time of every tracked file, not its content.

    A plain ``git status`` then finds that the index entries are out of date and
    writes a fresh index. A read that turns optional locks off does not.
    """
    for path in sorted(repository.rglob("*")):
        if path.is_file() and ".git" not in path.relative_to(repository).parts:
            os.utime(path, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))


# --- a case over one repository ----------------------------------------------

IDS = ("REQ-A", "REQ-B", "REQ-C")
GIVEN = "c" * 40


@dataclass(frozen=True)
class Fixture:
    """A would-be store whose content directory is a git repository.

    Every anchor of the store names that one repository. ``name`` is the
    repository name an anchor carries, and ``config`` maps it to the directory.
    ``case`` is an initialized case, and ``current`` is the store that supplies
    the current stream. Every requirement refines REQ-A except REQ-A itself.
    """

    root: Path
    repository: Path
    name: str
    case: Path
    config: Path

    @property
    def current(self) -> Path:
        return self.root

    def file(self, local_id: str) -> str:
        return f"requirement/{local_id}.txt"

    def rewrite(self, local_id: str, text: str) -> None:
        write(self.repository, self.file(local_id), text)


def build(tmp_path: Path, *, mapped: bool = True) -> Fixture:
    """A store of three requirements, committed once, and an empty case."""
    root = tmp_path / "store"
    repository = init_repository(root / "content")
    lines = ['kind = "Requirement"', "", "[nodes]"]
    for local_id in IDS:
        write(repository, f"requirement/{local_id}.txt", f"statement of {local_id}\n")
        lines.append(f'"{local_id}" = {{ contentHash = "requirement/{local_id}.txt" }}')
    write(root, "nodes/requirements.toml", "\n".join(lines) + "\n")
    write(
        root,
        "edges/refines.toml",
        '[edges]\nRefines = [\n    ["REQ-B", "REQ-A"],\n    ["REQ-C", "REQ-A"],\n]\n',
    )
    commit_all(repository, "first commit")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    fixture = Fixture(
        root=root,
        repository=repository,
        name=str(repository),
        case=case_root,
        config=tmp_path / "content-repositories.yaml",
    )
    configure(fixture, mapped=mapped)
    return fixture


def configure(fixture: Fixture, *, mapped: bool, directory: Path | None = None) -> None:
    """Write the configuration: the repository mapped, or only some other name.

    With ``directory``, the repository name maps to that directory instead of
    the repository.
    """
    name = fixture.name if mapped else "some-other-repository"
    target = directory if directory is not None else fixture.repository
    fixture.config.write_text(
        yaml.safe_dump({"repositories": {name: str(target)}}), encoding="utf-8"
    )


def seed_without_revisions(fixture: Fixture) -> None:
    """Write the store's records into the case through the library, with no map."""
    loader = StoreLoader(root=fixture.root)
    case.AffirmationStore(root=fixture.case).write_records(loader.nodes(), loader.edges())


def _text(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def sync(fixture: Fixture, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    status = main(
        [
            "case",
            "sync",
            "--case",
            str(fixture.case),
            "--config",
            str(fixture.config),
            "--current",
            str(fixture.current),
        ]
    )
    return status, _text(capsys)


def affirm(fixture: Fixture, capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str]:
    """Affirm the edge REQ-B refines REQ-A; ``extra`` are more arguments."""
    capsys.readouterr()
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(fixture.case),
            "--config",
            str(fixture.config),
            "--current",
            str(fixture.current),
            "--kind",
            "Refines",
            "--from",
            "REQ-B",
            "--to",
            "REQ-A",
            "--role",
            "Reviewer",
            "--reason",
            "checked",
            *extra,
        ]
    )
    return status, _text(capsys)


def held(case_root: Path) -> dict[str, NodeRecord]:
    """The node records a case holds, by local identifier."""
    return {node.local_id: node for node in case.AffirmationStore(root=case_root).nodes()}


def held_map(case_root: Path, local_id: str) -> dict[str, str]:
    return extracted_from(held(case_root)[local_id])


def held_digests(case_root: Path, local_id: str) -> dict[str, bytes]:
    return dict(held(case_root)[local_id].content_hashes)


def tree(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


# --- stored records ----------------------------------------------------------


def stored_entry(case_root: Path, kind: str, local_id: str) -> dict[str, Any]:
    """The stored entry of a node record, read from the document as JSON."""
    document = case_root / "nodes" / f"{NODE_DOCUMENTS[kind]}.jsonld"
    entries = json.loads(document.read_text(encoding="utf-8"))["@graph"]
    (entry,) = [item for item in entries if item["seg:localId"] == local_id]
    return entry


def has_stored_key(case_root: Path, kind: str, local_id: str) -> bool:
    """Whether the stored entry of a node record has the extraction revision key at all."""
    return JSON_KEY in stored_entry(case_root, kind, local_id)


# --- a case over several repositories -----------------------------------------

REQUIREMENTS_REPOSITORY = "reqrepo"
IMPLEMENTATIONS_REPOSITORY = "implrepo"


@dataclass(frozen=True)
class Shapes:
    """Copies of the capture-shape repositories, each made a git repository.

    The requirement reader anchors to ``reqrepo`` and the implementation
    reader to ``implrepo``. ``case`` is an initialized case. ``config`` is the
    configuration file. The two repositories carry commits of their own, so
    their revisions differ.
    """

    requirements: Path
    implementations: Path
    case: Path
    config: Path


def build_shapes(tmp_path: Path, *, held_paths: bool) -> Shapes:
    """Two committed repositories and a configuration over them.

    With ``held_paths`` the requirement reader names a source file that the
    repository holds. Without it, the reader names a path that the repository
    does not hold at any revision.
    """
    copies = shape.copied_repositories(tmp_path)
    requirements = init_repository(copies["docs"])
    implementations = init_repository(copies["lib"])
    commit_all(requirements, "requirements")
    write(implementations, "notes.txt", "one more commit in this repository\n")
    commit_all(implementations, "implementations")
    write(implementations, "notes.txt", "and a second one\n")
    commit_all(implementations, "implementations again")
    implementation_export = shape.export_of(
        tmp_path,
        [
            shape.implementation_need("I-LIB-MAX", "LIB_MAX", satisfies=["R-1"]),
            shape.implementation_need("I-LIB-MIN", "LIB_MIN", satisfies=["R-2"]),
        ],
        "implementation-needs",
    )
    block: dict[str, Any] = {
        "export": str(shape.REQUIREMENTS_EXPORT),
        shape.KEY_TYPES: ["req"],
        shape.KEY_REPOSITORY: REQUIREMENTS_REPOSITORY,
    }
    if held_paths:
        block[shape.KEY_MAP] = {
            "docs/alpha": str(requirements / "reqs" / "alpha.sdoc"),
            "docs/beta": str(requirements / "reqs" / "beta.sdoc"),
        }
    else:
        block["source"] = str(requirements / "reqs")
    document = {
        "repositories": {
            REQUIREMENTS_REPOSITORY: str(requirements),
            IMPLEMENTATIONS_REPOSITORY: str(implementations),
        },
        "implementation": IMPLEMENTATIONS_REPOSITORY,
        "producer": {
            "requirements": block,
            "implementations": {
                "export": str(implementation_export),
                "doxygen": str(shape.XML / "prefixed-impl"),
                shape.KEY_PREFIX: "lib-src/",
                shape.KEY_REPOSITORY: IMPLEMENTATIONS_REPOSITORY,
            },
        },
    }
    config_path = tmp_path / "shapes.yaml"
    config_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    case_root = tmp_path / "shapes-case"
    case.AffirmationStore(root=case_root).initialize()
    return Shapes(
        requirements=requirements,
        implementations=implementations,
        case=case_root,
        config=config_path,
    )


def move_requirements_to(shapes: Shapes, name: str) -> None:
    """Make the requirement reader anchor in a repository called ``name``.

    The new name maps to the same directory, so every anchored path and every
    content hash stays the same. Only the repository name of the anchors moves.
    """
    document = yaml.safe_load(shapes.config.read_text(encoding="utf-8"))
    document["repositories"][name] = str(shapes.requirements)
    document["producer"]["requirements"][shape.KEY_REPOSITORY] = name
    shapes.config.write_text(yaml.safe_dump(document), encoding="utf-8")


def sync_shapes(shapes: Shapes, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    status = main(["case", "sync", "--case", str(shapes.case), "--config", str(shapes.config)])
    return status, _text(capsys)


# --- a producer that the test supplies ----------------------------------------


@dataclass(frozen=True)
class ListedSource:
    """A record source over fixed lists, for nodes that no reader can produce."""

    node_records: tuple[NodeRecord, ...]

    def nodes(self) -> Iterator[NodeRecord]:
        return iter(self.node_records)

    def edges(self) -> Iterator[Any]:
        return iter(())


def supply(monkeypatch: pytest.MonkeyPatch, source: ListedSource) -> None:
    """Make the command line read ``source`` as the current stream.

    The one place that names how the command line finds its producer.
    """
    from affirmatrix.cli import _judgement

    monkeypatch.setattr(_judgement, "resolve_current", lambda *args, **kwargs: source)
