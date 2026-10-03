"""Verification suite for the proof gate over an implementation repository that cannot be read.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
world is the small one of ``evidence_support.make_world``: a would-be store
whose content directory is a git repository, a configuration that names that
directory as the implementation repository, and an empty case. The store holds
one test outcome, so graph status needs the implementation revision. No
revision is given, so each verb has to discover one, and that is a read of the
repository. The repository is made unreadable in five ways (see
``unreadable_support``), and each way is one variant of the same specification.
Where git is the cause, the message of git names the directory of the
repository. The configuration names it by the same text, so only a way that
changes the directory or removes git can show whether the name comes from the
configuration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import evidence_support as evidence
from . import extraction_support as base
from . import repository_reads_support as reads
from . import unreadable_support as support
from .proof_verify_support import seal, verify_cli
from .provenance_support import red

pytestmark = base.requires_git

_NAME = (
    "the report names the repository by the text of git or not at all, not by the configured name"
)
_VARIANTS = [
    "objects",
    "stand-in",
    pytest.param("not-a-repository", marks=red(367, _NAME)),
    pytest.param("missing-path", marks=red(367, _NAME)),
    pytest.param("git-absent", marks=red(367, _NAME)),
]


def _verbs(world: evidence.World) -> dict[str, list[str]]:
    scope = ["--scope", "SREQ-1"]
    return {
        "proof check": ["proof", "check", *scope, *world.args()],
        "proof generate": ["proof", "generate", *scope, *world.args()],
        "graph status": ["graph", "status", *world.args()],
    }


def _broken(
    variant: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[evidence.World, dict[str, list[str]]]:
    reads.isolate(monkeypatch, tmp_path)
    world = evidence.make_world(tmp_path / "world", outcomes=("head",))
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=world.content,
        config=world.config,
        name=str(world.content),
    )
    return world, _verbs(world)


@pytest.mark.parametrize("variant", _VARIANTS)
def test_the_gate_names_an_implementation_repository_that_it_cannot_read(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate names an implementation repository that it cannot read.

    A configuration names the implementation repository, and the stream holds a
    test outcome. A control run of each of the three verbs, while the repository
    is healthy, ends with a status other than 2. Then the repository cannot be
    read, in each of the five ways of the variants. Running proof check, proof
    generate and graph status, with no revision given, each exits with status 2.
    A line of the output names the repository as the configuration names it, and
    gives a reason. For the path that does not exist, the reason says that it
    does not exist. The output holds no traceback.

    :verifies: SEG-SREQ-367
    :test-id: SEG-TS-357
    """
    reads.isolate(monkeypatch, tmp_path)
    world = evidence.make_world(tmp_path / "world", outcomes=("head",))
    name = str(world.content)
    for command in _verbs(world).values():
        assert reads.attempt(command, capsys)[0] != 2
    support.break_repository(
        variant,
        monkeypatch,
        tmp_path,
        repository=world.content,
        config=world.config,
        name=name,
    )
    for verb, command in _verbs(world).items():
        status, text = reads.attempt(command, capsys)
        assert status == 2, verb
        assert support.TRACEBACK not in text, verb
        assert name in text, (verb, text)
        assert support.holds_reason(text, name, variant), (verb, text)


@pytest.mark.parametrize("variant", support.VARIANTS)
def test_proof_generate_writes_no_package_when_it_cannot_read_the_repository(
    variant: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """proof generate writes no evidence package when the implementation repository cannot be read.

    A configuration names the implementation repository, and the case has no
    package. The repository cannot be read, in each of the five ways of the
    variants. Running proof generate with no revision given exits with status 2.
    The proofs directory of the case holds no file afterwards, and every file of
    the case has the same bytes as before the command.

    :verifies: SEG-SREQ-368
    :test-id: SEG-TS-358
    """
    world, verbs = _broken(variant, monkeypatch, tmp_path)
    before = base.tree(world.case)
    status, _ = reads.attempt(verbs["proof generate"], capsys)
    assert status == 2
    assert not [path for path in (world.case / "proofs").rglob("*") if path.is_file()]
    assert base.tree(world.case) == before


def test_the_commands_that_need_no_implementation_revision_read_no_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Commands that need no implementation revision read no repository.

    A stand-in git logs each call. Graph status over a stream with no test
    outcome exits with status 0, and the log holds no call. Graph status over a
    stream with an outcome, with a revision given, exits with a status other
    than 2, and the log holds no call. Proof verify over a package that the
    generator wrote makes no call either. The log is empty after all three.

    :verifies: SEG-SREQ-112
    :test-id: SEG-TS-359
    """
    reads.isolate(monkeypatch, tmp_path)
    bare = evidence.make_world(tmp_path / "bare", outcomes=())
    full = evidence.make_world(tmp_path / "full", outcomes=("head",))
    sealed = seal(tmp_path / "sealed", capsys)
    stand_in = reads.install_stand_in(monkeypatch, tmp_path)
    status, _ = reads.attempt(["graph", "status", *bare.args()], capsys)
    assert status == 0
    status, _ = reads.attempt(["graph", "status", *full.args(), "--revision", full.head], capsys)
    assert status != 2
    verify_cli(capsys, sealed.opened, sealed.package.name)
    assert stand_in.calls() == []


def test_the_gate_reads_the_implementation_repository_without_the_variables_that_name_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """proof check, proof generate and graph status run git without the seven variables.

    A configuration names the implementation repository, and the stream holds a
    test outcome. A second repository exists. All seven variables GIT_DIR,
    GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY,
    GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_COMMON_DIR and GIT_NAMESPACE are set,
    and each names the second repository. A stand-in git logs the environment of
    each call. Running proof check, proof generate and graph status with no
    revision given leaves a log with calls for the revision and the status. In no
    call is one of the seven variables present.

    :verifies: SEG-SREQ-333
    :test-id: SEG-TS-360
    """
    reads.isolate(monkeypatch, tmp_path)
    world = evidence.make_world(tmp_path / "world", outcomes=("head",))
    decoy = reads.make_decoy(tmp_path / "decoy")
    stand_in = reads.install_stand_in(monkeypatch, tmp_path)
    reads.point_all(monkeypatch, decoy)
    for command in _verbs(world).values():
        status, _ = reads.attempt(command, capsys)
        assert status != reads.CRASHED, command
    assert {"rev-parse", "status"} <= stand_in.subcommands()
    assert stand_in.leaks() == []
