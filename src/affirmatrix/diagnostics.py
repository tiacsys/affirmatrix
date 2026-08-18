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
finding travels in — a severity, the condition that was found, and the
subject it was found on — both required and non-empty, because a diagnostic
naming nothing is not a finding.
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
    """One finding: a severity, the condition found, and the subject it names.

    ``condition`` and ``subject`` are both required non-empty strings — a
    diagnostic that names no condition or no subject would be a severity with
    nothing to report, which is not a finding at all.
    """

    severity: Severity
    condition: str
    subject: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", Severity(self.severity))
        _require(self.condition, "condition")
        _require(self.subject, "subject")


__all__ = ["Diagnostic", "Severity"]
