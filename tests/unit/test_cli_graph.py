"""``graph check|status`` (SEG-SREQ-076…083)."""

from __future__ import annotations

from pathlib import Path

from affirmatrix import case, commitment
from affirmatrix.cli import main
from affirmatrix.records import EdgeRecord, LinkState
from affirmatrix.sources.store import StoreLoader


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
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy), "--json"]
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
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy)]
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
    nodes = list(current.nodes())
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
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy)]
    )
    assert status == 1


def test_graph_status_verbose_adds_the_per_hash_comparison(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    root = tmp_path / "case"
    store = case.AffirmationStore(root=root)
    store.initialize()
    current = StoreLoader(root=would_be_store_copy)
    nodes = list(current.nodes())
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
        ]
    )
    assert status == 0
    out = capsys.readouterr().out
    assert '"comparison"' in out
    assert '"matching"' in out

    text_status = main(
        ["graph", "status", "--case", str(root), "--current", str(would_be_store_copy), "-v"]
    )
    assert text_status == 0
    text_out = capsys.readouterr().out
    assert "→" in text_out  # recorded → current, finding 2
