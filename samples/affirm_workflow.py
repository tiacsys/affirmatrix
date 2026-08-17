"""The affirm workflow, end to end, on a throwaway case root.

Walks the loop an operator runs when content has drifted: derive every edge's
state from the recorded and current streams, compose an affirmation for an
edge owed a judgement, hand both composed halves to the store, and derive
again to watch the change site come back active.

Everything here is capability, not authority: the case root is a temporary
directory, and composing a review event in a script is not an affirmation
act. On a real case the loop has one more step this script cannot and must
not perform — the maintainer reviews the dirty working tree and commits it,
and that commit is the affirmation (ADR-0009).

Run from the repository root:  .venv/bin/python samples/affirm_workflow.py
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Iterator
from pathlib import Path

from affirmatrix import affirmation, commitment, drift, records
from affirmatrix.case import AffirmationStore
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord


def node(local_id: str, kind: str, names: tuple[str, ...], seed: str) -> NodeRecord:
    """A node record over made-up content — the seed stands in for the bytes."""
    return NodeRecord(
        local_id,
        kind,
        {
            name: records.ContentAnchor(
                digest=hashlib.sha256(f"{name}:{seed}".encode()).digest(),
                repository="demo-repo",
                path="pkg/module.py",
                locator="file",
            )
            for name in names
        },
    )


def node_hash_of(record: NodeRecord) -> bytes:
    return commitment.node_hash(record.kind, record.content_hashes)


class Producer:
    """A record source built from literals — the current stream's stand-in."""

    def __init__(self, nodes: tuple[NodeRecord, ...], edges: tuple[EdgeRecord, ...]) -> None:
        self._nodes = nodes
        self._edges = edges

    def nodes(self) -> Iterator[NodeRecord]:
        return iter(self._nodes)

    def edges(self) -> Iterator[EdgeRecord]:
        return iter(self._edges)


def main() -> None:
    # The case as it was last affirmed: one implementation under one
    # requirement, the edge active and carrying the hash it was judged with.
    sreq = node("SREQ-1", "Requirement", ("contentHash",), seed="v1")
    impl_v1 = node("pkg.fn", "Implementation", ("apiHash", "bodyHash"), seed="v1")
    store = AffirmationStore(root=Path(tempfile.mkdtemp()) / "case")
    store.write_nodes([sreq, impl_v1])
    store.write_edges(
        [
            EdgeRecord(
                from_id="pkg.fn",
                to_id="SREQ-1",
                kind="Implements",
                state=LinkState.ACTIVE,
                edge_hash=commitment.edge_hash(
                    "pkg.fn", "SREQ-1", "Implements", node_hash_of(impl_v1), node_hash_of(sreq)
                ),
            )
        ]
    )

    # Today's content: the implementation moved on; the requirement did not.
    impl_v2 = node("pkg.fn", "Implementation", ("apiHash", "bodyHash"), seed="v2")
    current = Producer(
        nodes=(sreq, impl_v2),
        edges=(
            EdgeRecord(
                from_id="pkg.fn", to_id="SREQ-1", kind="Implements", state=LinkState.PENDING
            ),
        ),
    )

    # 1. The suspect detector derives every current edge's state from the two
    #    streams; the recorder's gate names which of those are owed a judgement.
    derivation = drift.derive(recorded=store, current=current)
    worklist = [edge for edge in derivation.edges() if affirmation.affirmable(edge.state)]
    for edge in worklist:
        print(f"owed a judgement: {edge.kind} {edge.from_id} -> {edge.to_id} ({edge.state})")

    # 2. The recorder composes the operator's judgement into the pair the case
    #    needs: the review event, and the edge record as it stands affirmed.
    #    Every judgement field is the operator's — the endpoints judged are
    #    today's records, and the source revisions are supplied, never
    #    discovered, because the tool runs no git.
    current_nodes = {record.local_id: record for record in derivation.nodes()}
    edge = worklist[0]
    composed = affirmation.compose(
        edge,
        from_node=current_nodes[edge.from_id],
        to_node=current_nodes[edge.to_id],
        role="SoftwareEngineer",
        reason="reviewed the change; the binding still holds",
        from_source_revision="1" * 40,
        to_source_revision="2" * 40,
    )

    # 3. The store persists both halves. It computes nothing — the recorder
    #    composed the active record and its hash; the store keeps what it is
    #    handed, validated against the case's own schemas.
    store.append_review_events([composed.event])
    store.write_edges([composed.edge])

    # 4. A second derivation finds the change site active again. Had the edge
    #    sat under ancestors, their transitive suspicion would clear here by
    #    recomputation — no one re-affirms an edge whose endpoints never moved.
    settled = drift.derive(recorded=store, current=current)
    for edge in settled.edges():
        print(f"after affirming: {edge.kind} {edge.from_id} -> {edge.to_id} ({edge.state})")

    # What the recorder refuses: a state affirmation cannot resolve. The edge
    # just affirmed is active now, and an active edge has nothing to affirm.
    try:
        affirmation.compose(
            composed.edge,
            from_node=current_nodes[edge.from_id],
            to_node=current_nodes[edge.to_id],
            role="SoftwareEngineer",
            reason="",
            from_source_revision="1" * 40,
            to_source_revision="2" * 40,
        )
    except affirmation.AffirmationError as refusal:
        print(f"refused: {refusal}")


if __name__ == "__main__":
    main()
