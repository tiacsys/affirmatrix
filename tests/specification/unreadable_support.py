"""Shared helpers for the specifications of a content repository that cannot be read.

Not a specification. The modules that realize specifications import these
helpers. A repository is made unreadable in five ways, and a specification runs
once for each way as variants of one claim:

* ``objects``: every object is removed from the repository. Its refs stay.
* ``stand-in``: a ``git`` first on ``PATH`` that writes a message and exits with
  status 128, whatever it is asked.
* ``not-a-repository``: the configuration maps the repository name to a
  directory that holds no repository.
* ``missing-path``: the configuration maps the repository name to a path that
  does not exist.
* ``git-absent``: no ``git`` is on ``PATH``.

Every fixture is built by the test, inside ``tmp_path``. A repository is broken
after the test has made its commits and its first runs of the command, so the
test can read a healthy answer first. The repository is named in the
configuration, and the expected name is that configured name, never a path that
a failure message holds.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

from . import extraction_support as base
from . import repository_reads_support as reads

#: The five ways to make a repository unreadable.
VARIANTS = ("objects", "stand-in", "not-a-repository", "missing-path", "git-absent")

#: The text that the stand-in git writes. A reason that comes from git holds it.
STAND_IN_MESSAGE = "the stand-in git fails every call"

#: A word that the reason of each variant holds, where the cause makes one certain.
#: ``None`` means only that the reason is some text beyond the name. A path that
#: does not exist must be reported as one that does not exist.
REASON_WORDS: dict[str, str | None] = {
    "objects": None,
    "stand-in": STAND_IN_MESSAGE,
    "not-a-repository": "not a git repository",
    "missing-path": "does not exist",
    "git-absent": "path",
}

#: The word that a crash prints. No refusal of the command holds it.
TRACEBACK = "Traceback"


def repoint(config: Path, name: str, target: Path) -> None:
    """Map the repository ``name`` to ``target`` in the configuration."""
    document = yaml.safe_load(config.read_text(encoding="utf-8"))
    document["repositories"][name] = str(target)
    config.write_text(yaml.safe_dump(document), encoding="utf-8")


def _put_first_on_path(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


def break_repository(
    variant: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    repository: Path,
    config: Path,
    name: str,
    only_here: bool = False,
) -> None:
    """Make the repository ``name`` at ``repository`` unreadable in the way ``variant`` says.

    A way that works through ``PATH`` breaks every repository of the run. A way
    that works through the configuration or the objects breaks this one only.
    With ``only_here``, the stand-in fails only for a call that runs in
    ``repository`` and passes every other call to the real git.
    """
    if variant == "objects":
        reads.break_objects(repository, tmp_path / "donor")
    elif variant == "stand-in":
        directory = tmp_path / "failing-git"
        directory.mkdir()
        program = directory / "git"
        guard = (
            f"import os, subprocess\nhere = {str(repository.resolve())!r}\n"
            "cwd = os.path.realpath(os.getcwd())\n"
            "if not (cwd == here or cwd.startswith(here + os.sep)):\n"
            f"    sys.exit(subprocess.run([{reads.REAL_GIT!r}, *sys.argv[1:]]).returncode)\n"
            if only_here
            else ""
        )
        program.write_text(
            f"#!{sys.executable}\nimport sys\n{guard}"
            f"sys.stderr.write('fatal: {STAND_IN_MESSAGE}\\n')\nsys.exit(128)\n",
            encoding="utf-8",
        )
        program.chmod(0o755)
        _put_first_on_path(monkeypatch, directory)
    elif variant == "not-a-repository":
        target = tmp_path / "not-a-repository"
        target.mkdir()
        repoint(config, name, target)
    elif variant == "missing-path":
        repoint(config, name, tmp_path / "no-such-directory")
    elif variant == "git-absent":
        empty = tmp_path / "empty-bin"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
    else:  # pragma: no cover - a mistake in a test
        raise ValueError(variant)


def lines_naming(text: str, name: str) -> list[str]:
    """The lines of ``text`` that name the repository."""
    return [line for line in text.splitlines() if name in line]


def holds_reason(text: str, name: str, variant: str) -> bool:
    """Whether a line that names the repository also gives a reason for the failure.

    Where the cause makes a word certain, the line holds the word, in any
    case. Otherwise the line holds at least three words beyond the name.
    """
    word = REASON_WORDS[variant]
    for line in lines_naming(text, name):
        rest = line.replace(name, " ")
        if word is None:
            if len(rest.split()) >= 3:
                return True
        elif word.lower() in rest.lower():
            return True
    return False


# --- a case over two repositories --------------------------------------------------

#: The edge from an implementation, in one repository, to a requirement, in another.
TWO_FROM = "I-LIB-MAX"
TWO_TO = "R-1"
#: The other edge of the same kind, used as a control.
CONTROL_FROM = "I-LIB-MIN"
CONTROL_TO = "R-2"


def two_repositories(tmp_path: Path) -> base.Shapes:
    """Two committed repositories, a configuration and an empty case."""
    return base.build_shapes(tmp_path, held_paths=True)


def affirm_two(
    shapes: base.Shapes,
    capsys: pytest.CaptureFixture[str],
    source: str = TWO_FROM,
    target: str = TWO_TO,
    *extra: str,
) -> tuple[int, str]:
    """Run edge affirm for one Implements edge of the two repositories."""
    arguments = [
        "edge", "affirm", "--case", str(shapes.case), "--config", str(shapes.config),
        "--kind", "Implements", "--from", source, "--to", target,
        "--role", "Reviewer", "--reason", "checked", *extra,
    ]  # fmt: skip
    return reads.attempt(arguments, capsys)


def show_two(
    shapes: base.Shapes, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[int, str]:
    """Run edge show with the verbose rendering for the edge of the two repositories."""
    arguments = [
        "edge", "show", "-v", "--case", str(shapes.case), "--config", str(shapes.config),
        "--kind", "Implements", "--from", TWO_FROM, "--to", TWO_TO, *extra,
    ]  # fmt: skip
    return reads.attempt(arguments, capsys)


def break_one_of_two(
    which: str,
    variant: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    shapes: base.Shapes,
) -> str:
    """Break the repository of the requirement (``to``) or of the implementation (``from``).

    Give the configured name of the broken repository. ``variant`` is ``objects``
    or ``stand-in``. A configuration that maps the name elsewhere is no way for
    these repositories: the readers of the producer read their files through it.
    """
    if which == "to":
        name, directory = base.REQUIREMENTS_REPOSITORY, shapes.requirements
    else:
        name, directory = base.IMPLEMENTATIONS_REPOSITORY, shapes.implementations
    break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=directory,
        config=shapes.config,
        name=name,
        only_here=True,
    )
    return name
