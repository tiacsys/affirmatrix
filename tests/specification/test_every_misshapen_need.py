"""Verification suite for the error that names every misshapen need of an export.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
real export can hold many misshapen needs. Each reader of a need export must
name all of them in one error, so the operator fixes the export once.

Every fixture is built by the test, in ``tmp_path``: an export of five needs
under chosen keys, three of them misshapen in the three ways the claims name,
and two good ones. The readers are built from their inputs and not through the
command line, so a test reads one component (``every_need_support`` has the
builders). The one test that goes through the command line is marked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import every_need_support as support

_STRICT = pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-351 to 353: the error names only the first misshapen need"
)


@pytest.mark.parametrize("name", support.CONTENT_FAMILIES)
@_STRICT
def test_the_content_extractor_names_every_misshapen_need_of_an_export(
    tmp_path: Path, name: str
) -> None:
    """The content extractor names every misshapen need of an export in one error.

    An export of the content extractor holds five needs, in the stream of the
    implementations or in the stream of the test cases, one stream at a time. One
    need lacks a text field the extractor reads. One need declares an id other than
    its key. One need has a link field that is a text and not a list. The other two
    are good. Building the extractor raises one error. The error has one line for
    each of the three bad needs. Each line holds the key of the need and a word
    that tells why: the name of the missing field, the id that was declared, or the
    name of the link field. No line names a good need. A control export that holds
    only one of the three bad needs, with the two good ones, is refused with an
    error that names that need.

    :verifies: SEG-SREQ-351
    :test-id: SEG-TS-389
    """
    reader = support.family(name)
    error, _ = support.refusal_of_misshapen(tmp_path / "several", reader)
    support.check_misshapen_report(error, reader.link_field, reader.text_field)

    control, _ = support.refusal_of_misshapen(tmp_path / "one", reader, keys=("A-LINKS", "G-ONE"))
    assert support.lines_naming(support.lines_of(control), "A-LINKS")
    assert support.lines_naming(support.lines_of(control), "G-ONE") == []


@_STRICT
def test_the_requirements_reader_names_every_misshapen_need_of_an_export(tmp_path: Path) -> None:
    """The requirements reader names every misshapen need of the requirement export in one error.

    The requirement export holds five needs of the configured type. One lacks a
    text field the reader reads. One declares an id other than its key. One has a
    parent-link field that is a text and not a list. The other two are good.
    Building the reader raises one error. The error has one line for each of the
    three bad needs. Each line holds the key of the need and a word that tells why:
    the name of the missing field, the id that was declared, or the name of the
    link field. No line names a good need. A control export that holds only one of
    the three bad needs, with the two good ones, is refused with an error that
    names that need.

    :verifies: SEG-SREQ-352
    :test-id: SEG-TS-390
    """
    reader = support.family("requirements")
    error, _ = support.refusal_of_misshapen(tmp_path / "several", reader)
    support.check_misshapen_report(error, reader.link_field, reader.text_field)

    control, _ = support.refusal_of_misshapen(tmp_path / "one", reader, keys=("M-RENAMED", "G-ONE"))
    assert support.lines_naming(support.lines_of(control), "M-RENAMED")
    assert support.lines_naming(support.lines_of(control), "G-ONE") == []


@pytest.mark.parametrize("name", support.OUTCOME_FAMILIES)
@_STRICT
def test_the_outcome_extractor_names_every_misshapen_need_of_an_export(
    tmp_path: Path, name: str
) -> None:
    """The outcome extractor names every misshapen need of an export in one error.

    An export of the outcome extractor holds five needs, in the test-case export
    or in the implementation export, one export at a time, with a good other
    export and a run bundle that is accepted. One need lacks a text field the
    extractor reads. One need declares an id other than its key. One need has a
    link field that is a text and not a list. The other two are good. Building the
    extractor raises one error. The error has one line for each of the three bad
    needs. Each line holds the key of the need and a word that tells why: the name
    of the missing field, the id that was declared, or the name of the link field.
    No line names a good need. A control export that holds only one of the three
    bad needs, with the two good ones, is refused with an error that names that
    need.

    :verifies: SEG-SREQ-353
    :test-id: SEG-TS-391
    """
    reader = support.family(name)
    error, _ = support.refusal_of_misshapen(tmp_path / "several", reader)
    support.check_misshapen_report(error, reader.link_field, reader.text_field)

    control, _ = support.refusal_of_misshapen(tmp_path / "one", reader, keys=("Z-LACKS", "G-TWO"))
    assert support.lines_naming(support.lines_of(control), "Z-LACKS")
    assert support.lines_naming(support.lines_of(control), "G-TWO") == []


def _check_count(tmp_path: Path, name: str) -> None:
    reader = support.family(name)
    error, export = support.refusal_of_misshapen(tmp_path / "several", reader)
    support.assert_header_counts(error, 3, [tmp_path, export])
    assert all(f"'{key}'" not in support.lines_of(error)[0] for key in support.BAD_KEYS)

    control, export = support.refusal_of_misshapen(tmp_path / "one", reader, keys=("A-LINKS",))
    support.assert_header_counts(control, 1, [tmp_path, export])


def _check_order(tmp_path: Path, name: str) -> None:
    reader = support.family(name)
    error, export = support.refusal_of_misshapen(tmp_path, reader)
    named = [
        key for line in support.lines_of(error) for key in support.BAD_KEYS if f"'{key}'" in line
    ]
    assert named == list(support.BAD_KEYS)
    again = support.raises_once(lambda: reader.build(tmp_path, export), reader.error)
    assert str(again) == str(error)


@pytest.mark.parametrize("name", support.CONTENT_FAMILIES)
@_STRICT
def test_the_error_for_misshapen_needs_of_the_content_extractor_starts_with_a_count(
    tmp_path: Path, name: str
) -> None:
    """The error for misshapen needs of an export of the content extractor starts with a count.

    An export of the content extractor, in the stream of the implementations or in
    the stream of the test cases, one at a time, holds three misshapen needs and
    two good ones. The first line of the error holds the number 3 and no other
    number, once the path of the export is cut out of it, and it names no need. Each
    of the lines after it names one bad need, so the error has four lines. With
    only one bad need, the first line holds the number 1 and one line follows.

    :verifies: SEG-SREQ-351
    :test-id: SEG-TS-392
    """
    _check_count(tmp_path, name)


@_STRICT
def test_the_error_for_misshapen_needs_of_the_requirements_reader_starts_with_a_count(
    tmp_path: Path,
) -> None:
    """The error for misshapen needs of the requirement export starts with a count line.

    The requirement export holds three misshapen needs and two good ones. The first
    line of the error holds the number 3 and no other number, once the path of the
    export is cut out of it, and it names no need. Each of the lines after it names
    one bad need, so the error has four lines. With only one bad need, the first
    line holds the number 1 and one line follows.

    :verifies: SEG-SREQ-352
    :test-id: SEG-TS-393
    """
    _check_count(tmp_path, "requirements")


@pytest.mark.parametrize("name", support.OUTCOME_FAMILIES)
@_STRICT
def test_the_error_for_misshapen_needs_of_the_outcome_extractor_starts_with_a_count(
    tmp_path: Path, name: str
) -> None:
    """The error for misshapen needs of an export of the outcome extractor starts with a count.

    The test-case export, or the implementation export, one at a time, holds three
    misshapen needs and two good ones. The first line of the error holds the number
    3 and no other number, once the path of the export is cut out of it, and it
    names no need. Each of the lines after it names one bad need, so the error has
    four lines. With only one bad need, the first line holds the number 1 and one
    line follows.

    :verifies: SEG-SREQ-353
    :test-id: SEG-TS-394
    """
    _check_count(tmp_path, name)


@pytest.mark.parametrize("name", support.CONTENT_FAMILIES)
@_STRICT
def test_misshapen_needs_of_the_content_extractor_are_listed_in_export_order(
    tmp_path: Path, name: str
) -> None:
    """The misshapen needs of an export of the content extractor are listed in export order.

    An export of the content extractor, in the stream of the implementations or in
    the stream of the test cases, one at a time, holds three misshapen needs and
    two good ones. The keys of the bad needs are not in alphabetical order in the
    export. The lines of the error name the bad needs in the order of the export.
    Building the extractor a second time over the same export gives an error with
    the same text.

    :verifies: SEG-SREQ-351
    :test-id: SEG-TS-395
    """
    _check_order(tmp_path, name)


@_STRICT
def test_misshapen_needs_of_the_requirements_reader_are_listed_in_export_order(
    tmp_path: Path,
) -> None:
    """The misshapen needs of the requirement export are listed in the order of the export.

    The requirement export holds three misshapen needs and two good ones. The keys
    of the bad needs are not in alphabetical order in the export. The lines of the
    error name the bad needs in the order of the export. Building the reader a
    second time over the same export gives an error with the same text.

    :verifies: SEG-SREQ-352
    :test-id: SEG-TS-396
    """
    _check_order(tmp_path, "requirements")


@pytest.mark.parametrize("name", support.OUTCOME_FAMILIES)
@_STRICT
def test_misshapen_needs_of_the_outcome_extractor_are_listed_in_export_order(
    tmp_path: Path, name: str
) -> None:
    """The misshapen needs of an export of the outcome extractor are listed in export order.

    The test-case export, or the implementation export, one at a time, holds three
    misshapen needs and two good ones. The keys of the bad needs are not in
    alphabetical order in the export. The lines of the error name the bad needs in
    the order of the export. Building the extractor a second time over the same
    export gives an error with the same text.

    :verifies: SEG-SREQ-353
    :test-id: SEG-TS-397
    """
    _check_order(tmp_path, name)


@_STRICT
def test_case_sync_reports_every_misshapen_need_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case sync prints one refusal that names every misshapen need and writes nothing.

    The implementation export of the configured producer holds three misshapen
    needs and two good ones. Case sync over an initialized case exits with status
    2. Its output names each of the three bad needs with a line of its own, and
    names no good need. The files of the case are the same after the command as
    before it. With the export mended, the same command exits with status 0.

    :verifies: SEG-SREQ-351
    :test-id: SEG-TS-398
    """
    from affirmatrix import case
    from affirmatrix.cli import main

    world = support.World(tmp_path)
    reader = support.family("content implementations")
    needs = support.misshapen(reader.good, reader.link_field, reader.text_field)
    broken = support.keyed_export(tmp_path, needs, "broken")
    world.implementation_export = broken
    cfg = world.write()
    root = tmp_path / "case"
    case.AffirmationStore(root=root).initialize()
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    capsys.readouterr()
    status = main(["case", "sync", "--case", str(root), "--config", str(cfg)])
    out = capsys.readouterr()
    lines = (out.out + out.err).splitlines()
    assert status == 2
    for key in support.BAD_KEYS:
        assert len(support.lines_naming(lines, key)) == 1, key
    for key in support.GOOD_KEYS:
        assert support.lines_naming(lines, key) == [], key
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before

    world.implementation_export = world.root / "impls.json"
    assert main(["case", "sync", "--case", str(root), "--config", str(world.write())]) == 0
