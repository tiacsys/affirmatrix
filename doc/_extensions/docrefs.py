"""Registry-driven cross-document wiring (cygnus pattern, simplified).

Loads ``doc/documents.yaml`` and derives, for one document, everything that
refers to the *other* documents: intersphinx mappings, sphinx-needs external
needs, and the cross-document navigation groups. The indices (every
document's ``objects.inv`` and ``needs.json``, in the deploy tree's layout) are
read from ``$AFFIRMATRIX_DOC_DEPLOY``. The ``python -m doc`` driver sets it to
a copy of the deploy tree's indices, taken before each stage; without it,
cross-document references degrade gracefully to nothing so a single document
still builds standalone.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load(registry_path: str | Path) -> dict:
    with open(registry_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _deploy_dir() -> Path | None:
    value = os.environ.get("AFFIRMATRIX_DOC_DEPLOY")
    return Path(value) if value else None


def _base_url(registry: dict) -> str:
    return os.environ.get("DOC_BASE_URL", registry.get("base_url", "")).rstrip("/")


def _others(registry: dict, me: str) -> list[dict]:
    return [d for d in registry["documents"] if d["id"] != me]


def intersphinx_for(registry: dict, me: str) -> dict:
    """intersphinx_mapping entries for every other document with a local inventory."""
    deploy = _deploy_dir()
    if deploy is None:
        return {}
    mapping = {}
    for doc in _others(registry, me):
        inv = deploy / doc["id"] / "html" / "objects.inv"
        if inv.is_file():
            url = f"{_base_url(registry)}/{doc['id']}/html"
            mapping[doc["prefix"]] = (url, str(inv))
    return mapping


def external_needs_for(registry: dict, me: str) -> list[dict]:
    """needs_external_needs entries for every other document that exports needs."""
    deploy = _deploy_dir()
    if deploy is None:
        return []
    entries = []
    for doc in _others(registry, me):
        if not doc.get("needs"):
            continue
        needs_json = deploy / doc["id"] / "html" / "needs.json"
        if needs_json.is_file():
            # No id_prefix: needs share one global ID namespace across the
            # federation (the SEG-SYS-/SEG-SREQ-/SEG-TS- conventions keep it
            # collision-free), so cross-document links use native IDs.
            entries.append(
                {
                    "base_url": f"{_base_url(registry)}/{doc['id']}/html",
                    "json_path": str(needs_json),
                }
            )
    return entries


def nav_groups(registry: dict, me: str) -> list[dict]:
    """Cross-document navigation: one entry per group, documents in registry order."""
    base = _base_url(registry)
    groups = []
    for group in registry.get("groups", []):
        links = [
            {"label": d["title"], "href": f"{base}/{d['id']}/html/", "current": d["id"] == me}
            for d in registry["documents"]
            if d.get("group") == group["id"]
        ]
        if links:
            groups.append({"title": group["title"], "links": links})
    return groups
