"""Shared helpers for the specifications of an error that names every bad item at once.

Not a specification. The modules that realize specifications import these
helpers. A reader of an export that holds several misshapen needs, the outcome
extractor over a run artifact that holds several unmapped results, and the
content extractor over a repository path that is not a directory must each give
one error. The helpers build small synthetic exports, run bundles and
repositories in a temporary directory and read what an error says.

How one error is read: the message is split in lines. The first line is the
header. Every later line is one item. A specification never depends on the
words of a reason, only on a word that must be in it (the name of the missing
field, the declared identifier, the name of the link field).

Every expected value in a test is computed from the fixture the test builds,
never by calling the code under test.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config
from affirmatrix.sources import SourceError

from . import capture_support as support
from . import path_root_support as roots

# --- reading an error --------------------------------------------------------


def lines_of(error: BaseException) -> list[str]:
    """The lines of the message of ``error``, without blank lines."""
    return [line for line in str(error).splitlines() if line.strip()]


def lines_naming(lines: Sequence[str], name: str) -> list[str]:
    """The lines that hold ``name`` between quotes, so a longer name never matches."""
    return [line for line in lines if f"'{name}'" in line]


def numbers_in(line: str, hidden: Sequence[object] = ()) -> list[int]:
    """The whole numbers in ``line`` once each text of ``hidden`` is cut out.

    A path of a temporary directory holds digits. A test hides each path it
    gave, so only the numbers the message itself adds are left.
    """
    text = line
    for item in sorted(map(str, hidden), key=len, reverse=True):
        text = text.replace(item, "")
    return [int(number) for number in re.findall(r"\b\d+\b", text)]


def raises_once(build: Callable[[], object], error: type[Exception]) -> Exception:
    """Run ``build`` and return the one error it raises; fail when it raises none."""
    with pytest.raises(error) as caught:
        build()
    return caught.value


# --- needs and exports -------------------------------------------------------


def keyed_export(tmp_path: Path, needs: Mapping[str, Mapping[str, Any]], name: str) -> Path:
    """An export that holds ``needs`` under the keys given, whatever each need's own id says."""
    document = {
        "current_version": "v0",
        "versions": {"v0": {"needs": {key: dict(need) for key, need in needs.items()}}},
    }
    path = tmp_path / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def requirement_need(ident: str, **more: Any) -> dict[str, Any]:
    """A requirement need of the type req, with no parent unless ``more`` gives one."""
    need: dict[str, Any] = {
        "id": ident,
        "type": "req",
        "title": ident.lower(),
        "content": f"The system shall do {ident}.",
        "docname": "reqs/alpha",
        "doctype": ".rst",
        "refines": [],
    }
    need.update(more)
    return need


def without_field(need: Mapping[str, Any], name: str) -> dict[str, Any]:
    """A copy of ``need`` that lacks the field ``name``."""
    return {key: value for key, value in need.items() if key != name}


def misshapen(
    good: Callable[[str], dict[str, Any]], link_field: str, text_field: str
) -> dict[str, dict[str, Any]]:
    """Three bad needs among two good ones, in an order that is not alphabetical.

    The needs are keyed Z-LACKS (no ``text_field``), M-RENAMED (an id other than
    its key) and A-LINKS (a ``link_field`` that is a text, not a list). The
    good needs are G-ONE and G-TWO. The order of the export is Z, G-ONE, M, A,
    G-TWO.
    """
    return {
        "Z-LACKS": without_field(good("Z-LACKS"), text_field),
        "G-ONE": good("G-ONE"),
        "M-RENAMED": good("OTHER-ID"),
        "A-LINKS": {**good("A-LINKS"), link_field: "SOME-TARGET"},
        "G-TWO": good("G-TWO"),
    }


#: The keys of the bad needs of :func:`misshapen`, in the order of the export.
BAD_KEYS = ("Z-LACKS", "M-RENAMED", "A-LINKS")
GOOD_KEYS = ("G-ONE", "G-TWO")


def check_misshapen_report(error: BaseException, link_field: str, text_field: str) -> None:
    """Assert that ``error`` names the three bad needs of :func:`misshapen`, each with its reason.

    A need's line holds its key and the word that tells its reason. No line
    names a good need.
    """
    lines = lines_of(error)
    reason_word = {"Z-LACKS": text_field, "M-RENAMED": "OTHER-ID", "A-LINKS": link_field}
    for key in BAD_KEYS:
        named = lines_naming(lines, key)
        assert len(named) == 1, (key, str(error))
        assert reason_word[key] in named[0], (key, named[0])
    for key in GOOD_KEYS:
        assert lines_naming(lines, key) == [], key
    assert "OTHER-ID" not in "".join(lines_naming(lines, "A-LINKS"))


def assert_header_counts(error: BaseException, items: int, hidden: Sequence[object]) -> None:
    """Assert that the first line is a header with the number ``items``, then one line per item."""
    lines = lines_of(error)
    assert numbers_in(lines[0], hidden) == [items], lines[0]
    assert len(lines) == 1 + items, str(error)


# --- the content extractor over exports --------------------------------------


def implementation_export_need(ident: str) -> dict[str, Any]:
    """An implementation need with a title and a link list."""
    return support.implementation_need(ident, f"SYM_{ident.replace('-', '_')}")


def test_case_export_need(ident: str) -> dict[str, Any]:
    """A test-case need with a test function and a link list."""
    return support.case_need(ident, f"test_{ident.replace('-', '_').lower()}")


def empty_tree(directory: Path) -> Path:
    """A Doxygen output with no member, enough for an extractor that reads no source."""
    return roots.doxygen_tree(directory, [])


def content_extractor(
    tmp_path: Path, *, implementations: Path | None = None, specifications: Path | None = None
):
    """The content extractor over the exports given, with Doxygen outputs that hold no member."""
    from affirmatrix.sources.content import CSourceExtractor

    tree = empty_tree(tmp_path / "xml")
    return CSourceExtractor(
        tmp_path,
        repository="sample",
        implementations=(
            None
            if implementations is None
            else config.ImplementationInputs(export=implementations, doxygen=tree)
        ),
        specifications=(
            None
            if specifications is None
            else config.SpecificationInputs(export=specifications, doxygen=tree)
        ),
    )


@dataclass(frozen=True)
class Family:
    """One reader of one export: how to make a good need and how to build the reader over an export.

    ``link_field`` is the field that must be a list of identifiers and
    ``text_field`` a text field the reader reads besides the identifier.
    ``error`` is the type of the error the reader raises.
    """

    name: str
    good: Callable[[str], dict[str, Any]]
    link_field: str
    text_field: str
    error: type[Exception]
    build: Callable[[Path, Path], object]


def _content_implementations(tmp_path: Path, export: Path) -> object:
    return content_extractor(tmp_path, implementations=export)


def _content_specifications(tmp_path: Path, export: Path) -> object:
    return content_extractor(tmp_path, specifications=export)


def _requirements(tmp_path: Path, export: Path) -> object:
    from affirmatrix.sources.reqs import RequirementsReader

    return RequirementsReader(
        export=export, types=frozenset({"req"}), repository="docs", source_directory=Path("reqs")
    )


def _outcome_good_case(ident: str) -> dict[str, Any]:
    from . import need_types_support as nt

    return nt.case_need(ident, SUITE, "test_put_get")


def _outcome_good_implementation(ident: str) -> dict[str, Any]:
    from . import need_types_support as nt

    return nt.implementation_need(ident)


def _outcome_over_specifications(tmp_path: Path, export: Path) -> object:
    from . import need_types_support as nt

    impls = support.export_of(tmp_path, [_outcome_good_implementation("I-1")], "healthy-impls")
    bundle = nt.write_bundle(
        tmp_path / "bundle", [(nt.SCENARIO, PLATFORM, [(result_of("test_put_get"), "passed")])]
    )
    return nt.outcome_extractor(bundle, export, impls)


def _outcome_over_implementations(tmp_path: Path, export: Path) -> object:
    from . import need_types_support as nt

    cases = support.export_of(tmp_path, [_outcome_good_case("TC-1")], "healthy-cases")
    bundle = nt.write_bundle(
        tmp_path / "bundle", [(nt.SCENARIO, PLATFORM, [(result_of("test_put_get"), "passed")])]
    )
    return nt.outcome_extractor(bundle, cases, export)


def _families() -> dict[str, Family]:
    from affirmatrix.sources.content import ExtractorError
    from affirmatrix.sources.outcomes import OutcomeError
    from affirmatrix.sources.reqs import ReaderError

    return {
        "content implementations": Family(
            "content implementations",
            implementation_export_need,
            "satisfies",
            "title",
            ExtractorError,
            _content_implementations,
        ),
        "content test cases": Family(
            "content test cases",
            test_case_export_need,
            "verifies",
            "test_function",
            ExtractorError,
            _content_specifications,
        ),
        "requirements": Family(
            "requirements",
            requirement_need,
            "refines",
            "content",
            ReaderError,
            _requirements,
        ),
        "outcome test cases": Family(
            "outcome test cases",
            _outcome_good_case,
            "verifies",
            "test_function",
            OutcomeError,
            _outcome_over_specifications,
        ),
        "outcome implementations": Family(
            "outcome implementations",
            _outcome_good_implementation,
            "satisfies",
            "id",
            OutcomeError,
            _outcome_over_implementations,
        ),
    }


def family(name: str) -> Family:
    """The reader family ``name``. Built on use, so a missing reader fails one test only."""
    return _families()[name]


#: The names of the readers of the claims, by claim.
CONTENT_FAMILIES = ("content implementations", "content test cases")
REQUIREMENT_FAMILIES = ("requirements",)
OUTCOME_FAMILIES = ("outcome test cases", "outcome implementations")


def refusal_of_misshapen(tmp_path: Path, reader: Family, keys: Sequence[str] | None = None):
    """The error the reader raises over an export of the misshapen needs, and the export path.

    With ``keys``, the export holds only those of the needs of :func:`misshapen`,
    in the order of the export.
    """
    needs = misshapen(reader.good, reader.link_field, reader.text_field)
    if keys is not None:
        needs = {key: needs[key] for key in needs if key in keys}
    export = keyed_export(tmp_path, needs, "export")
    return raises_once(lambda: reader.build(tmp_path, export), reader.error), export


# --- the outcome extractor over a run artifact ---------------------------------

SUITE = "queue"
PLATFORM = "native_sim"
SECOND_PLATFORM = "qemu_x86"


def result_of(function: str) -> str:
    """The identifier a run artifact gives the test ``function`` of the suite of the fixtures."""
    from . import need_types_support as nt

    return nt.result_identifier(nt.SCENARIO, SUITE, function)


# --- repositories for the path specifications --------------------------------

HEADER = (
    "/** @brief One. */\n"
    "#define M_ONE 1\n"
    "\n"
    "/** @brief Two. */\n"
    "#define M_TWO 2\n"
    "\n"
    "/** @brief Three. */\n"
    "#define M_THREE 3\n"
)
#: The header file in the library repository and each macro with its line.
HEADER_PATH = "include/macros.h"
MACROS = (("M_ONE", 2), ("M_TWO", 5), ("M_THREE", 8))

TEST_FILE = (
    "/**\n * @brief {tag}\n *\n * @testid{{{ident}}}\n */\n"
    "ZTEST(suite, test_{tag})\n{{\n\tzassert_true(true);\n}}\n\n"
)
TEST_PATH = "tests/cases.c"
TEST_TAGS = ("one", "two", "three")


def _test_source() -> tuple[str, list[tuple[str, int, int]]]:
    """The test source and, for each test, its name and the first and last line of its body."""
    text = ""
    spans = []
    line = 1
    for tag in TEST_TAGS:
        block = TEST_FILE.format(tag=tag, ident=f"T-{tag.upper()}")
        first = line + 5
        spans.append((f"test_{tag}", first, first + 3))
        text += block
        line += block.count("\n")
    return text, spans


class World:
    """Three repositories (docs, lib, suite), the exports over them and the configuration.

    ``requirements`` is the repository of the requirement document, ``library``
    the one of the implementations and ``suite`` the one of the tests. Each
    holds the plain files its stream reads and no version-control data. The
    stream of each reader holds three needs. ``write`` makes the configuration
    file for the repositories the caller maps; a path given for a name replaces
    the directory made here.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.requirements = tmp_path / "repositories" / "docs"
        self.library = tmp_path / "repositories" / "lib"
        self.suite = tmp_path / "repositories" / "suite"
        (self.requirements / "reqs").mkdir(parents=True)
        roots.write_file(self.library, HEADER_PATH, HEADER)
        source, spans = _test_source()
        roots.write_file(self.suite, TEST_PATH, source)
        needs = [support.implementation_need(f"I-{n}", n) for n, _ in MACROS]
        self.implementation_export = support.export_of(tmp_path, needs, "impls")
        self.implementation_tree = roots.doxygen_tree(
            tmp_path / "impl-xml", [(n, "define", HEADER_PATH, line, line) for n, line in MACROS]
        )
        cases = []
        for tag in TEST_TAGS:
            need = support.case_need(f"T-{tag.upper()}", f"test_{tag}")
            del need["test_module"]
            cases.append(need)
        self.specification_export = support.export_of(tmp_path, cases, "cases")
        self.specification_tree = roots.doxygen_tree(
            tmp_path / "spec-xml", [(n, "function", TEST_PATH, a, b) for n, a, b in spans]
        )
        reqs = [requirement_need(f"R-{n}") for n in ("1", "2", "3")]
        self.requirement_export = keyed_export(tmp_path, {r["id"]: r for r in reqs}, "reqs")

    def write(
        self,
        *,
        paths: Mapping[str, Path] | None = None,
        names: Mapping[str, str] | None = None,
        name: str = "affirmatrix.yaml",
    ) -> Path:
        """The configuration file. ``paths`` maps a repository role to the path configured for it.

        The roles are ``requirements``, ``library`` and ``suite``. ``names``
        maps a role to the configured name of its repository; the default name of
        each role is ``docs``, ``lib`` and ``suite``. Two roles with one name
        share one repository entry, and the path of the later role is used.
        """
        directories = {
            "requirements": self.requirements,
            "library": self.library,
            "suite": self.suite,
            **(paths or {}),
        }
        called = {"requirements": "docs", "library": "lib", "suite": "suite", **(names or {})}
        return support.configuration(
            self.root,
            requirements=support.requirements_block(
                export=str(self.requirement_export),
                source=str(directories["requirements"] / "reqs"),
                **{support.KEY_REPOSITORY: called["requirements"]},
            ),
            specifications=support.specifications_block(
                export=str(self.specification_export),
                doxygen=str(self.specification_tree),
                **{support.KEY_REPOSITORY: called["suite"]},
            ),
            implementations=support.implementations_block(
                export=str(self.implementation_export),
                doxygen=str(self.implementation_tree),
                **{support.KEY_REPOSITORY: called["library"]},
            ),
            repositories={called[role]: path for role, path in directories.items()},
            name=name,
        )


def producer_of(path: Path):
    """The producer a configuration file describes."""
    return support.producer_of(path)


def drained(path: Path) -> SourceError | None:
    """The error that building the producer of a file and taking both streams raises, or None.

    A repository that cannot be used may be refused when the producer is built
    or when its nodes are taken. A specification does not say which, so it
    reads both.
    """
    try:
        producer = support.producer_of(path)
        list(producer.nodes())
        list(producer.edges())
    except SourceError as error:
        return error
    return None


# --- a run artifact with unmapped and ambiguous results --------------------------


def outcome_inputs(tmp_path: Path, suites: Sequence[Any]):
    """The two exports and the run bundle of the fixtures, and the path of the run artifact.

    The test-case export holds TC-A, which the test ``put_get`` of the suite
    maps to, and TC-TWIN-ONE and TC-TWIN-TWO, which share the test ``twin`` of
    the suite, so a result of that test is ambiguous. ``suites`` are the suites
    of the run artifact, as :func:`need_types_support.write_bundle` takes them.
    """
    from . import need_types_support as nt

    cases = [
        nt.case_need("TC-A", SUITE, "test_put_get"),
        nt.case_need("TC-TWIN-ONE", SUITE, "test_twin"),
        nt.case_need("TC-TWIN-TWO", SUITE, "test_twin"),
    ]
    specifications, implementations = nt.exports(tmp_path, cases)
    bundle = nt.write_bundle(tmp_path / "bundle", suites)
    return specifications, implementations, bundle, bundle / "twister.json"


def outcome_refusal(tmp_path: Path, suites: Sequence[Any]):
    """The error the outcome extractor raises over the suites, and the path of the artifact."""
    from affirmatrix.sources.outcomes import OutcomeError

    from . import need_types_support as nt

    specifications, implementations, bundle, artifact = outcome_inputs(tmp_path, suites)
    error = raises_once(
        lambda: nt.outcome_extractor(bundle, specifications, implementations), OutcomeError
    )
    return error, artifact, bundle
