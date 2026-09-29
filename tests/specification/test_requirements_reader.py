"""Verification suite for the requirements reader and its configuration.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker.
The reader tests read the frozen requirement export under
``tests/fixtures/toolbox_evidence/``; every variant of it is built in the
test, in a temporary directory, by editing the loaded JSON. The configuration
tests write a configuration file to a temporary directory and load it.

The expected-digest computation in the content-hash tests is the
specification's own statement of the canonical form until the architecture
documentation states it: the SHA-256 of the UTF-8 canonical JSON (sorted keys,
no insignificant whitespace) of the need's content, its sorted refines and its
title. The reader is imported inside each test body, so a reader that does not
exist yet is an expected failure of the test, not of the collection.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config
from affirmatrix.records import LinkState

EXPORT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "toolbox_evidence"
    / "needs"
    / "requirement-specification"
    / "needs.json"
)
BOTH_TYPES = frozenset({"top_requirement", "requirement"})


def _document() -> dict[str, Any]:
    return json.loads(EXPORT.read_text(encoding="utf-8"))


def _needs(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (version,) = document["versions"].values()
    return version["needs"]


def _variant(tmp_path: Path, edit: Callable[[dict[str, Any]], None], name: str = "needs") -> Path:
    """The export with ``edit`` applied to its document, written under ``tmp_path``."""
    document = copy.deepcopy(_document())
    edit(document)
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _reader(export: Path = EXPORT, types: frozenset[str] = BOTH_TYPES):
    from affirmatrix.sources.reqs import RequirementsReader

    return RequirementsReader(
        export=export, types=types, repository="toolbox", source_directory=Path("doc")
    )


def _canonical_digest(content: str, refines: list[str], title: str) -> bytes:
    form = {"content": content, "refines": sorted(refines), "title": title}
    text = json.dumps(form, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).digest()


def _digests(export: Path) -> dict[str, bytes]:
    return {
        node.local_id: node.content_anchors["contentHash"].digest
        for node in _reader(export).nodes()
    }


def test_only_configured_need_types_become_requirements() -> None:
    """Only configured need types become Requirements.

    Reading the frozen requirement export with the configured types
    {top_requirement, requirement} supplies Requirement records for exactly
    the 29 need identifiers the export holds; reading it with {requirement}
    alone supplies exactly the 22 identifiers of needs of that type, and no
    identifier of a top_requirement need appears among them.

    :verifies: SEG-SREQ-145
    :test-id: SEG-TS-011
    """
    needs = _needs(_document())
    both = {node.local_id for node in _reader().nodes()}
    assert both == set(needs)
    assert len(both) == 29
    plain = {node.local_id for node in _reader(types=frozenset({"requirement"})).nodes()}
    assert plain == {key for key, need in needs.items() if need["type"] == "requirement"}
    assert len(plain) == 22
    assert not {key for key in plain if needs[key]["type"] == "top_requirement"}


def test_a_requirement_is_identified_by_its_need_identifier_verbatim() -> None:
    """A Requirement is identified by its need identifier, verbatim.

    Reading the frozen requirement export with both requirement types
    configured supplies records whose local identifiers equal, byte for
    byte, the ids of the export's needs, among them SD-REQ-002 and
    SD-TOP-001; no identifier is normalised, prefixed or re-cased.

    :verifies: SEG-SREQ-146
    :test-id: SEG-TS-012
    """
    needs = _needs(_document())
    ids = [node.local_id.encode("utf-8") for node in _reader().nodes()]
    assert sorted(ids) == sorted(need["id"].encode("utf-8") for need in needs.values())
    assert b"SD-REQ-002" in ids
    assert b"SD-TOP-001" in ids


def test_a_requirements_content_hash_covers_its_authored_fields_only(tmp_path: Path) -> None:
    """A Requirement's content hash covers its authored fields and no others.

    The contentHash digest supplied for SD-REQ-002 equals the SHA-256 of the
    UTF-8 canonical JSON (sorted keys, no insignificant whitespace) of an
    object holding exactly its title, its content and its sorted refines,
    computed in the test. In a copy of the export where only its status is
    changed, the digest is the same; in a copy where one character of its
    content is changed, the digest differs.

    :verifies: SEG-SREQ-147
    :test-id: SEG-TS-013
    """
    need = _needs(_document())["SD-REQ-002"]
    expected = _canonical_digest(need["content"], need["refines"], need["title"])
    assert _digests(EXPORT)["SD-REQ-002"] == expected

    def other_status(document: dict[str, Any]) -> None:
        _needs(document)["SD-REQ-002"]["status"] = "draft"

    def other_content(document: dict[str, Any]) -> None:
        target = _needs(document)["SD-REQ-002"]
        target["content"] = target["content"].replace("Every", "Each", 1)

    assert _digests(_variant(tmp_path, other_status, "status"))["SD-REQ-002"] == expected
    assert _digests(_variant(tmp_path, other_content, "content"))["SD-REQ-002"] != expected


def test_the_order_of_refines_links_does_not_change_the_content_hash(tmp_path: Path) -> None:
    """The order of a need's refines links does not change its content hash.

    In two copies of the export where SD-REQ-002 declares the same two
    parents, SD-TOP-006 and SD-TOP-001, in opposite orders, the digest
    supplied for SD-REQ-002 is the same in both, and equals the digest
    computed in the test from the sorted parents.

    :verifies: SEG-SREQ-148
    :test-id: SEG-TS-014
    """
    parents = ["SD-TOP-006", "SD-TOP-001"]

    def declaring(order: list[str]) -> Callable[[dict[str, Any]], None]:
        def edit(document: dict[str, Any]) -> None:
            _needs(document)["SD-REQ-002"]["refines"] = order

        return edit

    need = _needs(_document())["SD-REQ-002"]
    expected = _canonical_digest(need["content"], parents, need["title"])
    forward = _digests(_variant(tmp_path, declaring(parents), "forward"))["SD-REQ-002"]
    reverse = _digests(_variant(tmp_path, declaring(parents[::-1]), "reverse"))["SD-REQ-002"]
    assert forward == reverse == expected


def test_refines_edges_come_from_declared_links_only(tmp_path: Path) -> None:
    """Refines edges come from declared refines links only.

    Reading the frozen export supplies exactly the 22 (child, parent) pairs
    its needs declare in refines, each edge of kind Refines in the pending
    state, running from the child to the parent. In a copy where a need's
    refines_back lists a need that does not declare the link, the edge set
    is unchanged.

    :verifies: SEG-SREQ-149
    :test-id: SEG-TS-015
    """
    needs = _needs(_document())
    declared = {(key, parent) for key, need in needs.items() for parent in need["refines"]}
    assert len(declared) == 22

    edges = list(_reader().edges())
    assert {(edge.from_id, edge.to_id) for edge in edges} == declared
    assert len(edges) == 22
    assert all(edge.kind == "Refines" and edge.state == LinkState.PENDING for edge in edges)

    def stale_back_link(document: dict[str, Any]) -> None:
        _needs(document)["SD-TOP-007"]["refines_back"].append("SD-REQ-002")

    stale = list(_reader(_variant(tmp_path, stale_back_link)).edges())
    assert {(edge.from_id, edge.to_id) for edge in stale} == declared
    assert len(stale) == 22


def test_an_export_carrying_a_build_timestamp_is_refused(tmp_path: Path) -> None:
    """An export carrying a build timestamp is refused.

    Constructing the reader over a copy of the export that adds a created
    stamp to its version entry, and separately over one that adds it at the
    top level, raises the reader's error before any record is supplied;
    constructing it over the export as frozen, whose every timestamp field
    is null, does not.

    :verifies: SEG-SREQ-150
    :test-id: SEG-TS-016
    """
    from affirmatrix.sources.reqs import ReaderError

    def stamp_version(document: dict[str, Any]) -> None:
        (version,) = document["versions"].values()
        version["created"] = "2026-09-29T10:00:00"

    def stamp_top(document: dict[str, Any]) -> None:
        document["created"] = "2026-09-29T10:00:00"

    _reader()
    with pytest.raises(ReaderError):
        _reader(_variant(tmp_path, stamp_version, "version"))
    with pytest.raises(ReaderError):
        _reader(_variant(tmp_path, stamp_top, "top"))


def test_a_requirements_anchor_names_its_source_file_and_its_need() -> None:
    """A Requirement's anchor names its repository, source file and need.

    Reading the frozen export with the repository name "toolbox" and the
    source directory "doc" supplies, for every Requirement, a contentHash
    anchor whose repository is "toolbox" (a name, not a path), whose path is
    the need's docname and doctype under "doc" (doc/detailed.rst for
    SD-REQ-002, doc/top-level.rst for SD-TOP-001) and whose locator is
    need: followed by the need's identifier.

    :verifies: SEG-SREQ-151
    :test-id: SEG-TS-017
    """
    needs = _needs(_document())
    nodes = list(_reader().nodes())
    assert len(nodes) == 29
    for node in nodes:
        need = needs[node.local_id]
        anchor = node.content_anchors["contentHash"]
        assert anchor.repository == "toolbox"
        assert anchor.path == f"doc/{need['docname']}{need['doctype']}"
        assert anchor.locator == f"need:{need['id']}"
    paths = {node.local_id: node.content_anchors["contentHash"].path for node in nodes}
    assert paths["SD-REQ-002"] == "doc/detailed.rst"
    assert paths["SD-TOP-001"] == "doc/top-level.rst"


def _producer(tmp_path: Path) -> config.ProducerConfig:
    path = tmp_path / "repo" / "affirmatrix.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "producer:\n"
        "  repository: sample-repo\n"
        "  requirements:\n"
        "    export: needs/needs.json\n"
        "    types: [sreq, sys, sreq]\n"
        "    source: doc\n",
        encoding="utf-8",
    )
    producer = config.load(path).producer
    assert producer is not None
    return producer


def test_the_producers_repository_name_is_loaded_from_the_file(tmp_path: Path) -> None:
    """The producer's repository name is loaded from the configuration file.

    Loading a configuration file whose producer block names the repository
    "sample-repo" yields a producer whose repository is "sample-repo".

    :verifies: SEG-SREQ-192
    :test-id: SEG-TS-018
    """
    assert _producer(tmp_path).repository == "sample-repo"


def test_the_requirement_export_location_is_loaded_relative_to_the_file(tmp_path: Path) -> None:
    """The requirement export's location is loaded, resolved against the file.

    Loading a configuration file in a subdirectory whose producer
    requirements block names the export "needs/needs.json" yields a
    requirement export path equal to that subdirectory joined with the
    relative path, independent of the working directory.

    :verifies: SEG-SREQ-193
    :test-id: SEG-TS-019
    """
    requirements = _producer(tmp_path).requirements
    assert requirements is not None
    assert requirements.export == tmp_path / "repo" / "needs/needs.json"


def test_the_requirement_types_are_loaded_as_a_set_of_strings(tmp_path: Path) -> None:
    """The requirement types are loaded as a set of strings.

    Loading a configuration file whose producer requirements block lists
    the types sreq and sys, the first listed twice, yields the frozenset
    {"sreq", "sys"}.

    :verifies: SEG-SREQ-194
    :test-id: SEG-TS-020
    """
    requirements = _producer(tmp_path).requirements
    assert requirements is not None
    assert requirements.types == frozenset({"sreq", "sys"})


def test_the_requirement_source_directory_is_loaded_relative_to_the_file(tmp_path: Path) -> None:
    """The requirement source directory is loaded, resolved against the file.

    Loading a configuration file in a subdirectory whose producer
    requirements block names the source directory "doc" yields a source
    directory path equal to that subdirectory joined with "doc".

    :verifies: SEG-SREQ-198
    :test-id: SEG-TS-021
    """
    requirements = _producer(tmp_path).requirements
    assert requirements is not None
    assert requirements.source == tmp_path / "repo" / "doc"
