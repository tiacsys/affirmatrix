"""Shared internal — identifier minting (ADR-0007).

Not a component and never a requirement subject. This module is the only place
that knows the identifier base, and it mints the absolute IRIs that serialized
records carry. Minted IRIs are **opaque keys**: tooling reads an edge's
endpoints from the record's endpoint fields and never parses them back out of
an identifier, because the parts can themselves contain the separator and the
split is not reliably reversible.

What enters a hash preimage is the *case-local* stable identifier, never an
IRI — which is why the base stays revisable and why this module is invisible
to the commitment layer.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

#: The one place the identifier base is known.
#:
#: A module constant rather than a configuration value, deliberately: a base
#: read from configuration would still never reach a preimage, but it would
#: make two cases written by the same tool disagree about what an identifier
#: looks like for no gain the first version can use. Changing it is a
#: re-serialization and invalidates no affirmation (ADR-0007).
BASE = "https://affirmatrix.dev/case"


def _segment(value: str) -> str:
    """One path segment, percent-encoded so nothing in it can be structural.

    ``safe=""`` because a local identifier may contain a slash — a test
    outcome's is ``{runId}/{specId}`` — and a segment that silently became two
    would give one node two identities depending on how it was spelled.
    """
    return quote(value, safe="")


def node_iri(local_id: str) -> str:
    """The absolute IRI a node record is serialized under.

    No kind segment. An edge record carries its endpoints' identifiers and not
    their kinds, and a broken edge's endpoint is by definition no longer in the
    graph to be asked — so an IRI that needed the kind would leave some
    persistable edges unserializable. Local identifiers are unique within a
    case (ADR-0007), which is what makes the shorter form sufficient.
    """
    return f"{BASE}/node/{_segment(local_id)}"


def node_local_id(iri: str) -> str:
    """The case-local identifier a node IRI was minted from.

    The inverse of :func:`node_iri`, and deliberately of nothing else: a node
    IRI carries exactly one fully percent-encoded segment, so undoing the
    minting is well defined. This is not the identifier-splitting ADR-0007
    forbids — that rule is about recovering an edge's parts from its ``id``,
    whose segments may contain the separator. Read-back reads endpoints from
    ``seg:from``/``seg:to`` exactly as the record states them; those values are
    node IRIs, and this is the one place that can undo them, because it is the
    one place that knows the base.

    An IRI outside the node space is refused. Callers verify a recovered
    identifier by re-minting it and comparing against the stored one, so a
    non-canonical spelling cannot slip through as a parse this function never
    made.
    """
    prefix = f"{BASE}/node/"
    if not iri.startswith(prefix):
        raise ValueError(f"{iri!r} is not a node identifier: it does not start with {prefix!r}")
    segment = iri.removeprefix(prefix)
    if not segment or "/" in segment:
        raise ValueError(
            f"{iri!r} is not a node identifier: a node IRI carries exactly one segment"
        )
    return unquote(segment)


def edge_iri(kind: str, from_id: str, to_id: str) -> str:
    """The absolute IRI an edge record is serialized under.

    The endpoints are separate path segments rather than two halves of one.
    Any separator inside a segment is what percent-encoding removes, and the
    encoding leaves a few characters alone — so a separator drawn from those,
    a hyphen pair among them, would let ``a--b -> c`` and ``a -> b--c`` mint
    one identifier for two edges, and a document keyed by identifier would then
    hold one of them.

    The result is still an opaque key. That two segments happen to be
    separable is not licence to separate them: tooling reads an edge's
    endpoints from the record's own endpoint fields (ADR-0007).
    """
    return f"{BASE}/edge/{_segment(kind.lower())}/{_segment(from_id)}/{_segment(to_id)}"


def review_event_iri(ordinal: int) -> str:
    """The absolute IRI a review event is serialized under.

    A review event carries nothing that identifies it — the edge it concerns is
    not enough, since the same edge may be affirmed again — so identity is the
    position it was appended at. Zero-padded, so the events of a case sort in
    the order they were recorded.
    """
    if ordinal < 1:
        raise ValueError(f"a review event's ordinal starts at 1, got {ordinal}")
    return f"{BASE}/event/{ordinal:06d}"


__all__ = ["BASE", "edge_iri", "node_iri", "node_local_id", "review_event_iri"]
