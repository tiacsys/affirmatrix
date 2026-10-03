"""Verification suite for the list of need identifiers, read by the outcome extractor.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
outcome extractor reads the implementation export to give each outcome a
Witnesses edge to the implementations of what its test verifies. The same two
settings that narrow the needs for the content extractor narrow them here: a
list of need identifiers and need types. A fixture of one requirement, two test
cases that verify it and three implementation needs that satisfy it is built
by the test in ``tmp_path`` (see ``need_ids_support``). The extractor is built
from the inputs that the loader gives for a configuration file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix.sources.outcomes import OutcomeError

from . import capture_support as support
from . import every_need_support as errors
from . import need_ids_support as ids
from . import need_types_support as nt

_STRICT = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-359: the list of need identifiers is dropped, so every need is read",
)
_STRICT_REFUSAL = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-361: a listed identifier that names no admitted need is not refused",
)
_STRICT_OUTSIDE = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-375: a need outside the list is read and refused, because the list is dropped",
)

NEED_IDS = support.KEY_NEED_IDS
TYPES = support.KEY_TYPES
RUN = f"{nt.RUN_NAME}-{ids.Witnessing.PLATFORM}-{nt.SCENARIO}"
OUTCOMES = [f"{RUN}/TC-A", f"{RUN}/TC-B"]


def _everywhere(*targets: str) -> dict[str, list[str]]:
    """Each of the two outcomes has a Witnesses edge to each of ``targets``."""
    return {outcome: sorted(targets) for outcome in OUTCOMES}


@_STRICT
def test_witnesses_run_only_to_the_listed_implementation_needs(tmp_path: Path) -> None:
    """With a list and no need types, an outcome witnesses the listed needs only.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design. Each satisfies the requirement that two test cases verify. A
    run bundle holds one passed result for each test case. The list IMPL-A, IMPL-C
    is configured and no need types are. Each of the two outcomes has a Witnesses
    edge to IMPL-A and to IMPL-C, and to no other need. A control without the
    list gives each outcome an edge to all three.

    :verifies: SEG-SREQ-359
    :test-id: SEG-TS-433
    """
    world = ids.Witnessing(tmp_path)
    assert world.witnessed() == _everywhere("IMPL-A", "IMPL-B", "IMPL-C")

    assert world.witnessed(**{NEED_IDS: ["IMPL-A", "IMPL-C"]}) == _everywhere("IMPL-A", "IMPL-C")


def test_witnesses_run_only_to_the_implementation_needs_of_the_configured_types(
    tmp_path: Path,
) -> None:
    """With need types and no list, an outcome witnesses the needs of those types.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design. Each satisfies the requirement that two test cases verify. A
    run bundle holds one passed result for each test case. The types {impl} are
    configured and no list is. Each of the two outcomes has a Witnesses edge to
    IMPL-A and to IMPL-B and to no other need. With the types {design} each has
    one edge, to IMPL-C.

    :verifies: SEG-SREQ-339
    :test-id: SEG-TS-434
    """
    world = ids.Witnessing(tmp_path)

    assert world.witnessed(**{TYPES: ["impl"]}) == _everywhere("IMPL-A", "IMPL-B")
    assert world.witnessed(**{TYPES: ["design"]}) == _everywhere("IMPL-C")


@_STRICT
def test_an_outcome_witnesses_a_need_that_is_listed_and_of_a_configured_type(
    tmp_path: Path,
) -> None:
    """With need types and a list of need identifiers, a witnessed need is listed and typed.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design, and each satisfies the requirement that two test cases
    verify. The types {impl} and the list IMPL-A are configured. Each of the two
    outcomes has one Witnesses edge, to IMPL-A. There is none to IMPL-B, which has
    the type and is not listed, and none to IMPL-C, which has neither. With the
    types {impl, design} and the list IMPL-B, IMPL-C each outcome has an edge to
    those two needs only.

    :verifies: SEG-SREQ-359
    :test-id: SEG-TS-435
    """
    world = ids.Witnessing(tmp_path)

    assert world.witnessed(**{TYPES: ["impl"], NEED_IDS: ["IMPL-A"]}) == _everywhere("IMPL-A")
    both = {TYPES: ["impl", "design"], NEED_IDS: ["IMPL-B", "IMPL-C"]}
    assert world.witnessed(**both) == _everywhere("IMPL-B", "IMPL-C")


def test_without_types_and_without_a_list_an_outcome_witnesses_every_need(tmp_path: Path) -> None:
    """While neither need types nor a list is configured, an outcome witnesses every need.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design, and each satisfies the requirement that two test cases
    verify. The configuration names no need types and no list. Each of the two
    outcomes has a Witnesses edge to each of the three needs. A list that is null,
    which is the same as no list, gives the same edges.

    :verifies: SEG-SREQ-340
    :test-id: SEG-TS-436
    """
    world = ids.Witnessing(tmp_path)
    everything = _everywhere("IMPL-A", "IMPL-B", "IMPL-C")

    assert world.witnessed() == everything
    assert world.witnessed(**{NEED_IDS: None}) == everything


def _refusal(world: ids.Witnessing, **keys: object) -> OutcomeError:
    """The one error that building the outcome extractor over ``keys`` raises."""
    return errors.raises_once(lambda: world.extractor(**keys), OutcomeError)  # type: ignore[return-value]


@_STRICT_REFUSAL
def test_a_listed_identifier_that_names_no_need_is_refused_by_the_outcome_extractor(
    tmp_path: Path,
) -> None:
    """A listed need identifier that names no need of the export is refused, naming it.

    The implementation export holds IMPL-A, IMPL-B and IMPL-C. The list IMPL-A,
    IMPL-GONE is configured. Building the outcome extractor raises one error. The
    error names IMPL-GONE and does not name IMPL-A. A control that lists IMPL-A and
    IMPL-B builds the extractor without an error.

    :verifies: SEG-SREQ-361
    :test-id: SEG-TS-437
    """
    world = ids.Witnessing(tmp_path)
    assert world.extractor(**{NEED_IDS: ["IMPL-A", "IMPL-B"]}) is not None

    refused = _refusal(world, **{NEED_IDS: ["IMPL-A", "IMPL-GONE"]})

    assert "IMPL-GONE" in str(refused)
    assert "IMPL-A" not in str(refused)


@_STRICT_REFUSAL
def test_a_listed_identifier_of_a_need_of_another_type_is_refused_by_the_outcome_extractor(
    tmp_path: Path,
) -> None:
    """A listed need identifier whose need the configured types do not admit is refused.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design. The types {impl} and the list IMPL-A, IMPL-C are configured.
    Building the outcome extractor raises one error. The error names IMPL-C and
    does not name IMPL-A. A control that configures the types {impl, design}
    with the same list builds the extractor without an error.

    :verifies: SEG-SREQ-361
    :test-id: SEG-TS-438
    """
    world = ids.Witnessing(tmp_path)
    assert world.extractor(**{TYPES: ["impl", "design"], NEED_IDS: ["IMPL-A", "IMPL-C"]})

    refused = _refusal(world, **{TYPES: ["impl"], NEED_IDS: ["IMPL-A", "IMPL-C"]})

    assert "IMPL-C" in str(refused)
    assert "IMPL-A" not in str(refused)


@_STRICT_REFUSAL
def test_every_listed_identifier_that_names_no_need_is_named_in_one_outcome_error(
    tmp_path: Path,
) -> None:
    """Every listed need identifier that names no admitted need is named in one error.

    The implementation export holds IMPL-A and IMPL-B of the type impl and IMPL-C of
    the type design. The types {impl} and the list IMPL-A, IMPL-GONE-A, IMPL-C,
    IMPL-GONE-B are configured: two identifiers that name no need and one that
    names a need of another type. Building the outcome extractor raises one
    error. The error names IMPL-GONE-A, IMPL-C and IMPL-GONE-B, once each, and
    does not name IMPL-A.

    :verifies: SEG-SREQ-361
    :test-id: SEG-TS-439
    """
    world = ids.Witnessing(tmp_path)

    refused = _refusal(
        world, **{TYPES: ["impl"], NEED_IDS: ["IMPL-A", "IMPL-GONE-A", "IMPL-C", "IMPL-GONE-B"]}
    )

    lines = errors.lines_of(refused)
    for name in ("IMPL-GONE-A", "IMPL-C", "IMPL-GONE-B"):
        assert len([line for line in lines if name in line]) == 1, (name, str(refused))
    assert not [line for line in lines if "IMPL-A" in line]


#: Needs of the type impl that the outcome extractor cannot use, each in its own way.
MISSHAPEN = {
    "IMPL-RENAMED": nt.implementation_need("OTHER-ID"),
    "IMPL-BAD-LINKS": nt.implementation_need("IMPL-BAD-LINKS", satisfies="SREQ-1"),
}


@_STRICT_OUTSIDE
def test_a_need_outside_the_list_is_not_refused_by_the_outcome_extractor(tmp_path: Path) -> None:
    """A need that is not in the list of need identifiers is not refused, whatever its fault.

    The implementation export holds IMPL-A, IMPL-B and IMPL-C, and two needs that the
    outcome extractor cannot use: IMPL-RENAMED, whose id is another text than its key, and
    IMPL-BAD-LINKS, whose links are a text and not a list. Without a list,
    building the outcome extractor raises an error that names the two. With the
    list IMPL-A, IMPL-B the extractor is built without an error, and each outcome
    has a Witnesses edge to those two needs. With a list that holds IMPL-A and
    IMPL-BAD-LINKS it raises an error that names IMPL-BAD-LINKS and not IMPL-RENAMED:
    a need that is listed is still refused for its fault.

    :verifies: SEG-SREQ-375
    :test-id: SEG-TS-440
    """
    world = ids.Witnessing(tmp_path, extra=MISSHAPEN)

    unlisted = _refusal(world)
    assert "IMPL-RENAMED" in str(unlisted)
    assert "IMPL-BAD-LINKS" in str(unlisted)

    assert world.witnessed(**{NEED_IDS: ["IMPL-A", "IMPL-B"]}) == _everywhere("IMPL-A", "IMPL-B")

    listed = _refusal(world, **{NEED_IDS: ["IMPL-A", "IMPL-BAD-LINKS"]})
    assert "IMPL-BAD-LINKS" in str(listed)
    assert "IMPL-RENAMED" not in str(listed)
