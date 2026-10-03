"""The three read-only repository operations the command-line adapter may perform.

ADR-0010 narrows "the tool never runs git" to the library and the affirmation
store: the command-line adapter may read repository state, and this is the
one module where that happens. Three reads, no more:

* **Revision discovery** — the working tree's current revision
  (:func:`discover_revision`, ``git rev-parse HEAD``).
* **Cleanliness of the anchored paths** — whether the paths an endpoint's
  anchors name match their committed content (:func:`check_clean`,
  ``git status --porcelain=v1 -z`` over exactly those paths, not the whole
  tree). A path that was never committed is not clean either, but ``git
  status`` is silent about a path it has never seen. :func:`committed_paths`
  (``git ls-tree``) names the paths a revision holds, so the verbs that
  record an extraction revision can tell the two cases apart.
* **Before-content recovery** — the bytes a path held at a given revision,
  for display only (:func:`read_before_content`, ``git show <rev>:<path>``).

The adapter never writes: no add, no commit, no branch, no checkout, no
stash, no edit to any tracked file. Every git call runs with optional locks
off (``--no-optional-locks``). Without it, ``git status`` refreshes the stat
data in the index of the repository, and that is a write. With it, git
compares the content of a file whose stat data is out of date, and gives the
same answer more slowly. Every git failure — the binary absent,
the path not a repository, a bad revision — becomes one
:class:`RepositoryError`, so a handler never has to see a
``subprocess.CalledProcessError`` or import ``subprocess`` itself; this is
the only module in the package that does.

Cleanliness is checked with ``git status --porcelain=v1``, not
``git diff --quiet HEAD``: the latter has nothing to diff an untracked file
against and would call it clean, while an anchor pointing at content that was
never committed is exactly the case a discovered revision must not be
recorded against (SEG-SREQ-108). The ``-z`` form is used and its output split
on NUL rather than parsed line by line, because the line form quotes a path
containing a space or other unusual byte — exactly the kind of anchored path
this check must not misread.

A discovered revision is validated by :class:`Revision` on construction — the
one check that a value this module read out of git actually looks like a
revision. A revision the operator gives explicitly is never wrapped here and
is never validated by this module at all: it is recorded exactly as given,
and a malformed one is refused where every recorded revision is refused, at
the case's own schema (SEG-SREQ-109).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")


class RepositoryError(Exception):
    """One of the three repository reads could not be carried out.

    Raised for every way a read can fail — ``git`` absent from ``PATH``, the
    given path not a repository, a revision or a path git does not know —
    so a caller catches one type rather than a menagerie of
    ``subprocess`` and ``OSError`` variants.
    """


@dataclass(frozen=True, slots=True)
class Revision:
    """A source revision discovered from a repository's working tree.

    Validated on construction against the same shape the case's own schema
    pins for a recorded revision (a git SHA-1 or SHA-256 hex string):
    :func:`discover_revision` is the only producer, so this is the one place
    a value read out of git is checked to actually look like a revision
    before it travels any further. A revision the operator gives explicitly
    never passes through here — it is recorded as given, unvalidated by this
    adapter, and refused instead by the case's schema if it is malformed.
    """

    value: str

    def __post_init__(self) -> None:
        if not _REVISION_PATTERN.fullmatch(self.value):
            raise RepositoryError(
                f"{self.value!r} is not a revision this adapter can discover: expected 40 or "
                "64 lowercase hex characters"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Cleanliness:
    """Whether every path an endpoint's anchors name matches its committed content.

    ``dirty_paths`` names exactly the paths ``git status`` reported as
    differing or untracked, sorted — named, not merely counted, because a
    refusal built from this must name them (SEG-SREQ-108).
    """

    clean: bool
    dirty_paths: tuple[str, ...]


def _run(repo_path: Path, *args: str) -> bytes:
    """Run one read-only git subcommand under ``repo_path`` and return its raw stdout.

    :implements: SEG-SREQ-115

    Optional locks are off for every call, so no read refreshes the index.
    The only place ``subprocess`` runs in this package. A git failure of any
    kind becomes one :class:`RepositoryError`; nothing above this function
    ever sees a ``subprocess`` exception.
    """
    try:
        completed = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise RepositoryError(
            "git is not on PATH; the adapter's repository reads need it"
        ) from error
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryError(f"git {' '.join(args)} failed in {repo_path}: {stderr}") from error
    return completed.stdout


def discover_revision(repo_path: Path) -> Revision:
    """The working tree's current revision (ADR-0010, point 1).

    ``git rev-parse HEAD``, each endpoint resolved against its own
    repository so a review event's two revision fields are filled without a
    caller supplying either by hand.
    """
    return Revision(_run(repo_path, "rev-parse", "HEAD").decode("ascii").strip())


def check_clean(repo_path: Path, paths: Sequence[Path]) -> Cleanliness:
    """Whether every one of ``paths`` matches its committed content (ADR-0010, point 2).

    ``git status --porcelain=v1 -z`` over exactly the anchored paths, never
    the whole tree: a change elsewhere in the working tree must never refuse
    an affirmation whose endpoints do not touch it. An anchored path git has
    never seen committed — untracked — is reported dirty too: ``git diff
    --quiet`` alone would call it clean, having nothing to diff against, and
    an anchor pointing at content that was never committed is exactly the
    case this check exists to catch.
    """
    if not paths:
        return Cleanliness(clean=True, dirty_paths=())
    output = _run(
        repo_path, "status", "--porcelain=v1", "-z", "--", *(str(path) for path in paths)
    )
    dirty = tuple(sorted(_dirty_paths(output)))
    return Cleanliness(clean=not dirty, dirty_paths=dirty)


def committed_paths(repo_path: Path, revision: str, paths: Sequence[Path]) -> frozenset[str]:
    """The subset of ``paths`` that ``revision`` holds, as repository-relative POSIX names.

    ``git ls-tree -r --name-only -z <revision> -- <paths>``: one call for all
    the paths. Used with :func:`check_clean` to decide that a repository holds
    the committed content at every path an anchor names. A path the
    revision never held is missing from the answer.
    """
    if not paths:
        return frozenset()
    output = _run(
        repo_path,
        "ls-tree",
        "-r",
        "--name-only",
        "-z",
        revision,
        "--",
        *(path.as_posix() for path in paths),
    )
    return frozenset(name for name in output.decode("utf-8").split("\0") if name)


def _dirty_paths(output: bytes) -> list[str]:
    """Every path named by a NUL-separated ``git status --porcelain=v1 -z`` report.

    Splitting on NUL rather than parsing line by line is what keeps a path
    containing a space, or any other byte the line form would quote, intact
    — an anchored path is exactly the kind of caller-supplied name this
    check must not misread. An entry whose status is a rename or a copy ('R'
    or 'C' in either column) carries a second NUL-terminated field, the
    original path, immediately after its own; that field is skipped rather
    than read as a further entry, since it is never one of the anchored
    paths this query named. Not expected for a query scoped to specific
    paths — git reports a rename only when both the old and new names are
    otherwise in scope — but handled rather than assumed away.
    """
    fields = output.decode("utf-8").split("\0")
    dirty: list[str] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        if not field:
            index += 1
            continue
        status, path = field[:2], field[3:]
        dirty.append(path)
        if "R" in status or "C" in status:
            index += 1  # the rename/copy's original-path field, not an entry
        index += 1
    return dirty


def read_before_content(repo_path: Path, revision: str, path: Path) -> bytes:
    """The bytes ``path`` held at ``revision``, for display only (ADR-0010, point 3).

    ``git show <revision>:<path>``. ``path`` is relative to ``repo_path``,
    the same path an anchor names. The adapter never checks this content out
    or writes it anywhere; it is fetched once, rendered, and discarded.
    """
    return _run(repo_path, "show", f"{revision}:{path.as_posix()}")


__all__ = [
    "Cleanliness",
    "RepositoryError",
    "Revision",
    "check_clean",
    "committed_paths",
    "discover_revision",
    "read_before_content",
]
