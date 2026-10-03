"""Shared helpers for the specifications of the list of need identifiers.

Not a specification. The modules that realize specifications import these
helpers. The list of need identifiers narrows the implementation needs that the
content extractor and the outcome extractor read. The helpers build, in a
temporary directory, an implementation export of four needs over four macros of
one header, a Doxygen output that locates the macros, a repository, and the
configuration file. A test changes the keys of the implementations block and
reads the records that the extractor supplies.

The four needs differ in the two things that the filters look at. I-ONE, I-TWO
and I-THREE have the type impl and I-OTHER has the type other. Each needs a
different macro, so a record that is supplied can be told from one that is not.

Every expected value in a test is computed from the fixture the test builds,
never by calling the code under test.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import capture_support as support
from . import path_root_support as roots

HEADER_PATH = "include/macros.h"
HEADER = (
    "/** @brief One. */\n"
    "#define M_ONE 1\n"
    "\n"
    "/** @brief Two. */\n"
    "#define M_TWO 2\n"
    "\n"
    "/** @brief Three. */\n"
    "#define M_THREE 3\n"
    "\n"
    "/** @brief Other. */\n"
    "#define M_OTHER 4\n"
)
#: The need, its type, its macro and the line of the macro.
NEEDS = (
    ("I-ONE", "impl", "M_ONE", 2),
    ("I-TWO", "impl", "M_TWO", 5),
    ("I-THREE", "impl", "M_THREE", 8),
    ("I-OTHER", "other", "M_OTHER", 11),
)
ALL = tuple(name for name, *_ in NEEDS)
IMPL = ("I-ONE", "I-TWO", "I-THREE")


def implementation_needs() -> list[dict[str, Any]]:
    """The four needs of the export, each of its own type and macro."""
    return [
        support.implementation_need(name, macro, type=kind, satisfies=[f"R-{name}"])
        for name, kind, macro, _ in NEEDS
    ]


class Library:
    """The repository, the export and the Doxygen output of the four needs.

    ``extra`` needs are added to the export after the four. Each of them may
    be broken in a way that the macros of the tree cannot serve.
    """

    def __init__(self, tmp_path: Path, extra: Sequence[dict[str, Any]] = ()) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path
        self.repository = tmp_path / "library"
        roots.write_file(self.repository, HEADER_PATH, HEADER)
        needs = [*implementation_needs(), *extra]
        self.export = support.export_of(tmp_path, needs, "impls")
        self.tree = roots.doxygen_tree(
            tmp_path / "xml", [(m, "define", HEADER_PATH, line, line) for _, _, m, line in NEEDS]
        )

    def configuration(self, **keys: Any) -> Path:
        """A configuration whose implementation stream reads the library, with ``keys`` added."""
        block = support.implementations_block(
            export=str(self.export), doxygen=str(self.tree), **{support.KEY_REPOSITORY: "lib"}
        )
        block.update(keys)
        return support.configuration(
            self.root,
            implementations=block,
            repositories={"lib": self.repository, "suite": self.repository},
        )

    def supplied(self, **keys: Any) -> set[str]:
        """The identifiers of the records the content extractor supplies with ``keys``."""
        nodes, _ = support.records(self.configuration(**keys))
        return set(nodes)

    def implemented(self, **keys: Any) -> set[str]:
        """The needs that have an Implements edge, as the extractor supplies them with ``keys``."""
        _, edges = support.records(self.configuration(**keys))
        return {edge.from_id for edge in edges if edge.kind == "Implements"}


# --- the outcome extractor ---------------------------------------------------------------


class Witnessing:
    """One requirement, two test cases that verify it, and implementation needs that satisfy it.

    Each test case has one passed result in a run bundle. The implementation
    needs are IMPL-A and IMPL-B of the type impl and IMPL-C of the type design,
    and each satisfies the requirement, so without a filter an outcome witnesses
    all three. ``extra`` needs, by the key they have in the export, are added to the
    implementation export. The outcome extractor is built from the inputs that the
    loader gives for a configuration, with ``keys`` added to the implementations block.
    """

    SUITE = "queue"
    PLATFORM = "native_sim"
    FUNCTIONS = ("test_put_get", "test_isr")

    def __init__(self, tmp_path: Path, extra: Mapping[str, dict[str, Any]] | None = None) -> None:
        from . import every_need_support as errors
        from . import need_types_support as nt

        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path
        cases = [
            nt.case_need(f"TC-{n}", self.SUITE, function)
            for n, function in zip("AB", self.FUNCTIONS, strict=True)
        ]
        self.specifications = support.export_of(tmp_path, cases, "cases")
        needs = {
            n["id"]: n
            for n in (
                nt.implementation_need("IMPL-A"),
                nt.implementation_need("IMPL-B"),
                nt.implementation_need("IMPL-C", type="design"),
            )
        }
        self.implementations = errors.keyed_export(tmp_path, {**needs, **(extra or {})}, "impls")
        results = [
            (nt.result_identifier(nt.SCENARIO, self.SUITE, function), "passed")
            for function in self.FUNCTIONS
        ]
        self.bundle = nt.write_bundle(tmp_path / "bundle", [(nt.SCENARIO, self.PLATFORM, results)])

    def extractor(self, **keys: Any):
        """The outcome extractor over the exports, with ``keys`` in the implementations block."""
        from affirmatrix.sources.outcomes import TwisterOutcomeExtractor

        from . import need_types_support as nt

        unused = str(self.root / "no-doxygen")
        path = support.configuration(
            self.root,
            specifications=support.specifications_block(
                export=str(self.specifications), doxygen=unused
            ),
            implementations=support.implementations_block(
                export=str(self.implementations), doxygen=unused, **keys
            ),
        )
        inputs = support.loaded(path)
        return TwisterOutcomeExtractor(
            [self.bundle],
            checkout=nt.CHECKOUT,
            specifications=inputs.specifications,
            implementations=inputs.implementations,
        )

    def witnessed(self, **keys: Any) -> dict[str, list[str]]:
        """For each outcome, the sorted implementation needs it has a Witnesses edge to."""
        extractor = self.extractor(**keys)
        result: dict[str, list[str]] = {}
        for edge in extractor.edges():
            if edge.kind == "Witnesses":
                result.setdefault(edge.from_id, []).append(edge.to_id)
        return {outcome: sorted(targets) for outcome, targets in result.items()}
