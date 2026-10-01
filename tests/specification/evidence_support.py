"""Shared helpers of the verification suites for test evidence from run bundles.

Not a specification. The modules that realize specifications import these
helpers: the paths of the frozen fixtures, the digest recipe written in plain
Python, a configuration writer, a command runner and a few readers.

The digest recipe here is the one of the architecture page, written a second
time so that a test never asks the tool for the value it checks:
one line per file, ``<sha256 of the bytes>``, two blanks, the path inside the
bundle, a line feed; the lines in the byte order of the paths; the SHA-256 of
all the lines.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from affirmatrix import config
from affirmatrix.cli import main
from affirmatrix.sources import composed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TOOLBOX = FIXTURES / "toolbox_evidence"
CLEAN_BUNDLE = FIXTURES / "run_bundles" / "clean"
LEGACY_CASE = FIXTURES / "legacy_case"
GOLDEN = FIXTURES / "golden_evidence"

#: The digest of the clean bundle, made with the ``sha256sum`` recipe.
CLEAN_DIGEST = "f960023c5eacbe8c4a2fc2867d4d78c38bede4c02b1df6ac150f5804c8ca0043"
REVISION = "5847f3fdca777b8d62615d84b8926fdc8ce125ed"
OTHER_CHECKOUT_REVISION = "77e25d8f3cb2e94adb5a44426b98e088f1bef3fe"
OTHER_REVISION = "1" * 40
RUN_NAME = "twister-run-2026-09-29"
SECOND_RUN_NAME = "twister-run-second"
SCOPE = ("SD-TOP-001", "SD-TOP-003")
TIMESTAMP = "2026-10-01T00:00:00+00:00"
EVALUATION_DATE = "2026-10-01"
OUTCOMES_PER_RUN = 76


def recipe_digest(bundle: Path) -> str:
    """The hex digest of a bundle directory, by the recipe."""
    entries = sorted(
        (
            (path.relative_to(bundle).as_posix(), path)
            for path in bundle.rglob("*")
            if path.is_file()
        ),
        key=lambda item: item[0].encode("utf-8"),
    )
    lines = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n" for name, path in entries
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def copy_bundle(tmp_path: Path, name: str = "clean") -> Path:
    """A private copy of the clean bundle under ``tmp_path/bundles``, safe to change."""
    target = tmp_path / "bundles" / name
    shutil.copytree(CLEAN_BUNDLE, target)
    return target


def second_bundle(tmp_path: Path, name: str = "second") -> Path:
    """A copy of the clean bundle recorded at another revision, under another run name."""
    bundle = copy_bundle(tmp_path, name)
    (bundle / "toolbox.sha").write_text(OTHER_REVISION + "\n", encoding="utf-8")
    (bundle / "run.name").write_text(SECOND_RUN_NAME + "\n", encoding="utf-8")
    return bundle


def write_config(
    tmp_path: Path,
    bundles: list[Path],
    *,
    digests: list[str] | None = None,
    implementation: str = "toolbox",
    specification_export: Path | None = None,
    implementation_export: Path | None = None,
    where: str = "cfg",
) -> Path:
    """A configuration over the frozen exports with the given bundles, in file order.

    Each digest defaults to the bundle's own, by the recipe. Every path is
    absolute. The repository ``evidence`` is ``tmp_path/bundles``, the place the
    bundles lie under.
    """
    (tmp_path / "bundles").mkdir(exist_ok=True)
    (tmp_path / "zephyr").mkdir(exist_ok=True)
    wanted = digests or [recipe_digest(bundle) for bundle in bundles]
    runs = [
        {"bundle": str(bundle), "digest": f"sha256:{digest}", "repository": "evidence"}
        for bundle, digest in zip(bundles, wanted, strict=True)
    ]
    block = {
        "repository": "toolbox",
        "requirements": {
            "export": str(TOOLBOX / "needs/requirement-specification/needs.json"),
            "types": ["requirement", "top_requirement"],
            "source": str(TOOLBOX / "sources/doc/requirement-specification"),
        },
        "implementations": {
            "export": str(implementation_export or TOOLBOX / "needs/api-traceability/needs.json"),
            "doxygen": str(TOOLBOX / "xml/dox-safe-data-api"),
        },
        "specifications": {
            "export": str(specification_export or TOOLBOX / "needs/test-specification/needs.json"),
            "doxygen": str(TOOLBOX / "xml/dox-safe-data-testspec"),
        },
        "outcomes": runs,
    }
    document = {
        "repositories": {
            "toolbox": str(TOOLBOX / "sources"),
            "evidence": str(tmp_path / "bundles"),
            "zephyr": str(tmp_path / "zephyr"),
        },
        "implementation": implementation,
        "producer": block,
    }
    path = tmp_path / where / "affirmatrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def streams(config_path: Path) -> tuple[list, list]:
    """Every node and every edge the configured producer supplies, or its refusal."""
    producer = composed.from_config(config.load(config_path))
    return list(producer.nodes()), list(producer.edges())


def run(capsys, *argv: str) -> tuple[int, str]:
    """Run one command and return its exit status and what it printed.

    Anything printed earlier, by ``case init`` for example, is discarded first.
    """
    capsys.readouterr()
    status = main(list(argv))
    return status, capsys.readouterr().out


@dataclass(frozen=True)
class Session:
    """A configuration, a case root and the arguments that name them."""

    config: Path
    case: Path

    def args(self) -> list[str]:
        return ["--case", str(self.case), "--config", str(self.config)]


def session(tmp_path: Path, bundles: list[Path], capsys, **options) -> Session:
    """Write the configuration and make an empty case."""
    path = write_config(tmp_path, bundles, **options)
    root = tmp_path / "case"
    assert main(["case", "init", "--case", str(root)]) == 0
    capsys.readouterr()
    return Session(config=path, case=root)


def affirm_design(opened: Session, capsys) -> None:
    """Sync the case and affirm every strong edge, as the golden results were made."""
    assert run(capsys, "case", "sync", *opened.args())[0] == 0
    for kind in ("Refines", "Verifies", "Implements"):
        status, _ = run(
            capsys,
            "edge",
            "affirm",
            *opened.args(),
            "--kind",
            kind,
            "--role",
            "fixture-reviewer",
            "--reason",
            "synthetic golden affirmation",
            "--revision",
            REVISION,
        )
        assert status == 0


def scope_args() -> list[str]:
    return [item for name in SCOPE for item in ("--scope", name)]


def generate(opened: Session, capsys, out: Path) -> Path:
    """Generate the package for the golden scope; the directory of its four documents."""
    status, _ = run(
        capsys,
        "proof",
        "generate",
        *opened.args(),
        *scope_args(),
        "--revision",
        REVISION,
        "--timestamp",
        TIMESTAMP,
        "--evaluation-date",
        EVALUATION_DATE,
        "--output-dir",
        str(out),
    )
    assert status == 0
    (package,) = sorted((out / "proofs").iterdir())
    return package


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under ``root`` by relative path, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- A small world of a would-be store and a git repository ------------------------------


def _git(repo: Path, *args: str) -> str:
    import subprocess

    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@dataclass(frozen=True)
class World:
    """A would-be store, its git repository, a configuration and an empty case.

    The store's content directory is the git repository and the configuration
    names it as the implementation repository. Test outcomes in the store
    record the repository's HEAD revision (``head``) or another value.
    """

    store: Path
    content: Path
    head: str
    config: Path
    case: Path

    def args(self, *, config: bool = True) -> list[str]:
        arguments = ["--case", str(self.case), "--current", str(self.store)]
        return [*arguments, "--config", str(self.config)] if config else arguments


def make_world(
    tmp_path: Path,
    *,
    outcomes: tuple[str, ...] = ("head",),
    absent_specification: bool = False,
    dangling_strong: bool = False,
) -> World:
    """Build the world. Each name in ``outcomes`` is one outcome with two evidence edges.

    The name ``head`` records the repository's HEAD revision and any other name
    records the revision of ``OTHER_REVISION``. ``absent_specification`` adds a
    Confirms edge to a specification that the store does not hold.
    ``dangling_strong`` adds an Implements edge from an implementation that the
    store does not hold to the requirement.
    """
    store = tmp_path / "store"
    content = store / "content"
    (store / "nodes").mkdir(parents=True)
    (store / "edges").mkdir()
    content.mkdir()
    for name in ("req", "api", "body", "spec", "impl"):
        (content / f"{name}.txt").write_text(f"the {name}\n", encoding="utf-8")
    for index in range(len(outcomes)):
        (content / f"outcome-{index}.txt").write_text(f"passed {index}\n", encoding="utf-8")
    _git(content, "init", "-q")
    _git(content, "config", "user.email", "test@example.invalid")
    _git(content, "config", "user.name", "Test")
    _git(content, "add", ".")
    _git(content, "commit", "-q", "-m", "content")
    head = _git(content, "rev-parse", "HEAD")

    (store / "nodes" / "requirements.toml").write_text(
        'kind = "Requirement"\n[nodes]\n"SREQ-1" = { contentHash = "req.txt" }\n', encoding="utf-8"
    )
    (store / "nodes" / "implementations.toml").write_text(
        'kind = "Implementation"\n[nodes]\n'
        '"pkg.fn" = { apiHash = "api.txt", bodyHash = "body.txt" }\n',
        encoding="utf-8",
    )
    (store / "nodes" / "specifications.toml").write_text(
        'kind = "TestSpecification"\n[nodes]\n'
        '"TS-1" = { specHash = "spec.txt", implHash = "impl.txt" }\n',
        encoding="utf-8",
    )
    lines = ['kind = "TestOutcome"', "[nodes]"]
    confirms, witnesses = [], []
    for index, which in enumerate(outcomes):
        revision = head if which == "head" else OTHER_REVISION
        lines.append(
            f'"run-{index}/TS-1" = {{ contentHash = "outcome-{index}.txt", '
            f'result = "passed", revision = "{revision}" }}'
        )
        confirms.append(f'["run-{index}/TS-1", "TS-1"]')
        witnesses.append(f'["run-{index}/TS-1", "pkg.fn"]')
    if outcomes:
        (store / "nodes" / "outcomes.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if absent_specification:
        confirms.append('["run-0/TS-1", "TS-GONE"]')
    implements = '["pkg.fn", "SREQ-1"]' + (', ["pkg.gone", "SREQ-1"]' if dangling_strong else "")
    edges = ["[edges]", 'Verifies = [["TS-1", "SREQ-1"]]', f"Implements = [{implements}]"]
    if confirms:
        edges.append(f"Confirms = [{', '.join(confirms)}]")
    if witnesses:
        edges.append(f"Witnesses = [{', '.join(witnesses)}]")
    (store / "edges" / "coverage.toml").write_text("\n".join(edges) + "\n", encoding="utf-8")

    # The store names each anchor's repository by the path of its content directory.
    name = str(content)
    path = tmp_path / "cfg" / "affirmatrix.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump({"repositories": {name: name}, "implementation": name}), encoding="utf-8"
    )
    root = tmp_path / "case"
    assert main(["case", "init", "--case", str(root)]) == 0
    return World(store=store, content=content, head=head, config=path, case=root)


def make_dirty(world: World) -> None:
    """Leave one untracked file in the implementation repository."""
    (world.content / "stray.txt").write_text("not committed\n", encoding="utf-8")
