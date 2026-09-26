"""The record source — the input interface, and the persisted vocabulary.

Two things live here because they are one thing: the record *types* the engine
exchanges, and the protocol that yields them.

* **The protocol.** One interface, several adapters: the store loader, the
  requirements reader, the content extractor, the outcome extractor, and the
  read face of the affirmation store. Swapping iteration 0's store loader for
  the real extractors is an adapter change, not a rewrite.
* **Two roles.** A record stream is either *recorded* — what the affirmation
  store holds, edge records carrying the hash and state they were last
  affirmed with — or *current*, what a producer derives from today's content.
  Deriving an edge's state means comparing exactly these two (SEG-SREQ-015),
  so both need names.
* **The vocabulary.** Node records, edge records and review events are declared
  here so the affirmation store can serialize them without importing the
  components that compute them. That is the boundary keeping persistence below
  package generation in the layering (ADR-0004). Evidence-package documents
  join them when the generator lands.

Records carry hashes and references, never the content those hashes cover
(SEG-SREQ-018) — but every content hash travels with the source location of
what it covers (SEG-SREQ-050), because a digest that cannot say where to look
answers whether content changed and nothing else. Records are frozen: a record
that could be edited in flight would let a hash and the thing it describes
drift apart between the producer that made it and the store that keeps it.

Identifiers here are case-local and stable — the same strings that enter a hash
preimage. Absolute IRIs are minted at serialization time (ADR-0007), so a
record cannot disagree with its own hash about what it identifies.

Iteration-0 backlog item B5.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from affirmatrix._hashing import DIGEST_BYTES, checked_digest

_HEX_DIGITS = frozenset("0123456789abcdef")

#: The one node kind whose records carry an execution result. The taxonomy
#: declares that the kind exists; what a record of it must carry is the
#: vocabulary's own rule, so the spelling lives here beside it.
_TEST_OUTCOME = "TestOutcome"

#: The one node kind whose records carry an excusal's expiry and approver. Same
#: rule as ``_TEST_OUTCOME`` above: the taxonomy declares the kind, the
#: vocabulary declares what a record of it must carry.
_WAIVER = "Waiver"


class LinkState(StrEnum):
    """The states an edge can be in.

    Every edge — strong or evidence — is assigned a derived state by the
    suspect detector; only a strong edge is ever affirmable
    (:func:`affirmatrix.affirmation.affirmable`), so an evidence edge's state
    is carried on the suspect detector's derived stream for a reader — a
    directly outdated ``Confirms`` edge tells a reader the outcome's own
    content moved — but it never appears on the package gate's worklist and
    is never a target for a human judgement.

    ``pending`` and ``broken`` are not resolvable by affirming: a pending edge
    needs a first affirmation, and a broken edge needs its missing endpoint
    restored or the edge removed. Both block an evidence package all the same.
    """

    PENDING = "pending"
    ACTIVE = "active"
    DIRECTLY_OUTDATED = "directlyOutdated"
    TRANSITIVELY_SUSPECT = "transitivelySuspect"
    DOUBLY_OUTDATED = "doublyOutdated"
    BROKEN = "broken"


class TestResult(StrEnum):
    """The recorded result of one test execution — a closed set.

    Four ways a run can end, spelled the way the run artifacts spell them. The
    result is a producer-recorded claim, like an edge's state: the outcome's
    content hash still covers the artifact that is the authority on it, and
    the claim never enters a hash preimage — the same invariant anchors and
    the affirming role keep (a re-spelled result is a reviewable diff, never a
    suspicion event).
    """

    # Not a test class, whatever the name says to a test collector.
    __test__ = False

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class SourceRole(StrEnum):
    """Which of the two streams a record source supplies.

    Named because the difference is not cosmetic: comparing *recorded* against
    *current* is the whole of drift detection, and getting them the wrong way
    round inverts every verdict it produces.
    """

    RECORDED = "recorded"
    CURRENT = "current"


def _require(value: str, what: str) -> str:
    if not value:
        raise ValueError(f"a record needs a non-empty {what}")
    return value


def _coerced_date(value: date | str, local_id: str) -> date:
    """A waiver's expiry, accepted as a ``date`` or an ISO 8601 calendar-date string.

    The same convenience :class:`TestResult` gives a producer that hands over
    a plain string spelling of its closed vocabulary rather than the enum
    member itself.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(
                f"waiver {local_id!r}'s expiry {value!r} is not an ISO 8601 calendar date"
            ) from None
    raise ValueError(f"waiver {local_id!r}'s expiry must be a date, not {value!r}")


@dataclass(frozen=True, slots=True)
class ContentAnchor:
    """One named content hash's digest, bound to where its content lives.

    The location — repository, path, and span locator, per content hash
    (SEG-SREQ-050) — is what before-content recovery fetches by: without it a
    persisted digest answers *whether* content changed but not *what* to look
    at. One value rather than a digest here and a location there, so no write
    path can serialize a digest under one name and its location under another.

    The location is a reference, never integrity data: no part of it enters a
    hash preimage, so moving a file changes the anchor — a reviewable diff —
    without sending a single edge suspect. The locator's *format* is pinned per
    node kind by the case's schemas; the vocabulary asks only that it be there.
    """

    digest: bytes
    repository: str
    path: str
    locator: str

    def __post_init__(self) -> None:
        checked_digest(self.digest, "anchored digest")
        _require(self.repository, "repository")
        _require(self.path, "path")
        _require(self.locator, "locator")


@dataclass(frozen=True, slots=True)
class NodeRecord:
    """A node as the graph knows it: an identity, a kind, and anchored hashes.

    The content those hashes cover lives in the source that produced them and
    is fetched transiently when a human needs to look at it — which is what
    each anchor's location exists to make possible. The content itself is
    never carried here.

    A test outcome additionally carries the result of the execution it records
    (SEG-SREQ-055) — required there and refused everywhere else, because a
    result on a kind that records no execution would be a claim the kind
    cannot make. Requiredness lives here, on the vocabulary, so no supplier
    can omit it: the record source's obligation is discharged by there being
    no such record without one.

    A waiver likewise carries the date it expires and the name of the
    approver who granted it (SEG-SREQ-057, SEG-SREQ-058) — the same move,
    required exactly for the ``Waiver`` kind and refused everywhere else. Both
    are producer-recorded claims, like a test outcome's result: whether the
    waiver is actually still in force and whether that approver may actually
    grant it are judgements the gate makes from these claims, not something
    this vocabulary decides — so neither claim enters a hash preimage, the
    same invariant that keeps a test outcome's result out of one.

    A test outcome additionally carries the revision of the implementation
    repository the test execution ran against (SEG-SREQ-062) — the same
    required-there-refused-elsewhere move once more. Any non-empty string:
    the spelling is deliberately unconstrained here, the same way a role or a
    reason is elsewhere in this vocabulary, and it never enters a hash
    preimage — a producer that later spells the same revision differently
    produces a reviewable diff, not a suspicion event. What a gate does with
    two outcomes' revisions disagreeing is that gate's judgement, not this
    vocabulary's.
    """

    local_id: str
    kind: str
    content_anchors: Mapping[str, ContentAnchor]
    result: TestResult | None = field(default=None)
    expiry: date | None = field(default=None)
    approver: str | None = field(default=None)
    revision: str | None = field(default=None)

    def __post_init__(self) -> None:
        _require(self.local_id, "local identifier")
        _require(self.kind, "kind")
        if self.kind == _TEST_OUTCOME:
            if self.result is None:
                raise ValueError(
                    f"test outcome {self.local_id!r} records an execution and must carry its result"
                )
            object.__setattr__(self, "result", TestResult(self.result))
            if self.revision is None:
                raise ValueError(
                    f"test outcome {self.local_id!r} records an execution and must carry "
                    "the revision it ran against"
                )
            _require(self.revision, "revision")
        elif self.result is not None:
            raise ValueError(
                f"node {self.local_id!r} of kind {self.kind!r} records no test execution "
                "and cannot carry a result"
            )
        elif self.revision is not None:
            raise ValueError(
                f"node {self.local_id!r} of kind {self.kind!r} records no test execution "
                "and cannot carry a revision"
            )
        if self.kind == _WAIVER:
            if self.expiry is None:
                raise ValueError(
                    f"waiver {self.local_id!r} grants an excusal and must carry its expiry"
                )
            object.__setattr__(self, "expiry", _coerced_date(self.expiry, self.local_id))
            if self.approver is None:
                raise ValueError(
                    f"waiver {self.local_id!r} grants an excusal and must carry its approver"
                )
            _require(self.approver, "approver")
        else:
            if self.expiry is not None:
                raise ValueError(
                    f"node {self.local_id!r} of kind {self.kind!r} grants no excusal and "
                    "cannot carry an expiry"
                )
            if self.approver is not None:
                raise ValueError(
                    f"node {self.local_id!r} of kind {self.kind!r} grants no excusal and "
                    "cannot carry an approver"
                )
        if not self.content_anchors:
            raise ValueError(f"node {self.local_id!r} needs at least one content hash")
        for name, anchor in self.content_anchors.items():
            if not isinstance(anchor, ContentAnchor):
                raise ValueError(
                    f"node {self.local_id!r} gives {anchor!r} for {name!r}, which is not a "
                    "ContentAnchor; a content hash travels with its source location"
                )
        object.__setattr__(self, "content_anchors", MappingProxyType(dict(self.content_anchors)))

    @property
    def content_hashes(self) -> Mapping[str, bytes]:
        """The name→digest view the hashing layer consumes.

        A reading of the anchors, not a second store: it cannot disagree with
        them about which digest a name carries.
        """
        return MappingProxyType(
            {name: anchor.digest for name, anchor in self.content_anchors.items()}
        )


@dataclass(frozen=True, slots=True)
class EdgeRecord:
    """An edge as the graph knows it, with the state it was last left in.

    ``edge_hash`` is the hash the edge was affirmed against — present exactly
    when there was an affirmation to record one. An edge that has never been
    affirmed has nothing to compare against, which is why the field is absent
    rather than zeroed: a placeholder would be indistinguishable from a real
    hash that happens to mismatch.
    """

    from_id: str
    to_id: str
    kind: str
    state: LinkState
    edge_hash: bytes | None = field(default=None)

    def __post_init__(self) -> None:
        _require(self.from_id, "source identifier")
        _require(self.to_id, "target identifier")
        _require(self.kind, "kind")
        if self.state is LinkState.PENDING and self.edge_hash is not None:
            raise ValueError(
                f"edge {self.from_id!r} -> {self.to_id!r} is pending and so was never "
                "affirmed; it cannot carry the hash it was affirmed against"
            )
        if self.state is LinkState.ACTIVE and self.edge_hash is None:
            raise ValueError(
                f"edge {self.from_id!r} -> {self.to_id!r} is active and must carry the "
                "hash it was affirmed against"
            )
        if self.edge_hash is not None:
            checked_digest(self.edge_hash, f"{self.from_id}->{self.to_id} edge hash")


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    """One recorded human judgement about one edge.

    Carries the content hashes of both endpoints, so the judgement is bound to
    exactly what was reviewed (SEG-SREQ-024), and the source revision each
    endpoint stood at when it was made (SEG-SREQ-025). That second pair cannot
    be reconstructed later — nothing else correlates a source revision to the
    moment someone accepted it — so it is captured here or lost.

    Beside the composite hash, every named content hash of each endpoint
    travels here too, together with the anchor it was found at, exactly as
    they stood at judgement (SEG-SREQ-127). The composite is what the edge
    hash binds and what the detector's content axis compares; the named map
    is the finer record beside it, read by the per-hash comparison a suspect
    detector builds from this event rather than from the endpoint's current
    node record. Required and non-empty on both sides, the same
    at-composition-or-not-at-all rule as the source revisions: an endpoint
    with no named content hash to carry is not one this judgement could bind.

    The role is the capacity the judgement was made in (SEG-SREQ-049): who and
    when come from the commit that introduces the record, but in-what-role is
    the record's own to state. It is required and free — any non-empty string —
    because role validation is a process concern, not a tool rule; the design
    record's CamelCase spellings are documented convention, not constraint. An
    empty role would satisfy the field while recording nothing, so that alone
    is refused.

    The reason is stored exactly as supplied (SEG-SREQ-028). An empty one is
    allowed: a thin justification is the operator's to give and a reader's to
    judge, and silently substituting text would make the record a paraphrase of
    the judgement rather than the judgement.
    """

    from_id: str
    to_id: str
    kind: str
    from_node_hash: bytes
    to_node_hash: bytes
    from_source_revision: str
    to_source_revision: str
    role: str
    reason: str
    from_content_anchors: Mapping[str, ContentAnchor] = field(kw_only=True)
    to_content_anchors: Mapping[str, ContentAnchor] = field(kw_only=True)

    def __post_init__(self) -> None:
        _require(self.from_id, "source identifier")
        _require(self.to_id, "target identifier")
        _require(self.kind, "kind")
        _require(self.from_source_revision, "source revision for the source endpoint")
        _require(self.to_source_revision, "source revision for the target endpoint")
        _require(self.role, "role")
        checked_digest(self.from_node_hash, f"{self.from_id} node hash")
        checked_digest(self.to_node_hash, f"{self.to_id} node hash")
        for side, anchors in (
            ("source", self.from_content_anchors),
            ("target", self.to_content_anchors),
        ):
            if not anchors:
                raise ValueError(
                    f"a review event needs at least one named content hash for its {side} "
                    "endpoint, carried with the anchor it was found at when judged"
                )
            for name, anchor in anchors.items():
                if not isinstance(anchor, ContentAnchor):
                    raise ValueError(
                        f"the {side} endpoint's {name!r} is {anchor!r}, which is not a "
                        "ContentAnchor"
                    )
        object.__setattr__(
            self, "from_content_anchors", MappingProxyType(dict(self.from_content_anchors))
        )
        object.__setattr__(
            self, "to_content_anchors", MappingProxyType(dict(self.to_content_anchors))
        )


@dataclass(frozen=True, slots=True)
class EdgeReference:
    """A name for one edge: its kind and its two endpoints, as separate values.

    The currency of per-edge requests — a demotion request names the edges it
    licenses with these (SEG-SREQ-051). A triple rather than an identifier,
    because an identifier is an opaque key whose parts may contain the
    separator (ADR-0007); and a value type, so membership in a request is
    equality, not object identity.
    """

    kind: str
    from_id: str
    to_id: str

    def __post_init__(self) -> None:
        _require(self.kind, "kind")
        _require(self.from_id, "source identifier")
        _require(self.to_id, "target identifier")


def hex_digest(digest: bytes) -> str:
    """The lowercase hex spelling of a raw digest, for serialization.

    Hex belongs here rather than beside the hashing primitives (ADR-0005 iv):
    internally a digest is 32 raw bytes and nothing else, and the one place the
    other spelling is needed is where a record is written.
    """
    return checked_digest(digest, "digest").hex()


def digest_from_hex(text: str) -> bytes:
    """The raw digest a lowercase hex spelling denotes.

    Uppercase is refused rather than folded. Two spellings of one digest would
    read back as two different serializations of the same record, and the point
    of a single canonical form is that there is nothing to fold.
    """
    if len(text) != DIGEST_BYTES * 2 or any(character not in _HEX_DIGITS for character in text):
        raise ValueError(
            f"{text!r} is not a digest: expected {DIGEST_BYTES * 2} lowercase hex characters"
        )
    return bytes.fromhex(text)


@runtime_checkable
class RecordSource(Protocol):
    """Everything the engine consumes arrives through this.

    Structural, not inherited: an adapter satisfies it by having the two
    methods, so a producer never has to import the engine to be one. Both
    return iterators — a source may stream, and nothing may assume it can be
    walked twice.
    """

    def nodes(self) -> Iterator[NodeRecord]:
        """The node records this source supplies."""
        ...

    def edges(self) -> Iterator[EdgeRecord]:
        """The edge records this source supplies."""
        ...


__all__ = [
    "ContentAnchor",
    "EdgeRecord",
    "EdgeReference",
    "LinkState",
    "NodeRecord",
    "RecordSource",
    "ReviewEvent",
    "SourceRole",
    "TestResult",
    "digest_from_hex",
    "hex_digest",
]
