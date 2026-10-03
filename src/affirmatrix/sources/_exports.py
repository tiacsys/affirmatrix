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
from collections.abc import Callable, Mapping, Sequence
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


def need_fault(
    key: str, need: Mapping[str, Any], text_fields: Sequence[str], list_field: str
) -> str | None:
    """The reason a need is misshapen, or ``None`` for a need that is well formed.

    ``text_fields`` must all be strings and ``id`` must equal the need's key;
    ``list_field`` may be absent or null and otherwise must be a list of
    identifiers. The first fault of the need is the one given.
    """
    for name in text_fields:
        if not isinstance(need.get(name), str):
            return f"need {key!r} has no text field {name!r}"
    if need["id"] != key:
        return f"need {key!r} declares the id {need['id']!r}"
    links = need.get(list_field)
    if links is not None and not (
        isinstance(links, list) and all(isinstance(target, str) for target in links)
    ):
        return f"need {key!r} has a {list_field!r} that is not a list of identifiers"
    return None


def check_needs(
    export: Path,
    label: str,
    error: type[Exception],
    needs: Mapping[str, Mapping[str, Any]],
    text_fields: Sequence[str],
    list_field: str,
    extra: Callable[[str, Mapping[str, Any]], str | None] = lambda key, need: None,
) -> None:
    """Refuse an export that holds misshapen needs, naming every one in one error.

    The error starts with a line that counts the misshapen needs, and one line
    for each follows, in the order of the export, so the same export always gives
    the same text. ``extra`` gives a reason that only one reader knows, for a need
    that has the shape the fields ask for but cannot be used.

    :implements: SEG-SREQ-351
    :implements: SEG-SREQ-352
    :implements: SEG-SREQ-353
    """
    faults = []
    for key, need in needs.items():
        fault = need_fault(key, need, text_fields, list_field) or extra(key, need)
        if fault is not None:
            faults.append(fault)
    if faults:
        raise error(itemized(f"{label} {export}: {len(faults)} need(s) are misshapen", faults))


def admitted(
    needs: Mapping[str, Mapping[str, Any]],
    types: frozenset[str] | None,
    need_ids: frozenset[str] | None,
    label: str,
    error: type[Exception],
) -> dict[str, Mapping[str, Any]]:
    """The needs that both settings admit, in the order of the export.

    A need is admitted when its type is one of ``types`` (where types are set)
    and its key is one of ``need_ids`` (where a list is set). Both filters apply
    before any need is checked, so a need outside them is never refused for its
    shape. Every identifier of the list that no admitted need carries is named,
    once, in one error: a listed identifier that names no need of the export, or
    a need that the types do not admit.

    :implements: SEG-SREQ-358
    :implements: SEG-SREQ-359
    :implements: SEG-SREQ-360
    :implements: SEG-SREQ-361
    :implements: SEG-SREQ-374
    :implements: SEG-SREQ-375
    """
    typed = {key: need for key, need in needs.items() if types is None or need.get("type") in types}
    if need_ids is None:
        return typed
    missing = sorted(name for name in need_ids if name not in typed)
    if missing:
        raise error(
            itemized(
                f"{label}: {len(missing)} listed need identifier(s) name no need to read",
                [
                    f"need {name!r} is not in the export or is not of a configured type"
                    for name in missing
                ],
            )
        )
    return {key: need for key, need in typed.items() if key in need_ids}
