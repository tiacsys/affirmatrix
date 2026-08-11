"""The affirmation store's read face — a case presented as a record source.

The claim under test is SEG-SREQ-020: each record the store has written comes
back unchanged when it is read back. Equality here is record equality — the
reconstructed ``NodeRecord``, ``EdgeRecord`` or ``ReviewEvent`` equals the one
that was written — because that is what re-enters the engine; byte identity of
the documents is the write face's determinism and is tested with it.

The refusals matter as much as the round-trip. A recorded stream that quietly
came back short would tell drift detection that an affirmation never happened,
so an unreadable case raises and is never answered with an empty or partial
stream. The one deliberate asymmetry with the write face is stated rather than
smoothed: write creates a case that is not there, read refuses one — a missing
root is an ordinary place to start writing, but it is no place to read a
recorded stream from.

Every test builds its case under ``tmp_path``. The repository's own case is a
separate commit lineage that a maintainer operates; nothing here may touch it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from affirmatrix import case, identity, records

REVISION = "a1b2c3d4" * 5
LATER_REVISION = "f0e1d2c3" * 5


def digest(text: str) -> bytes:
    """A digest an auditor could reproduce with ``sha256sum``."""
    return hashlib.sha256(text.encode("utf-8")).digest()


def make_case(tmp_path: Path) -> case.AffirmationStore:
    return case.AffirmationStore(root=tmp_path / "case")


def anchor(content: str, locator: str = "file", path: str = "a/file.txt") -> records.ContentAnchor:
    return records.ContentAnchor(
        digest=digest(content), repository="the-source-repo", path=path, locator=locator
    )


def requirement(local_id: str = "SEG-SREQ-020", content: str = "a statement") -> records.NodeRecord:
    return records.NodeRecord(
        local_id=local_id,
        kind="Requirement",
        content_anchors={"contentHash": anchor(content, locator=f"need:{local_id}")},
    )


def one_node_of_every_kind() -> list[records.NodeRecord]:
    """One node per declared kind, split-hash kinds and every locator scheme included."""
    return [
        requirement(),
        records.NodeRecord(
            local_id="affirmatrix.case._atomic.replace_file",
            kind="Implementation",
            content_anchors={
                "apiHash": anchor(
                    "the api", locator="symbol:affirmatrix.case._atomic.replace_file#api"
                ),
                "bodyHash": anchor(
                    "the body", locator="symbol:affirmatrix.case._atomic.replace_file#body"
                ),
            },
        ),
        records.NodeRecord(
            local_id="SEG-TS-001",
            kind="TestSpecification",
            content_anchors={
                "specHash": anchor("the spec", locator="symbol:tests.test_store#spec"),
                "implHash": anchor("the test body", locator="symbol:tests.test_store#impl"),
            },
        ),
        records.NodeRecord(
            local_id="run-0001/SEG-TS-001",
            kind="TestOutcome",
            content_anchors={
                "contentHash": anchor("passed", locator="nodeid:tests/test_store.py::test_it")
            },
        ),
        records.NodeRecord(
            local_id="WVR-001", kind="Waiver", content_anchors={"contentHash": anchor("waived")}
        ),
    ]


EDGE_KINDS = ("Refines", "Verifies", "Implements", "Confirms", "Witnesses", "Excuses", "Calls")


def one_edge_of_every_kind() -> list[records.EdgeRecord]:
    """One pending edge per declared kind."""
    return [
        records.EdgeRecord(
            from_id=f"from-{kind.lower()}",
            to_id=f"to-{kind.lower()}",
            kind=kind,
            state=records.LinkState.PENDING,
        )
        for kind in EDGE_KINDS
    ]


def refines(
    from_id: str = "SEG-SREQ-020",
    to_id: str = "SEG-SYS-007",
    state: records.LinkState = records.LinkState.PENDING,
    edge_hash: bytes | None = None,
) -> records.EdgeRecord:
    return records.EdgeRecord(
        from_id=from_id, to_id=to_id, kind="Refines", state=state, edge_hash=edge_hash
    )


def review_event(
    reason: str = "reviewed together", role: str = "RequirementsEngineer"
) -> records.ReviewEvent:
    return records.ReviewEvent(
        from_id="SEG-SREQ-020",
        to_id="SEG-SYS-007",
        kind="Refines",
        from_node_hash=digest("SEG-SREQ-020"),
        to_node_hash=digest("SEG-SYS-007"),
        from_source_revision=REVISION,
        to_source_revision=LATER_REVISION,
        role=role,
        reason=reason,
    )


def by_identity(nodes: list[records.NodeRecord]) -> list[records.NodeRecord]:
    return sorted(nodes, key=lambda record: (record.kind, record.local_id))


def edit_entry(store: case.AffirmationStore, *parts: str, **changes: object) -> None:
    """Hand-edit the one entry of a document, the way no code path would."""
    document = store.root.joinpath(*parts)
    payload = json.loads(document.read_text(encoding="utf-8"))
    (entry,) = payload["@graph"]
    for field, value in changes.items():
        if value is None:
            entry.pop(field, None)
        else:
            entry[field] = value
    document.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def files_and_mtimes(root: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in root.rglob("*") if path.is_file()}


# ── Round-trip (SEG-SREQ-020) ───────────────────────────────────────────────


def test_every_node_kind_reads_back_as_it_was_written(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    written = one_node_of_every_kind()
    store.write_nodes(written)
    assert by_identity(list(store.nodes())) == by_identity(written)


def test_every_edge_kind_reads_back_as_it_was_written(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    written = one_edge_of_every_kind()
    store.write_edges(written)
    assert set(store.edges()) == set(written)


def test_a_multi_hash_node_reads_back_with_every_named_digest(tmp_path: Path) -> None:
    """The two digests separate intent from execution; losing one merges them."""
    store = make_case(tmp_path)
    store.write_nodes(
        [
            records.NodeRecord(
                local_id="affirmatrix.graph.build",
                kind="Implementation",
                content_anchors={
                    "apiHash": anchor("the api", locator="symbol:affirmatrix.graph.build#api"),
                    "bodyHash": anchor("the body", locator="symbol:affirmatrix.graph.build#body"),
                },
            )
        ]
    )
    (read,) = store.nodes()
    assert dict(read.content_hashes) == {
        "apiHash": digest("the api"),
        "bodyHash": digest("the body"),
    }


def test_a_node_reads_back_with_the_location_of_every_hash(tmp_path: Path) -> None:
    """SEG-SREQ-050 composed with SEG-SREQ-020: the location survives the trip."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (read,) = store.nodes()
    assert read.content_anchors["contentHash"] == anchor(
        "a statement", locator="need:SEG-SREQ-020"
    )


def test_a_review_event_reads_back_with_its_role(tmp_path: Path) -> None:
    """SEG-SREQ-049's record half: the role is data, reproduced as written."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(role="acting deputy reviewer (annex F)")])
    (read,) = store.review_events()
    assert read.role == "acting deputy reviewer (annex F)"


def test_a_pending_edge_reads_back_with_no_edge_hash(tmp_path: Path) -> None:
    """Absent stays absent: a placeholder would read as a hash that mismatches."""
    store = make_case(tmp_path)
    store.write_edges([refines()])
    (read,) = store.edges()
    assert read.state is records.LinkState.PENDING
    assert read.edge_hash is None


def test_an_affirmed_edge_reads_back_with_the_hash_it_was_affirmed_against(
    tmp_path: Path,
) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines(state=records.LinkState.ACTIVE, edge_hash=digest("affirmed"))])
    (read,) = store.edges()
    assert read.state is records.LinkState.ACTIVE
    assert read.edge_hash == digest("affirmed")


def test_review_events_read_back_as_written_and_in_recorded_order(tmp_path: Path) -> None:
    """Each record it has written includes the ones whose loss is least recoverable."""
    store = make_case(tmp_path)
    store.append_review_events([review_event(reason="the first"), review_event(reason="")])
    store.append_review_events([review_event(reason="the third")])
    assert list(store.review_events()) == [
        review_event(reason="the first"),
        review_event(reason=""),
        review_event(reason="the third"),
    ]


def test_identifiers_read_back_case_local(tmp_path: Path) -> None:
    """Read-back is where minting is undone (ADR-0007), including the encoding."""
    store = make_case(tmp_path)
    store.write_nodes(one_node_of_every_kind())
    store.write_edges([refines(from_id="run-0001/SEG-TS-001", to_id="a.dotted.path")])
    read_ids = {node.local_id for node in store.nodes()}
    assert "run-0001/SEG-TS-001" in read_ids
    assert "affirmatrix.case._atomic.replace_file" in read_ids
    (edge,) = store.edges()
    assert (edge.from_id, edge.to_id) == ("run-0001/SEG-TS-001", "a.dotted.path")
    for value in (*read_ids, edge.from_id, edge.to_id):
        assert not value.startswith("https://")


def test_reading_then_writing_back_leaves_every_document_byte_identical(
    tmp_path: Path,
) -> None:
    """Round-trip composed with the write face's determinism: a fixpoint."""
    store = make_case(tmp_path)
    store.write_nodes(one_node_of_every_kind())
    store.write_edges(one_edge_of_every_kind())
    before = {path: path.read_bytes() for path in store.root.rglob("*.jsonld")}
    store.write_nodes(list(store.nodes()))
    store.write_edges(list(store.edges()))
    assert {path: path.read_bytes() for path in store.root.rglob("*.jsonld")} == before


def test_a_record_written_between_two_reads_appears_in_the_second(tmp_path: Path) -> None:
    """Reads on demand, keeps nothing: the case on disk is the case."""
    store = make_case(tmp_path)
    store.write_nodes([requirement("SEG-SREQ-018")])
    first = list(store.nodes())
    store.write_nodes([requirement("SEG-SREQ-023")])
    second = list(store.nodes())
    assert len(first) == 1
    assert {node.local_id for node in second} == {"SEG-SREQ-018", "SEG-SREQ-023"}


def test_two_reads_yield_the_same_sequence(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes(one_node_of_every_kind())
    store.write_edges(one_edge_of_every_kind())
    assert list(store.nodes()) == list(store.nodes())
    assert list(store.edges()) == list(store.edges())


# ── The record-source protocol ──────────────────────────────────────────────


def test_the_store_satisfies_the_record_source_protocol(tmp_path: Path) -> None:
    """Structural, not inherited: having the two methods is being a source."""
    assert isinstance(make_case(tmp_path), records.RecordSource)


def test_reading_writes_nothing(tmp_path: Path) -> None:
    """A read that seeded or refreshed anything would be a store act unbidden."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    store.write_edges([refines()])
    store.append_review_events([review_event()])
    before = files_and_mtimes(store.root)
    list(store.nodes())
    list(store.edges())
    list(store.review_events())
    assert files_and_mtimes(store.root) == before


def test_reading_a_fresh_initialized_case_writes_nothing(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.initialize()
    before = files_and_mtimes(store.root)
    assert list(store.nodes()) == []
    assert list(store.edges()) == []
    assert list(store.review_events()) == []
    assert files_and_mtimes(store.root) == before


# ── An absent case is refused; an empty one is empty ───────────────────────


def test_an_absent_root_is_refused_rather_than_read_as_empty(tmp_path: Path) -> None:
    """An empty recorded stream says nothing was ever affirmed — silently wrong.

    A mistyped path caught here is a message about a path; caught nowhere it is
    drift detection discarding every affirmation the real case holds.
    """
    store = case.AffirmationStore(root=tmp_path / "no-such-case")
    for read in (store.nodes, store.edges, store.review_events):
        with pytest.raises(case.AffirmationStoreError, match="no-such-case"):
            read()


def test_a_directory_that_is_not_self_describing_is_refused(tmp_path: Path) -> None:
    """Write creates, read refuses: an empty directory is not a case yet."""
    root = tmp_path / "case"
    root.mkdir()
    store = case.AffirmationStore(root=root)
    with pytest.raises(case.AffirmationStoreError, match="self-describ"):
        store.nodes()


def test_an_initialized_empty_case_reads_as_empty_streams(tmp_path: Path) -> None:
    """A kind nothing has produced has no document, and that is zero records."""
    store = make_case(tmp_path)
    store.initialize()
    assert list(store.nodes()) == []
    assert list(store.edges()) == []
    assert list(store.review_events()) == []


# ── An unreadable case raises, never a short stream ────────────────────────


def test_a_malformed_document_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.initialize()
    (store.root / "nodes" / "requirements.jsonld").write_text("{ not json", encoding="utf-8")
    with pytest.raises(case.AffirmationStoreError, match="requirements.jsonld"):
        list(store.nodes())


def test_a_document_without_a_graph_of_entries_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.initialize()
    (store.root / "edges" / "refines.jsonld").write_text(
        '{"@graph": "not a list"}\n', encoding="utf-8"
    )
    with pytest.raises(case.AffirmationStoreError, match="refines.jsonld"):
        list(store.edges())


def test_an_uppercase_digest_is_refused_not_folded(tmp_path: Path) -> None:
    """Two spellings of one digest would be two serializations of one record."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    folded = digest("a statement").hex().upper()
    edit_entry(store, "nodes", "requirements.jsonld", **{"seg:contentHash": folded})
    with pytest.raises(case.AffirmationStoreError):
        list(store.nodes())


def test_an_entry_carrying_an_undeclared_field_is_refused_on_read_back(tmp_path: Path) -> None:
    """Validation applies on read-back too: the store reads only what a case may hold."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(store, "nodes", "requirements.jsonld", **{"seg:description": "the text itself"})
    with pytest.raises(case.AffirmationStoreError, match="seg:description"):
        list(store.nodes())


def test_a_hash_without_its_source_location_is_refused_on_read_back(tmp_path: Path) -> None:
    """A digest that no longer says where its content lives has lost half its record."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(store, "nodes", "requirements.jsonld", **{"seg:contentHashSource": None})
    with pytest.raises(case.AffirmationStoreError, match="seg:contentHashSource"):
        list(store.nodes())


def test_a_source_location_missing_a_member_is_refused_on_read_back(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(
        store,
        "nodes",
        "requirements.jsonld",
        **{
            "seg:contentHashSource": {
                "seg:sourceRepo": "the-source-repo",
                "seg:sourcePath": "a/file.txt",
            }
        },
    )
    with pytest.raises(case.AffirmationStoreError, match="seg:sourceLocator"):
        list(store.nodes())


def test_a_source_location_with_an_undeclared_member_is_refused_on_read_back(
    tmp_path: Path,
) -> None:
    """The nested object is as closed as the entry around it."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(
        store,
        "nodes",
        "requirements.jsonld",
        **{
            "seg:contentHashSource": {
                "seg:sourceRepo": "the-source-repo",
                "seg:sourcePath": "a/file.txt",
                "seg:sourceLocator": "need:SEG-SREQ-020",
                "seg:sourceBranch": "main",
            }
        },
    )
    with pytest.raises(case.AffirmationStoreError, match="seg:sourceBranch"):
        list(store.nodes())


def test_a_locator_of_a_scheme_the_kind_does_not_pin_is_refused_on_read_back(
    tmp_path: Path,
) -> None:
    """The pin holds for the auditor's tooling and for ours alike."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(
        store,
        "nodes",
        "requirements.jsonld",
        **{
            "seg:contentHashSource": {
                "seg:sourceRepo": "the-source-repo",
                "seg:sourcePath": "a/file.txt",
                "seg:sourceLocator": "symbol:some.function#api",
            }
        },
    )
    with pytest.raises(case.AffirmationStoreError, match="seg:sourceLocator"):
        list(store.nodes())


def test_an_empty_role_is_refused_on_read_back(tmp_path: Path) -> None:
    """An empty role satisfies the field while recording nothing; the schema refuses it."""
    store = make_case(tmp_path)
    store.append_review_events([review_event()])
    edit_entry(store, "events", "review_events.jsonld", **{"seg:affirmingRole": ""})
    with pytest.raises(case.AffirmationStoreError, match="seg:affirmingRole"):
        list(store.review_events())


def test_a_pending_edge_carrying_a_hash_is_refused_on_read_back(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines()])
    edit_entry(store, "edges", "refines.jsonld", **{"seg:edgeHash": digest("planted").hex()})
    with pytest.raises(case.AffirmationStoreError):
        list(store.edges())


def test_a_node_whose_identifier_disagrees_with_its_local_identifier_is_refused(
    tmp_path: Path,
) -> None:
    """Two spellings of one identity must agree, or the record would move on rewrite."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(store, "nodes", "requirements.jsonld", **{"seg:localId": "SEG-SREQ-999"})
    with pytest.raises(case.AffirmationStoreError, match="SEG-SREQ-999"):
        list(store.nodes())


def test_an_edge_endpoint_outside_the_node_identifier_space_is_refused(tmp_path: Path) -> None:
    store = make_case(tmp_path)
    store.write_edges([refines()])
    edit_entry(store, "edges", "refines.jsonld", **{"seg:from": "https://example.org/elsewhere"})
    with pytest.raises(case.AffirmationStoreError, match="elsewhere"):
        list(store.edges())


def test_a_case_schema_that_cannot_be_read_refuses_the_read(tmp_path: Path) -> None:
    """Reading against a smaller schema set than the case advertises is worse."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    (store.root / "schema" / "requirement.schema.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(case.AffirmationStoreError, match="requirement.schema.json"):
        list(store.nodes())


def test_a_read_refusal_names_the_document_and_the_entry(tmp_path: Path) -> None:
    """The reader's next step is opening the file, so the message must name it."""
    store = make_case(tmp_path)
    store.write_nodes([requirement()])
    edit_entry(store, "nodes", "requirements.jsonld", **{"seg:description": "planted"})
    with pytest.raises(case.AffirmationStoreError) as caught:
        list(store.nodes())
    message = str(caught.value)
    assert "requirements.jsonld" in message
    assert identity.node_iri("SEG-SREQ-020") in message


# ── The node-identifier inverse ─────────────────────────────────────────────


def test_the_node_identifier_inverse_returns_what_was_minted() -> None:
    """The inverse exists for exactly one IRI space, and is total on it."""
    local_ids = ("SEG-SREQ-020", "run-0001/SEG-TS-001", "affirmatrix.case._atomic.replace_file")
    for local_id in local_ids:
        assert identity.node_local_id(identity.node_iri(local_id)) == local_id


def test_an_identifier_outside_the_node_space_is_refused_by_the_inverse() -> None:
    """Everything else stays an opaque key (ADR-0007) — including every edge IRI."""
    outside = (
        identity.edge_iri("Refines", "a", "b"),
        "https://example.org/node/SEG-SREQ-020",
        f"{identity.BASE}/node/",
        f"{identity.BASE}/node/a/b",
        f"{identity.BASE}/event/000001",
    )
    for iri in outside:
        with pytest.raises(ValueError):
            identity.node_local_id(iri)
