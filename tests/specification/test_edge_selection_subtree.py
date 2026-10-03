"""Verification suite for edge selection inside a subtree.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Three
verbs share the selection: edge show, edge affirm and case remove. A selection
by subtree takes only the edges inside the subtree. Each test builds the
would-be store of ``subtree_support`` in ``tmp_path`` and runs
``affirmatrix.cli.main`` over it. Edge affirm gives a revision on the command
line, because the store has no repository. Every edge of the store is pending.

The expected sets of edges are written in ``subtree_support`` by hand. A test
that changes a case builds its own store, so no run sees the change of another.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from affirmatrix import proof

from . import subtree_support as support
from .provenance_support import red

_LEAK = "a selection by subtree also takes an edge that leaves the subtree"


def _requirement_endpoints(edges: set[support.Edge]) -> set[str]:
    """The requirement identifiers that the edges name, as source or as target."""
    ends = {end for _, source, target in edges for end in (source, target)}
    return {end for end in ends if end.startswith("REQ-")}


def _subtrees() -> dict[str, frozenset[str]]:
    return {
        support.TOP: support.SUBTREE_OF_TOP,
        support.MID: frozenset({support.MID, support.LEAF}),
    }


@red(345, _LEAK)
def test_the_subtree_is_the_requirement_and_every_requirement_that_refines_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A subtree selection reaches the requirement and every requirement that refines it.

    A store holds a chain of refinement, a requirement with a parent, and a
    requirement with two parents, one of them outside. Running edge show with
    a subtree selection for the top of the chain exits with status 0. The
    requirements that the listed edges name are the top, the requirement that
    refines it, the requirement that refines that one in turn, and the
    requirement with two parents. They are no others: not the parent of the
    top, not the second parent. The same holds for a subtree selection for
    the middle of the chain, which names the middle and the requirement below
    it.

    :verifies: SEG-SREQ-345
    :test-id: SEG-TS-335
    """
    world = support.build(tmp_path)
    for top, members in _subtrees().items():
        status, edges = support.show(world, capsys, "--below", top)
        assert status == 0, top
        assert _requirement_endpoints(edges) == members, top


def test_a_requirement_outside_the_subtree_adds_no_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sibling, and a requirement that refines only a requirement outside, add no edge.

    A store holds a sibling of the top, which refines the parent of the top, and
    a requirement that refines only a requirement outside the subtree. A test
    specification and an implementation relate to that requirement alone.
    Running edge show with a subtree selection for the top exits with status 0.
    No listed edge has the sibling, the requirement that refines only a
    requirement outside, or the test specification or implementation that
    relate to that requirement alone, as an endpoint.

    :verifies: SEG-SREQ-345
    :test-id: SEG-TS-336
    """
    world = support.build(tmp_path)
    status, edges = support.show(world, capsys, "--below", support.TOP)
    assert status == 0
    named = {end for _, source, target in edges for end in (source, target)}
    assert named.isdisjoint({"REQ-SIBLING", "REQ-OUTSIDE-CHILD", "TS-OUTSIDE", "IMP-OUTSIDE"})
    assert edges, "the selection is not empty, so the check above can fail"


@red(346, _LEAK)
def test_edge_show_lists_a_refines_edge_only_when_both_ends_are_in_the_subtree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edge show lists a Refines edge in a subtree only when both of its ends are in it.

    A store holds a top with a parent, a chain of refinement below the top, and
    a requirement that refines the top and a second requirement outside the
    subtree. Running edge show with a subtree selection for the top exits with
    status 0. The listed Refines edges are the three between two members: the
    middle refines the top, the leaf refines the middle, and the requirement
    with two parents refines the top. The edge from the top to its parent is
    not listed. The edge from the requirement with two parents to its second
    parent is not listed.

    :verifies: SEG-SREQ-346
    :test-id: SEG-TS-337
    """
    world = support.build(tmp_path)
    status, edges = support.show(world, capsys, "--below", support.TOP, "--kind", "Refines")
    assert status == 0
    assert edges == {edge for edge in support.INSIDE_TOP if edge[0] == "Refines"}


@red(346, _LEAK)
def test_edge_affirm_affirms_only_the_edges_inside_the_subtree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edge affirm with a subtree selection affirms only the edges inside the subtree.

    A store holds the shape of the earlier specifications, and the case is
    empty. Running edge affirm with a subtree selection for the top, a
    revision and a role exits with status 0. The case then holds a review
    event for each of the seven edges inside the subtree, and for no other
    edge. It holds no review event for the edge from the top to its parent,
    nor for the edge from a member to a second parent outside.

    :verifies: SEG-SREQ-346
    :test-id: SEG-TS-338
    """
    world = support.build(tmp_path)
    status, _ = support.affirm(world, capsys, "--below", support.TOP)
    assert status == 0
    assert support.affirmed_edges(world) == support.INSIDE_TOP


@red(346, _LEAK)
def test_case_remove_removes_only_the_edges_inside_the_subtree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case remove with a subtree selection removes only the edges inside the subtree.

    A case holds the records of the shape of the earlier specifications, written
    by case sync. Running case remove with a subtree selection for the top
    exits with status 0. The edge records that the case holds afterwards are
    all the edges of the store, less the seven edges inside the subtree. The
    edge from the top to its parent is still held, and so is the edge from a
    member to a second parent outside.

    :verifies: SEG-SREQ-346
    :test-id: SEG-TS-339
    """
    world = support.build(tmp_path)
    support.sync(world, capsys)
    assert support.held_edges(world) == support.all_edges()
    status, _ = support.remove(world, capsys, "--below", support.TOP)
    assert status == 0
    assert support.held_edges(world) == support.all_edges() - support.INSIDE_TOP


def test_a_verifies_or_implements_edge_is_in_the_subtree_by_the_requirement_it_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Verifies or Implements edge is selected by the requirement that it names.

    One test specification verifies a requirement inside the subtree and one
    outside, and one implementation implements a requirement inside and one
    outside. A selection by subtree for the top, with edge show, edge affirm
    and case remove in turn, takes the Verifies and Implements edges that name
    a requirement inside, and no other Verifies or Implements edge. The test
    specification and the implementation that relate to both sides give one
    selected edge and one edge that is not selected. A test specification and
    an implementation of the subtree that name a requirement outside are not
    selected either.

    :verifies: SEG-SREQ-347
    :test-id: SEG-TS-340
    """
    inside = {edge for edge in support.INSIDE_TOP if edge[0] != "Refines"}
    assert len(inside) == 4
    shown = support.build(tmp_path / "show")
    status, edges = support.show(shown, capsys, "--below", support.TOP)
    assert status == 0
    assert {edge for edge in edges if edge[0] != "Refines"} == inside

    affirmed = support.build(tmp_path / "affirm")
    status, _ = support.affirm(affirmed, capsys, "--below", support.TOP)
    assert status == 0
    assert {edge for edge in support.affirmed_edges(affirmed) if edge[0] != "Refines"} == inside

    removed = support.build(tmp_path / "remove")
    support.sync(removed, capsys)
    status, _ = support.remove(removed, capsys, "--below", support.TOP)
    assert status == 0
    left = support.held_edges(removed)
    assert {edge for edge in support.all_edges() - left if edge[0] != "Refines"} == inside


@red(347, _LEAK)
def test_a_leaf_requirement_selects_its_verifies_and_implements_edges_and_no_refines_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A leaf requirement selects the Verifies and Implements edges it names, and no Refines edge.

    A leaf requirement refines one requirement, has one test specification that
    verifies it and one implementation that implements it. Running edge show
    with a subtree selection for the leaf exits with status 0. The listed edges
    are the Verifies edge and the Implements edge of the leaf. The Refines edge
    from the leaf to its parent is not listed.

    :verifies: SEG-SREQ-347
    :test-id: SEG-TS-341
    """
    world = support.build(tmp_path)
    status, edges = support.show(world, capsys, "--below", support.LEAF)
    assert status == 0
    assert edges == {
        ("Verifies", "TS-LEAF", "REQ-LEAF"),
        ("Implements", "IMP-LEAF", "REQ-LEAF"),
    }


@red(346, _LEAK)
def test_a_subtree_below_a_requirement_that_is_not_a_top_leaves_out_its_own_refines_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A subtree selection for a requirement that has a parent leaves out its edge to the parent.

    The middle requirement of a chain refines the top, and the leaf refines the
    middle. In turn, edge show, edge affirm and case remove run with a
    subtree selection for the middle requirement, each over its own store.
    Each exits with status 0. Each takes four edges: the edge from the leaf to
    the middle, the Verifies edge and the Implements edge of the leaf, and the
    Implements edge of the middle. None takes the edge from the middle
    requirement to the top. The edge from the middle to the top is the one the
    selection leaves out, whichever verb runs.

    :verifies: SEG-SREQ-346
    :test-id: SEG-TS-342
    """
    own_edge = ("Refines", support.MID, support.TOP)
    shown = support.build(tmp_path / "show")
    status, edges = support.show(shown, capsys, "--below", support.MID)
    assert status == 0
    assert edges == support.INSIDE_MID
    affirmed = support.build(tmp_path / "affirm")
    status, _ = support.affirm(affirmed, capsys, "--below", support.MID)
    assert status == 0
    assert support.affirmed_edges(affirmed) == support.INSIDE_MID
    assert own_edge not in support.affirmed_edges(affirmed)
    removed = support.build(tmp_path / "remove")
    support.sync(removed, capsys)
    status, _ = support.remove(removed, capsys, "--below", support.MID)
    assert status == 0
    assert support.held_edges(removed) == support.all_edges() - support.INSIDE_MID
    assert own_edge in support.held_edges(removed)


def test_a_subtree_selection_for_an_unknown_requirement_matches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A subtree selection for a requirement the store does not hold matches no edge.

    The same store, and a requirement name that no node carries. Running edge
    show, edge affirm and case remove in turn with a subtree selection for
    that name each exit with status 2, a request that could not be judged. Edge
    affirm records no review event. Case remove removes no edge record.

    :verifies: SEG-SREQ-103
    :test-id: SEG-TS-343
    """
    world = support.build(tmp_path)
    support.sync(world, capsys)
    status, edges = support.show(world, capsys, "--below", "REQ-NO-SUCH")
    assert (status, edges) == (2, set())
    status, _ = support.affirm(world, capsys, "--below", "REQ-NO-SUCH")
    assert status == 2
    assert support.affirmed_edges(world) == set()
    status, _ = support.remove(world, capsys, "--below", "REQ-NO-SUCH")
    assert status == 2
    assert support.held_edges(world) == support.all_edges()


@red(346, _LEAK)
def test_the_edges_of_a_subtree_selection_are_the_edges_that_the_proof_scope_cuts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The edges of a subtree selection are the edges that a proof scope of that requirement holds.

    The store holds only strong edges, and the nodes that they join. Edge show
    runs with a subtree selection for the top, and again for the middle of the
    chain. The proof generator collects the scope of the same requirement over
    the graph of the same store, and it holds the edges that join two members
    of the scope. For each of the two requirements, the edges that edge show
    lists are the edges of that scope, no more and no fewer. This is the
    reason a selection takes only the edges inside: it answers what a proof of
    the requirement would hold.

    :verifies: SEG-SREQ-346
    :test-id: SEG-TS-344
    """
    world = support.build(tmp_path)
    built = support.built_graph(world)
    moment = datetime(2026, 10, 1, tzinfo=UTC)
    for requirement in (support.TOP, support.MID):
        scope = proof.collect_scope(built, [requirement], snapshot_timestamp=moment)
        collected = {(edge.kind, edge.from_id, edge.to_id) for edge in scope.subgraph.edges}
        status, edges = support.show(world, capsys, "--below", requirement)
        assert status == 0
        assert collected, requirement
        assert edges == collected, requirement
