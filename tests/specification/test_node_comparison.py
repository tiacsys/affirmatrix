"""Verification suite for the per-hash comparison of one node.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
suspect detector compares the node record that the case holds with the node
record of the current stream, for each named content hash. The tests call the
library only. They build the two node records in memory, so no command line,
no case and no repository is part of the claim. The expected status is the one
that the digests in the two records give.

The status values are those of ``affirmatrix.drift.HashStatus``, the same four
that the comparison of an edge uses. The name of the function that compares
the hashes of one node is in ``node_show_support``.
"""

from __future__ import annotations

import pytest

from affirmatrix.drift import HashStatus
from affirmatrix.records import NodeRecord

from . import node_show_support as support


def _reason(claim: str) -> str:
    return f"{claim}: the suspect detector gives no comparison of the hashes of one node"


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_a_hash_with_the_same_digest_on_both_sides_matches() -> None:
    """The suspect detector reports a hash as matching when both digests are equal.

    The case holds a requirement record whose contentHash covers one text. The
    current stream holds a record of the same node whose contentHash covers the
    same text, but with an anchor that names another path. The comparison has one
    item, for contentHash. Its status is matching. It carries both anchors.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-227
    """
    recorded = support.node("Requirement", "REQ-1", contentHash="the same text")
    moved = support.anchor("the same text", path="moved/REQ-1.txt")
    assert moved.path != recorded.content_anchors["contentHash"].path
    current = NodeRecord(
        local_id="REQ-1", kind="Requirement", content_anchors={"contentHash": moved}
    )
    items = support.compare_nodes(recorded, current)
    assert set(items) == {"contentHash"}
    assert items["contentHash"].status == HashStatus.MATCHING
    assert items["contentHash"].recorded == recorded.content_anchors["contentHash"]
    assert items["contentHash"].current == moved


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_a_hash_with_another_digest_on_each_side_differs() -> None:
    """The suspect detector reports a hash as differing when the two digests are not equal.

    The case holds a requirement record whose contentHash covers one text. The
    current stream holds a record of the same node whose contentHash covers
    another text. The comparison has one item, for contentHash. Its status is
    differing. It carries both anchors, so the two digests can be read.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-228
    """
    recorded = support.node("Requirement", "REQ-1", contentHash="the text that was recorded")
    current = support.node("Requirement", "REQ-1", contentHash="the text that is current")
    items = support.compare_nodes(recorded, current)
    assert set(items) == {"contentHash"}
    assert items["contentHash"].status == HashStatus.DIFFERING
    assert items["contentHash"].recorded == recorded.content_anchors["contentHash"]
    assert items["contentHash"].current == current.content_anchors["contentHash"]


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_a_hash_that_only_the_case_holds_is_recorded_only() -> None:
    """The suspect detector reports a hash that only the case's record carries as recorded only.

    The case holds a test specification record with the hashes specHash and
    implHash. The current stream holds a record of the same node with specHash
    alone, with the same digest. The comparison has two items. specHash is
    matching. implHash is recorded only, with the recorded anchor and no
    current anchor.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-229
    """
    recorded = support.node("TestSpecification", "TS-1", specHash="spec", implHash="impl")
    current = support.node("TestSpecification", "TS-1", specHash="spec")
    items = support.compare_nodes(recorded, current)
    assert set(items) == {"specHash", "implHash"}
    assert items["specHash"].status == HashStatus.MATCHING
    assert items["implHash"].status == HashStatus.RECORDED_ONLY
    assert items["implHash"].recorded == recorded.content_anchors["implHash"]
    assert items["implHash"].current is None


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_a_hash_that_only_the_current_stream_carries_is_current_only() -> None:
    """The suspect detector reports a hash that only the current record carries as current only.

    The case holds a test specification record with specHash alone. The current
    stream holds a record of the same node with specHash, with the same digest,
    and implHash. The comparison has two items. specHash is matching. implHash
    is current only, with the current anchor and no recorded anchor.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-230
    """
    recorded = support.node("TestSpecification", "TS-1", specHash="spec")
    current = support.node("TestSpecification", "TS-1", specHash="spec", implHash="impl")
    items = support.compare_nodes(recorded, current)
    assert set(items) == {"specHash", "implHash"}
    assert items["specHash"].status == HashStatus.MATCHING
    assert items["implHash"].status == HashStatus.CURRENT_ONLY
    assert items["implHash"].recorded is None
    assert items["implHash"].current == current.content_anchors["implHash"]


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_each_hash_name_of_a_node_gets_its_own_result() -> None:
    """The suspect detector gives one result for each hash name, each judged by itself.

    The case holds an implementation record with the hashes apiHash and
    bodyHash. In the current record apiHash covers the same text and bodyHash
    covers another text. The comparison has exactly two items. apiHash is matching
    and bodyHash is differing. The change of one hash does not change the
    status of the other.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-231
    """
    recorded = support.node("Implementation", "IMP-1", apiHash="api", bodyHash="body")
    current = support.node("Implementation", "IMP-1", apiHash="api", bodyHash="another body")
    items = support.compare_nodes(recorded, current)
    assert set(items) == {"apiHash", "bodyHash"}
    assert items["apiHash"].status == HashStatus.MATCHING
    assert items["bodyHash"].status == HashStatus.DIFFERING


@pytest.mark.xfail(strict=True, reason=_reason("SEG-SREQ-312"))
def test_a_node_that_only_one_side_holds_has_every_hash_on_one_side_only() -> None:
    """The suspect detector reports every hash of a node that only one side holds as one-sided.

    The case holds a test specification record with specHash and implHash, and
    the current stream holds no record of the node. The comparison has two
    items, and both are recorded only. In the other direction, the current
    stream holds the record and the case holds none. Both items are then current
    only.

    :verifies: SEG-SREQ-312
    :test-id: SEG-TS-232
    """
    held = support.node("TestSpecification", "TS-1", specHash="spec", implHash="impl")
    gone = support.compare_nodes(held, None)
    assert {name: item.status for name, item in gone.items()} == {
        "specHash": HashStatus.RECORDED_ONLY,
        "implHash": HashStatus.RECORDED_ONLY,
    }
    new = support.compare_nodes(None, held)
    assert {name: item.status for name, item in new.items()} == {
        "specHash": HashStatus.CURRENT_ONLY,
        "implHash": HashStatus.CURRENT_ONLY,
    }
