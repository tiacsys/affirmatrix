"""Verification suite for the report of every node the content extractor cannot supply.

The function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. It
reads the synthetic sources under ``tests/fixtures/capture_shape/``. Its
needs are built in the test, in a temporary directory. The extractor is reached
through the configuration file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from affirmatrix.sources import SourceError

from . import capture_support as support


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-282: extraction stops at the first bad node")
def test_every_node_that_cannot_be_supplied_is_reported_in_one_error(tmp_path: Path) -> None:
    """Every node that cannot be supplied is reported in one error, each with its reason.

    The test stream holds one good need, one need whose symbol no Doxygen member
    carries, and one whose test has no documentation comment. The implementation
    stream holds one good need and one whose macro has a blank line between its
    comment and its define line. Taking the records raises one source error. Its
    message names the three bad needs, each with its symbol and a reason, and the
    two reasons of the test stream differ. It does not name the two good needs.

    :verifies: SEG-SREQ-282
    :test-id: SEG-TS-171
    """
    tests = support.export_of(
        tmp_path,
        [
            support.case_need("S-good", "test_direct"),
            support.case_need("S-absent", "test_absent"),
            support.case_need("S-nocomment", "test_nodoc_code"),
        ],
        "tests",
    )
    macros = support.export_of(
        tmp_path,
        [
            support.implementation_need("I-good", "IMP_DIRECT"),
            support.implementation_need("I-blank", "IMP_BLANK"),
        ],
        "macros",
    )
    path = support.configuration(
        tmp_path,
        specifications=support.specifications_block("spans", export=str(tests)),
        implementations=support.implementations_block(
            "spans-impl", export=str(macros), **{support.KEY_REPOSITORY: "lib"}
        ),
        default_repository="suite",
    )
    with pytest.raises(SourceError) as caught:
        support.records(path)
    message = str(caught.value)
    bad = {"S-absent": "test_absent", "S-nocomment": "test_nodoc_code", "I-blank": "IMP_BLANK"}
    reasons = {}
    for ident, symbol in bad.items():
        (line,) = [text for text in message.splitlines() if ident in text]
        assert symbol in line
        reasons[ident] = re.sub(r"\W+", " ", line.replace(ident, "").replace(symbol, "")).strip()
        assert reasons[ident]
    assert reasons["S-absent"] != reasons["S-nocomment"]
    assert "S-good" not in message and "I-good" not in message
