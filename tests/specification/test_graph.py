"""Verification suite for the graph builder's refusals and edge states.

Each function below realizes one test specification (``SEG-TS-nnn``)
and demonstrates the software requirement named in its ``:verifies:`` marker
by building a graph from a small literal record set chosen to trigger, or
deliberately not trigger, the behaviour under test.
"""

from __future__ import annotations

import hashlib

import pytest

from affirmatrix import graph, records

D1 = hashlib.sha256(b"one").digest()


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
    """Name to digest pairs as anchors; the builder cares about names and digests only."""
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


def test_a_refines_cycle_or_self_loop_is_refused() -> None:
    """A refines cycle or self-loop is refused.

    Building a graph whose refines edges contain a self-loop, and
    separately one whose refines edges form a longer cycle, is refused
    with a graph-level error naming a cycle in both cases. Building a
    graph whose refines edges converge without looping — two children
    refining into one shared ancestor — succeeds; a diamond is not
    mistaken for a cycle.

    :verifies: SEG-SREQ-004
    :test-id: SEG-TS-007
    """
    with pytest.raises(graph.GraphError, match="cycle"):
        graph.build(Source([requirement("a")], [refines("a", "a")]))
    with pytest.raises(graph.GraphError, match="cycle"):
        graph.build(
            Source(
                [requirement("a"), requirement("b"), requirement("c")],
                [refines("a", "b"), refines("b", "c"), refines("c", "a")],
            )
        )
    diamond = graph.build(
        Source(
            [requirement("a"), requirement("b"), requirement("c"), requirement("d")],
            [refines("a", "b"), refines("a", "c"), refines("b", "d"), refines("c", "d")],
        )
    )
    assert set(diamond.node_ids()) == {"a", "b", "c", "d"}


def test_an_unaffirmed_edge_builds_as_pending() -> None:
    """An unaffirmed edge builds as pending.

    Building a graph from an edge record that carries no hash it was
    affirmed against, but whose recorded state claims otherwise, yields a
    built edge in the pending state — the state the record itself claims
    is disregarded in favour of the absence of an affirmed hash.

    :verifies: SEG-SREQ-016
    :test-id: SEG-TS-008
    """
    claimed = records.EdgeRecord("a", "b", "Refines", records.LinkState.DIRECTLY_OUTDATED)
    built = graph.build(Source([requirement("a"), requirement("b")], [claimed]))
    assert built.edges[0].state is records.LinkState.PENDING


def test_a_record_of_an_undeclared_kind_is_refused() -> None:
    """A record of an undeclared kind is refused.

    Building a graph from a node record declaring a kind the taxonomy
    provider does not declare is refused, and building a graph from an
    edge record declaring such a kind is refused likewise — an
    undeclared kind stops the build whether it appears on a node or an
    edge.

    :verifies: SEG-SREQ-031
    :test-id: SEG-TS-009
    """
    with pytest.raises(graph.GraphError, match="Speculation"):
        graph.build(Source([records.NodeRecord("x", "Speculation", anchors({"contentHash": D1}))]))
    with pytest.raises(graph.GraphError, match="Resembles"):
        graph.build(
            Source(
                [requirement("a"), requirement("b")],
                [records.EdgeRecord("a", "b", "Resembles", records.LinkState.PENDING)],
            )
        )
