"""``graph check|status`` (SEG-SREQ-076…083)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from affirmatrix import case, commitment, taxonomy
from affirmatrix.cli import main
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources.store import StoreLoader

#: The would-be store holds test outcomes, so graph status asks for the
#: implementation revision. No repository stands behind the store, so the
#: tests give one.
REVISION = ["--revision", "a-revision"]

#: The revision the clean run bundle records for the implementation checkout.
BUNDLE_REVISION = "5847f3fdca777b8d62615d84b8926fdc8ce125ed"
CLEAN_BUNDLE = Path(__file__).resolve().parents[1] / "fixtures" / "run_bundles" / "clean"


def _design_nodes(current: StoreLoader) -> list[NodeRecord]:
    """The store's nodes without its test outcomes, which the case does not store."""
    return [n for n in current.nodes() if n.kind not in taxonomy.evidence_node_kinds()]


def test_graph_check_reports_counts_by_kind_and_pending(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-077."""
    status = main(["graph", "check", "--current", str(would_be_store_copy), "--json"])
    assert status == 0
    out = capsys.readouterr().out
    assert '"pending"' in out
    assert '"nodesByKind"' in out


def test_graph_check_over_an_unbuildable_stream_is_the_negative_verdict(
    tmp_path: Path, capsys
) -> None:
    """SEG-SREQ-078, SEG-SREQ-079: no count of anything."""
    unbuildable = tmp_path / "unbuildable"
    (unbuildable / "nodes").mkdir(parents=True)
    (unbuildable / "edges").mkdir()
    (unbuildable / "content").mkdir()
    (unbuildable / "content" / "x.txt").write_text("x", encoding="utf-8")
    (unbuildable / "nodes" / "bad.toml").write_text(
        'kind = "NotADeclaredKind"\n[nodes]\nX = { contentHash = "x.txt" }\n', encoding="utf-8"
    )
    status = main(["graph", "check", "--current", str(unbuildable)])
    out = capsys.readouterr().out
    assert status == 1
    assert "pending" not in out
    assert "nodes by kind" not in out


def test_graph_status_derives_every_edges_state(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-080."""
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    status = main(
        [
            "graph",
            "status",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--json",
            *REVISION,
        ]
    )
    assert status == 0
    out = capsys.readouterr().out
    assert '"state": "pending"' in out


def test_graph_status_over_an_unbuildable_current_stream_cannot_be_judged(
    tmp_path: Path,
) -> None:
    """SEG-SREQ-081."""
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    status = main(
        ["graph", "status", "--case", str(root), "--current", str(tmp_path / "nope")]
    )
    assert status == 2


def test_graph_status_with_only_pending_edges_is_the_positive_verdict(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-082."""
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    status = main(
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy), *REVISION]
    )
    assert status == 0


def test_graph_status_naming_a_suspect_or_broken_edge_is_the_negative_verdict(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-083."""
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    current = StoreLoader(root=would_be_store_copy)
    nodes = _design_nodes(current)
    hashes = {n.local_id: commitment.node_hash(n.kind, n.content_hashes) for n in nodes}
    target_edge = next(edge for edge in current.edges() if edge.kind == "Implements")
    store.write_nodes(nodes)
    store.write_edges(
        [
            EdgeRecord(
                from_id=target_edge.from_id,
                to_id=target_edge.to_id,
                kind="Implements",
                state=LinkState.ACTIVE,
                edge_hash=commitment.edge_hash(
                    target_edge.from_id,
                    target_edge.to_id,
                    "Implements",
                    hashes[target_edge.from_id],
                    b"0" * 32,  # a hash that will not recompute equal
                ),
            )
        ]
    )
    status = main(
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy), *REVISION]
    )
    assert status == 1


def test_graph_status_verbose_adds_the_per_hash_comparison(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    current = StoreLoader(root=would_be_store_copy)
    nodes = _design_nodes(current)
    hashes = {n.local_id: commitment.node_hash(n.kind, n.content_hashes) for n in nodes}
    edge = next(edge for edge in current.edges() if edge.kind == "Refines")
    from_node = next(n for n in nodes if n.local_id == edge.from_id)
    to_node = next(n for n in nodes if n.local_id == edge.to_id)
    store.write_nodes(nodes)
    edge_hash = commitment.edge_hash(
        edge.from_id, edge.to_id, edge.kind, hashes[edge.from_id], hashes[edge.to_id]
    )
    store.write_edges(
        [
            EdgeRecord(
                from_id=edge.from_id,
                to_id=edge.to_id,
                kind=edge.kind,
                state=LinkState.ACTIVE,
                edge_hash=edge_hash,
            )
        ]
    )
    from affirmatrix import affirmation

    composed = affirmation.compose(
        EdgeRecord(
            from_id=edge.from_id, to_id=edge.to_id, kind=edge.kind, state=LinkState.PENDING
        ),
        from_node=from_node,
        to_node=to_node,
        role="SoftwareEngineer",
        reason="seed the event",
        from_source_revision="a" * 40,
        to_source_revision="b" * 40,
    )
    store.append_review_events([composed.event])

    status = main(
        [
            "graph",
            "status",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--json",
            "-v",
            *REVISION,
        ]
    )
    assert status == 0
    out = capsys.readouterr().out
    assert '"comparison"' in out
    assert '"matching"' in out

    text_status = main(
        [
            "graph",
            "status",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "-v",
            *REVISION,
        ]
    )
    assert text_status == 0
    text_out = capsys.readouterr().out
    assert "→" in text_out  # recorded → current, finding 2


def _case_with_a_vanished_edge(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    anchor = ContentAnchor(digest=b"0" * 32, repository="r", path="p", locator="file")
    store.write_nodes(
        [
            NodeRecord("SEG-GONE-1", "Requirement", {"contentHash": anchor}),
            NodeRecord("SEG-GONE-2", "Requirement", {"contentHash": anchor}),
        ]
    )
    store.write_edges(
        [
            EdgeRecord(
                from_id="SEG-GONE-1",
                to_id="SEG-GONE-2",
                kind="Refines",
                state=LinkState.ACTIVE,
                edge_hash=b"1" * 32,
            )
        ]
    )
    return root


def _status_lines(root: Path, current: Path, capsys, *extra: str) -> tuple[int, list[str]]:
    capsys.readouterr()
    status = main(
        ["graph", "status", "--case", str(root), "--current", str(current), *REVISION, *extra]
    )
    return status, capsys.readouterr().out.splitlines()


def test_graph_status_lists_a_vanished_edge_without_a_state(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-137: the row names the edge and says it vanished, with no parenthesised state."""
    root = _case_with_a_vanished_edge(tmp_path)
    _, lines = _status_lines(root, would_be_store_copy, capsys)
    row = [line for line in lines if line.startswith("SEG-GONE-1 --")]
    assert row == ["SEG-GONE-1 --[Refines]--> SEG-GONE-2  vanished from the current stream"]


def test_graph_status_json_row_of_a_vanished_edge_has_no_state_key(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-137."""
    root = _case_with_a_vanished_edge(tmp_path)
    _, lines = _status_lines(root, would_be_store_copy, capsys, "--json")
    rows = json.loads("\n".join(lines))["edges"]
    vanished = [row for row in rows if row["from"] == "SEG-GONE-1"]
    assert vanished == [{"from": "SEG-GONE-1", "to": "SEG-GONE-2", "kind": "Refines"}]


def test_graph_status_lists_vanished_edges_after_every_derived_edge(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-137: the vanished rows come last, so a leading slice of the listing is unchanged."""
    root = _case_with_a_vanished_edge(tmp_path)
    _, lines = _status_lines(root, would_be_store_copy, capsys)
    rows = [line for line in lines if not line.startswith("evidence:")]
    assert rows[-1].startswith("SEG-GONE-1 --")
    assert all("(" in line for line in rows[:-1])


def test_graph_status_pending_count_ignores_a_vanished_edge(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-137: no state, so the vanished row is in no state's count."""
    root = _case_with_a_vanished_edge(tmp_path)
    _, lines = _status_lines(root, would_be_store_copy, capsys)
    assert not [line for line in lines if "SEG-GONE" in line and "(" in line]


def test_graph_status_verdict_is_positive_when_only_a_vanished_edge_was_recorded_active(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-138: a vanished edge stays out of the verdict."""
    root = _case_with_a_vanished_edge(tmp_path)
    status, _ = _status_lines(root, would_be_store_copy, capsys)
    assert status == 0


def test_graph_status_verbose_gives_a_vanished_edge_no_comparison(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-137."""
    root = _case_with_a_vanished_edge(tmp_path)
    _, lines = _status_lines(root, would_be_store_copy, capsys, "--json", "-v")
    rows = json.loads("\n".join(lines))["edges"]
    assert "comparison" not in next(row for row in rows if row["from"] == "SEG-GONE-1")


def test_graph_status_without_a_producer_cannot_be_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEG-SREQ-142: no current stream given and none configured is a request it could not judge."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    assert main(["graph", "status", "--case", str(root)]) == 2


def test_graph_check_renders_counts_by_kind_as_words(
    would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-077: the counts read as words, not as a Python literal."""
    main(["graph", "check", "--current", str(would_be_store_copy)])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("checked: current stream at ")
    assert lines[1].startswith("nodes by kind: Implementation ")
    assert lines[2].startswith("edges by kind: ")
    assert "{" not in lines[1] + lines[2]


def test_graph_check_json_keeps_the_by_kind_mappings(would_be_store_copy: Path, capsys) -> None:
    """SEG-SREQ-077: the structured rendering is unchanged."""
    main(["graph", "check", "--current", str(would_be_store_copy), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert isinstance(report["nodesByKind"], dict)
    assert isinstance(report["edgesByKind"], dict)


# --- over a case synced from a composed producer -------------------------------


def _synced_from_composed(tmp_path: Path, composed_config, **overrides) -> tuple[Path, Path]:
    config_path = composed_config(**overrides)
    root = tmp_path / "case"
    assert main(["--config", str(config_path), "case", "init", "--case", str(root)]) == 0
    assert main(["--config", str(config_path), "case", "sync", "--case", str(root)]) == 0
    return config_path, root


def test_graph_check_over_a_case_synced_from_a_composed_producer_reports_62_pending(
    tmp_path: Path, composed_config, capsys
) -> None:
    _, root = _synced_from_composed(tmp_path, composed_config)
    capsys.readouterr()
    status = main(["graph", "check", "--case", str(root), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert status == 0
    assert report["pending"] == 62
    assert report["nodesByKind"] == {
        "Implementation": 12,
        "Requirement": 29,
        "TestSpecification": 19,
    }
    assert report["edgesByKind"] == {"Implements": 16, "Refines": 22, "Verifies": 24}


def test_graph_status_over_a_composed_producer_exits_0_with_every_edge_pending(
    tmp_path: Path, composed_config, capsys
) -> None:
    config_path, root = _synced_from_composed(tmp_path, composed_config)
    capsys.readouterr()
    status = main(["--config", str(config_path), "graph", "status", "--case", str(root), "--json"])
    rows = json.loads(capsys.readouterr().out)["edges"]
    assert status == 0
    assert len(rows) == 62
    assert {row["state"] for row in rows} == {"pending"}




def test_graph_status_over_a_named_bundle_lists_strong_edges_and_counts_evidence(
    tmp_path: Path, composed_config, capsys
) -> None:
    """SEG-SREQ-080, SEG-SREQ-210: the 62 strong edges are the rows; the 76 outcomes are counted."""
    config_path, root = _synced_from_composed(tmp_path, composed_config)
    capsys.readouterr()
    status = main(
        [
            "--config",
            str(config_path),
            "graph",
            "status",
            "--case",
            str(root),
            "--json",
            "--bundle",
            str(CLEAN_BUNDLE),
            "--revision",
            BUNDLE_REVISION,
        ]
    )
    document = json.loads(capsys.readouterr().out)
    assert status == 0
    assert len(document["edges"]) == 62
    assert {row["state"] for row in document["edges"]} == {"pending"}
    assert document["evidence"] == {"current": 76, "stale": 0, "dangling": 0}


def _store_with_one_outcome(root: Path) -> Path:
    """A would-be store in ``root`` that holds one requirement and one outcome at ``r1``."""
    for name in ("nodes", "edges", "content"):
        (root / name).mkdir(parents=True)
    (root / "content" / "req.txt").write_text("the requirement\n", encoding="utf-8")
    (root / "content" / "outcome.txt").write_text("passed\n", encoding="utf-8")
    (root / "nodes" / "requirements.toml").write_text(
        'kind = "Requirement"\n[nodes]\n"REQ-1" = { contentHash = "req.txt" }\n',
        encoding="utf-8",
    )
    (root / "nodes" / "outcomes.toml").write_text(
        'kind = "TestOutcome"\n[nodes]\n'
        '"run-1/TS-1" = { contentHash = "outcome.txt", result = "passed", revision = "r1" }\n',
        encoding="utf-8",
    )
    (root / "edges" / "coverage.toml").write_text("[edges]\n", encoding="utf-8")
    return root


def test_graph_status_text_ends_with_the_evidence_counts(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-210: the plain rendering names the three counts after the rows."""
    store = _store_with_one_outcome(tmp_path / "store")
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    status = main(["graph", "status", "--case", str(root), "--current", str(store), *REVISION])
    last = capsys.readouterr().out.splitlines()[-1]
    assert status == 0
    assert last == "evidence: 0 at the current revision, 1 at another revision, 0 dangling"


def test_graph_status_without_a_revision_over_a_stream_with_outcomes_cannot_be_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEG-SREQ-208: the stream holds an outcome, and no repository gives a revision."""
    monkeypatch.chdir(tmp_path)
    store = _store_with_one_outcome(tmp_path / "store")
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    status = main(["graph", "status", "--case", str(root), "--current", str(store)])
    assert status == 2
