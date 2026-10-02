"""Verification suite for the configuration of readers that differ from the first fixture.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Each
test writes a configuration file to a temporary directory and loads it. The
names of the keys and of the loaded attributes are held in one module,
``capture_support``. A relative path in a file is resolved against the
directory of that file, and the Doxygen prefix is text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import config

from . import capture_support as support


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sub" / "affirmatrix.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


_REQUIREMENTS = (
    "producer:\n"
    "  repository: suite\n"
    "  requirements:\n"
    "    export: needs/requirements.json\n"
    "    types: [req]\n"
)
_SPECIFICATIONS = "  specifications:\n    export: needs/test-cases.json\n    doxygen: xml/tests\n"
_IMPLEMENTATIONS = (
    "  implementations:\n    export: needs/implementations.json\n    doxygen: xml/impl\n"
)


def test_the_parent_field_is_carried(tmp_path: Path) -> None:
    """The name of the parent-link field is carried.

    A file whose requirements block names the parent field trace and the source
    directory reqs gives requirements inputs that carry the name trace.

    :verifies: SEG-SREQ-284
    :test-id: SEG-TS-174
    """
    path = _write(tmp_path, _REQUIREMENTS + f"    {support.KEY_PARENT}: trace\n    source: reqs\n")
    requirements = support.loaded(path).requirements
    assert support.attribute(requirements, support.ATTR_PARENT) == "trace"


def test_the_types_of_test_cases_and_implementations_are_carried(tmp_path: Path) -> None:
    """The need types of the test-case and implementation exports are carried.

    A file names the types test_case and test_manual in its specifications block.
    It names the type impl in its implementations block. The loaded inputs carry
    each of those sets of types and no other type.

    :verifies: SEG-SREQ-285
    :test-id: SEG-TS-175
    """
    text = (
        "producer:\n"
        "  repository: suite\n"
        + _SPECIFICATIONS
        + f"    {support.KEY_TYPES}: [test_case, test_manual]\n"
        + _IMPLEMENTATIONS
        + f"    {support.KEY_TYPES}: [impl]\n"
    )
    producer = support.loaded(_write(tmp_path, text))
    specifications = support.attribute(producer.specifications, support.ATTR_TYPES)
    implementations = support.attribute(producer.implementations, support.ATTR_TYPES)
    assert set(specifications) == {"test_case", "test_manual"}
    assert set(implementations) == {"impl"}


def test_a_reader_may_name_its_own_repository(tmp_path: Path) -> None:
    """A reader's own repository name is carried.

    A file names the default repository suite, and the requirements block names
    the repository docs. The requirements inputs carry docs. The specifications
    block names none, and its inputs carry no repository of their own.

    :verifies: SEG-SREQ-286
    :test-id: SEG-TS-176
    """
    text = (
        _REQUIREMENTS + f"    {support.KEY_REPOSITORY}: docs\n    source: reqs\n" + _SPECIFICATIONS
    )
    producer = support.loaded(_write(tmp_path, text))
    assert support.attribute(producer.requirements, support.ATTR_REPOSITORY) == "docs"
    assert support.attribute(producer.specifications, support.ATTR_REPOSITORY) in (None, "")
    assert producer.repository == "suite"


def test_the_doxygen_prefix_is_carried_for_each_output(tmp_path: Path) -> None:
    """The Doxygen path prefix is carried for each Doxygen output, as written.

    A file gives the prefix tree-root/ to the test output and the prefix
    lib-src/ to the implementation output. The loaded inputs carry each prefix as
    the text written, and the loader does not join either with the directory of
    the file.

    :verifies: SEG-SREQ-287
    :test-id: SEG-TS-177
    """
    text = (
        "producer:\n"
        "  repository: suite\n"
        + _SPECIFICATIONS
        + f"    {support.KEY_PREFIX}: tree-root/\n"
        + _IMPLEMENTATIONS
        + f"    {support.KEY_PREFIX}: lib-src/\n"
    )
    producer = support.loaded(_write(tmp_path, text))
    assert str(support.attribute(producer.specifications, support.ATTR_PREFIX)) == "tree-root/"
    assert str(support.attribute(producer.implementations, support.ATTR_PREFIX)) == "lib-src/"


def test_the_source_map_is_carried(tmp_path: Path) -> None:
    """The map from need docnames to source files is carried.

    A file in a subdirectory gives a source map of two docnames, docs/alpha and
    docs/beta, to the files reqs/alpha.sdoc and reqs/beta.sdoc. The loaded inputs
    carry the same two docnames. Each value is the subdirectory joined with the
    path written, as every other relative path is.

    :verifies: SEG-SREQ-288
    :test-id: SEG-TS-178
    """
    text = (
        _REQUIREMENTS
        + f"    {support.KEY_MAP}:\n"
        + "      docs/alpha: reqs/alpha.sdoc\n"
        + "      docs/beta: reqs/beta.sdoc\n"
    )
    path = _write(tmp_path, text)
    carried = support.attribute(support.loaded(path).requirements, support.ATTR_MAP)
    base = path.parent
    assert {key: Path(value) for key, value in carried.items()} == {
        "docs/alpha": base / "reqs/alpha.sdoc",
        "docs/beta": base / "reqs/beta.sdoc",
    }


def test_a_source_directory_and_a_source_map_exclude_each_other(tmp_path: Path) -> None:
    """A source directory and a source map exclude each other.

    Loading a file whose requirements block names a source directory and a source
    map raises the configuration error. So does loading a file that names neither.
    A file that names the source directory only loads, and so does a file that
    names the source map only.

    :verifies: SEG-SREQ-289
    :test-id: SEG-TS-179
    """
    directory = "    source: reqs\n"
    mapped = f"    {support.KEY_MAP}:\n      docs/alpha: reqs/alpha.sdoc\n"
    for name, extra, loads in (
        ("both", directory + mapped, False),
        ("neither", "", False),
        ("directory", directory, True),
        ("map", mapped, True),
    ):
        path = tmp_path / name / "affirmatrix.yaml"
        path.parent.mkdir()
        path.write_text(_REQUIREMENTS + extra, encoding="utf-8")
        if loads:
            assert config.load(path).producer is not None, name
        else:
            with pytest.raises(config.ConfigError):
                config.load(path)
