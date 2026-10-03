"""Shared helpers of the specifications of need types, run boards and path prefixes.

Not a specification. The modules that realize specifications import these
helpers. They build small synthetic exports and run bundles in a temporary
directory, so a test shows the shape that matters and nothing else. The shapes
follow what a documentation build gives: a need of another type (a test
procedure, for example) holds the keys of a test case with the value null.

The outcome extractor is built here from its inputs and not through the
command line, so a test reads one component. The tests that go through the
command line use the frozen fixtures of ``evidence_support``.

Every expected value in a test is computed from the fixture the test builds,
never by calling the extractor.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from affirmatrix import config, gates, graph
from affirmatrix.records import (
    ContentAnchor,
    EdgeRecord,
    LinkState,
    NodeRecord,
)

from .capture_support import export_of

CHECKOUT = "firmware"
RUN_NAME = "run-one"
REVISION = "a" * 40
SCENARIO = "kernel.api"
REQUIREMENT = "SREQ-1"
SPECIFICATION = "TC-1"
IMPLEMENTATION = "IMPL-1"
EVALUATION_DATE = date(2026, 6, 1)
AFFIRMED = bytes(range(32))

#: One result of a board: the test identifier and the status of the artifact.
Result = tuple[str, str]
#: One suite of a run artifact: scenario, platform and the results of the suite.
Suite = tuple[str, str, Sequence[Result]]


def result_identifier(scenario: str, suite: str, function: str) -> str:
    """The identifier a run artifact gives a test: the scenario, the suite and the function.

    The function loses its ``test_`` prefix. The parts are joined by dots.
    """
    return f"{scenario}.{suite}.{function.removeprefix('test_')}"


def case_need(
    ident: str, suite: str, function: str, *, type: str = "test_case", **more: Any
) -> dict[str, Any]:
    """A test-case need that verifies the one requirement of the fixtures."""
    need: dict[str, Any] = {
        "id": ident,
        "type": type,
        "suite": suite,
        "test_function": function,
        "test_module": f"tests/{suite}",
        "verifies": [REQUIREMENT],
    }
    need.update(more)
    return need


def procedure_need(area: str, step: str) -> dict[str, Any]:
    """A need of the type test_procedure, as a documentation build gives it.

    It has the keys of a test case, all null, and no link. Its identifier is
    ``test-proc-<area>_api_procedures-<step>``.
    """
    return {
        "id": f"test-proc-{area}_api_procedures-{step}",
        "type": "test_procedure",
        "suite": None,
        "test_function": None,
        "test_module": None,
        "verifies": [],
        "satisfies": [],
    }


def implementation_need(
    ident: str, *, type: str = "impl", satisfies: Any = (REQUIREMENT,)
) -> dict[str, Any]:
    """An implementation need that satisfies the requirements named in ``satisfies``."""
    return {
        "id": ident,
        "type": type,
        "title": ident.lower(),
        "satisfies": list(satisfies) if isinstance(satisfies, tuple) else satisfies,
    }


def write_bundle(directory: Path, suites: Sequence[Suite], *, name: str = RUN_NAME) -> Path:
    """A run bundle that holds one run artifact with ``suites``.

    The bundle records a clean checkout, named :data:`CHECKOUT`, at
    :data:`REVISION`, and the run's name.
    """
    directory.mkdir(parents=True, exist_ok=True)
    document = {
        "testsuites": [
            {
                "name": scenario,
                "platform": platform,
                "testcases": [
                    {"identifier": identifier, "status": status} for identifier, status in results
                ],
            }
            for scenario, platform, results in suites
        ]
    }
    (directory / "twister.json").write_text(json.dumps(document), encoding="utf-8")
    (directory / "run.name").write_text(f"{name}\n", encoding="utf-8")
    (directory / f"{CHECKOUT}.sha").write_text(f"{REVISION}\n", encoding="utf-8")
    (directory / f"{CHECKOUT}.dirty").write_text("", encoding="utf-8")
    return directory


def outcome_extractor(
    bundle: Path,
    specifications: Path,
    implementations: Path | None = None,
    *,
    specification_types: Sequence[str] | None = None,
    implementation_types: Sequence[str] | None = None,
):
    """The outcome extractor over one bundle and the exports, with the types given.

    The Doxygen directory of each input is not read by the outcome extractor, so
    a name that does not exist stands in for it. The extractor is imported here,
    so that one that does not exist yet fails a test and not the collection.
    """
    from affirmatrix.sources.outcomes import TwisterOutcomeExtractor

    unused = bundle.parent / "no-doxygen"
    return TwisterOutcomeExtractor(
        [bundle],
        checkout=CHECKOUT,
        specifications=config.SpecificationInputs(
            export=specifications,
            doxygen=unused,
            types=None if specification_types is None else frozenset(specification_types),
        ),
        implementations=(
            None
            if implementations is None
            else config.ImplementationInputs(
                export=implementations,
                doxygen=unused,
                types=None if implementation_types is None else frozenset(implementation_types),
            )
        ),
    )


def edge_pairs(extractor: Any, kind: str) -> list[tuple[str, str]]:
    """The edges of one kind that the extractor supplies, as sorted (from, to) pairs."""
    return sorted((e.from_id, e.to_id) for e in extractor.edges() if e.kind == kind)


def outcome_ids(extractor: Any) -> list[str]:
    """The local identifiers of the outcomes, in the order supplied."""
    return [node.local_id for node in extractor.nodes()]


def exports(tmp_path: Path, cases: Sequence[Mapping[str, Any]]) -> tuple[Path, Path]:
    """A test-case export of ``cases`` and an implementation export of one need.

    The implementation need satisfies the requirement that every test-case need
    of the fixtures verifies.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    specifications = export_of(tmp_path, [dict(case) for case in cases], "cases")
    implementations = export_of(tmp_path, [implementation_need(IMPLEMENTATION)], "impls")
    return specifications, implementations


# --- the verdict of a requirement, from outcomes the extractor reads ------------------


class _Records:
    """A record source over fixed lists."""

    def __init__(self, nodes: Sequence[NodeRecord], edges: Sequence[EdgeRecord]) -> None:
        self._nodes = tuple(nodes)
        self._edges = tuple(edges)

    def nodes(self) -> Iterator[NodeRecord]:
        return iter(self._nodes)

    def edges(self) -> Iterator[EdgeRecord]:
        return iter(self._edges)


def _node(local_id: str, kind: str, names: tuple[str, ...]) -> NodeRecord:
    anchors = {
        name: ContentAnchor(
            digest=bytes([index + 1]) * 32, repository="repo", path="file", locator="file"
        )
        for index, name in enumerate(names)
    }
    return NodeRecord(local_id, kind, anchors)


def built_graph(extractor: Any) -> graph.Graph:
    """The graph of one leaf requirement, its specification and implementation, and the outcomes.

    The requirement is verified by the specification and implemented by the
    implementation, both over active edges. The outcomes, and the Confirms and
    Witnesses edges, are the ones the extractor supplies.
    """
    nodes = [
        _node(REQUIREMENT, "Requirement", ("contentHash",)),
        _node(SPECIFICATION, "TestSpecification", ("specHash", "implHash")),
        _node(IMPLEMENTATION, "Implementation", ("apiHash", "bodyHash")),
        *extractor.nodes(),
    ]
    strong = [
        EdgeRecord(SPECIFICATION, REQUIREMENT, "Verifies", LinkState.ACTIVE, AFFIRMED),
        EdgeRecord(IMPLEMENTATION, REQUIREMENT, "Implements", LinkState.ACTIVE, AFFIRMED),
    ]
    return graph.build(_Records(nodes, [*strong, *extractor.edges()]))


def package_report(built: graph.Graph) -> gates.CoverageReport:
    """The package gate over the graph, at the revision the bundles record."""
    return gates.package_gate(built, evaluation_date=EVALUATION_DATE, current_revision=REVISION)
