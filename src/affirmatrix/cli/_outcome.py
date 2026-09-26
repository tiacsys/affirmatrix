"""The shared outcome vocabulary every verb reports through (SEG-SREQ-095…098).

One exit-status vocabulary of three members, one way to render a refusal
with the report the library returned, and one machine-readable rendering
that structures the same report a human-readable one presents. The per-verb
corner cases — which of the three statuses a given library result maps to —
are each verb's own claim and live with that verb's handler; what is shared
is the vocabulary itself and the mechanics of rendering it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import TextIO

#: The command's positive verdict.
POSITIVE = 0
#: The command's negative verdict, acted on.
NEGATIVE = 1
#: The command could not judge the request at all.
INDETERMINATE = 2

_STATUSES = frozenset({POSITIVE, NEGATIVE, INDETERMINATE})


def exit_for(status: int) -> int:
    """One of the three exit statuses, and nothing else.

    :implements: SEG-SREQ-095
    :implements: SEG-SREQ-096

    Every handler funnels its final decision through this one function
    rather than returning a bare literal scattered through the package, so
    the vocabulary stays exactly the three members it is ever a member of.
    """
    if status not in _STATUSES:
        raise ValueError(f"{status} is not one of the three exit statuses (0, 1, 2)")
    return status


def render_json(data: Mapping[str, object], stream: TextIO | None = None) -> None:
    """Print a structured report, stable keys, stdlib ``json``.

    :implements: SEG-SREQ-098

    Sorted keys and a fixed indent: a machine-readable rendering that
    structures the same report the human-readable one presents, and is
    itself reproducible byte for byte across two runs over the same report.
    ``stream`` defaults to whichever object ``sys.stdout`` names at call
    time, not at import time — a default parameter value is bound once,
    which would otherwise print past a test's own captured stream.
    """
    print(json.dumps(data, indent=2, sort_keys=True), file=stream or sys.stdout)


def render_refusal(message: str, *, as_json: bool, stream: TextIO | None = None) -> None:
    """Render a verb's refusal with the library's own report, not a bare status.

    :implements: SEG-SREQ-097

    ``message`` is text the library itself produced — a ``GraphError``'s
    message, the recorder's reason per edge, ``GenerationRefused``'s
    diagnostics rendered — never a rewording of it.
    """
    if as_json:
        render_json({"error": message}, stream)
    else:
        print(message, file=stream if stream is not None else sys.stdout)


def hash_display(digest_hex: str, *, verbose: bool) -> str:
    """A digest truncated for display, or shown in full under ``-v``.

    Truncated form: the first four and last four hex characters joined by
    an ellipsis (``abcd…ef12``) — enough to eyeball a change, never
    enough to be mistaken for the whole value.
    """
    if verbose or len(digest_hex) <= 10:
        return digest_hex
    return f"{digest_hex[:4]}…{digest_hex[-4:]}"


__all__ = [
    "INDETERMINATE",
    "NEGATIVE",
    "POSITIVE",
    "exit_for",
    "hash_display",
    "render_json",
    "render_refusal",
]
