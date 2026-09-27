"""Verification suite for the suspect detector's derived edge states.

Each function below realizes one test specification (``SEG-TS-nnn``)
and demonstrates the software requirement named in its ``:verifies:`` marker
by deriving states from a recorded and a current record source built from
literal records.
"""

from __future__ import annotations

import hashlib

from affirmatrix import commitment, drift, records
from affirmatrix.records import LinkState


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def anchors(names: tuple[str, ...], seed: str = "v1") -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(f"{name}:{seed}".encode()).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def requirement(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors(("contentHash",), seed))


def implementation(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Implementation", anchors(("apiHash", "bodyHash"), seed))


def outcome(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(
        local_id,
        "TestOutcome",
        anchors(("contentHash",), seed),
        result=records.TestResult.PASSED,
        revision="rev-a",
    )


def affirmed(
    kind: str, from_node: records.NodeRecord, to_node: records.NodeRecord
) -> records.EdgeRecord:
    """A recorded edge affirmed against exactly these two nodes' content."""
    return records.EdgeRecord(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        state=LinkState.ACTIVE,
        edge_hash=commitment.edge_hash(
            from_node.local_id,
            to_node.local_id,
            kind,
            commitment.node_hash(from_node.kind, from_node.content_hashes),
            commitment.node_hash(to_node.kind, to_node.content_hashes),
        ),
    )


def declared(kind: str, from_id: str, to_id: str) -> records.EdgeRecord:
    """A current edge as a producer declares it, before any state is derived."""
    return records.EdgeRecord(from_id, to_id, kind, state=LinkState.PENDING)


def state_of(derivation: drift.Derivation, kind: str, from_id: str, to_id: str) -> LinkState:
    for edge in derivation.edges():
        if (edge.kind, edge.from_id, edge.to_id) == (kind, from_id, to_id):
            return edge.state
    raise AssertionError(f"no derived edge {from_id!r} -> {to_id!r} ({kind})")


def test_every_edge_touching_an_absent_node_is_broken() -> None:
    """Every edge touching an absent node is broken.

    Deriving edge states from a current record stream whose declared
    source or target node is absent from that stream reports the edge as
    broken — for a strong edge whose recorded affirmation no longer has
    both endpoints present, and equally for an edge of a kind that
    carries no suspicion, such as an outcome's confirms edge to a
    specification that is not in the current stream. Absence of an
    endpoint takes precedence over every other derived state.

    :verifies: SEG-SREQ-017
    :test-id: SEG-TS-010
    """
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), (affirmed("Implements", impl, sreq),)),
        current=Source((impl,), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.BROKEN

    run = outcome("run-1/TS-1")
    evidence_derivation = drift.derive(
        recorded=Source((), ()),
        current=Source((run,), (declared("Confirms", "run-1/TS-1", "TS-1"),)),
    )
    assert state_of(evidence_derivation, "Confirms", "run-1/TS-1", "TS-1") is LinkState.BROKEN
