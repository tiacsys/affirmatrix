"""Verification suite for the checks of the proof verifier that rebuild the evidence.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests call the library as ``affirmatrix.proof.verify(package, config=...,
bundles=...)``. The configuration names the frozen exports and no run bundle;
the bundles are copies of the clean bundle in ``tmp_path``.

A generated package lists the digest of each bundle that supplied an outcome
in its scope. ``seal(second=True)`` makes a package that lists two digests: the
clean bundle and a second bundle recorded at another revision. Tampers change
one thing in a private copy of a package. Where a tamper changes the design,
the root is sealed again with the recipe of the tutorial, so that only the
design guard sees the change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .evidence_support import copy_bundle, recipe_digest
from .proof_verify_support import (
    copy_package,
    edit,
    flip_digit,
    golden_copy,
    library_verify,
    missing_edge,
    read,
    reseal,
    seal,
    statuses,
)

OPENED_ARMS = ("bundle-digests", "design-guard", "rebuilt-evidence", "snapshot-id")


def _check(report, name: str):
    return {check.name: check for check in report.checks}[name]


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-242: the proof verifier does not exist yet")
def test_a_bundle_whose_digest_the_package_does_not_list_is_a_mismatch(
    tmp_path: Path, capsys
) -> None:
    """The verifier fails the bundle digests check for a bundle the package does not list.

    A package lists the digest of the clean bundle. Given that bundle, the
    check named bundle-digests is passed. Given a copy of the clean bundle
    with one file more, the check is failed and its detail
    holds the digest of the given copy. A package that lists no digest, the
    golden package, gives the same result for the clean bundle.

    :verifies: SEG-SREQ-242
    :test-id: SEG-TS-127
    """
    sealed = seal(tmp_path, capsys)
    right = sealed.opened.bundles[0]
    changed = copy_bundle(tmp_path, "changed")
    (changed / "notes.txt").write_text("a new file\n", encoding="utf-8")
    assert recipe_digest(changed) != recipe_digest(right)

    control = library_verify(sealed.opened, sealed.package, bundles=[right])
    mismatch = library_verify(sealed.opened, sealed.package, bundles=[changed])
    legacy = library_verify(sealed.opened, golden_copy(tmp_path), bundles=[right])

    assert statuses(control)["bundle-digests"] == "passed"
    assert statuses(mismatch)["bundle-digests"] == "failed"
    assert recipe_digest(changed) in _check(mismatch, "bundle-digests").detail
    assert statuses(legacy)["bundle-digests"] == "failed"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-243: the proof verifier does not exist yet")
def test_a_listed_bundle_that_is_not_given_leaves_the_evidence_unjudged(
    tmp_path: Path, capsys
) -> None:
    """The verifier reports the evidence as not judged when a listed bundle is not given.

    A package lists the digests of two bundles. Given both, the checks named
    bundle-digests, rebuilt-evidence and snapshot-id are passed. Given only
    the first bundle, no check fails. The check named bundle-digests is not
    judged, its detail holds the digest of the bundle that is missing, and
    the checks named rebuilt-evidence and snapshot-id are not judged.

    :verifies: SEG-SREQ-243
    :test-id: SEG-TS-128
    """
    sealed = seal(tmp_path, capsys, second=True)
    first, second = sealed.opened.bundles
    assert len(read(sealed.package, "evidence_manifest")["runBundles"]) == 2

    both = statuses(library_verify(sealed.opened, sealed.package, bundles=[first, second]))
    one = library_verify(sealed.opened, sealed.package, bundles=[first])

    assert {both[name] for name in OPENED_ARMS} == {"passed"}
    found = statuses(one)
    assert "failed" not in found.values()
    for name in ("bundle-digests", "rebuilt-evidence", "snapshot-id"):
        assert found[name] == "not judged", name
    assert recipe_digest(second) in _check(one, "bundle-digests").detail


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-244: the proof verifier does not exist yet")
def test_a_design_node_the_readers_do_not_supply_leaves_the_evidence_unjudged(
    tmp_path: Path, capsys
) -> None:
    """The verifier reports the evidence as not judged when a design node hash differs.

    Given the clean bundle and the readers of the configuration, the check
    named design-guard is passed for a generated package. In a private copy
    the node hash of one requirement is changed by one digit in the design
    consistency proof, and the root is sealed again over the changed hash. The
    root and identity checks of the copy are passed. The design-guard check is
    not judged, its detail names the requirement, and the checks named
    rebuilt-evidence and snapshot-id are not judged. No check fails.

    :verifies: SEG-SREQ-244
    :test-id: SEG-TS-129
    """
    sealed = seal(tmp_path, capsys)
    bundles = list(sealed.opened.bundles)
    assert (
        statuses(library_verify(sealed.opened, sealed.package, bundles=bundles))["design-guard"]
        == "passed"
    )
    copy = copy_package(sealed.package, tmp_path, "node")

    def digit(body: dict) -> None:
        node = next(n for n in body["nodeManifest"] if n["id"] == "SD-REQ-001")
        node["hash"] = flip_digit(node["hash"])

    edit(copy, "design_consistency_proof", digit)
    reseal(copy)

    report = library_verify(sealed.opened, copy, bundles=bundles)

    found = statuses(report)
    assert found["root"] == "passed"
    assert found["identity"] == "passed"
    assert found["design-guard"] == "not judged"
    assert "SD-REQ-001" in _check(report, "design-guard").detail
    assert found["rebuilt-evidence"] == "not judged"
    assert found["snapshot-id"] == "not judged"
    assert "failed" not in found.values()


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-244: the proof verifier does not exist yet")
def test_a_design_edge_the_readers_do_not_supply_leaves_the_evidence_unjudged(
    tmp_path: Path, capsys
) -> None:
    """The verifier leaves the evidence unjudged for a design edge that no reader supplies.

    In a private copy of a generated package one more design edge joins two
    requirements that the readers of the configuration do not join, and the
    root is sealed again over the longer edge list. Given the clean bundle,
    the check named design-guard is not judged, its detail names both
    endpoints of the edge, and the checks named rebuilt-evidence and
    snapshot-id are not judged. The root check is passed. No check fails.

    :verifies: SEG-SREQ-244
    :test-id: SEG-TS-130
    """
    sealed = seal(tmp_path, capsys)
    copy = copy_package(sealed.package, tmp_path, "edge")
    extra = missing_edge(copy)
    edit(copy, "design_consistency_proof", lambda body: body["designEdges"].append(extra))
    reseal(copy)

    report = library_verify(sealed.opened, copy, bundles=list(sealed.opened.bundles))

    found = statuses(report)
    assert found["root"] == "passed"
    assert found["design-guard"] == "not judged"
    detail = _check(report, "design-guard").detail
    assert extra["from"] in detail and extra["to"] in detail
    assert found["rebuilt-evidence"] == "not judged"
    assert found["snapshot-id"] == "not judged"
    assert "failed" not in found.values()


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-245: the proof verifier does not exist yet")
def test_the_evidence_rebuilt_from_the_bundles_must_equal_the_recorded_evidence(
    tmp_path: Path, capsys
) -> None:
    """The verifier reports the rebuilt evidence check as failed when the record differs.

    Given the clean bundle, the verifier rebuilds the outcomes and the findings
    at the revision the package records. For a generated package the check
    named rebuilt-evidence is passed. Two private copies each change the
    record. In the first, the result of one passed outcome in the execution
    coverage record is failed. In the second, the coverage report holds one
    more finding about an outcome of the record. For each copy the check named
    rebuilt-evidence is failed, and the root check is still passed.

    :verifies: SEG-SREQ-245
    :test-id: SEG-TS-131
    """
    sealed = seal(tmp_path, capsys)
    bundles = list(sealed.opened.bundles)
    record = read(sealed.package, "execution_coverage_record")
    outcome = next(o["id"] for o in record["outcomes"] if o["result"] == "passed")
    assert (
        statuses(library_verify(sealed.opened, sealed.package, bundles=bundles))["rebuilt-evidence"]
        == "passed"
    )

    def result(body: dict) -> None:
        for item in body["outcomes"]:
            if item["id"] == outcome:
                item["result"] = "failed"

    def finding(body: dict) -> None:
        body["diagnostics"].append(
            {
                "condition": "outcome was skipped",
                "detail": "",
                "severity": "info",
                "subject": outcome,
            }
        )

    for label, document, tamper in (
        ("result", "execution_coverage_record", result),
        ("finding", "coverage_report", finding),
    ):
        copy = copy_package(sealed.package, tmp_path, label)
        edit(copy, document, tamper)
        found = statuses(library_verify(sealed.opened, copy, bundles=bundles))
        assert found["rebuilt-evidence"] == "failed", label
        assert found["root"] == "passed", label


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-246: the proof verifier does not exist yet")
def test_the_snapshot_identifier_must_follow_from_the_rebuilt_scope(tmp_path: Path, capsys) -> None:
    """The verifier reports the snapshot identifier check as failed when the identifier differs.

    A package generated at one timestamp and a package generated at another
    timestamp each pass the check named snapshot-id, given the clean bundle:
    the verifier mints the identifier with the timestamp the recorded
    identifier carries. A private copy changes the fingerprint part of the
    identifier in the design consistency proof and in the evidence manifest, so
    that the two documents agree, and the directory takes the new name. For
    the copy the check named snapshot-id is failed and the check named identity
    is passed.

    :verifies: SEG-SREQ-246
    :test-id: SEG-TS-132
    """
    sealed = seal(tmp_path, capsys)
    bundles = list(sealed.opened.bundles)
    (tmp_path / "later").mkdir()
    later = seal(tmp_path / "later", capsys, timestamp="2026-10-01T12:34:56+00:00")
    for package, opened in (
        (sealed.package, sealed.opened),
        (later.package, later.opened),
    ):
        found = statuses(library_verify(opened, package, bundles=list(opened.bundles)))
        assert found["snapshot-id"] == "passed", package.name
    assert sealed.package.name != later.package.name

    stamp, fingerprint = sealed.package.name.split("-")
    renamed = f"{stamp}-{flip_digit(fingerprint)}"
    copy = copy_package(sealed.package, tmp_path, "renamed", name=renamed)
    for document in ("design_consistency_proof", "evidence_manifest"):
        edit(copy, document, lambda body: body.update(snapshotId=renamed))

    found = statuses(library_verify(sealed.opened, copy, bundles=bundles))

    assert found["snapshot-id"] == "failed"
    assert found["identity"] == "passed"
