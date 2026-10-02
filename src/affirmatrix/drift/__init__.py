"""The suspect detector — link state derived from current content.

Takes two record sources — a *recorded* stream, which is the affirmation
store's read face (SEG-SREQ-054), and a *current* one from a producer — and
derives every current edge's state from that pair alone (SEG-SREQ-015).
Derivation never writes: recorded affirmations are left exactly as they were
(SEG-SREQ-034).

For an affirmed edge the state is a truth table over two independent axes.
The **content axis**: the edge's hash is recomputed from today's node hashes
and compared with the hash the edge was affirmed against — two-sided, so
either endpoint moving is a mismatch, and the verdict deliberately cannot say
which endpoint it was; that attribution belongs to the review events, which
record what each endpoint looked like when the judgement was made. The
**dependency axis**: the strong edges below the edge's own source endpoint —
its incoming strong edges, and theirs, recursively — every one of them
active. Content matching with every dependency active is ``active``
(SEG-SREQ-014); content differing alone is ``directlyOutdated``
(SEG-SREQ-011); a non-active dependency alone is ``transitivelySuspect``
(SEG-SREQ-012); both at once is ``doublyOutdated`` (SEG-SREQ-013) — outdated
on both counts, a statement about the edge's own content and its
dependencies, never about how many endpoints moved.

Transitive suspicion is derived, never affirmed. Every run derives states
afresh, so suspicion clears by recomputation once the edges it depended on
return to active — no one is asked to re-affirm an edge whose own endpoints
never moved, which would be a signature on something that did not change.
Affirmation resolves only the directly and doubly outdated cases.

Pending and broken sit outside the table because there is nothing to compare:
an edge with no stored hash was never affirmed, and the absence of a stored
hash is a state, not a mismatch (ADR-0005); an edge touching a node absent
from the current records is broken (SEG-SREQ-017), whatever its kind and
whether or not it was ever affirmed. Evidence edges receive states like every
other edge but neither receive nor transmit suspicion — the taxonomy keeps
them out of every dependency set.

The output is itself a record source (ADR-0004): the current nodes unchanged
and every current edge carrying its derived state, ready for the graph
builder to consume — which never learns the states were derived rather than
read. A recorded edge with no current counterpart receives no state at all —
the requirement set does not yet say what it is — and is carried untouched in
:attr:`Derivation.vanished` instead.

Beside the truth-table state, :func:`compare` answers a finer question for
an edge that has been affirmed: not the two-sided verdict alone, but which
named content hash of which endpoint moved, and against what (SEG-SREQ-128).
It reads the affirming review event's own per-hash digests and anchors —
never the current endpoint's node record, which states only what the content
is today, not what it was judged against — so a reader can see, per name,
whether it still matches, differs, or was gained or dropped since the
judgement. The edge's stored hash and the event's named hashes were both
written by the one affirmation that produced them, so a comparison against
that same event explains the verdict the truth table reached against that
hash, rather than telling it a second time.

:func:`compare_node` answers a neighbouring question for a node alone, with no
edge and no review event: how the node record the case holds compares with the
node record of the current stream. The case's record is the node as it stood at
the last ``case sync``. It is not the node as it stood at an affirmation. So a
match here after a new sync does not mean that an affirmed link still holds. For
"changed since affirmed", use :func:`compare` with the review event.

Iteration-0 backlog item B13 (SEG-SYS-003 and its decomposition).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from affirmatrix import commitment, graph, taxonomy
from affirmatrix.records import (
    ContentAnchor,
    EdgeRecord,
    EdgeReference,
    LinkState,
    NodeRecord,
    RecordSource,
    ReviewEvent,
)


class DriftError(Exception):
    """A pair of record streams whose edge states cannot be derived.

    Raised rather than answered with partial states: every condition that
    reaches this point — one edge affirmed twice, a dependency chain that
    loops — would otherwise surface as states that look derived and mean
    nothing.
    """


@dataclass(frozen=True, slots=True)
class Derivation:
    """The derived record stream, and the recorded edges that fell outside it.

    A record source in its own right: the graph the rest of the engine reads
    is built from this, exactly as it would be from a producer or from the
    affirmation store, so nothing downstream handles derived states as a
    special case. Both streams are materialized — each call returns a fresh
    iterator over the same records.
    """

    _nodes: tuple[NodeRecord, ...] = field(repr=False)
    _edges: tuple[EdgeRecord, ...] = field(repr=False)
    vanished: tuple[EdgeRecord, ...]

    def nodes(self) -> Iterator[NodeRecord]:
        """The current stream's node records, unchanged."""
        return iter(self._nodes)

    def edges(self) -> Iterator[EdgeRecord]:
        """Every current edge, carrying its derived state.

        An edge matched against a recorded affirmation keeps the hash it was
        affirmed against; deriving a state never strips an affirmation.
        """
        return iter(self._edges)


class HashStatus(StrEnum):
    """Whether one named content hash matches, differs, or exists on one side only.

    Four values, not a boolean: an affirming review event and an endpoint's
    current record may each carry a hash name the other does not — a name
    added or dropped since the judgement was made — and that absence is a
    fact about the comparison, not a verdict about content that was never
    there to compare (SEG-SREQ-128).
    """

    MATCHING = "matching"
    DIFFERING = "differing"
    RECORDED_ONLY = "recordedOnly"
    CURRENT_ONLY = "currentOnly"


@dataclass(frozen=True, slots=True)
class HashComparison:
    """One named content hash's comparison, for one endpoint.

    ``recorded`` is the anchor the affirming review event carried for this
    name; ``current`` is the anchor the endpoint's current node record
    carries for it. Either may be absent — :attr:`status` says which — and
    the other is carried alongside so a reader does not need a second lookup
    to see what it was. ``source_revision`` is the endpoint's own revision as
    the review event recorded it, the same value for every name of one
    endpoint, because the revision is a fact about the endpoint, not about
    one of its hashes.
    """

    name: str
    status: HashStatus
    recorded: ContentAnchor | None
    current: ContentAnchor | None
    source_revision: str


@dataclass(frozen=True, slots=True)
class Comparison:
    """The per-hash comparison of an edge's two endpoints against the affirming event.

    The value :func:`compare` returns; the marker naming the requirement it
    discharges lives on that function, the one that actually reads the
    event and derives the comparison, not on this plain result type.

    One :class:`HashComparison` per named content hash either side carries —
    the union of the event's names and the current record's names for that
    endpoint, so a hash dropped or gained since the affirming judgement is
    reported too, never silently absent.
    """

    from_hashes: tuple[HashComparison, ...]
    to_hashes: tuple[HashComparison, ...]


def compare(
    edge: EdgeReference, *, current_from: NodeRecord, current_to: NodeRecord, event: ReviewEvent
) -> Comparison:
    """Compare an edge's two current endpoints against the event that last affirmed it.

    :implements: SEG-SREQ-128

    Reads the event's own per-hash digests and anchors — never the current
    endpoint's recorded node record, which is a different question this
    function does not ask. ``event`` must be the affirmation this edge was
    judged under: composing a comparison against an event naming a different
    edge would silently misattribute a judgement to content nobody bound it
    to, so a mismatch raises :class:`DriftError` rather than comparing
    anyway.
    """
    if (event.kind, event.from_id, event.to_id) != (edge.kind, edge.from_id, edge.to_id):
        raise DriftError(
            f"the review event affirms {event.from_id!r} -> {event.to_id!r} ({event.kind}), "
            f"not {edge.from_id!r} -> {edge.to_id!r} ({edge.kind}); a comparison cannot be "
            "built against the wrong affirmation"
        )
    return Comparison(
        from_hashes=_endpoint_comparison(
            recorded=event.from_content_anchors,
            current=current_from,
            source_revision=event.from_source_revision,
        ),
        to_hashes=_endpoint_comparison(
            recorded=event.to_content_anchors,
            current=current_to,
            source_revision=event.to_source_revision,
        ),
    )


def _status(was: ContentAnchor | None, now: ContentAnchor | None) -> HashStatus:
    """The status of one named hash, from its recorded and its current anchor.

    Only the digests are compared. A moved anchor with the same digest matches.
    """
    if was is None:
        return HashStatus.CURRENT_ONLY
    if now is None:
        return HashStatus.RECORDED_ONLY
    return HashStatus.MATCHING if was.digest == now.digest else HashStatus.DIFFERING


def _endpoint_comparison(
    *, recorded: Mapping[str, ContentAnchor], current: NodeRecord, source_revision: str
) -> tuple[HashComparison, ...]:
    """One endpoint's named hashes, recorded against current, in name order."""
    names = sorted(set(recorded) | set(current.content_anchors))
    return tuple(
        HashComparison(
            name=name,
            status=_status(recorded.get(name), current.content_anchors.get(name)),
            recorded=recorded.get(name),
            current=current.content_anchors.get(name),
            source_revision=source_revision,
        )
        for name in names
    )


@dataclass(frozen=True, slots=True)
class NodeHashComparison:
    """One named content hash of one node, the case's record against the current one.

    ``recorded`` is the anchor the case's node record carries for this name and
    ``current`` the anchor the current stream's record carries. Either is
    ``None`` when its side has no such hash, and :attr:`status` says which.
    """

    name: str
    status: HashStatus
    recorded: ContentAnchor | None
    current: ContentAnchor | None


def compare_node(
    *, recorded: NodeRecord | None, current: NodeRecord | None
) -> tuple[NodeHashComparison, ...]:
    """Compare the case's node record with the current stream's, one result per hash name.

    :implements: SEG-SREQ-312

    ``recorded`` is the node record the case holds: the node as it stood at the
    last ``case sync``. It is not the node as it stood at an affirmation. A
    match here after a new sync therefore does not mean that an affirmed link
    still holds. An edge's "changed since affirmed" is :func:`compare` with the
    review event, and this function does not answer it.

    Either record can be ``None``. A node that only one side holds has every
    hash on that side only. The results follow name order, for the union of the
    names of both records. Each name is judged by itself: the change of one
    hash never changes the status of another. Only digests are compared, so a
    moved anchor with an equal digest matches. The function reads the two
    records and nothing else.
    """
    was = {} if recorded is None else recorded.content_anchors
    now = {} if current is None else current.content_anchors
    return tuple(
        NodeHashComparison(
            name=name,
            status=_status(was.get(name), now.get(name)),
            recorded=was.get(name),
            current=now.get(name),
        )
        for name in sorted(set(was) | set(now))
    )


def truth_table_state(*, content_matches: bool, dependencies_active: bool) -> LinkState:
    """The derived state of an affirmed edge, from its two axes.

    :implements: SEG-SREQ-011
    :implements: SEG-SREQ-012
    :implements: SEG-SREQ-013
    :implements: SEG-SREQ-014

    ``content_matches`` is the recomputed edge hash against the stored one;
    ``dependencies_active`` is the universal over the strong edges below the
    edge's source endpoint, true when that set is empty — which is how the
    recursion grounds out at endpoints nothing strong points into.
    """
    if content_matches:
        return LinkState.ACTIVE if dependencies_active else LinkState.TRANSITIVELY_SUSPECT
    return LinkState.DIRECTLY_OUTDATED if dependencies_active else LinkState.DOUBLY_OUTDATED


def derive(*, recorded: RecordSource, current: RecordSource) -> Derivation:
    """Derive every current edge's state from the two streams alone.

    :implements: SEG-SREQ-015
    :implements: SEG-SREQ-017
    :implements: SEG-SREQ-034
    :implements: SEG-SREQ-054

    ``recorded`` is the affirmation store's read face — edge records carrying
    the hashes they were affirmed against; ``current`` is a producer's stream
    over today's content. The roles are the parameters' to name and the
    caller's to honour: what a current edge claims about its own state or
    hash is ignored, because affirmed state is the recorded stream's to
    supply, and honouring the claim would let a producer assert a history
    that never happened. Non-mutation is structural — the function computes
    and returns, asking each stream for its records at most once and writing
    nowhere.

    The current stream must be buildable: anything :func:`graph.build`
    refuses is refused here, and the refines gate it enforces is what
    guarantees the dependency recursion terminates on well-kinded records.
    A recorded stream naming one edge twice, or a strong-edge structure that
    cycles anyway, raises :class:`DriftError` rather than deriving states
    that mean nothing.
    """
    snapshot = _Snapshot(taken_nodes=tuple(current.nodes()), taken_edges=tuple(current.edges()))
    built = graph.build(snapshot)
    resolution = _Resolution(
        built=built,
        affirmations=_by_reference(recorded.edges()),
        node_hashes={
            local_id: commitment.node_hash(
                built.node(local_id).kind, built.node(local_id).content_hashes
            )
            for local_id in built.node_ids()
        },
        node_ids=built.node_ids(),
    )
    derived = tuple(_derived_edge(edge, resolution) for edge in built.edges)
    present = {_reference(edge) for edge in built.edges}
    vanished = tuple(
        record
        for reference, record in resolution.affirmations.items()
        if reference not in present
    )
    return Derivation(_nodes=snapshot.taken_nodes, _edges=derived, vanished=vanished)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """The current stream, taken once and replayable.

    The builder consumes a record source and the output must carry the nodes
    the builder does not hand back, so the one permitted walk of the current
    stream happens here and everything after reads the copy.
    """

    taken_nodes: tuple[NodeRecord, ...]
    taken_edges: tuple[EdgeRecord, ...]

    def nodes(self) -> Iterator[NodeRecord]:
        return iter(self.taken_nodes)

    def edges(self) -> Iterator[EdgeRecord]:
        return iter(self.taken_edges)


@dataclass(slots=True)
class _Resolution:
    """One derivation's working state: the inputs indexed, the memos filling."""

    built: graph.Graph
    affirmations: Mapping[EdgeReference, EdgeRecord]
    node_hashes: Mapping[str, bytes]
    node_ids: frozenset[str]
    #: Edge reference to derived state, filled as edges are settled.
    states: dict[EdgeReference, LinkState] = field(default_factory=dict)
    #: Node to "every strong edge below it is active", filled in post-order.
    settled: dict[str, bool] = field(default_factory=dict)


def _reference(edge: EdgeRecord) -> EdgeReference:
    return EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id)


def _by_reference(edges: Iterator[EdgeRecord]) -> dict[EdgeReference, EdgeRecord]:
    """The recorded edges keyed by identity, refusing a double affirmation."""
    collected: dict[EdgeReference, EdgeRecord] = {}
    for record in edges:
        reference = _reference(record)
        if reference in collected:
            raise DriftError(
                f"the recorded stream names edge {record.from_id!r} -> {record.to_id!r} "
                f"({record.kind}) more than once; two records cannot both be the affirmation"
            )
        collected[reference] = record
    return collected


def _derived_edge(edge: EdgeRecord, resolution: _Resolution) -> EdgeRecord:
    """One current edge with its derived state and its recorded hash, if any."""
    if _shallow_state(edge, resolution) is None:
        _settle_dependencies(edge.from_id, resolution)
    record = resolution.affirmations.get(_reference(edge))
    return EdgeRecord(
        from_id=edge.from_id,
        to_id=edge.to_id,
        kind=edge.kind,
        state=_settled_state(edge, resolution),
        edge_hash=None if record is None else record.edge_hash,
    )


def _shallow_state(edge: EdgeRecord, resolution: _Resolution) -> LinkState | None:
    """The state decidable without looking at dependencies, if there is one.

    Broken and pending both short-circuit the truth table: an absent endpoint
    leaves no content to compare (SEG-SREQ-017), and a missing stored hash is
    a state, not a mismatch. Broken is checked first — an edge that is both
    dangling and unaffirmed needs its endpoint back before an affirmation
    could even be made.
    """
    if edge.from_id not in resolution.node_ids or edge.to_id not in resolution.node_ids:
        return LinkState.BROKEN
    record = resolution.affirmations.get(_reference(edge))
    if record is None or record.edge_hash is None:
        return LinkState.PENDING
    return None


def _settled_state(edge: EdgeRecord, resolution: _Resolution) -> LinkState:
    """This edge's derived state, memoised; its dependencies must be settled."""
    reference = _reference(edge)
    state = resolution.states.get(reference)
    if state is None:
        state = _shallow_state(edge, resolution)
        if state is None:
            stored = resolution.affirmations[reference].edge_hash
            recomputed = commitment.edge_hash(
                edge.from_id,
                edge.to_id,
                edge.kind,
                resolution.node_hashes[edge.from_id],
                resolution.node_hashes[edge.to_id],
            )
            state = truth_table_state(
                content_matches=recomputed == stored,
                dependencies_active=resolution.settled[edge.from_id],
            )
        resolution.states[reference] = state
    return state


def _settle_dependencies(start: str, resolution: _Resolution) -> None:
    """Fill the dependency memo for this node and everything below it.

    Iterative post-order with an explicit stack, because the depth here is
    the caller's decomposition, not ours, and a ``RecursionError`` would be a
    crash where the contract promises a derivation. Memoised across calls: a
    shared subtree is settled once. A strong in-edge that is broken or
    pending settles without descent — its state needs no dependencies — so
    the walk descends only where a comparison is actually owed.

    A source endpoint reappearing on the active path is a strong cycle. Only
    ill-kinded records can produce one — on the declared kinds every strong
    cycle is a refines cycle, which the graph builder has already refused —
    and the answer is a refusal, never a fixed point over a malformed graph.
    """
    if start in resolution.settled:
        return
    on_path: set[str] = set()
    stack: list[tuple[str, bool]] = [(start, False)]
    while stack:
        node_id, expanded = stack.pop()
        if expanded:
            on_path.discard(node_id)
            resolution.settled[node_id] = all(
                _settled_state(dependency, resolution) is LinkState.ACTIVE
                for dependency in _strong_in(resolution.built, node_id)
            )
            continue
        if node_id in resolution.settled:
            continue
        on_path.add(node_id)
        stack.append((node_id, True))
        for dependency in _strong_in(resolution.built, node_id):
            if _shallow_state(dependency, resolution) is not None:
                continue
            source = dependency.from_id
            if source in resolution.settled:
                continue
            if source in on_path:
                raise DriftError(
                    f"the strong edges cycle through {source!r}; a dependency chain "
                    "that loops has no derivable states"
                )
            stack.append((source, False))


def _strong_in(built: graph.Graph, local_id: str) -> tuple[EdgeRecord, ...]:
    """The strong edges pointing at this node — its direct dependencies."""
    propagating = taxonomy.propagating_edge_kinds()
    return tuple(edge for edge in built.incoming(local_id) if edge.kind in propagating)


__all__ = [
    "Comparison",
    "Derivation",
    "DriftError",
    "HashComparison",
    "HashStatus",
    "NodeHashComparison",
    "compare",
    "compare_node",
    "derive",
    "truth_table_state",
]
