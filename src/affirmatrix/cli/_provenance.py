"""Who recorded the last affirmation of an edge: the provenance block of ``edge show``.

A review event holds the role, the reason, the revisions and the hashes of an
affirmation. It holds no person and no time. ADR-0009 makes the commit that
adds the event the act of affirming. ADR-0015 lets the command-line adapter
read the history of the case to find that commit. This module turns the result
of the reads of :mod:`affirmatrix.cli._repository` into the block that
``edge show`` puts on the row of an edge, and into the text of that block.

The block says what the history of the case records. It never says that the
person affirmed the edge, and it never says that the identity is verified. A
commit author, a committer and a Signed-off-by line are text that the person
who made the commit set. The signature status is the one that git gives. The
tool runs no cryptography.

Three statuses cover every answer, and none of them is an error:

* ``found``: a commit holds the event. The block gives the facts of the
  earliest such commit.
* ``notCommitted``: no commit holds the event, or the history has no commit
  yet. The event is a draft in the working tree.
* ``unavailable``: the case is not a repository of its own, or git cannot read
  its history. The block never holds an identity taken from another
  repository, such as the one that encloses the case.

A read that fails gives ``unavailable`` and never a traceback. What the history
holds never changes an exit status (SEG-SREQ-303).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from affirmatrix.cli import _repository

FOUND = "found"
NOT_COMMITTED = "notCommitted"
UNAVAILABLE = "unavailable"

KEY = "recordedInCaseHistory"

_READY = "ready"
_STATUS_WORDS = {NOT_COMMITTED: "not committed", UNAVAILABLE: "not available"}


class CaseHistory:
    """The history of one case, read for the rows of one command.

    The checks of the whole case run once, when the first block is asked for.
    They make sure that the case is the top level of a repository and that the
    history has a commit. They also read whether the history is shallow. The
    search for the commit of an event runs once for each event. A command with
    no affirmed edge asks for no block, and so it runs no git.
    """

    def __init__(self, case_root: Path, document: PurePosixPath) -> None:
        self._case_root = case_root
        self._document = document
        self._ground: tuple[str, bool] | None = None

    def provenance(self, event_identifier: str) -> dict[str, object]:
        """The block for the event that ``event_identifier`` names, as the JSON object.

        :implements: SEG-SREQ-293
        :implements: SEG-SREQ-300
        :implements: SEG-SREQ-301
        :implements: SEG-SREQ-302

        Every key is present in every block. The keys that hold an identity
        are ``None`` unless the status is ``found``, and so are ``signature``
        and ``shallow``. ``signedOffBy`` is an empty list unless the status is
        ``found``. The author is ``None`` when the author is the committer
        (SEG-SREQ-295).
        """
        if self._ground is None:
            self._ground = self._read_ground()
        state, shallow = self._ground
        if state != _READY:
            return _block(state)
        try:
            recorded = _repository.find_recording_commit(
                self._case_root, self._document, event_identifier
            )
        except _repository.RepositoryError:
            return _block(UNAVAILABLE)
        if recorded is None:
            return _block(NOT_COMMITTED)
        return _block(FOUND, recorded=recorded, shallow=shallow)

    def _read_ground(self) -> tuple[str, bool]:
        try:
            _repository.check_own_repository(self._case_root)
            if not _repository.has_commits(self._case_root):
                return NOT_COMMITTED, False
            return _READY, _repository.is_shallow(self._case_root)
        except _repository.RepositoryError:
            return UNAVAILABLE, False


def _block(
    status: str, *, recorded: _repository.RecordingCommit | None = None, shallow: bool = False
) -> dict[str, object]:
    if recorded is None:
        return {
            "status": status,
            "commit": None,
            "subject": None,
            "committer": None,
            "author": None,
            "signedOffBy": [],
            "signature": None,
            "shallow": None,
        }
    same_person = (recorded.author.name, recorded.author.email) == (
        recorded.committer.name,
        recorded.committer.email,
    )
    return {
        "status": status,
        "commit": str(recorded.commit),
        "subject": recorded.subject,
        "committer": _person(recorded.committer),
        "author": None if same_person else _person(recorded.author),
        "signedOffBy": list(recorded.signed_off_by),
        "signature": recorded.signature,
        "shallow": shallow,
    }


def _person(person: _repository.Person) -> dict[str, str]:
    return {"name": person.name, "email": person.email, "date": person.date}


def text_lines(block: Mapping[str, Any]) -> list[str]:
    """The lines that the text report prints for one block, indented under the edge line.

    :implements: SEG-SREQ-298

    The first line always says "recorded in the case history", so the
    identity reads as what the history records. It never says "affirmed by"
    and never says that anything is verified. For a block with no commit, that
    one line gives the status in words and holds no identity and no date.
    """
    if block["status"] != FOUND:
        return [f"  recorded in the case history: {_STATUS_WORDS[block['status']]}"]
    committer = block["committer"]
    lines = [
        f"  recorded in the case history as: {committer['name']} <{committer['email']}>, "
        f"committed {committer['date']}",
        f'    commit {block["commit"]} "{block["subject"]}"',
    ]
    author = block["author"]
    if author is not None:
        lines.append(f"    author: {author['name']} <{author['email']}>, authored {author['date']}")
    lines.extend(f"    signed-off-by: {value}" for value in block["signedOffBy"])
    lines.append(f"    signature: {block['signature']}")
    if block["shallow"]:
        lines.append(
            "    shallow history: the history is cut short, so an earlier commit can hold the event"
        )
    return lines


__all__ = ["KEY", "CaseHistory", "text_lines"]
