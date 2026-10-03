"""Shared helpers for the specifications of repository reads.

This module is the one place that names the interface the specifications call:
the module constant that sets how many paths one call of git takes, and the
seven variables of the environment that name a repository. When the final
names differ, this module changes and no test does.

Every fixture is built by the test, inside ``tmp_path``. A repository is made
with ``git init`` and commits that the test makes. A decoy is a second
repository, with a history of its own, that a variable of the environment is
made to name. No test reads a real case. A test never asks the code under test
for an expected value. It reads the value from the repository with git.

The test's own calls of git run without the seven variables, with no global or
system settings, and with the real ``git`` program by its full path. So a
variable that the test sets for the command under test never reaches the
fixture, and a stand-in ``git`` on ``PATH`` never sees a call of the test.

A stand-in ``git`` is a small script in ``tmp_path``. It writes one line for each
call to a log: the arguments, and which of the seven variables the call had.
Then it runs the real ``git`` without the seven variables. It can also fail
the Nth call of one subcommand.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from affirmatrix import case
from affirmatrix.cli import _repository, main

from . import extraction_support as base
from . import node_show_support as nodes
from . import provenance_support as prov
from .provenance_support import DAN, moment

# --- the interface: the one place -------------------------------------------

#: The module constant that holds the most paths that one call of git takes.
#: A read of more paths is made in parts of at most this many paths.
LIMIT_NAME = "PATHS_PER_CALL"

#: The seven variables that name a repository, as the requirement lists them.
NAMES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
)
#: The variables that stay in the environment of a read. Operators and CI need them.
STAYING = ("GIT_CEILING_DIRECTORIES", "GIT_CONFIG_COUNT")

#: The exit status of a verb that raised an error instead of returning one.
CRASHED = -1

REAL_GIT = shutil.which("git")
requires_git = pytest.mark.skipif(REAL_GIT is None, reason="git is not on PATH")

red = prov.red


def lower_limit(monkeypatch: pytest.MonkeyPatch, paths: int) -> None:
    """Make one call of git take at most ``paths`` paths.

    The helper creates the constant when the module lacks it, so a test can run without parts.
    """
    monkeypatch.setattr(_repository, LIMIT_NAME, paths, raising=False)


# --- git, as the test uses it -------------------------------------------------


def clean_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment of a call of the test: no variable that names a repository."""
    environment = {key: value for key, value in os.environ.items() if key not in NAMES}
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_SYSTEM"] = os.devnull
    environment.update(extra or {})
    return environment


def run_git(
    directory: Path, *args: str, extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run git in ``directory`` and give the result. ``extra`` is added to the environment."""
    assert REAL_GIT is not None
    return subprocess.run(
        [REAL_GIT, "--no-optional-locks", *args],
        cwd=directory,
        check=False,
        capture_output=True,
        env=clean_environment(extra),
    )


def git(directory: Path, *args: str) -> str:
    completed = run_git(directory, *args)
    assert completed.returncode == 0, (args, completed.stderr)
    return completed.stdout.decode("utf-8").strip()


def head(directory: Path) -> str:
    return git(directory, "rev-parse", "HEAD")


def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Cut git off from the machine, and clear all seven variables for the command too."""
    prov.isolate(monkeypatch, tmp_path)
    # Under a cap on virtual memory, git cannot start the threads that preload an index, and
    # a call over very many files fails now and then. One thread needs no extra memory.
    prov.add_config(monkeypatch, {"core.preloadindex": "false"})


# --- decoys --------------------------------------------------------------------


def make_decoy(path: Path, *, same_text: bool = False) -> Path:
    """A repository with a history of its own, and the same file names as the fixture.

    The files hold other text, and the history has two commits, so no revision of the
    decoy is a revision of the fixture. With ``same_text``, the files hold the text that the
    fixture commits, so that a plain ``git status`` can find them equal and refresh an index.
    """
    prov.init_repository(path)
    for local_id in base.IDS:
        text = f"statement of {local_id}\n" if same_text else f"the decoy text of {local_id}\n"
        base.write(path, f"requirement/{local_id}.txt", text)
    prov.commit(path, "decoy: first", committer=DAN, committed=moment(-9))
    base.write(path, "requirement/extra.txt", "one more file of the decoy\n")
    prov.commit(path, "decoy: second", committer=DAN, committed=moment(-8))
    return path


def make_case_decoy(case: Path, path: Path) -> Path:
    """A repository that holds a copy of the files of ``case``, in a commit by someone else."""
    prov.copy_case_without_history(case, path)
    prov.init_repository(path)
    prov.commit(path, "a copy of the case", committer=DAN, committed=moment(9))
    return path


def point(monkeypatch: pytest.MonkeyPatch, variable: str, decoy: Path) -> None:
    """Set ``variable`` in the environment of the command so that it names ``decoy``."""
    values = {
        "GIT_DIR": decoy / ".git",
        "GIT_WORK_TREE": decoy,
        "GIT_INDEX_FILE": decoy / ".git" / "index",
        "GIT_OBJECT_DIRECTORY": decoy / ".git" / "objects",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": decoy / ".git" / "objects",
        "GIT_COMMON_DIR": decoy / ".git",
        "GIT_NAMESPACE": "decoy-namespace",
    }
    monkeypatch.setenv(variable, str(values[variable]))


def point_all(monkeypatch: pytest.MonkeyPatch, decoy: Path) -> None:
    """Set all seven variables, each so that it names ``decoy``."""
    for name in NAMES:
        point(monkeypatch, name, decoy)


def environment_with(variable: str, decoy: Path) -> dict[str, str]:
    """The one variable, as ``point`` sets it, for a call of the test's own git."""
    with pytest.MonkeyPatch.context() as patch:
        point(patch, variable, decoy)
        return {variable: os.environ[variable]}


def break_objects(repository: Path, donor: Path) -> None:
    """Copy ``repository`` to ``donor``, then remove every object from ``repository``.

    The refs and the index of ``repository`` stay. Git cannot read a commit there, unless
    it is told to look for objects in ``donor``.
    """
    shutil.copytree(repository, donor)
    objects = repository / ".git" / "objects"
    for entry in objects.iterdir():
        if len(entry.name) == 2 and entry.is_dir():
            shutil.rmtree(entry)


# --- a store of many requirements ----------------------------------------------


def many_ids(count: int) -> list[str]:
    return [f"REQ-{number:03d}" for number in range(count)]


def build_many(
    tmp_path: Path, count: int, *, dirty: tuple[int, ...] = (), uncommitted: tuple[int, ...] = ()
) -> base.Fixture:
    """A store of ``count`` requirements in one repository, and an empty case.

    Each requirement hashes its own file. Every file is committed once, except the files
    of the numbers in ``uncommitted``, which exist in the working tree only. After the commit,
    the files of the numbers in ``dirty`` change, and the change is not committed.
    """
    root = tmp_path / "store"
    repository = base.init_repository(root / "content")
    ids = many_ids(count)
    lines = ['kind = "Requirement"', "", "[nodes]"]
    for local_id in ids:
        lines.append(f'"{local_id}" = {{ contentHash = "requirement/{local_id}.txt" }}')
    for number, local_id in enumerate(ids):
        if number not in uncommitted:
            base.write(repository, f"requirement/{local_id}.txt", f"statement of {local_id}\n")
    base.write(root, "nodes/requirements.toml", "\n".join(lines) + "\n")
    edges = ",\n".join(f'    ["{local_id}", "{ids[0]}"]' for local_id in ids[1:])
    base.write(root, "edges/refines.toml", f"[edges]\nRefines = [\n{edges},\n]\n")
    base.commit_all(repository, "first commit")
    for number in uncommitted:
        base.write(repository, f"requirement/{ids[number]}.txt", f"statement of {ids[number]}\n")
    for number in dirty:
        base.write(repository, f"requirement/{ids[number]}.txt", "a change nobody committed\n")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    fixture = base.Fixture(
        root=root,
        repository=repository,
        name=str(repository),
        case=case_root,
        config=tmp_path / "content-repositories.yaml",
    )
    base.configure(fixture, mapped=True)
    return fixture


def revisions_by_node(fixture: base.Fixture, count: int) -> dict[str, dict[str, str]]:
    """The extraction revision map of each requirement in the case."""
    return {local_id: base.held_map(fixture.case, local_id) for local_id in many_ids(count)}


# --- the reads, as raw git gives them -----------------------------------------


def raw_answers(
    repository: Path, extra: dict[str, str] | None = None
) -> dict[str, tuple[int, bytes]]:
    """The answer of each of the four content reads of the adapter, from raw git.

    Each answer is the exit status and the output. The paths are the three files
    of the fixture.
    """
    paths = [f"requirement/{local_id}.txt" for local_id in base.IDS]
    calls = {
        "revision": ["rev-parse", "HEAD"],
        "status": ["status", "--porcelain=v1", "-z", "--", *paths],
        "tree": ["ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *paths],
        "show": ["show", f"HEAD:{paths[1]}"],
    }
    answers = {}
    for name, arguments in calls.items():
        completed = run_git(repository, *arguments, extra=extra)
        answers[name] = (completed.returncode, completed.stdout)
    return answers


def decoy_changes(repository: Path, variable: str, decoy: Path, *reads: str) -> bool:
    """Whether raw git, with ``variable`` on ``decoy``, answers one of ``reads`` differently."""
    plain = raw_answers(repository)
    set_up = raw_answers(repository, environment_with(variable, decoy))
    return any(plain[name] != set_up[name] for name in reads)


def case_answers(case: Path, extra: dict[str, str] | None = None) -> dict[str, tuple[int, bytes]]:
    """The answer of each read of the history of a case, from raw git."""
    calls = {
        "top level": ["rev-parse", "--show-toplevel"],
        "head": ["rev-parse", "--verify", "--quiet", "HEAD"],
        "log": ["log", "--reverse", "--format=%H", "--", prov.EVENTS_FILE],
    }
    answers = {}
    for name, arguments in calls.items():
        completed = run_git(case, *arguments, extra=extra)
        answers[name] = (completed.returncode, completed.stdout)
    return answers


def case_decoy_changes(case: Path, variable: str, decoy: Path) -> bool:
    """Whether raw git, with ``variable`` on ``decoy``, answers a read of the case differently."""
    return case_answers(case) != case_answers(case, environment_with(variable, decoy))


def plain_status_writes(repository: Path, variable: str, decoy: Path, watched: list[Path]) -> bool:
    """Whether a plain ``git status`` in ``repository``, with the variable set, writes a file.

    The call has no ``--no-optional-locks``, so it can refresh an index. ``watched`` are
    the directories whose files are compared before and after.
    """
    before = [base.snapshot(path) for path in watched]
    assert REAL_GIT is not None
    subprocess.run(
        [REAL_GIT, "status", "--porcelain=v1"],
        cwd=repository,
        check=False,
        capture_output=True,
        env=clean_environment(environment_with(variable, decoy)),
    )
    return [base.snapshot(path) for path in watched] != before


# --- the verbs, as an operator runs them --------------------------------------


def attempt(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Run ``main``. An error that leaves it becomes ``CRASHED`` and its text."""
    capsys.readouterr()
    try:
        status = main(arguments)
    except Exception as error:  # noqa: BLE001 - a crash is an answer the test reports
        return CRASHED, f"{type(error).__name__}: {error}"
    captured = capsys.readouterr()
    return status, captured.out + captured.err


def sync_arguments(fixture: base.Fixture) -> list[str]:
    return [
        "case", "sync",
        "--case", str(fixture.case),
        "--config", str(fixture.config),
        "--current", str(fixture.current),
    ]  # fmt: skip


def sync(fixture: base.Fixture, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    return attempt(sync_arguments(fixture), capsys)


def affirm(fixture: base.Fixture, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Affirm the edge REQ-B refines REQ-A."""
    arguments = [
        "edge", "affirm",
        "--case", str(fixture.case),
        "--config", str(fixture.config),
        "--current", str(fixture.current),
        "--kind", prov.KIND, "--from", prov.FROM, "--to", prov.TO,
        "--role", "Reviewer", "--reason", "checked",
    ]  # fmt: skip
    return attempt(arguments, capsys)


def show_before_content(
    place: nodes.Place, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict | None]:
    """Run ``edge show -v --json`` for REQ-B to REQ-A. Give the status and the row."""
    arguments = [
        "edge", "show", *place.arguments(),
        "--kind", prov.KIND, "--from", prov.FROM, "--to", prov.TO,
        "--json", "-v",
    ]  # fmt: skip
    status, text = attempt(arguments, capsys)
    try:
        (row,) = json.loads(text)["edges"]
    except (ValueError, KeyError, TypeError):
        return status, None
    return status, row


def show_node_once(
    place: nodes.Place, local_id: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, dict]]:
    """Run ``node show`` once, for the JSON report. Give the status and the hashes by name.

    One run makes one read of the repository, so a stand-in git counts the calls of
    that read alone.
    """
    status, text = attempt(["node", "show", local_id, *place.arguments(), "--json", "-v"], capsys)
    try:
        document = json.loads(text)
        return status, {entry["name"]: entry for entry in document["hashes"]}
    except (ValueError, KeyError, TypeError):
        return status, {}


def before_text(row: dict | None, side: str) -> str | None:
    """The before-content of one endpoint in a row of ``edge show -v``, or ``None``."""
    if row is None:
        return None
    entry = (row.get("beforeContent") or {}).get(side)
    return None if entry is None else entry["content"]


def event_revisions(case: Path) -> set[str]:
    """The source revisions that the review events of the case hold."""
    document = json.loads(prov.events_text(case))
    found: set[str] = set()
    for entry in document["@graph"]:
        found.update(entry["seg:affirmedAt"].values())
    return found


def report_lines(text: str, repository: str) -> list[str]:
    """The lines of ``text`` that name ``repository`` and report records without a revision."""
    return [line for line in text.splitlines() if repository in line and "extraction" in line]


# --- a stand-in git -------------------------------------------------------------


@dataclass(frozen=True)
class StandIn:
    """A ``git`` on ``PATH`` that logs each call, and can fail one of them."""

    directory: Path
    log: Path

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        lines = self.log.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def calls_of(self, subcommand: str) -> list[dict]:
        return [call for call in self.calls() if subcommand in call["arguments"][:2]]

    def subcommands(self) -> set[str]:
        """The first word that is not an option, for each call."""
        return {
            next(item for item in call["arguments"] if not item.startswith("-"))
            for call in self.calls()
            if any(not item.startswith("-") for item in call["arguments"])
        }

    def leaks(self) -> list[tuple[list[str], list[str]]]:
        """The calls that had one of the seven variables: the arguments and the variables."""
        return [(call["arguments"], call["present"]) for call in self.calls() if call["present"]]

    def lacking(self) -> list[list[str]]:
        """The arguments of each call that lost a variable that has to stay."""
        return [
            call["arguments"] for call in self.calls() if sorted(call["staying"]) != sorted(STAYING)
        ]

    def path_counts(self, subcommand: str) -> list[int]:
        """How many path arguments each call of ``subcommand`` had, after ``--``."""
        counts = []
        for call in self.calls_of(subcommand):
            arguments = call["arguments"]
            counts.append(len(arguments) - arguments.index("--") - 1 if "--" in arguments else 0)
        return counts


def install_stand_in(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fail: tuple[str, int] | None = None,
) -> StandIn:
    """Put a stand-in ``git`` first on ``PATH``.

    With ``fail=("status", 2)``, the second call of ``git status`` writes an error to
    the standard error stream and exits with status 128, and does not run git.
    """
    directory = tmp_path / "stand-in-bin"
    directory.mkdir()
    log = tmp_path / "stand-in-calls.jsonl"
    configuration = {
        "real": REAL_GIT,
        "log": str(log),
        "counter": str(tmp_path / "stand-in-counter.json"),
        "names": list(NAMES),
        "fail": list(fail) if fail else None,
    }
    (directory / "config.json").write_text(json.dumps(configuration), encoding="utf-8")
    program = directory / "git"
    program.write_text(_STAND_IN.replace("PYTHON", sys.executable), encoding="utf-8")
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return StandIn(directory, log)


_STAND_IN = """#!PYTHON
import json
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "config.json"), encoding="utf-8") as stream:
    config = json.load(stream)
arguments = sys.argv[1:]
present = [name for name in config["names"] if name in os.environ]
staying = [name for name in ("GIT_CEILING_DIRECTORIES", "GIT_CONFIG_COUNT") if name in os.environ]
with open(config["log"], "a", encoding="utf-8") as stream:
    line = {"arguments": arguments, "present": present, "staying": staying}
    stream.write(json.dumps(line) + "\\n")
fail = config["fail"]
if fail:
    subcommands = [item for item in arguments if not item.startswith("-")][:1]
    if subcommands == [fail[0]]:
        try:
            with open(config["counter"], encoding="utf-8") as stream:
                count = json.load(stream)
        except FileNotFoundError:
            count = 0
        count += 1
        with open(config["counter"], "w", encoding="utf-8") as stream:
            json.dump(count, stream)
        if count == fail[1]:
            sys.stderr.write("fatal: the stand-in fails this call\\n")
            sys.exit(128)
environment = {key: value for key, value in os.environ.items() if key not in config["names"]}
sys.exit(subprocess.run([config["real"], *arguments], env=environment).returncode)
"""
