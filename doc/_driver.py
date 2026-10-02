"""``python -m doc`` — registry-driven build orchestrator for the doc federation.

Replaces cygnus's CMake layer (which provided phony target factories, not
incrementality). The dependency structure is fixed and two layers deep, so it
is encoded literally:

  stage 1  build EVERY document once, publishing objects.inv + needs.json
           into the shared deploy tree;
  stage 2  build the SELECTED documents again — now every cross-document
           reference (intersphinx, needs_external_needs) resolves against the
           stage-1 indices. Doctrees are reused between stages.

Sphinx's own doctree cache provides incrementality; this driver provides
selection, the barrier, parallelism, and cleanup.

Commands:
  python -m doc build [DOC ...] [-b html] [--no-index] [-j N] [--test-run DIR]
  python -m doc test-run [--output DIR]
  python -m doc live DOC
  python -m doc clean [DOC ...]

The test report shows one pytest run: ``--test-run DIR``, else the
environment variable ``AFFIRMATRIX_TEST_RUN``, else ``build/test-run``.
``test-run`` makes such a run, in the shape of a run bundle.
"""

from __future__ import annotations

import argparse
import os
import resource
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

DOC_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DOC_ROOT.parent
BUILD_ROOT = REPO_ROOT / "build" / "doc"
DEPLOY = BUILD_ROOT / "deploy"
TEST_RUN = REPO_ROOT / "build" / "test-run"
RUN_ENV = "AFFIRMATRIX_TEST_RUN"
#: The memory cap and the time limit of a test run: a runaway test is a
#: killed process, not a machine out of memory.
RUN_MEMORY_BYTES = 1024**3
RUN_TIMEOUT_SECONDS = 300


def registry() -> dict:
    with open(DOC_ROOT / "documents.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def doc_ids(reg: dict) -> list[str]:
    return [d["id"] for d in reg["documents"]]


def sphinx(doc: str, builder: str, *, out: Path, extra_env: dict | None = None) -> int:
    src = DOC_ROOT / doc
    doctrees = BUILD_ROOT / doc / "doctrees"
    logdir = BUILD_ROOT / doc
    logdir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"AFFIRMATRIX_DOC_DEPLOY": str(DEPLOY)} | (extra_env or {})
    cmd = [
        sys.executable, "-m", "sphinx",
        "-b", builder,
        "-c", str(src),
        "-d", str(doctrees),
        "-w", str(logdir / f"{builder}.log"),
        str(src), str(out),
    ]
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def build_stage(docs: list[str], builder: str, jobs: int, label: str) -> None:
    failures = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(sphinx, d, builder, out=DEPLOY / d / builder): d for d in docs
        }
        for future, doc in futures.items():
            if future.result() != 0:
                failures.append(doc)
    if failures:
        sys.exit(f"{label} failed for: {', '.join(failures)}")


def cmd_build(args: argparse.Namespace) -> None:
    if args.test_run:
        os.environ[RUN_ENV] = str(Path(args.test_run).resolve())
    reg = registry()
    everything = doc_ids(reg)
    selected = args.docs or everything
    unknown = set(selected) - set(everything)
    if unknown:
        sys.exit(f"unknown document(s): {', '.join(sorted(unknown))} (see doc/documents.yaml)")
    if not args.no_index:
        print(f"== stage 1: indices for {len(everything)} documents")
        build_stage(everything, "html", args.jobs, "stage 1")
    print(f"== stage 2: {args.builder} for {', '.join(selected)}")
    build_stage(selected, args.builder, args.jobs, "stage 2")
    print(f"done — output under {DEPLOY}")


def _git(*argv: str) -> str:
    proc = subprocess.run(["git", *argv], cwd=REPO_ROOT, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def _cap_memory() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (RUN_MEMORY_BYTES, RUN_MEMORY_BYTES))


def cmd_test_run(args: argparse.Namespace) -> None:
    """Run the test suite once and record it in the shape of a run bundle.

    The directory holds ``junit.xml`` (pytest's own JUnit report), the
    checkout's revision and dirty flag (``affirmatrix.sha``,
    ``affirmatrix.dirty``, empty when clean), the run name and the command.
    The revision is taken before the run, so it names what was tested.
    """
    out = Path(args.output).resolve() if args.output else TEST_RUN
    out.mkdir(parents=True, exist_ok=True)
    revision = _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain")
    cmd = [
        sys.executable, "-m", "pytest", "-q", "-o", "addopts=",
        f"--junitxml={out / 'junit.xml'}",
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, preexec_fn=_cap_memory, timeout=RUN_TIMEOUT_SECONDS
        )
        code = proc.returncode
    except subprocess.TimeoutExpired:
        sys.exit(f"the test run took longer than {RUN_TIMEOUT_SECONDS} s and was stopped")
    (out / "affirmatrix.sha").write_text(revision, encoding="utf-8")
    (out / "affirmatrix.dirty").write_text(dirty, encoding="utf-8")
    name = args.name or f"pytest-{revision.strip()[:12] or 'unknown'}"
    (out / "run.name").write_text(name + "\n", encoding="utf-8")
    (out / "command.txt").write_text(" ".join(cmd[1:]) + "\n", encoding="utf-8")
    print(f"test run recorded in {out} (pytest exit {code})")
    raise SystemExit(code)


def cmd_live(args: argparse.Namespace) -> None:
    doc = args.doc
    src = DOC_ROOT / doc
    out = DEPLOY / doc / "html"
    env = os.environ | {"AFFIRMATRIX_DOC_DEPLOY": str(DEPLOY)}
    cmd = [
        sys.executable, "-m", "sphinx_autobuild",
        "-b", "html",
        "-c", str(src),
        "--watch", str(src),
        str(src), str(out),
    ]
    raise SystemExit(subprocess.run(cmd, env=env).returncode)


def cmd_serve(args: argparse.Namespace) -> None:
    """Serve the built federation (deploy tree) over HTTP."""
    import http.server

    if not DEPLOY.exists():
        sys.exit("nothing built yet — run `python -m doc build` first")
    handler = http.server.SimpleHTTPRequestHandler

    class Handler(handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DEPLOY), **kw)

    print(f"serving {DEPLOY} at http://localhost:{args.port}/ (landing: /manual/html/)")
    http.server.ThreadingHTTPServer(("", args.port), Handler).serve_forever()


def cmd_clean(args: argparse.Namespace) -> None:
    targets = args.docs or doc_ids(registry())
    for doc in targets:
        for path in (BUILD_ROOT / doc, DEPLOY / doc):
            shutil.rmtree(path, ignore_errors=True)
    if not args.docs and BUILD_ROOT.exists() and not any(BUILD_ROOT.iterdir()):
        shutil.rmtree(BUILD_ROOT.parent, ignore_errors=True)
    print("cleaned")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m doc")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="two-stage build of the document federation")
    p_build.add_argument("docs", nargs="*", help="documents to build (default: all)")
    p_build.add_argument("-b", "--builder", default="html")
    p_build.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 2)
    p_build.add_argument(
        "--no-index", action="store_true",
        help="skip stage 1 (fast rebuild against existing indices)",
    )
    p_build.add_argument(
        "--test-run", metavar="DIR",
        help="the test run the test report shows (default: $AFFIRMATRIX_TEST_RUN, "
        "else build/test-run)",
    )
    p_build.set_defaults(func=cmd_build)

    p_run = sub.add_parser("test-run", help="run the tests once, recorded for the test report")
    p_run.add_argument(
        "--output", metavar="DIR", help="where to record it (default build/test-run)"
    )
    p_run.add_argument("--name", help="the run name (default pytest-<revision>)")
    p_run.set_defaults(func=cmd_test_run)

    p_live = sub.add_parser("live", help="sphinx-autobuild live preview for one document")
    p_live.add_argument("doc")
    p_live.set_defaults(func=cmd_live)

    p_serve = sub.add_parser("serve", help="serve the built federation over HTTP")
    p_serve.add_argument("-p", "--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_clean = sub.add_parser("clean", help="remove build intermediates and deploy output")
    p_clean.add_argument("docs", nargs="*")
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args(argv)
    args.func(args)
