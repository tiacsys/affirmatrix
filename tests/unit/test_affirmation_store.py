"""The affirmation store's write face, and the case it writes into.

Two things are under test here, and they fail differently. The store is code:
it must refuse a record before any byte lands, keep every path under the write
root, leave no half-written document behind, and carry through everything a
write was not about. The schemas and the shared context are data: they must
describe exactly the fields a record has, and no field that could carry the
content a digest covers.

The refusals are the substance. A store that writes correctly when it is
handed correct records is easy; the requirements this realizes are almost all
about what must *not* happen — content persisted, an invalid record written, a
path escaping the root, a record disappearing because a producer went quiet.

Every test builds its case under ``tmp_path``. The repository's own case is a
separate commit lineage that a maintainer operates; nothing here may touch it.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterable
from datetime import date
from importlib import resources
from pathlib import Path
from types import MappingProxyType

import pytest

from affirmatrix import case, identity, records, taxonomy
from affirmatrix.case import _atomic, _documents, _layout

PACKAGED = resources.files("affirmatrix.case")

REVISION = "a1b2c3d4" * 5
LATER_REVISION = "f0e1d2c3" * 5


def digest(text: str) -> bytes:
    """A digest an auditor could reproduce with ``sha256sum``."""
    return hashlib.sha256(text.encode("utf-8")).digest()


def make_case(tmp_path: Path) -> case.AffirmationStore:
    """A store over a write root that does not exist yet — the ordinary case."""
    return case.AffirmationStore(root=tmp_path / "case")


def anchor(
    content: str,
    locator: str = "file",
    path: str = "doc/spec/store.rst",
    repository: str = "the-source-repo",
) -> records.ContentAnchor:
    return records.ContentAnchor(
        digest=digest(content), repository=repository, path=path, locator=locator
    )


def requirement(local_id: str = "SEG-SREQ-018", content: str = "a statement") -> records.NodeRecord:
    return records.NodeRecord(
        local_id=local_id,
        kind="Requirement",
        content_anchors={"contentHash": anchor(content, locator=f"need:{local_id}")},
    )


def waiver(
    local_id: str = "WVR-001",
    content: str = "a waiver document",
    expiry: date = date(2099, 1, 1),
    approver: str = "A. Reviewer",
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id=local_id,
        kind="Waiver",
        content_anchors={"contentHash": anchor(content, locator="file")},
        expiry=expiry,
        approver=approver,
    )


def outcome(
    local_id: str = "run-1/TS-1",
    content: str = "a test outcome",
    result: records.TestResult = records.TestResult.PASSED,
    revision: str = "r1",
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id=local_id,
        kind="TestOutcome",
        content_anchors={"contentHash": anchor(content, locator="file")},
        result=result,
        revision=revision,
    )


def refines(
    from_id: str = "SEG-SREQ-018",
    to_id: str = "SEG-SYS-007",
    state: records.LinkState = records.LinkState.PENDING,
    edge_hash: bytes | None = None,
) -> records.EdgeRecord:
    return records.EdgeRecord(
        from_id=from_id, to_id=to_id, kind="Refines", state=state, edge_hash=edge_hash
    )


def review_event(
    from_id: str = "SEG-SREQ-018",
    to_id: str = "SEG-SYS-007",
    reason: str = "reviewed together",
    role: str = "RequirementsEngineer",
) -> records.ReviewEvent:
    return records.ReviewEvent(
        from_id=from_id,
        to_id=to_id,
        kind="Refines",
        from_node_hash=digest(from_id),
        to_node_hash=digest(to_id),
        from_source_revision=REVISION,
        to_source_revision=LATER_REVISION,
        role=role,
        reason=reason,
        from_content_anchors={"contentHash": anchor(f"{from_id} content")},
        to_content_anchors={"contentHash": anchor(f"{to_id} content")},
    )


def document_of(store: case.AffirmationStore, *parts: str) -> dict:
    return json.loads(store.root.joinpath(*parts).read_text(encoding="utf-8"))


def entries_of(store: case.AffirmationStore, *parts: str) -> list[dict]:
    return document_of(store, *parts)["@graph"]


def local_ids_of(store: case.AffirmationStore) -> set[str]:
    return {entry["seg:localId"] for entry in entries_of(store, "nodes", "requirements.jsonld")}


def files_under(root: Path) -> set[Path]:
    return {path for path in root.rglob("*") if path.is_file()}


def packaged_schema_names() -> list[str]:
    return sorted(source.name for source in (PACKAGED / "schema").iterdir())


def packaged_schema(name: str) -> dict:
    return json.loads((PACKAGED / "schema" / name).read_text(encoding="utf-8"))


def break_the_rename(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interrupt every write at the last possible moment, after the bytes exist."""

    def refuse(source: object, target: object) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr(_atomic.os, "replace", refuse)


# ── Layout and self-description ─────────────────────────────────────────────


def test_a_fresh_write_root_gains_the_layout_it_needs(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.initialize()
    for name in ("nodes", "edges", "events", "proofs", "schema"):
        assert (store.root / name).is_dir(), name


def test_a_fresh_write_root_becomes_self_describing(tmp_path: Path) -> None:
    """A case carries the schemas and the context it is read by, or it is not one."""
    store = make_case(tmp_path)
    store.initialize()
    assert (store.root / "context.jsonld").is_file()
    emitted = sorted(path.name for path in (store.root / "schema").iterdir())
    assert emitted == packaged_schema_names()


def test_the_emitted_schemas_are_the_packaged_schemas_byte_for_byte(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.initialize()
    for name in packaged_schema_names():
        assert (store.root / "schema" / name).read_bytes() == (
            PACKAGED / "schema" / name
        ).read_bytes(), name


def test_re_emitting_the_self_describing_files_leaves_them_untouched(tmp_path: Path) -> None:
    """Nothing a write was not about may change, down to the modification time.

    A case is a commit lineage, and a store that refreshed its own schemas on
    every write would put that churn in front of whoever reviews the diff.
    """
    store = make_case(tmp_path)
    store.initialize()
    before = {path: path.stat().st_mtime_ns for path in files_under(store.root)}
    store.initialize()
    assert {path: path.stat().st_mtime_ns for path in files_under(store.root)} == before


def test_a_schema_the_case_already_carries_is_never_written_over(tmp_path: Path) -> None:
    """The case's copy is the one the auditor reads, so it is the one that governs.

    The packaged copy seeds a case that has none. Replacing a case's schemas
    would be a store act, and the tool takes none unbidden.
    """
    store = make_case(tmp_path)
    store.initialize()
    target = store.root / "schema" / "requirement.schema.json"
    amended = packaged_schema("requirement.schema.json") | {"title": "this case's own wording"}
    target.write_text(json.dumps(amended, indent=2) + "\n", encoding="utf-8")
    store.write_nodes([requirement()])
    assert json.loads(target.read_text(encoding="utf-8"))["title"] == "this case's own wording"


def test_every_declared_kind_has_a_collection_document() -> None:
    """A kind cannot be declared without also being given somewhere to live."""
    assert set(_layout.NODE_DOCUMENTS) == taxonomy.node_kinds()
    assert set(_layout.EDGE_DOCUMENTS) == taxonomy.edge_kinds()
    assert set(_layout.NODE_SCHEMAS) == taxonomy.node_kinds()
    assert set(_layout.EDGE_SCHEMAS) == taxonomy.edge_kinds()


def test_every_packaged_schema_declares_draft_2020_12() -> None:
    for name in packaged_schema_names():
        assert packaged_schema(name)["$schema"] == "https://json-schema.org/draft/2020-12/schema", (
            name
        )


def test_every_packaged_schema_forbids_properties_it_does_not_declare() -> None:
    """The structural half of "no content is persisted".

    A schema that admitted an undeclared property would admit a field carrying
    the very text a digest beside it covers. Composed schemas need the
    unevaluated form, because a plain refusal cannot see through composition.
    """
    used = [*_layout.NODE_SCHEMAS.values(), *_layout.EDGE_SCHEMAS.values(), _layout.EVENT_SCHEMA]
    for name in used:
        schema = packaged_schema(name)
        closed = schema.get("additionalProperties") is False
        composed = schema.get("unevaluatedProperties") is False
        assert closed or composed, name


# ── Documents ───────────────────────────────────────────────────────────────


def test_a_node_is_written_to_the_document_of_its_kind(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (entry,) = entries_of(store, "nodes", "requirements.jsonld")
    assert entry["type"] == "seg:Requirement"
    assert entry["seg:localId"] == "SEG-SREQ-018"


def test_a_node_document_carries_identifiers_kinds_digests_and_their_locations(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (entry,) = entries_of(store, "nodes", "requirements.jsonld")
    assert set(entry) == {"id", "type", "seg:localId", "seg:contentHash", "seg:contentHashSource"}
    assert entry["seg:contentHash"] == digest("a statement").hex()


def test_a_waiver_document_carries_its_expiry_and_approver(tmp_path: Path) -> None:
    """SEG-SREQ-057, SEG-SREQ-058: producer-recorded claims, written beside
    the digest exactly as a test outcome's result is."""
    store = make_case(tmp_path)
    store.write_nodes([waiver(expiry=date(2030, 6, 15), approver="B. Approver")])
    (entry,) = entries_of(store, "nodes", "waivers.jsonld")
    assert entry["seg:expiry"] == "2030-06-15"
    assert entry["seg:approver"] == "B. Approver"
    assert "seg:contentHash" in entry


def test_a_waiver_missing_its_expiry_is_refused_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _documents.node_entry

    def without_expiry(record: records.NodeRecord) -> dict:
        entry = original(record)
        entry.pop("seg:expiry", None)
        return entry

    monkeypatch.setattr(_documents, "node_entry", without_expiry)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:expiry"):
        store.write_nodes([waiver()])


def test_a_waiver_missing_its_approver_is_refused_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _documents.node_entry

    def without_approver(record: records.NodeRecord) -> dict:
        entry = original(record)
        entry.pop("seg:approver", None)
        return entry

    monkeypatch.setattr(_documents, "node_entry", without_approver)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:approver"):
        store.write_nodes([waiver()])


def test_a_test_outcome_document_carries_its_revision(tmp_path: Path) -> None:
    """SEG-SREQ-062: a producer-recorded claim, written beside the digest
    exactly as a waiver's expiry and approver are."""
    store = make_case(tmp_path)
    store.write_nodes([outcome(revision="a1b2c3")])
    (entry,) = entries_of(store, "nodes", "test_outcomes.jsonld")
    assert entry["seg:revision"] == "a1b2c3"
    assert "seg:contentHash" in entry


def test_a_test_outcome_missing_its_revision_is_refused_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _documents.node_entry

    def without_revision(record: records.NodeRecord) -> dict:
        entry = original(record)
        entry.pop("seg:revision", None)
        return entry

    monkeypatch.setattr(_documents, "node_entry", without_revision)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:revision"):
        store.write_nodes([outcome()])


def test_a_node_document_locates_the_content_behind_each_digest(tmp_path: Path) -> None:
    """SEG-SREQ-050: repository, path and span locator, beside every content hash."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (entry,) = entries_of(store, "nodes", "requirements.jsonld")
    assert entry["seg:contentHashSource"] == {
        "seg:sourceRepo": "the-source-repo",
        "seg:sourcePath": "doc/spec/store.rst",
        "seg:sourceLocator": "need:SEG-SREQ-018",
    }


def test_a_split_hash_node_locates_each_hash_separately(tmp_path: Path) -> None:
    """Per hash, not per node: the two spans of one function differ by locator."""
    store = make_case(tmp_path)
    store.write_nodes(
        [
            records.NodeRecord(
                local_id="affirmatrix.graph.build",
                kind="Implementation",
                content_anchors={
                    "apiHash": anchor(
                        "the api",
                        locator="symbol:affirmatrix.graph.build#api",
                        path="src/affirmatrix/graph/__init__.py",
                    ),
                    "bodyHash": anchor(
                        "the body",
                        locator="symbol:affirmatrix.graph.build#body",
                        path="src/affirmatrix/graph/__init__.py",
                    ),
                },
            )
        ]
    )
    (entry,) = entries_of(store, "nodes", "implementations.jsonld")
    assert entry["seg:apiHashSource"]["seg:sourceLocator"] == "symbol:affirmatrix.graph.build#api"
    assert entry["seg:bodyHashSource"]["seg:sourceLocator"] == "symbol:affirmatrix.graph.build#body"


def test_a_document_never_contains_the_content_a_hash_covers(tmp_path: Path) -> None:
    """The direct reading of the requirement: look for the content in the bytes."""
    statement = "the parser locates spans and never feeds a hash"
    store = make_case(tmp_path)
    store.write_nodes([requirement(content=statement)])
    written = (store.root / "nodes" / "requirements.jsonld").read_bytes()
    assert statement.encode("utf-8") not in written


def test_identifiers_in_a_document_are_absolute_iris(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (entry,) = entries_of(store, "nodes", "requirements.jsonld")
    assert entry["id"].startswith("https://")


def test_an_edge_records_its_endpoints_as_identifiers_not_as_a_split_identifier(
    tmp_path: Path,
) -> None:
    """An identifier is an opaque key; the endpoints are fields of their own.

    A reader that recovered the endpoints by splitting the identifier would be
    trusting a separator that either part may itself contain.
    """
    store = make_case(tmp_path)
    store.write_edges([refines()])
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:from"] == identity.node_iri("SEG-SREQ-018")
    assert entry["seg:to"] == identity.node_iri("SEG-SYS-007")


def test_an_instance_document_references_the_context_relative_to_its_own_location(
    tmp_path: Path,
) -> None:
    """A case describes itself offline, and survives being moved as a whole."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    reference = document_of(store, "nodes", "requirements.jsonld")["@context"]
    assert reference == "../context.jsonld"
    assert (store.root / "nodes" / reference).resolve() == (store.root / "context.jsonld")


def test_entries_are_written_in_identifier_order(tmp_path: Path) -> None:
    """The document is a function of what it holds, not of the order it arrived."""
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-023"), requirement("SEG-SREQ-018")])
    identifiers = [entry["id"] for entry in entries_of(store, "nodes", "requirements.jsonld")]
    assert identifiers == sorted(identifiers)


def test_two_identical_writes_produce_byte_identical_documents(tmp_path: Path) -> None:
    """Otherwise every run would show a diff, and a real change would hide in it."""
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018"), requirement("SEG-SREQ-023")])
    first = (store.root / "nodes" / "requirements.jsonld").read_bytes()
    store.write_nodes([requirement("SEG-SREQ-023"), requirement("SEG-SREQ-018")])
    assert (store.root / "nodes" / "requirements.jsonld").read_bytes() == first


def test_a_pending_edge_carries_no_edge_hash(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines()])
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:linkState"] == "pending"
    assert "seg:edgeHash" not in entry


def test_an_active_edge_carries_the_hash_it_was_affirmed_against(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:edgeHash"] == digest("affirmed").hex()


# ── Validation ──────────────────────────────────────────────────────────────


def test_a_node_whose_hash_names_do_not_match_its_kind_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    misnamed = records.NodeRecord(
        local_id="SEG-SREQ-018", kind="Requirement", content_anchors={"apiHash": anchor("x")}
    )
    with pytest.raises(case.AffirmationStoreError, match="SEG-SREQ-018"):
        store.write_nodes([misnamed])


def test_a_locator_outside_the_kinds_pinned_formats_is_refused(tmp_path: Path) -> None:
    """The locator's format is pinned per node kind, and the schema is the pin.

    The record type checks non-empty only — vocabulary stays format-agnostic —
    so a symbol locator on a Requirement must fall to the schema, exactly as it
    would for an auditor validating the document with standard tooling.
    """
    store = make_case(tmp_path)
    mislocated = records.NodeRecord(
        local_id="SEG-SREQ-050",
        kind="Requirement",
        content_anchors={"contentHash": anchor("x", locator="symbol:some.function#api")},
    )
    with pytest.raises(case.AffirmationStoreError, match="seg:contentHashSource"):
        store.write_nodes([mislocated])


def test_a_node_of_an_undeclared_kind_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    unknown = records.NodeRecord(
        local_id="thing", kind="Gizmo", content_anchors={"contentHash": anchor("x")}
    )
    with pytest.raises(case.AffirmationStoreError, match="Gizmo"):
        store.write_nodes([unknown])


def test_an_edge_of_an_undeclared_kind_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    unknown = records.EdgeRecord(
        from_id="a", to_id="b", kind="Resembles", state=records.LinkState.PENDING
    )
    with pytest.raises(case.AffirmationStoreError, match="Resembles"):
        store.write_edges([unknown])


def test_an_active_edge_without_an_edge_hash_is_refused_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The schema is the second guard, and it has to hold on its own.

    The record type refuses this combination first, so the serializer is made
    to produce it here. The point is that an auditor validating the document
    with standard tooling and no knowledge of our types reaches the same
    refusal we do.
    """
    original = _documents.edge_entry

    def without_the_hash(record: records.EdgeRecord) -> dict:
        entry = original(record)
        entry["seg:linkState"] = "active"
        entry.pop("seg:edgeHash", None)
        return entry

    monkeypatch.setattr(_documents, "edge_entry", without_the_hash)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="edge-refines"):
        store.write_edges([refines()])


def test_a_record_carrying_a_field_outside_its_schema_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The field that must never appear is the one holding what a digest covers."""
    original = _documents.node_entry

    def with_the_statement(record: records.NodeRecord) -> dict:
        return original(record) | {"seg:description": "the requirement text itself"}

    monkeypatch.setattr(_documents, "node_entry", with_the_statement)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:description"):
        store.write_nodes([requirement()])


def test_an_edge_carrying_a_field_outside_its_schema_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The edge schemas compose, and composition needs the unevaluated form.

    A plain refusal of undeclared properties cannot see through composition and
    would reject every field the shared definitions contributed, so the closure
    an edge document relies on is a different keyword — and therefore worth its
    own check.
    """
    original = _documents.edge_entry

    def with_a_note(record: records.EdgeRecord) -> dict:
        return original(record) | {"seg:note": "why this edge exists"}

    monkeypatch.setattr(_documents, "edge_entry", with_a_note)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:note"):
        store.write_edges([refines()])


def test_nothing_is_written_when_one_record_in_the_batch_is_refused(tmp_path: Path) -> None:
    """A batch validates before a document is opened, not record by record."""
    store = make_case(tmp_path)
    invalid = records.NodeRecord(
        local_id="SEG-SREQ-023", kind="Requirement", content_anchors={"specHash": anchor("x")}
    )
    with pytest.raises(case.AffirmationStoreError):
        store.write_nodes([requirement(), invalid])
    assert not (store.root / "nodes" / "requirements.jsonld").exists()


def test_a_refusal_names_the_record_and_what_was_wrong_with_it(tmp_path: Path) -> None:
    """A batch is the usual size of a write, so "something was invalid" is no help."""
    store = make_case(tmp_path)
    invalid = records.NodeRecord(
        local_id="SEG-SREQ-023", kind="Requirement", content_anchors={"specHash": anchor("x")}
    )
    with pytest.raises(case.AffirmationStoreError) as caught:
        store.write_nodes([invalid])
    message = str(caught.value)
    assert "SEG-SREQ-023" in message
    assert "requirement.schema.json" in message
    assert "seg:contentHash" in message


def test_a_schema_the_case_carries_but_cannot_be_read_is_refused(tmp_path: Path) -> None:
    """Validating against a smaller set than the case advertises is worse than refusing."""
    store = make_case(tmp_path)
    store.initialize()
    (store.root / "schema" / "requirement.schema.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(case.AffirmationStoreError, match="requirement.schema.json"):
        store.write_nodes([requirement()])


# ── Confinement ─────────────────────────────────────────────────────────────


def test_a_snapshot_identifier_that_climbs_out_of_the_write_root_is_refused(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError):
        store.write_proof_document("..", "design_consistency_proof", {})


def test_an_absolute_snapshot_identifier_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="separator"):
        store.write_proof_document(str(tmp_path / "elsewhere"), "coverage_report", {})


def test_a_snapshot_identifier_with_a_path_separator_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="separator"):
        store.write_proof_document("2026-08-10/nested", "coverage_report", {})


@pytest.mark.parametrize("character", sorted('<>:"|?*') + ["\\", "\x1f"])
def test_a_segment_with_a_character_invalid_on_some_filesystem_is_refused(
    tmp_path: Path, character: str
) -> None:
    """A published case must be checkable out on every supported platform.

    The generator's minting rule (SEG-SREQ-052) is the primary guard; this is
    the store's defense in depth at its one path choke point, so no
    caller-supplied name can put an uncheckoutable file in a case.
    """
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="file name|separator"):
        store.write_proof_document(f"2026{character}08", "coverage_report", {})


def test_a_target_resolving_outside_the_write_root_through_a_symlink_is_refused(
    tmp_path: Path,
) -> None:
    """The case a purely lexical check cannot see.

    Every segment here is well formed; what escapes is the directory they are
    joined onto, which is why resolution and not spelling is the check.
    """
    store = make_case(tmp_path)
    store.initialize()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (store.root / "proofs").rmdir()
    (store.root / "proofs").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(case.AffirmationStoreError, match="outside"):
        store.write_proof_document("2026-08-10", "coverage_report", {})
    assert files_under(elsewhere) == set()


def test_every_file_a_write_creates_lies_under_the_write_root(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    before = files_under(tmp_path)
    store.write_nodes([requirement()])
    store.write_edges([refines()])
    store.append_review_events([review_event()])
    created = files_under(tmp_path) - before
    assert created
    assert all(path.is_relative_to(store.root) for path in created)


# ── Atomicity ───────────────────────────────────────────────────────────────


def test_an_interrupted_write_leaves_the_previous_document_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018")])
    intact = (store.root / "nodes" / "requirements.jsonld").read_bytes()
    break_the_rename(monkeypatch)
    with pytest.raises(OSError):
        store.write_nodes([requirement("SEG-SREQ-023")])
    assert (store.root / "nodes" / "requirements.jsonld").read_bytes() == intact


def test_an_interrupted_write_creates_no_document_in_a_fresh_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    store.initialize()
    break_the_rename(monkeypatch)
    with pytest.raises(OSError):
        store.write_nodes([requirement()])
    assert not (store.root / "nodes" / "requirements.jsonld").exists()


def test_an_interrupted_write_leaves_no_temporary_file_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Including the ones an ordinary listing would not show."""
    store = make_case(tmp_path)
    store.initialize()
    break_the_rename(monkeypatch)
    with pytest.raises(OSError):
        store.write_nodes([requirement()])
    assert files_under(store.root / "nodes") == set()


def test_a_document_is_renamed_into_place_from_its_own_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rename is only atomic within one filesystem.

    A temporary file in the system's scratch directory would degrade the rename
    into a copy, so the directory it is created in is asserted rather than
    assumed.
    """
    seen: list[str] = []
    original = tempfile.mkstemp

    def watched(**arguments: object) -> tuple[int, str]:
        seen.append(str(arguments["dir"]))
        return original(**arguments)

    monkeypatch.setattr(_atomic.tempfile, "mkstemp", watched)
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    assert seen[-1] == str(store.root / "nodes")


# ── Explicit deletion ───────────────────────────────────────────────────────


def test_writing_one_node_leaves_the_others_in_the_document(tmp_path: Path) -> None:
    """The whole document is rewritten, so everything not mentioned is carried."""
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018"), requirement("SEG-SREQ-023")])
    store.write_nodes([requirement("SEG-SREQ-018", content="reworded")])
    assert local_ids_of(store) == {"SEG-SREQ-018", "SEG-SREQ-023"}


def test_writing_one_kind_leaves_the_other_documents_untouched(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    before = (store.root / "nodes" / "requirements.jsonld").stat().st_mtime_ns
    store.write_edges([refines()])
    assert (store.root / "nodes" / "requirements.jsonld").stat().st_mtime_ns == before


def test_a_removal_drops_only_the_records_it_names(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018"), requirement("SEG-SREQ-023")])
    store.remove_nodes("Requirement", ["SEG-SREQ-018"])
    assert local_ids_of(store) == {"SEG-SREQ-023"}


def test_removing_a_record_that_is_not_persisted_is_refused(tmp_path: Path) -> None:
    """Retired and never written are different, and somebody is relying on which."""
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018")])
    with pytest.raises(case.AffirmationStoreError, match="SEG-SREQ-023"):
        store.remove_nodes("Requirement", ["SEG-SREQ-023"])


def test_a_document_survives_the_removal_of_its_last_record(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines()])
    store.remove_edges("Refines", [("SEG-SREQ-018", "SEG-SYS-007")])
    assert entries_of(store, "edges", "refines.jsonld") == []


def test_a_malformed_existing_document_is_refused_rather_than_overwritten(
    tmp_path: Path,
) -> None:
    """Replacing it would be the silent removal that explicit deletion rules out."""
    store = make_case(tmp_path)
    store.initialize()
    damaged = store.root / "nodes" / "requirements.jsonld"
    damaged.write_text('{"@graph": "not a list"}\n', encoding="utf-8")
    with pytest.raises(case.AffirmationStoreError, match="requirements.jsonld"):
        store.write_nodes([requirement()])
    assert damaged.read_text(encoding="utf-8") == '{"@graph": "not a list"}\n'


# ── Affirmations ────────────────────────────────────────────────────────────


def test_appending_a_review_event_preserves_the_events_already_recorded(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    store.append_review_events([review_event(reason="the first")])
    store.append_review_events([review_event(reason="the second")])
    reasons = [entry["seg:reason"] for entry in entries_of(store, "events", "review_events.jsonld")]
    assert reasons == ["the first", "the second"]


def test_each_appended_review_event_gets_the_next_identifier(tmp_path: Path) -> None:
    """Events are only ever appended, so position is identity."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(), review_event()])
    store.append_review_events([review_event()])
    identifiers = [entry["id"] for entry in entries_of(store, "events", "review_events.jsonld")]
    assert identifiers == [identity.review_event_iri(ordinal) for ordinal in (1, 2, 3)]


def test_an_affirmed_edge_keeps_its_state_when_another_edge_is_written(
    tmp_path: Path,
) -> None:
    """The hazard this guards: a producer's stream is pending by construction."""
    store = make_case(tmp_path)
    affirmed = refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))
    store.write_edges([affirmed])
    store.write_edges([refines(from_id="SEG-SREQ-023")])
    states = {
        entry["seg:from"]: entry["seg:linkState"]
        for entry in entries_of(store, "edges", "refines.jsonld")
    }
    assert states[identity.node_iri("SEG-SREQ-018")] == "active"


def test_an_affirmed_edge_keeps_its_state_when_a_node_document_is_written(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    before = (store.root / "edges" / "refines.jsonld").read_bytes()
    store.write_nodes([requirement()])
    assert (store.root / "edges" / "refines.jsonld").read_bytes() == before


def test_a_review_event_records_the_source_revision_of_each_endpoint(tmp_path: Path) -> None:
    """Nothing else correlates a revision to the moment somebody accepted it."""
    store = make_case(tmp_path)
    store.append_review_events([review_event()])
    (entry,) = entries_of(store, "events", "review_events.jsonld")
    assert entry["seg:affirmedAt"] == {
        "seg:fromRevision": REVISION,
        "seg:toRevision": LATER_REVISION,
    }


def test_a_review_event_records_each_endpoints_named_content_hashes(tmp_path: Path) -> None:
    """SEG-SREQ-127: every named content hash an endpoint carried, paired with
    its anchor, nested per endpoint the same way a node record's own entry
    pairs a digest with its source location."""
    store = make_case(tmp_path)
    event = review_event()
    store.append_review_events([event])
    (entry,) = entries_of(store, "events", "review_events.jsonld")
    assert entry["seg:fromContentAnchors"] == {
        "seg:contentHash": records.hex_digest(digest("SEG-SREQ-018 content")),
        "seg:contentHashSource": {
            "seg:sourceRepo": "the-source-repo",
            "seg:sourcePath": "doc/spec/store.rst",
            "seg:sourceLocator": "file",
        },
    }
    assert entry["seg:toContentAnchors"]["seg:contentHash"] == records.hex_digest(
        digest("SEG-SYS-007 content")
    )


def test_a_field_declared_to_hold_an_identifier_only_ever_holds_one(tmp_path: Path) -> None:
    """A term is defined once for a whole document, however deeply it is nested.

    A field the context declares as holding an identifier will be read as one
    wherever it appears — so reusing such a name for something that is not an
    identifier, a revision inside a nested object say, would have a reader
    resolve that value against the context's base and arrive somewhere.
    """
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    store.write_edges([refines()])
    store.append_review_events([review_event()])
    declarations = json.loads((store.root / "context.jsonld").read_text(encoding="utf-8"))
    coerced = {
        term
        for term, definition in declarations["@context"].items()
        if isinstance(definition, dict) and definition.get("@type") == "@id"
    }
    assert coerced, "the context declares no identifier-valued terms, so this proves nothing"
    instances = (path for path in store.root.rglob("*.jsonld") if path.name != "context.jsonld")
    for document in sorted(instances):
        for term, value in _fields_of(json.loads(document.read_text(encoding="utf-8"))):
            if term in coerced:
                assert str(value).startswith("https://"), f"{document.name}: {term} = {value!r}"


def _fields_of(node: object) -> Iterable[tuple[str, object]]:
    """Every key and value in a document, however deeply nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _fields_of(value)
    elif isinstance(node, list):
        for item in node:
            yield from _fields_of(item)


def test_a_review_event_with_an_empty_reason_is_persisted_as_given(tmp_path: Path) -> None:
    """A thin justification is the operator's to give and a reader's to judge."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(reason="")])
    (entry,) = entries_of(store, "events", "review_events.jsonld")
    assert entry["seg:reason"] == ""


def test_a_review_event_records_the_role_it_was_made_in(tmp_path: Path) -> None:
    """SEG-SREQ-049, as persistence sees it: the role travels with the judgement."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(role="TestEngineer")])
    (entry,) = entries_of(store, "events", "review_events.jsonld")
    assert entry["seg:affirmingRole"] == "TestEngineer"


def test_a_role_outside_the_documented_convention_is_still_writable(tmp_path: Path) -> None:
    """No enum, no closed vocabulary: role validation is a process concern."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(role="acting deputy reviewer (annex F)")])
    (entry,) = entries_of(store, "events", "review_events.jsonld")
    assert entry["seg:affirmingRole"] == "acting deputy reviewer (annex F)"


def test_an_event_without_a_role_is_refused_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The schema guard has to hold on its own, for the auditor with only the case."""
    original = _documents.event_entry

    def without_the_role(event: records.ReviewEvent, ordinal: int) -> dict:
        entry = original(event, ordinal)
        entry.pop("seg:affirmingRole", None)
        return entry

    monkeypatch.setattr(_documents, "event_entry", without_the_role)
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="seg:affirmingRole"):
        store.append_review_events([review_event()])


# ── Affirmed standing is never lost by omission (SEG-SREQ-051) ──────────────


def demotion(
    from_id: str = "SEG-SREQ-018", to_id: str = "SEG-SYS-007", kind: str = "Refines"
) -> records.EdgeReference:
    return records.EdgeReference(kind=kind, from_id=from_id, to_id=to_id)


def test_replacing_an_affirmed_edge_with_an_unaffirmed_record_is_refused(
    tmp_path: Path,
) -> None:
    """The record stream is never itself the request — a current stream, every
    edge pending, must not be able to reset what the case says was affirmed."""
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    with pytest.raises(case.DemotionNotRequestedError, match="SEG-SREQ-018"):
        store.write_edges([refines()])


def test_a_refused_demotion_writes_nothing(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    before = (store.root / "edges" / "refines.jsonld").read_bytes()
    with pytest.raises(case.DemotionNotRequestedError):
        store.write_edges([refines()])
    assert (store.root / "edges" / "refines.jsonld").read_bytes() == before


def test_a_demotion_named_per_edge_is_allowed(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    store.write_edges([refines()], demote={demotion()})
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:linkState"] == "pending"
    assert "seg:edgeHash" not in entry


def test_only_the_named_edge_may_be_demoted(tmp_path: Path) -> None:
    """Naming is per-edge, not per-write: one name does not license a batch."""
    store = make_case(tmp_path)
    store.write_edges(
        [
            refines(state=records.LinkState.ACTIVE, edge_hash=digest("first")),
            refines(
                from_id="SEG-SREQ-023",
                state=records.LinkState.ACTIVE,
                edge_hash=digest("second"),
            ),
        ]
    )
    before = (store.root / "edges" / "refines.jsonld").read_bytes()
    with pytest.raises(case.DemotionNotRequestedError, match="SEG-SREQ-023"):
        store.write_edges(
            [refines(), refines(from_id="SEG-SREQ-023")],
            demote={demotion()},
        )
    assert (store.root / "edges" / "refines.jsonld").read_bytes() == before


def test_a_demotion_refusal_names_every_edge_it_refuses(tmp_path: Path) -> None:
    """One refusal is one complete diagnosis, as removal and validation already do."""
    store = make_case(tmp_path)
    store.write_edges(
        [
            refines(state=records.LinkState.ACTIVE, edge_hash=digest("first")),
            refines(
                from_id="SEG-SREQ-023",
                state=records.LinkState.ACTIVE,
                edge_hash=digest("second"),
            ),
        ]
    )
    with pytest.raises(case.DemotionNotRequestedError) as caught:
        store.write_edges([refines(), refines(from_id="SEG-SREQ-023")])
    message = str(caught.value)
    assert "SEG-SREQ-018" in message
    assert "SEG-SREQ-023" in message


def test_a_demotion_request_that_demotes_nothing_is_refused(tmp_path: Path) -> None:
    """An unused name is a request that did nothing, silently — refused on the
    same grounds removal refuses a record the case never held."""
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    with pytest.raises(case.DemotionNotRequestedError, match="does not demote"):
        store.write_edges(
            [refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))],
            demote={demotion()},
        )


def test_replacing_an_affirmed_hash_with_a_different_hash_is_not_a_demotion(
    tmp_path: Path,
) -> None:
    """SEG-SREQ-051 guards the loss of affirmed standing, not its movement."""
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("first"))])
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("second"))])
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:edgeHash"] == digest("second").hex()


def test_a_state_change_that_keeps_the_hash_is_not_a_demotion(tmp_path: Path) -> None:
    """Drift detection marks an edge outdated while keeping what it was affirmed
    against; the guard must not stand in the detector's way."""
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    store.write_edges(
        [refines(state=records.LinkState.DIRECTLY_OUTDATED, edge_hash=digest("affirmed"))]
    )
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:linkState"] == "directlyOutdated"


def test_a_first_write_of_a_pending_edge_needs_no_demotion(tmp_path: Path) -> None:
    """No incumbent, no affirmed standing to lose."""
    store = make_case(tmp_path)
    store.write_edges([refines()])
    (entry,) = entries_of(store, "edges", "refines.jsonld")
    assert entry["seg:linkState"] == "pending"


def test_the_demotion_error_is_an_affirmation_store_error(tmp_path: Path) -> None:
    """Callers that catch the store's one refusal type keep catching it."""
    assert issubclass(case.DemotionNotRequestedError, case.AffirmationStoreError)


# ── The proofs path ─────────────────────────────────────────────────────────


TOY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://affirmatrix.dev/case/schema/toy.schema.json",
    "type": "object",
    "required": ["seg:snapshotId"],
    "additionalProperties": False,
    "properties": {"seg:snapshotId": {"type": "string"}},
}


def register_toy_document(store: case.AffirmationStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the evidence-package documents, which arrive with their generator."""
    store.initialize()
    (store.root / "schema" / "toy.schema.json").write_text(
        json.dumps(TOY_SCHEMA, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        _layout, "PROOF_DOCUMENT_SCHEMAS", MappingProxyType({"toy": "toy.schema.json"})
    )


def test_a_proof_document_lands_under_its_snapshot_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    snapshot = "2026-08-10T09-00-00Z-a1b2c3"
    written = store.write_proof_document(snapshot, "toy", {"seg:snapshotId": "s"})
    assert written == store.root / "proofs" / snapshot / "toy.jsonld"
    assert json.loads(written.read_text(encoding="utf-8")) == {
        "@context": "../../context.jsonld",
        "seg:snapshotId": "s",
    }


def test_a_proof_document_kind_with_no_registered_schema_is_refused(tmp_path: Path) -> None:
    """A document with no schema cannot be shown to be valid, so it is not written.

    ``design_consistency_proof`` stood in for an unregistered kind before the
    evidence-package generator landed and registered it for real; the
    placeholder here is a name that is never registered.
    """
    store = make_case(tmp_path)
    with pytest.raises(case.AffirmationStoreError, match="no schema is registered"):
        store.write_proof_document("2026-08-10", "not-a-registered-kind", {})
    assert files_under(store.root / "proofs") == set()


def test_a_proof_document_that_does_not_validate_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    with pytest.raises(case.AffirmationStoreError, match="toy"):
        store.write_proof_document("2026-08-10", "toy", {"seg:elsewhere": "s"})
    assert files_under(store.root / "proofs") == set()


def test_a_proof_document_is_written_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    break_the_rename(monkeypatch)
    with pytest.raises(OSError):
        store.write_proof_document("2026-08-10", "toy", {"seg:snapshotId": "s"})
    assert files_under(store.root / "proofs") == set()


# ── The proof document read face (SEG-SREQ-020 over proofs) ────────────────


def test_a_written_proof_document_reads_back_equal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    snapshot = "2026-08-10T09-00-00Z-a1b2c3"
    store.write_proof_document(snapshot, "toy", {"seg:snapshotId": "s"})
    assert store.read_proof_document(snapshot, "toy") == {"seg:snapshotId": "s"}


def test_reading_a_proof_document_kind_with_no_registered_schema_is_refused(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    store.initialize()
    with pytest.raises(case.AffirmationStoreError, match="no schema is registered"):
        store.read_proof_document("2026-08-10", "not-a-registered-kind")


def test_reading_a_proof_document_that_does_not_exist_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    with pytest.raises(case.AffirmationStoreError):
        store.read_proof_document("2026-08-10", "toy")


def test_a_hand_edited_proof_document_missing_its_context_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    snapshot = "2026-08-10T09-00-00Z-a1b2c3"
    store.write_proof_document(snapshot, "toy", {"seg:snapshotId": "s"})
    path = store.root / "proofs" / snapshot / "toy.jsonld"
    path.write_text(json.dumps({"seg:snapshotId": "s"}) + "\n", encoding="utf-8")
    with pytest.raises(case.AffirmationStoreError, match="@context"):
        store.read_proof_document(snapshot, "toy")


def test_reading_a_package_returns_every_document_keyed_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    snapshot = "2026-08-10T09-00-00Z-a1b2c3"
    store.write_proof_document(snapshot, "toy", {"seg:snapshotId": "s"})
    assert dict(store.read_package(snapshot)) == {"toy": {"seg:snapshotId": "s"}}


def test_reading_a_package_missing_one_document_refuses_the_whole_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_case(tmp_path)
    register_toy_document(store, monkeypatch)
    with pytest.raises(case.AffirmationStoreError):
        store.read_package("2026-08-10")


# ── Identifier minting ──────────────────────────────────────────────────────


def test_a_node_identifier_is_minted_from_the_local_identifier_alone(tmp_path: Path) -> None:
    """It cannot carry the kind: an edge knows its endpoints, not their kinds.

    A broken edge's endpoint is by definition no longer in the graph to be
    asked, and such an edge still has to be persistable.
    """
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (entry,) = entries_of(store, "nodes", "requirements.jsonld")
    assert entry["id"] == f"{identity.BASE}/node/SEG-SREQ-018"


def test_an_identifier_is_a_valid_iri_for_a_dotted_implementation_path() -> None:
    """And for an outcome identity, which carries a separator of its own."""
    assert identity.node_iri("affirmatrix.case._atomic.replace_file").endswith(
        "affirmatrix.case._atomic.replace_file"
    )
    assert "/" not in identity.node_iri("run-0001/SEG-TS-001").removeprefix(
        f"{identity.BASE}/node/"
    )


def test_two_edges_never_mint_one_identifier(tmp_path: Path) -> None:
    """A document is keyed by identifier, so a collision loses a record.

    The endpoints most likely to collide are the ones containing whatever
    character joins them, which is why the joining character is one that
    encoding always removes from a segment.
    """
    first = identity.edge_iri("Refines", "a/b", "c")
    second = identity.edge_iri("Refines", "a", "b/c")
    assert first != second
    store = make_case(tmp_path)
    store.write_edges([refines("a/b", "c"), refines("a", "b/c")])
    assert len(entries_of(store, "edges", "refines.jsonld")) == 2


# ── The store is the only writer ────────────────────────────────────────────


def test_a_store_reads_and_writes_nothing_when_it_is_constructed(tmp_path: Path) -> None:
    """The ordinary case is a root that does not exist yet; creating it is the job."""
    root = tmp_path / "case"
    case.AffirmationStore(root=root)
    assert not root.exists()


def test_two_stores_over_one_root_see_the_same_case(tmp_path: Path) -> None:
    """Nothing is held in memory between writes, so the case on disk is the case."""
    root = tmp_path / "case"
    case.AffirmationStore(root=root).write_nodes([requirement("SEG-SREQ-018")])
    case.AffirmationStore(root=root).write_nodes([requirement("SEG-SREQ-023")])
    entries: Iterable[dict] = json.loads(
        (root / "nodes" / "requirements.jsonld").read_text(encoding="utf-8")
    )["@graph"]
    assert {entry["seg:localId"] for entry in entries} == {"SEG-SREQ-018", "SEG-SREQ-023"}


def test_the_write_root_is_a_parameter_and_never_a_default() -> None:
    """Relocating the whole store is passing a different path, and nothing else."""
    with pytest.raises(TypeError):
        case.AffirmationStore()  # type: ignore[call-arg]
