"""Shared pytest fixtures for the command-line and configuration test modules."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

WOULD_BE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "would_be_store"


@pytest.fixture
def would_be_store_copy(tmp_path: Path) -> Path:
    """A private copy of the would-be store fixture, safe for a test to mutate.

    The drift-detection exercise depends on editing content between two
    reads; a shared, checked-in fixture must never be the thing a test
    edits, so every test that needs to mutate content gets its own copy
    under ``tmp_path``.
    """
    target = tmp_path / "would_be_store"
    shutil.copytree(WOULD_BE_STORE, target)
    return target
