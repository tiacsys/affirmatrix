"""Verification suite for the case that stores no test evidence.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
affirmation store refuses test outcome nodes and evidence edges (Confirms,
Witnesses, Excuses). ``case sync`` removes the ones that an older case holds,
after it has written the derived stream.

The older case is ``tests/fixtures/legacy_case/``: 10 test outcome nodes, 10
Confirms and 12 Witnesses edges in the state pending, six affirmed strong
edges with review events, four pending strong edges and one stored package.
The tests copy it and its stream to ``tmp_path`` and never write the fixture.
They read the case documents as JSON, so a record is read without the code
under test. The stream is copied beside the case, as the case records its
location as ``stream/content``; a sync from the copy therefore writes the same
anchors as the sync that made the case. The stream copy holds the design only:
the files that hold the outcomes and the evidence edges are deleted from it,
because a producer of the design supplies no test evidence.

The store's own names are read inside the test bodies only, so this module
collects before the code carries the change.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import pytest

from .evidence_support import LEGACY_CASE, run, snapshot

EVIDENCE_DOCUMENTS = ("edges/confirms.jsonld", "edges/witnesses.jsonld")
OUTCOME_DOCUMENT = "nodes/test_outcomes.jsonld"
STRONG_DOCUMENTS = ("edges/refines.jsonld", "edges/verifies.jsonld", "edges/implements.jsonld")
REMOVED = {OUTCOME_DOCUMENT, *EVIDENCE_DOCUMENTS}


def _entries(root: Path, document: str) -> list[dict]:
    path = root / document
    return json.loads(path.read_text(encoding="utf-8"))["@graph"] if path.exists() else []


def _local(iri: str) -> str:
    return unquote(iri.rsplit("/", 1)[1])


def _legacy(tmp_path: Path) -> tuple[Path, Path]:
    """Copies of the legacy case and its stream, the stream without outcomes and evidence edges.

    The copy is checked against the shape the README states, so a fixture that
    drifted fails here and not somewhere below.
    """
    root, stream = tmp_path / "case", tmp_path / "stream"
    shutil.copytree(LEGACY_CASE / "case", root)
    shutil.copytree(LEGACY_CASE / "stream", stream)
    assert len(_entries(root, OUTCOME_DOCUMENT)) == 10
    assert len(_entries(root, "edges/confirms.jsonld")) == 10
    assert len(_entries(root, "edges/witnesses.jsonld")) == 12
    assert {e["seg:linkState"] for d in EVIDENCE_DOCUMENTS for e in _entries(root, d)} == {
        "pending"
    }
    states = [e["seg:linkState"] for d in STRONG_DOCUMENTS for e in _entries(root, d)]
    assert sorted(states) == ["active"] * 6 + ["pending"] * 4
    assert len(_entries(root, "events/review_events.jsonld")) == 6
    assert len(list((root / "proofs").iterdir())) == 1
    (stream / "nodes" / "test_outcomes.toml").unlink()
    (stream / "edges" / "evidence.toml").unlink()
    return root, stream


def _sync(capsys, tmp_path: Path, root: Path) -> tuple[int, str]:
    return run(capsys, "case", "sync", "--case", str(root), "--current", "stream")


@pytest.fixture
def at_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from ``tmp_path``, which holds no ``affirmatrix.yaml``, so ``stream`` names the copy."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_store_refuses_test_outcomes_and_evidence_edges(tmp_path: Path) -> None:
    """The affirmation store refuses a write that names a test outcome node or an evidence edge.

    A case holds nothing. A write of a requirement node together with a test
    outcome node is refused, and no file of the case changes. A write of a
    Confirms edge, a Witnesses edge or an Excuses edge is refused, and no file
    changes. A write of a Refines edge together with a Confirms edge is
    refused, and the Refines edge is not written. A write of a waiver node and
    a write of a Refines edge are accepted.

    :verifies: SEG-SREQ-227
    :test-id: SEG-TS-098
    """
    from affirmatrix.case import AffirmationStore, AffirmationStoreError
    from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord, TestResult

    root = tmp_path / "case"
    store = AffirmationStore(root=root)
    store.initialize()
    anchor = ContentAnchor(digest=b"0" * 32, repository="r", path="p", locator="file")
    requirement = NodeRecord("REQ-1", "Requirement", {"contentHash": anchor})
    outcome = NodeRecord(
        "run/TS-1", "TestOutcome", {"contentHash": anchor}, result=TestResult.PASSED, revision="r1"
    )
    before = snapshot(root)

    with pytest.raises(AffirmationStoreError):
        store.write_nodes([requirement, outcome])
    assert snapshot(root) == before
    for kind in ("Confirms", "Witnesses", "Excuses"):
        with pytest.raises(AffirmationStoreError):
            store.write_edges([EdgeRecord("run/TS-1", "TS-1", kind, LinkState.PENDING)])
        assert snapshot(root) == before
    refines = EdgeRecord("REQ-1", "REQ-2", "Refines", LinkState.PENDING)
    with pytest.raises(AffirmationStoreError):
        store.write_edges([refines, EdgeRecord("run/TS-1", "TS-1", "Confirms", LinkState.PENDING)])
    assert snapshot(root) == before

    waiver = NodeRecord(
        "WVR-1", "Waiver", {"contentHash": anchor}, expiry=date(2099, 1, 1), approver="A. Reviewer"
    )
    store.write_nodes([waiver])
    store.write_edges([refines])
    assert [node.local_id for node in store.nodes()] == ["WVR-1"]
    assert [(e.kind, e.from_id) for e in store.edges()] == [("Refines", "REQ-1")]


def test_case_sync_removes_the_stored_evidence_and_names_it(
    tmp_path: Path, capsys, at_tmp: Path
) -> None:
    """Case sync removes every stored outcome and evidence edge, after it writes the derived stream.

    The legacy case holds 10 test outcome nodes, 10 Confirms edges and 12
    Witnesses edges. Case sync runs from a stream of the design alone and exits
    with status 0. Afterwards the case holds no test outcome node and no
    Confirms or Witnesses edge. The report names each of the 10 outcomes, and
    each of the 22 edges by its two ends and its kind. The documents of the
    strong edges, the review events, the stored package and the other node
    documents are byte for byte as before. The six affirmed edges keep their
    hashes.

    :verifies: SEG-SREQ-228
    :test-id: SEG-TS-099
    """
    root, _ = _legacy(tmp_path)
    before = snapshot(root)
    outcomes = [_local(e["id"]) for e in _entries(root, OUTCOME_DOCUMENT)]
    edges = [
        (e["type"].removeprefix("seg:"), _local(e["seg:from"]), _local(e["seg:to"]))
        for document in EVIDENCE_DOCUMENTS
        for e in _entries(root, document)
    ]

    status, out = _sync(capsys, tmp_path, root)

    assert status == 0
    assert _entries(root, OUTCOME_DOCUMENT) == []
    assert all(_entries(root, document) == [] for document in EVIDENCE_DOCUMENTS)
    lines = out.splitlines()
    assert all(any(outcome in line for line in lines) for outcome in outcomes)
    assert len(edges) == 22
    for kind, source, target in edges:
        assert any(kind in line and source in line and target in line for line in lines)
    after = snapshot(root)
    assert set(before) - set(after) <= REMOVED
    assert set(after) - set(before) == set()
    for name in set(after) - REMOVED:
        assert after[name] == before[name], name
    hashed = [e for d in STRONG_DOCUMENTS for e in _entries(root, d) if "seg:edgeHash" in e]
    assert len(hashed) == 6


def test_a_second_sync_removes_nothing_and_changes_nothing(
    tmp_path: Path, capsys, at_tmp: Path
) -> None:
    """A case that holds no evidence is changed by no further case sync.

    The legacy case is synced from a stream of the design alone. A second sync
    from the same stream exits with status 0. Every file of the case is byte
    for byte as it was after the first sync, and the report names none of the
    removed outcomes.

    :verifies: SEG-SREQ-228
    :test-id: SEG-TS-100
    """
    root, _ = _legacy(tmp_path)
    outcomes = [_local(e["id"]) for e in _entries(root, OUTCOME_DOCUMENT)]
    assert _sync(capsys, tmp_path, root)[0] == 0
    after_first = snapshot(root)
    assert after_first.keys() >= {"events/review_events.jsonld"}
    assert _entries(root, OUTCOME_DOCUMENT) == []

    status, out = _sync(capsys, tmp_path, root)

    assert status == 0
    assert snapshot(root) == after_first
    assert not any(outcome in out for outcome in outcomes)


def _forbid_refines_to(directory: Path, target: str) -> None:
    """Make the case's copy of the Refines schema refuse an edge that ends at ``target``."""
    path = directory / "edge-refines.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["not"] = {
        "properties": {"seg:to": {"const": f"https://affirmatrix.dev/case/node/{target}"}},
        "required": ["seg:to"],
    }
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def test_a_refused_sync_removes_nothing(tmp_path: Path, capsys, at_tmp: Path) -> None:
    """A case sync that cannot write the derived stream changes nothing, evidence included.

    The stream of the design holds one Refines edge that the case does not
    store, from FX-SREQ-2 to FX-SREQ-1. The legacy case's copy of the Refines
    schema does not allow an edge that ends at FX-SREQ-1, and every record the
    case stores is still valid. Case sync exits with status 2. Every file of
    the case is byte for byte as before, so the 10 outcomes and the 22 evidence
    edges are still stored.

    :verifies: SEG-SREQ-212
    :test-id: SEG-TS-101
    """
    root, stream = _legacy(tmp_path)
    design = stream / "edges" / "design.toml"
    text = design.read_text(encoding="utf-8")
    design.write_text(
        text.replace("Refines = [\n", 'Refines = [\n    ["FX-SREQ-2", "FX-SREQ-1"],\n'),
        encoding="utf-8",
    )
    _forbid_refines_to(root / "schema", "FX-SREQ-1")
    before = snapshot(root)

    status, _ = _sync(capsys, tmp_path, root)

    assert status == 2
    assert snapshot(root) == before


def test_a_vanished_strong_edge_is_reported_and_kept_and_evidence_is_not_reported(
    tmp_path: Path, capsys, at_tmp: Path
) -> None:
    """Case sync reports a vanished strong edge and keeps it, and reports no vanished evidence edge.

    The stream of the design lacks the Refines edge from FX-SREQ-2 to
    FX-SYS-1, which the legacy case stores as pending. Case sync exits with
    status 0. It reports exactly one vanished edge, that Refines edge, and
    reports no vanished edge of kind Confirms, Witnesses or Excuses, although
    the stream holds none of the 22 evidence edges the case stored. The Refines
    edge is still in the case.

    :verifies: SEG-SREQ-074
    :test-id: SEG-TS-102
    """
    root, stream = _legacy(tmp_path)
    design = stream / "edges" / "design.toml"
    text = design.read_text(encoding="utf-8")
    assert '["FX-SREQ-2", "FX-SYS-1"],' in text
    design.write_text(text.replace('    ["FX-SREQ-2", "FX-SYS-1"],\n', ""), encoding="utf-8")

    status, out = _sync(capsys, tmp_path, root)

    assert status == 0
    vanished = [line for line in out.splitlines() if line.startswith("vanished")]
    assert len(vanished) == 1
    assert "FX-SREQ-2" in vanished[0] and "FX-SYS-1" in vanished[0] and "Refines" in vanished[0]
    kept = [
        (_local(e["seg:from"]), _local(e["seg:to"])) for e in _entries(root, STRONG_DOCUMENTS[0])
    ]
    assert ("FX-SREQ-2", "FX-SYS-1") in kept


def test_a_stored_package_without_run_bundle_digests_still_reads(
    tmp_path: Path, capsys, at_tmp: Path
) -> None:
    """A package stored before run bundles were recorded is read back as written.

    The legacy case stores one package of four documents, and its evidence
    manifest has no field for run bundles. The store reads the package and
    returns the four documents. After a refresh of the case's schema copy to
    the packaged schemas, the store reads the same package again and returns
    the same four documents.

    :verifies: SEG-SREQ-020
    :test-id: SEG-TS-103
    """
    from affirmatrix.case import AffirmationStore

    root, _ = _legacy(tmp_path)
    store = AffirmationStore(root=root)
    (package,) = [path.name for path in (root / "proofs").iterdir()]
    first = dict(store.read_package(package))
    assert sorted(first) == [
        "coverage_report",
        "design_consistency_proof",
        "evidence_manifest",
        "execution_coverage_record",
    ]

    assert run(capsys, "case", "refresh", "--case", str(root))[0] == 0

    assert dict(store.read_package(package)) == first
