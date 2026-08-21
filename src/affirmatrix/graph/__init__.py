"""The graph builder — records to the in-memory graph.

Assembles node and edge records into the typed graph the rest of the engine
reads. It is the narrow gate every record passes through, so most of what it
does is refuse: a kind the vocabulary does not declare (SEG-SREQ-031), a cycle
or self-loop in the refines relation (SEG-SREQ-004), a local identifier used
twice (ADR-0007). Each refusal exists because the alternative is a graph that
looks complete, seals to a perfectly valid root, and is wrong.

An edge that was never affirmed is reported as pending (SEG-SREQ-016), judged
by whether it carries a hash it was affirmed against rather than by what its
record claims. Beyond that the builder carries recorded state rather than
recomputing it: the builder assembles, the suspect detector derives (ADR-0004).

What it deliberately does *not* refuse is as important. An edge pointing at a
node that is not present is built, not rejected — a dangling endpoint is a
broken edge, and reaching that verdict needs both record streams, which the
suspect detector has and this component does not.

Iteration-0 backlog items B7 (build) and B8 (cycles).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from affirmatrix import taxonomy
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord, RecordSource

_REFINES = "Refines"


class GraphError(Exception):
    """A record set that cannot become a graph.

    Raised rather than collected: every condition that reaches this point makes
    the resulting graph untrustworthy in a way nothing downstream could detect,
    so continuing would substitute a silent wrong answer for a loud one.
    """


@dataclass(frozen=True, slots=True)
class Graph:
    """Nodes and edges, indexed for traversal in both directions.

    Adjacency is built once and read many times. Every later component walks
    this structure — satisfaction recurses over it, scope collection expands
    across it — so a linear scan per lookup would be paid on every step of
    every traversal.
    """

    _nodes: Mapping[str, NodeRecord]
    edges: tuple[EdgeRecord, ...]
    _incoming: Mapping[str, tuple[EdgeRecord, ...]] = field(repr=False)
    _outgoing: Mapping[str, tuple[EdgeRecord, ...]] = field(repr=False)

    def node(self, local_id: str) -> NodeRecord:
        """The node with this identifier, or ``KeyError`` if there is none."""
        return self._nodes[local_id]

    def node_ids(self) -> frozenset[str]:
        """Every node identifier in the graph."""
        return frozenset(self._nodes)

    def nodes_of_kind(self, kind: str) -> tuple[NodeRecord, ...]:
        """Every node of one kind, in insertion order."""
        return tuple(node for node in self._nodes.values() if node.kind == kind)

    def incoming(self, local_id: str, kind: str | None = None) -> tuple[EdgeRecord, ...]:
        """Edges pointing at this node, optionally narrowed to one kind."""
        return _filtered(self._incoming.get(local_id, ()), kind)

    def outgoing(self, local_id: str, kind: str | None = None) -> tuple[EdgeRecord, ...]:
        """Edges leaving this node, optionally narrowed to one kind."""
        return _filtered(self._outgoing.get(local_id, ()), kind)

    def restricted_to(self, ids: frozenset[str]) -> Graph:
        """The induced subgraph over ``ids``: every edge whose two endpoints are both in it.

        Full induced, not merely the edges a membership walk used to reach
        ``ids``: an edge kind that never decides membership — ``Witnesses``,
        say — can still connect two ids a walk reached by different routes,
        and a caller judging this subgraph must see that edge or a piece of
        evidence that is actually complete would read as incomplete for a
        reason that never happened. An edge with one endpoint outside ``ids``
        is dropped without comment; this is a deliberate cut of an
        already-built graph, not a second refusal surface, so nothing here
        raises over what the cut leaves out.

        An id in ``ids`` that names no node here is simply absent from the
        result: :func:`build` already decided which edges to admit to a
        missing node, and that decision is not repeated by cutting the graph
        down afterwards.
        """
        kept_nodes = {local_id: node for local_id, node in self._nodes.items() if local_id in ids}
        kept_edges = tuple(
            edge for edge in self.edges if edge.from_id in ids and edge.to_id in ids
        )
        return Graph(
            _nodes=MappingProxyType(kept_nodes),
            edges=kept_edges,
            _incoming=_index(kept_edges, lambda edge: edge.to_id),
            _outgoing=_index(kept_edges, lambda edge: edge.from_id),
        )


def _filtered(edges: tuple[EdgeRecord, ...], kind: str | None) -> tuple[EdgeRecord, ...]:
    if kind is None:
        return edges
    return tuple(edge for edge in edges if edge.kind == kind)


def build(source: RecordSource) -> Graph:
    """Turn a record source into a graph, refusing anything that cannot be one.

    :implements: SEG-SREQ-004
    :implements: SEG-SREQ-016
    :implements: SEG-SREQ-031
    """
    nodes = _collect_nodes(source.nodes())
    edges = tuple(_admit_edge(record) for record in source.edges())
    _reject_refines_cycles(edges)
    return Graph(
        _nodes=MappingProxyType(nodes),
        edges=edges,
        _incoming=_index(edges, lambda edge: edge.to_id),
        _outgoing=_index(edges, lambda edge: edge.from_id),
    )


def _collect_nodes(records: Iterator[NodeRecord]) -> dict[str, NodeRecord]:
    collected: dict[str, NodeRecord] = {}
    for record in records:
        if record.kind not in taxonomy.node_kinds():
            raise GraphError(
                f"node {record.local_id!r} declares kind {record.kind!r}, "
                "which the vocabulary does not contain"
            )
        _check_content_hashes(record)
        if record.local_id in collected:
            raise GraphError(
                f"local identifier {record.local_id!r} is used by more than one node; "
                "identifiers must be unique within a case"
            )
        collected[record.local_id] = record
    return collected


def _check_content_hashes(record: NodeRecord) -> None:
    """A node must carry exactly the content hashes its kind declares.

    The names travel into the node-hash preimage, so a node carrying names its
    kind does not declare would hash under a description the vocabulary cannot
    give, and one missing a declared name would hash as though the content it
    omits does not exist.
    """
    declared = taxonomy.content_hash_names(record.kind)
    carried = frozenset(record.content_hashes)
    if carried == declared:
        return
    undeclared = ", ".join(sorted(carried - declared))
    missing = ", ".join(sorted(declared - carried))
    detail = "; ".join(
        part
        for part in (
            f"carries undeclared content hashes: {undeclared}" if undeclared else "",
            f"missing declared content hashes: {missing}" if missing else "",
        )
        if part
    )
    raise GraphError(f"node {record.local_id!r} of kind {record.kind!r} {detail}")


def _admit_edge(record: EdgeRecord) -> EdgeRecord:
    if record.kind not in taxonomy.edge_kinds():
        raise GraphError(
            f"edge {record.from_id!r} -> {record.to_id!r} declares kind "
            f"{record.kind!r}, which the vocabulary does not contain"
        )
    if record.edge_hash is None and record.state is not LinkState.PENDING:
        # An edge carrying nothing it was affirmed against was never affirmed,
        # whatever its record claims. Believing the label over the evidence
        # would let a producer assert a history that never happened.
        return replace(record, state=LinkState.PENDING)
    return record


def _index(edges: Iterable[EdgeRecord], key) -> Mapping[str, tuple[EdgeRecord, ...]]:
    grouped: dict[str, list[EdgeRecord]] = {}
    for edge in edges:
        grouped.setdefault(key(edge), []).append(edge)
    return MappingProxyType({node_id: tuple(group) for node_id, group in grouped.items()})


def _reject_refines_cycles(edges: Iterable[EdgeRecord]) -> None:
    """Refuse a refines relation that is not acyclic.

    Satisfaction recurses along refines, so a cycle would not merely be untidy:
    the recursion would not terminate, and a self-loop would let a requirement
    stand as its own justification.
    """
    parents: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind == _REFINES:
            parents.setdefault(edge.from_id, []).append(edge.to_id)

    done: set[str] = set()
    for start in parents:
        if start not in done:
            _walk_from(start, parents, done)


def _walk_from(start: str, parents: Mapping[str, list[str]], done: set[str]) -> None:
    """Depth-first search from one node, iteratively.

    Iterative rather than recursive because the depth here is the depth of the
    caller's decomposition, not ours. A deep refines chain would exhaust the
    interpreter stack, and a ``RecursionError`` is a crash where the contract
    promises a graph-level error.
    """
    path = [start]
    on_path = {start}
    stack = [(start, iter(parents.get(start, ())))]
    while stack:
        node_id, remaining = stack[-1]
        descended = False
        for parent in remaining:
            if parent in done:
                continue
            if parent in on_path:
                cycle = " -> ".join([*path[path.index(parent) :], parent])
                raise GraphError(f"the refines relation contains a cycle: {cycle}")
            path.append(parent)
            on_path.add(parent)
            stack.append((parent, iter(parents.get(parent, ()))))
            descended = True
            break
        if not descended:
            stack.pop()
            on_path.discard(node_id)
            path.pop()
            done.add(node_id)


__all__ = ["Graph", "GraphError", "build"]
