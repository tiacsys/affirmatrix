"""The edge selection grammar (SEG-SREQ-099…104)."""

from __future__ import annotations

from affirmatrix import graph
from affirmatrix.cli import _selector
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord


def _pending(from_id: str, to_id: str, kind: str = "Refines") -> EdgeRecord:
    return EdgeRecord(from_id=from_id, to_id=to_id, kind=kind, state=LinkState.PENDING)


class _Source:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def _built_graph():
    from affirmatrix.records import ContentAnchor

    def node(local_id: str) -> NodeRecord:
        return NodeRecord(
            local_id, "Requirement", {"contentHash": ContentAnchor(b"0" * 32, "r", "p", "file")}
        )

    nodes = [node("A"), node("B"), node("C"), node("D")]
    edges = [_pending("B", "A"), _pending("C", "B"), _pending("D", "A", kind="Verifies")]
    return graph.build(_Source(nodes, edges))


def test_kind_narrows_the_selection() -> None:
    built = _built_graph()
    matched = _selector.select(built.edges, _selector.Selector(kind="Verifies"), built)
    assert [e.kind for e in matched] == ["Verifies"]


def test_endpoints_narrow_the_selection() -> None:
    built = _built_graph()
    matched = _selector.select(
        built.edges, _selector.Selector(from_id="C", to_id="B"), built
    )
    assert [(e.from_id, e.to_id) for e in matched] == [("C", "B")]


def test_kind_and_both_endpoints_select_at_most_one() -> None:
    """SEG-SREQ-101."""
    built = _built_graph()
    matched = _selector.select(
        built.edges, _selector.Selector(kind="Refines", from_id="B", to_id="A"), built
    )
    assert len(matched) == 1


def test_a_selector_matching_nothing_returns_empty() -> None:
    built = _built_graph()
    matched = _selector.select(built.edges, _selector.Selector(kind="Excuses"), built)
    assert matched == []


def test_below_narrows_to_the_subtree() -> None:
    """C refines B refines A: --below A reaches every edge touching A, B, or C."""
    built = _built_graph()
    matched = _selector.select(built.edges, _selector.Selector(below="A"), built)
    assert {(e.from_id, e.to_id) for e in matched} == {("B", "A"), ("C", "B"), ("D", "A")}


def test_an_empty_selector_matches_everything() -> None:
    built = _built_graph()
    matched = _selector.select(built.edges, _selector.Selector(), built)
    assert len(matched) == 3


def test_is_empty_is_true_only_when_every_field_is_absent() -> None:
    assert _selector.Selector().is_empty()
    assert not _selector.Selector(kind="Refines").is_empty()


def test_the_four_fields_are_registered_as_separate_options() -> None:
    """SEG-SREQ-102: never one combined token."""
    import argparse

    parser = argparse.ArgumentParser()
    _selector.add_selector_arguments(parser)
    args = parser.parse_args(["--kind", "Refines", "--from", "a", "--to", "b", "--below", "c"])
    selector = _selector.selector_from_args(args)
    assert selector == _selector.Selector(kind="Refines", from_id="a", to_id="b", below="c")
