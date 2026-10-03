"""Verification suite for a Doxygen member that records no body.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. Doxygen
writes ``-1`` for the end of a body that it did not record, for example for a
function that is only declared. The tests read the frozen evidence fixture under
``tests/fixtures/toolbox_evidence/``. Each variant of an input is built in the
test, in a temporary directory, by copying a Doxygen tree and editing the
``<location>`` of one member. The extractor is imported inside the helper that
builds it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from affirmatrix import config

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "toolbox_evidence"
IMPLEMENTATION_EXPORT = FIXTURE / "needs" / "api-traceability" / "needs.json"
SPECIFICATION_EXPORT = FIXTURE / "needs" / "test-specification" / "needs.json"
IMPLEMENTATION_XML = FIXTURE / "xml" / "dox-safe-data-api"
SPECIFICATION_XML = FIXTURE / "xml" / "dox-safe-data-testspec"
SOURCES = FIXTURE / "sources"
INIT = "IMPL-safe_data_init"
INIT_SYMBOL = "safe_data_init"
INIT_AND_VERIFY = "TC_SAFE_DATA_INIT_AND_VERIFY"


def _without_body(tmp_path: Path, doxygen: Path, symbol: str, name: str, **attributes: str) -> Path:
    """A copy of the Doxygen tree in which the location of ``symbol`` has the attributes given."""
    copy = tmp_path / name
    shutil.copytree(doxygen, copy)
    found = []
    for path in sorted(copy.glob("*.xml")):
        text = path.read_text(encoding="utf-8")
        for block in re.finditer(r"<memberdef\b.*?</memberdef>", text, re.DOTALL):
            if f"<name>{symbol}</name>" in block.group(0):
                found.append((path, text, block))
    assert len(found) == 1
    path, text, block = found[0]
    tag = re.search(r"<location [^>]*/>", block.group(0))
    assert tag is not None
    new_tag = tag.group(0)
    for key, value in attributes.items():
        new_tag, count = re.subn(rf'(?<=\s){key}="[^"]*"', f'{key}="{value}"', new_tag)
        assert count == 1
    changed = block.group(0).replace(tag.group(0), new_tag)
    path.write_text(text[: block.start()] + changed + text[block.end() :], encoding="utf-8")
    return copy


def _nodes(
    implementations: tuple[Path, Path] | None, specifications: tuple[Path, Path] | None
) -> dict[str, Any]:
    """Construct the extractor over the fixture sources, then drain its node stream."""
    from affirmatrix.sources.content import CSourceExtractor

    extractor = CSourceExtractor(
        SOURCES,
        repository="toolbox",
        implementations=(
            None
            if implementations is None
            else config.ImplementationInputs(export=implementations[0], doxygen=implementations[1])
        ),
        specifications=(
            None
            if specifications is None
            else config.SpecificationInputs(export=specifications[0], doxygen=specifications[1])
        ),
    )
    return {node.local_id: node for node in extractor.nodes()}


def test_a_member_with_no_recorded_body_is_an_error_for_its_node(tmp_path: Path) -> None:
    """A member whose body ends at -1 is an error for its node, and the node is not hashed.

    In a copy of the Doxygen output of the implementations where the location
    of safe_data_init gives the end of the body as -1, extracting raises the
    extractor's error. The message names IMP-safe_data_init, the need whose
    member records no body, and the stream gives no record for it. The same
    holds for a copy where both the start and the end of the body are -1. In a
    copy of the Doxygen output of the test specifications where the location of
    the test function of TC_SAFE_DATA_INIT_AND_VERIFY gives the end of the body
    as -1, extracting raises the error and the message names that need. The
    extraction over the fixture as frozen supplies all 12 Implementation
    records, so the rule does not refuse a member that records a body.

    :verifies: SEG-SREQ-350
    :test-id: SEG-TS-361
    """
    from affirmatrix.sources.content import ExtractorError

    frozen = _nodes((IMPLEMENTATION_EXPORT, IMPLEMENTATION_XML), None)
    assert len([n for n in frozen.values() if n.kind == "Implementation"]) == 12
    variants = {
        "end": {"bodyend": "-1"},
        "start and end": {"bodystart": "-1", "bodyend": "-1"},
    }
    for label, attributes in variants.items():
        xml = _without_body(
            tmp_path, IMPLEMENTATION_XML, INIT_SYMBOL, label.replace(" ", "-"), **attributes
        )
        with pytest.raises(ExtractorError, match=re.escape(INIT)):
            _nodes((IMPLEMENTATION_EXPORT, xml), None)

    test_symbol = _test_symbol()
    xml = _without_body(tmp_path, SPECIFICATION_XML, test_symbol, "test-body", bodyend="-1")
    with pytest.raises(ExtractorError, match=re.escape(INIT_AND_VERIFY)):
        _nodes(None, (SPECIFICATION_EXPORT, xml))


def _test_symbol() -> str:
    """The function that the need TC_SAFE_DATA_INIT_AND_VERIFY names, read from its export."""
    import json

    document = json.loads(SPECIFICATION_EXPORT.read_text(encoding="utf-8"))
    (version,) = document["versions"].values()
    return version["needs"][INIT_AND_VERIFY]["test_function"]
