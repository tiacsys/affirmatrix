"""Verification suite for the outcomes that count when implementation needs are listed.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
list of need identifiers narrows the implementation needs that an outcome can
witness. An outcome counts only when it witnesses an implementation, so the list
decides which outcomes confirm and which are set aside and reported as
information. The test runs ``proof check`` over the frozen evidence fixture and
one run bundle, with the strong edges affirmed. The implementation export is the
fixture's, with one need added: a copy of a listed need under another
identifier, so that one requirement has two implementation needs. The expected
sets are computed from the exports with the standard library.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from affirmatrix import gates

from . import capture_support as support
from .evidence_support import (
    REVISION,
    TOOLBOX,
    copy_bundle,
    run,
    scope_args,
    session,
)

_STRICT = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-359: the list of need identifiers is dropped, so no outcome is set aside",
)

DISCARDED = gates.Condition.DISCARDED_OUTCOME
#: The need that the list leaves out. It alone implements three requirements of the scope.
LEFT_OUT = "IMPL-safe_data_verify_repair"
ALONE = ("SD-REQ-004", "SD-REQ-009", "SD-REQ-010")
#: The requirement that has two implementation needs, one of them listed and one not.
SHARED = "SD-REQ-005"
LISTED_OF_SHARED = "IMPL-safe_data_read"
UNLISTED_TWIN = "IMPL-safe_data_read_twin"
#: A requirement of the scope with a listed need, which a test can verify beside a left-out one.
LISTED_OF_OTHER = "SD-REQ-003"


def _export(relative: str) -> dict:
    return json.loads((TOOLBOX / relative).read_text(encoding="utf-8"))


def _exports(tmp_path: Path) -> tuple[Path, list[str]]:
    """The implementation export of the fixture plus the twin; and the identifiers to list.

    The twin has the identifier ``UNLISTED_TWIN`` and every other field of the
    need ``LISTED_OF_SHARED``. The list holds every need of the fixture except
    ``LEFT_OUT``, so it holds neither the twin nor the only need of ``ALONE``.
    """
    document = _export("needs/api-traceability/needs.json")
    (version,) = document["versions"].values()
    needs = version["needs"]
    listed = [key for key in needs if key != LEFT_OUT]
    assert needs[LEFT_OUT]["satisfies"] and set(needs[LEFT_OUT]["satisfies"]) == set(ALONE)
    twin = {**needs[LISTED_OF_SHARED], "id": UNLISTED_TWIN}
    needs[UNLISTED_TWIN] = twin
    path = tmp_path / "implementations.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, listed


def _tests_verifying() -> dict[str, set[str]]:
    """The requirements each test-case need verifies, by the need's identifier."""
    (version,) = _export("needs/test-specification/needs.json")["versions"].values()
    return {key: set(need.get("verifies") or []) for key, need in version["needs"].items()}


def _checked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    """The ``proof check`` report over the bundle, with the list in the implementations block."""
    export, listed = _exports(tmp_path)
    opened = session(tmp_path, [copy_bundle(tmp_path)], capsys, implementation_export=export)
    document = yaml.safe_load(opened.config.read_text(encoding="utf-8"))
    document["producer"]["implementations"][support.KEY_NEED_IDS] = listed
    opened.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert run(capsys, "case", "sync", *opened.args())[0] == 0
    for kind in ("Refines", "Verifies", "Implements"):
        affirmed, _ = run(
            capsys,
            "edge", "affirm", *opened.args(), "--kind", kind,
            "--role", "fixture-reviewer", "--reason", "synthetic", "--revision", REVISION,
        )  # fmt: skip
        assert affirmed == 0
    status, out = run(
        capsys,
        "proof", "check", "--json", *opened.evidence_args(), *scope_args(), "--revision", REVISION,
    )  # fmt: skip
    assert status in (0, 1), out[-300:]
    return json.loads(out)


@_STRICT
def test_an_outcome_whose_only_witnessed_implementation_is_not_listed_is_set_aside(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With a list of need identifiers, an outcome with no listed implementation is set aside.

    The implementation export of the frozen evidence fixture has one more need, a
    copy of the need that implements SD-REQ-005 under another identifier, so that
    SD-REQ-005 has two implementation needs. The list holds every need of the
    fixture except the copy and except the need that alone implements SD-REQ-004,
    SD-REQ-009 and SD-REQ-010. The producer reads the fixture and one run
    bundle. Running proof check for the golden scope with the strong edges affirmed
    gives these results. The outcomes of the tests that verify only those three
    requirements are listed as discarded outcomes, and each has one finding of the
    condition for a discarded outcome, with severity information and the outcome
    as its subject. No outcome of the test that verifies SD-REQ-005 is discarded,
    so that outcome confirms through the listed need. No outcome of the test that
    verifies SD-REQ-003 and SD-REQ-009 is discarded: it confirms through the
    listed need of SD-REQ-003. The three requirements that lost their only need
    are coverage gaps, and SD-REQ-005 is not.

    :verifies: SEG-SREQ-355
    :verifies: SEG-SREQ-356
    :verifies: SEG-SREQ-359
    :test-id: SEG-TS-441
    """
    report = _checked(tmp_path, capsys)

    verifies = _tests_verifying()
    set_aside = {test for test, required in verifies.items() if required <= set(ALONE)}
    confirming = {
        test
        for test, required in verifies.items()
        if not required <= set(ALONE) and required & {SHARED, LISTED_OF_OTHER}
    }
    assert len(set_aside) == 3
    assert len(confirming) == 3

    discarded = set(report["discardedOutcomes"])
    tails = {outcome.rsplit("/", 1)[1] for outcome in discarded}
    assert tails == set_aside
    assert tails.isdisjoint(confirming)
    findings = [d for d in report["diagnostics"] if d["condition"] == DISCARDED.value]
    assert sorted(d["subject"] for d in findings) == sorted(discarded)
    assert {d["severity"] for d in findings} == {"info"}
    assert set(ALONE) <= set(report["coverageGaps"])
    assert SHARED not in report["coverageGaps"]
