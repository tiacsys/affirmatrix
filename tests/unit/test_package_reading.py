"""Reading an evidence package from a directory, and naming one in a case."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from affirmatrix import proof
from affirmatrix.case import AffirmationStore, AffirmationStoreError, read_package_directory
from affirmatrix.cli import _judgement, _proof

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden_evidence" / "one_run" / "proofs"


def _golden() -> Path:
    (package,) = sorted(GOLDEN.iterdir())
    return package


def _case_with(tmp_path: Path, *names: str) -> AffirmationStore:
    for name in names:
        shutil.copytree(_golden(), tmp_path / "proofs" / name)
    return AffirmationStore(root=tmp_path)


def test_a_package_directory_reads_with_no_case() -> None:
    documents = read_package_directory(_golden())

    assert set(documents) == {
        "design_consistency_proof",
        "execution_coverage_record",
        "coverage_report",
        "evidence_manifest",
    }
    assert "@context" not in documents["evidence_manifest"]


def test_a_directory_that_holds_no_package_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AffirmationStoreError):
        read_package_directory(tmp_path / "absent")
    with pytest.raises(AffirmationStoreError):
        read_package_directory(tmp_path)


def test_the_case_lists_the_packages_it_holds(tmp_path: Path) -> None:
    assert AffirmationStore(root=tmp_path).snapshot_ids() == ()

    store = _case_with(tmp_path, "20261001T000000Z-aaaaaaaaaaaa", "20261001T000001Z-bbbbbbbbbbbb")

    assert store.snapshot_ids() == (
        "20261001T000000Z-aaaaaaaaaaaa",
        "20261001T000001Z-bbbbbbbbbbbb",
    )
    assert store.proof_directory("20261001T000000Z-aaaaaaaaaaaa").is_dir()


def test_a_package_is_named_by_path_by_identifier_or_by_prefix(tmp_path: Path) -> None:
    store = _case_with(tmp_path, "20261001T000000Z-aaaaaaaaaaaa", "20261001T000001Z-bbbbbbbbbbbb")

    assert _proof.resolve_package(str(_golden()), store) == _golden()
    assert _proof.resolve_package("20261001T000001Z", store).name == "20261001T000001Z-bbbbbbbbbbbb"
    with pytest.raises(_judgement.JudgementError, match="aaaaaaaaaaaa.*bbbbbbbbbbbb"):
        _proof.resolve_package("20261001T00000", store)
    with pytest.raises(_judgement.JudgementError):
        _proof.resolve_package("2030", store)
    with pytest.raises(_judgement.JudgementError):
        _proof.resolve_package("", store)


def test_the_sealed_root_of_a_stored_package_is_the_generator_root() -> None:
    stored = proof.read_package(_golden())
    design = stored.design

    from affirmatrix.proof import _package
    from affirmatrix.records import digest_from_hex, hex_digest

    root = _package.sealed_root(
        requested_ids=design["scope"],
        revision=design["revision"],
        node_hashes=(digest_from_hex(node["hash"]) for node in design["nodeManifest"]),
        edges=((e["from"], e["to"], e["kind"]) for e in design["designEdges"]),
    )

    assert hex_digest(root) == design["root"]
