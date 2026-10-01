"""Package assembly and persistence (SEG-SREQ-035…041, -046…048) and the
store's proof-document read face (SEG-SREQ-019…022 over proofs).

Two tests are worth reading before the rest: one is the auditor's test —
recomputing a design consistency proof's own root from that one persisted
document alone, with no :class:`~affirmatrix.graph.Graph` anywhere in scope —
because that is the whole point of SEG-SYS-005; the other is that a blocked
scope's ``assemble`` call raises before any document body is built, so
``persist`` is never reached and no case directory ever comes into being.

A second thing worth reading before the rest: refusal and error are
different kinds of stop, never one caught as the other.
:class:`~affirmatrix.proof.GenerationRefused` is the gate's own verdict
acted on; a :class:`~affirmatrix.proof.ScopeError` or the ``ValueError`` an
ambiguous confirming outcome earns are inputs the generator cannot even
judge. The tests near the bottom of the file pin both directions.

Fixture graphs are built in memory from literal records, like
``test_proof_scope.py`` and ``test_gates.py``; every store is a fresh
``tmp_path`` case. Nothing here touches the repository's own case, and no
test affirms anything anywhere.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest

from affirmatrix import case, commitment, gates, graph, proof, records
from affirmatrix.proof import _package
from affirmatrix.records import LinkState, TestResult

#: A fixed instant for every scope collected in this file.
TIMESTAMP = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

#: A fixed "today" for every gate evaluation in this file.
EVALUATION_DATE = date(2026, 6, 1)

#: A fixed "current revision" for every gate evaluation in this file that
#: does not itself test staleness.
CURRENT_REVISION = "r1"


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
    local_id: str,
    seed: str | None = None,
    result: TestResult = TestResult.PASSED,
    revision: str = CURRENT_REVISION,
) -> records.NodeRecord:
    return records.NodeRecord(
        local_id,
        "TestOutcome",
        anchors(("contentHash",), seed or local_id),
        result=result,
        revision=revision,
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
    kind: str, from_id: str, to_id: str, state: LinkState = LinkState.ACTIVE
) -> records.EdgeRecord:
    """A literal, affirmed-looking edge. Assembly reads endpoints and kinds; the
    package gate reads state — every strong edge here is active so a fully
    covered fixture is ready, not blocked."""
    edge_hash = (
        None
        if state is LinkState.PENDING
        else hashlib.sha256(f"{kind}:{from_id}:{to_id}".encode()).digest()
    )
    return records.EdgeRecord(
        from_id=from_id, to_id=to_id, kind=kind, state=state, edge_hash=edge_hash
    )


def ready_fixture() -> tuple[list[records.NodeRecord], list[records.EdgeRecord]]:
    """One fully covered, fully affirmed leaf requirement — a ready scope."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl, run = implementation("pkg.fn"), outcome("run-1/TS-1")
    nodes = [sreq, spec, impl, run]
    edges = [
        edge("Verifies", "TS-1", "SREQ-1"),
        edge("Implements", "pkg.fn", "SREQ-1"),
        edge("Confirms", "run-1/TS-1", "TS-1"),
        edge("Witnesses", "run-1/TS-1", "pkg.fn"),
    ]
    return nodes, edges


def assembled(nodes, edges, requested_ids) -> _package.Package:
    built = graph.build(Source(nodes, edges))
    return proof.assemble(
        built,
        requested_ids,
        snapshot_timestamp=TIMESTAMP,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )


# ── A ready scope assembles all four documents ──────────────────────────────


def test_a_ready_scope_assembles_all_four_documents() -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    assert not package.coverage_report.blocked
    assert set(package.documents) == {
        proof.DESIGN_CONSISTENCY_PROOF,
        proof.EXECUTION_COVERAGE_RECORD,
        proof.COVERAGE_REPORT,
        proof.EVIDENCE_MANIFEST,
    }


def test_a_ready_scope_with_informational_findings_is_not_refused() -> None:
    """A stale outcome is informational, never blocking (SEG-SREQ-063,
    SEG-SREQ-067): the scope still assembles, and the finding still shows up
    in its coverage report document."""
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl = implementation("pkg.fn")
    fresh_run = outcome("run-1/TS-1")
    stale_run = outcome("run-2/TS-1", revision="a-different-revision")
    nodes = [sreq, spec, impl, fresh_run, stale_run]
    edges = [
        edge("Verifies", "TS-1", "SREQ-1"),
        edge("Implements", "pkg.fn", "SREQ-1"),
        edge("Confirms", "run-1/TS-1", "TS-1"),
        edge("Witnesses", "run-1/TS-1", "pkg.fn"),
        edge("Confirms", "run-2/TS-1", "TS-1"),
        edge("Witnesses", "run-2/TS-1", "pkg.fn"),
    ]
    package = assembled(nodes, edges, {"SREQ-1"})
    assert not package.coverage_report.blocked
    assert package.coverage_report.stale_outcomes == {"run-2/TS-1"}
    assert package.documents[proof.COVERAGE_REPORT]["staleOutcomes"] == ["run-2/TS-1"]


# ── Refusal (SEG-SREQ-046, SEG-SREQ-047, SEG-SREQ-048) ──────────────────────


def test_a_blocked_scope_raises_generation_refused() -> None:
    orphan = requirement("ORPHAN-1")
    built = graph.build(Source([orphan], []))
    with pytest.raises(proof.GenerationRefused) as caught:
        proof.assemble(
            built,
            {"ORPHAN-1"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    refusal = caught.value
    assert refusal.scope.requested_ids == {"ORPHAN-1"}
    expected_scope, expected_report = _package.check_readiness(
        built,
        {"ORPHAN-1"},
        snapshot_timestamp=TIMESTAMP,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )
    assert refusal.scope == expected_scope
    assert refusal.coverage_report == expected_report
    assert refusal.coverage_report.blocked


def test_a_refused_scope_creates_no_case_directory(tmp_path) -> None:
    """SEG-SREQ-046's second half: refusal precedes writing, so a store the
    caller holds but never gets to pass to ``persist`` never has its layout
    created at all."""
    orphan = requirement("ORPHAN-1")
    built = graph.build(Source([orphan], []))
    store = case.AffirmationStore(root=tmp_path / "case")
    with pytest.raises(proof.GenerationRefused):
        proof.assemble(
            built,
            {"ORPHAN-1"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    assert not store.root.exists()


@pytest.mark.parametrize(
    ("nodes_edges", "requested_ids", "expected_condition"),
    [
        pytest.param(
            (
                [requirement("SREQ-1"), implementation("pkg.fn")],
                [edge("Implements", "pkg.fn", "SREQ-1", state=LinkState.PENDING)],
            ),
            {"SREQ-1"},
            gates.Condition.UNREADY_EDGE,
            id="unready-edge",
        ),
        pytest.param(
            ([requirement("SREQ-1")], []),
            {"SREQ-1"},
            gates.Condition.COVERAGE_GAP,
            id="coverage-gap",
        ),
        pytest.param(
            ([requirement("SREQ-1")], []),
            set(),
            gates.Condition.EMPTY_DESIGN_SET,
            id="empty-design-set",
        ),
    ],
)
def test_each_blocking_condition_is_refused(nodes_edges, requested_ids, expected_condition) -> None:
    nodes, edges = nodes_edges
    built = graph.build(Source(nodes, edges))
    with pytest.raises(proof.GenerationRefused) as caught:
        proof.assemble(
            built,
            requested_ids,
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    conditions = {d.condition for d in caught.value.coverage_report.diagnostics}
    assert expected_condition in conditions


def test_an_unwaived_failing_outcome_is_refused() -> None:
    nodes, edges = ready_fixture()
    failed = [
        outcome("run-1/TS-1", result=TestResult.FAILED) if n.local_id == "run-1/TS-1" else n
        for n in nodes
    ]
    built = graph.build(Source(failed, edges))
    with pytest.raises(proof.GenerationRefused) as caught:
        proof.assemble(
            built,
            {"SREQ-1"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    conditions = {d.condition for d in caught.value.coverage_report.diagnostics}
    assert gates.Condition.UNWAIVED_FAILING_OUTCOME in conditions


def test_generation_refused_is_not_a_scope_error_value_error_or_store_error() -> None:
    orphan = requirement("ORPHAN-1")
    built = graph.build(Source([orphan], []))
    try:
        proof.assemble(
            built,
            {"ORPHAN-1"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    except proof.GenerationRefused as refusal:
        assert not isinstance(refusal, proof.ScopeError)
        assert not isinstance(refusal, ValueError)
        assert not isinstance(refusal, case.AffirmationStoreError)
    else:
        pytest.fail("expected GenerationRefused")


def test_a_scope_error_is_never_a_generation_refused() -> None:
    built = graph.build(Source([requirement("SREQ-1")], []))
    with pytest.raises(proof.ScopeError) as caught:
        proof.assemble(
            built,
            {"MISSING"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )
    assert not isinstance(caught.value, proof.GenerationRefused)


def test_check_readiness_agrees_with_collect_scope_and_package_gate() -> None:
    nodes, edges = ready_fixture()
    built = graph.build(Source(nodes, edges))

    scope, report = _package.check_readiness(
        built,
        {"SREQ-1"},
        snapshot_timestamp=TIMESTAMP,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )

    independently_collected = proof.collect_scope(built, {"SREQ-1"}, snapshot_timestamp=TIMESTAMP)
    independently_judged = gates.package_gate(
        independently_collected.subgraph,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )
    assert scope == independently_collected
    assert report == independently_judged


# ── Persisting a ready package ──────────────────────────────────────────────


def test_persisting_a_ready_package_writes_all_four_documents_under_its_snapshot(
    tmp_path,
) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    written = _package.persist(package, store)
    assert set(written) == {
        proof.DESIGN_CONSISTENCY_PROOF,
        proof.EXECUTION_COVERAGE_RECORD,
        proof.COVERAGE_REPORT,
        proof.EVIDENCE_MANIFEST,
    }
    for path in written.values():
        assert path.is_file()
        assert path.parent.name == package.scope.snapshot_id


def test_write_then_read_back_is_equal_for_every_document(tmp_path) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    _package.persist(package, store)
    for name in (
        proof.DESIGN_CONSISTENCY_PROOF,
        proof.EXECUTION_COVERAGE_RECORD,
        proof.COVERAGE_REPORT,
        proof.EVIDENCE_MANIFEST,
    ):
        assert store.read_proof_document(package.scope.snapshot_id, name) == package.documents[name]


def test_read_package_returns_all_four_documents_keyed_by_name(tmp_path) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    _package.persist(package, store)
    read_back = store.read_package(package.scope.snapshot_id)
    assert dict(read_back) == dict(package.documents)


def test_read_package_refuses_if_any_one_document_is_missing(tmp_path) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    written = _package.persist(package, store)
    written[proof.EVIDENCE_MANIFEST].unlink()
    with pytest.raises(case.AffirmationStoreError):
        store.read_package(package.scope.snapshot_id)


def test_reading_a_document_kind_absent_from_the_cases_own_schemas_is_refused(tmp_path) -> None:
    """A case whose own ``schema/`` directory predates this pass's four kinds
    refuses to read one, rather than pretending it can validate what it does
    not declare. Only the case's own copy is touched — the module's
    registration is real throughout, exactly the scenario a case initialized
    before this pass would actually be in."""
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    written = _package.persist(package, store)
    (store.root / "schema" / "evidence_manifest.schema.json").unlink()
    with pytest.raises(case.AffirmationStoreError, match="declares no schema"):
        store.read_proof_document(package.scope.snapshot_id, proof.EVIDENCE_MANIFEST)
    assert written[proof.EVIDENCE_MANIFEST].exists()  # the file itself was untouched


# ── The auditor's test: recompute the root with no graph in hand ───────────


def test_the_design_consistency_proof_recomputes_its_own_root_from_its_own_contents_alone(
    tmp_path,
) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    _package.persist(package, store)

    document = store.read_proof_document(package.scope.snapshot_id, proof.DESIGN_CONSISTENCY_PROOF)

    # No affirmatrix.graph.Graph anywhere below this line: only the document's
    # own fields, and the two general-purpose primitives every auditor has —
    # the commitment layer, and the standard library's own JSON encoder.
    metadata = json.dumps(
        {
            "scope": document["scope"],
            "revision": document["revision"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    node_hashes = (bytes.fromhex(entry["hash"]) for entry in document["nodeManifest"])
    edge_tuples = ((e["from"], e["to"], e["kind"]) for e in document["designEdges"])
    recomputed = commitment.design_root(metadata, node_hashes, edge_tuples)

    assert recomputed.hex() == document["root"]


def test_evidence_never_appears_in_the_design_consistency_proof(tmp_path) -> None:
    """The design consistency proof is the design subgraph alone, per the
    proof-package page — never an evidence node or edge."""
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    _package.persist(package, store)
    document = store.read_proof_document(package.scope.snapshot_id, proof.DESIGN_CONSISTENCY_PROOF)

    assert {entry["kind"] for entry in document["nodeManifest"]} <= {
        "Requirement",
        "TestSpecification",
        "Implementation",
    }
    assert {e["kind"] for e in document["designEdges"]} <= {"Refines", "Verifies", "Implements"}
    assert "run-1/TS-1" not in {entry["id"] for entry in document["nodeManifest"]}


# ── The execution coverage record ───────────────────────────────────────────


def test_the_execution_coverage_record_excludes_stale_outcomes(tmp_path) -> None:
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl = implementation("pkg.fn")
    fresh_run = outcome("run-1/TS-1")
    stale_run = outcome("run-2/TS-1", revision="a-different-revision")
    nodes = [sreq, spec, impl, fresh_run, stale_run]
    edges = [
        edge("Verifies", "TS-1", "SREQ-1"),
        edge("Implements", "pkg.fn", "SREQ-1"),
        edge("Confirms", "run-1/TS-1", "TS-1"),
        edge("Witnesses", "run-1/TS-1", "pkg.fn"),
        edge("Confirms", "run-2/TS-1", "TS-1"),
        edge("Witnesses", "run-2/TS-1", "pkg.fn"),
    ]
    package = assembled(nodes, edges, {"SREQ-1"})
    record = package.documents[proof.EXECUTION_COVERAGE_RECORD]
    ids = {entry["id"] for entry in record["outcomes"]}
    assert ids == {"run-1/TS-1"}


def test_the_execution_coverage_record_carries_confirms_and_result_and_revision(tmp_path) -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    (entry,) = package.documents[proof.EXECUTION_COVERAGE_RECORD]["outcomes"]
    assert entry["id"] == "run-1/TS-1"
    assert entry["result"] == "passed"
    assert entry["revision"] == CURRENT_REVISION
    assert entry["confirms"] == "TS-1"
    assert "waiver" not in entry


def test_an_outcome_confirming_two_in_scope_specifications_is_refused() -> None:
    """Nothing in the graph forbids an outcome confirming two specifications;
    the generator refuses the ambiguous case rather than silently keeping
    only one of them."""
    sreq = requirement("SREQ-1")
    spec_a, spec_b = specification("TS-1"), specification("TS-2")
    impl = implementation("pkg.fn")
    run = outcome("run-1/both")
    nodes = [sreq, spec_a, spec_b, impl, run]
    edges = [
        edge("Verifies", "TS-1", "SREQ-1"),
        edge("Verifies", "TS-2", "SREQ-1"),
        edge("Implements", "pkg.fn", "SREQ-1"),
        edge("Confirms", "run-1/both", "TS-1"),
        edge("Confirms", "run-1/both", "TS-2"),
        edge("Witnesses", "run-1/both", "pkg.fn"),
    ]
    built = graph.build(Source(nodes, edges))
    with pytest.raises(ValueError, match="run-1/both"):
        proof.assemble(
            built,
            {"SREQ-1"},
            snapshot_timestamp=TIMESTAMP,
            evaluation_date=EVALUATION_DATE,
            current_revision=CURRENT_REVISION,
        )


def test_an_excused_failing_outcome_carries_its_waiver_id_and_a_copy_of_its_expiry() -> None:
    sreq, spec = requirement("SREQ-1"), specification("TS-1")
    impl = implementation("pkg.fn")
    run = outcome("run-1/TS-1", result=TestResult.FAILED)
    excuse = waiver("WVR-1", expiry=date(2099, 3, 4))
    nodes = [sreq, spec, impl, run, excuse]
    edges = [
        edge("Verifies", "TS-1", "SREQ-1"),
        edge("Implements", "pkg.fn", "SREQ-1"),
        edge("Confirms", "run-1/TS-1", "TS-1"),
        edge("Witnesses", "run-1/TS-1", "pkg.fn"),
        edge("Excuses", "WVR-1", "run-1/TS-1", state=LinkState.PENDING),
    ]
    package = assembled(nodes, edges, {"SREQ-1"})
    assert not package.coverage_report.blocked
    (entry,) = package.documents[proof.EXECUTION_COVERAGE_RECORD]["outcomes"]
    assert entry["waiver"] == {"id": "WVR-1", "expiry": "2099-03-04"}


# ── The coverage report document ────────────────────────────────────────────


def test_the_coverage_report_document_matches_the_typed_report() -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    document = package.documents[proof.COVERAGE_REPORT]
    assert document["blocked"] is False
    assert document["designSetEmpty"] is False
    assert document["diagnostics"] == []
    assert document["coverageGaps"] == []
    assert document["staleOutcomes"] == []
    assert document["skippedOutcomes"] == []


def _skipped_fixture():
    nodes, edges = ready_fixture()
    nodes.append(outcome("run-2/TS-1", result=TestResult.SKIPPED))
    edges += [
        edge("Confirms", "run-2/TS-1", "TS-1"),
        edge("Witnesses", "run-2/TS-1", "pkg.fn"),
    ]
    return nodes, edges


def test_a_skipped_outcome_is_named_in_the_coverage_report_document_and_does_not_refuse() -> None:
    nodes, edges = _skipped_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    document = package.documents[proof.COVERAGE_REPORT]
    assert document["skippedOutcomes"] == ["run-2/TS-1"]
    assert document["blocked"] is False
    assert [(d["severity"], d["condition"], d["subject"]) for d in document["diagnostics"]] == [
        ("info", str(gates.Condition.SKIPPED_OUTCOME), "run-2/TS-1")
    ]


def test_a_skipped_outcome_stays_in_the_execution_coverage_record_without_a_waiver_entry() -> None:
    nodes, edges = _skipped_fixture()
    nodes.append(waiver("WVR-1"))
    edges.append(edge("Excuses", "WVR-1", "run-2/TS-1", state=LinkState.PENDING))
    package = assembled(nodes, edges, {"SREQ-1"})
    entries = {e["id"]: e for e in package.documents[proof.EXECUTION_COVERAGE_RECORD]["outcomes"]}
    assert entries["run-2/TS-1"]["result"] == "skipped"
    assert "waiver" not in entries["run-2/TS-1"]


def test_a_package_holding_a_skipped_outcome_persists_and_reads_back(tmp_path) -> None:
    nodes, edges = _skipped_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    _package.persist(package, store)
    assert dict(store.read_package(package.scope.snapshot_id)) == dict(package.documents)


def test_a_coverage_report_sealed_before_the_skipped_field_existed_still_validates(
    tmp_path,
) -> None:
    """The array is not required: an older package carries none, and a reader
    tells an absent array (not judged for skips) from an empty one."""
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    document = package.documents[proof.COVERAGE_REPORT]
    older = {key: value for key, value in document.items() if key != "skippedOutcomes"}
    store = case.AffirmationStore(root=tmp_path / "case")
    store.write_proof_document(package.scope.snapshot_id, proof.COVERAGE_REPORT, older)
    read_back = store.read_proof_document(package.scope.snapshot_id, proof.COVERAGE_REPORT)
    assert "skippedOutcomes" not in read_back


# ── The evidence manifest ───────────────────────────────────────────────────


def test_the_evidence_manifest_states_requested_and_member_scope_and_totality() -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    manifest = package.documents[proof.EVIDENCE_MANIFEST]
    assert manifest["requestedScope"] == ["SREQ-1"]
    assert set(manifest["memberScope"]) == {"SREQ-1", "TS-1", "pkg.fn", "run-1/TS-1"}
    assert manifest["total"] is True
    assert manifest["revision"] == CURRENT_REVISION


def test_the_evidence_manifest_references_the_sibling_documents_by_relative_name() -> None:
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    manifest = package.documents[proof.EVIDENCE_MANIFEST]
    assert manifest["designConsistencyProof"] == "design_consistency_proof.jsonld"
    assert manifest["executionCoverageRecord"] == "execution_coverage_record.jsonld"
    assert manifest["coverageReport"] == "coverage_report.jsonld"
    assert "/" not in manifest["designConsistencyProof"]


def test_the_manifests_sibling_references_match_what_persist_actually_named(tmp_path) -> None:
    """The literal filenames above can never drift from what the store
    actually writes: each reference is checked against the basename of the
    path ``persist`` returned for that same document."""
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    store = case.AffirmationStore(root=tmp_path / "case")
    written = _package.persist(package, store)
    manifest = package.documents[proof.EVIDENCE_MANIFEST]
    assert manifest["designConsistencyProof"] == written[proof.DESIGN_CONSISTENCY_PROOF].name
    assert manifest["executionCoverageRecord"] == written[proof.EXECUTION_COVERAGE_RECORD].name
    assert manifest["coverageReport"] == written[proof.COVERAGE_REPORT].name


# ── Canonical metadata and the two-hashes-two-purposes distinction ─────────


def test_canonical_metadata_is_stable_for_the_same_inputs() -> None:
    first = _package._canonical_metadata(requested_ids={"SREQ-1"}, revision=CURRENT_REVISION)
    second = _package._canonical_metadata(requested_ids={"SREQ-1"}, revision=CURRENT_REVISION)
    assert first == second


def test_canonical_metadata_differs_when_the_current_revision_differs() -> None:
    first = _package._canonical_metadata(requested_ids={"SREQ-1"}, revision="r1")
    second = _package._canonical_metadata(requested_ids={"SREQ-1"}, revision="r2")
    assert first != second


def test_canonical_metadata_differs_when_the_requested_scope_differs() -> None:
    first = _package._canonical_metadata(requested_ids={"SREQ-1"}, revision=CURRENT_REVISION)
    second = _package._canonical_metadata(
        requested_ids={"SREQ-1", "SREQ-2"}, revision=CURRENT_REVISION
    )
    assert first != second


def test_the_canonical_metadata_names_the_scope_and_the_revision_alone() -> None:
    metadata = _package._canonical_metadata(requested_ids={"SREQ-2", "SREQ-1"}, revision="r1")
    assert metadata == b'{"revision":"r1","scope":["SREQ-1","SREQ-2"]}'


def _assembled_at(nodes, edges, timestamp: datetime) -> _package.Package:
    return proof.assemble(
        graph.build(Source(nodes, edges)),
        {"SREQ-1"},
        snapshot_timestamp=timestamp,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )


def _design_root(package: _package.Package) -> str:
    return package.documents[proof.DESIGN_CONSISTENCY_PROOF]["root"]


def test_two_packages_over_one_design_at_different_instants_carry_the_same_root() -> None:
    nodes, edges = ready_fixture()
    earlier = _assembled_at(nodes, edges, TIMESTAMP)
    later = _assembled_at(nodes, edges, datetime(2026, 6, 2, 9, 30, 0, tzinfo=UTC))

    assert _design_root(earlier) == _design_root(later)
    assert earlier.scope.snapshot_id != later.scope.snapshot_id


def test_changing_an_in_scope_outcome_never_changes_the_package_root() -> None:
    nodes, edges = ready_fixture()
    rerun = [
        outcome("run-1/TS-1", seed="a second run") if n.kind == "TestOutcome" else n for n in nodes
    ]

    before = _assembled_at(nodes, edges, TIMESTAMP)
    after = _assembled_at(rerun, edges, TIMESTAMP)

    assert _design_root(before) == _design_root(after)
    assert before.scope.snapshot_id != after.scope.snapshot_id


def test_changing_a_design_node_changes_the_package_root() -> None:
    nodes, edges = ready_fixture()
    edited = [
        implementation("pkg.fn", seed="edited") if n.kind == "Implementation" else n for n in nodes
    ]

    before = _assembled_at(nodes, edges, TIMESTAMP)
    after = _assembled_at(edited, edges, TIMESTAMP)

    assert _design_root(before) != _design_root(after)


def test_the_snapshot_id_fingerprint_and_the_package_root_are_different_hashes() -> None:
    """Two distinct calls to design_root, over overlapping but different
    inputs — the fingerprint folds the whole induced subgraph with an empty
    metadata (B16), the package root folds the design subset alone with real
    metadata (B17). Recomputing the fingerprint the same way collect_scope
    does and comparing it to the persisted root pins that they never agree
    by construction."""
    nodes, edges = ready_fixture()
    package = assembled(nodes, edges, {"SREQ-1"})
    subgraph = package.scope.subgraph
    members = [subgraph.node(local_id) for local_id in subgraph.node_ids()]
    node_hashes = (commitment.node_hash(node.kind, node.content_hashes) for node in members)
    edge_tuples = ((e.from_id, e.to_id, e.kind) for e in subgraph.edges)
    fingerprint = commitment.design_root(b"", node_hashes, edge_tuples).hex()
    root = package.documents[proof.DESIGN_CONSISTENCY_PROOF]["root"]
    assert fingerprint != root


# ── Generation changes nothing ──────────────────────────────────────────────


def test_assembling_leaves_the_input_graph_unchanged() -> None:
    nodes, edges = ready_fixture()
    built = graph.build(Source(nodes, edges))
    edges_before, node_ids_before = built.edges, built.node_ids()

    proof.assemble(
        built,
        {"SREQ-1"},
        snapshot_timestamp=TIMESTAMP,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
    )

    assert built.edges == edges_before
    assert built.node_ids() == node_ids_before


def test_generation_leaves_the_stores_node_edge_and_event_streams_unchanged(tmp_path) -> None:
    nodes, edges = ready_fixture()
    store = case.AffirmationStore(root=tmp_path / "case")
    store.write_nodes([n for n in nodes if n.kind != "TestOutcome"])
    store.write_edges([e for e in edges if e.kind in {"Verifies", "Implements"}])

    nodes_before = list(store.nodes())
    edges_before = list(store.edges())
    events_before = list(store.review_events())

    package = assembled(nodes, edges, {"SREQ-1"})
    _package.persist(package, store)

    assert list(store.nodes()) == nodes_before
    assert list(store.edges()) == edges_before
    assert list(store.review_events()) == events_before


# ── Markers, sanity ──────────────────────────────────────────────────────────


def test_assemble_and_persist_are_pure_and_repeatable() -> None:
    nodes, edges = ready_fixture()
    first = assembled(nodes, edges, {"SREQ-1"})
    second = assembled(nodes, edges, {"SREQ-1"})
    assert first.documents == second.documents


# ── The run bundles a package records (SEG-SREQ-226) ────────────────────────


def _manifest(nodes, edges, bundles) -> dict:
    built = graph.build(Source(nodes, edges))
    package = proof.assemble(
        built,
        {"SREQ-1"},
        snapshot_timestamp=TIMESTAMP,
        evaluation_date=EVALUATION_DATE,
        current_revision=CURRENT_REVISION,
        evidence_bundles=bundles,
    )
    return package.documents[proof.EVIDENCE_MANIFEST]


def test_the_manifest_lists_the_digests_of_the_bundles_of_outcomes_in_scope() -> None:
    nodes, edges = ready_fixture()
    other = outcome("run-9/TS-9")
    manifest = _manifest(
        [*nodes, other],
        edges,
        {"run-1/TS-1": "sha256:" + "a" * 64, "run-9/TS-9": "sha256:" + "b" * 64},
    )
    assert manifest["runBundles"] == ["sha256:" + "a" * 64]


def test_the_manifest_lists_each_digest_once_and_sorted() -> None:
    nodes, edges = ready_fixture()
    second = outcome("run-2/TS-1")
    edges = [*edges, edge("Confirms", "run-2/TS-1", "TS-1")]
    manifest = _manifest(
        [*nodes, second],
        edges,
        {"run-1/TS-1": "sha256:" + "b" * 64, "run-2/TS-1": "sha256:" + "b" * 64},
    )
    assert manifest["runBundles"] == ["sha256:" + "b" * 64]


def test_the_manifest_lists_no_digest_when_no_bundle_is_given() -> None:
    nodes, edges = ready_fixture()
    assert _manifest(nodes, edges, None)["runBundles"] == []
