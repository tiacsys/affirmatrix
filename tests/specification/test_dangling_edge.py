"""Verification suite for an edge that touches an absent node.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
suspect detector decides that an edge whose endpoint is absent from the current
records is broken. The graph builder keeps that decision for an edge that was
never affirmed: it reports such an edge as broken, and every other edge that
was never affirmed as pending. ``graph status`` then lists a dangling strong
edge as broken and exits with status 1, and it counts a dangling evidence edge.

The library tests build graphs from literal records. The command-line tests use
a small would-be store, given with ``--current``, whose content directory is a
git repository (see ``evidence_support.make_world``). A dangling strong edge
there is an Implements edge from an implementation the store does not hold. A
dangling evidence edge is a Confirms edge to a specification the store does not
hold. No test reads a name the code does not have today, except inside a test
body, so this module collects before the code carries the change.

A proof scope is collected over the nodes that are present, so a dangling edge
never lies in the scope of a command-line proof check. The proof test therefore
builds its graph from literal records and calls the gate directly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from affirmatrix import drift, gates, graph, records
from affirmatrix.records import LinkState

from .evidence_support import make_world, run


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def _requirement(local_id: str) -> records.NodeRecord:
    anchor = records.ContentAnchor(
        digest=hashlib.sha256(local_id.encode()).digest(),
        repository="the-source-repo",
        path="pkg/module.py",
        locator="file",
    )
    return records.NodeRecord(local_id, "Requirement", {"contentHash": anchor})


def _strong_rows(document: dict) -> dict[tuple[str, str, str], str]:
    strong = {"Refines", "Verifies", "Implements"}
    return {
        (r["kind"], r["from"], r["to"]): r["state"]
        for r in document["edges"]
        if r["kind"] in strong
    }


def test_the_builder_keeps_a_broken_edge_that_was_never_affirmed() -> None:
    """The graph builder reports a never-affirmed edge its record reports as broken as broken.

    The builder gets two requirements and a Refines edge between them. The
    record of the edge carries no hash and claims the state broken. The built
    graph reports the edge as broken, and it still carries no hash.

    :verifies: SEG-SREQ-016
    :test-id: SEG-TS-104
    """
    source = Source(
        [_requirement("SREQ-1"), _requirement("SYS-1")],
        [records.EdgeRecord("SREQ-1", "SYS-1", "Refines", LinkState.BROKEN)],
    )

    (edge,) = graph.build(source).edges

    assert edge.state is LinkState.BROKEN
    assert edge.edge_hash is None


def test_the_builder_still_resets_other_unaffirmed_edges_to_pending() -> None:
    """The graph builder reports every other never-affirmed edge as pending.

    The builder gets three requirements and three edges. A Refines edge carries
    no hash and claims the state directly outdated. A second Refines edge is
    pending. A third carries the hash it was affirmed against and the state
    active. The built graph reports the first two as pending, and the third as
    active with its hash.

    :verifies: SEG-SREQ-016
    :test-id: SEG-TS-105
    """
    digest = hashlib.sha256(b"an edge hash, not recomputed here").digest()
    source = Source(
        [_requirement("A"), _requirement("B"), _requirement("C")],
        [
            records.EdgeRecord("A", "B", "Refines", LinkState.DIRECTLY_OUTDATED),
            records.EdgeRecord("B", "C", "Refines", LinkState.PENDING),
            records.EdgeRecord("A", "C", "Refines", LinkState.ACTIVE, digest),
        ],
    )

    built = graph.build(source)

    by_pair = {(e.from_id, e.to_id): e for e in built.edges}
    assert by_pair[("A", "B")].state is LinkState.PENDING
    assert by_pair[("B", "C")].state is LinkState.PENDING
    assert by_pair[("A", "C")].state is LinkState.ACTIVE
    assert by_pair[("A", "C")].edge_hash == digest


def test_a_never_affirmed_edge_to_an_absent_node_is_broken_after_the_derivation_and_the_build() -> (
    None
):
    """A never-affirmed edge to an absent node is broken in the graph built from the derivation.

    The current records hold one requirement and a Refines edge from it to a
    requirement that the records lack. The recorded records are empty. The
    suspect detector derives the edge and the builder builds the derived
    records. The built graph reports the edge as broken.

    :verifies: SEG-SREQ-016
    :test-id: SEG-TS-106
    """
    current = Source(
        [_requirement("SREQ-1")],
        [records.EdgeRecord("SREQ-1", "SYS-GONE", "Refines", LinkState.PENDING)],
    )

    derivation = drift.derive(recorded=Source(), current=current)
    (edge,) = graph.build(derivation).edges

    assert edge.state is LinkState.BROKEN


def test_graph_status_lists_a_dangling_strong_edge_as_broken_and_exits_1(
    tmp_path: Path, capsys
) -> None:
    """A never-affirmed strong edge to an absent node is a broken row and gives exit status 1.

    The current stream is a store with a Verifies edge and an Implements edge
    between present nodes, and a second Implements edge from an implementation
    the store does not hold. Nothing is affirmed. Graph status lists the
    second Implements edge as broken, lists the other two edges as pending, and
    exits with status 1. The same store without the second Implements edge
    exits with status 0 and lists two pending edges.

    :verifies: SEG-SREQ-083
    :test-id: SEG-TS-107
    """
    sound = make_world(tmp_path / "sound", outcomes=())
    status, out = run(capsys, "graph", "status", "--json", *sound.args())
    assert status == 0
    assert set(_strong_rows(json.loads(out)).values()) == {"pending"}

    dangling = make_world(tmp_path / "dangling", outcomes=(), dangling_strong=True)
    status, out = run(capsys, "graph", "status", "--json", *dangling.args())

    assert status == 1
    assert _strong_rows(json.loads(out)) == {
        ("Verifies", "TS-1", "SREQ-1"): "pending",
        ("Implements", "pkg.fn", "SREQ-1"): "pending",
        ("Implements", "pkg.gone", "SREQ-1"): "broken",
    }


def test_graph_status_lists_an_affirmed_edge_whose_endpoint_left_as_broken(
    tmp_path: Path, capsys
) -> None:
    """An affirmed strong edge whose endpoint leaves the stream is a broken row and gives exit 1.

    One Verifies edge is affirmed over a store. The store is then changed so
    that it no longer holds the requirement the edge ends at. Graph status
    lists the Verifies edge as broken and exits with status 1.

    :verifies: SEG-SREQ-083
    :test-id: SEG-TS-108
    """
    world = make_world(tmp_path, outcomes=())
    status, _ = run(
        capsys,
        "edge",
        "affirm",
        *world.args(),
        "--kind",
        "Verifies",
        "--from",
        "TS-1",
        "--to",
        "SREQ-1",
        "--role",
        "fixture-reviewer",
        "--reason",
        "",
    )
    assert status == 0
    nodes = world.store / "nodes" / "requirements.toml"
    nodes.write_text(
        nodes.read_text(encoding="utf-8").replace('"SREQ-1"', '"SREQ-9"'), encoding="utf-8"
    )

    status, out = run(capsys, "graph", "status", "--json", *world.args())

    assert status == 1
    assert _strong_rows(json.loads(out))[("Verifies", "TS-1", "SREQ-1")] == "broken"


def test_graph_status_counts_a_dangling_confirms_edge_and_exits_1(tmp_path: Path, capsys) -> None:
    """A Confirms edge to an absent specification gives exit status 1 and one dangling count.

    The current stream is a store with one outcome recorded at the revision of
    the implementation repository, its Confirms and Witnesses edges, and a
    second Confirms edge to a specification the store does not hold. Graph
    status runs with that revision. It exits with status 1. Its evidence
    section counts one outcome at the current revision, no outcome at another
    revision and one dangling edge.

    :verifies: SEG-SREQ-083
    :test-id: SEG-TS-109
    """
    world = make_world(tmp_path, outcomes=("head",), absent_specification=True)

    status, out = run(capsys, "graph", "status", "--json", *world.args(), "--revision", world.head)

    assert status == 1
    assert json.loads(out)["evidence"] == {"current": 1, "stale": 0, "dangling": 1}


def test_graph_status_lists_pending_strong_edges_as_pending_and_exits_0(
    tmp_path: Path, capsys
) -> None:
    """Never-affirmed strong edges between present nodes are pending rows and give exit status 0.

    The current stream is a store with an outcome and its evidence edges, one
    Verifies edge and one Implements edge, all endpoints present, nothing
    affirmed, and a clean implementation repository that the configuration
    names. Graph status lists both strong edges as pending and exits with
    status 0.

    :verifies: SEG-SREQ-082
    :test-id: SEG-TS-110
    """
    world = make_world(tmp_path, outcomes=("head",))

    status, out = run(capsys, "graph", "status", "--json", *world.args())

    assert status == 0
    assert _strong_rows(json.loads(out)) == {
        ("Verifies", "TS-1", "SREQ-1"): "pending",
        ("Implements", "pkg.fn", "SREQ-1"): "pending",
    }


def test_the_gate_names_a_broken_strong_edge_as_broken() -> None:
    """The gate lists a broken strong edge as not ready, with the detail broken.

    The built graph holds two requirements and a Refines edge between them that
    carries no hash and whose record reports the state broken. The package gate
    lists that edge among its unready edges, in the state broken, and gives its
    finding the detail broken. The report is blocked.

    :verifies: SEG-SREQ-016
    :test-id: SEG-TS-111
    """
    built = graph.build(
        Source(
            [_requirement("SREQ-1"), _requirement("SYS-1")],
            [records.EdgeRecord("SREQ-1", "SYS-1", "Refines", LinkState.BROKEN)],
        )
    )

    report = gates.package_gate(
        built, evaluation_date=date(2026, 6, 1), current_revision="a-revision"
    )

    (edge,) = report.unready_edges
    assert edge.state is LinkState.BROKEN
    details = [d.detail for d in report.diagnostics if d.subject == "SREQ-1 -> SYS-1 (Refines)"]
    assert details == ["broken"]
    assert report.blocked


def test_case_sync_writes_a_dangling_edge_as_broken_and_writes_pending_when_the_node_returns(
    tmp_path: Path, capsys
) -> None:
    """Case sync stores a dangling edge as broken, and as pending once the node returns.

    The current stream is a store whose Implements edge starts at an
    implementation the store does not hold. Case sync exits with status 0 and
    the stored edge document holds that edge in the state broken, with no
    hash. The store then gains that implementation. The next case sync exits
    with status 0 and the stored edge is pending, with no hash.

    :verifies: SEG-SREQ-072
    :test-id: SEG-TS-112
    """
    world = make_world(tmp_path, outcomes=(), dangling_strong=True)
    document = world.case / "edges" / "implements.jsonld"

    def stored() -> dict:
        entries = json.loads(document.read_text(encoding="utf-8"))["@graph"]
        (entry,) = [e for e in entries if e["seg:from"].endswith("/pkg.gone")]
        return entry

    assert run(capsys, "case", "sync", *world.args())[0] == 0
    assert stored()["seg:linkState"] == "broken"
    assert "seg:edgeHash" not in stored()

    nodes = world.store / "nodes" / "implementations.toml"
    with nodes.open("a", encoding="utf-8") as handle:
        handle.write('"pkg.gone" = { apiHash = "api.txt", bodyHash = "body.txt" }\n')

    assert run(capsys, "case", "sync", *world.args())[0] == 0
    assert stored()["seg:linkState"] == "pending"
    assert "seg:edgeHash" not in stored()
