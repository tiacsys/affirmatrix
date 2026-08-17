"""The affirmation recorder — writing the human judgement.

Builds the review event that records an affirmation: the edge, the content
hashes of both endpoints (SEG-SREQ-024), the reason supplied, preserved as
given (SEG-SREQ-028), and the source commit of each endpoint at the moment of
judgement (SEG-SREQ-025). That last one cannot be reconstructed afterwards —
nothing else correlates a source revision to the moment someone accepted it —
so it is captured at affirmation or not at all.

**Capability, not authority.** This component is built and unit-tested here;
an operator runs it. The recorder originates no affirmation of its own
(SEG-SREQ-026), and only an unaffirmed or outdated edge can be affirmed
(SEG-SREQ-027) — affirmation cannot clear a broken edge or a stale outcome,
which need an endpoint fix or a re-run. It is a review act, not a button that
makes the graph green.

Persisting the event is the affirmation store's; composing it is this
component's. One affirmation composes a pair: the review event that records
the judgement, and the edge record as it stands affirmed — active, carrying
the hash the judgement binds. The edge's new record is composed here rather
than at the store because the store persists what it is handed and computes
no hashes; both halves fold the same endpoint hashes, so record and event
cannot disagree about what was affirmed.

The recorder computes nothing about link state either. The edge it takes is a
*derived* record — the suspect detector's output, carrying the state the two
streams imply — and the caller's obligation is to supply one; a recorder that
re-derived would be a second telling of link state. Source revisions are
opaque here: the tool never runs git, so the operator supplies them, and
their format is judged where the record is persisted, against the case's own
schema.

Iteration-0 backlog item B14 (SEG-SYS-004 and its decomposition).
"""

from __future__ import annotations

from dataclasses import dataclass

from affirmatrix import commitment
from affirmatrix.records import EdgeRecord, LinkState, NodeRecord, ReviewEvent

__all__ = [
    "Affirmation",
    "AffirmationError",
    "affirmable",
    "compose",
]

_AFFIRMABLE = frozenset(
    {LinkState.PENDING, LinkState.DIRECTLY_OUTDATED, LinkState.DOUBLY_OUTDATED}
)

#: Why each non-affirmable state is refused — each names the act that would
#: actually resolve it, so a refusal is a signpost rather than a dead end.
_REFUSALS = {
    LinkState.ACTIVE: (
        "it is active — both endpoints stand as last judged, so there is nothing to affirm"
    ),
    LinkState.TRANSITIVELY_SUSPECT: (
        "its own endpoints did not change; it clears by recomputation once the outdated "
        "edges below it are re-affirmed, and a new signature here would sign content "
        "that did not move"
    ),
    LinkState.BROKEN: (
        "an endpoint is missing from the current records; it needs the endpoint restored "
        "or the edge removed, not a judgement about content that is not there"
    ),
}


class AffirmationError(Exception):
    """An affirmation that cannot be composed as requested.

    Raised for an edge whose state affirmation cannot resolve, and for a
    supplied node that is not the edge's endpoint — either way the review
    event would record a judgement about something nobody reviewed.
    """


@dataclass(frozen=True, slots=True)
class Affirmation:
    """One composed affirmation: the judgement's record, and its effect.

    The pair the operator hands to the store together — the event to
    ``append_review_events``, the edge to ``write_edges``. Two views of one
    act, composed from the same endpoint hashes: the event states what was
    judged, the edge record is what the graph holds once that judgement is
    recorded.
    """

    event: ReviewEvent
    edge: EdgeRecord


def affirmable(state: LinkState) -> bool:
    """Whether an edge in this state can be affirmed.

    :implements: SEG-SREQ-027

    True exactly for pending, directly outdated, and doubly outdated — the
    states where a human judgement about the edge's own content is what is
    missing. Active has nothing to affirm; transitive suspicion clears by
    recomputation, never by signature; broken needs its endpoint back first.
    """
    return state in _AFFIRMABLE


def compose(
    edge: EdgeRecord,
    *,
    from_node: NodeRecord,
    to_node: NodeRecord,
    role: str,
    reason: str,
    from_source_revision: str,
    to_source_revision: str,
) -> Affirmation:
    """Compose the records one affirmation produces, persisting nothing.

    :implements: SEG-SREQ-024
    :implements: SEG-SREQ-025
    :implements: SEG-SREQ-026
    :implements: SEG-SREQ-028
    :implements: SEG-SREQ-049

    ``edge`` is a derived record naming the state the affirmation resolves;
    anything :func:`affirmable` refuses is refused whole. ``from_node`` and
    ``to_node`` are the edge's *current* endpoint records — what the reviewer
    judged today — and the event binds their hashes, not the ones the edge
    was last affirmed against, which would re-sign the past. The recorder
    derives those hashes from the records it was handed and originates
    nothing: every judgement field is the operator's, required, without a
    default — even an empty reason must be given, never assumed — and each is
    carried into the event exactly as supplied. Composing is pure; the one
    affirmation act is the operator committing what the store then persisted.
    """
    if not affirmable(edge.state):
        raise AffirmationError(
            f"edge {edge.from_id!r} -> {edge.to_id!r} ({edge.kind}) cannot be "
            f"affirmed: {_REFUSALS[edge.state]}"
        )
    mismatches = [
        f"{node.local_id!r} is not the edge's {side} endpoint {expected!r}"
        for node, side, expected in (
            (from_node, "source", edge.from_id),
            (to_node, "target", edge.to_id),
        )
        if node.local_id != expected
    ]
    if mismatches:
        raise AffirmationError(
            f"this judgement does not bind edge {edge.from_id!r} -> {edge.to_id!r} "
            f"({edge.kind}): {'; '.join(mismatches)}"
        )
    from_node_hash = commitment.node_hash(from_node.kind, from_node.content_hashes)
    to_node_hash = commitment.node_hash(to_node.kind, to_node.content_hashes)
    return Affirmation(
        event=ReviewEvent(
            from_id=edge.from_id,
            to_id=edge.to_id,
            kind=edge.kind,
            from_node_hash=from_node_hash,
            to_node_hash=to_node_hash,
            from_source_revision=from_source_revision,
            to_source_revision=to_source_revision,
            role=role,
            reason=reason,
        ),
        edge=EdgeRecord(
            from_id=edge.from_id,
            to_id=edge.to_id,
            kind=edge.kind,
            state=LinkState.ACTIVE,
            edge_hash=commitment.edge_hash(
                edge.from_id, edge.to_id, edge.kind, from_node_hash, to_node_hash
            ),
        ),
    )
