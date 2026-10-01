"""Shared pytest fixtures for the command-line and configuration test modules."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

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


TOOLBOX_EVIDENCE = Path(__file__).resolve().parents[1] / "fixtures" / "toolbox_evidence"
RUN_BUNDLES = Path(__file__).resolve().parents[1] / "fixtures" / "run_bundles"
CLEAN_BUNDLE = RUN_BUNDLES / "clean"


@pytest.fixture
def composed_config(tmp_path: Path) -> Callable[..., Path]:
    """A factory for a configuration file that points the readers at the toolbox evidence fixture.

    Every path is absolute, so the file names the same places wherever it is
    written; nothing is copied and nothing under the fixture is written. The
    repository is the fixture's ``sources`` tree (where the extractor finds the
    C files Doxygen names) and the requirement source directory is a path under
    it that need not exist. Each keyword overrides one part. The file names no run
    bundle: a test names it where the command line would, and the top-level key
    ``implementation`` names the checkout whose records the bundle holds.
    """

    def write(
        *,
        where: Path | None = None,
        repositories: dict[str, str] | None = None,
        producer: dict | None = None,
        requirements: bool = True,
        content: bool = True,
    ) -> Path:
        evidence = TOOLBOX_EVIDENCE
        block: dict = {"repository": "toolbox"}
        if requirements:
            block["requirements"] = {
                "export": str(evidence / "needs" / "requirement-specification" / "needs.json"),
                "types": ["requirement", "top_requirement"],
                "source": str(evidence / "sources" / "doc" / "requirement-specification"),
            }
        if content:
            block["implementations"] = {
                "export": str(evidence / "needs" / "api-traceability" / "needs.json"),
                "doxygen": str(evidence / "xml" / "dox-safe-data-api"),
            }
            block["specifications"] = {
                "export": str(evidence / "needs" / "test-specification" / "needs.json"),
                "doxygen": str(evidence / "xml" / "dox-safe-data-testspec"),
            }
        mapped = (
            repositories if repositories is not None else {"toolbox": str(evidence / "sources")}
        )
        block.update(producer or {})
        document = {"repositories": mapped, "implementation": "toolbox", "producer": block}
        path = (where or tmp_path) / "affirmatrix.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
        return path

    return write
