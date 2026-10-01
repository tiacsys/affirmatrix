"""Verification suite for the run bundles a package records and the results that must not move.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker.

Two groups of tests live here. The first shows what a package says about the
run bundles it used. The second guards two risks of reading test evidence
through bundles: a verdict that moves, and a design root that moves. Its
tests compare the tool's results over the frozen evidence with the golden
results in ``tests/fixtures/golden_evidence/``. The goldens were made by the
code that read the same evidence through three loose records, before bundles
existed; their README gives the commands.

Each golden arm is rebuilt in ``tmp_path``: a configuration over the clean
bundle (``one_run``) or over the clean bundle and a second bundle recorded at
another revision (``two_runs``), a case in which the strong edges are
affirmed, and the scope ``SD-TOP-001`` and ``SD-TOP-003`` with the revision of
the clean bundle. The comparisons are exact for the documents that hold the
design or the verdict and structural for the rest (see the golden README).
The new names are read inside the test bodies only.
"""

from __future__ import annotations

import json
from pathlib import Path

from affirmatrix import config, drift, graph, satisfaction
from affirmatrix.case import AffirmationStore
from affirmatrix.sources import composed

from .evidence_support import (
    GOLDEN,
    REVISION,
    Session,
    affirm_design,
    copy_bundle,
    generate,
    load_json,
    recipe_digest,
    run,
    scope_args,
    second_bundle,
    session,
)

ARMS = ("one_run", "two_runs")


def _arm(tmp_path: Path, capsys, arm: str) -> Session:
    """The golden arm: its bundles, its configuration, a case with every strong edge affirmed."""
    bundles = [copy_bundle(tmp_path, "first")]
    if arm == "two_runs":
        bundles.append(second_bundle(tmp_path, "second"))
    opened = session(tmp_path, bundles, capsys)
    affirm_design(opened, capsys)
    return opened


def _golden_package(arm: str) -> Path:
    (package,) = sorted((GOLDEN / arm / "proofs").iterdir())
    return package


def _third_bundle(tmp_path: Path, name: str = "third") -> Path:
    """The clean bundle with the results of one test function only, which lies outside the scope."""
    bundle = copy_bundle(tmp_path, name)
    (bundle / "run.name").write_text("twister-run-third\n", encoding="utf-8")
    artifact = bundle / "twister.json"
    document = json.loads(artifact.read_text(encoding="utf-8"))
    for suite in document["testsuites"]:
        suite["testcases"] = [
            case for case in suite["testcases"] if case["identifier"].endswith(".write_reseals")
        ]
    artifact.write_text(json.dumps(document), encoding="utf-8")
    return bundle


def test_a_package_records_the_digest_of_every_bundle_that_supplied_an_outcome_in_scope(
    tmp_path: Path, capsys
) -> None:
    """A package's manifest holds the digest of every run bundle that supplied an in-scope outcome.

    Three bundles are configured. The first is recorded at the revision given,
    and supplies outcomes in the scope. The second is recorded at another
    revision: its outcomes in the scope are set aside by the gate, and the
    package still records it. The third is recorded at the revision given, and
    holds results of one test function that lies outside the scope: it is not
    recorded. The evidence manifest of the generated package holds the digest
    of the first and of the second, and not the digest of the third. With only
    the first bundle configured, the manifest holds only that digest.

    :verifies: SEG-SREQ-226
    :test-id: SEG-TS-092
    """
    first = copy_bundle(tmp_path, "first")
    second = second_bundle(tmp_path, "second")
    third = _third_bundle(tmp_path)
    opened = session(tmp_path, [first, second, third], capsys)
    affirm_design(opened, capsys)

    package = generate(opened, capsys, tmp_path / "out")

    manifest = (package / "evidence_manifest.jsonld").read_text(encoding="utf-8")
    assert recipe_digest(first) in manifest
    assert recipe_digest(second) in manifest
    assert recipe_digest(third) not in manifest

    alone = tmp_path / "alone"
    single = _arm(alone, capsys, "one_run")
    package = generate(single, capsys, alone / "out")
    manifest = (package / "evidence_manifest.jsonld").read_text(encoding="utf-8")
    assert recipe_digest(alone / "bundles" / "first") in manifest
    assert recipe_digest(second) not in manifest


def test_the_design_root_does_not_move_with_the_evidence(tmp_path: Path, capsys) -> None:
    """A package's design root and design proof are those of the golden, with one run or two.

    The golden design root was made before bundles existed. The package
    generated over the clean bundle has a design consistency proof that is
    byte for byte the golden's. The package generated over the clean bundle and
    a second bundle at another revision has a design consistency proof that is
    byte for byte the golden's for two runs. In both the design root is the
    root written in the golden. The scope of both packages holds test outcomes,
    and the root is the same with 24 or 48 of them in the scope.

    :verifies: SEG-SREQ-133
    :test-id: SEG-TS-093
    """
    root = (GOLDEN / "design_root.txt").read_text(encoding="utf-8").strip()
    for arm in ARMS:
        work = tmp_path / arm
        opened = _arm(work, capsys, arm)

        package = generate(opened, capsys, work / "out")

        golden = _golden_package(arm)
        proof = package / "design_consistency_proof.jsonld"
        assert proof.read_bytes() == (golden / "design_consistency_proof.jsonld").read_bytes()
        assert load_json(proof)["root"] == root
        assert package.name == golden.name


def test_a_stale_run_changes_no_coverage_finding_of_the_gate(tmp_path: Path, capsys) -> None:
    """The gate leaves the outcomes of a run at another revision out of every coverage finding.

    The gate's report over the clean bundle equals the golden report. The
    report over the clean bundle and a second bundle at another revision
    equals the first report in every part except the list of stale outcomes and
    the diagnostics that name them: the blocked flag, the coverage gaps, the
    unready edges, the skipped, excused, unwaived and discarded outcomes and
    the empty-design flag are the same. The gate does not block.

    :verifies: SEG-SREQ-063
    :test-id: SEG-TS-094
    """
    golden = load_json(GOLDEN / "one_run" / "gate_report.json")
    reports = {}
    for arm in ARMS:
        work = tmp_path / arm
        opened = _arm(work, capsys, arm)
        status, out = run(
            capsys,
            "proof",
            "check",
            "--json",
            *opened.args(),
            *scope_args(),
            "--revision",
            REVISION,
        )
        assert status == 0
        reports[arm] = json.loads(out)

    assert reports["one_run"] == golden
    moved = {"staleOutcomes", "diagnostics"}
    assert {k: v for k, v in reports["two_runs"].items() if k not in moved} == {
        k: v for k, v in golden.items() if k not in moved
    }
    assert reports["two_runs"]["blocked"] is False


def test_a_stale_outcome_is_reported_as_information(tmp_path: Path, capsys) -> None:
    """The gate reports each outcome of a run at another revision as an informational finding.

    The gate's report over the clean bundle and a second bundle at another
    revision equals the golden report for two runs. It lists 24 outcomes of the
    second run as stale. Each has one finding of severity information, and no
    outcome of the first run is listed as stale.

    :verifies: SEG-SREQ-067
    :test-id: SEG-TS-095
    """
    opened = _arm(tmp_path, capsys, "two_runs")

    status, out = run(
        capsys, "proof", "check", "--json", *opened.args(), *scope_args(), "--revision", REVISION
    )

    assert status == 0
    report = json.loads(out)
    assert report == load_json(GOLDEN / "two_runs" / "gate_report.json")
    assert len(report["staleOutcomes"]) == 24
    stale = [d for d in report["diagnostics"] if d["subject"] in report["staleOutcomes"]]
    assert len(stale) == 24
    assert {d["severity"] for d in stale} == {"info"}


def test_leaf_verdicts_over_bundles_equal_the_golden_verdicts(tmp_path: Path, capsys) -> None:
    """Every requirement's satisfaction over bundle evidence equals the golden verdict.

    The producer the configuration describes supplies the outcomes of the
    bundles. The graph built from the case and that producer gives the
    satisfaction evaluator the same verdicts as the golden for each of the 29
    requirements, 18 of them satisfied, with the same outcomes set aside as
    incomplete. The verdicts are the same with a second run at another
    revision.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-096
    """
    for arm in ARMS:
        work = tmp_path / arm
        opened = _arm(work, capsys, arm)
        loaded = config.load(opened.config, case=opened.case)
        current = composed.from_config(loaded)
        built = graph.build(
            drift.derive(recorded=AffirmationStore(root=loaded.case), current=current)
        )

        verdict = satisfaction.evaluate(built)

        document = {
            "satisfaction": dict(sorted(verdict.satisfaction.items())),
            "discardedOutcomes": sorted(verdict.discarded_outcomes),
        }
        assert document == load_json(GOLDEN / arm / "leaf_verdicts.json")
        assert sum(document["satisfaction"].values()) == 18


def test_a_package_gains_one_field_and_changes_nothing_else(tmp_path: Path, capsys) -> None:
    """The documents of a package equal the golden's, and the manifest gains one field.

    For one run and for two runs, the coverage report and the execution
    coverage record are byte for byte the golden's, and the package has the
    golden's snapshot identifier. The evidence manifest has every field of the
    golden's manifest with the same value, and exactly one more field. That
    field holds the digest of each bundle used: one for one run, two for two
    runs.

    :verifies: SEG-SREQ-226
    :test-id: SEG-TS-097
    """
    for arm in ARMS:
        work = tmp_path / arm
        opened = _arm(work, capsys, arm)

        package = generate(opened, capsys, work / "out")

        golden = _golden_package(arm)
        assert package.name == golden.name
        for name in ("coverage_report", "execution_coverage_record"):
            assert (package / f"{name}.jsonld").read_bytes() == (
                golden / f"{name}.jsonld"
            ).read_bytes()
        new, old = (
            load_json(package / "evidence_manifest.jsonld"),
            load_json(golden / "evidence_manifest.jsonld"),
        )
        assert {key: new[key] for key in old} == old
        (extra,) = set(new) - set(old)
        used = [work / "bundles" / "first"]
        if arm == "two_runs":
            used.append(work / "bundles" / "second")
        text = json.dumps(new[extra])
        assert all(recipe_digest(bundle) in text for bundle in used)
