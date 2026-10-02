"""Verification suite for how the affirmation store carries the extraction revisions.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests run the store and the library. They run no git. A node record carries an
optional map from a repository name to a revision. The specifications read the
map back through the store and, where the stored form is the claim, from the
JSON document of the case. The names of the field and of the stored key are in
``extraction_support``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from affirmatrix import case, commitment, drift, graph
from affirmatrix.cli import main
from affirmatrix.records import ContentAnchor, LinkState, NodeRecord
from affirmatrix.sources.store import StoreLoader

from . import extraction_support as support

FIRST = "1" * 40
SECOND = "2" * 64


def _anchor(text: str, repository: str = "content") -> ContentAnchor:
    return ContentAnchor(
        digest=hashlib.sha256(text.encode("utf-8")).digest(),
        repository=repository,
        path=f"{text}.txt",
        locator="file",
    )


def _node(kind: str, local_id: str) -> NodeRecord:
    """One node record of each kind a case can hold, with the fields the kind needs."""
    if kind == "Implementation":
        anchors = {"apiHash": _anchor(f"{local_id}-api"), "bodyHash": _anchor(f"{local_id}-body")}
    elif kind == "TestSpecification":
        anchors = {"specHash": _anchor(f"{local_id}-spec"), "implHash": _anchor(f"{local_id}-impl")}
    else:
        anchors = {"contentHash": _anchor(local_id)}
    extra = {"expiry": "2030-01-01", "approver": "Approver"} if kind == "Waiver" else {}
    return NodeRecord(local_id=local_id, kind=kind, content_anchors=anchors, **extra)


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-304: a node record has no field for an extraction revision"
)
def test_a_node_record_keeps_the_extraction_revisions_it_is_given(tmp_path: Path) -> None:
    """A node record keeps the extraction revisions it is given.

    The store writes one node record of each kind that a case holds: a
    requirement, an implementation, a test specification and a waiver. Each
    record carries a map from a repository name to a revision. The map has one
    repository for one record and two repositories for the others. A new store
    over the same root reads each record back with the same map. The stored
    document of each record holds the map as a JSON object under one key, from
    repository name to revision.

    :verifies: SEG-SREQ-304
    :test-id: SEG-TS-195
    """
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    maps = {
        "Requirement": {"content": FIRST},
        "Implementation": {"content": FIRST, "library": SECOND},
        "TestSpecification": {"library": SECOND},
        "Waiver": {"content": FIRST, "library": SECOND},
    }
    given = {
        kind: support.with_extracted_from(_node(kind, f"NODE-{kind}"), revisions)
        for kind, revisions in maps.items()
    }
    store.write_nodes(given.values())
    read_back = support.held(root)
    for kind, revisions in maps.items():
        assert support.extracted_from(read_back[f"NODE-{kind}"]) == revisions, kind
        assert support.stored_entry(root, kind, f"NODE-{kind}")[support.JSON_KEY] == revisions


def test_a_node_record_without_an_extraction_revision_is_read_back_as_written(
    tmp_path: Path,
) -> None:
    """A node record without an extraction revision is read back as written.

    The store writes one node record of each kind that a case holds, with no
    extraction revision. A new store over the same root reads each record back
    equal to the record written. The record carries no revision. The stored
    document of each record has no extraction revision field. Writing the
    same records again changes no byte of the case.

    :verifies: SEG-SREQ-305
    :test-id: SEG-TS-196
    """
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    kinds = ("Requirement", "Implementation", "TestSpecification", "Waiver")
    written = {f"NODE-{kind}": _node(kind, f"NODE-{kind}") for kind in kinds}
    store.write_nodes(written.values())
    assert support.held(root) == written
    for kind in kinds:
        assert support.extracted_from(support.held(root)[f"NODE-{kind}"]) == {}
        assert not support.has_stored_key(root, kind, f"NODE-{kind}")
    before = support.tree(root)
    store.write_nodes(written.values())
    assert support.tree(root) == before


@support.requires_git
@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-005: a node record has no field for an extraction revision"
)
def test_the_extraction_revisions_never_enter_a_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The extraction revisions never enter a node hash, an edge hash or the design root.

    Two cases hold the same nodes and edges. In the second case every node
    record also carries a map of extraction revisions. Each node hash, derived
    from the node kind and the content hashes, is the same in both cases. The
    design root over all node hashes and edge tuples is the same. An edge is
    affirmed in the first case. A current stream whose node records carry the
    map derives that edge as active, with the edge hash it was affirmed against.

    :verifies: SEG-SREQ-005
    :test-id: SEG-TS-197
    """
    monkeypatch.chdir(tmp_path)
    fixture = support.build(tmp_path)
    loader = StoreLoader(root=fixture.root)
    nodes, edges = list(loader.nodes()), list(loader.edges())
    stamped = [
        support.with_extracted_from(node, {"content": FIRST, "library": SECOND}) for node in nodes
    ]
    plain_root, stamped_root = tmp_path / "plain", tmp_path / "stamped"
    for root, records in ((plain_root, nodes), (stamped_root, stamped)):
        store = case.AffirmationStore(root=root)
        store.initialize()
        store.write_records(records, edges)

    def seal(root: Path) -> tuple[dict[str, bytes], bytes]:
        built = graph.build(case.AffirmationStore(root=root))
        hashes = {
            local_id: commitment.node_hash(
                built.node(local_id).kind, built.node(local_id).content_hashes
            )
            for local_id in sorted(built.node_ids())
        }
        tuples = [(edge.from_id, edge.to_id, edge.kind) for edge in built.edges]
        return hashes, commitment.design_root(b"", hashes.values(), tuples)

    assert seal(plain_root) == seal(stamped_root)
    arguments = ["--kind", "Refines", "--from", "REQ-B", "--to", "REQ-A"]
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(plain_root),
            "--current",
            str(fixture.root),
            *arguments,
            "--role",
            "Reviewer",
            "--reason",
            "checked",
            "--revision",
            support.GIVEN,
        ]
    )
    assert status == 0

    class Stamped:
        def nodes(self):
            return iter(stamped)

        def edges(self):
            return iter(edges)

    recorded = case.AffirmationStore(root=plain_root)
    (affirmed,) = [edge for edge in recorded.edges() if edge.edge_hash is not None]
    derived = {
        (edge.from_id, edge.to_id, edge.kind): edge
        for edge in drift.derive(recorded=recorded, current=Stamped()).edges()
    }
    again = derived[(affirmed.from_id, affirmed.to_id, affirmed.kind)]
    assert again.state is LinkState.ACTIVE
    assert again.edge_hash == affirmed.edge_hash


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-304: no node schema declares an extraction revision"
)
def test_every_node_schema_declares_the_extraction_revisions_as_optional() -> None:
    """Every node schema declares the extraction revisions as an optional property.

    Each of the five packaged node schemas, for a requirement, an implementation,
    a test specification, a test outcome and a waiver, declares the extraction
    revision key as a property. The property is an object. No schema lists it as
    required, so a record without it stays valid.

    :verifies: SEG-SREQ-304
    :test-id: SEG-TS-198
    """
    from importlib import resources

    directory = resources.files("affirmatrix.case") / "schema"
    for kind, name in support.NODE_SCHEMAS.items():
        schema = json.loads((directory / name).read_text(encoding="utf-8"))
        declared = schema["properties"].get(support.JSON_KEY)
        assert declared is not None, kind
        assert declared["type"] == "object", kind
        assert support.JSON_KEY not in schema["required"], kind


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-325: a node record has no field for an extraction revision"
)
def test_a_malformed_extraction_revision_is_refused(tmp_path: Path) -> None:
    """The store refuses an extraction revision that is not 40 or 64 lowercase hex characters.

    The store is given a node record whose map holds one of these values: the word
    XYZ, 40 uppercase hex characters, 39 lowercase hex characters, and 41
    lowercase hex characters. Each write raises a store error. No file of the case
    changes. A value of 40 and a value of 64 lowercase hex characters are
    accepted.

    :verifies: SEG-SREQ-325
    :test-id: SEG-TS-220
    """
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    before = support.tree(root)
    for value in ("XYZ", "A" * 40, "a" * 39, "a" * 41):
        node = support.with_extracted_from(_node("Requirement", "NODE-BAD"), {"content": value})
        with pytest.raises(case.AffirmationStoreError):
            store.write_nodes([node])
        assert support.tree(root) == before, value
    for value in (FIRST, SECOND):
        node = support.with_extracted_from(_node("Requirement", "NODE-GOOD"), {"content": value})
        store.write_nodes([node])
        assert support.held_map(root, "NODE-GOOD") == {"content": value}


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-326: a node record has no field for an extraction revision"
)
def test_a_node_record_with_no_revision_is_stored_with_no_field(tmp_path: Path) -> None:
    """The store persists a node record with no extraction revision with no such field.

    The store writes a node record with an empty map, and a node record with no
    map. The stored document of each has no extraction revision key. A record is
    written with a map and then written again with an empty map. The stored
    document of that record then has no extraction revision key, and not an
    empty object.

    :verifies: SEG-SREQ-326
    :test-id: SEG-TS-221
    """
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    empty = support.with_extracted_from(_node("Requirement", "NODE-EMPTY"), {})
    store.write_nodes([empty, _node("Requirement", "NODE-NONE")])
    for local_id in ("NODE-EMPTY", "NODE-NONE"):
        assert not support.has_stored_key(root, "Requirement", local_id)
    stamped = support.with_extracted_from(_node("Requirement", "NODE-AGAIN"), {"content": FIRST})
    store.write_nodes([stamped])
    assert support.has_stored_key(root, "Requirement", "NODE-AGAIN")
    store.write_nodes([support.with_extracted_from(stamped, {})])
    assert not support.has_stored_key(root, "Requirement", "NODE-AGAIN")
