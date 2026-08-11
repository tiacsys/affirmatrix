"""The graph builder (SEG-SREQ-004, -016, -031).

The builder is the narrow gate every record passes through on its way into the
graph, so most of its behaviour is about what it refuses. Two refusals are
ratified — a refines cycle, and a kind the vocabulary does not declare — and
both exist for the same reason: each would otherwise produce a graph that looks
complete and seals to a perfectly valid root while being wrong. A graph missing
records nobody noticed were dropped is the more dangerous of the two, because
nothing downstream can tell.

What the builder must *not* refuse matters just as much. An edge pointing at a
node that is not present is not an error here: that is a broken edge, and
deciding so needs both record streams, which is the suspect detector's job.
"""

from __future__ import annotations

import hashlib

import pytest

from affirmatrix import graph, records

D1 = hashlib.sha256(b"one").digest()
D2 = hashlib.sha256(b"two").digest()
D3 = hashlib.sha256(b"three").digest()


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def anchors(digests: dict[str, bytes]) -> dict[str, records.ContentAnchor]:
    """Name→digest pairs as anchors; the builder cares about names and digests only."""
    return {
        name: records.ContentAnchor(
            digest=digest, repository="the-source-repo", path="pkg/module.py", locator="file"
        )
        for name, digest in digests.items()
    }


def requirement(local_id: str, digest: bytes = D1) -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors({"contentHash": digest}))


def refines(child: str, parent: str, **kwargs) -> records.EdgeRecord:
    kwargs.setdefault("state", records.LinkState.PENDING)
    return records.EdgeRecord(child, parent, "Refines", **kwargs)


# ── Building ────────────────────────────────────────────────────────────────


def test_a_built_graph_holds_its_nodes_by_local_identifier() -> None:
    built = graph.build(Source([requirement("SEG-SREQ-001")]))
    assert built.node("SEG-SREQ-001").kind == "Requirement"
    assert set(built.node_ids()) == {"SEG-SREQ-001"}


def test_an_empty_source_builds_an_empty_graph() -> None:
    built = graph.build(Source())
    assert not built.node_ids()
    assert not built.edges


def test_the_builder_consumes_a_source_that_can_only_be_walked_once() -> None:
    """Sources stream; nothing may assume a second pass is available."""
    built = graph.build(Source([requirement("A"), requirement("B")]))
    assert set(built.node_ids()) == {"A", "B"}


def test_adjacency_is_indexed_in_both_directions() -> None:
    source = Source(
        [requirement("child"), requirement("parent")],
        [refines("child", "parent")],
    )
    built = graph.build(source)
    assert [edge.to_id for edge in built.outgoing("child")] == ["parent"]
    assert [edge.from_id for edge in built.incoming("parent")] == ["child"]
    assert built.incoming("child") == ()
    assert built.outgoing("parent") == ()


def test_adjacency_can_be_narrowed_to_one_kind() -> None:
    source = Source(
        [requirement("r"), requirement("p"), records.NodeRecord("t", "TestSpecification",
            anchors({"specHash": D1, "implHash": D2}))],
        [refines("r", "p"), records.EdgeRecord("t", "r", "Verifies", records.LinkState.PENDING)],
    )
    built = graph.build(source)
    assert len(built.incoming("r")) == 1
    assert built.incoming("r", kind="Refines") == ()
    assert len(built.incoming("r", kind="Verifies")) == 1


def test_an_unknown_node_is_reported_rather_than_returning_nothing() -> None:
    built = graph.build(Source())
    with pytest.raises(KeyError):
        built.node("nobody")


# ── SEG-SREQ-031: unrecognized kinds are rejected ───────────────────────────


def test_a_node_of_an_undeclared_kind_is_rejected() -> None:
    source = Source([records.NodeRecord("x", "Speculation", anchors({"contentHash": D1}))])
    with pytest.raises(graph.GraphError, match="Speculation"):
        graph.build(source)


def test_an_edge_of_an_undeclared_kind_is_rejected() -> None:
    source = Source(
        [requirement("a"), requirement("b")],
        [records.EdgeRecord("a", "b", "Resembles", records.LinkState.PENDING)],
    )
    with pytest.raises(graph.GraphError, match="Resembles"):
        graph.build(source)


def test_rejection_stops_the_build_rather_than_skipping_the_record() -> None:
    """Skipping would leave a smaller graph that still seals to a valid root.

    A graph silently missing records is indistinguishable, downstream, from a
    graph that never had them — and it would seal, and the seal would verify.
    """
    source = Source(
        [requirement("a"), records.NodeRecord("b", "Speculation", anchors({"contentHash": D1}))]
    )
    with pytest.raises(graph.GraphError):
        graph.build(source)


def test_a_node_carrying_a_content_hash_its_kind_does_not_declare_is_rejected() -> None:
    """The vocabulary fixes which hashes a kind carries, and the node hash folds
    those names in — so an undeclared name would change the hash of a node the
    vocabulary cannot describe."""
    source = Source([records.NodeRecord("a", "Requirement", anchors({"apiHash": D1}))])
    with pytest.raises(graph.GraphError, match="apiHash"):
        graph.build(source)


def test_a_node_missing_a_content_hash_its_kind_declares_is_rejected() -> None:
    source = Source([records.NodeRecord("i", "Implementation", anchors({"apiHash": D1}))])
    with pytest.raises(graph.GraphError, match="bodyHash"):
        graph.build(source)


# ── SEG-SREQ-004: refines cycles are a graph-level error ────────────────────


def test_a_refines_self_loop_is_an_error() -> None:
    source = Source([requirement("a")], [refines("a", "a")])
    with pytest.raises(graph.GraphError, match="cycle"):
        graph.build(source)


def test_a_refines_cycle_is_an_error() -> None:
    source = Source(
        [requirement("a"), requirement("b"), requirement("c")],
        [refines("a", "b"), refines("b", "c"), refines("c", "a")],
    )
    with pytest.raises(graph.GraphError, match="cycle"):
        graph.build(source)


def test_the_cycle_error_names_the_cycle() -> None:
    """A cycle is fixed by editing one of its edges; the report must say which."""
    source = Source(
        [requirement("a"), requirement("b")],
        [refines("a", "b"), refines("b", "a")],
    )
    with pytest.raises(graph.GraphError) as caught:
        graph.build(source)
    assert "a" in str(caught.value) and "b" in str(caught.value)


def test_a_diamond_in_the_refines_relation_is_not_a_cycle() -> None:
    """Two parents sharing a grandparent is a legitimate decomposition."""
    source = Source(
        [requirement(name) for name in ("leaf", "left", "right", "top")],
        [
            refines("leaf", "left"),
            refines("leaf", "right"),
            refines("left", "top"),
            refines("right", "top"),
        ],
    )
    assert len(graph.build(source).edges) == 4


def test_a_deep_refines_chain_does_not_exhaust_the_stack() -> None:
    """Depth here is the caller's decomposition depth, not ours.

    A recursive walk crashes with ``RecursionError`` on a long chain, which is
    a crash where the contract promises a graph-level error.
    """
    depth = 5000
    nodes = [requirement(f"r{i}") for i in range(depth)]
    edges = [refines(f"r{i}", f"r{i + 1}") for i in range(depth - 1)]
    assert len(graph.build(Source(nodes, edges)).edges) == depth - 1


def test_a_cycle_deep_in_a_long_chain_is_still_reported() -> None:
    depth = 5000
    nodes = [requirement(f"r{i}") for i in range(depth)]
    edges = [refines(f"r{i}", f"r{i + 1}") for i in range(depth - 1)]
    edges.append(refines(f"r{depth - 1}", "r0"))
    with pytest.raises(graph.GraphError, match="cycle"):
        graph.build(Source(nodes, edges))


def test_cycles_in_other_edge_kinds_are_not_refines_cycles() -> None:
    """Only refines must be acyclic — it is the relation satisfaction recurses on."""
    source = Source(
        [
            records.NodeRecord("t", "TestSpecification", anchors({"specHash": D1, "implHash": D2})),
            requirement("r"),
        ],
        [
            records.EdgeRecord("t", "r", "Verifies", records.LinkState.PENDING),
            records.EdgeRecord("r", "t", "Verifies", records.LinkState.PENDING),
        ],
    )
    assert len(graph.build(source).edges) == 2


# ── SEG-SREQ-016: unaffirmed edges are pending ──────────────────────────────


def test_an_edge_with_no_affirmed_hash_is_reported_as_pending() -> None:
    built = graph.build(Source([requirement("a"), requirement("b")], [refines("a", "b")]))
    assert built.edges[0].state is records.LinkState.PENDING


def test_a_claimed_state_without_an_affirmed_hash_is_normalized_to_pending() -> None:
    """The absence of an affirmed hash is the evidence, not the state field.

    A source claiming an edge is suspect while carrying nothing it was affirmed
    against is describing an edge nobody ever affirmed. Trusting the label over
    the evidence would let a producer assert an affirmation history that never
    happened.
    """
    claimed = records.EdgeRecord("a", "b", "Refines", records.LinkState.DIRECTLY_OUTDATED)
    built = graph.build(Source([requirement("a"), requirement("b")], [claimed]))
    assert built.edges[0].state is records.LinkState.PENDING


def test_a_recorded_state_is_carried_rather_than_recomputed() -> None:
    """The builder assembles; deriving current state is the detector's job."""
    affirmed = records.EdgeRecord("a", "b", "Refines", records.LinkState.ACTIVE, edge_hash=D3)
    built = graph.build(Source([requirement("a"), requirement("b")], [affirmed]))
    assert built.edges[0].state is records.LinkState.ACTIVE
    assert built.edges[0].edge_hash == D3


# ── What the builder must not refuse ────────────────────────────────────────


def test_an_edge_to_an_absent_node_is_built_not_rejected() -> None:
    """A dangling endpoint is a broken edge, and that verdict needs both streams."""
    built = graph.build(Source([requirement("a")], [refines("a", "gone")]))
    assert len(built.edges) == 1
    assert built.edges[0].to_id == "gone"


def test_a_dangling_endpoint_still_indexes() -> None:
    built = graph.build(Source([requirement("a")], [refines("a", "gone")]))
    assert len(built.outgoing("a")) == 1
    assert len(built.incoming("gone")) == 1


def test_a_node_with_no_edges_is_kept() -> None:
    """An orphan is a finding for the gate, not something to drop on the floor."""
    built = graph.build(Source([requirement("lonely")]))
    assert set(built.node_ids()) == {"lonely"}


# ── Identity ────────────────────────────────────────────────────────────────


def test_a_duplicate_local_identifier_is_an_error() -> None:
    source = Source([requirement("same", D1), requirement("same", D2)])
    with pytest.raises(graph.GraphError, match="same"):
        graph.build(source)


def test_two_kinds_may_not_share_a_local_identifier() -> None:
    source = Source(
        [
            requirement("shared"),
            records.NodeRecord(
                "shared", "TestSpecification", anchors({"specHash": D1, "implHash": D2})
            ),
        ]
    )
    with pytest.raises(graph.GraphError, match="shared"):
        graph.build(source)


# ── The built graph is a value ──────────────────────────────────────────────


def test_the_built_graph_does_not_expose_mutable_internals() -> None:
    built = graph.build(Source([requirement("a"), requirement("b")], [refines("a", "b")]))
    with pytest.raises(AttributeError):
        built.edges.append(refines("b", "a"))  # type: ignore[attr-defined]


def test_building_twice_from_equal_sources_gives_equal_graphs() -> None:
    def make() -> Source:
        return Source([requirement("a"), requirement("b")], [refines("a", "b")])

    first, second = graph.build(make()), graph.build(make())
    assert first.edges == second.edges
    assert set(first.node_ids()) == set(second.node_ids())
