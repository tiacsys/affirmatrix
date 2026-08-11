"""The persisted vocabulary and the record-source protocol.

Records are what crosses every boundary in the engine: a producer emits them, a
builder consumes them, the store serializes them. Three properties are load
bearing and are tested as such.

*They carry no content.* A record carries hashes and references — never the
text, source, or output those hashes cover (SEG-SREQ-018). The type makes that
structural rather than a habit callers are asked to keep.

*They are immutable.* A record that could be edited in flight would let a hash
and the thing it describes drift apart between producer and store.

*Identifiers are case-local.* Absolute IRIs are minted at serialization
(ADR-0007); a record in memory carries the stable local identifier that also
enters a hash preimage, so the two can never disagree.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from affirmatrix import records

D1 = hashlib.sha256(b"one").digest()
D2 = hashlib.sha256(b"two").digest()


def anchor(digest: bytes = D1, locator: str = "file") -> records.ContentAnchor:
    return records.ContentAnchor(
        digest=digest, repository="the-source-repo", path="pkg/module.py", locator=locator
    )


# ── Content anchors ─────────────────────────────────────────────────────────


def test_a_content_anchor_binds_a_digest_to_where_its_content_lives() -> None:
    """SEG-SREQ-050's shape: one named hash, one location, one value."""
    bound = anchor()
    assert bound.digest == D1
    assert bound.repository == "the-source-repo"
    assert bound.path == "pkg/module.py"
    assert bound.locator == "file"


def test_a_content_anchor_requires_every_part_of_the_location() -> None:
    """A partial location fetches nothing: each field is one leg of the recovery."""
    with pytest.raises(ValueError, match="repository"):
        records.ContentAnchor(digest=D1, repository="", path="p", locator="file")
    with pytest.raises(ValueError, match="path"):
        records.ContentAnchor(digest=D1, repository="r", path="", locator="file")
    with pytest.raises(ValueError, match="locator"):
        records.ContentAnchor(digest=D1, repository="r", path="p", locator="")


def test_a_content_anchor_rejects_a_digest_that_is_not_raw_bytes() -> None:
    with pytest.raises(ValueError, match="32 raw bytes"):
        records.ContentAnchor(
            digest=D1.hex().encode(), repository="r", path="p", locator="file"
        )


def test_a_content_anchor_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        anchor().path = "elsewhere"  # type: ignore[misc]


# ── Node records ────────────────────────────────────────────────────────────


def test_a_node_record_carries_its_kind_and_anchored_content_hashes() -> None:
    node = records.NodeRecord(
        local_id="SEG-SREQ-001", kind="Requirement", content_anchors={"contentHash": anchor()}
    )
    assert node.local_id == "SEG-SREQ-001"
    assert node.kind == "Requirement"
    assert node.content_anchors == {"contentHash": anchor()}


def test_a_node_record_derives_its_content_hashes_from_its_anchors() -> None:
    """The name-to-digest view feeds hashing, and it is a reading of the anchors,
    so the two can never disagree about which digest a name carries."""
    node = records.NodeRecord(
        "affirmatrix.graph.build",
        "Implementation",
        {"apiHash": anchor(D1), "bodyHash": anchor(D2)},
    )
    assert node.content_hashes == {"apiHash": D1, "bodyHash": D2}


def test_a_node_record_is_immutable() -> None:
    node = records.NodeRecord("SEG-SREQ-001", "Requirement", {"contentHash": anchor()})
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.local_id = "SEG-SREQ-002"  # type: ignore[misc]


def test_a_node_record_cannot_be_mutated_through_its_content_anchors() -> None:
    """Freezing the record is worthless if its mapping is still a live dict."""
    source = {"contentHash": anchor(D1)}
    node = records.NodeRecord("SEG-SREQ-001", "Requirement", source)
    source["contentHash"] = anchor(D2)
    assert node.content_anchors["contentHash"].digest == D1
    with pytest.raises(TypeError):
        node.content_anchors["contentHash"] = anchor(D2)  # type: ignore[index]


def test_a_node_record_rejects_a_bare_digest_where_an_anchor_belongs() -> None:
    """The realistic mistake: content was hashed but nobody said where it lives."""
    with pytest.raises(ValueError, match="ContentAnchor"):
        records.NodeRecord("SEG-SREQ-001", "Requirement", {"contentHash": D1})


def test_a_node_record_needs_at_least_one_content_hash() -> None:
    with pytest.raises(ValueError, match="at least one"):
        records.NodeRecord("SEG-SREQ-001", "Requirement", {})


def test_a_node_record_needs_a_local_identifier_and_a_kind() -> None:
    with pytest.raises(ValueError, match="local identifier"):
        records.NodeRecord("", "Requirement", {"contentHash": anchor()})
    with pytest.raises(ValueError, match="kind"):
        records.NodeRecord("SEG-SREQ-001", "", {"contentHash": anchor()})


# ── Edge records ────────────────────────────────────────────────────────────


def test_an_edge_record_carries_endpoints_kind_and_state() -> None:
    edge = records.EdgeRecord(
        from_id="SEG-SREQ-001",
        to_id="SEG-SYS-001",
        kind="Refines",
        state=records.LinkState.ACTIVE,
        edge_hash=D1,
    )
    assert (edge.from_id, edge.to_id, edge.kind) == ("SEG-SREQ-001", "SEG-SYS-001", "Refines")
    assert edge.state is records.LinkState.ACTIVE
    assert edge.edge_hash == D1


def test_an_edge_record_is_immutable() -> None:
    edge = records.EdgeRecord("a", "b", "Refines", records.LinkState.PENDING)
    with pytest.raises(dataclasses.FrozenInstanceError):
        edge.state = records.LinkState.ACTIVE  # type: ignore[misc]


def test_an_unaffirmed_edge_carries_no_edge_hash() -> None:
    """A pending edge was never affirmed, so there is nothing it was affirmed against.

    Absence of a stored hash is a state, not a mismatch (ADR-0005) — modelling
    it as ``None`` keeps the detector from comparing against a placeholder.
    """
    edge = records.EdgeRecord("a", "b", "Refines", records.LinkState.PENDING)
    assert edge.edge_hash is None


def test_an_active_edge_must_carry_the_hash_it_was_affirmed_against() -> None:
    with pytest.raises(ValueError, match="affirmed against"):
        records.EdgeRecord("a", "b", "Refines", records.LinkState.ACTIVE)


def test_a_pending_edge_must_not_carry_an_edge_hash() -> None:
    with pytest.raises(ValueError, match="never affirmed"):
        records.EdgeRecord("a", "b", "Refines", records.LinkState.PENDING, edge_hash=D1)


def test_edge_states_cover_the_specified_vocabulary() -> None:
    assert {state.value for state in records.LinkState} == {
        "pending",
        "active",
        "directlyOutdated",
        "transitivelySuspect",
        "doublyOutdated",
        "broken",
    }


# ── Review events ───────────────────────────────────────────────────────────


def test_a_review_event_binds_both_endpoint_hashes_and_both_anchors() -> None:
    """SEG-SREQ-024 and SEG-SREQ-025 together: what was affirmed, and against what."""
    event = records.ReviewEvent(
        from_id="SEG-SREQ-001",
        to_id="SEG-SYS-001",
        kind="Refines",
        from_node_hash=D1,
        to_node_hash=D2,
        from_source_revision="a" * 40,
        to_source_revision="b" * 40,
        role="RequirementsEngineer",
        reason="Refinement still holds after the wording change.",
    )
    assert event.from_node_hash == D1
    assert event.to_node_hash == D2
    assert event.from_source_revision == "a" * 40
    assert event.to_source_revision == "b" * 40


def test_a_review_event_carries_the_role_it_was_made_in() -> None:
    """SEG-SREQ-049: the capacity someone was acting in is part of the judgement."""
    event = records.ReviewEvent(
        "a", "b", "Refines", D1, D2, "a" * 40, "b" * 40, role="TestEngineer", reason="x"
    )
    assert event.role == "TestEngineer"


def test_a_review_event_requires_a_non_empty_role() -> None:
    """An empty role would satisfy the field while recording nothing."""
    with pytest.raises(ValueError, match="role"):
        records.ReviewEvent("a", "b", "Refines", D1, D2, "a" * 40, "b" * 40, role="", reason="x")


def test_a_role_is_a_free_string_not_a_closed_vocabulary() -> None:
    """Role validation is a process concern; the tool checks non-empty and nothing else."""
    event = records.ReviewEvent(
        "a", "b", "Refines", D1, D2, "a" * 40, "b" * 40,
        role="acting deputy reviewer (annex F)", reason="",
    )
    assert event.role == "acting deputy reviewer (annex F)"


def test_a_review_event_preserves_the_reason_verbatim() -> None:
    """SEG-SREQ-028: recorded without alteration — including its whitespace."""
    reason = "  Two spaces, a\ttab,\nand a newline.  "
    event = records.ReviewEvent(
        "a", "b", "Refines", D1, D2, "a" * 40, "b" * 40, role="SoftwareEngineer", reason=reason
    )
    assert event.reason == reason


def test_a_review_event_requires_both_source_anchors() -> None:
    """The anchor cannot be backfilled: nothing else records where each endpoint was."""
    with pytest.raises(ValueError, match="source revision"):
        records.ReviewEvent(
            "a", "b", "Refines", D1, D2, "", "b" * 40, role="SoftwareEngineer", reason="x"
        )
    with pytest.raises(ValueError, match="source revision"):
        records.ReviewEvent(
            "a", "b", "Refines", D1, D2, "a" * 40, "", role="SoftwareEngineer", reason="x"
        )


def test_a_review_event_is_immutable() -> None:
    event = records.ReviewEvent(
        "a", "b", "Refines", D1, D2, "a" * 40, "b" * 40, "SoftwareEngineer", "why"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.reason = "different"  # type: ignore[misc]


def test_a_review_event_accepts_an_empty_reason_but_not_a_missing_one() -> None:
    """An unexplained affirmation is a poor one, but it is the operator's to make."""
    event = records.ReviewEvent(
        "a", "b", "Refines", D1, D2, "a" * 40, "b" * 40, role="SoftwareEngineer", reason=""
    )
    assert event.reason == ""


# ── No content, ever ────────────────────────────────────────────────────────


def test_no_record_type_offers_a_field_for_content() -> None:
    """SEG-SREQ-018 made structural: there is nowhere to put content.

    A record that merely *happens* not to carry content today invites a field
    being added later "just for debugging"; the absence has to be checkable.
    """
    allowed = {
        records.ContentAnchor: {"digest", "repository", "path", "locator"},
        records.NodeRecord: {"local_id", "kind", "content_anchors"},
        records.EdgeRecord: {"from_id", "to_id", "kind", "state", "edge_hash"},
        records.EdgeReference: {"kind", "from_id", "to_id"},
        records.ReviewEvent: {
            "from_id",
            "to_id",
            "kind",
            "from_node_hash",
            "to_node_hash",
            "from_source_revision",
            "to_source_revision",
            "role",
            "reason",
        },
    }
    for record_type, expected in allowed.items():
        actual = {field.name for field in dataclasses.fields(record_type)}
        assert actual == expected, f"{record_type.__name__} grew a field"


# ── Edge references ─────────────────────────────────────────────────────────


def test_an_edge_reference_names_an_edge_by_its_identifying_triple() -> None:
    """Kind and endpoints as their own values — never an identifier to split (ADR-0007)."""
    reference = records.EdgeReference(kind="Implements", from_id="f", to_id="SEG-SREQ-051")
    assert (reference.kind, reference.from_id, reference.to_id) == (
        "Implements",
        "f",
        "SEG-SREQ-051",
    )


def test_an_edge_reference_requires_every_part_of_the_name() -> None:
    with pytest.raises(ValueError, match="kind"):
        records.EdgeReference(kind="", from_id="f", to_id="t")
    with pytest.raises(ValueError, match="source identifier"):
        records.EdgeReference(kind="Refines", from_id="", to_id="t")
    with pytest.raises(ValueError, match="target identifier"):
        records.EdgeReference(kind="Refines", from_id="f", to_id="")


def test_an_edge_reference_is_usable_as_a_set_member() -> None:
    """A demotion request is checked per edge, so the name must equal by value."""
    assert records.EdgeReference("Refines", "a", "b") in {
        records.EdgeReference("Refines", "a", "b")
    }
    assert records.EdgeReference("Refines", "a", "b") != records.EdgeReference(
        "Verifies", "a", "b"
    )


# ── Hex is a serialization form ─────────────────────────────────────────────


def test_a_digest_serializes_as_lowercase_hex() -> None:
    """One canonical written form, so two spellings of a digest cannot exist."""
    assert records.hex_digest(D1) == D1.hex()
    assert records.hex_digest(D1) == records.hex_digest(D1).lower()


def test_a_hex_digest_parses_back_to_the_same_bytes() -> None:
    assert records.digest_from_hex(records.hex_digest(D1)) == D1


def test_an_uppercase_digest_is_refused_rather_than_folded() -> None:
    """Folding would admit a second spelling of a record that must have one."""
    with pytest.raises(ValueError, match="lowercase"):
        records.digest_from_hex(D1.hex().upper())


def test_a_string_that_is_not_a_digest_is_refused() -> None:
    with pytest.raises(ValueError):
        records.digest_from_hex("cafe")


def test_serializing_something_that_is_not_a_digest_is_refused() -> None:
    """The realistic mistake is hex that has already been converted once."""
    with pytest.raises(ValueError):
        records.hex_digest(D1.hex().encode("ascii"))


# ── The record source protocol and its two roles ────────────────────────────


class _Fake:
    """A record source built from literals — the shape every adapter must satisfy."""

    def __init__(self, nodes: list[records.NodeRecord], edges: list[records.EdgeRecord]):
        self._nodes = nodes
        self._edges = edges

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def test_a_duck_typed_source_satisfies_the_protocol() -> None:
    """Structural typing: an adapter need not import us to be one."""
    source = _Fake([], [])
    assert isinstance(source, records.RecordSource)


def test_an_object_missing_edges_is_not_a_record_source() -> None:
    class Partial:
        def nodes(self):
            return iter(())

    assert not isinstance(Partial(), records.RecordSource)


def test_the_two_roles_are_nameable() -> None:
    """Drift detection needs to say *which* stream it means (SEG-SREQ-015)."""
    assert {role.value for role in records.SourceRole} == {"recorded", "current"}


def test_a_role_reads_as_its_name() -> None:
    assert str(records.SourceRole.RECORDED) == "recorded"
    assert str(records.SourceRole.CURRENT) == "current"
