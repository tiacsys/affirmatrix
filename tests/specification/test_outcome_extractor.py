"""Verification suite for the outcome extractor over a twister run.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests read the frozen evidence fixture under ``tests/fixtures/toolbox_evidence/``:
the run artifact (a twister report), the two records kept beside it (the full
revision and the run name), and the two need exports that give the mapping and
the witnesses. The fixture holds four scenarios of 19 results each, 76 in all:
65 passed and 11 skipped.

The tests compute every expected value from the fixture files, never by calling
the extractor. A result reaches its test-case need when the scenario, the suite
and the test function (without its ``test_`` prefix), joined by dots, equal the
result's test identifier. The tests form that identifier and compare it. They
never split an identifier or an outcome identity to recover its parts. An
expected content digest is the SHA-256 of the canonical record, a JSON object
of ``result``, ``run`` and ``specification`` with sorted keys and no blanks.
Every variant of an input is built in the test, in a temporary directory, by
copying the whole fixture tree (the test cannot know which of its files the
extractor opens) and editing the copy. The extractor is imported inside the
helper that builds it, so an extractor that does not exist yet is an expected
failure of the test, not of the collection.

An error for what the inputs alone show (a missing revision record) is raised
when the extractor is built. An error for one result is raised before the
stream is complete, either when the extractor is built or when the records are
taken, and never skipped: the helpers build the extractor and drain the stream
in one call, so a test does not depend on which of the two it is.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from affirmatrix import config
from affirmatrix.records import TestResult

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "toolbox_evidence"
ARTIFACT = Path("twister") / "twister.json"
REVISION_RECORD = Path("revisions") / "toolbox.sha"
NAME_RECORD = Path("revisions") / "run.name"
SPECIFICATION_EXPORT = Path("needs") / "test-specification" / "needs.json"
SPECIFICATION_XML = Path("xml") / "dox-safe-data-testspec"
IMPLEMENTATION_EXPORT = Path("needs") / "api-traceability" / "needs.json"
IMPLEMENTATION_XML = Path("xml") / "dox-safe-data-api"
REPOSITORY = "toolbox"
RUN_NAME = "twister-run-2026-09-29"
PLATFORM = "native_sim-native-64"
REVISION = "5847f3fdca777b8d62615d84b8926fdc8ce125ed"
BASE = "safe_data.api"
SCENARIOS = (BASE, "safe_data.api.plain", "safe_data.api.timeout", "safe_data.api.strict")
INIT_AND_VERIFY = "TC_SAFE_DATA_INIT_AND_VERIFY"
SELFTEST = "TC_SAFE_DATA_SELFTEST"
WRITE_OBSERVES = "TC_SAFE_DATA_WRITE_OBSERVES_OVERWRITTEN_CORRUPTION"
INIT_RESULT = "safe_data.api.safe_data.init_and_verify"
SELFTEST_RESULT = "safe_data.api.safe_data.selftest"
INIT_DIGEST = "b21f9c415e6b2de8ea131a18c709acdface0c91c976041b752ae382bf3128869"


class Result(NamedTuple):
    """One result of the artifact and what the fixture's export says it maps to."""

    scenario: str
    platform: str
    identifier: str
    status: str
    specification: str


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _needs(export: Path) -> dict[str, dict[str, Any]]:
    (version,) = _load(export)["versions"].values()
    return version["needs"]


def _edit_json(tree: Path, relative: Path, edit: Callable[[Any], None]) -> None:
    """Rewrite one JSON file of a copied tree after ``edit`` has changed its document."""
    path = tree / relative
    document = _load(path)
    edit(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def _tree(tmp_path: Path, name: str = "tree") -> Path:
    """A copy of the whole fixture, to be edited."""
    copy = tmp_path / name
    shutil.copytree(FIXTURE, copy)
    return copy


def _edit_needs(edit: Callable[[dict[str, dict[str, Any]]], None]) -> Callable[[Any], None]:
    def apply(document: Any) -> None:
        (version,) = document["versions"].values()
        edit(version["needs"])

    return apply


def _set_status(identifier: str, status: str) -> Callable[[Any], None]:
    """An edit of the artifact that gives the result ``identifier`` the status ``status``."""

    def edit(document: Any) -> None:
        (case,) = [
            case
            for suite in document["testsuites"]
            for case in suite["testcases"]
            if case["identifier"] == identifier
        ]
        case["status"] = status

    return edit


def _token(platform: str) -> str:
    """The platform as one segment of a run identifier: no slash."""
    return platform.replace("/", "-")


def _run_identifier(scenario: str, platform: str = PLATFORM, name: str = RUN_NAME) -> str:
    return f"{name}-{platform}-{scenario}"


def _expected(tree: Path = FIXTURE) -> list[Result]:
    """Every result of the tree's artifact with its need, formed and compared, never split.

    A need's test identifier is the scenario, the suite and the test function
    without ``test_``, joined by dots. Exactly one need must form each result's.
    """
    needs = _needs(tree / SPECIFICATION_EXPORT)
    results = []
    for suite in _load(tree / ARTIFACT)["testsuites"]:
        scenario = suite["name"]
        formed = {
            f"{scenario}.{need['suite']}.{need['test_function'].removeprefix('test_')}": need_id
            for need_id, need in needs.items()
        }
        for case in suite["testcases"]:
            results.append(
                Result(
                    scenario,
                    suite["platform"],
                    case["identifier"],
                    case["status"],
                    formed[case["identifier"]],
                )
            )
    return results


def _identity(result: Result, name: str = RUN_NAME) -> str:
    run = _run_identifier(result.scenario, _token(result.platform), name)
    return f"{run}/{result.specification}"


def _canonical(specification: str, run: str, result: str) -> bytes:
    """The SHA-256 of the canonical record of one outcome."""
    record = {"result": result, "run": run, "specification": specification}
    text = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).digest()


def _runs(tree: Path = FIXTURE) -> list[config.RunInputs]:
    return [
        config.RunInputs(
            artifact=tree / ARTIFACT, revision=tree / REVISION_RECORD, name=tree / NAME_RECORD
        )
    ]


def _extractor(
    tree: Path = FIXTURE,
    *,
    runs: list[config.RunInputs] | None = None,
    repository: str = REPOSITORY,
    implementations: bool = True,
):
    """An outcome extractor over the tree, its root. ``implementations=False`` drops that input."""
    from affirmatrix.sources.outcomes import TwisterOutcomeExtractor

    return TwisterOutcomeExtractor(
        tree,
        _runs(tree) if runs is None else runs,
        repository=repository,
        specifications=config.SpecificationInputs(
            export=tree / SPECIFICATION_EXPORT, doxygen=tree / SPECIFICATION_XML
        ),
        implementations=(
            config.ImplementationInputs(
                export=tree / IMPLEMENTATION_EXPORT, doxygen=tree / IMPLEMENTATION_XML
            )
            if implementations
            else None
        ),
    )


def _nodes(tree: Path = FIXTURE, **inputs: Any) -> dict[str, Any]:
    """Construct, then drain ``nodes()``. Keyed by local identifier, each identifier once."""
    nodes = list(_extractor(tree, **inputs).nodes())
    assert len({node.local_id for node in nodes}) == len(nodes)
    return {node.local_id: node for node in nodes}


def _edges(tree: Path = FIXTURE, **inputs: Any) -> list[Any]:
    return list(_extractor(tree, **inputs).edges())


def _error() -> type[Exception]:
    from affirmatrix.sources.outcomes import OutcomeError

    return OutcomeError


def _refused(tree: Path, identifier: str) -> None:
    """The extractor refuses the tree with an error that names the result."""
    with pytest.raises(_error(), match=re.escape(identifier)):
        _nodes(tree)


def _digests(nodes: dict[str, Any]) -> dict[str, bytes]:
    return {
        identity: node.content_anchors["contentHash"].digest for identity, node in nodes.items()
    }


def _pairs(edges: list[Any], kind: str) -> list[tuple[str, str]]:
    return sorted((edge.from_id, edge.to_id) for edge in edges if edge.kind == kind)


def _witnessed(specification: str, tree: Path = FIXTURE) -> set[str]:
    """The implementations whose need satisfies a requirement the specification verifies."""
    verified = set(_needs(tree / SPECIFICATION_EXPORT)[specification]["verifies"])
    needs = _needs(tree / IMPLEMENTATION_EXPORT)
    return {need_id for need_id, need in needs.items() if verified & set(need["satisfies"])}


def test_a_run_identifier_joins_the_run_name_the_platform_and_the_scenario(tmp_path: Path) -> None:
    """A run identifier joins the run's name, platform and scenario, in that order.

    The fixture records the run name twister-run-2026-09-29. It records four scenarios, all
    on the platform native_sim/native/64.

    Extracting supplies outcomes of exactly four run identifiers. Each is the name, the
    platform as native_sim-native-64 and one scenario name, joined by hyphens. Each run
    identifier starts the identities of 19 outcomes. The nested scenarios stay apart.

    When the name record holds another-run, every run identifier starts with another-run.
    When one scenario records the platform qemu_x86, the run identifier of that scenario
    holds qemu_x86.

    :verifies: SEG-SREQ-178
    :test-id: SEG-TS-053
    """
    nodes = _nodes()
    runs = {_run_identifier(scenario) for scenario in SCENARIOS}
    assert len(runs) == 4
    for run in runs:
        assert sum(identity.startswith(f"{run}/") for identity in nodes) == 19
    assert len(nodes) == 4 * 19

    renamed = _tree(tmp_path, "renamed")
    (renamed / NAME_RECORD).write_text("another-run\n", encoding="utf-8")
    assert set(_nodes(renamed)) == {_identity(r, "another-run") for r in _expected(renamed)}

    moved = _tree(tmp_path, "moved")

    def move_timeout(document: Any) -> None:
        (suite,) = [s for s in document["testsuites"] if s["name"] == "safe_data.api.timeout"]
        suite["platform"] = "qemu_x86"

    _edit_json(moved, ARTIFACT, move_timeout)
    after = _nodes(moved)
    assert set(after) == {_identity(r) for r in _expected(moved)}
    assert f"{_run_identifier('safe_data.api.timeout', 'qemu_x86')}/{INIT_AND_VERIFY}" in after


def test_a_specification_identifier_is_the_test_case_needs_identifier_verbatim(
    tmp_path: Path,
) -> None:
    """A specification identifier is the identifier of the test-case need, verbatim.

    Extracting from the fixture supplies 76 outcomes. Each identity ends with a slash and
    the identifier of one of the 19 test-case needs of the export. Each need identifier ends
    the identities of exactly four outcomes, one for each scenario.

    In a copy of the export, the need TC_SAFE_DATA_INIT_AND_VERIFY is renamed TC-renamed-1.
    Then the four identities that ended with the old identifier end with the new one. No
    other identity changes.

    :verifies: SEG-SREQ-179
    :test-id: SEG-TS-054
    """
    needs = _needs(FIXTURE / SPECIFICATION_EXPORT)
    nodes = _nodes()
    assert len(needs) == 19
    endings: dict[str, set[str]] = defaultdict(set)
    for identity in nodes:
        (owner,) = [need_id for need_id in needs if identity.endswith(f"/{need_id}")]
        endings[owner].add(identity)
    assert set(endings) == set(needs)
    assert all(len(identities) == len(SCENARIOS) for identities in endings.values())

    def rename(exported: dict[str, dict[str, Any]]) -> None:
        need = exported.pop(INIT_AND_VERIFY)
        need["id"] = "TC-renamed-1"
        exported["TC-renamed-1"] = need

    renamed = _tree(tmp_path)
    _edit_json(renamed, SPECIFICATION_EXPORT, _edit_needs(rename))
    after = set(_nodes(renamed))
    assert after == (set(nodes) - endings[INIT_AND_VERIFY]) | {
        identity.removesuffix(INIT_AND_VERIFY) + "TC-renamed-1"
        for identity in endings[INIT_AND_VERIFY]
    }


def test_a_result_maps_to_the_need_with_its_scenario_suite_and_test_function(
    tmp_path: Path,
) -> None:
    """A result maps to the need whose suite and test function join the result's scenario.

    The fixture records the result safe_data.api.safe_data.init_and_verify. The need
    TC_SAFE_DATA_INIT_AND_VERIFY has the suite safe_data and the test function
    test_init_and_verify. Extracting gives that result the specification
    TC_SAFE_DATA_INIT_AND_VERIFY. The same holds in the nested scenario safe_data.api.plain.

    In the scenario safe_data.api, that result is passed and the result
    write_observes_overwritten_corruption is skipped. In a copy of the export, the test
    functions of these two needs are swapped. Then the passed result belongs to the other
    need, and the skipped result belongs to TC_SAFE_DATA_INIT_AND_VERIFY.

    In a copy of the artifact, the scenario safe_data.api.strict is renamed zz.api in its
    suite and its results. Then the results of zz.api map the same way.

    :verifies: SEG-SREQ-180
    :test-id: SEG-TS-055
    """
    run = _run_identifier(BASE)
    nodes = _nodes()
    assert nodes[f"{run}/{INIT_AND_VERIFY}"].result == TestResult.PASSED
    assert nodes[f"{run}/{WRITE_OBSERVES}"].result == TestResult.SKIPPED
    assert f"{_run_identifier('safe_data.api.plain')}/{INIT_AND_VERIFY}" in nodes

    def swap(exported: dict[str, dict[str, Any]]) -> None:
        first, second = exported[INIT_AND_VERIFY], exported[WRITE_OBSERVES]
        first["test_function"], second["test_function"] = (
            second["test_function"],
            first["test_function"],
        )

    swapped = _tree(tmp_path, "swapped")
    _edit_json(swapped, SPECIFICATION_EXPORT, _edit_needs(swap))
    after = _nodes(swapped)
    assert len(after) == 76
    assert after[f"{run}/{WRITE_OBSERVES}"].result == TestResult.PASSED
    assert after[f"{run}/{INIT_AND_VERIFY}"].result == TestResult.SKIPPED

    def rename_scenario(document: Any) -> None:
        (suite,) = [s for s in document["testsuites"] if s["name"] == "safe_data.api.strict"]
        suite["name"] = "zz.api"
        for case in suite["testcases"]:
            case["identifier"] = "zz.api." + case["identifier"].removeprefix(
                "safe_data.api.strict."
            )

    renamed = _tree(tmp_path, "renamed")
    _edit_json(renamed, ARTIFACT, rename_scenario)
    mapped = _nodes(renamed)
    assert set(mapped) == {_identity(r) for r in _expected(renamed)}
    assert f"{_run_identifier('zz.api')}/{INIT_AND_VERIFY}" in mapped


def test_an_unmapped_or_ambiguous_result_is_an_error_for_that_result(tmp_path: Path) -> None:
    """An unmapped or ambiguous result is an error that names the result.

    In a copy of the export, a second need has the suite and the test function of
    TC_SAFE_DATA_INIT_AND_VERIFY. The result safe_data.api.safe_data.init_and_verify now
    maps to two needs. Extracting raises an error that names that result.

    In a copy of the export, the need TC_SAFE_DATA_SELFTEST is dropped. The result
    safe_data.api.safe_data.selftest now maps to no need. Extracting raises an error that
    names that result.

    :verifies: SEG-SREQ-181
    :test-id: SEG-TS-056
    """

    def add_twin(exported: dict[str, dict[str, Any]]) -> None:
        exported["TC_TWIN"] = {**exported[INIT_AND_VERIFY], "id": "TC_TWIN"}

    ambiguous = _tree(tmp_path, "ambiguous")
    _edit_json(ambiguous, SPECIFICATION_EXPORT, _edit_needs(add_twin))
    _refused(ambiguous, INIT_RESULT)

    def drop_selftest(exported: dict[str, dict[str, Any]]) -> None:
        del exported[SELFTEST]

    unmapped = _tree(tmp_path, "unmapped")
    _edit_json(unmapped, SPECIFICATION_EXPORT, _edit_needs(drop_selftest))
    _refused(unmapped, SELFTEST_RESULT)


def test_a_content_hash_covers_the_specification_the_run_and_the_result_only(
    tmp_path: Path,
) -> None:
    """A content hash covers the specification identifier, the run identifier and the result.

    The contentHash digest of the outcome of TC_SAFE_DATA_INIT_AND_VERIFY in the scenario
    safe_data.api equals a SHA-256. The SHA-256 is of this canonical record:

    {"result":"passed","run":"twister-run-2026-09-29-native_sim-native-64-safe_data.api",
    "specification":"TC_SAFE_DATA_INIT_AND_VERIFY"}

    In hex, the digest is b21f9c415e6b2de8ea131a18c709acdface0c91c976041b752ae382bf3128869.
    Each of the 76 digests equals the SHA-256 of its own canonical record.

    In a copy of the artifact, the execution time and the reason of every result are
    changed. Then no digest changes. In a copy, the status of that result is failed. Then
    only its digest changes, to the digest of the record with the result failed.

    :verifies: SEG-SREQ-182
    :test-id: SEG-TS-057
    """
    before = _digests(_nodes())
    identity = f"{_run_identifier(BASE)}/{INIT_AND_VERIFY}"
    assert before[identity] == bytes.fromhex(INIT_DIGEST)
    for result in _expected():
        run = _run_identifier(result.scenario, _token(result.platform))
        assert before[_identity(result)] == _canonical(result.specification, run, result.status)

    timed = _tree(tmp_path, "timed")

    def retime(document: Any) -> None:
        for suite in document["testsuites"]:
            suite["execution_time"] = "99.99"
            for case in suite["testcases"]:
                case["execution_time"] = "99.99"
                case["reason"] = "changed reason"

    _edit_json(timed, ARTIFACT, retime)
    assert _digests(_nodes(timed)) == before

    failed = _tree(tmp_path, "failed")
    _edit_json(failed, ARTIFACT, _set_status(INIT_RESULT, "failed"))
    after = _digests(_nodes(failed))
    assert {key for key in after if after[key] != before[key]} == {identity}
    assert after[identity] == _canonical(INIT_AND_VERIFY, _run_identifier(BASE), "failed")


def test_a_recorded_status_maps_onto_the_closed_result_set(tmp_path: Path) -> None:
    """A recorded status maps onto the member of the closed result set it corresponds to.

    In the fixture, each result with the status passed gives an outcome with the result
    passed. Each result with the status skipped gives an outcome with the result skipped.

    In a copy of the artifact, the result init_and_verify in safe_data.api has the status
    failed and the result selftest has the status error. Then the two outcomes record the
    results failed and error. Every other outcome is unchanged.

    :verifies: SEG-SREQ-183
    :test-id: SEG-TS-058
    """
    nodes = _nodes()
    for result in _expected():
        assert nodes[_identity(result)].result == TestResult(result.status)
    assert {node.result for node in nodes.values()} == {TestResult.PASSED, TestResult.SKIPPED}

    changed = _tree(tmp_path)
    _edit_json(changed, ARTIFACT, _set_status(INIT_RESULT, "failed"))
    _edit_json(changed, ARTIFACT, _set_status(SELFTEST_RESULT, "error"))
    after = _nodes(changed)
    run = _run_identifier(BASE)
    assert after[f"{run}/{INIT_AND_VERIFY}"].result == TestResult.FAILED
    assert after[f"{run}/{SELFTEST}"].result == TestResult.ERROR
    untouched = set(nodes) - {f"{run}/{INIT_AND_VERIFY}", f"{run}/{SELFTEST}"}
    assert {key: after[key].result for key in untouched} == {
        key: nodes[key].result for key in untouched
    }


def test_a_status_with_no_counterpart_is_an_error_for_that_result(tmp_path: Path) -> None:
    """A status with no counterpart in the closed result set is an error for that result.

    In a copy of the artifact, the result safe_data.api.safe_data.init_and_verify has the
    status blocked. Extracting raises an error that names that result. The same holds for
    the status no-such-status.

    :verifies: SEG-SREQ-184
    :test-id: SEG-TS-059
    """
    for status in ("blocked", "no-such-status"):
        variant = _tree(tmp_path, status)
        _edit_json(variant, ARTIFACT, _set_status(INIT_RESULT, status))
        _refused(variant, INIT_RESULT)


def test_a_skipped_result_is_recorded_as_a_skipped_outcome() -> None:
    """A skipped result is recorded as an outcome whose result is skipped.

    The fixture records 76 results. 65 are passed and 11 are skipped. The skips fall 2, 5, 1
    and 3 over the four scenarios.

    Extracting supplies 76 outcomes. The 11 outcomes with the result skipped are exactly
    those of the 11 skipped results.

    :verifies: SEG-SREQ-185
    :test-id: SEG-TS-060
    """
    results = _expected()
    skipped = {_identity(r) for r in results if r.status == "skipped"}
    assert len(results) == 76
    assert [sum(r.scenario == s and r.status == "skipped" for r in results) for s in SCENARIOS] == [
        2,
        5,
        1,
        3,
    ]
    nodes = _nodes()
    assert len(nodes) == 76
    assert len(skipped) == 11
    assert {identity for identity, node in nodes.items() if node.result == "skipped"} == skipped


def test_an_outcomes_revision_is_the_revision_recorded_beside_the_run(tmp_path: Path) -> None:
    """An outcome's revision is the full revision recorded beside the run artifact.

    The revision record of the fixture holds 5847f3fdca777b8d62615d84b8926fdc8ce125ed and a
    line feed. Each of the 76 outcomes has that text, without the line feed, as its
    revision.

    When the record holds 77e25d8f3cb2e94adb5a44426b98e088f1bef3fe, every outcome has that
    revision.

    :verifies: SEG-SREQ-186
    :test-id: SEG-TS-061
    """
    assert (FIXTURE / REVISION_RECORD).read_text(encoding="utf-8") == REVISION + "\n"
    nodes = _nodes()
    assert len(nodes) == 76
    assert {node.revision for node in nodes.values()} == {REVISION}

    other = "77e25d8f3cb2e94adb5a44426b98e088f1bef3fe"
    changed = _tree(tmp_path)
    (changed / REVISION_RECORD).write_text(other + "\n", encoding="utf-8")
    assert {node.revision for node in _nodes(changed).values()} == {other}


def test_a_run_with_no_recorded_revision_is_refused(tmp_path: Path) -> None:
    """A run with no recorded full revision is refused, and no outcome is supplied.

    Building the extractor raises an error when the revision record of the run is missing.
    It raises the same error when the record is empty. It raises the same error when the
    record holds only a line feed.

    :verifies: SEG-SREQ-187
    :test-id: SEG-TS-062
    """
    missing = _tree(tmp_path, "missing")
    (missing / REVISION_RECORD).unlink()
    with pytest.raises(_error()):
        _extractor(missing)
    for name, text in (("empty", ""), ("blank", "\n")):
        variant = _tree(tmp_path, name)
        (variant / REVISION_RECORD).write_text(text, encoding="utf-8")
        with pytest.raises(_error()):
            _extractor(variant)


def test_a_confirms_edge_runs_from_each_outcome_to_its_specification() -> None:
    """A Confirms edge runs from each outcome to the specification its result maps to.

    Extracting from the fixture supplies exactly 76 edges of kind Confirms. Their pairs are
    the 76 pairs of an outcome identity and a specification identifier, formed from the
    results. One pair is the outcome of safe_data.api.safe_data.init_and_verify and
    TC_SAFE_DATA_INIT_AND_VERIFY. No outcome has two such edges.

    :verifies: SEG-SREQ-188
    :test-id: SEG-TS-063
    """
    expected = sorted((_identity(r), r.specification) for r in _expected())
    assert len(expected) == 76
    assert _pairs(_edges(), "Confirms") == expected
    assert (f"{_run_identifier(BASE)}/{INIT_AND_VERIFY}", INIT_AND_VERIFY) in expected


def test_a_witnesses_edge_runs_to_each_implementation_of_what_the_specification_verifies(
    tmp_path: Path,
) -> None:
    """A Witnesses edge runs from each outcome to each implementation of what its test verifies.

    The need TC_SAFE_DATA_INIT_AND_VERIFY verifies SD-REQ-001 and SD-REQ-003. The
    implementation needs IMPL-safe_data_init and IMPL-safe_data_verify satisfy them. Each of
    the four outcomes of that specification has Witnesses edges to exactly those two
    implementations.

    For every outcome, the edges run to exactly the implementations whose need satisfies a
    requirement that its specification verifies. This holds for a skipped outcome too. The
    skipped outcome of TC_SAFE_DATA_WRITE_OBSERVES_OVERWRITTEN_CORRUPTION has one edge, to
    IMPL-safe_data_write.

    In a copy of the implementation export, IMPL-safe_data_commit also satisfies SD-REQ-001.
    Then the four outcomes have an edge to it as well. Without the implementation input, no
    Witnesses edge is supplied.

    :verifies: SEG-SREQ-189
    :test-id: SEG-TS-064
    """
    assert _witnessed(INIT_AND_VERIFY) == {"IMPL-safe_data_init", "IMPL-safe_data_verify"}
    results = _expected()
    expected = sorted((_identity(r), i) for r in results for i in _witnessed(r.specification))
    pairs = _pairs(_edges(), "Witnesses")
    assert pairs == expected
    init_identities = {_identity(r) for r in results if r.specification == INIT_AND_VERIFY}
    assert len(init_identities) == 4
    for identity in init_identities:
        assert {to for from_id, to in pairs if from_id == identity} == {
            "IMPL-safe_data_init",
            "IMPL-safe_data_verify",
        }
    skipped = f"{_run_identifier(BASE)}/{WRITE_OBSERVES}"
    assert _nodes()[skipped].result == TestResult.SKIPPED
    assert [to for from_id, to in pairs if from_id == skipped] == ["IMPL-safe_data_write"]

    widened = _tree(tmp_path)

    def widen(exported: dict[str, dict[str, Any]]) -> None:
        exported["IMPL-safe_data_commit"]["satisfies"].append("SD-REQ-001")

    _edit_json(widened, IMPLEMENTATION_EXPORT, _edit_needs(widen))
    wider = _pairs(_edges(widened), "Witnesses")
    assert {(f, t) for f, t in wider} == set(pairs) | {
        (identity, "IMPL-safe_data_commit") for identity in init_identities
    }

    assert _pairs(_edges(implementations=False), "Witnesses") == []


def test_an_outcomes_anchor_names_the_run_artifact_and_the_result(tmp_path: Path) -> None:
    """An outcome's anchor names the run artifact's path in its repository and the result.

    The extractor is given the fixture directory as its root and the repository as the
    configured name toolbox. The artifact is twister/twister.json under that root. Each of
    the 76 outcomes has exactly one content hash, contentHash. Its anchor names the
    repository toolbox and the path twister/twister.json, relative to the root. Its locator
    is nodeid: followed by the identifier of the result, for example
    nodeid:safe_data.api.safe_data.init_and_verify.

    In a copy of the fixture, the artifact is moved to out/run1/twister.json. Then every
    anchor has that path.

    :verifies: SEG-SREQ-190
    :test-id: SEG-TS-065
    """
    identifiers = {_identity(r): r.identifier for r in _expected()}
    nodes = _nodes()
    assert set(nodes) == set(identifiers)
    for identity, node in nodes.items():
        assert set(node.content_anchors) == {"contentHash"}
        anchor = node.content_anchors["contentHash"]
        assert anchor.repository == REPOSITORY
        assert anchor.path == "twister/twister.json"
        assert anchor.locator == f"nodeid:{identifiers[identity]}"
    assert (
        nodes[f"{_run_identifier(BASE)}/{INIT_AND_VERIFY}"].content_anchors["contentHash"].locator
        == f"nodeid:{INIT_RESULT}"
    )

    moved = _tree(tmp_path)
    (moved / "out" / "run1").mkdir(parents=True)
    shutil.move(moved / ARTIFACT, moved / "out" / "run1" / "twister.json")
    relocated = [
        config.RunInputs(
            moved / "out" / "run1" / "twister.json", moved / REVISION_RECORD, moved / NAME_RECORD
        )
    ]
    paths = {
        node.content_anchors["contentHash"].path for node in _nodes(moved, runs=relocated).values()
    }
    assert paths == {"out/run1/twister.json"}


def test_each_runs_inputs_are_loaded_relative_to_the_file(tmp_path: Path) -> None:
    """Each run's artifact, revision record and name record are loaded, resolved against the file.

    A configuration file in a subdirectory lists two outcomes in its producer block. Each
    has an artifact, a revision and a name. Loading the file yields two run inputs, in the
    order of the file. Each of their three locations is the subdirectory joined with the
    relative path that the file gives.

    :verifies: SEG-SREQ-197
    :test-id: SEG-TS-066
    """
    path = tmp_path / "repo" / "affirmatrix.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "producer:\n"
        "  repository: sample-repo\n"
        "  outcomes:\n"
        "    - artifact: twister/twister.json\n"
        "      revision: revisions/toolbox.sha\n"
        "      name: revisions/run.name\n"
        "    - artifact: later/twister.json\n"
        "      revision: later/toolbox.sha\n"
        "      name: later/run.name\n",
        encoding="utf-8",
    )
    producer = config.load(path).producer
    assert producer is not None
    base = tmp_path / "repo"
    assert producer.outcomes == (
        config.RunInputs(
            artifact=base / "twister/twister.json",
            revision=base / "revisions/toolbox.sha",
            name=base / "revisions/run.name",
        ),
        config.RunInputs(
            artifact=base / "later/twister.json",
            revision=base / "later/toolbox.sha",
            name=base / "later/run.name",
        ),
    )
