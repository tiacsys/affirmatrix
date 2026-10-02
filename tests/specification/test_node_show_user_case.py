"""Verification suite for the question that node show answers end to end.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
question: a case was synced, and then the content of a node changed in its
repository. Is the content still the one the case recorded, and if it is not,
from which revision did the case read the recorded one?

Each test builds a git repository in ``tmp_path`` and syncs a case over it. Then
it changes the content, commits the change and runs ``node show`` as an operator
would.
The expected revisions come from ``git rev-parse HEAD``, taken before and after
the change. The expected content is the text of the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import case

from . import extraction_support as base
from . import node_show_support as support

pytestmark = support.requires_git

CHANGED = "a new statement of REQ-B\nwith a second line\n"


def test_node_show_answers_what_changed_and_where_the_recorded_content_was_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show gives the differing hash, the current bytes and the recorded extraction revision.

    A case sync records the revision of the repository. Then the content of one
    requirement changes and the change is committed, so the repository is at a
    new revision. node show for the changed requirement exits with status 1. It
    names contentHash as differing. It shows the new content, in the text and in
    the JSON, and the SHA-256 of the JSON content is the current digest. It gives
    the first revision as the revision the case recorded, and the new revision as
    the revision of the checkout. node show for a requirement that did not change
    exits with status 0.

    :verifies: SEG-SREQ-313
    :test-id: SEG-TS-253
    """
    fixture = base.build(tmp_path)
    support.sync(fixture, capsys)
    first = base.head(fixture.repository)
    fixture.rewrite("REQ-B", CHANGED)
    second = base.commit_all(fixture.repository, "change REQ-B")
    assert second != first
    where = support.place(fixture)
    shown = support.show(where, "REQ-B", capsys)
    assert shown.status == 1
    entry = shown.entry("contentHash")
    assert entry[support.KEY_STATUS] == support.DIFFERING
    assert shown.block_status("contentHash") == support.DIFFERING
    assert entry[support.KEY_CONTENT] == CHANGED
    assert support.hex_of(entry[support.KEY_CONTENT].encode("utf-8")) == entry[support.KEY_CURRENT]
    assert shown.shown_content("contentHash") == CHANGED.splitlines()
    assert entry[support.KEY_RECORDED_REVISION] == first
    assert entry[support.KEY_CHECKOUT][support.KEY_CHECKOUT_REVISION] == second
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert first in line and second not in line
    assert support.show(where, "REQ-C", capsys).status == 0


def test_node_show_gives_no_fallback_revision_for_a_node_record_with_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """node show says that none is recorded, and gives no other revision in its place.

    The case holds a requirement record with no extraction revision. A review
    event of an edge of that requirement records another revision, given on the
    command line, for the same requirement. Then the content of the requirement
    changes and the change is committed. node show for the requirement exits with
    status 1. It names contentHash as differing and shows the new content. It says
    that none is recorded as the extraction revision. The revision of the review
    event appears nowhere in the text or in the JSON. The checkout line gives
    the revision of the repository.

    :verifies: SEG-SREQ-317
    :test-id: SEG-TS-254
    """
    fixture = base.build(tmp_path, mapped=False)
    support.sync(fixture, capsys)
    status, out = base.affirm(fixture, capsys, "--revision", support.GIVEN)
    assert status == 0, out
    assert base.held_map(fixture.case, "REQ-B") == {}
    (event,) = case.AffirmationStore(root=fixture.case).review_events()
    assert support.GIVEN in (event.from_source_revision, event.to_source_revision)
    base.configure(fixture, mapped=True)
    fixture.rewrite("REQ-B", CHANGED)
    revision = base.commit_all(fixture.repository, "change REQ-B")
    shown = support.show(support.place(fixture), "REQ-B", capsys)
    assert shown.status == 1
    entry = shown.entry("contentHash")
    assert entry[support.KEY_STATUS] == support.DIFFERING
    assert entry[support.KEY_CONTENT] == CHANGED
    assert entry[support.KEY_RECORDED_REVISION] is None
    (line,) = shown.labelled("contentHash", support.LABEL_EXTRACTED)
    assert support.NONE_RECORDED in line.lower()
    assert support.GIVEN not in shown.text and support.GIVEN not in shown.raw
    (line,) = shown.labelled("contentHash", support.LABEL_CHECKOUT)
    assert revision in line
