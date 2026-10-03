"""The edge selection grammar shared by show, affirm, and remove (SEG-SREQ-099…104, 345…347).

One grammar of narrowing fields — kind, either endpoint, and subtree — rather
than a distinct address form per verb. A subtree selects the edges that lie
inside it: a refinement edge when both its ends are members, a verifies or
implements edge by the requirement it names. A selector with every field absent
is still an edge selection: it names every edge, which ``edge show`` and
``case remove`` may legitimately act on but ``edge affirm`` refuses
(SEG-SREQ-104) as a distinct rule of its own verb, not this grammar's.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass

from affirmatrix.graph import Graph
from affirmatrix.records import EdgeRecord

_REFINES = "Refines"
_BY_REQUIREMENT = frozenset({"Verifies", "Implements"})


@dataclass(frozen=True, slots=True)
class Selector:
    """One edge selection, as the four narrowing fields that build it.

    :implements: SEG-SREQ-099

    Kind, source, target, and subtree ("below") are separate values
    (SEG-SREQ-102); every combination narrows the set the others admit
    (SEG-SREQ-100), and kind together with both endpoints narrows to at most
    one edge (SEG-SREQ-101), because that triple is an edge's own identity.
    """

    kind: str | None = None
    from_id: str | None = None
    to_id: str | None = None
    below: str | None = None

    def is_empty(self) -> bool:
        """Whether no field narrows at all — a selection naming every edge."""
        return (
            self.kind is None and self.from_id is None and self.to_id is None and self.below is None
        )


def add_selector_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the selector's four fields as separate options.

    :implements: SEG-SREQ-102

    ``--kind --from --to --below``, never a joined token: argparse gives
    each its own flag, so a selector cannot be built any other way.
    """
    parser.add_argument("--kind", help="the edge kind to narrow to")
    parser.add_argument("--from", dest="from_id", help="the source endpoint's identifier")
    parser.add_argument("--to", dest="to_id", help="the target endpoint's identifier")
    parser.add_argument("--below", help="the identifier whose refinement subtree narrows to")


def selector_from_args(args: argparse.Namespace) -> Selector:
    """The selector an argparse namespace's four fields build."""
    return Selector(kind=args.kind, from_id=args.from_id, to_id=args.to_id, below=args.below)


def select(edges: Iterable[EdgeRecord], selector: Selector, graph: Graph) -> list[EdgeRecord]:
    """Every edge the selector's narrowing fields admit, in a stable order.

    :implements: SEG-SREQ-100
    :implements: SEG-SREQ-101
    :implements: SEG-SREQ-345
    :implements: SEG-SREQ-346
    :implements: SEG-SREQ-347

    ``graph`` is consulted only when ``below`` narrows by subtree; the other
    three fields are plain equality over the edge's own kind and endpoints.
    The subtree admits an edge by :func:`_inside`: an edge that leaves the
    subtree, such as the one from its top to its own parent, is not selected.
    """
    subtree = _subtree_ids(graph, selector.below) if selector.below is not None else None
    matched = [
        edge
        for edge in edges
        if (selector.kind is None or edge.kind == selector.kind)
        and (selector.from_id is None or edge.from_id == selector.from_id)
        and (selector.to_id is None or edge.to_id == selector.to_id)
        and (subtree is None or _inside(edge, subtree))
    ]
    matched.sort(key=lambda edge: (edge.kind, edge.from_id, edge.to_id))
    return matched


def _inside(edge: EdgeRecord, subtree: frozenset[str]) -> bool:
    """Whether the edge lies inside the subtree.

    A refinement edge lies inside when both its ends are members. A verifies
    or implements edge lies inside by the requirement it names, which is its
    target, whichever subtree the test specification or the implementation
    belongs to. Any other kind keeps the plain rule: one end is a member.
    """
    if edge.kind == _REFINES:
        return edge.from_id in subtree and edge.to_id in subtree
    if edge.kind in _BY_REQUIREMENT:
        return edge.to_id in subtree
    return edge.from_id in subtree or edge.to_id in subtree


def _subtree_ids(graph: Graph, root: str) -> frozenset[str]:
    """``root`` itself and every node that transitively refines it.

    The reading "below" takes of subtree: the requirement and everything an
    operator would think of as under it, walking refines edges toward their
    refiners exactly as scope collection already does.
    """
    ids = {root}
    frontier = [root]
    while frontier:
        current = frontier.pop()
        for edge in graph.incoming(current, _REFINES):
            if edge.from_id not in ids:
                ids.add(edge.from_id)
                frontier.append(edge.from_id)
    return frozenset(ids)


__all__ = ["Selector", "add_selector_arguments", "select", "selector_from_args"]
