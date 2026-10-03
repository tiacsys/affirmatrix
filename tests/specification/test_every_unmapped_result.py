"""Verification suite for the error that names every unmapped or ambiguous result of a run.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A run
artifact can hold many results that map to no test-case need, and some that map
to more than one. The outcome extractor must name all of them in one error. The
full run of a real project holds hundreds of them, so the error must stay easy
to read: it starts with a count and lists the results in the order of the
artifact, and a second run over the same artifact gives the same text.

Every fixture is built by the test, in ``tmp_path``: a test-case export of three
needs, two of which share a test function, and a run bundle whose one artifact
holds the results the test chooses. The extractor is built from its inputs and
not through the command line (``every_need_support`` has the builders).
"""

from __future__ import annotations

import re
from pathlib import Path

from . import every_need_support as support
from . import need_types_support as nt

PUT_GET = support.result_of("test_put_get")
TWIN = support.result_of("test_twin")


def _unmapped(name: str) -> str:
    return support.result_of(f"test_unmapped_{name}")


def _lines_naming_result(lines: list[str], identifier: str) -> list[str]:
    return [line for line in lines if f"'{identifier}'" in line]


def test_every_unmapped_and_ambiguous_result_is_named_in_one_error(tmp_path: Path) -> None:
    """Every unmapped or ambiguous result of a run artifact is named in one error.

    A run artifact holds one board with five results: PUT_GET, which maps to one
    need, three results that map to no need, and one result of a test that two
    needs share. The extractor raises one error. It has one line for each of the
    four bad results. Each line holds the identifier of the result. The line of an
    unmapped result says that it maps to no test-case need. The line of the
    ambiguous result names both needs. The error does not name the result that
    maps to one need. A control artifact that holds only one unmapped result, with
    the good one, is refused with an error that names it.

    :verifies: SEG-SREQ-354
    :test-id: SEG-TS-399
    """
    results = [
        (PUT_GET, "passed"),
        (_unmapped("z"), "failed"),
        (TWIN, "passed"),
        (_unmapped("a"), "skipped"),
        (_unmapped("m"), "passed"),
    ]
    error, _, _ = support.outcome_refusal(
        tmp_path / "several", [(nt.SCENARIO, "native_sim", results)]
    )
    lines = support.lines_of(error)
    for name in ("z", "a", "m"):
        named = _lines_naming_result(lines, _unmapped(name))
        assert len(named) == 1, (name, str(error))
        assert "no test-case need" in named[0]
    (twin,) = _lines_naming_result(lines, TWIN)
    assert "'TC-TWIN-ONE'" in twin and "'TC-TWIN-TWO'" in twin
    assert _lines_naming_result(lines, PUT_GET) == []

    control, _, _ = support.outcome_refusal(
        tmp_path / "one",
        [(nt.SCENARIO, "native_sim", [(PUT_GET, "passed"), (_unmapped("a"), "passed")])],
    )
    assert _lines_naming_result(support.lines_of(control), _unmapped("a"))
    assert _lines_naming_result(support.lines_of(control), PUT_GET) == []


def _big_artifact() -> tuple[list, int]:
    """Two boards with 60 bad results among good ones: 58 unmapped and two ambiguous.

    The same unmapped test is on both boards, so the list holds the same
    identifier twice, once for each result.
    """
    first = [(PUT_GET, "passed")]
    second = [(PUT_GET, "passed")]
    for number in range(29):
        first.append((_unmapped(f"{number:03d}"), "passed"))
        second.append((_unmapped(f"{number:03d}"), "skipped"))
    first.append((TWIN, "passed"))
    second.append((TWIN, "passed"))
    suites = [
        (nt.SCENARIO, support.PLATFORM, first),
        (nt.SCENARIO, support.SECOND_PLATFORM, second),
    ]
    return suites, 60


def test_the_error_for_unmapped_results_starts_with_a_count(tmp_path: Path) -> None:
    """The error for unmapped or ambiguous results of a run starts with a count line.

    A run artifact holds two boards. The first board holds 29 unmapped results and
    one ambiguous result. The second board holds the same 29 unmapped results and
    the same ambiguous result again, and each board also holds one good result. So
    the artifact holds 60 bad results, which are 58 unmapped results and two
    ambiguous ones. The first line of the error holds the number 60 and no other
    number, once the paths of the bundle and the artifact are cut out of it, and it
    names no result. The error has one more line for each bad result, so 61 lines.
    With a single bad result the first line holds the number 1 and one line
    follows.

    :verifies: SEG-SREQ-354
    :test-id: SEG-TS-400
    """
    suites, expected = _big_artifact()
    error, artifact, bundle = support.outcome_refusal(tmp_path / "many", suites)
    lines = support.lines_of(error)
    hidden = [tmp_path, bundle, artifact]
    assert support.numbers_in(lines[0], hidden) == [expected], lines[0]
    assert len(lines) == 1 + expected
    assert _lines_naming_result(lines[:1], _unmapped("000")) == []

    control, artifact, bundle = support.outcome_refusal(
        tmp_path / "one", [(nt.SCENARIO, support.PLATFORM, [(_unmapped("a"), "passed")])]
    )
    lines = support.lines_of(control)
    assert support.numbers_in(lines[0], [tmp_path, bundle, artifact]) == [1], lines[0]
    assert len(lines) == 2


def test_unmapped_results_are_listed_in_the_order_of_the_artifact_every_time(
    tmp_path: Path,
) -> None:
    """The bad results of a run are listed in the order of the run artifact, and the text is stable.

    A run artifact holds two boards. The identifiers of the bad results are not in
    alphabetical order in the artifact: three unmapped results and one ambiguous
    result on the first board, then two unmapped results on the second board. The
    lines of the error name the six results in the order of the artifact. Building
    the extractor a second time over the same artifact gives an error with the same
    text.

    :verifies: SEG-SREQ-354
    :test-id: SEG-TS-401
    """
    order = [_unmapped("z"), TWIN, _unmapped("a"), _unmapped("m"), _unmapped("c"), _unmapped("b")]
    suites = [
        (
            nt.SCENARIO,
            support.PLATFORM,
            [(order[0], "passed"), (PUT_GET, "passed"), (order[1], "passed"), (order[2], "failed")],
        ),
        (
            nt.SCENARIO,
            support.SECOND_PLATFORM,
            [(order[3], "passed"), (order[4], "passed"), (order[5], "skipped")],
        ),
    ]
    error, _, _ = support.outcome_refusal(tmp_path / "first", suites)
    lines = support.lines_of(error)
    named = [identifier for line in lines for identifier in order if f"'{identifier}'" in line]
    assert named == order
    again, _, _ = support.outcome_refusal(tmp_path / "second", suites)
    assert re.sub(re.escape(str(tmp_path)) + r"/\w+", "", str(again)) == re.sub(
        re.escape(str(tmp_path)) + r"/\w+", "", str(error)
    )


def test_a_result_with_the_status_not_run_is_refused_for_its_status(tmp_path: Path) -> None:
    """A result with the status not run is refused for its status, with no result left out.

    A run artifact holds the result PUT_GET with the status not run, which maps to
    one need, and after it three results that map to no need. The extractor raises
    an error that names the result PUT_GET and says that its status has no
    counterpart in the closed set. This is a refusal of its own: it does not name
    the three unmapped results, which come after it in the artifact. An artifact
    whose only bad result has the status not run is refused the same way.

    :verifies: SEG-SREQ-184
    :test-id: SEG-TS-402
    """
    results = [(PUT_GET, "not run"), *((_unmapped(n), "passed") for n in ("a", "b", "c"))]
    error, _, _ = support.outcome_refusal(
        tmp_path / "mixed", [(nt.SCENARIO, "native_sim", results)]
    )
    text = str(error)
    assert f"'{PUT_GET}'" in text and "'not run'" in text
    assert all(f"'{_unmapped(n)}'" not in text for n in ("a", "b", "c"))

    alone, _, _ = support.outcome_refusal(
        tmp_path / "alone", [(nt.SCENARIO, "native_sim", [(PUT_GET, "not run")])]
    )
    assert f"'{PUT_GET}'" in str(alone) and "'not run'" in str(alone)


def test_every_not_run_result_is_named_in_one_status_refusal(tmp_path: Path) -> None:
    """Every result with the status not run is named in one refusal for its status.

    A run artifact holds two boards. The first board holds, in this order, an
    unmapped result, a result with the status not run, a second unmapped result and
    a second result with the status not run. The second board holds a result with
    the status not run, then an unmapped result. The extractor raises one error. It
    has one line for each of the three results with the status not run, and each
    line holds the identifier of the result and the status. It names none of the
    unmapped results, even those that come before a result with the status not run.
    A second artifact holds one board with two unmapped results and then one result
    with the status not run. It is refused for the status, and its error names none
    of the unmapped results.

    :verifies: SEG-SREQ-184
    :test-id: SEG-TS-412
    """
    quiet = _unmapped("a"), _unmapped("b"), _unmapped("c")
    suites = [
        (
            nt.SCENARIO,
            support.PLATFORM,
            [(quiet[0], "passed"), (PUT_GET, "not run"), (quiet[1], "failed"), (TWIN, "not run")],
        ),
        (nt.SCENARIO, support.SECOND_PLATFORM, [(PUT_GET, "not run"), (quiet[2], "passed")]),
    ]
    error, _, _ = support.outcome_refusal(tmp_path / "spread", suites)
    lines = support.lines_of(error)
    not_run = [line for line in lines if "'not run'" in line]
    assert len(not_run) == 3, str(error)
    assert sum(f"'{PUT_GET}'" in line for line in not_run) == 2
    assert sum(f"'{TWIN}'" in line for line in not_run) == 1
    assert all(f"'{name}'" not in str(error) for name in quiet)

    late, _, _ = support.outcome_refusal(
        tmp_path / "late",
        [
            (
                nt.SCENARIO,
                support.PLATFORM,
                [(quiet[0], "passed"), (quiet[1], "passed"), (PUT_GET, "not run")],
            )
        ],
    )
    assert "'not run'" in str(late) and f"'{PUT_GET}'" in str(late)
    assert all(f"'{name}'" not in str(late) for name in quiet[:2])


def test_each_unmapped_result_line_names_its_board_and_scenario(tmp_path: Path) -> None:
    """Each line of the error for unmapped results holds the board and the scenario.

    A run artifact holds two boards that run the scenario scn.alpha, on the
    platforms native_sim and qemu_x86, and a third board that runs the scenario
    scn.beta on native_sim. Each board holds the same unmapped result, whose
    identifier does not begin with the name of any scenario. The extractor raises
    one error with one line for each of the three results. The line of each result
    holds its platform and its scenario. The three lines are different from one
    another. The error has a count line first, and that line names no platform and
    no scenario.

    :verifies: SEG-SREQ-354
    :test-id: SEG-TS-413
    """
    identifier = "other.suite.unmapped_q"
    boards = [
        ("scn.alpha", support.PLATFORM),
        ("scn.alpha", support.SECOND_PLATFORM),
        ("scn.beta", support.PLATFORM),
    ]
    suites = [(scenario, platform, [(identifier, "passed")]) for scenario, platform in boards]
    error, _, _ = support.outcome_refusal(tmp_path, suites)
    lines = support.lines_of(error)
    items = [line for line in lines if f"'{identifier}'" in line]
    assert len(items) == 3, str(error)
    for line, (scenario, platform) in zip(items, boards, strict=True):
        assert scenario in line and platform in line, line
    assert len(set(items)) == 3
    assert "scn." not in lines[0] and support.PLATFORM not in lines[0]
