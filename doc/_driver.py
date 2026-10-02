"""``python -m doc`` — registry-driven build orchestrator for the doc federation.

Replaces cygnus's CMake layer (which provided phony target factories, not
incrementality). The dependency structure is fixed and two layers deep, so it
is encoded literally:

  stage 1  build EVERY document once, publishing objects.inv + needs.json
           into the shared deploy tree;
  stage 2  build the SELECTED documents again — now every cross-document
           reference (intersphinx, needs_external_needs) resolves against the
           stage-1 indices. Doctrees are reused between stages.

The documents of a stage build at the same time and rewrite their indices in
the deploy tree as they finish. So no document reads the deploy tree: before
each stage the driver copies every index there into a snapshot directory,
and the documents of the stage read the snapshot. A stage thus reads the
indices of the stage before it, whole, whichever document finishes first.

Sphinx's own doctree cache provides incrementality; this driver provides
selection, the barrier, parallelism, and cleanup.

Commands:
  python -m doc build [DOC ...] [-b html] [--no-index] [-j N] [--test-run DIR]
  python -m doc test-run [--output DIR]
  python -m doc live DOC
  python -m doc site DIR
  python -m doc check-site DIR --base-url URL
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
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

import yaml

DOC_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DOC_ROOT.parent
BUILD_ROOT = REPO_ROOT / "build" / "doc"
DEPLOY = BUILD_ROOT / "deploy"
#: The indices a stage reads: a copy of the deploy tree's indices, taken
#: before the stage starts, in the deploy tree's layout.
INDICES = BUILD_ROOT / "_indices"
INDEX_FILES = ("objects.inv", "needs.json")
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


def snapshot_indices(docs: list[str]) -> None:
    """Copy the indices the deploy tree holds now into ``INDICES``.

    Called while no document builds, so every file copied is whole. A
    document with no index yet is left out, as the deploy tree has none.
    """
    shutil.rmtree(INDICES, ignore_errors=True)
    for doc in docs:
        for name in INDEX_FILES:
            source = DEPLOY / doc / "html" / name
            if source.is_file():
                target = INDICES / doc / "html" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)


def sphinx(doc: str, builder: str, *, out: Path, extra_env: dict | None = None) -> int:
    src = DOC_ROOT / doc
    doctrees = BUILD_ROOT / doc / "doctrees"
    logdir = BUILD_ROOT / doc
    logdir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"AFFIRMATRIX_DOC_DEPLOY": str(INDICES)} | (extra_env or {})
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
    snapshot_indices(doc_ids(registry()))
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


def cmd_site(args: argparse.Namespace) -> None:
    """Assemble the published site: each document's html/ tree and the landing page.

    The layout is the deploy tree's, ``<document>/html/``, so every link the
    build wrote against ``DOC_BASE_URL`` resolves when the site is served there.
    """
    out = Path(args.output).resolve()
    if out.exists():
        sys.exit(f"{out} exists; give a new directory")
    for doc in doc_ids(registry()):
        html = DEPLOY / doc / "html"
        if not html.is_dir():
            sys.exit(f"{doc} is not built — run `python -m doc build` first")
        shutil.copytree(html, out / doc / "html")
    shutil.copyfile(DOC_ROOT / "site" / "index.html", out / "index.html")
    print(f"site assembled in {out}")


class _Links(HTMLParser):
    """The href and src values of one page, and the ids it defines."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name in ("href", "src"):
                self.links.append(value)
            elif name == "id":
                self.ids.add(value)


def cmd_check_site(args: argparse.Namespace) -> None:
    """Check every link inside an assembled site, offline.

    A relative link resolves against its page; a link that starts with the
    base URL resolves against the site root. The target file must exist, and
    a fragment must name an id on the target page. Links to other hosts are
    not fetched.
    """
    root = Path(args.site).resolve()
    base = args.base_url.rstrip("/") + "/"
    pages: dict[Path, _Links] = {}

    def parsed(page: Path) -> _Links:
        if page not in pages:
            parser = _Links()
            parser.feed(page.read_text(encoding="utf-8", errors="replace"))
            pages[page] = parser
        return pages[page]

    checked = 0
    broken: list[str] = []
    for page in sorted(root.rglob("*.html")):
        for link in parsed(page).links:
            if link.startswith(("#", "mailto:", "javascript:", "data:")):
                continue
            if link.startswith(base):
                relative, origin = link[len(base) :], root
            elif "://" in link or link.startswith("//"):
                continue
            else:
                relative, origin = link, page.parent
            parts = urllib.parse.urlsplit(relative)
            target = (origin / urllib.parse.unquote(parts.path)).resolve()
            if target.is_dir():
                target = target / "index.html"
            checked += 1
            where = f"{link} (in {page.relative_to(root)})"
            if not target.is_file():
                broken.append(f"missing target: {where}")
            elif parts.fragment and target.suffix == ".html":
                if urllib.parse.unquote(parts.fragment) not in parsed(target).ids:
                    broken.append(f"missing anchor: {where}")
    for line in broken:
        print(line)
    print(f"{checked} links checked, {len(broken)} broken")
    if broken:
        raise SystemExit(1)


def cmd_clean(args: argparse.Namespace) -> None:
    targets = args.docs or doc_ids(registry())
    for doc in targets:
        for path in (BUILD_ROOT / doc, DEPLOY / doc, INDICES / doc):
            shutil.rmtree(path, ignore_errors=True)
    if not args.docs:
        shutil.rmtree(INDICES, ignore_errors=True)
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

    p_site = sub.add_parser("site", help="assemble the built federation into a site directory")
    p_site.add_argument("output", metavar="DIR", help="the new site directory")
    p_site.set_defaults(func=cmd_site)

    p_check = sub.add_parser("check-site", help="check every link inside an assembled site")
    p_check.add_argument("site", metavar="DIR", help="the assembled site")
    p_check.add_argument(
        "--base-url",
        required=True,
        help="the URL the site is built for (the value of DOC_BASE_URL)",
    )
    p_check.set_defaults(func=cmd_check_site)

    p_clean = sub.add_parser("clean", help="remove build intermediates and deploy output")
    p_clean.add_argument("docs", nargs="*")
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args(argv)
    args.func(args)
