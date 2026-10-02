"""Shared internal — reading a sphinx-needs export as a record source's input.

Not a component and never a requirement subject: the requirements reader and
the content extractor both consume a reproducible ``needs.json`` and refuse the
same things, so the reading lives here once and each of them supplies its own
error type and the name it calls its export by. A record source that used to
carry its own copy now imports this one, so the two cannot drift apart about
what an export must look like.

What an export must be: a JSON object with exactly one version (a source
serves one build; choosing between two builds' hashes would be a silent
decision), whose ``needs`` is an object of objects, and which carries no
build timestamp (``created``) at the top level or in the version entry, the one
mark of a non-reproducible build a reader can see. The null timestamp fields
inside needs are not that.

Every function raises the ``error`` type it is given, with a message that names
the export and, where one need is at fault, that need. No function opens
anything but the export itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_TIMESTAMP_KEY = "created"


def itemized(header: str, items: Sequence[str]) -> str:
    """A message of one header line and one indented line for each of ``items``.

    A refusal that has several things to name gives each its own line, so a
    reader of the message, or a program that reads it, finds one thing on one line.
    """
    return "\n".join([header, *(f"  {item}" for item in items)])


def refuse_timestamps(
    export: Path, label: str, error: type[Exception], holder: Mapping[str, Any], where: str
) -> None:
    """Refuse an export whose ``where`` carries a build timestamp."""
    if _TIMESTAMP_KEY in holder:
        raise error(
            f"{label} {export}: carries a build timestamp "
            f"({_TIMESTAMP_KEY!r}) in {where}; only a reproducible export is consumed"
        )


def read_needs(export: Path, label: str, error: type[Exception]) -> Mapping[str, Any]:
    """The ``needs`` mapping of the one version an export holds.

    Each need is checked to be an object; what a need must carry is the
    caller's to say, through :func:`check_need`.
    """
    try:
        document = json.loads(export.read_text(encoding="utf-8"))
    except (OSError, ValueError) as cause:
        raise error(f"{label} {export}: cannot be read: {cause}") from cause
    if not isinstance(document, dict):
        raise error(f"{label} {export}: the top level is not an object")
    refuse_timestamps(export, label, error, document, "the top level")
    versions = document.get("versions")
    if not isinstance(versions, dict):
        raise error(f"{label} {export}: has no 'versions' object")
    if len(versions) != 1:
        raise error(
            f"{label} {export}: holds {len(versions)} versions "
            f"({', '.join(map(repr, versions)) or 'none'}); a source serves one build, "
            "so an export must hold exactly one"
        )
    ((name, version),) = versions.items()
    if not isinstance(version, dict):
        raise error(f"{label} {export}: version {name!r} is not an object")
    refuse_timestamps(export, label, error, version, f"version {name!r}")
    needs = version.get("needs")
    if not isinstance(needs, dict):
        raise error(f"{label} {export}: version {name!r} has no 'needs' object")
    for key, need in needs.items():
        if not isinstance(need, dict):
            raise error(f"{label} {export}: need {key!r} is not an object")
    return needs


def check_need(
    export: Path,
    label: str,
    error: type[Exception],
    key: str,
    need: Mapping[str, Any],
    text_fields: Sequence[str],
    list_field: str,
) -> None:
    """Refuse a need missing a text field, declaring another id, or with a bad link list.

    ``text_fields`` must all be strings and ``id`` must equal the need's key;
    ``list_field`` may be absent or null and otherwise must be a list of
    identifiers.
    """
    for name in text_fields:
        if not isinstance(need.get(name), str):
            raise error(f"{label} {export}: need {key!r} has no text field {name!r}")
    if need["id"] != key:
        raise error(f"{label} {export}: need {key!r} declares the id {need['id']!r}")
    links = need.get(list_field)
    if links is not None and not (
        isinstance(links, list) and all(isinstance(target, str) for target in links)
    ):
        raise error(
            f"{label} {export}: need {key!r} has a {list_field!r} that is not a list of identifiers"
        )
