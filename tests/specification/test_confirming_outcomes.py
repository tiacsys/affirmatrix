"""Verification suite for the outcomes that count as confirming evidence.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. An
outcome counts only when it has a Confirms edge to a test specification and a
Witnesses edge to an implementation. An outcome that lacks one of the two is set
aside, and the gate reports it as information.

The first two tests build a small graph in memory from literal records. The
last two run ``proof check`` over the frozen evidence fixture and one run
bundle, once with a producer that reads no implementation export, and once with
the export. Read in the second way, the Witnesses edges come from the export, so
a producer without it supplies no Witnesses edge at all. The tests read the
verdict and the findings by subject and condition, never the text of a detail.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import yaml

from affirmatrix import diagnostics, gates, graph, records, satisfaction
from affirmatrix.records import LinkState, TestResult

from .evidence_support import (
    REVISION,
    copy_bundle,
    run,
    scope_args,
    session,
)

LEAF = "SREQ-1"
BOTH = "run-1/TS-1"
CONFIRM_ONLY = "run-2/TS-1"
WITNESS_ONLY = "run-3/TS-1"
AFFIRMED = hashlib.sha256(b"an edge hash, not recomputed here").digest()
DISCARDED = gates.Condition.DISCARDED_OUTCOME


class _Source:
    def __init__(self, nodes: list[records.NodeRecord], edges: list[records.EdgeRecord]) -> None:
        self._nodes, self._edges = nodes, edges

    def nodes(self):
        return iter(self._nodes)

    def edges(self):
        return iter(self._edges)


def _node(local_id: str, kind: str, names: tuple[str, ...], **fields) -> records.NodeRecord:
    anchors = {
        name: records.ContentAnchor(
            digest=hashlib.sha256(name.encode("utf-8")).digest(),
            repository="the-source-repo",
            path="pkg/module.py",
            locator="file",
        )
        for name in names
    }
    return records.NodeRecord(local_id, kind, anchors, **fields)


def _edge(kind: str, from_id: str, to_id: str) -> records.EdgeRecord:
    return records.EdgeRecord(from_id, to_id, kind, LinkState.ACTIVE, AFFIRMED)


def _graph(outcomes: dict[str, tuple[bool, bool]]) -> graph.Graph:
    """One covered leaf, and one passed outcome for each name given.

    Each value says whether the outcome has a Confirms edge and whether it has a
    Witnesses edge.
    """
    nodes = [
        _node(LEAF, "Requirement", ("contentHash",)),
        _node("TS-1", "TestSpecification", ("specHash", "implHash")),
        _node("pkg.fn", "Implementation", ("apiHash", "bodyHash")),
    ]
    edges = [_edge("Verifies", "TS-1", LEAF), _edge("Implements", "pkg.fn", LEAF)]
    for name, (confirms, witnesses) in outcomes.items():
        nodes.append(
            _node(name, "TestOutcome", ("contentHash",), result=TestResult.PASSED, revision="r1")
        )
        if confirms:
            edges.append(_edge("Confirms", name, "TS-1"))
        if witnesses:
            edges.append(_edge("Witnesses", name, "pkg.fn"))
    return graph.build(_Source(nodes, edges))


def _gate(built: graph.Graph) -> gates.CoverageReport:
    return gates.package_gate(built, evaluation_date=date(2026, 6, 1), current_revision="r1")


def test_an_outcome_counts_only_with_both_a_confirms_and_a_witnesses_edge() -> None:
    """An outcome is a confirming outcome only when it has both a Confirms and a Witnesses edge.

    One leaf has an active verifies edge and an active implements edge. Three
    outcomes passed. The first has a Confirms edge to the test specification and
    a Witnesses edge to the implementation. The second has a Confirms edge and
    no Witnesses edge. The third has a Witnesses edge and no Confirms edge. The
    satisfaction evaluator sets aside the second and the third, and not the
    first. The leaf is satisfied. With only the second and the third outcome in
    the graph, the leaf is not satisfied, and both outcomes are still set aside.
    With only the second outcome, the leaf is not satisfied either.

    :verifies: SEG-SREQ-355
    :test-id: SEG-TS-362
    """
    everything = {BOTH: (True, True), CONFIRM_ONLY: (True, False), WITNESS_ONLY: (False, True)}
    built = _graph(everything)
    verdict = satisfaction.evaluate(built)
    assert verdict.discarded_outcomes == {CONFIRM_ONLY, WITNESS_ONLY}
    assert satisfaction.leaf_satisfied(built, LEAF)

    incomplete = {name: ends for name, ends in everything.items() if name != BOTH}
    only_incomplete = _graph(incomplete)
    assert satisfaction.evaluate(only_incomplete).discarded_outcomes == {
        CONFIRM_ONLY,
        WITNESS_ONLY,
    }
    assert not satisfaction.leaf_satisfied(only_incomplete, LEAF)

    only_confirms = _graph({CONFIRM_ONLY: (True, False)})
    assert not satisfaction.leaf_satisfied(only_confirms, LEAF)


def test_the_gate_reports_each_discarded_outcome_as_information() -> None:
    """The gate reports each outcome that the satisfaction evaluator sets aside as information.

    A graph holds one leaf and three passed outcomes: one with a Confirms edge
    and a Witnesses edge, one with a Confirms edge only, and one with a
    Witnesses edge only. The package gate reports exactly one finding of the
    condition for a discarded outcome for each of the second and the third
    outcome, with the outcome as its subject and the severity information. It
    reports no such finding for the first outcome. The set of discarded
    outcomes in the report holds the second and the third outcome. The report
    is not blocked, because the first outcome covers the leaf.

    :verifies: SEG-SREQ-356
    :test-id: SEG-TS-363
    """
    report = _gate(
        _graph({BOTH: (True, True), CONFIRM_ONLY: (True, False), WITNESS_ONLY: (False, True)})
    )

    assert report.discarded_outcomes == {CONFIRM_ONLY, WITNESS_ONLY}
    found = [(d.subject, d.severity) for d in report.diagnostics if d.condition == DISCARDED]
    assert sorted(found) == [
        (CONFIRM_ONLY, diagnostics.Severity.INFO),
        (WITNESS_ONLY, diagnostics.Severity.INFO),
    ]
    assert not report.blocked


def _gate_over_bundle(tmp_path: Path, capsys, *, implementations: bool) -> dict:
    """The ``proof check`` report over the clean bundle, as the producer is configured.

    The design edges that the producer supplies are affirmed, so no finding for a
    pending edge hides the result. With ``implementations`` false the producer block names no
    implementation export, and the case holds no Implements edge.
    """
    opened = session(tmp_path, [copy_bundle(tmp_path, "first")], capsys)
    if not implementations:
        document = yaml.safe_load(opened.config.read_text(encoding="utf-8"))
        del document["producer"]["implementations"]
        opened.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert run(capsys, "case", "sync", *opened.args())[0] == 0
    kinds = ("Refines", "Verifies", "Implements") if implementations else ("Refines", "Verifies")
    for kind in kinds:
        affirmed, _ = run(
            capsys,
            "edge", "affirm", *opened.args(), "--kind", kind,
            "--role", "fixture-reviewer", "--reason", "synthetic", "--revision", REVISION,
        )  # fmt: skip
        assert affirmed == 0
    status, out = run(
        capsys,
        "proof", "check", "--json", *opened.evidence_args(), *scope_args(), "--revision", REVISION,
    )  # fmt: skip
    assert status in (0, 1)
    return json.loads(out)


def test_without_an_implementation_export_every_outcome_is_discarded_and_reported(
    tmp_path: Path, capsys
) -> None:
    """With no implementation export, no outcome confirms, and each is reported once as information.

    The producer reads the frozen evidence fixture and one run bundle, and its
    block names no implementation export, so no outcome has a Witnesses edge.
    Running proof check for the golden scope with the strong edges affirmed
    reports the 24 outcomes of the scope as discarded. Each of them has one
    finding of the condition for a discarded outcome, with severity information
    and the outcome as its subject. A leaf of the scope, SD-REQ-001, is a
    coverage gap and so is not satisfied. The same check over a producer that
    reads the export, in the next test, discards none.

    :verifies: SEG-SREQ-355
    :verifies: SEG-SREQ-356
    :test-id: SEG-TS-364
    """
    report = _gate_over_bundle(tmp_path, capsys, implementations=False)

    discarded = set(report["discardedOutcomes"])
    assert len(discarded) == 24
    findings = [d for d in report["diagnostics"] if d["condition"] == DISCARDED.value]
    assert sorted(d["subject"] for d in findings) == sorted(discarded)
    assert {d["severity"] for d in findings} == {"info"}
    assert "SD-REQ-001" in report["coverageGaps"]


def test_with_an_implementation_export_no_outcome_is_discarded(tmp_path: Path, capsys) -> None:
    """With the implementation export, every outcome of the scope confirms and none is discarded.

    The producer reads the frozen evidence fixture, one run bundle and the
    implementation export, so each outcome has a Witnesses edge to the
    implementations of what its test verifies. Running proof check for the
    golden scope with the strong edges affirmed lists no discarded outcome and
    holds no finding of the condition for a discarded outcome.

    :verifies: SEG-SREQ-355
    :verifies: SEG-SREQ-356
    :test-id: SEG-TS-365
    """
    report = _gate_over_bundle(tmp_path, capsys, implementations=True)

    assert report["discardedOutcomes"] == []
    assert [d for d in report["diagnostics"] if d["condition"] == DISCARDED.value] == []
