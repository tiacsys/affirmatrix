"""The extraction revision rule of the command-line adapter (ADR-0016).

A node record can carry the revision of each repository at which the content
behind its hashes was read. The library and the store hold that map as a
value. This module is where the adapter decides what the map holds, for the
two verbs that write node records: ``case sync`` and ``edge affirm``.

The revision of a repository *can be discovered* for a node when the
repository is configured and can be read, and holds the committed content at
every path the node's anchors name in it. Three reads give this
(:mod:`affirmatrix.cli._repository`): the revision, the paths that differ from
the commit, and the paths the commit holds. Each repository is read once for
each run, for all the paths of all the nodes the run writes.

For each repository that a node's anchors name, the rule is:

* The content hashes equal those the case holds for the node: keep the held
  revision. If the case holds none, record the discovered one.
* The content hashes differ, or the case holds no record of the node: record
  the discovered revision. Never keep the held one: a revision next
  to a hash it did not give is false.
* The revision cannot be discovered: record none, and count the node.

A revision for a repository that the anchors do not name is never kept. A
revision that the operator gives on the command line is never an input here:
it is an assertion, not a checked fact.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from affirmatrix.cli import _repository
from affirmatrix.config import Config
from affirmatrix.records import NodeRecord


@dataclass(frozen=True, slots=True)
class RepositoryState:
    """What one read of a repository gave: its revision, and the paths that cannot back it.

    ``unusable`` holds every anchored path that differs from the commit or that
    the commit does not hold, as repository-relative POSIX names.
    """

    revision: str
    unusable: frozenset[str]


@dataclass(frozen=True, slots=True)
class Stamped:
    """Node records with their extraction revisions, and the count of records with none.

    ``missing`` maps each repository name to the number of records written
    without a revision for it. It holds no repository with a count of zero.
    """

    nodes: tuple[NodeRecord, ...]
    missing: Mapping[str, int]


def _anchored_paths(node: NodeRecord, repository: str) -> frozenset[str]:
    return frozenset(
        Path(anchor.path).as_posix()
        for anchor in node.content_anchors.values()
        if anchor.repository == repository
    )


def _repositories(node: NodeRecord) -> frozenset[str]:
    return frozenset(anchor.repository for anchor in node.content_anchors.values())


def read_repositories(nodes: Iterable[NodeRecord], config: Config) -> dict[str, RepositoryState]:
    """Read each repository the nodes name once, and keep the ones that can be read.

    A repository that is not configured, is not a git repository, or cannot be
    read is left out. For the rule this is the same as a revision that cannot be
    discovered.
    """
    anchored: dict[str, set[str]] = {}
    for node in nodes:
        for repository in _repositories(node):
            anchored.setdefault(repository, set()).update(_anchored_paths(node, repository))
    states: dict[str, RepositoryState] = {}
    for repository, paths in sorted(anchored.items()):
        location = config.repository(repository)
        if location is None:
            continue
        ordered = [Path(path) for path in sorted(paths)]
        try:
            revision = str(_repository.discover_revision(location))
            dirty = _repository.check_clean(location, ordered).dirty_paths
            held = _repository.committed_paths(location, revision, ordered)
        except _repository.RepositoryError:
            continue
        states[repository] = RepositoryState(revision, frozenset(dirty) | (paths - held))
    return states


def discovered_revision(
    node: NodeRecord, repository: str, states: Mapping[str, RepositoryState]
) -> str | None:
    """The revision of ``repository`` for ``node``, or ``None`` when it cannot be discovered."""
    state = states.get(repository)
    if state is None or _anchored_paths(node, repository) & state.unusable:
        return None
    return state.revision


def extraction_revisions(
    node: NodeRecord, held: NodeRecord | None, states: Mapping[str, RepositoryState]
) -> dict[str, str]:
    """The extraction revisions ``node`` is written with, by the rule of this module."""
    unchanged = held is not None and dict(held.content_hashes) == dict(node.content_hashes)
    revisions: dict[str, str] = {}
    for repository in sorted(_repositories(node)):
        kept = held.extracted_from.get(repository) if held is not None and unchanged else None
        revision = kept or discovered_revision(node, repository, states)
        if revision is not None:
            revisions[repository] = revision
    return revisions


def stamp(nodes: Iterable[NodeRecord], held: Mapping[str, NodeRecord], config: Config) -> Stamped:
    """Give each node its extraction revisions, and count the records left without one.

    :implements: SEG-SREQ-306
    :implements: SEG-SREQ-307
    :implements: SEG-SREQ-308
    :implements: SEG-SREQ-309
    :implements: SEG-SREQ-327

    ``held`` holds the node records the case holds, by local identifier. Read
    them before the write: the rule compares with what the case holds now.
    """
    listed = list(nodes)
    states = read_repositories(listed, config)
    missing: Counter[str] = Counter()
    stamped: list[NodeRecord] = []
    for node in listed:
        revisions = extraction_revisions(node, held.get(node.local_id), states)
        missing.update(_repositories(node) - revisions.keys())
        stamped.append(replace(node, extracted_from=revisions))
    return Stamped(tuple(stamped), dict(sorted(missing.items())))


def report(missing: Mapping[str, int]) -> None:
    """Print one line for each repository that has records written without a revision."""
    for repository, count in missing.items():
        print(f"no extraction revision: {repository}: {count} node records")


__all__ = [
    "RepositoryState",
    "Stamped",
    "discovered_revision",
    "extraction_revisions",
    "read_repositories",
    "report",
    "stamp",
]
