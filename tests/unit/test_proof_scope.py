"""Scope collection (SEG-SREQ-036, -039, -052) and the induced subgraph it hands the gate.

Fixture graphs are built in memory from literal records, like ``test_gates.py``
and ``test_graph.py``; nothing here touches the repository's own case, and
scope collection is exercised as the pure function it is — no store, no
package file, no mutation.

Two tests are worth reading before the rest: one pins that a scope's induced
subgraph is exactly the cut over its member set, no more and no less, by
comparing ``package_gate`` over the collected subgraph against
``package_gate`` over an independently restricted graph built from nothing
but the published member ids; the other pins the deliberate divergence this
brings — an outcome witnessing an implementation outside a requested scope is
incomplete *within that scope* and the gate says so, even though the same
outcome is complete evidence over the whole graph.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from affirmatrix import gates, graph, proof, records
from affirmatrix.records import LinkState, TestResult

#: A fixed instant for every scope collected in this file — determinism tests
#: would otherwise depend on which second the suite happened to run.
TIMESTAMP = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

#: A fixed "today" for the gate calls in this file, matching ``test_gates.py``.
EVALUATION_DATE = date(2026, 6, 1)


class Source:
    """A record source built from literals."""

    def __init__(self, nodes=(), edges=()):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def anchors(names: tuple[str, ...], seed: str) -> dict[str, records.ContentAnchor]:
    return {
        name: records.ContentAnchor(
            digest=hashlib.sha256(f"{name}:{seed}".encode()).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }


def requirement(local_id: str, seed: str | None = None) -> records.NodeRecord:
    return records.NodeRecord(local_id, "Requirement", anchors(("contentHash",), seed or local_id))


def implementation(local_id: str, seed: str | None = None) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "Implementation", anchors(("apiHash", "bodyHash"), seed or local_id)
    )


def specification(local_id: str, seed: str | None = None) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "TestSpecification", anchors(("specHash", "implHash"), seed or local_id)
    )


def outcome(
    local_id: str, seed: str | None = None, result: TestResult = TestResult.PASSED
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id, "TestOutcome", anchors(("contentHash",), seed or local_id), result=result
    )


def waiver(
    local_id: str,
    seed: str | None = None,
    expiry: date = date(2099, 1, 1),
    approver: str = "A. Reviewer",
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id,
        "Waiver",
        anchors(("contentHash",), seed or local_id),
        expiry=expiry,
        approver=approver,
    )


def edge(
    kind: str, from_id: str, to_id: str, state: LinkState = LinkState.PENDING
) -> records.EdgeRecord:
    """A literal edge. Scope collection reads endpoints and kinds, never state."""
    return records.EdgeRecord(from_id=from_id, to_id=to_id, kind=kind, state=state)


# ── One test per expansion hop ──────────────────────────────────────────────


def test_scope_includes_the_requested_requirement() -> None:
    built = graph.build(Source([requirement("SEG-SREQ-001")]))
    scope = proof.collect_scope(built, {"SEG-SREQ-001"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"SEG-SREQ-001"}
    assert scope.requested_ids == {"SEG-SREQ-001"}


def test_scope_includes_a_direct_refiner() -> None:
    source = Source(
        [requirement("parent"), requirement("child")],
        [edge("Refines", "child", "parent")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"parent"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"parent", "child"}


def test_scope_includes_refiners_transitively() -> None:
    source = Source(
        [requirement("top"), requirement("middle"), requirement("leaf")],
        [edge("Refines", "middle", "top"), edge("Refines", "leaf", "middle")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"top"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"top", "middle", "leaf"}


def test_scope_excludes_an_ancestor_and_its_other_children() -> None:
    """Pins the ruling: 'refines upward' means refiners, never an ancestor.

    A parent pulled in without ``sibling`` — nobody requested it — would let
    the gate force ``sibling`` satisfied and report the parent clean on a
    subtree this scope never checked.
    """
    source = Source(
        [requirement("parent"), requirement("requested"), requirement("sibling")],
        [edge("Refines", "requested", "parent"), edge("Refines", "sibling", "parent")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"requested"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"requested"}


def test_scope_includes_a_verifying_specification() -> None:
    source = Source(
        [requirement("req"), specification("spec")],
        [edge("Verifies", "spec", "req")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"req", "spec"}


def test_scope_includes_an_implementing_implementation() -> None:
    source = Source(
        [requirement("req"), implementation("impl")],
        [edge("Implements", "impl", "req")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"req", "impl"}


def test_scope_includes_a_confirming_outcome() -> None:
    """The evidence ride-along: an outcome joins the scope via the specification it confirms."""
    source = Source(
        [requirement("req"), specification("spec"), outcome("run/spec")],
        [edge("Verifies", "spec", "req"), edge("Confirms", "run/spec", "spec")],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"req", "spec", "run/spec"}


def test_scope_includes_an_excusing_waiver() -> None:
    source = Source(
        [
            requirement("req"),
            specification("spec"),
            outcome("run/spec", result=TestResult.FAILED),
            waiver("waiver-1"),
        ],
        [
            edge("Verifies", "spec", "req"),
            edge("Confirms", "run/spec", "spec"),
            edge("Excuses", "waiver-1", "run/spec"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"req", "spec", "run/spec", "waiver-1"}


def test_the_composite_walk_collects_every_hop_in_one_pass() -> None:
    source = Source(
        [
            requirement("top"),
            requirement("child"),
            specification("spec"),
            implementation("impl"),
            outcome("run/spec", result=TestResult.FAILED),
            waiver("waiver-1"),
        ],
        [
            edge("Refines", "child", "top"),
            edge("Verifies", "spec", "child"),
            edge("Implements", "impl", "child"),
            edge("Confirms", "run/spec", "spec"),
            edge("Excuses", "waiver-1", "run/spec"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"top"}, snapshot_timestamp=TIMESTAMP)
    assert scope.member_ids == {"top", "child", "spec", "impl", "run/spec", "waiver-1"}


# ── The induced subgraph, and the cross-scope witnesses ruling ─────────────


def test_the_subgraph_keeps_a_witnesses_edge_between_two_in_scope_nodes() -> None:
    source = Source(
        [requirement("req"), specification("spec"), implementation("impl"), outcome("run/spec")],
        [
            edge("Verifies", "spec", "req"),
            edge("Implements", "impl", "req"),
            edge("Confirms", "run/spec", "spec"),
            edge("Witnesses", "run/spec", "impl"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    witnesses = [e for e in scope.subgraph.edges if e.kind == "Witnesses"]
    assert len(witnesses) == 1
    assert witnesses[0].from_id == "run/spec"
    assert witnesses[0].to_id == "impl"


def test_an_outcome_witnessing_an_out_of_scope_implementation_loses_that_edge() -> None:
    """No membership hop for ``Witnesses``: the scope is a deliberate cut, never widened."""
    source = Source(
        [
            requirement("req"),
            requirement("other-req"),
            specification("spec"),
            implementation("other-impl"),
            outcome("run/spec"),
        ],
        [
            edge("Verifies", "spec", "req"),
            edge("Implements", "other-impl", "other-req"),
            edge("Confirms", "run/spec", "spec"),
            edge("Witnesses", "run/spec", "other-impl"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert "run/spec" in scope.member_ids
    assert "other-impl" not in scope.member_ids
    assert not [e for e in scope.subgraph.edges if e.kind == "Witnesses"]


def test_the_gate_discards_an_outcome_whose_witnesses_edge_fell_outside_the_scope() -> None:
    """The deliberate divergence: incomplete for this scope, complete for the whole graph."""
    source = Source(
        [
            requirement("req"),
            requirement("other-req"),
            specification("spec"),
            implementation("other-impl"),
            outcome("run/spec"),
        ],
        [
            edge("Verifies", "spec", "req"),
            edge("Implements", "other-impl", "other-req"),
            edge("Confirms", "run/spec", "spec"),
            edge("Witnesses", "run/spec", "other-impl"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)

    report_over_scope = gates.package_gate(scope.subgraph, evaluation_date=EVALUATION_DATE)
    report_over_whole_graph = gates.package_gate(built, evaluation_date=EVALUATION_DATE)

    assert "run/spec" in report_over_scope.discarded_outcomes
    assert "run/spec" not in report_over_whole_graph.discarded_outcomes


def test_package_gate_over_the_collected_subgraph_matches_an_independent_restriction() -> None:
    """The no-false-findings test: the scope's subgraph is exactly the cut over its members."""
    source = Source(
        [
            requirement("top"),
            requirement("child"),
            specification("spec"),
            implementation("impl"),
            outcome("run/spec", result=TestResult.FAILED),
            waiver("waiver-1"),
            requirement("unrelated"),
            specification("unrelated-spec"),
        ],
        [
            edge("Refines", "child", "top"),
            edge("Verifies", "spec", "child"),
            edge("Implements", "impl", "child"),
            edge("Confirms", "run/spec", "spec"),
            edge("Excuses", "waiver-1", "run/spec"),
            edge("Verifies", "unrelated-spec", "unrelated"),
        ],
    )
    built = graph.build(source)
    scope = proof.collect_scope(built, {"top"}, snapshot_timestamp=TIMESTAMP)

    independently_restricted = built.restricted_to(scope.member_ids)
    report_from_scope = gates.package_gate(scope.subgraph, evaluation_date=EVALUATION_DATE)
    report_from_independent_cut = gates.package_gate(
        independently_restricted, evaluation_date=EVALUATION_DATE
    )

    assert report_from_scope.diagnostics == report_from_independent_cut.diagnostics
    assert report_from_scope.blocked == report_from_independent_cut.blocked
    assert "unrelated" not in scope.member_ids


# ── SEG-SREQ-036: a requested id that does not hold is refused loudly ──────


def test_requesting_an_absent_id_raises_scope_error() -> None:
    built = graph.build(Source([requirement("a")]))
    with pytest.raises(proof.ScopeError, match="missing"):
        proof.collect_scope(built, {"missing"}, snapshot_timestamp=TIMESTAMP)


def test_requesting_a_non_requirement_id_raises_scope_error() -> None:
    built = graph.build(Source([implementation("impl")]))
    with pytest.raises(proof.ScopeError, match="impl"):
        proof.collect_scope(built, {"impl"}, snapshot_timestamp=TIMESTAMP)


# ── SEG-SREQ-039: the partial-vs-total signal ───────────────────────────────


def test_total_is_true_when_the_scope_covers_every_top_level_requirement() -> None:
    built = graph.build(Source([requirement("top1"), requirement("top2")]))
    scope = proof.collect_scope(built, {"top1", "top2"}, snapshot_timestamp=TIMESTAMP)
    assert scope.total is True


def test_total_is_false_when_a_top_level_requirement_is_missing() -> None:
    built = graph.build(Source([requirement("top1"), requirement("top2")]))
    scope = proof.collect_scope(built, {"top1"}, snapshot_timestamp=TIMESTAMP)
    assert scope.total is False


def test_total_is_vacuously_true_for_a_graph_with_no_requirements() -> None:
    built = graph.build(Source([implementation("impl")]))
    scope = proof.collect_scope(built, set(), snapshot_timestamp=TIMESTAMP)
    assert scope.total is True
    assert scope.member_ids == frozenset()


# ── SEG-SREQ-052: the snapshot identifier ───────────────────────────────────


def test_snapshot_identifier_uses_only_posix_and_windows_safe_characters() -> None:
    built = graph.build(Source([requirement("req")]))
    scope = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP)
    reserved = set('<>:"/\\|?*') | {chr(code) for code in range(0x20)}
    assert not reserved & set(scope.snapshot_id)


def test_snapshot_identifier_is_deterministic_for_the_same_scope_and_timestamp() -> None:
    def make_id() -> str:
        built = graph.build(Source([requirement("req")]))
        return proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP).snapshot_id

    assert make_id() == make_id()


def test_snapshot_identifier_changes_when_an_outcome_is_added() -> None:
    """Evidence-inclusive: the fingerprint folds every in-scope edge, outcomes included."""
    without_outcome = graph.build(
        Source([requirement("req"), specification("spec")], [edge("Verifies", "spec", "req")])
    )
    with_outcome = graph.build(
        Source(
            [requirement("req"), specification("spec"), outcome("run/spec")],
            [edge("Verifies", "spec", "req"), edge("Confirms", "run/spec", "spec")],
        )
    )
    scope_without = proof.collect_scope(without_outcome, {"req"}, snapshot_timestamp=TIMESTAMP)
    scope_with = proof.collect_scope(with_outcome, {"req"}, snapshot_timestamp=TIMESTAMP)
    assert scope_without.snapshot_id != scope_with.snapshot_id


def test_snapshot_identifier_changes_when_the_timestamp_changes() -> None:
    built = graph.build(Source([requirement("req")]))
    first = proof.collect_scope(built, {"req"}, snapshot_timestamp=TIMESTAMP).snapshot_id
    second = proof.collect_scope(
        built, {"req"}, snapshot_timestamp=TIMESTAMP.replace(year=2027)
    ).snapshot_id
    assert first != second


def test_a_naive_timestamp_is_rejected() -> None:
    built = graph.build(Source([requirement("req")]))
    with pytest.raises(ValueError, match="timezone"):
        proof.collect_scope(built, {"req"}, snapshot_timestamp=datetime(2026, 6, 1))


# ── SEG-SREQ-041's discipline half: collection changes nothing ─────────────


def test_collect_scope_leaves_the_input_graph_unchanged() -> None:
    source = Source(
        [requirement("top"), requirement("child"), specification("spec")],
        [edge("Refines", "child", "top"), edge("Verifies", "spec", "child")],
    )
    built = graph.build(source)
    edges_before, node_ids_before = built.edges, built.node_ids()

    proof.collect_scope(built, {"top"}, snapshot_timestamp=TIMESTAMP)

    assert built.edges == edges_before
    assert built.node_ids() == node_ids_before
