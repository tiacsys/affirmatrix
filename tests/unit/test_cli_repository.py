"""The command-line adapter's three repository reads (ADR-0010).

Everything here drives a real, throwaway ``git`` repository under
``tmp_path`` — there is no faking a version-control system convincingly, and
the whole point of this module is that its three functions behave the way
``git`` itself does. Skipped outright when ``git`` is not on the host's
``PATH``; the library's own tests do not change; nothing here touches the
repository's own case.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from affirmatrix.cli import _repository

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real repository: two committed files, one of which a test may dirty."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "anchored.txt").write_text("the anchored content\n", encoding="utf-8")
    (root / "other.txt").write_text("unrelated content\n", encoding="utf-8")
    _git(root, "add", "anchored.txt", "other.txt")
    _git(root, "commit", "-q", "-m", "first commit")
    return root


def _head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


# --- discovery ---------------------------------------------------------------


def test_discovery_returns_the_commit(repo: Path) -> None:
    revision = _repository.discover_revision(repo)
    assert str(revision) == _head(repo)


def test_a_discovered_revision_looks_like_a_revision() -> None:
    """The typed :class:`Revision` validates a discovered value on construction."""
    with pytest.raises(_repository.RepositoryError, match="revision"):
        _repository.Revision("not-a-revision")


# --- cleanliness --------------------------------------------------------------


def test_a_clean_repository_reports_clean(repo: Path) -> None:
    cleanliness = _repository.check_clean(repo, [Path("anchored.txt")])
    assert cleanliness.clean is True
    assert cleanliness.dirty_paths == ()


def test_a_dirty_anchored_path_refuses_and_names_it(repo: Path) -> None:
    (repo / "anchored.txt").write_text("changed after affirmation\n", encoding="utf-8")
    cleanliness = _repository.check_clean(repo, [Path("anchored.txt")])
    assert cleanliness.clean is False
    assert cleanliness.dirty_paths == ("anchored.txt",)


def test_a_dirty_anchored_path_with_a_space_in_its_name_is_named_intact(repo: Path) -> None:
    """The ``-z`` porcelain form is what keeps such a name from being quoted."""
    (repo / "a file with spaces.txt").write_text("first content\n", encoding="utf-8")
    _git(repo, "add", "a file with spaces.txt")
    _git(repo, "commit", "-q", "-m", "add a spaced file")
    (repo / "a file with spaces.txt").write_text("changed after affirmation\n", encoding="utf-8")
    cleanliness = _repository.check_clean(repo, [Path("a file with spaces.txt")])
    assert cleanliness.clean is False
    assert cleanliness.dirty_paths == ("a file with spaces.txt",)


def test_a_dirty_unanchored_path_does_not_refuse(repo: Path) -> None:
    """Cleanliness is over the anchored paths, not the whole tree."""
    (repo / "other.txt").write_text("changed, but nobody anchored this\n", encoding="utf-8")
    cleanliness = _repository.check_clean(repo, [Path("anchored.txt")])
    assert cleanliness.clean is True
    assert cleanliness.dirty_paths == ()


def test_an_uncommitted_anchored_path_is_dirty_too(repo: Path) -> None:
    """An anchor pointing at content that was never committed is exactly the
    case this check exists to catch — ``git diff --quiet`` alone would miss it."""
    (repo / "untracked.txt").write_text("never committed\n", encoding="utf-8")
    cleanliness = _repository.check_clean(repo, [Path("untracked.txt")])
    assert cleanliness.clean is False
    assert cleanliness.dirty_paths == ("untracked.txt",)


# --- before-content ------------------------------------------------------------


def test_before_content_at_a_recorded_revision_survives_a_later_commit(repo: Path) -> None:
    revision = _head(repo)
    (repo / "anchored.txt").write_text("changed after the recorded revision\n", encoding="utf-8")
    _git(repo, "add", "anchored.txt")
    _git(repo, "commit", "-q", "-m", "second commit")
    recovered = _repository.read_before_content(repo, revision, Path("anchored.txt"))
    assert recovered == b"the anchored content\n"


def test_before_content_for_a_path_absent_at_that_revision_is_refused(repo: Path) -> None:
    revision = _head(repo)
    (repo / "new_file.txt").write_text("added later\n", encoding="utf-8")
    _git(repo, "add", "new_file.txt")
    _git(repo, "commit", "-q", "-m", "second commit")
    with pytest.raises(_repository.RepositoryError, match="new_file.txt"):
        _repository.read_before_content(repo, revision, Path("new_file.txt"))
