"""Shared helpers for the specifications of who recorded an affirmation.

This module is the one place that names the interface the specifications call:
the JSON key and the shape of the provenance of an edge, the status words, and
the labels of the text report. When the final names differ, this module changes
and no test does.

Every fixture is built by the test, inside ``tmp_path``. A case is a directory
that the library and ``edge affirm`` fill. The test makes it a git repository
with ``git init``, and it makes every commit, as a person makes a store act.
No test reads a real case. A test never asks the code under test for an expected
value. It reads the value from the repository with git or from the case with the
standard library.

Git is isolated from the machine of the test. :func:`isolate` points git at no
global or system configuration, removes every variable that names a repository,
and sets ``GIT_CEILING_DIRECTORIES`` to the parent of ``tmp_path``. So git cannot
climb into a checkout that holds the temporary directory. The committer and the
author of each commit come from the environment of that commit. Nothing reads
``~/.gitconfig``, ``~/.gnupg`` or ``~/.ssh``, and no agent is used.

A signed commit uses a stand-in for the ``gpg`` program (:func:`sign_with_stand_in`).
The stand-in is a small script in ``tmp_path``. It writes a signature that names
a scenario, and it answers a verification with the status lines of that scenario.
Git reads those lines as it reads the lines of a real ``gpg``. So every letter of
git's signature status can be made on any machine, with no key and no agent.

The text report is read loosely. A specification finds the block of one edge by its
first line. It reads the lines of the block that start with a label. It never reads
the layout between them. The JSON report is read by key.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from affirmatrix.cli import main

from . import extraction_support as base
from . import node_show_support as nodes

# --- the interface: the one place -------------------------------------------

#: The key, on the row of an affirmed edge, that holds the provenance (proposal).
KEY_PROVENANCE = "recordedInCaseHistory"
KEY_STATUS = "status"
#: ``found``: a commit holds the event. ``notCommitted``: no commit holds it.
#: ``unavailable``: the case is not a repository of its own, or its history cannot be read.
FOUND = "found"
NOT_COMMITTED = "notCommitted"
UNAVAILABLE = "unavailable"
#: The identifier of the recording commit, 40 hex characters, or ``null``.
KEY_COMMIT = "commit"
#: The subject line of the recording commit, or ``null``.
KEY_SUBJECT = "subject"
#: The committer: an object with the keys below, or ``null``.
KEY_COMMITTER = "committer"
#: The author: the same object, or ``null`` when the author is the committer.
KEY_AUTHOR = "author"
KEY_NAME = "name"
KEY_EMAIL = "email"
#: ISO 8601 with the offset, as ``git log --format=%cI`` gives it.
KEY_DATE = "date"
#: The Signed-off-by lines of the message, in order, as a list of text. Each entry is
#: the value as written (``Name <email>``). The word ``Signed-off-by:`` can lead it.
KEY_SIGNED_OFF_BY = "signedOffBy"
#: The signature status, as one of the words below. Null unless the status is ``found``.
KEY_SIGNATURE = "signature"
#: A boolean: whether the history of the case is shallow. Null unless the status is ``found``.
KEY_SHALLOW = "shallow"

# The signature words. Git gives a letter. N none, G good, B bad, U good with unknown
# validity, X expired signature, Y expired key, R revoked key, E cannot check.
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

# The labels of the text report. A line is found by its label, in lower case.
LABEL_RECORDED = "recorded in the case history"
LABEL_RECORDED_AS = "recorded in the case history as"
LABEL_AUTHOR = "author:"
LABEL_SIGNED_OFF_BY = "signed-off-by:"
LABEL_SIGNATURE = "signature:"
WORD_NOT_COMMITTED = "not committed"
WORD_NOT_AVAILABLE = "not available"
WORD_SHALLOW = "shallow"
#: No output of the verb carries one of these words.
FORBIDDEN_WORDS = ("affirmed by", "verified", "authenticated")

#: The file of review events in a case, relative to the case root.
EVENTS_FILE = "events/review_events.jsonld"

KIND = "Refines"
FROM = "REQ-B"
OTHER = "REQ-C"
TO = "REQ-A"

requires_git = base.requires_git


def red(claim: int, why: str) -> pytest.MarkDecorator:
    """Mark a specification that is red until the claim is built. Strict: a pass is a failure."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"SEG-SREQ-{claim}: {why}")


# --- people and times --------------------------------------------------------


@dataclass(frozen=True)
class Person:
    """A name and an e-mail address, as git records them."""

    name: str
    email: str

    @property
    def written(self) -> str:
        return f"{self.name} <{self.email}>"


ALICE = Person("Alice Committer", "alice@example.invalid")
BOB = Person("Bob Author", "bob@example.invalid")
CAROL = Person("Carol Starter", "carol@example.invalid")
DAN = Person("Dan Amender", "dan@example.invalid")

_ZONE = timezone(timedelta(hours=2))
_START = datetime(2026, 3, 4, 5, 6, 7, tzinfo=_ZONE)


def moment(hours: int) -> datetime:
    """A time that is ``hours`` after a fixed start, in a zone that is not UTC."""
    return _START + timedelta(hours=hours)


# --- git ---------------------------------------------------------------------

_REPOSITORY_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    "GIT_COMMITTER_DATE",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_AUTHOR_DATE",
    "GIT_CONFIG_COUNT",
    "SSH_AUTH_SOCK",
    "GPG_AGENT_INFO",
)


def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Cut git off from the machine, for the test and for the command under test.

    The command runs git in this process environment, so the variables are set
    with ``monkeypatch`` and they reach it.
    """
    for name in _REPOSITORY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve().parent))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    # A commit can start a background maintenance run, which writes a lock file under .git
    # after the commit returns, and the run races with the tests that compare the .git directory.
    add_config(monkeypatch, {"gc.auto": "0", "maintenance.auto": "false"})


def add_config(monkeypatch: pytest.MonkeyPatch, settings: dict[str, str]) -> None:
    """Add git settings through the environment, after the ones that are already there."""
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    for offset, (key, value) in enumerate(settings.items()):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{count + offset}", key)
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{count + offset}", value)
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(count + len(settings)))


def git(directory: Path, *args: str, env: dict[str, str] | None = None, stdin: str = "") -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
        env={**os.environ, **(env or {})},
    )
    return completed.stdout.strip()


def head(directory: Path) -> str:
    return git(directory, "rev-parse", "HEAD")


def init_repository(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q", "-b", "main")


def commit(
    directory: Path,
    message: str,
    *,
    committer: Person = ALICE,
    committed: datetime | None = None,
    author: Person | None = None,
    authored: datetime | None = None,
    signature: str | None = None,
    amend: bool = False,
) -> str:
    """Commit every change in ``directory`` and return the new commit.

    The committer and the author, and their dates, are set in the environment of
    this one commit. An author that is not given is the committer, with the same
    date. With ``amend``, the last commit is replaced and keeps its author. With
    ``signature``, the commit is signed by the stand-in, under that scenario.
    """
    when = committed if committed is not None else moment(1)
    writer = author if author is not None else committer
    env = {
        "GIT_COMMITTER_NAME": committer.name,
        "GIT_COMMITTER_EMAIL": committer.email,
        "GIT_COMMITTER_DATE": when.isoformat(),
        "GIT_AUTHOR_NAME": writer.name,
        "GIT_AUTHOR_EMAIL": writer.email,
        "GIT_AUTHOR_DATE": (authored if authored is not None else when).isoformat(),
    }
    arguments = ["commit", "-q", "--allow-empty", "--cleanup=verbatim"]
    if signature is not None:
        env["FAKE_GPG_SCENARIO"] = signature
        arguments.append("-S")
    else:
        arguments.append("--no-gpg-sign")
    git(directory, "add", "-A")
    if amend:
        git(directory, *arguments, "--amend", "--no-edit", env=env)
    else:
        git(directory, *arguments, "-F", "-", env=env, stdin=message)
    return head(directory)


def sign_with_stand_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Make git sign and verify with a stand-in program that lives in ``tmp_path``.

    The settings go in the environment, never in a global configuration. The
    stand-in signs with a text that names the scenario in ``FAKE_GPG_SCENARIO``.
    It verifies by printing the status lines that a real ``gpg`` prints for
    that scenario. It needs no key and no agent.
    """
    program = tmp_path / "stand-in-gpg"
    program.write_text(_STAND_IN.replace("PYTHON", sys.executable), encoding="utf-8")
    program.chmod(0o755)
    settings = {
        "gpg.format": "openpgp",
        "gpg.program": str(program),
        "user.signingkey": "STAND-IN",
    }
    add_config(monkeypatch, settings)


_STAND_IN = """#!PYTHON
import os
import sys

arguments = sys.argv[1:]
sys.stdin.buffer.read()
if "--verify" in arguments:
    with open(arguments[arguments.index("--verify") + 1], encoding="utf-8") as stream:
        text = stream.read()
    scenario = [line for line in text.splitlines() if line.startswith("SCENARIO ")][0].split()[1]
    key = "0123456789ABCDEF"
    good = [f"GOODSIG {key} Stand-in", "VALIDSIG FP 2026-01-01 1 0 4 0 1 8 00 FP"]
    statuses = {
        "G": [*good, "TRUST_ULTIMATE 0 pgp"],
        "U": [*good, "TRUST_UNDEFINED 0 pgp"],
        "B": [f"BADSIG {key} Stand-in"],
        "X": [f"EXPSIG {key} Stand-in"],
        "Y": [f"EXPKEYSIG {key} Stand-in"],
        "R": [f"REVKEYSIG {key} Stand-in"],
        "E": [f"ERRSIG {key} 1 8 00 1700000000 9 -", f"NO_PUBKEY {key}"],
    }[scenario]
    for line in statuses:
        print("[GNUPG:] " + line, flush=True)
    sys.exit(0 if scenario in "GU" else 1)
sys.stdout.write(
    "-----BEGIN PGP SIGNATURE-----\\n\\nSCENARIO " + os.environ["FAKE_GPG_SCENARIO"]
    + "\\n-----END PGP SIGNATURE-----\\n"
)
sys.stderr.write("[GNUPG:] SIG_CREATED D 1 8 00 1700000000 FP\\n")
"""


# --- cases -------------------------------------------------------------------


def build(tmp_path: Path) -> base.Fixture:
    """A store of three requirements, committed once, and an empty case."""
    return base.build(tmp_path)


def start_history(
    fixture: base.Fixture, *, committer: Person = CAROL, hours: int = 0, case: Path | None = None
) -> str:
    """Make the case a git repository and commit its layout, with no review event."""
    root = case if case is not None else fixture.case
    init_repository(root)
    return commit(root, "start the case", committer=committer, committed=moment(hours))


def affirm(
    fixture: base.Fixture,
    *selector: str,
    reason: str = "checked",
    case: Path | None = None,
) -> None:
    """Affirm the edges the selector names, by the verb. The default is REQ-B to REQ-A."""
    chosen = selector or ("--kind", KIND, "--from", FROM, "--to", TO)
    status = main(
        [
            "edge",
            "affirm",
            "--case",
            str(case if case is not None else fixture.case),
            "--config",
            str(fixture.config),
            "--current",
            str(fixture.current),
            *chosen,
            "--role",
            "Reviewer",
            "--reason",
            reason,
        ]
    )
    assert status == 0


def affirm_other(fixture: base.Fixture, *, reason: str = "checked", case: Path | None = None):
    """Affirm the edge REQ-C to REQ-A."""
    affirm(fixture, "--kind", KIND, "--from", OTHER, "--to", TO, reason=reason, case=case)


def affirmed_and_committed(
    fixture: base.Fixture, message: str = "affirm REQ-B", **commit_arguments: Any
) -> str:
    """The case starts as a repository, REQ-B to REQ-A is affirmed, and one commit holds it.

    Returns the recording commit.
    """
    start_history(fixture)
    affirm(fixture)
    return commit(fixture.case, message, **commit_arguments)


def event_ids(case_root: Path) -> list[str]:
    """The identifiers of the review events, as the events file holds them, in file order."""
    document = json.loads((case_root / EVENTS_FILE).read_text(encoding="utf-8"))
    return [entry["id"] for entry in document["@graph"]]


def edit_events(case_root: Path, old: str, new: str) -> None:
    """Replace one piece of text in the events file. The text must occur exactly once."""
    path = case_root / EVENTS_FILE
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


def events_text(case_root: Path) -> str:
    return (case_root / EVENTS_FILE).read_text(encoding="utf-8")


def write_events_text(case_root: Path, text: str) -> None:
    (case_root / EVENTS_FILE).write_text(text, encoding="utf-8")


def events_text_without_entries(text: str) -> str:
    """The text of the events file with the list of events empty, in the form the store writes."""
    document = json.loads(text)
    document["@graph"] = []
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def rename_event(case_root: Path, old: str, new: str) -> None:
    """Change the identifier of one event in the events file, as text, and nothing else."""
    edit_events(case_root, f'"id": "{old}"', f'"id": "{new}"')


def next_identifier(identifier: str) -> str:
    """The identifier of the event that follows ``identifier``, by the number it ends with."""
    prefix, _, number = identifier.rpartition("/")
    return f"{prefix}/{int(number) + 1:0{len(number)}d}"


def make_worktree(host: Path, path: Path) -> None:
    """A repository ``host`` with one commit, and ``path`` its worktree on a branch of its own."""
    init_repository(host)
    (host / "host.txt").write_text("the host repository\n", encoding="utf-8")
    commit(host, "host commit", committer=DAN, committed=moment(-5))
    try:
        git(host, "worktree", "add", "-q", "--orphan", "-b", "case", str(path))
    except subprocess.CalledProcessError:  # git before 2.42 has no --orphan
        git(host, "worktree", "add", "-q", "-b", "case", str(path))


def make_stale_index(directory: Path) -> None:
    """Change the recorded modification time of every tracked file, not its content."""
    base.make_index_stale(directory)


def control_writes_the_index(directory: Path, watched: Path) -> bool:
    """Whether a plain ``git status`` in ``directory`` changes a file under ``watched``."""
    before = base.snapshot(watched)
    git(directory, "status", "--porcelain=v1")
    return base.snapshot(watched) != before


# --- the report --------------------------------------------------------------


def where(fixture: base.Fixture, case: Path | None = None) -> nodes.Place:
    place = nodes.place(fixture)
    return nodes.Place(case if case is not None else place.case, place.config, place.current)


def instants(line: str) -> list[datetime]:
    found = []
    for token in re.split(r"[\s,;\"'()]+", line):
        try:
            found.append(datetime.fromisoformat(token))
        except ValueError:
            continue
    return [item for item in found if item.tzinfo is not None]


def normal(word: str) -> str:
    """A status word with no case, space, hyphen or underscore, so that two spellings meet."""
    return re.sub(r"[\s_-]", "", word).lower()


@dataclass(frozen=True)
class Shown:
    """The text and the JSON report of ``edge show``, from two runs of the command."""

    status: int
    text: str
    raw: str
    document: Any

    def rows(self) -> list[dict[str, Any]]:
        return list(self.document["edges"])

    def row(self, from_id: str = FROM) -> dict[str, Any]:
        (row,) = [item for item in self.rows() if item["from"] == from_id]
        return row

    def provenance(self, from_id: str = FROM) -> dict[str, Any]:
        """The provenance object of one edge. The test fails when the row has none."""
        row = self.row(from_id)
        assert KEY_PROVENANCE in row, f"the row of {from_id} has no {KEY_PROVENANCE}"
        return row[KEY_PROVENANCE]

    def block(self, from_id: str = FROM) -> list[str]:
        """The lines of the text block of one edge, the first line included."""
        lines = self.text.splitlines()
        block: list[str] = []
        inside = False
        for line in lines:
            if line and not line[0].isspace():
                inside = line.startswith(f"{from_id} --[")
            if inside:
                block.append(line)
        return block

    def block_text(self, from_id: str = FROM) -> str:
        return "\n".join(self.block(from_id))

    def labelled(self, label: str, from_id: str = FROM) -> list[str]:
        """The lines of the block of one edge that start with ``label``, stripped."""
        return [
            line.strip()
            for line in self.block(from_id)
            if line.strip().lower().startswith(label.lower())
        ]

    def recorded_line(self, from_id: str = FROM) -> str:
        """The one line of the block that opens the provenance, or the test fails."""
        lines = [line.strip() for line in self.block(from_id) if LABEL_RECORDED in line.lower()]
        assert len(lines) == 1, (from_id, lines, self.text)
        return lines[0]


def show(place: nodes.Place, capsys: pytest.CaptureFixture[str], *selector: str) -> Shown:
    """Run ``edge show`` twice, as text and as JSON. The two must give the same status.

    The default selector is the edge REQ-B to REQ-A.
    """
    chosen = selector or ("--kind", KIND, "--from", FROM, "--to", TO)
    arguments = ["edge", "show", *place.arguments(), *chosen]
    capsys.readouterr()
    status = main(arguments)
    text = nodes.output(capsys)
    json_status = main([*arguments, nodes.JSON_OPTION])
    raw = nodes.output(capsys)
    assert json_status == status, (status, json_status)
    try:
        document = json.loads(raw)
    except ValueError:
        document = None
    return Shown(status, text, raw, document)


def person_is(entry: dict[str, Any] | None, person: Person, when: datetime) -> bool:
    """Whether a JSON person has this name and e-mail, and a date that is this instant."""
    if not isinstance(entry, dict):
        return False
    try:
        date = datetime.fromisoformat(entry[KEY_DATE])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        entry.get(KEY_NAME) == person.name
        and entry.get(KEY_EMAIL) == person.email
        and date.tzinfo is not None
        and date == when
    )


def line_has(line: str, person: Person, when: datetime) -> bool:
    """Whether a text line names this person, with name and e-mail, and gives this instant."""
    return (
        person.name in line
        and person.email in line
        and any(item == when for item in instants(line))
    )


def signed_off_value(entry: str) -> str:
    """A Signed-off-by entry without the leading word, so a list and a line compare."""
    return re.sub(r"^\s*signed-off-by:\s*", "", entry, flags=re.IGNORECASE).strip()


def hex_prefix(commit_id: str) -> str:
    """The seven characters a short identifier at least holds."""
    return commit_id[:7]


def is_found_at(shown: Shown, commit_id: str, from_id: str = FROM) -> bool:
    """Whether the JSON and the text both name this commit for one edge."""
    entry = shown.provenance(from_id)
    return (
        entry.get(KEY_STATUS) == FOUND
        and entry.get(KEY_COMMIT) == commit_id
        and hex_prefix(commit_id) in shown.block_text(from_id)
    )


def copy_case_without_history(source: Path, target: Path) -> Path:
    """A copy of a case's files, with no ``.git``, as a case that was only copied."""
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git"))
    return target


# --- named cases -------------------------------------------------------------
#
# Each builder makes one case under ``root`` and returns what a specification needs.
# The caller has called :func:`isolate`.


def case_committed(
    root: Path,
    *,
    committer: Person = ALICE,
    hours: int = 3,
    signature: str | None = None,
) -> tuple[base.Fixture, str]:
    """A case whose one affirmation is added by one commit. Returns the case and the commit."""
    fixture = build(root)
    commit_id = affirmed_and_committed(
        fixture, committer=committer, committed=moment(hours), signature=signature
    )
    return fixture, commit_id


def case_draft(root: Path) -> base.Fixture:
    """A case whose one affirmation is in the working tree and in no commit."""
    fixture = build(root)
    start_history(fixture)
    affirm(fixture)
    return fixture


def case_copied(root: Path) -> tuple[nodes.Place, str]:
    """A case that was copied with no history. Returns the place and the commit it came from."""
    fixture, commit_id = case_committed(root / "source")
    copy = copy_case_without_history(fixture.case, root / "copy")
    return where(fixture, copy), commit_id


def case_nested(root: Path) -> tuple[nodes.Place, str]:
    """A case that sits in another repository, which holds it in a commit of its own.

    Returns the place of the case and the commit of the enclosing repository.
    """
    fixture, _ = case_committed(root / "source")
    outer = root / "outer"
    init_repository(outer)
    copy_case_without_history(fixture.case, outer / "case")
    outer_commit = commit(outer, "add the case", committer=DAN, committed=moment(7))
    return where(fixture, outer / "case"), outer_commit


def case_unreadable(root: Path) -> base.Fixture:
    """A case repository whose last commit has lost its object file."""
    fixture, commit_id = case_committed(root)
    (fixture.case / ".git" / "objects" / commit_id[:2] / commit_id[2:]).unlink()
    return fixture


def case_shallow(root: Path) -> tuple[nodes.Place, nodes.Place, str, str]:
    """A depth-one clone of a case with three commits.

    The first commit starts the case. A second adds the event of REQ-B, and a third adds the
    event of REQ-C. Returns the place of the clone, the place of the source with its full history,
    the second commit and the third.
    """
    fixture = build(root / "source")
    start_history(fixture)
    affirm(fixture)
    second = commit(fixture.case, "affirm REQ-B", committer=ALICE, committed=moment(3))
    affirm_other(fixture)
    third = commit(fixture.case, "affirm REQ-C", committer=BOB, committed=moment(4))
    clone = root / "clone"
    git(root, "clone", "-q", "--depth", "1", f"file://{fixture.case}", str(clone))
    return where(fixture, clone), where(fixture), second, third
