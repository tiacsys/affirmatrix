"""Shared helpers for the specifications of node show and of the content behind a hash.

This module is the one place that names the interface the specifications call.
It names the verb and its options. It names the method that gives the bytes
behind a hash, and the function that compares the hashes of one node. It names
the keys of the JSON report and the line forms of the text report. When the final
names differ, this module changes and no test does.

Every fixture is built by the test, inside ``tmp_path``. A git repository is made
with ``git init`` and commits that the test makes. A case is written through the
library or by ``case sync``. No test reads a real case. A test never asks the code
under test for an expected value. It reads the value from the repository or the
case with git or the standard library, or computes it here with ``hashlib``.

The text report is read loosely. A specification finds the block of one hash by
its first line, and then reads the labelled lines of the block. It never reads
the layout between them. The JSON report is read by key.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import case
from affirmatrix.cli import main
from affirmatrix.records import ContentAnchor, NodeRecord

from . import capture_support as shape
from . import extraction_support as base

# --- the interface: the one place -------------------------------------------

#: The noun and the verb of the command.
VERB = ("node", "show")
#: The option that asks for the JSON report, and the one that asks for full digests.
JSON_OPTION = "--json"
VERBOSE_OPTION = "-v"

#: The method of a record source that gives the bytes behind one hash:
#: ``source.content(local_id, hash_name)`` gives the bytes, or ``None``. It is the
#: one method of the runtime-checkable protocol ``ContentSource`` (ruled). The
#: protocol ``RecordSource`` keeps nodes and edges only.
CONTENT_METHOD = "content"
#: The function of ``affirmatrix.drift`` that compares the hashes of one node:
#: ``compare_node(recorded=..., current=...)`` (ruled). Either record can be ``None``.
#: It gives one item for each hash name, with ``name``, ``status``, ``recorded``
#: and ``current`` (the two anchors).
COMPARE_FUNCTION = "compare_node"

# The keys of the JSON report.
KEY_ID = "id"
KEY_KIND = "kind"
KEY_HASHES = "hashes"
KEY_NAME = "name"
KEY_STATUS = "status"
#: The full recorded digest in hex, or ``null`` when the case holds no such hash.
KEY_RECORDED = "recorded"
#: The full current digest in hex, or ``null`` when the current record has no such hash.
KEY_CURRENT = "current"
#: The extraction revision the case records for the repository of the recorded
#: anchor, or ``null``.
KEY_RECORDED_REVISION = "recordedRevision"
#: ``null`` when the hash has no current anchor. Else an object with the keys below.
#: The JSON report always gives full digests (ruled).
KEY_CHECKOUT = "checkout"
KEY_CHECKOUT_REPOSITORY = "repository"
KEY_CHECKOUT_CONFIGURED = "configured"
KEY_CHECKOUT_REVISION = "revision"
KEY_CHECKOUT_DIRTY = "dirtyPaths"
#: The reason, as text, when a configured repository cannot be read. Else absent or null.
KEY_CHECKOUT_ERROR = "error"
#: The current content, or ``null`` when no content is supplied. It is the text
#: of the bytes when they are valid UTF-8. Otherwise it is their base64 form, and
#: the entry names the encoding under ``KEY_ENCODING`` (claim 328).
KEY_CONTENT = "content"
KEY_ENCODING = "encoding"
ENCODING_BASE64 = "base64"
#: The key of a refusal.
KEY_ERROR = "error"

# The statuses are the values of ``affirmatrix.drift.HashStatus``.
MATCHING = "matching"
DIFFERING = "differing"
RECORDED_ONLY = "recordedOnly"
CURRENT_ONLY = "currentOnly"

# The line forms of the text report. The first line of the block of a hash is
# ``hash <name>: <status>``. The labelled lines follow, indented.
HASH_LINE_PREFIX = "hash "
LABEL_EXTRACTED = "extracted from:"
LABEL_CHECKOUT = "checkout:"
LABEL_WORKTREE = "worktree:"
CONTENT_HEADER = "content:"
#: The words of the three "none" reports and of a clean worktree, found in a labelled line.
NONE_RECORDED = "none recorded"
NONE_SUPPLIED = "none supplied"
NOT_CONFIGURED = "no repository is configured"
#: The words of a hash with no current side, and of a repository that cannot be read.
NO_CURRENT_CONTENT = "no current content"
CANNOT_READ = "cannot be read"
CLEAN = "clean"

requires_git = base.requires_git

GIVEN = base.GIVEN


# --- the text and the JSON report -------------------------------------------


def output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


@dataclass(frozen=True)
class Place:
    """Where a command finds its case, its configuration and its current stream.

    ``current`` is ``None`` when the configuration names the producer.
    """

    case: Path
    config: Path
    current: Path | None

    def arguments(self) -> list[str]:
        arguments = ["--case", str(self.case), "--config", str(self.config)]
        if self.current is not None:
            arguments += ["--current", str(self.current)]
        return arguments

    def moved_to(self, current: Path | None) -> Place:
        return Place(self.case, self.config, current)


def place(fixture: base.Fixture) -> Place:
    return Place(fixture.case, fixture.config, fixture.current)


def place_shapes(shapes: base.Shapes) -> Place:
    return Place(shapes.case, shapes.config, None)


@dataclass(frozen=True)
class Shown:
    """The text and the JSON report of one node, from two runs of the command."""

    status: int
    text: str
    raw: str
    document: Any

    def hashes(self) -> dict[str, dict[str, Any]]:
        return {entry[KEY_NAME]: entry for entry in self.document[KEY_HASHES]}

    def entry(self, name: str) -> dict[str, Any]:
        return self.hashes()[name]

    def block(self, name: str) -> list[str]:
        """The lines of the text block of one hash, the first line included."""
        lines = self.text.splitlines()
        opening = f"{HASH_LINE_PREFIX}{name}:"
        block: list[str] = []
        inside = False
        for line in lines:
            if line.startswith(HASH_LINE_PREFIX):
                inside = line.startswith(opening)
            if inside:
                block.append(line)
        return block

    def block_status(self, name: str) -> str:
        (first, *_) = self.block(name) or [""]
        return first.partition(":")[2].strip()

    def labelled(self, name: str, label: str) -> list[str]:
        """The lines of the block of one hash that start with ``label``."""
        return [line.strip() for line in self.block(name) if line.strip().startswith(label)]

    def shown_content(self, name: str) -> list[str]:
        """The lines that follow the content header in the block of one hash."""
        block = self.block(name)
        for number, line in enumerate(block):
            if line.strip() == CONTENT_HEADER:
                return [item.strip() for item in block[number + 1 :]]
        return []

    def block_text(self, name: str) -> str:
        return "\n".join(self.block(name))


def show(
    where: Place,
    local_id: str,
    capsys: pytest.CaptureFixture[str],
    *extra: str,
    current: Path | None | bool = True,
) -> Shown:
    """Run ``node show`` twice, as text and as JSON with full digests.

    Both runs must give the same exit status. With ``current`` a path, that
    path is the current stream. With ``current`` false, none is given.
    """
    target = where if current is True else where.moved_to(current or None)
    arguments = [*VERB, local_id, *target.arguments(), *extra]
    capsys.readouterr()
    status = main(arguments)
    text = output(capsys)
    json_status = main([*arguments, JSON_OPTION, VERBOSE_OPTION])
    raw = output(capsys)
    assert json_status == status, (status, json_status)
    try:
        document = json.loads(raw)
    except ValueError:
        document = None
    return Shown(status, text, raw, document)


def content_bytes(entry: dict[str, Any]) -> bytes:
    """The bytes that the JSON content of one hash entry stands for."""
    content = entry[KEY_CONTENT]
    if entry.get(KEY_ENCODING) == ENCODING_BASE64:
        return base64.b64decode(content, validate=True)
    return content.encode("utf-8")


def hex_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


# --- the library -------------------------------------------------------------


def content_of(source: object, local_id: str, name: str) -> bytes | None:
    """The bytes a record source gives for one hash of one node."""
    return getattr(source, CONTENT_METHOD)(local_id, name)


def members(producer: Any, kind: type) -> list[Any]:
    """The members of a composed producer that are of one class."""
    return [member for member in producer.sources if isinstance(member, kind)]


def anchor(text: str, *, path: str | None = None, repository: str = "content") -> ContentAnchor:
    """An anchor whose digest is the SHA-256 of ``text``."""
    return ContentAnchor(
        digest=digest_of(text.encode("utf-8")),
        repository=repository,
        path=path if path is not None else f"{hex_of(text.encode('utf-8'))[:8]}.txt",
        locator="file",
    )


def node(kind: str, local_id: str, **texts: str) -> NodeRecord:
    """A node record whose hash of each name covers the given text."""
    return NodeRecord(
        local_id=local_id,
        kind=kind,
        content_anchors={name: anchor(text) for name, text in texts.items()},
    )


def compare_nodes(recorded: NodeRecord | None, current: NodeRecord | None) -> dict[str, Any]:
    """The items of the node comparison, by hash name. One item for each name."""
    from affirmatrix import drift

    items = list(getattr(drift, COMPARE_FUNCTION)(recorded=recorded, current=current))
    by_name = {item.name: item for item in items}
    assert len(by_name) == len(items), "two items for one hash name"
    return by_name


# --- a store of three kinds, in one git repository --------------------------

#: The files each node of the store hashes, by hash name, relative to the repository.
MULTI_FILES: dict[str, dict[str, str]] = {
    "REQ-A": {"contentHash": "requirement/REQ-A.txt"},
    "TS-1": {
        "specHash": "test-specification/TS-1.spec.txt",
        "implHash": "test-specification/TS-1.impl.txt",
    },
    "IMP-1": {
        "apiHash": "implementation/IMP-1.api.txt",
        "bodyHash": "implementation/IMP-1.body.txt",
    },
}
MULTI_KINDS = {"REQ-A": "Requirement", "TS-1": "TestSpecification", "IMP-1": "Implementation"}
_MANIFESTS = {
    "REQ-A": "requirements.toml",
    "TS-1": "test-specifications.toml",
    "IMP-1": "implementations.toml",
}


def original_text(local_id: str, name: str) -> str:
    """Two lines, so that a test can tell a whole text from a part of it."""
    return f"the {name} of {local_id}\nsecond line of the {name} of {local_id}\n"


def build_multi(tmp_path: Path) -> base.Fixture:
    """A store of a requirement, a test specification and an implementation.

    The files are in one git repository and committed once. The test
    specification verifies the requirement and the implementation implements
    it. The case is initialized and empty. The configuration maps the
    repository.
    """
    root = tmp_path / "store"
    repository = base.init_repository(root / "content")
    for local_id, files in MULTI_FILES.items():
        lines = [f'kind = "{MULTI_KINDS[local_id]}"', "", "[nodes]"]
        fields = ", ".join(f'{name} = "{path}"' for name, path in files.items())
        for name, path in files.items():
            base.write(repository, path, original_text(local_id, name))
        lines.append(f'"{local_id}" = {{ {fields} }}')
        base.write(root, f"nodes/{_MANIFESTS[local_id]}", "\n".join(lines) + "\n")
    base.write(
        root,
        "edges/links.toml",
        '[edges]\nVerifies = [["TS-1", "REQ-A"]]\nImplements = [["IMP-1", "REQ-A"]]\n',
    )
    base.commit_all(repository, "first commit")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    fixture = base.Fixture(
        root=root,
        repository=repository,
        name=str(repository),
        case=case_root,
        config=tmp_path / "content-repositories.yaml",
    )
    base.configure(fixture, mapped=True)
    return fixture


def rewrite_hash_file(fixture: base.Fixture, local_id: str, name: str, text: str) -> str:
    """Write the file one hash covers. Return its path in the repository."""
    path = MULTI_FILES[local_id][name]
    base.write(fixture.repository, path, text)
    return path


def current_text(fixture: base.Fixture, local_id: str, name: str) -> str:
    """The text in the working tree of the file one hash covers."""
    path = MULTI_FILES[local_id][name]
    return (fixture.repository / path).read_text(encoding="utf-8")


def current_hex(fixture: base.Fixture, local_id: str, name: str) -> str:
    path = MULTI_FILES[local_id][name]
    return hex_of((fixture.repository / path).read_bytes())


def recorded_hex(fixture: base.Fixture, local_id: str, name: str) -> str:
    """The digest the case holds for one hash, in hex."""
    return base.held_digests(fixture.case, local_id)[name].hex()


def sync(fixture: base.Fixture, capsys: pytest.CaptureFixture[str]) -> None:
    status, out = base.sync(fixture, capsys)
    assert status == 0, out


def drop_requirement(fixture: base.Fixture, local_id: str) -> None:
    """Remove one requirement of the single-kind store from its manifest and its edges."""
    manifest = fixture.root / "nodes" / "requirements.toml"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if f'"{local_id}"' not in line]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")
    edges = fixture.root / "edges" / "refines.toml"
    pairs = [f'    ["{one}", "REQ-A"],' for one in base.IDS if one not in (local_id, "REQ-A")]
    edges.write_text("[edges]\nRefines = [\n" + "\n".join(pairs) + "\n]\n", encoding="utf-8")


def add_requirement(fixture: base.Fixture, local_id: str) -> None:
    """Add one requirement, with its file, to the single-kind store."""
    base.write(fixture.repository, f"requirement/{local_id}.txt", f"statement of {local_id}\n")
    manifest = fixture.root / "nodes" / "requirements.toml"
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(f'"{local_id}" = {{ contentHash = "requirement/{local_id}.txt" }}\n')


# --- producers over the capture-shape fixture --------------------------------


def composed_configuration(tmp_path: Path, *, requirements: bool = True) -> Path:
    """A configuration of the three readers over the capture-shape repositories.

    The requirements reader anchors to ``docs``, the test specifications to
    ``suite`` and the implementations to ``lib``. The repositories are the
    frozen fixture directories. They are only read.
    """
    own = {shape.KEY_REPOSITORY: "docs"}
    needs = shape.needs_of
    cases = [
        n
        for n in needs(shape.document_of(shape.TEST_CASES_EXPORT)).values()
        if n["type"] == "test_case"
    ]
    impls = [
        n
        for n in needs(shape.document_of(shape.IMPLEMENTATIONS_EXPORT)).values()
        if n["type"] == "impl"
    ]
    specifications = shape.specifications_block(
        export=str(shape.export_of(tmp_path, cases, "cases")),
        **{shape.KEY_PREFIX: "suite/", shape.KEY_REPOSITORY: "suite"},
    )
    implementations = shape.implementations_block(
        export=str(shape.export_of(tmp_path, impls, "impls")),
        **{shape.KEY_PREFIX: "lib-src/", shape.KEY_REPOSITORY: "lib"},
    )
    return shape.configuration(
        tmp_path,
        requirements=shape.requirements_block(**own) if requirements else None,
        specifications=specifications,
        implementations=implementations,
    )


# --- reads of a repository ---------------------------------------------------


def stale_checkout(fixture: base.Fixture, local_id: str = "REQ-C") -> None:
    """An uncommitted change in one file, and an index that is out of date."""
    fixture.rewrite(local_id, "an edit that nobody committed\n")
    base.make_index_stale(fixture.repository)


def control_writes_the_index(repository: Path) -> bool:
    """Whether a plain ``git status`` changes the index of ``repository``."""
    before = base.snapshot(repository / ".git")
    base.git(repository, "status", "--porcelain=v1")
    return base.snapshot(repository / ".git") != before


def listed(*records: NodeRecord) -> base.ListedSource:
    return base.ListedSource(tuple(records))
