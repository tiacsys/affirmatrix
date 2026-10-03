"""Verification suite for edge selection by subtree over edges of every kind.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
selection by subtree names a requirement. It admits the Refines, Verifies and
Implements edges inside the subtree and no edge of another kind. When the node
it names is not a requirement of the graph, it admits no edge, and the request
fails with status 2 like any selection that matches nothing.

The store of ``evidence_edge_support`` holds, with the requirements, the
implementations and the test specifications of ``subtree_support``, a test
outcome and the edges of the evidence kinds. The first tests run the three verbs
that share the selection over that store. The tests at the end call ``select``
over a graph that they build in memory from literal records.

Each test that changes a case builds its own store. Edge affirm gives a revision
and a synthetic role.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from affirmatrix import graph, records
from affirmatrix.cli._selector import Selector, select
from affirmatrix.records import LinkState

from . import evidence_edge_support as evidence
from . import subtree_support as support

#: The edges of the store that a case holds: all but the kinds that no case holds.
HELD = frozenset(edge for edge in evidence.everything() if edge[0] not in ("Confirms", "Witnesses"))
#: A node of each kind that is not a requirement, and a name that no node carries.
NOT_REQUIREMENTS = (
    evidence.SPECIFICATION,
    evidence.IMPLEMENTATION,
    evidence.OUTCOME,
    "REQ-NO-SUCH",
    evidence.DECOY,
)


def test_a_subtree_selection_shows_only_refines_verifies_and_implements_edges(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edge show with a subtree selection for a requirement lists no edge of an evidence kind.

    A store holds the shape of the earlier specifications. It also holds an
    outcome, a Confirms edge from the outcome to a test specification, a
    Witnesses edge from it to an implementation, and a Calls edge between two
    implementations. It holds three more edges of those kinds that have a
    requirement of the subtree at one end: a Confirms edge to the leaf, a
    Witnesses edge to the middle requirement and a Calls edge to the leaf. Edge
    show with a subtree selection for the top, for the middle requirement and for
    the leaf each exits with status 0. The listed edges are the Refines,
    Verifies and Implements edges inside the subtree, as for the store without
    the additions, and no listed edge has the kind Confirms, Witnesses or Calls.

    :verifies: SEG-SREQ-371
    :test-id: SEG-TS-366
    """
    world = evidence.build(tmp_path)
    expected = {
        support.TOP: support.INSIDE_TOP,
        support.MID: support.INSIDE_MID,
        support.LEAF: evidence.INSIDE_LEAF,
    }
    for requirement, inside in expected.items():
        status, edges = support.show(world, capsys, "--below", requirement)
        assert status == 0, requirement
        assert edges == inside, requirement


def test_case_remove_with_a_subtree_selection_removes_only_the_three_kinds_of_a_subtree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case remove with a subtree selection for a requirement leaves an edge of another kind.

    The case holds the records of the store of the earlier specifications,
    written by case sync, and so holds the Calls edge that has the leaf at one
    end and the Calls edge between two implementations. Case remove with a
    subtree selection for the top exits with status 0. The edge records that the
    case holds afterwards are those held before, less the seven edges inside the
    subtree. Both Calls edges are still held.

    :verifies: SEG-SREQ-371
    :test-id: SEG-TS-367
    """
    world = evidence.build(tmp_path)
    support.sync(world, capsys)
    assert support.held_edges(world) == HELD
    status, _ = support.remove(world, capsys, "--below", support.TOP)
    assert status == 0
    assert support.held_edges(world) == HELD - support.INSIDE_TOP
    assert ("Calls", evidence.IMPLEMENTATION, support.LEAF) in support.held_edges(world)


def _in_memory(edges: list[records.EdgeRecord]) -> graph.Graph:
    """A graph over a requirement, a refiner, a specification, two implementations, an outcome."""
    names = {
        "REQ-A": ("Requirement", ("contentHash",)),
        "REQ-B": ("Requirement", ("contentHash",)),
        "TS-1": ("TestSpecification", ("specHash", "implHash")),
        "IMP-1": ("Implementation", ("apiHash", "bodyHash")),
        "IMP-2": ("Implementation", ("apiHash", "bodyHash")),
        "OUT-1": ("TestOutcome", ("contentHash",)),
    }
    nodes = []
    for local_id, (kind, fields) in names.items():
        anchors = {
            field: records.ContentAnchor(
                digest=hashlib.sha256(f"{local_id}.{field}".encode()).digest(),
                repository="the-source-repo",
                path="pkg/module.py",
                locator="file",
            )
            for field in fields
        }
        extra = (
            {"result": records.TestResult.PASSED, "revision": "r1"} if kind == "TestOutcome" else {}
        )
        nodes.append(records.NodeRecord(local_id, kind, anchors, **extra))

    class Source:
        def nodes(self):
            return iter(nodes)

        def edges(self):
            return iter(edges)

    return graph.build(Source())


def _edge(kind: str, source: str, target: str) -> records.EdgeRecord:
    return records.EdgeRecord(source, target, kind, LinkState.PENDING)


def test_select_admits_no_edge_of_a_kind_outside_the_three_for_a_subtree() -> None:
    """The selection function takes no Confirms, Witnesses, Calls or Excuses edge by subtree.

    A graph holds a requirement, a requirement that refines it, a test
    specification, two implementations and an outcome. It holds one Refines
    edge, one Verifies edge and one Implements edge inside the subtree of the
    first requirement. It also holds, for each of the kinds Confirms, Witnesses,
    Calls and Excuses, one edge that has a requirement of the subtree as its
    source and one that has it as its target. Selecting by the subtree of the
    first requirement returns the three edges of the three kinds, and no other.
    Selecting by kind and subtree together for each of the four other kinds
    returns no edge.

    :verifies: SEG-SREQ-371
    :test-id: SEG-TS-368
    """
    strong = [
        _edge("Refines", "REQ-B", "REQ-A"),
        _edge("Verifies", "TS-1", "REQ-A"),
        _edge("Implements", "IMP-1", "REQ-A"),
    ]
    others = []
    for kind in ("Confirms", "Witnesses", "Calls", "Excuses"):
        others.append(_edge(kind, "OUT-1", "REQ-B"))
        others.append(_edge(kind, "REQ-A", "IMP-2"))
    built = _in_memory([*strong, *others])

    chosen = select([*strong, *others], Selector(below="REQ-A"), built)
    assert sorted((e.kind, e.from_id, e.to_id) for e in chosen) == sorted(
        (e.kind, e.from_id, e.to_id) for e in strong
    )
    for kind in ("Confirms", "Witnesses", "Calls", "Excuses"):
        assert select(others, Selector(below="REQ-A", kind=kind), built) == []


def test_edge_show_below_a_node_that_is_not_a_requirement_matches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edge show with a subtree selection for a node that is not a requirement lists no edge.

    The store holds a test specification, an implementation and an outcome, each
    with edges of an evidence kind, and a requirement that is the far end of a
    refinement edge only, which no node of the store carries. Edge show with a
    subtree selection for the test specification, for the implementation, for
    the outcome, for a name that no node carries, and for the name that is the
    far end of the broken refinement edge each lists no edge and exits with
    status 2.

    :verifies: SEG-SREQ-372
    :test-id: SEG-TS-369
    """
    world = evidence.build(tmp_path)
    for name in NOT_REQUIREMENTS:
        status, edges = support.show(world, capsys, "--below", name)
        assert (status, edges) == (2, set()), name


def test_edge_affirm_below_a_node_that_is_not_a_requirement_affirms_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edge affirm with a subtree selection for a node that is not a requirement fails.

    The same store, and an empty case. Edge affirm with a revision, a synthetic
    role and a subtree selection for the test specification, for the
    implementation, for the outcome and for the far end of the broken
    refinement edge each exits with status 2. The case holds no review event
    after any of them.

    :verifies: SEG-SREQ-372
    :test-id: SEG-TS-370
    """
    for name in (evidence.SPECIFICATION, evidence.IMPLEMENTATION, evidence.OUTCOME, evidence.DECOY):
        world = evidence.build(tmp_path / name)
        status, _ = support.affirm(world, capsys, "--below", name)
        assert status == 2, name
        assert support.affirmed_edges(world) == set(), name


def test_case_remove_below_a_node_that_is_not_a_requirement_removes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case remove with a subtree selection for a node that is not a requirement fails.

    The case holds the records of the store, written by case sync. It holds a
    Calls edge between two implementations, and the broken refinement edge. Case
    remove with a subtree selection for the implementation, for the test
    specification, for the outcome and for the far end of the broken refinement
    edge each exits with status 2. The case holds the same edge records after
    each of them.

    :verifies: SEG-SREQ-372
    :test-id: SEG-TS-371
    """
    world = evidence.build(tmp_path)
    support.sync(world, capsys)
    assert support.held_edges(world) == HELD
    for name in (evidence.IMPLEMENTATION, evidence.SPECIFICATION, evidence.OUTCOME, evidence.DECOY):
        status, _ = support.remove(world, capsys, "--below", name)
        assert status == 2, name
        assert support.held_edges(world) == HELD, name


def test_select_by_the_subtree_of_a_node_that_is_not_a_requirement_returns_no_edge() -> None:
    """The selection function takes no edge by the subtree of an outcome or any other node.

    A graph holds a requirement and the nodes of the other kinds: a test
    specification, two implementations and an outcome. It holds a Confirms edge
    from the outcome to the test specification, a Witnesses edge from the outcome
    to an implementation, a Calls edge between the implementations, and the
    Verifies and Implements edges of the requirement. Selecting by the subtree
    of the outcome, of the test specification, of each implementation, and of a
    name that no node carries returns no edge.

    :verifies: SEG-SREQ-372
    :test-id: SEG-TS-372
    """
    edges = [
        _edge("Confirms", "OUT-1", "TS-1"),
        _edge("Witnesses", "OUT-1", "IMP-1"),
        _edge("Calls", "IMP-1", "IMP-2"),
        _edge("Verifies", "TS-1", "REQ-A"),
        _edge("Implements", "IMP-1", "REQ-A"),
    ]
    built = _in_memory(edges)
    for name in ("OUT-1", "TS-1", "IMP-1", "IMP-2", "REQ-NO-SUCH"):
        assert select(edges, Selector(below=name), built) == [], name


def test_a_requirement_with_no_refiner_selects_its_verifies_and_implements_edges(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A subtree selection for a requirement that nothing refines still takes its two edges.

    The store holds a requirement that no requirement refines and that refines
    no requirement, one test specification that verifies it and one
    implementation that implements it, beside the outcome and the edges of the
    evidence kinds. Edge show with a subtree selection for that requirement exits
    with status 0 and lists the Verifies edge and the Implements edge. Case
    remove with the same selection exits with status 0 and removes those two
    edges and no other.

    :verifies: SEG-SREQ-347
    :verifies: SEG-SREQ-372
    :test-id: SEG-TS-373
    """
    world = evidence.build(tmp_path)
    status, edges = support.show(world, capsys, "--below", evidence.NO_REFINERS)
    assert (status, edges) == (0, evidence.INSIDE_ALONE)
    support.sync(world, capsys)
    status, _ = support.remove(world, capsys, "--below", evidence.NO_REFINERS)
    assert status == 0
    assert support.held_edges(world) == HELD - evidence.INSIDE_ALONE
