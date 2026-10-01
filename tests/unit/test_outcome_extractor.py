"""Unit tests of the outcome extractor over small trees built in a temporary directory.

The acceptance tests read the evidence fixture. These tests build the smallest
tree that shows one property: two test-case needs, one implementation need and
a run bundle: a run artifact of one suite, a revision record and a dirty flag
for the implementation checkout ``impl``, and the run name. Each test changes
one thing of that tree and states what the extractor does with it. A bundle's
digest is computed when the extractor is built, so a change made before that
is not a digest mismatch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config
from affirmatrix.records import LinkState, TestResult
from affirmatrix.sources.outcomes import (
    OutcomeError,
    TwisterOutcomeExtractor,
    bundle_digest,
    canonical_record,
)

PASSED_DIGEST = "b21f9c415e6b2de8ea131a18c709acdface0c91c976041b752ae382bf3128869"
RUN_NAME = "run-one"


def _need(identifier: str, function: str, verifies: list[str], suite: str = "s") -> dict[str, Any]:
    return {
        "id": identifier,
        "type": "test_case",
        "suite": suite,
        "test_function": function,
        "verifies": verifies,
    }


def _implementation(identifier: str, satisfies: list[str]) -> dict[str, Any]:
    return {"id": identifier, "type": "impl", "satisfies": satisfies}


def _export(needs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"versions": {"1": {"needs": {need["id"]: need for need in needs}}}}


def _suite(scenario: str, cases: dict[str, str], platform: str = "plat/one") -> dict[str, Any]:
    return {
        "name": scenario,
        "platform": platform,
        "testcases": [{"identifier": name, "status": status} for name, status in cases.items()],
    }


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _bundle(
    directory: Path, suites: list[dict[str, Any]], *, revision: str = "abc123", name: str = RUN_NAME
) -> Path:
    """A run bundle in ``directory``: the artifact, the checkout ``impl`` and the name."""
    _write(directory / "twister.json", {"testsuites": suites})
    (directory / "impl.sha").write_text(f"{revision}\n", encoding="utf-8")
    (directory / "impl.dirty").write_text("", encoding="utf-8")
    (directory / "run.name").write_text(f"{name}\n", encoding="utf-8")
    return directory


def _tree(tmp_path: Path, *, suites: list[dict[str, Any]] | None = None) -> Path:
    """A root holding a run of one scenario ``sc`` with results ``a`` and ``b``."""
    _write(
        tmp_path / "specs.json",
        _export([_need("TC_A", "test_a", ["REQ1"]), _need("TC_B", "test_b", ["REQ2"])]),
    )
    _write(
        tmp_path / "impls.json",
        _export([_implementation("IMPL_1", ["REQ1"]), _implementation("IMPL_2", ["REQ3"])]),
    )
    default = [_suite("sc", {"sc.s.a": "passed", "sc.s.b": "skipped"})]
    _bundle(tmp_path / "run", default if suites is None else suites)
    return tmp_path


def _extractor(
    root: Path,
    *,
    bundles: list[Path] | None = None,
    implementations: bool = True,
    checkout: str | None = "impl",
) -> TwisterOutcomeExtractor:
    return TwisterOutcomeExtractor(
        [root / "run"] if bundles is None else bundles,
        checkout=checkout,
        specifications=config.SpecificationInputs(export=root / "specs.json", doxygen=root),
        implementations=(
            config.ImplementationInputs(export=root / "impls.json", doxygen=root)
            if implementations
            else None
        ),
    )


def test_the_canonical_record_is_the_compact_sorted_json_of_three_members() -> None:
    record = canonical_record("TC_A", "run-one-plat-one-sc", TestResult.PASSED)
    assert record == (b'{"result":"passed","run":"run-one-plat-one-sc","specification":"TC_A"}')


def test_the_content_hash_of_a_known_record_is_its_sha256() -> None:
    name = "twister-run-2026-09-29-native_sim-native-64-safe_data.api"
    record = canonical_record("TC_SAFE_DATA_INIT_AND_VERIFY", name, TestResult.PASSED)
    assert hashlib.sha256(record).hexdigest() == PASSED_DIGEST


def test_a_non_ascii_identifier_is_written_as_utf_8_and_not_escaped() -> None:
    record = canonical_record("TC_Ä", "run", TestResult.FAILED)
    assert record == '{"result":"failed","run":"run","specification":"TC_Ä"}'.encode()


def test_a_slash_in_the_platform_becomes_a_hyphen_in_the_identity(tmp_path: Path) -> None:
    nodes = list(_extractor(_tree(tmp_path)).nodes())
    assert [node.local_id for node in nodes] == [
        f"{RUN_NAME}-plat-one-sc/TC_A",
        f"{RUN_NAME}-plat-one-sc/TC_B",
    ]


def test_a_test_function_loses_only_one_leading_test_prefix(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(
        root / "specs.json",
        _export([_need("TC_A", "test_test_a", []), _need("TC_B", "check_b", [])]),
    )
    _write(
        root / "run" / "twister.json",
        {"testsuites": [_suite("sc", {"sc.s.test_a": "passed", "sc.s.check_b": "passed"})]},
    )
    specifications = [node.local_id.split("/")[1] for node in _extractor(root).nodes()]
    assert specifications == ["TC_A", "TC_B"]


def test_one_identifier_maps_to_the_need_that_forms_it_in_each_nested_scenario(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _write(
        root / "specs.json",
        _export(
            [_need("TC_LONG", "test_f", [], suite="t.u"), _need("TC_SHORT", "test_f", [], "u")]
        ),
    )
    _write(
        root / "run" / "twister.json",
        {
            "testsuites": [
                _suite("s", {"s.t.u.f": "passed"}),
                _suite("s.t", {"s.t.u.f": "passed"}),
            ]
        },
    )
    specifications = [node.local_id.rsplit("/", 1)[1] for node in _extractor(root).nodes()]
    assert specifications == ["TC_LONG", "TC_SHORT"]


def test_a_scenario_with_no_results_supplies_nothing(tmp_path: Path) -> None:
    root = _tree(tmp_path, suites=[_suite("empty", {}), _suite("sc", {"sc.s.a": "passed"})])
    assert [node.local_id for node in _extractor(root).nodes()] == [f"{RUN_NAME}-plat-one-sc/TC_A"]


def test_two_runs_supply_their_outcomes_in_order_each_with_its_own_revision(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    (root / "run" / "run.name").write_text("first\n", encoding="utf-8")
    _bundle(
        root / "later", [_suite("sc", {"sc.s.a": "failed"})], revision="def456", name="second"
    )
    bundles = [root / "run", root / "later"]
    nodes = list(_extractor(root, bundles=bundles).nodes())
    assert [(node.local_id, node.revision) for node in nodes] == [
        ("first-plat-one-sc/TC_A", "abc123"),
        ("first-plat-one-sc/TC_B", "abc123"),
        ("second-plat-one-sc/TC_A", "def456"),
    ]


def test_a_missing_revision_record_is_refused_naming_the_record(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.sha").unlink()
    with pytest.raises(OutcomeError, match=r"revision record .*impl\.sha"):
        _extractor(root)


@pytest.mark.parametrize("text", ["", "\n", "   \n"])
def test_a_revision_record_with_no_text_is_refused(tmp_path: Path, text: str) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.sha").write_text(text, encoding="utf-8")
    with pytest.raises(OutcomeError, match="is empty"):
        _extractor(root)


def test_a_revision_record_of_two_lines_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.sha").write_text("abc\ndef\n", encoding="utf-8")
    with pytest.raises(OutcomeError, match="more than one line"):
        _extractor(root)


def test_a_revision_record_with_blanks_around_its_text_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.sha").write_text(" abc123\n", encoding="utf-8")
    with pytest.raises(OutcomeError, match="blanks"):
        _extractor(root)


def test_a_revision_record_ending_in_a_carriage_return_and_line_feed_is_read(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.sha").write_bytes(b"abc123\r\n")
    assert {node.revision for node in _extractor(root).nodes()} == {"abc123"}


def test_an_empty_name_record_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "run.name").write_text("\n", encoding="utf-8")
    with pytest.raises(OutcomeError, match="name record .*is empty"):
        _extractor(root)


def test_a_name_with_a_slash_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "run.name").write_text("a/b\n", encoding="utf-8")
    with pytest.raises(OutcomeError, match="slash"):
        _extractor(root)


def test_a_run_artifact_that_is_not_json_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "twister.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(OutcomeError, match="cannot be read"):
        _extractor(root)


def test_a_run_artifact_without_testsuites_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root / "run" / "twister.json", {"suites": []})
    with pytest.raises(OutcomeError, match="'testsuites'"):
        _extractor(root)


def test_a_bundle_anywhere_is_read_and_anchored_by_its_digest(tmp_path: Path) -> None:
    """SEG-SREQ-190: the bundle needs no root; its digest is the repository member."""
    root = _tree(tmp_path / "root")
    outside = _tree(tmp_path / "elsewhere")
    nodes = list(_extractor(root, bundles=[outside / "run"]).nodes())
    digest = bundle_digest(outside / "run")
    anchors = {
        (n.content_anchors["contentHash"].repository, n.content_anchors["contentHash"].path)
        for n in nodes
    }
    assert anchors == {(digest, "twister.json")}


@pytest.mark.parametrize("status", ["blocked", "", None, 3])
def test_a_status_outside_the_closed_set_is_refused_naming_the_result(
    tmp_path: Path, status: object
) -> None:
    root = _tree(tmp_path)
    _write(
        root / "run" / "twister.json",
        {
            "testsuites": [
                {**_suite("sc", {}), "testcases": [{"identifier": "sc.s.a", "status": status}]}
            ]
        },
    )
    with pytest.raises(OutcomeError, match=r"twister\.json.*'sc\.s\.a'.*status"):
        _extractor(root)


def test_an_unmapped_result_is_refused_naming_the_run_and_the_result(tmp_path: Path) -> None:
    root = _tree(tmp_path, suites=[_suite("sc", {"sc.s.missing": "passed"})])
    with pytest.raises(OutcomeError, match=r"twister\.json.*'sc\.s\.missing' maps to no"):
        _extractor(root)


def test_an_ambiguous_result_is_refused_naming_both_needs(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(
        root / "specs.json",
        _export([_need("TC_A", "test_a", []), _need("TC_TWIN", "test_a", [])]),
    )
    with pytest.raises(OutcomeError, match=r"'sc\.s\.a' maps to 2 .*'TC_A'.*'TC_TWIN'"):
        _extractor(root)


def test_a_duplicate_suite_and_function_that_no_result_reaches_is_ignored(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _write(
        root / "specs.json",
        _export(
            [_need("TC_A", "test_a", []), _need("TC_B", "test_b", []), _need("TC_C", "test_b", [])]
        ),
    )
    _write(root / "run" / "twister.json", {"testsuites": [_suite("sc", {"sc.s.a": "passed"})]})
    assert len(list(_extractor(root).nodes())) == 1


def test_a_test_case_need_with_an_empty_test_function_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _write(root / "specs.json", _export([_need("TC_A", "", [])]))
    with pytest.raises(OutcomeError, match="need 'TC_A' has an empty"):
        _extractor(root)


def test_an_export_with_a_build_timestamp_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    export = json.loads((root / "impls.json").read_text(encoding="utf-8"))
    export["created"] = "2026-01-01"
    _write(root / "impls.json", export)
    with pytest.raises(OutcomeError, match="build timestamp"):
        _extractor(root)


def test_every_edge_is_pending(tmp_path: Path) -> None:
    edges = list(_extractor(_tree(tmp_path)).edges())
    assert edges
    assert {edge.state for edge in edges} == {LinkState.PENDING}


def test_a_witnesses_edge_runs_to_the_implementation_of_a_verified_requirement(
    tmp_path: Path,
) -> None:
    edges = list(_extractor(_tree(tmp_path)).edges())
    assert [(e.from_id, e.to_id) for e in edges if e.kind == "Witnesses"] == [
        (f"{RUN_NAME}-plat-one-sc/TC_A", "IMPL_1")
    ]


def test_an_implementation_that_satisfies_two_verified_requirements_is_one_witness(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _write(root / "specs.json", _export([_need("TC_A", "test_a", ["REQ1", "REQ3"])]))
    _write(root / "impls.json", _export([_implementation("IMPL_1", ["REQ1", "REQ3"])]))
    _write(root / "run" / "twister.json", {"testsuites": [_suite("sc", {"sc.s.a": "passed"})]})
    witnesses = [e.to_id for e in _extractor(root).edges() if e.kind == "Witnesses"]
    assert witnesses == ["IMPL_1"]


def test_no_witnesses_edge_is_supplied_when_no_implementation_satisfies_a_verified_requirement(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _write(root / "impls.json", _export([_implementation("IMPL_2", ["REQ3"])]))
    kinds = {edge.kind for edge in _extractor(root).edges()}
    assert kinds == {"Confirms"}


def test_no_witnesses_edge_is_supplied_without_the_implementation_input(tmp_path: Path) -> None:
    kinds = [edge.kind for edge in _extractor(_tree(tmp_path), implementations=False).edges()]
    assert kinds == ["Confirms", "Confirms"]


def test_two_runs_that_give_one_outcome_identity_are_refused_naming_both_runs(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _bundle(root / "twin", [_suite("sc", {"sc.s.a": "passed"})], revision="def456")
    bundles = [root / "run", root / "twin"]
    with pytest.raises(OutcomeError, match=r"twin.*already supplied.*run bundle .*run$"):
        _extractor(root, bundles=bundles)


def test_a_bundle_digest_has_the_form_sha256_and_64_hex_digits(tmp_path: Path) -> None:
    digest = bundle_digest(_tree(tmp_path) / "run")
    assert len(digest) == len("sha256:") + 64
    assert digest.startswith("sha256:")


def test_an_empty_directory_in_a_bundle_does_not_change_its_digest(tmp_path: Path) -> None:
    bundle = _tree(tmp_path) / "run"
    before = bundle_digest(bundle)
    (bundle / "logs").mkdir()
    assert bundle_digest(bundle) == before


def test_a_link_in_a_bundle_is_refused(tmp_path: Path) -> None:
    bundle = _tree(tmp_path) / "run"
    (bundle / "link.json").symlink_to(bundle / "twister.json")
    with pytest.raises(OutcomeError, match="link"):
        bundle_digest(bundle)


def test_a_bundle_path_with_a_backslash_is_refused(tmp_path: Path) -> None:
    bundle = _tree(tmp_path) / "run"
    (bundle / "a\\b.txt").write_text("x", encoding="utf-8")
    with pytest.raises(OutcomeError, match="backslash"):
        bundle_digest(bundle)


def test_a_bundle_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    with pytest.raises(OutcomeError, match="not a directory"):
        bundle_digest(root / "specs.json")


def test_a_missing_dirty_flag_of_the_implementation_checkout_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.dirty").unlink()
    with pytest.raises(OutcomeError, match="dirty flag .*impl\\.dirty"):
        _extractor(root)


def test_a_dirty_implementation_checkout_is_refused_naming_the_first_line(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "run" / "impl.dirty").write_text(" M a.c\n?? b.c\n", encoding="utf-8")
    with pytest.raises(OutcomeError, match=r"dirty.*' M a\.c'"):
        _extractor(root)


@pytest.mark.parametrize("checkout", [None, "", "a/b", ".."])
def test_an_unusable_implementation_checkout_is_refused(
    tmp_path: Path, checkout: str | None
) -> None:
    with pytest.raises(OutcomeError, match="implementation checkout"):
        _extractor(_tree(tmp_path), checkout=checkout)


def test_each_outcome_names_the_digest_of_the_bundle_that_supplied_it(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _bundle(root / "later", [_suite("sc", {"sc.s.a": "failed"})], name="second")
    extractor = _extractor(root, bundles=[root / "run", root / "later"])
    assert extractor.evidence_bundles() == {
        f"{RUN_NAME}-plat-one-sc/TC_A": bundle_digest(root / "run"),
        f"{RUN_NAME}-plat-one-sc/TC_B": bundle_digest(root / "run"),
        "second-plat-one-sc/TC_A": bundle_digest(root / "later"),
    }
