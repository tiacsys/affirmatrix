"""``case init|check|sync|refresh|remove`` (SEG-SREQ-069…075, 136, 141)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from affirmatrix import case, commitment
from affirmatrix.cli import main
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources.store import StoreLoader


def _case_root(tmp_path: Path) -> Path:
    return tmp_path / "case"


def test_case_init_creates_layout_and_schemas(tmp_path: Path) -> None:
    """SEG-SREQ-070."""
    root = _case_root(tmp_path)
    status = main(["case", "init", "--case", str(root)])
    assert status == 0
    store = case.AffirmationStore(root=root)
    assert store.layout() == frozenset(
        {"nodes", "edges", "events", "proofs", "schema"}
    )
    assert store.missing_schemas() == frozenset()


def test_case_init_on_an_existing_case_succeeds_unchanged(tmp_path: Path) -> None:
    root = _case_root(tmp_path)
    assert main(["case", "init", "--case", str(root)]) == 0
    before = sorted((root / "schema").iterdir())
    assert main(["case", "init", "--case", str(root)]) == 0
    assert sorted((root / "schema").iterdir()) == before


def test_case_check_reports_layout_schemas_counts_config_and_producer(
    tmp_path: Path, would_be_store_copy: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEG-SREQ-071."""
    monkeypatch.chdir(tmp_path)  # the conventional ./affirmatrix.yaml must not be found
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    status = main(
        ["case", "check", "--case", str(root), "--current", str(would_be_store_copy), "--json"]
    )
    out = capsys.readouterr().out
    assert status == 0
    assert '"producerReadable": true' in out
    assert '"missingSchemas": []' in out
    assert '"configurationFound": false' in out


def test_case_check_reports_an_unreadable_producer(tmp_path: Path, capsys) -> None:
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    status = main(
        ["case", "check", "--case", str(root), "--current", str(tmp_path / "nope"), "--json"]
    )
    out = capsys.readouterr().out
    assert '"producerReadable": false' in out
    assert status == 1


def test_case_sync_writes_the_derived_stream_never_demoting(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-072, SEG-SREQ-073."""
    root = _case_root(tmp_path)
    store = case.AffirmationStore(root=root)
    store.initialize()

    current = StoreLoader(root=would_be_store_copy)
    nodes = list(current.nodes())
    hashes = {node.local_id: commitment.node_hash(node.kind, node.content_hashes) for node in nodes}
    one_edge = next(iter(current.edges()))
    store.write_nodes(nodes)
    store.write_edges(
        [
            EdgeRecord(
                from_id=one_edge.from_id,
                to_id=one_edge.to_id,
                kind=one_edge.kind,
                state=LinkState.ACTIVE,
                edge_hash=commitment.edge_hash(
                    one_edge.from_id,
                    one_edge.to_id,
                    one_edge.kind,
                    hashes[one_edge.from_id],
                    hashes[one_edge.to_id],
                ),
            )
        ]
    )

    status = main(
        ["case", "sync", "--case", str(root), "--current", str(would_be_store_copy)]
    )
    assert status == 0
    edges_by_reference = {
        (edge.from_id, edge.to_id, edge.kind): edge for edge in store.edges()
    }
    affirmed = edges_by_reference[(one_edge.from_id, one_edge.to_id, one_edge.kind)]
    assert affirmed.state is LinkState.ACTIVE
    assert affirmed.edge_hash is not None


def test_case_sync_reports_vanished_edges_without_removing_them(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-074."""
    root = _case_root(tmp_path)
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
                from_id="SEG-GONE-1", to_id="SEG-GONE-2", kind="Refines", state=LinkState.PENDING
            )
        ]
    )

    status = main(["case", "sync", "--case", str(root), "--current", str(would_be_store_copy)])
    assert status == 0
    # The vanished edge — its endpoints are not in the would-be store's own
    # current stream — is reported, but still reads back from the store.
    still_present = [
        edge
        for edge in store.edges()
        if (edge.from_id, edge.to_id, edge.kind) == ("SEG-GONE-1", "SEG-GONE-2", "Refines")
    ]
    assert len(still_present) == 1


def test_case_remove_removes_only_the_selectors_names(tmp_path: Path) -> None:
    """SEG-SREQ-075."""
    root = _case_root(tmp_path)
    store = case.AffirmationStore(root=root)
    store.initialize()
    store.write_edges(
        [
            EdgeRecord(from_id="A", to_id="B", kind="Refines", state=LinkState.PENDING),
            EdgeRecord(from_id="C", to_id="D", kind="Refines", state=LinkState.PENDING),
        ]
    )
    status = main(
        ["case", "remove", "--case", str(root), "--kind", "Refines", "--from", "A", "--to", "B"]
    )
    assert status == 0
    remaining = {(edge.from_id, edge.to_id) for edge in store.edges()}
    assert remaining == {("C", "D")}


def test_case_remove_with_no_match_cannot_be_judged(tmp_path: Path) -> None:
    """SEG-SREQ-103, applied to remove as SEG-SREQ-099 states."""
    root = _case_root(tmp_path)
    case.AffirmationStore(root=root).initialize()
    status = main(["case", "remove", "--case", str(root), "--kind", "NoSuchKind"])
    assert status == 2


def _stale_case(tmp_path: Path) -> Path:
    root = _case_root(tmp_path)
    assert main(["case", "init", "--case", str(root)]) == 0
    (root / "schema" / "requirement.schema.json").write_text("{}\n", encoding="utf-8")
    (root / "schema" / "waiver.schema.json").unlink()
    return root


def test_case_refresh_prints_each_schema_it_rewrote_and_exits_zero(
    tmp_path: Path, capsys
) -> None:
    """SEG-SREQ-141."""
    root = _stale_case(tmp_path)
    capsys.readouterr()
    status = main(["case", "refresh", "--case", str(root)])
    assert status == 0
    assert capsys.readouterr().out.splitlines() == [
        "refreshed: requirement.schema.json",
        "refreshed: waiver.schema.json",
    ]


def test_case_refresh_of_a_current_case_says_the_copy_is_up_to_date(
    tmp_path: Path, capsys
) -> None:
    """SEG-SREQ-141."""
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    capsys.readouterr()
    assert main(["case", "refresh", "--case", str(root)]) == 0
    assert capsys.readouterr().out == "schema copy up to date\n"


def test_case_refresh_json_lists_the_refreshed_names(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-141."""
    root = _stale_case(tmp_path)
    capsys.readouterr()
    assert main(["case", "refresh", "--case", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "refreshed": ["requirement.schema.json", "waiver.schema.json"]
    }


def test_case_refresh_json_of_a_current_case_lists_none(tmp_path: Path, capsys) -> None:
    """SEG-SREQ-141."""
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    capsys.readouterr()
    assert main(["case", "refresh", "--case", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"refreshed": []}


def test_case_refresh_of_a_missing_case_root_cannot_be_judged(tmp_path: Path) -> None:
    """SEG-SREQ-141, SEG-SREQ-139: exit 2, and nothing is created."""
    root = _case_root(tmp_path)
    assert main(["case", "refresh", "--case", str(root)]) == 2
    assert not root.exists()


def test_case_refresh_leaves_the_records_untouched(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-139: records written by a sync are byte-identical after a refresh."""
    root = _stale_case(tmp_path)
    main(["case", "sync", "--case", str(root), "--current", str(would_be_store_copy)])
    records = {
        path: path.read_bytes()
        for directory in ("nodes", "edges")
        for path in (root / directory).rglob("*.jsonld")
    }
    assert records
    main(["case", "refresh", "--case", str(root)])
    assert {path: path.read_bytes() for path in records} == records


def _tree(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_case_sync_over_an_unbuildable_stream_writes_nothing_and_cannot_be_judged(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-136: a refines cycle in the current stream stops the sync before any write."""
    root = _case_root(tmp_path)
    case.AffirmationStore(root=root).initialize()
    refines = would_be_store_copy / "edges" / "refines.toml"
    refines.write_text(
        refines.read_text(encoding="utf-8").replace(
            "Refines = [\n", 'Refines = [\n    ["SEG-SYS-001", "SEG-SREQ-001"],\n', 1
        ),
        encoding="utf-8",
    )
    before = _tree(root)
    status = main(["case", "sync", "--case", str(root), "--current", str(would_be_store_copy)])
    assert status == 2
    assert _tree(root) == before


def test_case_sync_over_an_unreadable_producer_writes_nothing(tmp_path: Path) -> None:
    """SEG-SREQ-136: a producer that cannot be read stops the sync before any write."""
    root = _case_root(tmp_path)
    case.AffirmationStore(root=root).initialize()
    before = _tree(root)
    status = main(["case", "sync", "--case", str(root), "--current", str(tmp_path / "nope")])
    assert status == 2
    assert _tree(root) == before


def test_case_sync_without_a_producer_cannot_be_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEG-SREQ-142: no current stream given and none configured is a request it could not judge."""
    monkeypatch.chdir(tmp_path)
    root = _case_root(tmp_path)
    case.AffirmationStore(root=root).initialize()
    before = _tree(root)
    assert main(["case", "sync", "--case", str(root)]) == 2
    assert _tree(root) == before


def test_case_check_renders_record_counts_as_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """SEG-SREQ-071: the counts read as words, not as a Python literal."""
    monkeypatch.chdir(tmp_path)
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    capsys.readouterr()
    main(["case", "check", "--case", str(root)])
    assert "record counts: nodes 0, edges 0, review events 0\n" in capsys.readouterr().out


def test_case_check_json_keeps_the_record_count_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """SEG-SREQ-071: the structured rendering is unchanged."""
    monkeypatch.chdir(tmp_path)
    root = _case_root(tmp_path)
    main(["case", "init", "--case", str(root)])
    capsys.readouterr()
    main(["case", "check", "--case", str(root), "--json"])
    assert json.loads(capsys.readouterr().out)["recordCounts"] == {
        "edges": 0,
        "nodes": 0,
        "reviewEvents": 0,
    }


def test_case_check_run_from_another_directory_finds_the_case_a_config_file_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """SEG-SREQ-135: a configuration file's relative case resolves against the file."""
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "affirmatrix.yaml").write_text("case: ./the-case\n", encoding="utf-8")
    main(["case", "init", "--case", str(repository / "the-case")])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    capsys.readouterr()
    main(["case", "check", "--config", str(repository / "affirmatrix.yaml"), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["configurationFound"] is True
    assert report["layout"] == ["edges", "events", "nodes", "proofs", "schema"]
