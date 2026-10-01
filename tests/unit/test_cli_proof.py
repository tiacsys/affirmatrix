"""``proof check|generate`` (SEG-SREQ-089…094, 126)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from affirmatrix import case, commitment, drift, graph, proof, taxonomy
from affirmatrix.cli import main
from affirmatrix.records import EdgeRecord, LinkState
from affirmatrix.sources.store import StoreLoader

REVISION = "a" * 40


def _minimal_store(root: Path) -> Path:
    """A tiny would-be store: one requirement, fully verified and implemented."""
    (root / "nodes").mkdir(parents=True)
    (root / "edges").mkdir()
    (root / "content").mkdir()
    for name, text in (
        ("req.txt", "the requirement"),
        ("api.txt", "the api"),
        ("body.txt", "the body"),
        ("spec.txt", "the spec"),
        ("impl.txt", "the test body"),
        ("outcome.txt", "passed"),
    ):
        (root / "content" / name).write_text(text, encoding="utf-8")
    (root / "nodes" / "requirements.toml").write_text(
        'kind = "Requirement"\n[nodes]\n"SREQ-1" = { contentHash = "req.txt" }\n',
        encoding="utf-8",
    )
    (root / "nodes" / "implementations.toml").write_text(
        'kind = "Implementation"\n'
        '[nodes]\n"pkg.fn" = { apiHash = "api.txt", bodyHash = "body.txt" }\n',
        encoding="utf-8",
    )
    (root / "nodes" / "test_specifications.toml").write_text(
        'kind = "TestSpecification"\n'
        '[nodes]\n"TS-1" = { specHash = "spec.txt", implHash = "impl.txt" }\n',
        encoding="utf-8",
    )
    (root / "nodes" / "test_outcomes.toml").write_text(
        'kind = "TestOutcome"\n'
        f'[nodes]\n"run-1/TS-1" = {{ contentHash = "outcome.txt", '
        f'result = "passed", revision = "{REVISION}" }}\n',
        encoding="utf-8",
    )
    (root / "edges" / "coverage.toml").write_text(
        "[edges]\n"
        'Verifies = [["TS-1", "SREQ-1"]]\n'
        'Implements = [["pkg.fn", "SREQ-1"]]\n'
        'Confirms = [["run-1/TS-1", "TS-1"]]\n'
        'Witnesses = [["run-1/TS-1", "pkg.fn"]]\n',
        encoding="utf-8",
    )
    return root


def _ready_case(case_root: Path, store_root: Path) -> None:
    """A case with SREQ-1's design edges affirmed active against the minimal store.

    The case holds the design nodes only: it stores no test outcome.
    """
    store = case.AffirmationStore(root=case_root)
    store.initialize()
    current = StoreLoader(root=store_root)
    nodes = [n for n in current.nodes() if n.kind not in taxonomy.evidence_node_kinds()]
    hashes = {n.local_id: commitment.node_hash(n.kind, n.content_hashes) for n in nodes}
    store.write_nodes(nodes)
    design_edges = (("TS-1", "SREQ-1", "Verifies"), ("pkg.fn", "SREQ-1", "Implements"))
    store.write_edges(
        [
            EdgeRecord(
                from_id=from_id,
                to_id=to_id,
                kind=kind,
                state=LinkState.ACTIVE,
                edge_hash=commitment.edge_hash(
                    from_id, to_id, kind, hashes[from_id], hashes[to_id]
                ),
            )
            for from_id, to_id, kind in design_edges
        ]
    )


def test_proof_check_reports_the_gates_coverage_verdict(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-090, SEG-SREQ-091."""
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    _ready_case(case_root, store_root)
    status = main(
        [
            "proof",
            "check",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
            "--json",
        ]
    )
    out = capsys.readouterr().out
    document = json.loads(out)
    assert document["blocked"] is False
    assert status == 0


def test_proof_check_json_is_exactly_the_coverage_report_document(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-091: the same serialization a generated package's own document uses."""
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    _ready_case(case_root, store_root)
    main(
        [
            "proof",
            "check",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
            "--json",
        ]
    )
    printed = json.loads(capsys.readouterr().out)

    store = case.AffirmationStore(root=case_root)
    current = StoreLoader(root=store_root)
    built = graph.build(drift.derive(recorded=store, current=current))
    _, report = proof.check_readiness(
        built,
        {"SREQ-1"},
        snapshot_timestamp=datetime.now(UTC),
        evaluation_date=date.today(),
        current_revision=REVISION,
    )
    assert printed == proof.coverage_report_document(report)


def test_a_blocked_scope_is_the_negative_verdict(tmp_path: Path) -> None:
    """SEG-SREQ-090: nothing affirmed at all."""
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    status = main(
        [
            "proof",
            "check",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
        ]
    )
    assert status == 1


def test_proof_generate_writes_under_the_case_by_default(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-092, SEG-SREQ-093."""
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    _ready_case(case_root, store_root)
    status = main(
        [
            "proof",
            "generate",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
        ]
    )
    assert status == 0
    assert any((case_root / "proofs").iterdir())


def test_proof_generate_output_dir_relocates_the_write_root(tmp_path: Path) -> None:
    """SEG-SREQ-094."""
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    _ready_case(case_root, store_root)
    output_dir = tmp_path / "elsewhere"
    status = main(
        [
            "proof",
            "generate",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
            "--output-dir",
            str(output_dir),
        ]
    )
    assert status == 0
    assert any((output_dir / "proofs").iterdir())
    assert not (case_root / "proofs").is_dir() or not any((case_root / "proofs").iterdir())


def test_proof_generate_refused_renders_the_gates_diagnostics(tmp_path: Path, capsys) -> None:
    store_root = _minimal_store(tmp_path / "store")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    status = main(
        [
            "proof",
            "generate",
            "--case",
            str(case_root),
            "--current",
            str(store_root),
            "--scope",
            "SREQ-1",
            "--revision",
            REVISION,
        ]
    )
    out = capsys.readouterr().out
    assert status == 1
    assert "refused" in out


def test_no_configured_value_reaches_the_design_root(tmp_path: Path) -> None:
    """SEG-SREQ-126: mutate every configured value, the design root does not change."""
    timestamp = "2030-01-02T03:04:05+00:00"
    evaluation_date = "2030-01-02"

    def run(tag: str, repo_path: str, roles: list[str]) -> str:
        store_root = _minimal_store(tmp_path / f"store-{tag}")
        case_root = tmp_path / f"case-{tag}"
        _ready_case(case_root, store_root)
        config_path = tmp_path / f"affirmatrix-{tag}.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "case": str(case_root),
                    "producer": {"root": str(store_root)},
                    "repositories": {"implementation": repo_path},
                    "implementation": "implementation",
                    "roles": roles,
                }
            ),
            encoding="utf-8",
        )
        main(
            [
                "--config",
                str(config_path),
                "proof",
                "generate",
                "--scope",
                "SREQ-1",
                "--revision",
                REVISION,
                "--timestamp",
                timestamp,
                "--evaluation-date",
                evaluation_date,
            ]
        )
        document = json.loads(
            (next((case_root / "proofs").iterdir()) / "design_consistency_proof.jsonld").read_text(
                encoding="utf-8"
            )
        )
        return document["root"]

    root_one = run("one", "/repos/impl-one", ["SoftwareEngineer"])
    root_two = run("two", "/somewhere/else/entirely", ["TestEngineer", "FunctionalSafetyManager"])
    assert root_one == root_two
