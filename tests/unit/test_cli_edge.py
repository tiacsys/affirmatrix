"""``edge show|affirm`` (SEG-SREQ-084…088, 106)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from affirmatrix import case
from affirmatrix.cli import main

REVISION = "a" * 40


def _init(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    return root


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_edge_show_renders_the_tag_and_per_hash_comparison(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """SEG-SREQ-085."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "show",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--json",
        ]
    )
    assert status == 0
    out = capsys.readouterr().out
    assert '"tag": "needs affirmation"' in out


def test_edge_show_verbose_text_renders_hashes_and_before_content(
    tmp_path: Path, would_be_store_copy: Path, capsys
) -> None:
    """Text mode must show what ``-v`` computes, not only ``--json`` (finding 2)."""
    content_dir = would_be_store_copy / "content"
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    for name in ("SEG-SREQ-001", "SEG-SYS-001"):
        path = repo / "requirement" / f"{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"committed content for {name}\n", encoding="utf-8")
    _git(repo, "add", "requirement")
    _git(repo, "commit", "-q", "-m", "first commit")

    root = _init(tmp_path)
    config_path = tmp_path / "affirmatrix.yaml"
    config_path.write_text(
        yaml.safe_dump({"repositories": {str(content_dir): str(repo)}}), encoding="utf-8"
    )
    affirm_status = main(
        [
            "--config",
            str(config_path),
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "seed",
        ]
    )
    assert affirm_status == 0
    capsys.readouterr()  # discard the affirm output

    status = main(
        [
            "--config",
            str(config_path),
            "edge",
            "show",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "-v",
        ]
    )
    assert status == 0
    out = capsys.readouterr().out
    assert "→" in out  # recorded → current
    assert "before-content @ from" in out
    assert "committed content for SEG-SREQ-001" in out


def test_edge_show_with_no_match_cannot_be_judged(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-103."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "show",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "NoSuchKind",
        ]
    )
    assert status == 2


def test_edge_affirm_with_no_selector_cannot_be_judged(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-104."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
        ]
    )
    assert status == 2


def test_edge_affirm_a_mixed_selection_affirms_its_affirmable_members(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-087: kind Refines matches many edges, all pending, all affirmable."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "",
            "--revision",
            REVISION,
        ]
    )
    assert status == 0
    store = case.AffirmationStore(root=root)
    assert any(edge.kind == "Refines" for edge in store.edges())
    assert any(True for _ in store.review_events())


def test_edge_affirm_writes_an_event_without_node_hashes_and_an_edge_with_its_hash(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-024, SEG-SREQ-127: the event binds through its named hashes; the edge folds both."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "seed",
            "--revision",
            REVISION,
        ]
    )
    assert status == 0
    store = case.AffirmationStore(root=root)
    (event,) = store.review_events()
    assert (event.from_node_hash, event.to_node_hash) == (None, None)
    document = (root / "events" / "review_events.jsonld").read_text(encoding="utf-8")
    assert "NodeHash" not in document
    affirmed = next(edge for edge in store.edges() if edge.edge_hash is not None)
    assert (affirmed.from_id, affirmed.to_id) == ("SEG-SREQ-001", "SEG-SYS-001")


def test_edge_affirm_with_no_affirmable_member_is_a_refusal(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-088."""
    root = _init(tmp_path)
    # Affirm once...
    main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
            "--revision",
            REVISION,
        ]
    )
    # ...then affirming the SAME, now-active edge again has nothing affirmable.
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
            "--revision",
            REVISION,
        ]
    )
    assert status == 1


def test_edge_affirm_with_no_matching_edge_cannot_be_judged(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-103."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "NoSuchKind",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
        ]
    )
    assert status == 2


def test_role_and_reason_are_required_with_no_default(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-106."""
    root = _init(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "edge",
                "affirm",
                "--case",
                str(root),
                "--current",
                str(would_be_store_copy),
                "--kind",
                "Refines",
                "--reason",
                "x",
            ]
        )


def test_a_given_revision_is_recorded_for_every_endpoint_as_given(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-109."""
    root = _init(tmp_path)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
            "--revision",
            REVISION,
        ]
    )
    assert status == 0
    store = case.AffirmationStore(root=root)
    (event,) = store.review_events()
    assert event.from_source_revision == REVISION
    assert event.to_source_revision == REVISION


def test_edge_affirm_with_a_role_outside_the_vocabulary_writes_nothing(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-113: the role is one input for the whole invocation, checked
    before any edge is composed — a rejection is exit 2, nothing written."""
    root = _init(tmp_path)
    config_path = tmp_path / "affirmatrix.yaml"
    config_path.write_text(yaml.safe_dump({"roles": ["TestEngineer"]}), encoding="utf-8")
    status = main(
        [
            "--config",
            str(config_path),
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
            "--revision",
            REVISION,
        ]
    )
    assert status == 2
    store = case.AffirmationStore(root=root)
    assert list(store.edges()) == []
    assert list(store.review_events()) == []


def test_edge_affirm_with_a_dirty_anchor_writes_nothing(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    """SEG-SREQ-108, realized as a whole-invocation refusal: any endpoint's
    revision failing to resolve refuses the batch, nothing composed."""
    content_dir = would_be_store_copy / "content"
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    tracked = repo / "requirement" / "SEG-SREQ-001.txt"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("committed content\n", encoding="utf-8")
    _git(repo, "add", "requirement/SEG-SREQ-001.txt")
    _git(repo, "commit", "-q", "-m", "first commit")
    tracked.write_text("changed after affirmation\n", encoding="utf-8")  # now dirty

    root = _init(tmp_path)
    config_path = tmp_path / "affirmatrix.yaml"
    config_path.write_text(
        yaml.safe_dump({"repositories": {str(content_dir): str(repo)}}), encoding="utf-8"
    )
    status = main(
        [
            "--config",
            str(config_path),
            "edge",
            "affirm",
            "--case",
            str(root),
            "--current",
            str(would_be_store_copy),
            "--kind",
            "Refines",
            "--from",
            "SEG-SREQ-001",
            "--to",
            "SEG-SYS-001",
            "--role",
            "SoftwareEngineer",
            "--reason",
            "x",
        ]
    )
    assert status == 2
    store = case.AffirmationStore(root=root)
    assert list(store.edges()) == []
    assert list(store.review_events()) == []
