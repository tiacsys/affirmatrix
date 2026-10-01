"""A judgement's inputs: explicit, discovered, or refused (SEG-SREQ-105…113).

Discovery and cleanliness are exercised against a real, throwaway git
repository — the same discipline ``test_cli_repository.py`` uses — since a
node's anchor must name a repository the configuration maps for either to
apply at all; the would-be store's own anchors never do (they carry a
literal content-directory path), which is exactly why the command-line test
modules pass ``--revision`` explicitly throughout rather than exercising
discovery end to end.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from affirmatrix import config, records
from affirmatrix.cli import _judgement

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "module.py").write_text("original content\n", encoding="utf-8")
    _git(root, "add", "module.py")
    _git(root, "commit", "-q", "-m", "first commit")
    return root


def _anchor(repository: str, path: str = "module.py") -> records.ContentAnchor:
    return records.ContentAnchor(
        digest=hashlib.sha256(b"x").digest(), repository=repository, path=path, locator="file"
    )


def _node(repository: str) -> records.NodeRecord:
    return records.NodeRecord("pkg.fn", "Implementation", {"contentHash": _anchor(repository)})


def test_a_given_revision_overrides_discovery(repo: Path) -> None:
    """SEG-SREQ-109."""
    node = _node("implementation")
    cfg = config.Config(repositories={"implementation": repo})
    assert _judgement.resolve_revision(node, config=cfg, given="a" * 40, label="x") == "a" * 40


def test_a_revision_is_discovered_when_the_repository_is_mapped(repo: Path) -> None:
    """SEG-SREQ-107."""
    node = _node("implementation")
    cfg = config.Config(repositories={"implementation": repo})
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    revision = _judgement.resolve_revision(node, config=cfg, given=None, label="x")
    assert revision == completed.stdout.strip()


def test_a_dirty_anchor_refuses_a_discovered_revision(repo: Path) -> None:
    """SEG-SREQ-108."""
    (repo / "module.py").write_text("changed after affirmation\n", encoding="utf-8")
    node = _node("implementation")
    cfg = config.Config(repositories={"implementation": repo})
    with pytest.raises(_judgement.JudgementError, match="module.py"):
        _judgement.resolve_revision(node, config=cfg, given=None, label="x")


def test_an_unmapped_repository_requires_an_explicit_revision() -> None:
    """SEG-SREQ-110."""
    node = _node("not-configured-anywhere")
    cfg = config.Config()
    with pytest.raises(_judgement.JudgementError, match="repository"):
        _judgement.resolve_revision(node, config=cfg, given=None, label="x")


def test_a_configured_role_vocabulary_is_enforced() -> None:
    """SEG-SREQ-113."""
    cfg = config.Config(roles=frozenset({"SoftwareEngineer"}))
    _judgement.check_role("SoftwareEngineer", cfg)  # does not raise
    with pytest.raises(_judgement.JudgementError, match="role"):
        _judgement.check_role("TestEngineer", cfg)


def test_no_configured_vocabulary_accepts_every_role() -> None:
    _judgement.check_role("anything at all", config.Config())


def test_before_content_is_recovered_at_a_revision(repo: Path) -> None:
    """SEG-SREQ-111."""
    revision_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    (repo / "module.py").write_text("changed later\n", encoding="utf-8")
    _git(repo, "add", "module.py")
    _git(repo, "commit", "-q", "-m", "second commit")
    node = _node("implementation")
    cfg = config.Config(repositories={"implementation": repo})
    content = _judgement.recover_before_content(node, revision_before, cfg)
    assert content == b"original content\n"


def test_the_gates_revision_follows_the_same_rule_as_an_endpoints(repo: Path) -> None:
    """SEG-SREQ-112."""
    cfg = config.Config(repositories={"implementation": repo}, implementation="implementation")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    assert _judgement.resolve_gate_revision(cfg, given=None) == completed.stdout.strip()
    assert _judgement.resolve_gate_revision(cfg, given="b" * 40) == "b" * 40


def test_the_gates_revision_requires_an_explicit_value_when_unconfigured() -> None:
    with pytest.raises(_judgement.JudgementError, match="revision"):
        _judgement.resolve_gate_revision(config.Config(), given=None)


def test_resolve_current_requires_a_producer_when_neither_is_given() -> None:
    with pytest.raises(_judgement.JudgementError, match="producer"):
        _judgement.resolve_current(None, config.Config())


def test_resolve_current_overrides_the_configured_producer(
    tmp_path: Path, would_be_store_copy: Path
) -> None:
    configured = tmp_path / "configured-does-not-exist"
    source = _judgement.resolve_current(
        str(would_be_store_copy), config.Config(producer_root=configured)
    )
    assert source.root == would_be_store_copy


def test_resolve_current_with_a_directory_is_the_store_loader_despite_configured_readers(
    would_be_store_copy: Path, composed_config
) -> None:
    from affirmatrix.sources.store import StoreLoader

    loaded = config.load(composed_config())
    source = _judgement.resolve_current(str(would_be_store_copy), loaded)
    assert isinstance(source, StoreLoader)
    assert source.root == would_be_store_copy


def test_resolve_current_folds_a_missing_reader_export_into_a_judgement_error(
    composed_config,
) -> None:
    path = composed_config(content=False)
    path.write_text(path.read_text(encoding="utf-8").replace("needs.json", "absent.json"))
    with pytest.raises(_judgement.JudgementError, match="cannot be read"):
        _judgement.resolve_current(None, config.load(path))


def test_resolve_current_folds_an_unconfigured_repository_into_a_judgement_error(
    composed_config,
) -> None:
    loaded = config.load(composed_config(repositories={"other": "."}))
    with pytest.raises(_judgement.JudgementError, match="not a configured repository"):
        _judgement.resolve_current(None, loaded)


def test_resolve_timestamp_defaults_to_now_and_is_timezone_aware() -> None:
    stamp = _judgement.resolve_timestamp(None)
    assert stamp.tzinfo is not None


def test_resolve_evaluation_date_parses_an_explicit_iso_date() -> None:
    assert _judgement.resolve_evaluation_date("2030-01-02").isoformat() == "2030-01-02"


def test_the_gates_revision_of_a_repository_git_cannot_read_is_a_judgement_error(
    tmp_path: Path,
) -> None:
    """SEG-SREQ-208: no obtainable revision is a request the command line cannot judge."""
    cfg = config.Config(repositories={"implementation": tmp_path}, implementation="implementation")
    with pytest.raises(_judgement.JudgementError, match="cannot be read"):
        _judgement.resolve_gate_revision(cfg, given=None)
