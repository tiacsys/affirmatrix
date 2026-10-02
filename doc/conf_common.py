"""Shared Sphinx configuration for all affirmatrix documents (cygnus pattern).

Each document's conf.py is a thin shim calling :func:`configure` with its own
directory. The only per-document values are derived from that directory unless
overridden. All cross-document wiring comes from ``documents.yaml`` via the
``docrefs`` helper — nothing per-document is hardcoded here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DOC_ROOT = Path(__file__).resolve().parent

sys.path.insert(0, str(DOC_ROOT / "_extensions"))

import docrefs  # noqa: E402


def configure(namespace: dict, doc_dir: str | Path, project: str | None = None) -> None:
    """Populate a document conf.py's globals with the shared configuration."""
    doc_dir = Path(doc_dir).resolve()
    folder = doc_dir.name
    if project is None:
        project = "affirmatrix — " + folder.replace("-", " ").title()

    registry = docrefs.load(DOC_ROOT / "documents.yaml")

    namespace.update(
        project=project,
        author="the affirmatrix project",
        copyright="2026, The affirmatrix contributors",
        # Document version: exported into needs.json (current_version), which
        # needs_external_needs requires. Placeholder until scoped git-tag
        # version resolution (documents.yaml `version_scope`) is wired in.
        version="0.0.1",
        release="0.0.1.dev0",
        extensions=[
            "sphinx.ext.intersphinx",
            "sphinx_needs",
            "sphinx_rtd_dark_mode",  # RTD theme + light/dark switcher (firmhold)
        ],
        exclude_patterns=["_build"],
        # -- sphinx-needs: shared typed-needs configuration -------------------
        needs_from_toml=os.path.relpath(DOC_ROOT / "needs_config.toml", doc_dir),
        needs_schema_definitions_from_json=str(DOC_ROOT / "schemas.json"),
        needs_build_json=True,
        needs_reproducible_json=True,
        # -- cross-document wiring, derived from the registry ------------------
        intersphinx_mapping=docrefs.intersphinx_for(registry, folder),
        needs_external_needs=docrefs.external_needs_for(registry, folder),
        html_context={"reference_groups": docrefs.nav_groups(registry, folder)},
        html_theme="sphinx_rtd_theme",
        html_theme_options={"logo_only": False, "navigation_depth": 2},
        html_logo=str(DOC_ROOT / "images" / "affirmatrix-logo-small.png"),
        # sphinx_rtd_dark_mode: start light, toggle lives in the sidebar
        default_dark_mode=False,
        templates_path=[str(DOC_ROOT / "_templates")],
    )
