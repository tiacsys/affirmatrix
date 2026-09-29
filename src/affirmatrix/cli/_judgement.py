"""A judgement's inputs, explicit, discovered, or refused (SEG-SREQ-105…113).

An affirmation's role, reason, and source revisions, and the package gate's
implementation revision, are each supplied one of three ways: given
explicitly, discovered under one checked rule, or refused when neither is
available. This module is where that rule lives, once, for every judgement
that depends on it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from affirmatrix.cli import _repository
from affirmatrix.config import Config
from affirmatrix.records import NodeRecord, RecordSource
from affirmatrix.sources.store import StoreError, StoreLoader


class JudgementError(Exception):
    """A judgement's inputs could not be resolved — explicit, discovered, or refused.

    Raised for a missing role or reason argparse itself would already
    refuse, for a dirty anchor a discovered revision cannot be recorded
    against, for an anchor with no repository and no explicit revision, and
    for a role outside a configured vocabulary. Every case is the command
    line's own request it could not judge (exit status 2).
    """


def endpoint_repository_name(node: NodeRecord) -> str | None:
    """The one repository name every named content hash of this node agrees on.

    ``None`` when the node's anchors do not all agree on one repository name
    — the would-be store's own anchors always do, since one node's content
    lives in one place — which reads the same as "no repository stands
    behind this anchor" (SEG-SREQ-110): either way a revision must be given
    explicitly.
    """
    names = {anchor.repository for anchor in node.content_anchors.values()}
    return next(iter(names)) if len(names) == 1 else None


def resolve_revision(
    node: NodeRecord, *, config: Config, given: str | None, label: str
) -> str:
    """One endpoint's source revision: given, discovered, or refused.

    :implements: SEG-SREQ-107
    :implements: SEG-SREQ-108
    :implements: SEG-SREQ-109
    :implements: SEG-SREQ-110

    ``given`` overrides discovery entirely when present, recorded exactly as
    given, neither discovered nor checked (SEG-SREQ-109). Otherwise, where
    the node's anchors name a repository the configuration maps
    (SEG-SREQ-107), the working tree's revision is discovered and the
    anchored paths checked clean before it is trusted (SEG-SREQ-108);
    lacking a mapped repository, a revision must be given explicitly
    (SEG-SREQ-110).
    """
    if given is not None:
        return given
    repository_name = endpoint_repository_name(node)
    repository_path = config.repository(repository_name) if repository_name is not None else None
    if repository_path is None:
        raise JudgementError(
            f"{label}: no repository is configured for this endpoint's anchor; "
            "a revision must be given explicitly (--revision)"
        )
    revision = _repository.discover_revision(repository_path)
    anchored_paths = [Path(anchor.path) for anchor in node.content_anchors.values()]
    cleanliness = _repository.check_clean(repository_path, anchored_paths)
    if not cleanliness.clean:
        raise JudgementError(
            f"{label}: the content at {', '.join(cleanliness.dirty_paths)} differs from what "
            f"is committed at {revision}; refusing to record a discovered revision"
        )
    return str(revision)


def check_role(role: str, config: Config) -> None:
    """Refuse a role outside a configured vocabulary.

    :implements: SEG-SREQ-113

    Where no vocabulary is configured, every role is accepted — enforcement
    is opt-in, by configuring one at all.
    """
    if config.roles is not None and role not in config.roles:
        raise JudgementError(
            f"role {role!r} is outside the configured role vocabulary: "
            f"{', '.join(sorted(config.roles))}"
        )


def recover_before_content(node: NodeRecord, revision: str, config: Config) -> bytes | None:
    """The bytes an endpoint's anchor names at a revision, for display only.

    :implements: SEG-SREQ-111

    ``None`` when no repository stands behind the anchor, or the anchor
    carries more than one path — before-content recovery is a single
    ``git show``, and an endpoint with a location this adapter cannot
    resolve to one repository and one path is not this function's to guess.
    """
    repository_name = endpoint_repository_name(node)
    if repository_name is None:
        return None
    repository_path = config.repository(repository_name)
    if repository_path is None:
        return None
    paths = {anchor.path for anchor in node.content_anchors.values()}
    if len(paths) != 1:
        return None
    return _repository.read_before_content(repository_path, revision, Path(next(iter(paths))))


def resolve_gate_revision(config: Config, *, given: str | None) -> str:
    """The proof gate's implementation revision, under the same rule as an endpoint's.

    :implements: SEG-SREQ-112

    ``given`` overrides discovery; otherwise the configured implementation
    repository's revision is discovered and the whole repository checked
    clean, or a revision must be given explicitly when none is configured.
    """
    if given is not None:
        return given
    repository_path = config.implementation_repository()
    if repository_path is None:
        raise JudgementError(
            "no implementation repository is configured; a revision must be given "
            "explicitly (--revision)"
        )
    revision = _repository.discover_revision(repository_path)
    cleanliness = _repository.check_clean(repository_path, [Path(".")])
    if not cleanliness.clean:
        raise JudgementError(
            f"the implementation repository is dirty at {', '.join(cleanliness.dirty_paths)}; "
            f"refusing to record a discovered revision at {revision}"
        )
    return str(revision)


def resolve_current(current: str | None, config: Config) -> RecordSource:
    """The producer supplying the current stream: given, configured, or refused.

    :implements: SEG-SREQ-142

    A verb deriving from both record sources refuses, as a request it could
    not judge, when it is given no current stream and none is configured.
    ``current`` overrides the configured producer root when given; absent
    both, or naming a root that is not a would-be store, the request cannot
    be judged — both read as the same "could not judge" refusal to every
    caller, so both are folded into one exception here rather than asking
    each call site to catch two.
    """
    root = Path(current) if current is not None else config.producer_root
    if root is None:
        raise JudgementError(
            "no producer is available: give --current or configure producer.root"
        )
    try:
        return StoreLoader(root=root)
    except StoreError as error:
        raise JudgementError(str(error)) from error


def resolve_evaluation_date(given: str | None) -> date:
    """The date a waiver's expiry is judged against, given or defaulting to today."""
    return date.fromisoformat(given) if given is not None else date.today()


def resolve_timestamp(given: str | None) -> datetime:
    """The snapshot timestamp, given or defaulting to now, always timezone-aware UTC."""
    if given is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(given)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


__all__ = [
    "JudgementError",
    "check_role",
    "endpoint_repository_name",
    "recover_before_content",
    "resolve_current",
    "resolve_evaluation_date",
    "resolve_gate_revision",
    "resolve_revision",
    "resolve_timestamp",
]
