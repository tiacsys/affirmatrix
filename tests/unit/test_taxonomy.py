"""The built-in graph vocabulary (SEG-SREQ-029, -030, -032).

Most of this module's content is constants, which usually means a thin test.
Not here: ADR-0005 folds the node kind and the content-hash names into the node
hash preimage, so every string this provider declares is part of the integrity
surface. Renaming one re-hashes every node of that kind and sends every edge
touching them suspect. The spellings are therefore pinned explicitly below
rather than derived, so that changing one is a deliberate act with a failing
test attached rather than a tidy-up someone lands on a Friday.
"""

from __future__ import annotations

import hashlib

import pytest

from affirmatrix import commitment, taxonomy

# ── SEG-SREQ-029: the kind set is closed ────────────────────────────────────


def test_the_node_kinds_are_exactly_these_five() -> None:
    assert taxonomy.node_kinds() == frozenset(
        {
            "Requirement",
            "Implementation",
            "TestSpecification",
            "TestOutcome",
            "Waiver",
        }
    )


def test_the_edge_kinds_are_exactly_these_seven() -> None:
    assert taxonomy.edge_kinds() == frozenset(
        {
            "Refines",
            "Verifies",
            "Implements",
            "Confirms",
            "Witnesses",
            "Excuses",
            "Calls",
        }
    )


def test_the_declared_kinds_cannot_be_mutated_by_a_caller() -> None:
    """A provider whose declaration can be edited in place declares nothing."""
    kinds = taxonomy.node_kinds()
    with pytest.raises(AttributeError):
        kinds.add("Fabrication")  # type: ignore[attr-defined]
    assert "Fabrication" not in taxonomy.node_kinds()


# ── SEG-SREQ-030: exactly three edge kinds propagate ────────────────────────


def test_exactly_refines_verifies_and_implements_propagate() -> None:
    propagating = {kind for kind in taxonomy.edge_kinds() if taxonomy.propagates(kind)}
    assert propagating == {"Refines", "Verifies", "Implements"}


def test_the_evidence_edges_do_not_propagate() -> None:
    """Suspicion stops at the evidence boundary: a stale outcome needs a re-run.

    Propagating through ``Confirms`` would mark a test specification suspect
    because an outcome went stale, inviting re-affirmation where re-execution
    is what is actually required.
    """
    for kind in ("Confirms", "Witnesses", "Excuses", "Calls"):
        assert not taxonomy.propagates(kind)


def test_asking_whether_an_undeclared_kind_propagates_is_an_error() -> None:
    """Answering ``False`` would let a typo silently switch off propagation."""
    with pytest.raises(ValueError, match="not a declared edge kind"):
        taxonomy.propagates("Refnies")


def test_a_node_kind_is_not_an_edge_kind() -> None:
    with pytest.raises(ValueError, match="not a declared edge kind"):
        taxonomy.propagates("Requirement")


# ── SEG-SREQ-032: each node kind declares its content hashes ────────────────


def test_each_node_kind_declares_exactly_these_content_hash_names() -> None:
    assert taxonomy.content_hash_names("Requirement") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("TestOutcome") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("Waiver") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("Implementation") == frozenset({"apiHash", "bodyHash"})
    assert taxonomy.content_hash_names("TestSpecification") == frozenset(
        {"specHash", "implHash"}
    )


def test_every_declared_node_kind_carries_at_least_one_content_hash() -> None:
    """A node with nothing hashed is a node the graph cannot anchor."""
    for kind in taxonomy.node_kinds():
        assert taxonomy.content_hash_names(kind)


def test_asking_an_undeclared_node_kind_for_its_content_hashes_is_an_error() -> None:
    with pytest.raises(ValueError, match="not a declared node kind"):
        taxonomy.content_hash_names("Requirment")


def test_the_split_kinds_separate_intent_from_execution() -> None:
    """The two-hash kinds split what was declared from what was written.

    That split is what lets a suspect edge say *which* half moved: intent
    changing asks whether the thing still satisfies its requirement, execution
    changing asks whether it still needs re-running.
    """
    assert taxonomy.content_hash_names("Implementation") >= {"apiHash"}
    assert taxonomy.content_hash_names("TestSpecification") >= {"specHash"}


# ── Internal consistency ────────────────────────────────────────────────────


def test_every_propagating_kind_is_a_declared_edge_kind() -> None:
    for kind in taxonomy.propagating_edge_kinds():
        assert kind in taxonomy.edge_kinds()


def test_no_token_is_both_a_node_kind_and_an_edge_kind() -> None:
    assert not taxonomy.node_kinds() & taxonomy.edge_kinds()


def test_no_kind_carries_the_serialization_prefix() -> None:
    """Local tokens, not serialized ones (ADR-0007) — the preimage takes these."""
    for kind in taxonomy.node_kinds() | taxonomy.edge_kinds():
        assert not kind.startswith("seg:")


# ── The declaration is what the commitment layer consumes ───────────────────


def test_the_declared_names_are_usable_as_node_hash_inputs() -> None:
    """SEG-SREQ-005 draws on this declaration, so the two must actually fit."""
    digest = hashlib.sha256(b"content").digest()
    for kind in taxonomy.node_kinds():
        names = taxonomy.content_hash_names(kind)
        node_hash = commitment.node_hash(kind, dict.fromkeys(names, digest))
        assert len(node_hash) == 32


def test_two_kinds_with_identical_content_still_differ() -> None:
    """Binding the kind is what keeps single-hash kinds from colliding.

    ``Requirement``, ``TestOutcome`` and ``Waiver`` all declare one content
    hash under the same name, so nothing but the kind distinguishes their
    preimages.
    """
    digest = hashlib.sha256(b"identical").digest()
    hashes = {
        commitment.node_hash(kind, {"contentHash": digest})
        for kind in ("Requirement", "TestOutcome", "Waiver")
    }
    assert len(hashes) == 3


# ── The evidence kinds: what the case does not store ────────────────────────


def test_the_evidence_kinds_are_the_outcome_node_and_the_three_evidence_edges() -> None:
    assert taxonomy.evidence_node_kinds() == frozenset({"TestOutcome"})
    assert taxonomy.evidence_edge_kinds() == frozenset({"Confirms", "Witnesses", "Excuses"})


def test_the_evidence_kinds_are_declared_kinds_and_no_evidence_edge_propagates() -> None:
    assert taxonomy.evidence_node_kinds() <= taxonomy.node_kinds()
    assert taxonomy.evidence_edge_kinds() <= taxonomy.edge_kinds()
    assert taxonomy.evidence_edge_kinds().isdisjoint(taxonomy.propagating_edge_kinds())
