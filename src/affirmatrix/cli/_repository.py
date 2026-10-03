"""The read-only repository operations the command-line adapter may perform.

ADR-0010 narrows "the tool never runs git" to the library and the affirmation
store: the command-line adapter may read repository state, and this is the
one module where that happens. ADR-0015 adds a fourth read. Four reads, no
more:

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
* **The history of the case** — the commit that recorded a review event, and
  the facts of that commit (:func:`find_recording_commit`). The other three
  reads are in content repositories. This one is in the repository of the
  case. It needs three helpers: :func:`check_own_repository` (the case is the
  top level of a repository), :func:`has_commits` (the history is not empty)
  and :func:`is_shallow`.

The adapter never writes: no add, no commit, no branch, no checkout, no
stash, no edit to any tracked file. Every git call runs with optional locks
off (``--no-optional-locks``). Without it, ``git status`` refreshes the stat
data in the index of the repository, and that is a write. With it, git
compares the content of a file whose stat data is out of date, and gives the
same answer more slowly.

Every git call also runs without the seven variables that name a repository
or a part of one: ``GIT_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``,
``GIT_OBJECT_DIRECTORY``, ``GIT_ALTERNATE_OBJECT_DIRECTORIES``,
``GIT_COMMON_DIR`` and ``GIT_NAMESPACE``. With one of them set, git would
answer from another repository than the one at the path (SEG-SREQ-332). The
rest of the environment stays: ``PATH``, ``GIT_CEILING_DIRECTORIES`` and the
``GIT_CONFIG_*`` settings are the operator's.

A read over many paths is made in parts. One call of git takes at most a
number of bytes of path arguments, and at most :data:`PATHS_PER_CALL` paths.
The byte bound decides on a real machine. The count is a large safety cap that
a test can lower. The byte bound comes from the machine: half
of ``SC_ARG_MAX`` minus the size of the environment that git gets, with each
argument counted as its bytes, one end byte and one pointer. It never falls
below :data:`PATH_BYTES_FLOOR` (64 KiB), which is half of the 128 KiB that Linux
promises, and that value is used when the system gives no limit. A system
refuses a call whose arguments are too long, and a count alone does not keep a
call short, because long paths make a long call. The answers of the parts are joined, and
they equal the answer of one call. A part that fails fails the whole read, so
the repository counts as one that cannot be read; the answer of the parts that
did succeed is never used alone. Every git failure — the binary absent,
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

import os
import re
import subprocess
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")

#: The most path arguments in one call of git. This is a safety cap and a seam
#: for tests: the byte bound (:func:`_byte_bound`) decides on a real machine,
#: and a test lowers this value to force parts. Read when a read starts.
PATHS_PER_CALL = 100000

#: The least number of bytes of path arguments in one call of git. Linux
#: promises at least 128 KiB for the arguments and the environment of a
#: program together. Half of that leaves room for the environment and for the
#: fixed arguments. The real bound is larger on most machines
#: (see :func:`_byte_bound`).
PATH_BYTES_FLOOR = 64 * 1024

#: The bytes that the system counts for a pointer to one argument.
_POINTER_BYTES = 8

#: The names that point git at a repository, or at a part of one. They are
#: removed from the environment of every call (SEG-SREQ-333).
_REPOSITORY_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
)


class RepositoryError(Exception):
    """One of the repository reads could not be carried out.

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


def _run(repo_path: Path, *args: str, accept: Collection[int] = (0,)) -> bytes:
    """Run one read-only git subcommand under ``repo_path`` and return its raw stdout.

    :implements: SEG-SREQ-115
    :implements: SEG-SREQ-116

    Optional locks are off for every call, so no read refreshes the index.
    The environment of the call is the one of the process without the seven
    names in ``_REPOSITORY_VARIABLES``, so git finds the repository from
    ``repo_path`` alone. The only place ``subprocess`` runs in this package.
    A git failure of any kind becomes one :class:`RepositoryError`; nothing above this function
    ever sees a ``subprocess`` exception. An exit status in ``accept`` is an
    answer and not a failure: ``git rev-parse --verify --quiet`` uses status 1
    to say that a name does not resolve.
    """
    try:
        completed = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=repo_path,
            check=False,
            capture_output=True,
            env=_git_environment(),
        )
    except FileNotFoundError as error:
        raise RepositoryError(
            "git is not on PATH; the adapter's repository reads need it"
        ) from error
    except OSError as error:
        raise RepositoryError(f"git could not run in {repo_path}: {error}") from error
    if completed.returncode not in accept:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryError(f"git {' '.join(args)} failed in {repo_path}: {stderr}")
    return completed.stdout


def _git_environment() -> dict[str, str]:
    """The environment of the process, without the names that point git at a repository."""
    return {name: value for name, value in os.environ.items() if name not in _REPOSITORY_VARIABLES}


def _argument_cost(text: str) -> int:
    """The bytes that one argument or one environment entry takes in a call."""
    return len(os.fsencode(text)) + 1 + _POINTER_BYTES


def _byte_bound() -> int:
    """The most bytes of path arguments for one call of git, on this machine.

    Half of what the system leaves for arguments after the environment that git
    gets: ``(SC_ARG_MAX - environment) // 2``, never below
    :data:`PATH_BYTES_FLOOR`. The floor is used when the system gives no limit
    (an error or -1). Computed at each call, because the environment can change.
    """
    try:
        limit = os.sysconf("SC_ARG_MAX")
    except (ValueError, OSError):
        return PATH_BYTES_FLOOR
    if limit <= PATH_BYTES_FLOOR:
        return PATH_BYTES_FLOOR
    environment = sum(
        _argument_cost(f"{name}={value}") for name, value in _git_environment().items()
    )
    return max(PATH_BYTES_FLOOR, (limit - environment) // 2)


def _parts(names: Sequence[str]) -> Iterator[Sequence[str]]:
    """Split ``names`` into runs, in order, that one call of git can take.

    A run holds at most :data:`PATHS_PER_CALL` names and at most
    the bytes that :func:`_byte_bound` gives. Every name is in exactly one run.
    The limits are read here, at call time. A name that alone exceeds the byte
    limit makes a run of its own.
    """
    bound = _byte_bound()
    start = 0
    size = 0
    for index, name in enumerate(names):
        cost = _argument_cost(name)
        if index > start and (index - start >= PATHS_PER_CALL or size + cost > bound):
            yield names[start:index]
            start, size = index, 0
        size += cost
    if start < len(names):
        yield names[start:]


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
    case this check exists to catch. Many paths are read in parts, and a part
    that fails fails the read.
    """
    if not paths:
        return Cleanliness(clean=True, dirty_paths=())
    dirty = tuple(
        sorted(
            name
            for part in _parts([str(path) for path in paths])
            for name in _dirty_paths(_run(repo_path, "status", "--porcelain=v1", "-z", "--", *part))
        )
    )
    return Cleanliness(clean=not dirty, dirty_paths=dirty)


def committed_paths(repo_path: Path, revision: str, paths: Sequence[Path]) -> frozenset[str]:
    """The subset of ``paths`` that ``revision`` holds, as repository-relative POSIX names.

    ``git ls-tree -r --name-only -z <revision> -- <paths>``, in parts when the
    paths are many (see the module docstring). Used with :func:`check_clean` to
    decide that a repository holds the committed content at every path an anchor
    names. A path the revision never held is missing from the answer.
    """
    if not paths:
        return frozenset()
    held: set[str] = set()
    for part in _parts([path.as_posix() for path in paths]):
        output = _run(repo_path, "ls-tree", "-r", "--name-only", "-z", revision, "--", *part)
        held.update(name for name in output.decode("utf-8").split("\0") if name)
    return frozenset(held)


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


@dataclass(frozen=True, slots=True)
class Person:
    """A name, an e-mail address and a date, as a commit records them.

    The date is the ISO 8601 form with the offset that ``git log
    --format=%cI`` gives.
    """

    name: str
    email: str
    date: str


@dataclass(frozen=True, slots=True)
class RecordingCommit:
    """The facts of the commit that recorded a review event.

    Every field is text that the commit holds, as written. The committer, the
    author and the sign-offs are what a person set when they made the commit.
    The tool does not check them. ``signature`` is the word for the status that
    git gives (see :data:`SIGNATURE_WORDS`). The tool runs no cryptography.
    """

    commit: Revision
    subject: str
    committer: Person
    author: Person
    signed_off_by: tuple[str, ...]
    signature: str


#: The word for each status letter of ``git log --format=%G?``. The two expired
#: letters, an expired signature and an expired key, share one word.
SIGNATURE_WORDS = {
    "N": "none",
    "G": "good",
    "B": "bad",
    "U": "unknownValidity",
    "X": "expired",
    "Y": "expired",
    "R": "revoked",
    "E": "cannotCheck",
}

# One field of each kind, separated by NUL. A commit message cannot hold a NUL,
# so no field can run into the next one. The sign-offs travel as one field, joined
# by the unit separator.
_FORMAT_FIELDS = (
    "%H",
    "%cn",
    "%ce",
    "%cI",
    "%an",
    "%ae",
    "%aI",
    "%G?",
    "%s",
    "%(trailers:key=Signed-off-by,valueonly,unfold,separator=%x1f)",
)
_FORMAT = "%x00".join(_FORMAT_FIELDS)
_ERE_SPECIAL = frozenset("\\.[]{}()*+?^$|")


def check_own_repository(case_root: Path) -> None:
    """Make sure that ``case_root`` is the top level of a repository of its own (ADR-0015).

    :implements: SEG-SREQ-301

    ``git rev-parse --show-toplevel`` must name the case root. A worktree of
    another repository passes, because its top level is the worktree. A case
    that lies inside another repository fails: the history of the enclosing
    repository says nothing about the case. Git is never told where the
    repository is (no ``--git-dir``, no ``-C`` into a parent). Raises
    :class:`RepositoryError` when the case is not a repository, or when its
    top level is another directory.
    """
    top_level = _run(case_root, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace")
    if Path(top_level.rstrip("\n")).resolve() != case_root.resolve():
        raise RepositoryError(
            f"{case_root} is not the top level of a repository: it lies inside {top_level.strip()}"
        )


def has_commits(case_root: Path) -> bool:
    """Whether the history of the case holds at least one commit (ADR-0015).

    ``git rev-parse --verify --quiet HEAD``. Status 1 with no output means that
    ``HEAD`` names no commit yet, as in a repository that was just created. Any
    other failure is a :class:`RepositoryError`.
    """
    return bool(_run(case_root, "rev-parse", "--verify", "--quiet", "HEAD", accept=(0, 1)).strip())


def is_shallow(case_root: Path) -> bool:
    """Whether the history of the case is cut short, as in a clone made with ``--depth``."""
    answer = _run(case_root, "rev-parse", "--is-shallow-repository").decode("ascii").strip()
    if answer not in {"true", "false"}:
        raise RepositoryError(f"git does not say whether {case_root} is shallow: {answer!r}")
    return answer == "true"


def find_recording_commit(
    case_root: Path, document: PurePosixPath, event_identifier: str
) -> RecordingCommit | None:
    """The earliest commit whose events document holds ``event_identifier``, with its facts.

    :implements: SEG-SREQ-293
    :implements: SEG-SREQ-294
    :implements: SEG-SREQ-295
    :implements: SEG-SREQ-296
    :implements: SEG-SREQ-297
    :implements: SEG-SREQ-299

    The search is ``git log --reverse`` over ``document`` with a pickaxe
    regular expression. The expression matches ``"id"`` and the identifier
    together, as a JSON member, with white space allowed between the parts. The
    closing quote alone is not a boundary, because a free-text reason can end
    with the identifier of another event. The first commit that git lists is the
    earliest commit that adds the text. A commit that created the document is
    not the answer when a later commit added the event. The result is ``None``
    when no commit adds the event.

    A second call reads the facts of that one commit. So the signature check,
    which can start a program, runs for one commit only. The identity is as the
    commit records it: name, e-mail address and date, for the committer and for
    the author. No mailmap is applied (``--no-mailmap``). ``--no-show-signature``
    keeps the signature text that ``log.showSignature`` adds out of the output.
    """
    found = _run(
        case_root,
        "log",
        "--reverse",
        "--format=%H",
        "--no-textconv",
        "--pickaxe-regex",
        f"-S{_identifier_pattern(event_identifier)}",
        "--",
        document.as_posix(),
    )
    lines = found.decode("ascii").split()
    if not lines:
        return None
    commit = Revision(lines[0])
    record = _run(
        case_root,
        "show",
        "--no-patch",
        "--no-mailmap",
        "--no-show-signature",
        f"--format=format:{_FORMAT}",
        commit.value,
        "--",
    )
    fields = record.decode("utf-8", errors="replace").split("\0")
    if len(fields) != len(_FORMAT_FIELDS) or fields[0] != commit.value:
        raise RepositoryError(f"git gave an unexpected record for the commit {commit}")
    _, committer_name, committer_email, committer_date, *rest = fields
    author_name, author_email, author_date, letter, subject, trailers = rest
    if letter not in SIGNATURE_WORDS:
        raise RepositoryError(f"git gave the unknown signature status {letter!r} for {commit}")
    return RecordingCommit(
        commit=commit,
        subject=subject,
        committer=Person(committer_name, committer_email, committer_date),
        author=Person(author_name, author_email, author_date),
        signed_off_by=tuple(item for item in trailers.strip("\n").split("\x1f") if item),
        signature=SIGNATURE_WORDS[letter],
    )


def _identifier_pattern(identifier: str) -> str:
    """The pickaxe pattern that matches ``identifier`` as the value of an ``id`` member.

    A POSIX extended regular expression. The pattern escapes the special
    characters with a backslash and no other character. So it does not depend
    on how a regular expression library reads a backslash before an ordinary
    character.
    """
    escaped = "".join(f"\\{one}" if one in _ERE_SPECIAL else one for one in identifier)
    return f'"id"[[:space:]]*:[[:space:]]*"{escaped}"'


__all__ = [
    "PATHS_PER_CALL",
    "PATH_BYTES_FLOOR",
    "SIGNATURE_WORDS",
    "Cleanliness",
    "Person",
    "RecordingCommit",
    "RepositoryError",
    "Revision",
    "check_clean",
    "check_own_repository",
    "committed_paths",
    "discover_revision",
    "find_recording_commit",
    "has_commits",
    "is_shallow",
    "read_before_content",
]
