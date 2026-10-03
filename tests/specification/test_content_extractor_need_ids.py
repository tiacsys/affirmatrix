"""Verification suite for the list of need identifiers, read by the content extractor.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
implementations block of the configuration can list need identifiers, and name
need types. The content extractor supplies a record for a need of the
implementation export when both settings that are given admit it. Every
fixture is built by the test in ``tmp_path`` (see ``need_ids_support``): four
needs over four macros of one header. The extractor is reached through the
configuration file, the way the command line reaches it. A test that shows a
refusal starts from a control that is accepted, so it fails for the claim and
never for an input that cannot be read at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix.sources import SourceError

from . import capture_support as support
from . import every_need_support as errors
from . import need_ids_support as ids

_STRICT = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-358: the list of need identifiers is dropped, so every need is read",
)
_STRICT_REFUSAL = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-360: a listed identifier that names no admitted need is not refused",
)
_STRICT_OUTSIDE = pytest.mark.xfail(
    strict=True,
    reason="SEG-SREQ-374: a need outside the list is read and refused, because the list is dropped",
)

NEED_IDS = support.KEY_NEED_IDS
TYPES = support.KEY_TYPES


@_STRICT
def test_a_list_of_need_identifiers_alone_selects_the_needs_it_names(tmp_path: Path) -> None:
    """With a list of need identifiers and no need types, a need is read when it is listed.

    The implementation export holds I-ONE, I-TWO and I-THREE of the type impl
    and I-OTHER of the type other, each over a macro that the Doxygen output
    locates. The list I-ONE, I-OTHER is configured and no need types are. The
    extractor supplies a record for I-ONE and for I-OTHER, and for no other
    need. Each of the two has one Implements edge, and no other need has one.
    The type of a listed need does not matter when no types are configured.

    :verifies: SEG-SREQ-358
    :test-id: SEG-TS-425
    """
    library = ids.Library(tmp_path)

    assert library.supplied(**{NEED_IDS: ["I-ONE", "I-OTHER"]}) == {"I-ONE", "I-OTHER"}
    assert library.implemented(**{NEED_IDS: ["I-ONE", "I-OTHER"]}) == {"I-ONE", "I-OTHER"}


def test_need_types_alone_select_the_needs_of_those_types(tmp_path: Path) -> None:
    """With need types and no list of need identifiers, a need is read when its type is one of them.

    The implementation export holds I-ONE, I-TWO and I-THREE of the type impl
    and I-OTHER of the type other. The types {impl} are configured and no list is.
    The extractor supplies a record for each of the three needs of the type impl
    and none for I-OTHER. With the types {other} it supplies one for I-OTHER and
    for no other need. With the types {impl, other} it supplies all four.

    :verifies: SEG-SREQ-275
    :test-id: SEG-TS-426
    """
    library = ids.Library(tmp_path)

    assert library.supplied(**{TYPES: ["impl"]}) == set(ids.IMPL)
    assert library.supplied(**{TYPES: ["other"]}) == {"I-OTHER"}
    assert library.supplied(**{TYPES: ["impl", "other"]}) == set(ids.ALL)


@_STRICT
def test_a_need_must_be_listed_and_of_a_configured_type_to_be_read(tmp_path: Path) -> None:
    """With need types and a list of need identifiers, a need is read when it is listed and typed.

    The implementation export holds I-ONE, I-TWO and I-THREE of the type impl
    and I-OTHER of the type other. The types {impl} and the list I-ONE, I-TWO are
    configured. The extractor supplies a record for I-ONE and I-TWO. It supplies
    none for I-THREE, which has the type but is not listed, and none for
    I-OTHER, which has neither. With the types {impl, other} and the list I-ONE,
    I-OTHER it supplies I-ONE and I-OTHER, and not I-TWO.

    :verifies: SEG-SREQ-358
    :test-id: SEG-TS-427
    """
    library = ids.Library(tmp_path)

    assert library.supplied(**{TYPES: ["impl"], NEED_IDS: ["I-ONE", "I-TWO"]}) == {
        "I-ONE",
        "I-TWO",
    }
    both = {TYPES: ["impl", "other"], NEED_IDS: ["I-ONE", "I-OTHER"]}
    assert library.supplied(**both) == {"I-ONE", "I-OTHER"}
    assert library.implemented(**both) == {"I-ONE", "I-OTHER"}


def test_without_types_and_without_a_list_every_need_is_read(tmp_path: Path) -> None:
    """While neither need types nor a list of need identifiers is configured, every need is read.

    The implementation export holds I-ONE, I-TWO and I-THREE of the type impl
    and I-OTHER of the type other. The configuration names no need types and no
    list. The extractor supplies a record for each of the four needs, and one
    Implements edge from each. A configuration whose list is null, which is
    the same as no list, supplies the same four.

    :verifies: SEG-SREQ-276
    :test-id: SEG-TS-428
    """
    library = ids.Library(tmp_path)

    assert library.supplied() == set(ids.ALL)
    assert library.implemented() == set(ids.ALL)
    assert library.supplied(**{NEED_IDS: None}) == set(ids.ALL)


def _refusal(library: ids.Library, **keys: object) -> SourceError:
    """The one error that building the extractor over ``keys`` and taking its records raises."""
    path = library.configuration(**keys)
    return errors.raises_once(lambda: support.records(path), SourceError)  # type: ignore[return-value]


@_STRICT_REFUSAL
def test_a_listed_identifier_that_names_no_need_is_refused(tmp_path: Path) -> None:
    """A listed need identifier that names no need of the export is refused, naming it.

    The implementation export holds I-ONE, I-TWO, I-THREE and I-OTHER. The list
    I-ONE, I-GONE is configured. Reading the export raises one error from the
    extractor. The error names I-GONE and does not name I-ONE. A control that
    lists I-ONE and I-TWO is read without an error.

    :verifies: SEG-SREQ-360
    :test-id: SEG-TS-429
    """
    library = ids.Library(tmp_path)
    assert library.supplied(**{NEED_IDS: ["I-ONE", "I-TWO"]}) is not None

    refused = _refusal(library, **{NEED_IDS: ["I-ONE", "I-GONE"]})

    assert "I-GONE" in str(refused)
    assert "I-ONE" not in str(refused)


@_STRICT_REFUSAL
def test_a_listed_identifier_of_a_need_of_another_type_is_refused(tmp_path: Path) -> None:
    """A listed need identifier whose need the configured types do not admit is refused.

    The implementation export holds I-ONE and I-TWO of the type impl, and
    I-OTHER of the type other. The types {impl} and the list I-ONE, I-OTHER are
    configured. Reading the export raises one error from the extractor. The
    error names I-OTHER and does not name I-ONE. A control that configures the
    types {impl, other} with the same list is read without an error, and the
    extractor supplies I-ONE and I-OTHER.

    :verifies: SEG-SREQ-360
    :test-id: SEG-TS-430
    """
    library = ids.Library(tmp_path)
    admitted = library.supplied(**{TYPES: ["impl", "other"], NEED_IDS: ["I-ONE", "I-OTHER"]})
    assert admitted == {"I-ONE", "I-OTHER"}

    refused = _refusal(library, **{TYPES: ["impl"], NEED_IDS: ["I-ONE", "I-OTHER"]})

    assert "I-OTHER" in str(refused)
    assert "I-ONE" not in str(refused)


@_STRICT_REFUSAL
def test_every_listed_identifier_that_names_no_need_is_named_in_one_error(tmp_path: Path) -> None:
    """Every listed need identifier that names no admitted need is named in one error.

    The implementation export holds I-ONE, I-TWO and I-THREE of the type impl and
    I-OTHER of the type other. The types {impl} and the list I-ONE, I-GONE-A,
    I-OTHER, I-GONE-B are configured: two identifiers that name no need and one
    that names a need of another type. Reading the export raises one error from
    the extractor. The error names I-GONE-A, I-OTHER and I-GONE-B, and does not
    name I-ONE. It names each of the three once.

    :verifies: SEG-SREQ-360
    :test-id: SEG-TS-431
    """
    library = ids.Library(tmp_path)

    refused = _refusal(
        library, **{TYPES: ["impl"], NEED_IDS: ["I-ONE", "I-GONE-A", "I-OTHER", "I-GONE-B"]}
    )

    lines = errors.lines_of(refused)
    for name in ("I-GONE-A", "I-OTHER", "I-GONE-B"):
        assert len([line for line in lines if name in line]) == 1, (name, str(refused))
    assert not [line for line in lines if "I-ONE" in line]


#: A need that is misshapen, in two ways, and a need whose macro no member of the tree names.
MISSHAPEN = (
    {k: v for k, v in support.implementation_need("I-NO-TITLE", "x").items() if k != "title"},
    support.implementation_need("I-BAD-LINKS", "M_ONE", satisfies="R-1"),
)
NO_MACRO = (support.implementation_need("I-NO-MACRO", "M_NOT_IN_THE_TREE"),)


@_STRICT_OUTSIDE
def test_a_need_outside_the_list_is_not_refused(tmp_path: Path) -> None:
    """A need that is not in the list of need identifiers is not refused, whatever its fault.

    The implementation export holds I-ONE and I-TWO, which the Doxygen output
    locates, and needs of the type impl that the extractor cannot use. In the
    first export they are I-NO-TITLE, which has no title, and I-BAD-LINKS, whose
    links are a text and not a list. In the second export the need is
    I-NO-MACRO, whose macro is in no member of the output. Without a list,
    reading each export raises an error that names its faulty needs. With the
    list I-ONE, I-TWO the extractor supplies a record for the two needs and raises
    no error, for each export. With a list that holds I-ONE and one faulty need
    it raises an error that names that need, and does not name the other faulty
    need of the export: a need that is listed is still refused for its fault.

    :verifies: SEG-SREQ-374
    :test-id: SEG-TS-432
    """
    shapes = ids.Library(tmp_path / "shape", extra=MISSHAPEN)
    unlisted = _refusal(shapes, **{TYPES: ["impl"]})
    assert "I-NO-TITLE" in str(unlisted)
    assert "I-BAD-LINKS" in str(unlisted)
    assert shapes.supplied(**{NEED_IDS: ["I-ONE", "I-TWO"]}) == {"I-ONE", "I-TWO"}
    listed = _refusal(shapes, **{NEED_IDS: ["I-ONE", "I-NO-TITLE"]})
    assert "I-NO-TITLE" in str(listed)
    assert "I-BAD-LINKS" not in str(listed)

    macros = ids.Library(tmp_path / "macro", extra=NO_MACRO)
    assert "I-NO-MACRO" in str(_refusal(macros, **{TYPES: ["impl"]}))
    assert macros.supplied(**{NEED_IDS: ["I-ONE", "I-TWO"]}) == {"I-ONE", "I-TWO"}
    assert "I-NO-MACRO" in str(_refusal(macros, **{NEED_IDS: ["I-ONE", "I-NO-MACRO"]}))
