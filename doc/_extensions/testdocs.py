"""Render the test specification and the test report from the tests themselves.

The test specification is the docstrings of the tests: a test whose docstring
carries a ``:test-id:`` field is one specification, its first line the title,
the paragraphs below it the claim, and its ``:verifies:`` fields the
requirements it demonstrates. This extension reads the test modules with
``ast`` (it never imports them) and writes one ``tspec`` need per such test.

The test report is the JUnit XML of a pytest run. Each test case becomes one
``outcome`` need with its result, and a ``reports`` link to the specification
of the same test when the test has one. The run is a directory in the shape of
a run bundle: ``junit.xml`` beside the revision of the checkout, its dirty
flag, the run name and the command (``python -m doc test-run`` makes one).

Both pages are generated at ``builder-inited`` into ``_generated/`` inside
the document's source directory (ignored by git) and pulled in with
``.. include::``. The output is sorted and carries no time in any need field,
so ``needs.json`` changes only when the tests or the results change.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.errors import ExtensionError

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
DEFAULT_RUN = REPO_ROOT / "build" / "test-run"
RUN_ENV = "AFFIRMATRIX_TEST_RUN"
CHECKOUT = "affirmatrix"
GENERATED = "_generated"

#: sphinx-needs reads ``[[...]]`` in a title as a dynamic function. A word
#: joiner between the brackets keeps the text and stops the parse.
_DYNAMIC_OPEN = "[["
_SAFE_OPEN = "[⁠["


@dataclass(frozen=True, slots=True)
class Specification:
    """One test whose docstring carries a ``:test-id:`` field."""

    test_id: str
    verifies: tuple[str, ...]
    title: str
    body: str
    nodeid: str
    module: str


def collect_specifications(tests_root: Path = TESTS_ROOT) -> list[Specification]:
    """Every test function with a ``:test-id:`` docstring field, sorted by id.

    A second test with the same id is an error, named with both node ids.
    """
    found: dict[str, Specification] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        module = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test"):
                continue
            docstring = ast.get_docstring(node, clean=False)
            if not docstring or not _has_field(docstring, ":test-id:"):
                continue
            spec = _specification(docstring, f"{module}::{node.name}", module)
            if spec.test_id in found:
                raise ExtensionError(
                    f"{spec.test_id} is the test id of both {found[spec.test_id].nodeid} "
                    f"and {spec.nodeid}"
                )
            found[spec.test_id] = spec
    return [found[key] for key in sorted(found)]


def _has_field(docstring: str, field: str) -> bool:
    """Whether a docstring line starts with the field (a mention in prose does not count)."""
    return any(line.strip().startswith(field) for line in docstring.splitlines())


def _specification(docstring: str, nodeid: str, module: str) -> Specification:
    lines = inspect.cleandoc(docstring).splitlines()
    test_id = ""
    verifies: list[str] = []
    prose: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(":test-id:"):
            test_id = stripped.removeprefix(":test-id:").strip()
        elif stripped.startswith(":verifies:"):
            verifies.append(stripped.removeprefix(":verifies:").strip())
        else:
            prose.append(line)
    if not test_id:
        raise ExtensionError(f"{nodeid}: the :test-id: field is empty")
    if not verifies:
        raise ExtensionError(f"{nodeid} ({test_id}) names no :verifies: requirement")
    title = prose[0].strip() if prose else test_id
    body = "\n".join(prose[1:]).strip()
    return Specification(test_id, tuple(verifies), title, body, nodeid, module)


def _safe(text: str) -> str:
    return text.replace(_DYNAMIC_OPEN, _SAFE_OPEN)


def _indent(text: str, prefix: str = "   ") -> str:
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def specification_rst(specs: list[Specification]) -> str:
    """The test-specification page body: one section per module, one need per test."""
    out: list[str] = []
    by_module: dict[str, list[Specification]] = {}
    for spec in specs:
        by_module.setdefault(spec.module, []).append(spec)
    for module in sorted(by_module):
        heading = f"``{module}``"
        out += [heading, "-" * len(heading), ""]
        for spec in by_module[module]:
            out += [
                f".. tspec:: {_safe(spec.title)}",
                f"   :id: {spec.test_id}",
                f"   :verifies: {', '.join(spec.verifies)}",
                f"   :nodeid: {spec.nodeid}",
                "",
            ]
            if spec.body:
                out += [_indent(spec.body), ""]
    return "\n".join(out) + "\n"


@dataclass(frozen=True, slots=True)
class Result:
    """One test case of a JUnit XML report."""

    nodeid: str
    module: str
    result: str


def _nodeid(classname: str, name: str) -> tuple[str, str]:
    module = classname.replace(".", "/") + ".py"
    return f"{module}::{name}", module


def read_results(junit: Path) -> tuple[list[Result], dict[str, str]]:
    """The test cases of a JUnit XML file, sorted by node id, and the run's totals."""
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    results: list[Result] = []
    stamp = ""
    for suite in suites:
        stamp = stamp or suite.get("timestamp", "")
        for case in suite.iter("testcase"):
            nodeid, module = _nodeid(case.get("classname", ""), case.get("name", ""))
            if case.find("failure") is not None:
                outcome = "failed"
            elif case.find("error") is not None:
                outcome = "error"
            elif case.find("skipped") is not None:
                outcome = "skipped"
            else:
                outcome = "passed"
            results.append(Result(nodeid, module, outcome))
    results.sort(key=lambda r: r.nodeid)
    totals = {"timestamp": stamp}
    for kind in ("passed", "failed", "error", "skipped"):
        totals[kind] = str(sum(1 for r in results if r.result == kind))
    return results, totals


def outcome_id(nodeid: str) -> str:
    """A stable need id for one test case, from its node id alone."""
    return "SEG-OUT-" + hashlib.sha256(nodeid.encode("utf-8")).hexdigest()[:12].upper()


def _record(run: Path, name: str) -> str:
    path = run / name
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def report_rst(run: Path, specs: list[Specification]) -> str:
    """The test-report page body: the run's header, then one need per test case."""
    junit = run / "junit.xml"
    if not junit.is_file():
        return (
            ".. admonition:: No test run given\n\n"
            f"   No ``junit.xml`` was found in ``{run}``. Make a run with\n"
            "   ``python -m doc test-run``, or name one with\n"
            f"   ``python -m doc build --test-run DIR`` or ``{RUN_ENV}=DIR``.\n"
        )
    results, totals = read_results(junit)
    by_nodeid = {spec.nodeid: spec.test_id for spec in specs}
    revision = _record(run, f"{CHECKOUT}.sha") or "not recorded"
    if not (run / f"{CHECKOUT}.dirty").is_file():
        clean = "not recorded"
    elif _record(run, f"{CHECKOUT}.dirty"):
        clean = "dirty"
    else:
        clean = "clean"
    name = _record(run, "run.name") or "not recorded"
    out = [
        ".. list-table:: The run this report shows",
        "   :stub-columns: 1",
        "",
        f"   * - Run name\n     - ``{name}``",
        f"   * - Started\n     - {totals['timestamp'] or 'not recorded'}",
        f"   * - Revision\n     - ``{revision}``",
        f"   * - Working tree\n     - {clean}",
        f"   * - Passed\n     - {totals['passed']}",
        f"   * - Failed\n     - {totals['failed']}",
        f"   * - Errors\n     - {totals['error']}",
        f"   * - Skipped\n     - {totals['skipped']}",
        "",
    ]
    by_module: dict[str, list[Result]] = {}
    for result in results:
        by_module.setdefault(result.module, []).append(result)
    for module in sorted(by_module):
        heading = f"``{module}``"
        out += [heading, "-" * len(heading), ""]
        for result in by_module[module]:
            out += [
                f".. outcome:: {_safe(result.nodeid.split('::', 1)[1])}",
                f"   :id: {outcome_id(result.nodeid)}",
                f"   :result: {result.result}",
                f"   :nodeid: {result.nodeid}",
            ]
            if result.nodeid in by_nodeid:
                out.append(f"   :reports: {by_nodeid[result.nodeid]}")
            out.append("")
    return "\n".join(out) + "\n"


def run_directory() -> Path:
    """The run the report shows: ``AFFIRMATRIX_TEST_RUN``, else ``build/test-run``."""
    given = os.environ.get(RUN_ENV)
    return Path(given).resolve() if given else DEFAULT_RUN


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def _generate(app: Sphinx) -> None:
    srcdir = Path(app.srcdir)
    specs = collect_specifications()
    if app.config.testdocs_page == "specification":
        _write(srcdir / GENERATED / "specifications.inc", specification_rst(specs))
    elif app.config.testdocs_page == "report":
        _write(srcdir / GENERATED / "report.inc", report_rst(run_directory(), specs))


def setup(app: Sphinx) -> dict:
    # The fields ``nodeid`` and ``result`` are declared in doc/needs_config.toml,
    # for every document, so that the other documents import them too.
    app.add_config_value("testdocs_page", "", "env")
    app.connect("builder-inited", _generate)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
