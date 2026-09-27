"""Verification suite for the commitment layer's three hash derivations.

Each function below realizes one test specification (``SEG-TS-nnn``)
and demonstrates the software requirement named in its ``:verifies:`` marker.
A baseline computation is fixed and then one input at a time is varied,
checking that the derived hash moves exactly where the requirement says it
must.
"""

from __future__ import annotations

import hashlib

from affirmatrix import commitment

#: Stand-in 32-byte digests. Their provenance is irrelevant to the layer
#: under test — it only ever checks a digest's length, never its origin.
N1 = hashlib.sha256(b"one").digest()
N2 = hashlib.sha256(b"two").digest()
N3 = hashlib.sha256(b"three").digest()
D1 = hashlib.sha256(b"content-one").digest()
D2 = hashlib.sha256(b"content-two").digest()


def test_the_edge_hash_binds_endpoints_type_and_both_node_hashes() -> None:
    """The edge hash binds both endpoints.

    Computing an edge's hash from a fixed baseline of endpoint identifiers,
    edge type, and both node hashes, then independently varying each of
    the five inputs in turn — the source identifier, the target
    identifier, the edge type, the source node hash, and the target node
    hash — changes the resulting hash on every variation. No single input
    can move without the edge hash moving with it.

    :verifies: SEG-SREQ-002
    :test-id: SEG-TS-004
    """
    baseline = commitment.edge_hash("a", "b", "Refines", N1, N2)
    assert commitment.edge_hash("x", "b", "Refines", N1, N2) != baseline
    assert commitment.edge_hash("a", "x", "Refines", N1, N2) != baseline
    assert commitment.edge_hash("a", "b", "Verifies", N1, N2) != baseline
    assert commitment.edge_hash("a", "b", "Refines", N3, N2) != baseline
    assert commitment.edge_hash("a", "b", "Refines", N1, N3) != baseline


def test_the_design_root_seals_the_whole_design_set() -> None:
    """The design root seals the whole design set.

    Computing a design root over a fixed set of node hashes, edge tuples,
    and caller metadata, then reordering the node hashes and edges before
    recomputing, yields the same root — the canonical sort absorbs input
    order. Independently varying one node hash, one edge's endpoint or
    type, or the metadata changes the root; no single member of the
    design set can move without the root moving with it.

    :verifies: SEG-SREQ-003
    :test-id: SEG-TS-005
    """
    edges = [("a", "b", "Refines"), ("b", "c", "Verifies")]
    reordered_edges = [("b", "c", "Verifies"), ("a", "b", "Refines")]
    baseline = commitment.design_root(b"meta", [N1, N2], edges)
    assert commitment.design_root(b"meta", [N2, N1], reordered_edges) == baseline
    assert commitment.design_root(b"meta", [N3, N2], edges) != baseline
    assert commitment.design_root(b"meta", [N1, N2], [("a", "x", "Refines"), edges[1]]) != baseline
    assert commitment.design_root(b"meta", [N1, N2], [("a", "b", "Verifies"), edges[1]]) != baseline
    assert commitment.design_root(b"other-meta", [N1, N2], edges) != baseline


def test_the_node_hash_derives_from_type_and_content_hashes_alone() -> None:
    """The node hash derives from type and content hashes alone.

    Computing a node hash from a fixed node type and one named content
    hash, then independently varying the node type, the content digest,
    and the content-hash field name, changes the resulting hash on every
    variation; and the node hash of a single content hash never equals
    that content hash's own digest — the type and the name are folded
    in, not merely passed through.

    :verifies: SEG-SREQ-005
    :test-id: SEG-TS-006
    """
    baseline = commitment.node_hash("Requirement", {"contentHash": D1})
    assert commitment.node_hash("Waiver", {"contentHash": D1}) != baseline
    assert commitment.node_hash("Requirement", {"contentHash": D2}) != baseline
    assert commitment.node_hash("Requirement", {"otherName": D1}) != baseline
    assert baseline != D1
