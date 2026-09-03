"""Generating an evidence package, end to end, on a throwaway case root.

Walks the path from a graph an operator has already affirmed to a persisted
evidence package: collect a scope for one requirement, judge it, assemble the
four documents, and write them into a case under a temporary directory. Then
reads the package straight back and recomputes the design consistency
proof's own root from that one document alone — the auditor's check, with no
graph in hand.

Everything here is capability, not authority: the case root is a temporary
directory, and generating a package in a script is not the operator's act
of generating an authoritative proof and sealing one into the repository's
own case.

Run from the repository root:  .venv/bin/python samples/generate_package.py
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from affirmatrix import commitment, graph, proof, records
from affirmatrix.case import AffirmationStore
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord


def node(
    local_id: str, kind: str, names: tuple[str, ...], seed: str, **extra: object
) -> NodeRecord:
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
        **extra,
    )


def affirmed(kind: str, from_node: NodeRecord, to_node: NodeRecord) -> EdgeRecord:
    """A strong edge, affirmed against exactly these two nodes' current content."""
    from_hash = commitment.node_hash(from_node.kind, from_node.content_hashes)
    to_hash = commitment.node_hash(to_node.kind, to_node.content_hashes)
    return EdgeRecord(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        state=LinkState.ACTIVE,
        edge_hash=commitment.edge_hash(
            from_node.local_id, to_node.local_id, kind, from_hash, to_hash
        ),
    )


def evidence(kind: str, from_id: str, to_id: str) -> EdgeRecord:
    """An evidence edge — always pending, never affirmed."""
    return EdgeRecord(from_id=from_id, to_id=to_id, kind=kind, state=LinkState.PENDING)


class Producer:
    """A record source built from literals — a fully affirmed graph's stand-in."""

    def __init__(self, nodes: tuple[NodeRecord, ...], edges: tuple[EdgeRecord, ...]) -> None:
        self._nodes = nodes
        self._edges = edges

    def nodes(self) -> Iterator[NodeRecord]:
        return iter(self._nodes)

    def edges(self) -> Iterator[EdgeRecord]:
        return iter(self._edges)


def main() -> None:
    current_revision = "a" * 40

    # A small, fully covered, fully affirmed design: one requirement, one
    # specification, one implementation, one passing outcome fresh against
    # the current revision.
    sreq = node("SREQ-1", "Requirement", ("contentHash",), seed="v1")
    spec = node("TS-1", "TestSpecification", ("specHash", "implHash"), seed="v1")
    impl = node("pkg.fn", "Implementation", ("apiHash", "bodyHash"), seed="v1")
    run = node(
        "run-1/TS-1",
        "TestOutcome",
        ("contentHash",),
        seed="v1",
        result=records.TestResult.PASSED,
        revision=current_revision,
    )
    nodes = (sreq, spec, impl, run)
    edges = (
        affirmed("Verifies", spec, sreq),
        affirmed("Implements", impl, sreq),
        evidence("Confirms", "run-1/TS-1", "TS-1"),
        evidence("Witnesses", "run-1/TS-1", "pkg.fn"),
    )
    built = graph.build(Producer(nodes, edges))

    # 1. Assemble is pure: collect the scope, judge it, build the four
    #    documents in memory. Nothing is written yet.
    package = proof.assemble(
        built,
        {"SREQ-1"},
        snapshot_timestamp=datetime.now(UTC),
        evaluation_date=date.today(),
        current_revision=current_revision,
    )
    print(f"scope total: {package.scope.total}")
    print(f"coverage report blocked: {package.coverage_report.blocked}")

    if package.documents is None:
        print("scope is blocked; nothing to persist")
        return

    # 2. Persist writes the four documents through the store's proof-document
    #    face, under proofs/{snapshot_id}/ in a throwaway case.
    store = AffirmationStore(root=Path(tempfile.mkdtemp()) / "case")
    written = proof.persist(package, store)
    for name, path in sorted(written.items()):
        print(f"wrote {name}: {path}")

    # 3. Read the package back and recompute the design consistency proof's
    #    own root from that one document alone — no graph in hand.
    read_back = store.read_package(package.scope.snapshot_id)
    design_proof = read_back[proof.DESIGN_CONSISTENCY_PROOF]
    node_hashes = (bytes.fromhex(entry["hash"]) for entry in design_proof["nodeManifest"])
    edge_tuples = ((e["from"], e["to"], e["kind"]) for e in design_proof["designEdges"])
    metadata = json.dumps(
        {
            "snapshotId": design_proof["snapshotId"],
            "scope": design_proof["scope"],
            "revision": design_proof["revision"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    recomputed = commitment.design_root(metadata, node_hashes, edge_tuples).hex()
    print(f"root as persisted:  {design_proof['root']}")
    print(f"root as recomputed: {recomputed}")
    print(f"the auditor's check: {'passes' if recomputed == design_proof['root'] else 'FAILS'}")


if __name__ == "__main__":
    main()
