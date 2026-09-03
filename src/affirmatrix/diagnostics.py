"""Shared internal — the severity model of the error-handling contract.

Not a component and never a requirement subject. Error, warning and info, and
the diagnostic record they travel in: an error blocks both committing and
generating an evidence package, a warning blocks the package only, and info is
reported without blocking anything. The components that decide *which*
condition earns which severity own those requirements; this module owns only
the vocabulary they share.

:class:`Severity` carries the blocking meaning as two properties,
``blocks_commit`` and ``blocks_package``, so that meaning lives in exactly one
place: no gate re-derives the blocking table from the three names, and no two
gates can read it two different ways. :class:`Diagnostic` is the record one
finding travels in — a severity, the condition that was found, the subject it
was found on, and an optional occurrence detail. ``condition`` and ``subject``
are required and non-empty, because a diagnostic naming nothing is not a
finding; ``detail`` is neither, because not every condition varies by
occurrence and a component with nothing to add should not have to invent
something to say.

Keeping which conditions exist out of this module is deliberate, not an
oversight. A closed condition vocabulary is a claim about *what one
component's gate can find* — its own requirement, its own set — and this
module would stop being a leaf the moment it declared one. So ``condition``
stays a plain string here: whichever component owns a gate's conditions
declares its own closed set (an enum of its own) and only ever constructs a
``Diagnostic`` from a member of it; this module's part is the record shape
and the severity table both share, nothing about what a condition may say.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """The three severities of the error-handling contract, and what each blocks.

    Ordered here from most to least severe, though nothing relies on that
    order: each severity answers ``blocks_commit`` and ``blocks_package`` for
    itself, so a caller never has to know where a severity sits relative to
    the others to know what it blocks.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def blocks_commit(self) -> bool:
        """Whether a condition at this severity blocks committing.

        True only for :attr:`ERROR` — the tightest gate, reserved for
        conditions a warning or an info finding is not severe enough to stop.
        """
        return self is Severity.ERROR

    @property
    def blocks_package(self) -> bool:
        """Whether a condition at this severity blocks generating a package.

        True for :attr:`ERROR` and :attr:`WARNING`; :attr:`INFO` never blocks
        anything — it is reported and nothing more.
        """
        return self in (Severity.ERROR, Severity.WARNING)


def _require(value: str, what: str) -> str:
    if not value:
        raise ValueError(f"a diagnostic needs a non-empty {what}")
    return value


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One finding: a severity, the condition found, the subject it names, and
    an optional occurrence detail.

    ``condition`` and ``subject`` are both required non-empty strings — a
    diagnostic that names no condition or no subject would be a severity with
    nothing to report, which is not a finding at all. ``detail`` carries
    whatever varies from one occurrence of the same condition to the next —
    which state an edge is in, say — kept apart from ``condition`` so the
    condition itself stays one of a closed, occurrence-independent set;
    empty is allowed, because not every condition has anything occurrence-
    specific to add.
    """

    severity: Severity
    condition: str
    subject: str
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", Severity(self.severity))
        _require(self.condition, "condition")
        _require(self.subject, "subject")


__all__ = ["Diagnostic", "Severity"]
