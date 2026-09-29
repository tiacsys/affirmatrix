"""The suspect detector (SEG-SREQ-011…015, SEG-SREQ-017, -034, -054).

The derivation under test is a truth table over two independent axes — does
the edge's recomputed hash still equal the one it was affirmed against, and
is every strong edge below its source endpoint active — plus the two states
that sit outside the table: pending, where there is no stored hash to compare
against, and broken, where an endpoint is not there to compare. The edge
cases are where the honesty lives: suspicion climbs strong edges and stops at
the evidence boundary, clears by recomputation rather than by a second
affirmation, and derivation writes nothing anywhere.

Fixture graphs are built in memory from literal records; the one store-backed
test builds its case under ``tmp_path`` and reads the would-be store from a
throwaway copy. Nothing here touches the repository's own case.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from affirmatrix import case, commitment, drift, graph, records, satisfaction, taxonomy
from affirmatrix.records import EdgeReference, LinkState, RecordSource
from affirmatrix.sources.store import StoreLoader

WOULD_BE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "would_be_store"

#: A hash that no current content recomputes to — an affirmation whose
#: content has moved on.
STALE = hashlib.sha256(b"affirmed against content that has moved on").digest()


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


class OneShotSource(Source):
    """A source whose streams cannot be asked for twice."""

    def __init__(self, nodes=(), edges=()):
        super().__init__(nodes, edges)
        self._served: set[str] = set()

    def _once(self, stream: str):
        if stream in self._served:
            raise AssertionError(f"{stream}() was called twice; nothing may assume that works")
        self._served.add(stream)

    def nodes(self):
        self._once("nodes")
        return super().nodes()

    def edges(self):
        self._once("edges")
        return super().edges()


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


def specification(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "TestSpecification", anchors(("specHash", "implHash"), seed)
    )


def outcome(local_id: str, seed: str = "v1") -> records.NodeRecord:
    return records.NodeRecord(
        local_id,
        "TestOutcome",
        anchors(("contentHash",), seed),
        result=records.TestResult.PASSED,
        revision="r1",
    )


def node_hash_of(node: records.NodeRecord) -> bytes:
    return commitment.node_hash(node.kind, node.content_hashes)


def affirmed(
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


def declared(kind: str, from_id: str, to_id: str) -> records.EdgeRecord:
    """A current edge as a producer yields it: declared, never affirmed."""
    return records.EdgeRecord(from_id=from_id, to_id=to_id, kind=kind, state=LinkState.PENDING)


def state_of(derivation: drift.Derivation, kind: str, from_id: str, to_id: str) -> LinkState:
    states = {
        EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id): edge.state
        for edge in derivation.edges()
    }
    return states[EdgeReference(kind=kind, from_id=from_id, to_id=to_id)]


def chain(impl_seed: str = "v1", sreq_seed: str = "v1", sys_seed: str = "v1"):
    """The smallest graph with a dependency: an implementation under a
    requirement under a system requirement, every edge affirmed against v1.

    Returns ``(recorded, current)`` sources; the seeds drift the current
    content while the recorded stream stays at what was affirmed.
    """
    sys_v1, sreq_v1, impl_v1 = requirement("SYS-1"), requirement("SREQ-1"), implementation("pkg.fn")
    recorded = Source(
        nodes=(sys_v1, sreq_v1, impl_v1),
        edges=(affirmed("Refines", sreq_v1, sys_v1), affirmed("Implements", impl_v1, sreq_v1)),
    )
    current = Source(
        nodes=(
            requirement("SYS-1", sys_seed),
            requirement("SREQ-1", sreq_seed),
            implementation("pkg.fn", impl_seed),
        ),
        edges=(declared("Refines", "SREQ-1", "SYS-1"), declared("Implements", "pkg.fn", "SREQ-1")),
    )
    return recorded, current


# --- the truth table, each state through its defining combination ----------


def test_active_when_content_matches_and_every_dependency_is_active() -> None:
    recorded, current = chain()
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.ACTIVE
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.ACTIVE


def test_directly_outdated_when_own_content_differs_and_dependencies_hold() -> None:
    """Only the parent requirement moved, so only the edge touching it is
    outdated — and it is *directly* outdated even though just one of its two
    endpoints changed, because the axis is the edge's own content, not an
    endpoint count."""
    recorded, current = chain(sys_seed="v2")
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.ACTIVE


def test_transitively_suspect_when_only_a_dependency_moved() -> None:
    recorded, current = chain(impl_seed="v2")
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT


def test_doubly_outdated_when_both_axes_fail_at_once() -> None:
    """One change to the middle node lands on both axes of the edge above it:
    the refines edge's own content differs *and* its dependency went
    non-active. Doubly outdated counts axes, never endpoints."""
    recorded, current = chain(sreq_seed="v2")
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.DOUBLY_OUTDATED


@pytest.mark.parametrize(
    ("content_matches", "dependencies_active", "expected"),
    [
        (True, True, LinkState.ACTIVE),
        (False, True, LinkState.DIRECTLY_OUTDATED),
        (True, False, LinkState.TRANSITIVELY_SUSPECT),
        (False, False, LinkState.DOUBLY_OUTDATED),
    ],
)
def test_truth_table_state_maps_the_two_axes(
    content_matches: bool, dependencies_active: bool, expected: LinkState
) -> None:
    state = drift.truth_table_state(
        content_matches=content_matches, dependencies_active=dependencies_active
    )
    assert state is expected


def test_no_dependencies_ground_the_recursion_as_vacuously_active() -> None:
    """An affirmed, matching edge whose source endpoint has no strong
    in-edges satisfies "every strong edge it depends on is active" over the
    empty set."""
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), (affirmed("Implements", impl, sreq),)),
        current=Source((sreq, impl), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.ACTIVE


# --- pending: the absence of a stored hash is a state, not a mismatch ------


def test_a_current_edge_the_case_never_saw_is_pending() -> None:
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), ()),
        current=Source((sreq, impl), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.PENDING


def test_a_recorded_but_never_affirmed_edge_is_pending() -> None:
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), (declared("Implements", "pkg.fn", "SREQ-1"),)),
        current=Source((sreq, impl), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.PENDING


def test_what_a_current_edge_claims_about_itself_is_ignored() -> None:
    """Affirmed state belongs to the recorded stream. A current edge arriving
    with an active state and a hash, unknown to the case, derives as pending —
    getting the two roles the wrong way round must not invert the verdict."""
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    boastful = affirmed("Implements", impl, sreq)
    derivation = drift.derive(
        recorded=Source((sreq, impl), ()),
        current=Source((sreq, impl), (boastful,)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.PENDING


# --- broken: every edge touching a node absent from the current records ----


def test_an_affirmed_edge_whose_target_vanished_is_broken() -> None:
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), (affirmed("Implements", impl, sreq),)),
        current=Source((impl,), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.BROKEN


def test_an_affirmed_edge_whose_source_vanished_is_broken() -> None:
    """With an endpoint gone there is no content to compare, so broken takes
    precedence over the whole truth table."""
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    derivation = drift.derive(
        recorded=Source((sreq, impl), (affirmed("Implements", impl, sreq),)),
        current=Source((sreq,), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.BROKEN


def test_a_never_affirmed_dangling_edge_is_broken_not_pending() -> None:
    sreq = requirement("SREQ-1")
    derivation = drift.derive(
        recorded=Source((), ()),
        current=Source((sreq,), (declared("Implements", "pkg.fn", "SREQ-1"),)),
    )
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.BROKEN


def test_an_evidence_edge_to_an_absent_node_is_broken_too() -> None:
    """SEG-SREQ-017 says every edge, and means it — the evidence boundary
    stops suspicion, not brokenness."""
    run = outcome("run-1/TS-1")
    derivation = drift.derive(
        recorded=Source((), ()),
        current=Source((run,), (declared("Confirms", "run-1/TS-1", "TS-1"),)),
    )
    assert state_of(derivation, "Confirms", "run-1/TS-1", "TS-1") is LinkState.BROKEN


# --- the dependency relation: direction, reach, and the evidence boundary --


def test_suspicion_climbs_a_chain_of_strong_edges() -> None:
    top, sys, sreq = requirement("TOP-1"), requirement("SYS-1"), requirement("SREQ-1")
    impl_v1, impl_v2 = implementation("pkg.fn"), implementation("pkg.fn", "v2")
    recorded = Source(
        (top, sys, sreq, impl_v1),
        (
            affirmed("Refines", sys, top),
            affirmed("Refines", sreq, sys),
            affirmed("Implements", impl_v1, sreq),
        ),
    )
    current = Source(
        (top, sys, sreq, impl_v2),
        (
            declared("Refines", "SYS-1", "TOP-1"),
            declared("Refines", "SREQ-1", "SYS-1"),
            declared("Implements", "pkg.fn", "SREQ-1"),
        ),
    )
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT
    assert state_of(derivation, "Refines", "SYS-1", "TOP-1") is LinkState.TRANSITIVELY_SUSPECT


def test_suspicion_stops_at_the_evidence_boundary() -> None:
    """A drifted outcome outdates its own confirms edge, but the verifies
    edge above the specification stays active: re-execution is what a stale
    outcome needs, and marking the specification suspect would invite a
    re-affirmation instead."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    run_v1, run_v2 = outcome("run-1/TS-1"), outcome("run-1/TS-1", "v2")
    recorded = Source(
        (sreq, spec, run_v1),
        (affirmed("Verifies", spec, sreq), affirmed("Confirms", run_v1, spec)),
    )
    current = Source(
        (sreq, spec, run_v2),
        (declared("Verifies", "TS-1", "SREQ-1"), declared("Confirms", "run-1/TS-1", "TS-1")),
    )
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Confirms", "run-1/TS-1", "TS-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Verifies", "TS-1", "SREQ-1") is LinkState.ACTIVE


def test_dependencies_attach_at_the_source_endpoint_not_at_siblings() -> None:
    """A drifted implementation under a requirement unsettles the edge whose
    subtree it sits in — the refines edge above — and leaves the sibling
    verifies edge into the same requirement alone. Affirmation is owed at the
    change site, not across the neighbourhood."""
    sys, sreq, spec = requirement("SYS-1"), requirement("SREQ-1"), specification("TS-1")
    impl_v1, impl_v2 = implementation("pkg.fn"), implementation("pkg.fn", "v2")
    recorded = Source(
        (sys, sreq, spec, impl_v1),
        (
            affirmed("Refines", sreq, sys),
            affirmed("Verifies", spec, sreq),
            affirmed("Implements", impl_v1, sreq),
        ),
    )
    current = Source(
        (sys, sreq, spec, impl_v2),
        (
            declared("Refines", "SREQ-1", "SYS-1"),
            declared("Verifies", "TS-1", "SREQ-1"),
            declared("Implements", "pkg.fn", "SREQ-1"),
        ),
    )
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT
    assert state_of(derivation, "Verifies", "TS-1", "SREQ-1") is LinkState.ACTIVE


def test_a_pending_dependency_is_not_active_and_unsettles_the_edge_above() -> None:
    sys, sreq, impl = requirement("SYS-1"), requirement("SREQ-1"), implementation("pkg.fn")
    recorded = Source((sys, sreq, impl), (affirmed("Refines", sreq, sys),))
    current = Source(
        (sys, sreq, impl),
        (declared("Refines", "SREQ-1", "SYS-1"), declared("Implements", "pkg.fn", "SREQ-1")),
    )
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.PENDING
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT


def test_a_broken_dependency_is_not_active_and_unsettles_the_edge_above() -> None:
    sys, sreq, impl = requirement("SYS-1"), requirement("SREQ-1"), implementation("pkg.fn")
    recorded = Source(
        (sys, sreq, impl),
        (affirmed("Refines", sreq, sys), affirmed("Implements", impl, sreq)),
    )
    current = Source(
        (sys, sreq),
        (declared("Refines", "SREQ-1", "SYS-1"), declared("Implements", "pkg.fn", "SREQ-1")),
    )
    derivation = drift.derive(recorded=recorded, current=current)
    assert state_of(derivation, "Implements", "pkg.fn", "SREQ-1") is LinkState.BROKEN
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT


# --- suspicion clears by recomputation, never by a second affirmation ------


def test_suspicion_clears_by_recomputation_once_the_change_site_is_reaffirmed() -> None:
    """Two derivation runs. The first sees a drifted implementation: its edge
    is directly outdated, the ancestor transitively suspect. Between the runs
    the operator re-affirms the change site — the recorded implements edge now
    carries the hash over today's content — and the second run derives the
    ancestor active again, though no one ever re-affirmed *it*."""
    sys, sreq = requirement("SYS-1"), requirement("SREQ-1")
    impl_v1, impl_v2 = implementation("pkg.fn"), implementation("pkg.fn", "v2")
    refines_affirmed = affirmed("Refines", sreq, sys)
    current = Source(
        (sys, sreq, impl_v2),
        (declared("Refines", "SREQ-1", "SYS-1"), declared("Implements", "pkg.fn", "SREQ-1")),
    )

    first = drift.derive(
        recorded=Source(
            (sys, sreq, impl_v1), (refines_affirmed, affirmed("Implements", impl_v1, sreq))
        ),
        current=current,
    )
    assert state_of(first, "Implements", "pkg.fn", "SREQ-1") is LinkState.DIRECTLY_OUTDATED
    assert state_of(first, "Refines", "SREQ-1", "SYS-1") is LinkState.TRANSITIVELY_SUSPECT

    second = drift.derive(
        recorded=Source(
            (sys, sreq, impl_v2), (refines_affirmed, affirmed("Implements", impl_v2, sreq))
        ),
        current=current,
    )
    assert state_of(second, "Implements", "pkg.fn", "SREQ-1") is LinkState.ACTIVE
    assert state_of(second, "Refines", "SREQ-1", "SYS-1") is LinkState.ACTIVE


# --- the output: a record source the graph builder consumes ----------------


def test_the_derivation_is_a_record_source_carrying_derived_states() -> None:
    recorded, current = chain(impl_seed="v2")
    derivation = drift.derive(recorded=recorded, current=current)
    assert isinstance(derivation, RecordSource)
    built = graph.build(derivation)
    states = {
        EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id): edge.state
        for edge in built.edges
    }
    assert states[EdgeReference(kind="Implements", from_id="pkg.fn", to_id="SREQ-1")] is (
        LinkState.DIRECTLY_OUTDATED
    )
    assert states[EdgeReference(kind="Refines", from_id="SREQ-1", to_id="SYS-1")] is (
        LinkState.TRANSITIVELY_SUSPECT
    )
    assert built.node_ids() == {"SYS-1", "SREQ-1", "pkg.fn"}


def test_satisfaction_over_the_derived_graph_sees_the_suspicion() -> None:
    """The pipeline the engine runs: derive, build, evaluate. A leaf covered
    by active edges loses its coverage when the implementation drifts."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    run = outcome("run-1/TS-1")
    impl_v1, impl_v2 = implementation("pkg.fn"), implementation("pkg.fn", "v2")
    recorded_edges = (
        affirmed("Verifies", spec, sreq),
        affirmed("Implements", impl_v1, sreq),
        declared("Confirms", "run-1/TS-1", "TS-1"),
        declared("Witnesses", "run-1/TS-1", "pkg.fn"),
    )
    current_edges = tuple(declared(edge.kind, edge.from_id, edge.to_id) for edge in recorded_edges)

    covered = drift.derive(
        recorded=Source((sreq, spec, run, impl_v1), recorded_edges),
        current=Source((sreq, spec, run, impl_v1), current_edges),
    )
    assert satisfaction.evaluate(graph.build(covered)).is_satisfied("SREQ-1")

    drifted = drift.derive(
        recorded=Source((sreq, spec, run, impl_v1), recorded_edges),
        current=Source((sreq, spec, run, impl_v2), current_edges),
    )
    assert not satisfaction.evaluate(graph.build(drifted)).is_satisfied("SREQ-1")


def test_each_input_stream_is_asked_for_at_most_once() -> None:
    recorded, current = chain()
    once_recorded = OneShotSource(list(recorded.nodes()), list(recorded.edges()))
    once_current = OneShotSource(list(current.nodes()), list(current.edges()))
    derivation = drift.derive(recorded=once_recorded, current=once_current)
    assert state_of(derivation, "Refines", "SREQ-1", "SYS-1") is LinkState.ACTIVE


def test_derivation_leaves_both_input_streams_unchanged() -> None:
    recorded, current = chain(impl_seed="v2")
    recorded_before = (list(recorded.nodes()), list(recorded.edges()))
    current_before = (list(current.nodes()), list(current.edges()))
    drift.derive(recorded=recorded, current=current)
    assert (list(recorded.nodes()), list(recorded.edges())) == recorded_before
    assert (list(current.nodes()), list(current.edges())) == current_before


# --- unmatched edges --------------------------------------------------------


def test_a_recorded_edge_absent_from_current_is_named_not_stated() -> None:
    """The derived stream is today's topology; an affirmed edge whose
    declaration vanished from source is carried untouched in ``vanished``
    with no state claimed for it — what it *is* awaits a requirement."""
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    gone = affirmed("Implements", impl, sreq)
    derivation = drift.derive(
        recorded=Source((sreq, impl), (gone,)),
        current=Source((sreq, impl), ()),
    )
    assert list(derivation.edges()) == []
    assert derivation.vanished == (gone,)


def test_a_matched_recorded_edge_is_not_vanished() -> None:
    recorded, current = chain()
    derivation = drift.derive(recorded=recorded, current=current)
    assert derivation.vanished == ()


# --- refusals ----------------------------------------------------------------


def test_a_strong_cycle_is_refused_loudly() -> None:
    """Ill-kinded records can cycle strong edges past the refines gate; the
    derivation refuses rather than diverging or quietly assigning states."""
    one, other = requirement("REQ-A"), requirement("REQ-B")
    recorded = Source(
        (one, other),
        (affirmed("Verifies", one, other), affirmed("Implements", other, one)),
    )
    current = Source(
        (one, other),
        (declared("Verifies", "REQ-A", "REQ-B"), declared("Implements", "REQ-B", "REQ-A")),
    )
    with pytest.raises(drift.DriftError, match="cycle"):
        drift.derive(recorded=recorded, current=current)


def test_duplicate_recorded_edges_are_refused() -> None:
    """Two recorded records for one edge cannot both be the affirmation."""
    sreq, impl = requirement("SREQ-1"), implementation("pkg.fn")
    twice = (
        affirmed("Implements", impl, sreq),
        records.EdgeRecord("pkg.fn", "SREQ-1", "Implements", LinkState.ACTIVE, STALE),
    )
    with pytest.raises(drift.DriftError, match="more than once"):
        drift.derive(
            recorded=Source((sreq, impl), twice),
            current=Source((sreq, impl), (declared("Implements", "pkg.fn", "SREQ-1"),)),
        )


# --- the store-backed round trip --------------------------------------------


def test_store_backed_round_trip_derives_drift_and_leaves_the_case_unchanged(
    tmp_path: Path,
) -> None:
    """The workflow end to end: affirm the would-be store's slice into a
    fresh case through the write face, drift one implementation's content,
    and derive with the read face as the recorded stream. The change site
    comes out directly outdated, the requirement chain above it transitively
    suspect, untouched siblings stay active — and the case is byte-identical
    afterwards (SEG-SREQ-034)."""
    content_root = tmp_path / "store"
    shutil.copytree(WOULD_BE_STORE, content_root)
    current = StoreLoader(root=content_root)
    store = case.AffirmationStore(root=tmp_path / "case")

    nodes = list(current.nodes())
    hashes = {node.local_id: node_hash_of(node) for node in nodes}
    strong = taxonomy.propagating_edge_kinds()
    store.write_nodes(nodes)
    store.write_edges(
        [
            records.EdgeRecord(
                from_id=edge.from_id,
                to_id=edge.to_id,
                kind=edge.kind,
                state=LinkState.ACTIVE,
                edge_hash=commitment.edge_hash(
                    edge.from_id, edge.to_id, edge.kind, hashes[edge.from_id], hashes[edge.to_id]
                ),
            )
            if edge.kind in strong
            else edge
            for edge in current.edges()
        ]
    )

    unchanged = drift.derive(recorded=store, current=current)
    assert {edge.state for edge in unchanged.edges() if edge.kind in strong} == {LinkState.ACTIVE}
    assert {edge.state for edge in unchanged.edges() if edge.kind not in strong} == {
        LinkState.PENDING
    }

    drifted_body = (
        content_root / "content" / "implementation" / "affirmatrix.commitment.node_hash.body.txt"
    )
    drifted_body.write_bytes(drifted_body.read_bytes() + b"\n# content drifted after affirmation\n")
    case_before = {
        path: path.read_bytes() for path in sorted((tmp_path / "case").rglob("*")) if path.is_file()
    }

    derivation = drift.derive(recorded=store, current=current)
    assert (
        state_of(derivation, "Implements", "affirmatrix.commitment.node_hash", "SEG-SREQ-005")
        is LinkState.DIRECTLY_OUTDATED
    )
    assert (
        state_of(derivation, "Refines", "SEG-SREQ-005", "SEG-SYS-001")
        is LinkState.TRANSITIVELY_SUSPECT
    )
    assert (
        state_of(derivation, "Implements", "affirmatrix.commitment.edge_hash", "SEG-SREQ-002")
        is LinkState.ACTIVE
    )
    assert state_of(derivation, "Refines", "SEG-SREQ-002", "SEG-SYS-001") is LinkState.ACTIVE
    assert derivation.vanished == ()

    case_after = {
        path: path.read_bytes() for path in sorted((tmp_path / "case").rglob("*")) if path.is_file()
    }
    assert case_after == case_before


# --- the per-hash comparison against the affirming event (SEG-SREQ-128) -----


def affirming_event(
    from_node: records.NodeRecord,
    to_node: records.NodeRecord,
    *,
    kind: str = "Implements",
    from_source_revision: str = "a" * 40,
    to_source_revision: str = "b" * 40,
) -> records.ReviewEvent:
    """The event a real affirmation of ``from_node -> to_node`` would compose —
    built directly, the way :func:`affirmatrix.affirmation.compose` builds it,
    so a test can affirm against one seed and then compare against another."""
    return records.ReviewEvent(
        from_id=from_node.local_id,
        to_id=to_node.local_id,
        kind=kind,
        from_source_revision=from_source_revision,
        to_source_revision=to_source_revision,
        from_content_anchors=from_node.content_anchors,
        to_content_anchors=to_node.content_anchors,
        role="SoftwareEngineer",
        reason="reviewed",
    )


def reference(from_node: records.NodeRecord, to_node: records.NodeRecord) -> EdgeReference:
    return EdgeReference(kind="Implements", from_id=from_node.local_id, to_id=to_node.local_id)


def test_an_unmoved_hash_compares_as_matching() -> None:
    impl = implementation("pkg.fn", "v1")
    sreq = requirement("SEG-SREQ-1", "v1")
    event = affirming_event(impl, sreq)
    comparison = drift.compare(
        reference(impl, sreq), current_from=impl, current_to=sreq, event=event
    )
    assert {row.status for row in comparison.from_hashes} == {drift.HashStatus.MATCHING}
    assert {row.status for row in comparison.to_hashes} == {drift.HashStatus.MATCHING}


def test_a_moved_hash_compares_as_differing() -> None:
    impl_then = implementation("pkg.fn", "v1")
    impl_now = implementation("pkg.fn", "v2")
    sreq = requirement("SEG-SREQ-1", "v1")
    event = affirming_event(impl_then, sreq)
    comparison = drift.compare(
        reference(impl_then, sreq), current_from=impl_now, current_to=sreq, event=event
    )
    by_name = {row.name: row for row in comparison.from_hashes}
    assert {row.status for row in by_name.values()} == {drift.HashStatus.DIFFERING}
    assert by_name["apiHash"].recorded == impl_then.content_anchors["apiHash"]
    assert by_name["apiHash"].current == impl_now.content_anchors["apiHash"]
    assert by_name["apiHash"].source_revision == event.from_source_revision


def test_a_name_the_event_never_carried_compares_as_current_only() -> None:
    """A hash gained since the affirming judgement — not an error, a fact."""
    impl_then = records.NodeRecord("pkg.fn", "Implementation", anchors(("apiHash",), "v1"))
    impl_now = implementation("pkg.fn", "v1")  # apiHash + bodyHash
    sreq = requirement("SEG-SREQ-1", "v1")
    event = affirming_event(impl_then, sreq)
    comparison = drift.compare(
        reference(impl_then, sreq), current_from=impl_now, current_to=sreq, event=event
    )
    by_name = {row.name: row for row in comparison.from_hashes}
    assert by_name["bodyHash"].status is drift.HashStatus.CURRENT_ONLY
    assert by_name["bodyHash"].recorded is None
    assert by_name["bodyHash"].current == impl_now.content_anchors["bodyHash"]
    assert by_name["apiHash"].status is drift.HashStatus.MATCHING


def test_a_name_only_the_event_carried_compares_as_recorded_only() -> None:
    """A hash dropped since the affirming judgement, the mirror image."""
    impl_then = implementation("pkg.fn", "v1")  # apiHash + bodyHash
    impl_now = records.NodeRecord("pkg.fn", "Implementation", anchors(("apiHash",), "v1"))
    sreq = requirement("SEG-SREQ-1", "v1")
    event = affirming_event(impl_then, sreq)
    comparison = drift.compare(
        reference(impl_then, sreq), current_from=impl_now, current_to=sreq, event=event
    )
    by_name = {row.name: row for row in comparison.from_hashes}
    assert by_name["bodyHash"].status is drift.HashStatus.RECORDED_ONLY
    assert by_name["bodyHash"].current is None
    assert by_name["bodyHash"].recorded == impl_then.content_anchors["bodyHash"]


def test_both_endpoints_moving_is_reported_independently() -> None:
    impl_then, sreq_then = implementation("pkg.fn", "v1"), requirement("SEG-SREQ-1", "v1")
    impl_now, sreq_now = implementation("pkg.fn", "v2"), requirement("SEG-SREQ-1", "v2")
    event = affirming_event(impl_then, sreq_then)
    comparison = drift.compare(
        reference(impl_then, sreq_then), current_from=impl_now, current_to=sreq_now, event=event
    )
    assert {row.status for row in comparison.from_hashes} == {drift.HashStatus.DIFFERING}
    assert {row.status for row in comparison.to_hashes} == {drift.HashStatus.DIFFERING}


def test_comparing_against_the_wrong_events_edge_is_refused() -> None:
    impl, sreq = implementation("pkg.fn", "v1"), requirement("SEG-SREQ-1", "v1")
    other = requirement("SEG-SREQ-2", "v1")
    event = affirming_event(impl, other)
    with pytest.raises(drift.DriftError, match="SEG-SREQ-2"):
        drift.compare(reference(impl, sreq), current_from=impl, current_to=sreq, event=event)
