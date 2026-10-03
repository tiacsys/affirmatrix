"""Verification suite for a requirement whose tests ran on more than one board.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. One
run artifact can hold the same test on several platforms. The outcome extractor
gives one outcome for each platform, and each outcome confirms the one test
specification. The satisfaction rule then reads all of them: every confirming
outcome that is not skipped must pass.

Each test writes a run bundle with three suites of one scenario, one suite for
each platform, and reads the outcomes through the outcome extractor. It builds
the graph of one leaf requirement from those outcomes (see
``need_types_support``) and reads the verdict of the satisfaction evaluator and
the report of the package gate. The platform ``mps2/an385`` holds a slash, so
the identity of its outcome holds a hyphen in its place.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from affirmatrix import satisfaction

from . import need_types_support as support

SUITE = "queue"
FUNCTION = "test_put_get"
BOARDS = ("native_sim/native/64", "qemu_x86", "mps2/an385")
RESULT = support.result_identifier(support.SCENARIO, SUITE, FUNCTION)


def _outcome(board: str) -> str:
    """The local identifier of the outcome of the test on one board."""
    run = f"{support.RUN_NAME}-{board.replace('/', '-')}-{support.SCENARIO}"
    return f"{run}/{support.SPECIFICATION}"


def _extractor(tmp_path: Path, statuses: Mapping[str, str]):
    """The outcome extractor over one run artifact: each board in ``statuses`` ran the test."""
    case = support.case_need(support.SPECIFICATION, SUITE, FUNCTION)
    specifications, implementations = support.exports(tmp_path, [case])
    suites = [(support.SCENARIO, board, [(RESULT, status)]) for board, status in statuses.items()]
    bundle = support.write_bundle(tmp_path / "bundle", suites)
    return support.outcome_extractor(bundle, specifications, implementations)


def _on_each_board(*statuses: str) -> dict[str, str]:
    return dict(zip(BOARDS, statuses, strict=False))


def test_a_leaf_is_satisfied_when_the_test_passed_on_every_board(tmp_path: Path) -> None:
    """A leaf is satisfied when the test of its specification passed on every board.

    One run artifact records one test on three platforms, native_sim/native/64,
    qemu_x86 and mps2/an385, and the test passed on each. One leaf requirement
    has an active Verifies edge from the specification of the test and an active
    Implements edge. The extractor supplies three outcomes, one for each platform,
    and each outcome has a Confirms edge to the specification. The satisfaction
    evaluator reports the leaf as satisfied. The same holds for the first two
    platforms alone.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-331
    """
    extractor = _extractor(tmp_path / "three", _on_each_board("passed", "passed", "passed"))

    assert support.outcome_ids(extractor) == [_outcome(board) for board in BOARDS]
    assert support.edge_pairs(extractor, "Confirms") == sorted(
        (_outcome(board), support.SPECIFICATION) for board in BOARDS
    )
    assert satisfaction.leaf_satisfied(support.built_graph(extractor), support.REQUIREMENT)

    two = _extractor(tmp_path / "two", _on_each_board("passed", "passed"))
    assert satisfaction.leaf_satisfied(support.built_graph(two), support.REQUIREMENT)


def test_a_leaf_is_not_satisfied_when_the_test_failed_on_one_board(tmp_path: Path) -> None:
    """A leaf is not satisfied when the test failed on one board, though it passed on the others.

    One run artifact records one test on three platforms. The test passed on two
    and failed on one, and the failing board is in turn the first, the second and
    the third. The extractor supplies three outcomes. For each order, the
    satisfaction evaluator reports the leaf as not satisfied. The package gate
    blocks, and the outcome of the failing board is the one outcome that no waiver
    excuses. A control with the test passed on every board is satisfied.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-332
    """
    control = _extractor(tmp_path / "control", _on_each_board("passed", "passed", "passed"))
    assert satisfaction.leaf_satisfied(support.built_graph(control), support.REQUIREMENT)

    for failing in range(len(BOARDS)):
        statuses = ["passed"] * len(BOARDS)
        statuses[failing] = "failed"
        extractor = _extractor(tmp_path / f"fail-{failing}", _on_each_board(*statuses))
        built = support.built_graph(extractor)

        assert len(support.outcome_ids(extractor)) == len(BOARDS)
        assert not satisfaction.leaf_satisfied(built, support.REQUIREMENT), failing
        report = support.package_report(built)
        assert report.blocked, failing
        assert report.unwaived_outcomes == {_outcome(BOARDS[failing])}, failing


def test_a_board_that_skipped_the_test_adds_no_obligation(tmp_path: Path) -> None:
    """A board that skipped the test adds no obligation: the others decide the leaf.

    One run artifact records one test on three platforms. The test passed on two
    and was skipped on one, and the skipping board is in turn the first, the
    second and the third. The extractor supplies three outcomes. For each order, the
    satisfaction evaluator reports the leaf as satisfied. The package gate lists
    the skipped outcome and no other, and the gate does not block. The same holds
    for a run artifact with two platforms, where the test was skipped on one and
    passed on the other.

    :verifies: SEG-SREQ-006
    :test-id: SEG-TS-333
    """
    for skipping in range(len(BOARDS)):
        statuses = ["passed"] * len(BOARDS)
        statuses[skipping] = "skipped"
        extractor = _extractor(tmp_path / f"skip-{skipping}", _on_each_board(*statuses))
        built = support.built_graph(extractor)

        assert satisfaction.leaf_satisfied(built, support.REQUIREMENT), skipping
        report = support.package_report(built)
        assert report.skipped_outcomes == {_outcome(BOARDS[skipping])}, skipping
        assert not report.blocked, skipping

    pair = _extractor(tmp_path / "pair", _on_each_board("skipped", "passed"))
    assert satisfaction.leaf_satisfied(support.built_graph(pair), support.REQUIREMENT)
