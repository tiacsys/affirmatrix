"""The affirmation recorder (SEG-SREQ-024…028, SEG-SREQ-049).

Composing is the whole capability under test: from a derived edge record and
an operator's judgement, the recorder builds the review event that records
the affirmation and the edge record as it stands affirmed — and does nothing
else. The tests pin the composed content to the requirements (both current
endpoint hashes, both source revisions, the role, the reason verbatim), the
state gate to exactly the three affirmable states, and origination to zero:
no store is touched, no judgement field has a default, nothing supplied is
altered.

Every composition here is a capability test on literal records or a
``tmp_path`` case root — never an affirmation act, which is an operator's
commit on the real case and no test's to make.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

import pytest

from affirmatrix import affirmation, case, commitment, drift, records
from affirmatrix.records import EdgeReference, LinkState

#: A hash that no current content recomputes to — an affirmation whose
#: content has moved on.
STALE = hashlib.sha256(b"affirmed against content that has moved on").digest()

#: An operator's judgement, as keyword arguments. Revisions are 40-hex so the
#: same judgement passes the case schema in the store-backed test.
JUDGEMENT = {
    "role": "SoftwareEngineer",
    "reason": "reviewed the change; the binding still holds",
    "from_source_revision": "1" * 40,
    "to_source_revision": "2" * 40,
}


def anchors(names: tuple[str, ...], seed: str = "v1") -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(f"{name}:{seed}".encode()).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def requirement(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors(("contentHash",), seed))


def implementation(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(local_id, "Implementation", anchors(("apiHash", "bodyHash"), seed))


def node_hash_of(node: records.NodeRecord) -> bytes:
    return commitment.node_hash(node.kind, node.content_hashes)


def derived(
    kind: str,
    from_node: records.NodeRecord,
    to_node: records.NodeRecord,
    state: LinkState,
    edge_hash: bytes | None = STALE,
) -> records.EdgeRecord:
    """An edge record as the derived stream yields it, in the given state.

    The default stored hash is stale, matching the states an operator
    actually affirms; pending must override it with ``None``, and an active
    fixture supplies the genuinely matching hash itself.
    """
    return records.EdgeRecord(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        state=state,
        edge_hash=None if state is LinkState.PENDING else edge_hash,
    )


def outdated_pair() -> tuple[records.EdgeRecord, records.NodeRecord, records.NodeRecord]:
    """A directly outdated Implements edge and its two current endpoints."""
    impl, sreq = implementation("pkg.fn", "v2"), requirement("SREQ-1")
    return derived("Implements", impl, sreq, LinkState.DIRECTLY_OUTDATED), impl, sreq


# --- what a composition carries ----------------------------------------------


def test_the_event_binds_the_current_hashes_of_both_endpoints() -> None:
    """The judgement is bound to what the reviewer judged today — the node
    hashes of the *current* records, not the ones the edge was affirmed
    against (SEG-SREQ-024)."""
    edge, impl, sreq = outdated_pair()
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert composed.event.from_node_hash == node_hash_of(impl)
    assert composed.event.to_node_hash == node_hash_of(sreq)


def test_the_event_carries_each_endpoints_source_revision() -> None:
    """SEG-SREQ-025: the anchor is captured at composition or not at all."""
    edge, impl, sreq = outdated_pair()
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert composed.event.from_source_revision == JUDGEMENT["from_source_revision"]
    assert composed.event.to_source_revision == JUDGEMENT["to_source_revision"]


def test_the_event_carries_the_role_the_judgement_was_made_in() -> None:
    """SEG-SREQ-049. The value is free: the recorder passes an undocumented
    spelling through unjudged — role validation is a process concern."""
    edge, impl, sreq = outdated_pair()
    judgement = {**JUDGEMENT, "role": "a role no convention documents"}
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **judgement)
    assert composed.event.role == "a role no convention documents"


@pytest.mark.parametrize(
    "reason",
    ["", "  leading and trailing kept  ", "two\nlines", "größe Prüfung — ünïcode"],
    ids=["empty", "whitespace", "multiline", "unicode"],
)
def test_the_reason_is_recorded_verbatim(reason: str) -> None:
    """SEG-SREQ-028: no trimming, no normalisation, no substitute for empty."""
    edge, impl, sreq = outdated_pair()
    judgement = {**JUDGEMENT, "reason": reason}
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **judgement)
    assert composed.event.reason == reason


def test_the_event_names_the_edge_it_affirms() -> None:
    edge, impl, sreq = outdated_pair()
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert (composed.event.from_id, composed.event.to_id, composed.event.kind) == (
        "pkg.fn",
        "SREQ-1",
        "Implements",
    )


def test_an_empty_role_or_revision_is_refused_by_the_vocabulary() -> None:
    """The recorder validates nothing about the values; emptiness is refused
    where every record refuses it — at the vocabulary."""
    edge, impl, sreq = outdated_pair()
    for field in ("role", "from_source_revision", "to_source_revision"):
        judgement = {**JUDGEMENT, field: ""}
        with pytest.raises(ValueError, match="non-empty"):
            affirmation.compose(edge, from_node=impl, to_node=sreq, **judgement)


# --- the edge as it stands affirmed ------------------------------------------


def test_the_affirmed_edge_is_active_and_carries_the_recomputed_hash() -> None:
    """The pair the operator hands to the store: the event, and the edge
    record whose stored hash is the one the event's endpoint hashes fold to —
    agreement by construction, not by discipline."""
    edge, impl, sreq = outdated_pair()
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert composed.edge.state is LinkState.ACTIVE
    assert composed.edge.edge_hash == commitment.edge_hash(
        "pkg.fn",
        "SREQ-1",
        "Implements",
        composed.event.from_node_hash,
        composed.event.to_node_hash,
    )
    assert (composed.edge.from_id, composed.edge.to_id, composed.edge.kind) == (
        edge.from_id,
        edge.to_id,
        edge.kind,
    )


# --- the gate: only pending or outdated edges are affirmable ------------------


@pytest.mark.parametrize(
    ("state", "verdict"),
    [
        (LinkState.PENDING, True),
        (LinkState.ACTIVE, False),
        (LinkState.DIRECTLY_OUTDATED, True),
        (LinkState.TRANSITIVELY_SUSPECT, False),
        (LinkState.DOUBLY_OUTDATED, True),
        (LinkState.BROKEN, False),
    ],
)
def test_affirmable_names_exactly_the_three_states(state: LinkState, verdict: bool) -> None:
    assert affirmation.affirmable(state) is verdict


@pytest.mark.parametrize(
    "state",
    [LinkState.PENDING, LinkState.DIRECTLY_OUTDATED, LinkState.DOUBLY_OUTDATED],
)
def test_compose_accepts_every_affirmable_state(state: LinkState) -> None:
    impl, sreq = implementation("pkg.fn", "v2"), requirement("SREQ-1")
    edge = derived("Implements", impl, sreq, state)
    composed = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert composed.edge.state is LinkState.ACTIVE


@pytest.mark.parametrize(
    ("state", "why"),
    [
        (LinkState.ACTIVE, "nothing to affirm"),
        (LinkState.TRANSITIVELY_SUSPECT, "recomputation"),
        (LinkState.BROKEN, "endpoint"),
    ],
)
def test_compose_refuses_every_non_affirmable_state(state: LinkState, why: str) -> None:
    """Each refusal says why that state cannot be affirmed: an active edge has
    nothing to affirm, a transitively suspect one clears by recomputation
    (re-affirming it would sign content that did not change), and a broken
    one needs its endpoint back before a judgement could bind anything."""
    impl, sreq = implementation("pkg.fn"), requirement("SREQ-1")
    edge_hash = commitment.edge_hash(
        "pkg.fn", "SREQ-1", "Implements", node_hash_of(impl), node_hash_of(sreq)
    )
    edge = derived(
        "Implements",
        impl,
        sreq,
        state,
        edge_hash=edge_hash if state is LinkState.ACTIVE else STALE,
    )
    with pytest.raises(affirmation.AffirmationError, match=why):
        affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)


def test_a_vanished_edge_is_refused_by_the_state_it_was_recorded_in() -> None:
    """A vanished edge (``Derivation.vanished``) carries its *recorded* state
    untouched, typically active; that state refuses it here. A vanished edge
    recorded pending is indistinguishable at this surface — its guard is
    upstream, in there being no current node records to supply."""
    impl, sreq = implementation("pkg.fn"), requirement("SREQ-1")
    vanished = derived("Implements", impl, sreq, LinkState.ACTIVE)
    with pytest.raises(affirmation.AffirmationError, match="nothing to affirm"):
        affirmation.compose(vanished, from_node=impl, to_node=sreq, **JUDGEMENT)


def test_a_node_that_is_not_the_edges_endpoint_is_refused() -> None:
    """The judgement binds the edge's endpoints; hashes of some other node
    would compose a record about an edge nobody reviewed."""
    edge, impl, sreq = outdated_pair()
    stranger = requirement("SREQ-2")
    with pytest.raises(affirmation.AffirmationError, match="endpoint"):
        affirmation.compose(edge, from_node=impl, to_node=stranger, **JUDGEMENT)
    with pytest.raises(affirmation.AffirmationError, match="endpoint"):
        affirmation.compose(edge, from_node=stranger, to_node=sreq, **JUDGEMENT)


# --- origination: the recorder brings no judgement of its own -----------------


def test_every_judgement_field_is_required_by_keyword_with_no_default() -> None:
    """SEG-SREQ-026 as a signature: a default for role, reason, or a revision
    would be a fragment of judgement the recorder supplies itself."""
    signature = inspect.signature(affirmation.compose)
    for name in ("role", "reason", "from_source_revision", "to_source_revision"):
        parameter = signature.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


def test_the_recorder_reaches_no_store_and_no_filesystem() -> None:
    """SEG-SREQ-026 made mechanical: the component that originates no
    affirmation persists none either. The layering lint permits ``case`` as a
    ceiling; this pins the recorder below it, and off the filesystem."""
    source = Path(inspect.getsourcefile(affirmation)).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    forbidden = {"affirmatrix.case", "pathlib", "os", "io", "shutil", "tempfile"}
    assert not {name for name in imported if name in forbidden or name.startswith("os.")}


def test_composing_twice_composes_the_same_affirmation() -> None:
    """Pure composition: equal inputs, equal values, no hidden state — and in
    particular nothing minted per call, no identifier and no timestamp
    (position in the store is identity)."""
    edge, impl, sreq = outdated_pair()
    first = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    second = affirmation.compose(edge, from_node=impl, to_node=sreq, **JUDGEMENT)
    assert first == second


# --- the operator's path, end to end ------------------------------------------


def test_the_operators_path_re_activates_the_change_site_and_clears_above(
    tmp_path: Path,
) -> None:
    """The B13 join, now through the recorder: derive → compose for the
    directly outdated edge → event and updated record through the store → a
    second derivation shows the edge active and its ancestor cleared by
    recomputation (never by a second affirmation). A capability test on a
    throwaway case root — composing here is not an affirmation act."""
    sys_v1, sreq_v1, impl_v1 = requirement("SYS-1"), requirement("SREQ-1"), implementation("pkg.fn")
    store = case.AffirmationStore(root=tmp_path / "case")
    store.write_nodes([sys_v1, sreq_v1, impl_v1])
    store.write_edges(
        [
            _affirmed("Refines", sreq_v1, sys_v1),
            _affirmed("Implements", impl_v1, sreq_v1),
        ]
    )

    impl_v2 = implementation("pkg.fn", "v2")
    current = _Source(
        nodes=(sys_v1, sreq_v1, impl_v2),
        edges=(
            _declared("Refines", "SREQ-1", "SYS-1"),
            _declared("Implements", "pkg.fn", "SREQ-1"),
        ),
    )
    drifted = drift.derive(recorded=store, current=current)
    assert _state_of(drifted, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert _state_of(drifted, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT

    change_site = next(edge for edge in drifted.edges() if edge.kind == "Implements")
    composed = affirmation.compose(change_site, from_node=impl_v2, to_node=sreq_v1, **JUDGEMENT)
    store.append_review_events([composed.event])
    store.write_edges([composed.edge])

    settled = drift.derive(recorded=store, current=current)
    assert _state_of(settled, "Implements", "pkg.fn", "SREQ-1") is LinkState.ACTIVE
    assert _state_of(settled, "Refines", "SREQ-1", "SYS-1") is LinkState.ACTIVE
    assert list(store.review_events()) == [composed.event]


class _Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def _affirmed(
    kind: str, from_node: records.NodeRecord, to_node: records.NodeRecord
) -> records.EdgeRecord:
    """A recorded edge affirmed against exactly these two nodes' content."""
    return records.EdgeRecord(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        state=LinkState.ACTIVE,
        edge_hash=commitment.edge_hash(
            from_node.local_id,
            to_node.local_id,
            kind,
            node_hash_of(from_node),
            node_hash_of(to_node),
        ),
    )


def _declared(kind: str, from_id: str, to_id: str) -> records.EdgeRecord:
    """A current edge as a producer yields it: declared, never affirmed."""
    return records.EdgeRecord(from_id=from_id, to_id=to_id, kind=kind, state=LinkState.PENDING)


def _state_of(derivation: drift.Derivation, kind: str, from_id: str, to_id: str) -> LinkState:
    states = {
        EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id): edge.state
        for edge in derivation.edges()
    }
    return states[EdgeReference(kind=kind, from_id=from_id, to_id=to_id)]
