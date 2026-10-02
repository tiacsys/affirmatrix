"""The node noun: show one node against what the case recorded (SEG-SREQ-313).

``node show ID`` answers one question. The case recorded a node at its last
sync, and the current stream supplies the node now. Is the content still the
one the case recorded, and if it is not, from which revision did the case read
the recorded one? The report has one block for each named content hash of the
node: the comparison of the two digests, the extraction revision the case
records, the repository the current anchor names (its revision and whether the
anchored paths match their commit) and the current content.

The verb reads the node records of both sides and builds no graph. That is why
a hash that only one side holds reaches the report. The graph builder refuses a
node whose hash names do not fit its kind, so a verb behind the builder cannot
show such a hash. A verb that builds the graph, such as ``graph check``, judges
the whole stream. This verb judges one node.

The checks run in this order. Each failed check is exit status 2, a request that
the command cannot judge, with a message that names the cause:

1. The case holds exactly one node with the identifier (SEG-SREQ-322).
2. A current stream is given or configured (SEG-SREQ-142, SEG-SREQ-202).
3. The current stream can be read in full (SEG-SREQ-323).
4. The current stream holds the identifier at most once (SEG-SREQ-329).

After these, the exit status comes from the hashes alone: 0 while every one
matches, else 1 (SEG-SREQ-320, SEG-SREQ-321). A repository that is dirty, not
configured or unreadable never changes it (SEG-SREQ-320, SEG-SREQ-331). The verb
writes nothing and runs git only through the read-only operations of
:mod:`affirmatrix.cli._repository` (SEG-SREQ-115, SEG-SREQ-324).
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping
from dataclasses import dataclass

from affirmatrix import drift
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _extraction, _judgement, _outcome, _repository
from affirmatrix.config import Config
from affirmatrix.records import ContentSource, NodeRecord, RecordSource, hex_digest
from affirmatrix.sources import SourceError

_UTF_8 = "utf-8"
_BASE64 = "base64"


@dataclass(frozen=True, slots=True)
class _Checkout:
    """What one read of a repository said, for the repository a current anchor names.

    ``revision`` and ``dirty`` are ``None`` when the repository is not
    configured (``configured`` is false) or cannot be read (``error`` holds the
    reason). ``dirty`` names each anchored path that differs from its commit.
    """

    repository: str
    configured: bool
    revision: str | None = None
    dirty: tuple[str, ...] | None = None
    error: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "configured": self.configured,
            "revision": self.revision,
            "dirtyPaths": None if self.dirty is None else list(self.dirty),
            "error": self.error,
        }

    def lines(self) -> list[str]:
        """The ``checkout`` line, and the ``worktree`` line when the read succeeded."""
        if not self.configured:
            return [f"checkout: no repository is configured for {self.repository}"]
        if self.error is not None:
            return [f"checkout: {self.repository} cannot be read: {self.error}"]
        worktree = "clean" if not self.dirty else "differs: " + ", ".join(self.dirty or ())
        return [f"checkout: {self.repository} at {self.revision}", f"worktree: {worktree}"]


@dataclass(frozen=True, slots=True)
class _Shown:
    """The report of one hash: its comparison and everything read beside it."""

    comparison: drift.NodeHashComparison
    recorded_revision: str | None
    checkout: _Checkout | None
    content: bytes | None

    def document(self) -> dict[str, object]:
        """The JSON entry. Digests are in full and the content is lossless."""
        entry: dict[str, object] = {
            "name": self.comparison.name,
            "status": self.comparison.status.value,
            "recorded": _full(self.comparison.recorded),
            "current": _full(self.comparison.current),
            "recordedRevision": self.recorded_revision,
            "checkout": None if self.checkout is None else self.checkout.document(),
            "content": None,
            "encoding": None,
        }
        if self.content is not None:
            entry["content"], entry["encoding"] = _encoded(self.content)
        return entry


def add_show_arguments(parser: argparse.ArgumentParser) -> None:
    """Register ``node show``'s own arguments: the identifier, and the current stream.

    :implements: SEG-SREQ-230

    No ``--bundle``: the verb reads no run bundle.
    """
    parser.add_argument("local_id", metavar="ID", help="the case-local identifier of the node")
    parser.add_argument("--current", help="the producer supplying the current stream")


def handle_show(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Compare one node's recorded hashes with the current stream's, and report them.

    :implements: SEG-SREQ-313
    :implements: SEG-SREQ-314
    :implements: SEG-SREQ-315
    :implements: SEG-SREQ-316
    :implements: SEG-SREQ-317
    :implements: SEG-SREQ-318
    :implements: SEG-SREQ-319
    :implements: SEG-SREQ-320
    :implements: SEG-SREQ-321
    :implements: SEG-SREQ-322
    :implements: SEG-SREQ-323
    :implements: SEG-SREQ-324
    :implements: SEG-SREQ-329
    :implements: SEG-SREQ-330
    :implements: SEG-SREQ-331

    The checks and their order are in the module docstring. The library decides
    each hash's status (:func:`affirmatrix.drift.compare_node`); this function
    reads, renders, and maps "every hash matches" to the exit status.
    """
    local_id = args.local_id
    held = [node for node in store.nodes() if node.local_id == local_id]
    if len(held) != 1:
        problem = "holds no node" if not held else "holds more than one node"
        return _refuse(f"the case {problem} with the identifier {local_id!r}", args)
    recorded = held[0]
    try:
        current = _judgement.resolve_current(args.current, config)
        found = [node for node in current.nodes() if node.local_id == local_id]
        if len(found) > 1:
            return _refuse(
                f"the current stream holds more than one node with the identifier {local_id!r}",
                args,
            )
        now = found[0] if found else None
        shown = _shown(recorded, now, current, config)
    except (_judgement.JudgementError, SourceError) as error:
        return _refuse(str(error), args)
    if args.json:
        _outcome.render_json(
            {"id": local_id, "kind": recorded.kind, "hashes": [one.document() for one in shown]}
        )
    else:
        _print(local_id, recorded.kind, shown, verbose=args.verbose)
    matching = all(one.comparison.status is drift.HashStatus.MATCHING for one in shown)
    return _outcome.exit_for(_outcome.POSITIVE if matching else _outcome.NEGATIVE)


def _refuse(message: str, args: argparse.Namespace) -> int:
    _outcome.render_refusal(message, as_json=args.json)
    return _outcome.exit_for(_outcome.INDETERMINATE)


def _shown(
    recorded: NodeRecord, now: NodeRecord | None, current: RecordSource, config: Config
) -> list[_Shown]:
    """Every hash of the node, compared, with its revision, checkout and content.

    Each configured repository the current anchors name is read once, for all
    the paths of the node in it. The content comes from ``current`` when it is a
    :class:`~affirmatrix.records.ContentSource`, and only for a hash that has a
    current anchor.
    """
    checkouts = _checkouts(now, config)
    source = current if isinstance(current, ContentSource) else None
    shown = []
    for item in drift.compare_node(recorded=recorded, current=now):
        held_revision = (
            None if item.recorded is None else recorded.extracted_from.get(item.recorded.repository)
        )
        content = (
            source.content(recorded.local_id, item.name)
            if source is not None and item.current is not None
            else None
        )
        shown.append(
            _Shown(
                comparison=item,
                recorded_revision=held_revision,
                checkout=None if item.current is None else checkouts[item.current.repository],
                content=content,
            )
        )
    return shown


def _checkouts(now: NodeRecord | None, config: Config) -> Mapping[str, _Checkout]:
    """One read for each repository the current record's anchors name, by repository name.

    A repository that is not configured, or that cannot be read, is a
    :class:`_Checkout` that says so. Neither stops the report.
    """
    if now is None:
        return {}
    checkouts: dict[str, _Checkout] = {}
    for name in sorted({anchor.repository for anchor in now.content_anchors.values()}):
        location = config.repository(name)
        if location is None:
            checkouts[name] = _Checkout(name, configured=False)
            continue
        try:
            state = _extraction.read_repository(location, _extraction.anchored_paths(now, name))
        except _repository.RepositoryError as error:
            checkouts[name] = _Checkout(name, configured=True, error=str(error))
        else:
            checkouts[name] = _Checkout(
                name, configured=True, revision=state.revision, dirty=tuple(sorted(state.unusable))
            )
    return checkouts


def _full(anchor) -> str | None:
    return None if anchor is None else hex_digest(anchor.digest)


def _encoded(data: bytes) -> tuple[str, str]:
    """The content as JSON carries it, and the name of its encoding.

    :implements: SEG-SREQ-328

    Text when the bytes are valid UTF-8. Otherwise their base64 form, so the
    JSON never changes a byte.
    """
    try:
        return data.decode(_UTF_8), _UTF_8
    except UnicodeDecodeError:
        return base64.b64encode(data).decode("ascii"), _BASE64


def _print(local_id: str, kind: str, shown: list[_Shown], *, verbose: bool) -> None:
    print(f"node {local_id} ({kind})")
    for one in shown:
        comparison = one.comparison
        print(f"hash {comparison.name}: {comparison.status.value}")
        print(f"  recorded: {_digest(comparison.recorded, verbose)}")
        print(f"  current: {_digest(comparison.current, verbose)}")
        print(f"  extracted from: {one.recorded_revision or 'none recorded'}")
        if one.checkout is not None:
            for line in one.checkout.lines():
                print(f"  {line}")
        _print_content(one)


def _digest(anchor, verbose: bool) -> str:
    return _outcome.anchor_display(anchor, verbose=verbose) or "none"


def _print_content(one: _Shown) -> None:
    """The content block: the bytes as UTF-8 text, or the reason there are none to show."""
    if one.comparison.current is None:
        print("  content: no current content")
    elif one.content is None:
        print("  content: none supplied")
    elif not one.content:
        print("  content: empty (0 bytes)")
    else:
        text = one.content.decode(_UTF_8, errors="replace")
        if text.encode(_UTF_8) == one.content:
            print("  content:")
        else:
            print("  content (not valid UTF-8; U+FFFD marks the bytes that fail, --json is exact):")
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        for line in lines:
            print(f"    {line}")


__all__ = ["add_show_arguments", "handle_show"]
