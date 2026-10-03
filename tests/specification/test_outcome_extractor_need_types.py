"""Verification suite for the need types that the outcome extractor reads.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
need export can hold needs of more than one type. The outcome extractor must
read the needs of the configured types and no others, as the content extractor
does. A need of another type has the keys of a test case with the value null,
or it has links of another shape, and the extractor must not refuse the export
for it.

Most tests build the outcome extractor from its inputs, over exports and one
run bundle written in ``tmp_path`` (see ``need_types_support``). The two tests
that go through the command line use the frozen fixtures of the toolbox
evidence, with one need of another type added to each export. A test that shows
a refusal starts from a control that is accepted, so it fails for the claim
and never for an input that cannot be read at all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from affirmatrix.sources.outcomes import OutcomeError

from . import need_types_support as support
from .evidence_support import (
    OUTCOMES_PER_RUN,
    REVISION,
    TOOLBOX,
    copy_bundle,
    run,
    session,
)

SUITE = "queue"
PLATFORM = "native_sim"
PUT_GET = support.result_identifier(support.SCENARIO, SUITE, "test_put_get")
ISR = support.result_identifier(support.SCENARIO, SUITE, "test_isr")
OTHER = support.result_identifier(support.SCENARIO, SUITE, "test_other_thing")
RUN = f"{support.RUN_NAME}-{PLATFORM}-{support.SCENARIO}"


def _cases() -> list[dict[str, Any]]:
    """Two test cases and, beside them, three needs of the type test_procedure."""
    return [
        support.case_need("TC-A", SUITE, "test_put_get"),
        support.procedure_need("queue", "tDrain"),
        support.case_need("TC-B", SUITE, "test_isr"),
        support.procedure_need("queue", "tTake"),
        support.procedure_need("stack", "tPut"),
    ]


def _bundle(tmp_path: Path, *identifiers: str) -> Path:
    """A bundle whose one board passed every result named."""
    results = [(identifier, "passed") for identifier in identifiers]
    return support.write_bundle(tmp_path / "bundle", [(support.SCENARIO, PLATFORM, results)])


def _kinds(extractor: Any, kind: str) -> list[str]:
    return [target for _, target in support.edge_pairs(extractor, kind)]


def test_only_needs_of_the_configured_types_are_test_case_needs(tmp_path: Path) -> None:
    """Only the needs of the configured types are test-case needs.

    The test-case export holds TC-A and TC-B of the type test_case. It also holds
    TC-OTHER of the type test_other, with a suite and a test function. A run bundle
    records a result for the test of each of the three needs. With the types
    {test_case, test_other} configured, the extractor supplies three outcomes, and
    one of them confirms TC-OTHER. With the types {test_case} configured, the
    extractor refuses the bundle with an error that names the result of TC-OTHER,
    because that result maps to no test-case need.

    :verifies: SEG-SREQ-336
    :test-id: SEG-TS-317
    """
    cases = [
        support.case_need("TC-A", SUITE, "test_put_get"),
        support.case_need("TC-B", SUITE, "test_isr"),
        support.case_need("TC-OTHER", SUITE, "test_other_thing", type="test_other"),
    ]
    specifications, implementations = support.exports(tmp_path, cases)
    bundle = _bundle(tmp_path, PUT_GET, ISR, OTHER)

    both = support.outcome_extractor(
        bundle,
        specifications,
        implementations,
        specification_types=["test_case", "test_other"],
    )
    assert len(support.outcome_ids(both)) == 3
    assert "TC-OTHER" in _kinds(both, "Confirms")

    with pytest.raises(OutcomeError, match=re.escape(OTHER)):
        support.outcome_extractor(
            bundle, specifications, implementations, specification_types=["test_case"]
        )


def test_without_configured_types_every_need_is_a_test_case_need(tmp_path: Path) -> None:
    """While no type is configured, every need of the test-case export is a test-case need.

    The test-case export holds TC-A of the type test_case and TC-OTHER of the type
    test_other, both with a suite and a test function. A run bundle records a result
    for the test of each. With no types configured, the extractor supplies two
    outcomes, and the outcomes confirm TC-A and TC-OTHER. When the export also holds
    a need of the type test_procedure whose suite is null, the extractor refuses the
    export with an error that names the need and says it has no text field 'suite'.

    :verifies: SEG-SREQ-337
    :test-id: SEG-TS-318
    """
    cases = [
        support.case_need("TC-A", SUITE, "test_put_get"),
        support.case_need("TC-OTHER", SUITE, "test_other_thing", type="test_other"),
    ]
    specifications, implementations = support.exports(tmp_path / "plain", cases)
    bundle = _bundle(tmp_path, PUT_GET, OTHER)

    extractor = support.outcome_extractor(bundle, specifications, implementations)
    assert sorted(_kinds(extractor, "Confirms")) == ["TC-A", "TC-OTHER"]

    procedure = support.procedure_need("queue", "tDrain")
    with_procedure, _ = support.exports(tmp_path / "mixed", [*cases, procedure])
    with pytest.raises(OutcomeError, match=re.escape(procedure["id"])) as refused:
        support.outcome_extractor(bundle, with_procedure, implementations)
    assert "has no text field 'suite'" in str(refused.value)


def test_a_need_of_another_type_does_not_refuse_the_test_case_export(tmp_path: Path) -> None:
    """A need of another type does not refuse the test-case export.

    The test-case export holds two needs of the type test_case and three needs of
    the type test_procedure. The identifier of a procedure need has the form
    test-proc-<area>_api_procedures-<step>, and its suite and test function are
    null. The types {test_case} are configured. A run bundle records one result
    for the test of each test case. Building the extractor and taking every
    record raises no error. The extractor supplies two outcomes, and each Confirms
    edge runs to a test case. No edge runs to a procedure need.

    :verifies: SEG-SREQ-338
    :test-id: SEG-TS-319
    """
    specifications, implementations = support.exports(tmp_path, _cases())
    bundle = _bundle(tmp_path, PUT_GET, ISR)

    extractor = support.outcome_extractor(
        bundle, specifications, implementations, specification_types=["test_case"]
    )

    assert support.outcome_ids(extractor) == [f"{RUN}/TC-A", f"{RUN}/TC-B"]
    assert sorted(_kinds(extractor, "Confirms")) == ["TC-A", "TC-B"]
    assert not [t for t in _kinds(extractor, "Confirms") if t.startswith("test-proc-")]


def _with_other_types(tmp_path: Path, *, design: bool = True) -> tuple[Path, Path]:
    """The toolbox exports with one need of another type added to each.

    The test-case export gets a test procedure whose suite and test function are
    null. The implementation export gets a need of the type design whose
    ``satisfies`` is a text and not a list, unless ``design`` is false.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    exports = {}
    note = {"id": "DESIGN-NOTE", "type": "design", "title": "a note", "satisfies": "SD-REQ-019"}
    for name, relative, extra in (
        (
            "specifications",
            "needs/test-specification/needs.json",
            support.procedure_need("queue", "tDrain"),
        ),
        ("implementations", "needs/api-traceability/needs.json", note if design else None),
    ):
        document = json.loads((TOOLBOX / relative).read_text(encoding="utf-8"))
        (version,) = document["versions"].values()
        if extra is not None:
            version["needs"][extra["id"]] = extra
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        exports[name] = path
    return exports["specifications"], exports["implementations"]


def _typed_session(tmp_path: Path, capsys: pytest.CaptureFixture[str], *, typed: bool):
    """A session over the toolbox, and the exports of ``_with_other_types``.

    With ``typed``, the configuration names the types of both exports, and the
    implementation export holds a need of another type. Without it, only the
    test-case export does.
    """
    specifications, implementations = _with_other_types(tmp_path, design=typed)
    opened = session(
        tmp_path,
        [copy_bundle(tmp_path)],
        capsys,
        specification_export=specifications,
        implementation_export=implementations,
    )
    if typed:
        document = yaml.safe_load(opened.config.read_text(encoding="utf-8"))
        document["producer"]["specifications"]["types"] = ["test_case"]
        document["producer"]["implementations"]["types"] = ["impl"]
        opened.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    return opened


def test_a_bundle_read_over_exports_with_other_types_gives_a_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bundle read over exports that hold needs of other types is not refused.

    The test-case export of the toolbox fixture has a need of the type
    test_procedure added, with a suite and a test function that are null. The
    implementation export has a need of the type design added, whose links are not a
    list. The configuration names the types test_case and impl for the two
    exports. Running graph status with the clean bundle and a given revision exits
    with status 0. Its machine-readable report counts 76 outcomes at the current
    revision and none at another.

    :verifies: SEG-SREQ-338
    :test-id: SEG-TS-320
    """
    opened = _typed_session(tmp_path, capsys, typed=True)

    status, out = run(
        capsys, "graph", "status", "--json", *opened.evidence_args(), "--revision", REVISION
    )

    assert status == 0, out[-300:]
    assert json.loads(out)["evidence"] == {"current": OUTCOMES_PER_RUN, "stale": 0, "dangling": 0}


def test_a_bundle_read_over_a_procedure_need_with_no_configured_types_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no types configured, a need of another type with no test function refuses the read.

    The test-case export of the toolbox fixture has a need of the type
    test_procedure added, with a suite and a test function that are null. The
    configuration names no types. Running graph status with the clean bundle and a
    given revision exits with status 2 and prints no report. The output names the
    procedure need. A control, whose export lacks that need, gives exit status 0.

    :verifies: SEG-SREQ-337
    :test-id: SEG-TS-321
    """
    control = session(tmp_path / "control", [copy_bundle(tmp_path / "control")], capsys)
    assert (
        run(capsys, "graph", "status", "--json", *control.evidence_args(), "--revision", REVISION)[
            0
        ]
        == 0
    )

    opened = _typed_session(tmp_path / "mixed", capsys, typed=False)
    status, out = run(
        capsys, "graph", "status", "--json", *opened.evidence_args(), "--revision", REVISION
    )

    assert status == 2
    assert "test-proc-queue_api_procedures-tDrain" in out
    assert '"edges"' not in out


def test_a_need_of_another_type_does_not_refuse_the_implementation_export(
    tmp_path: Path,
) -> None:
    """A need of another type does not refuse the implementation export.

    The implementation export holds IMPL-1 of the type impl and NOTE-1 of the type
    design. The links of NOTE-1 are a text and not a list. A run bundle records one
    result for one test case. With the types {impl} configured for the
    implementation export, the extractor is built without an error, and one
    Witnesses edge runs from the outcome to IMPL-1. With no types configured, the
    extractor refuses the export with an error that names NOTE-1.

    :verifies: SEG-SREQ-338
    :test-id: SEG-TS-322
    """
    specifications, _ = support.exports(
        tmp_path, [support.case_need("TC-A", SUITE, "test_put_get")]
    )
    implementations = support.export_of(
        tmp_path,
        [
            support.implementation_need("IMPL-1"),
            support.implementation_need("NOTE-1", type="design", satisfies="SREQ-1"),
        ],
        "mixed-impls",
    )
    bundle = _bundle(tmp_path, PUT_GET)

    extractor = support.outcome_extractor(
        bundle, specifications, implementations, implementation_types=["impl"]
    )
    assert support.edge_pairs(extractor, "Witnesses") == [(f"{RUN}/TC-A", "IMPL-1")]

    with pytest.raises(OutcomeError, match="NOTE-1"):
        support.outcome_extractor(bundle, specifications, implementations)


def _witnessing_exports(tmp_path: Path) -> tuple[Path, Path]:
    """One test case, and two needs that satisfy the requirement it verifies.

    IMPL-1 is of the type impl and NOTE-1 of the type design. Both have a valid
    list of links.
    """
    specifications, _ = support.exports(
        tmp_path, [support.case_need("TC-A", SUITE, "test_put_get")]
    )
    implementations = support.export_of(
        tmp_path,
        [
            support.implementation_need("IMPL-1"),
            support.implementation_need("NOTE-1", type="design"),
        ],
        "witnessing",
    )
    return specifications, implementations


def test_the_witnesses_come_from_the_implementation_needs_of_the_configured_types(
    tmp_path: Path,
) -> None:
    """Witnesses edges come only from the implementation needs of the configured types.

    The implementation export holds IMPL-1 of the type impl and NOTE-1 of the type
    design. Both satisfy the requirement that the one test case verifies, and both
    have a valid list of links. A run bundle records one result for that test case.
    With the types {impl} configured, the extractor supplies one Witnesses edge from
    the outcome, and it runs to IMPL-1. With the types {design} configured, the one
    edge runs to NOTE-1.

    :verifies: SEG-SREQ-339
    :test-id: SEG-TS-323
    """
    specifications, implementations = _witnessing_exports(tmp_path)
    bundle = _bundle(tmp_path, PUT_GET)
    outcome = f"{RUN}/TC-A"

    for types, expected in ((["impl"], "IMPL-1"), (["design"], "NOTE-1")):
        extractor = support.outcome_extractor(
            bundle, specifications, implementations, implementation_types=types
        )
        assert support.edge_pairs(extractor, "Witnesses") == [(outcome, expected)], types


def test_without_configured_types_every_implementation_need_is_read(tmp_path: Path) -> None:
    """While no type is configured, every need of the implementation export is read.

    The implementation export holds IMPL-1 of the type impl and NOTE-1 of the type
    design. Both satisfy the requirement that the one test case verifies. A run
    bundle records one result for that test case. With no types configured for the
    implementation export, the extractor supplies two Witnesses edges from the
    outcome, one to each need.

    :verifies: SEG-SREQ-340
    :test-id: SEG-TS-324
    """
    specifications, implementations = _witnessing_exports(tmp_path)
    bundle = _bundle(tmp_path, PUT_GET)

    extractor = support.outcome_extractor(bundle, specifications, implementations)

    outcome = f"{RUN}/TC-A"
    assert support.edge_pairs(extractor, "Witnesses") == [(outcome, "IMPL-1"), (outcome, "NOTE-1")]
