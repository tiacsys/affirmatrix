"""Scope collection — the proof generator's first slice.

A scope starts from a set of requested requirements and expands to everything
a faithful judgement of them needs, then hands the result to
:func:`affirmatrix.gates.package_gate` through the graph the gate was always
written to accept — this module does not call the gate itself. The only
reason it touches :mod:`affirmatrix.commitment` at all is to mint the
snapshot identifier (SEG-SREQ-052) — a node hash per member and one call to
fold the set into a fingerprint — and every one of those calls is the
commitment layer's own primitive, never a computation this module does
itself; it holds no hashing logic of its own.

The expansion order, hop by hop
--------------------------------

1. **Refines, to a fixed point, toward refiners — never toward an ancestor.**
   A requirement's own coverage is incomplete without every one of its
   transitive refiners, so those are pulled in regardless of depth. An
   ancestor is not: pulling one in without the siblings nobody requested
   would let the gate force those absent siblings satisfied (the leaf/non-leaf
   predicates isolate a requirement's own direct edges by design) and report
   an ancestor clean on a subtree this scope never actually checked. A
   package about one requirement asserts something about that requirement and
   what it depends on, never about its parent's other children.
2. **Verifies and implements**, one hop from every requirement now collected,
   to the specifications and implementations that realize it.
3. **Confirms**, one hop from every specification now collected, to the
   outcomes that confirm it. Evidence rides in on top of the design set here:
   a subgraph cut at the strong edges alone would carry specifications with no
   outcomes attached, and the gate would report gaps and discards the full
   graph does not have.
4. **Excuses**, one hop from every outcome now collected, to the waivers that
   excuse it.

A missing hop does not fail loudly; it silently narrows the scope, which is
the more dangerous outcome — a package that under-reports what it covers
invites being read as covering more than it does.

What the expansion does not do: it never walks a ``Witnesses`` edge to decide
membership, because the implementation a ``Witnesses`` edge names is already
reachable through ``implements`` when it matters (hop 2). An outcome witnessing
an implementation this scope never asked about is not chased outside the scope
to bring that implementation in — the scope is a deliberate cut, and widening
it silently after the fact would defeat the point of cutting it. Whether that
outcome's ``Witnesses`` edge itself survives the cut is a separate question,
answered below.

The subgraph is the full induced cut, not just the discovery edges
---------------------------------------------------------------------

:meth:`affirmatrix.graph.Graph.restricted_to` builds the scope's subgraph as
every edge of any kind whose *both* endpoints are members — not only the
edges the walk above used to discover them. This matters concretely for
``Witnesses``: it never decides membership, but once an outcome and an
implementation are both members for other reasons, the ``Witnesses`` edge
between them belongs in the subgraph too, or a genuinely complete piece of
evidence would look incomplete to the gate for a reason that never happened.

The flip side is deliberate: an outcome that confirms an in-scope
specification but witnesses an implementation this scope never reached loses
that ``Witnesses`` edge in the cut. Read within this scope alone, such an
outcome is incomplete evidence — it satisfies only one of the two questions
:mod:`affirmatrix.satisfaction` asks of it — and the gate discards it exactly
as it would discard any incomplete outcome. That reading is truthful *for this
scope*: the same outcome may well be complete evidence for a different,
wider scope that also requests the implementation in question. Nothing here
tries to be honest about a wider scope nobody asked for.

The partial-vs-total signal and the snapshot identifier
-----------------------------------------------------------

The partial-vs-total signal (SEG-SREQ-039) asks a question the subgraph
cannot answer about itself: whether every top-level requirement — one that is
never the source of a ``refines`` edge — made it into the scope. Answering
that needs the whole graph, not the cut; a subgraph has no way to know what it
excludes. A graph with no requirements at all reports every scope total,
vacuously — there is nothing left out because there is nothing to leave out —
and that vacuous truth is safe precisely because an empty design set is
:mod:`affirmatrix.gates`'s own alarm to raise (SEG-SREQ-045), not this
module's.

The snapshot identifier (SEG-SREQ-052) is minted here because it comes into
existence with the scope, well before any package exists to carry it. Its
timestamp half is an explicit, caller-supplied value — never a clock read, the
same purity-by-parameterization :func:`affirmatrix.gates.package_gate`'s
``evaluation_date`` already commits to — rendered without the colons a
timestamp's usual spelling carries, which Windows filenames refuse. Its hash
half routes through :func:`affirmatrix.commitment.design_root`, the one
primitive general enough to fold a node/edge set into one digest, called with
an explicit empty ``metadata``: this is not a package's sealed root, only a
content fingerprint of the scope taken before any package or its real
metadata exists, and it is why this module still needs no hashing logic of its
own. The fold covers every member's node hash and every edge the induced
subgraph keeps, evidence included, deliberately: a re-run of a test or a
newly granted waiver changes the fingerprint rather than reusing the old one,
which is what lets the identifier answer for the evidence a scope carries and
not only for its design shape.

What this module leaves unmarked
------------------------------------

SEG-SREQ-038 asks that a package *record* its scope; SEG-SREQ-041 asks that
*generating a package* change nothing. Both are stated over a package, and no
package exists until a later slice assembles one — only the value this module
builds, and the purity a test enforces below. Marking either requirement here
would claim an act — recording into a package, generating one — this module
does not perform; both stay unmarked, the same restraint
:mod:`affirmatrix.gates` already takes with SEG-SREQ-059's unauthorised-half.

What this module does not attempt: SEG-SREQ-040's stale-outcome exclusion has
no anchor here either. The staleness comparison itself is now realized —
:func:`affirmatrix.gates.package_gate` judges it, given the current revision
of the implementation repository as an explicit input — but that judgement
happens after this module hands its subgraph to the gate, over the graph the
gate was handed, not over the collection this module performs. So hop 3
above still collects every outcome confirming an in-scope specification
without asking whether any of them is stale; a package's exclusion of what
the gate reports stale is a later slice's, once a package exists to exclude
anything from.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from affirmatrix import commitment, records
from affirmatrix.graph import Graph

_REQUIREMENT = "Requirement"
_REFINES = "Refines"
_VERIFIES = "Verifies"
_IMPLEMENTS = "Implements"
_CONFIRMS = "Confirms"
_EXCUSES = "Excuses"

#: Characters no POSIX or Windows filesystem accepts in a path segment, plus
#: control characters — the reserved set SEG-SREQ-052 asks a minted identifier
#: to avoid. The render steps below can only ever produce digits, ``T``,
#: ``Z``, ``-`` and lowercase hex, so none of these can appear today; the
#: check exists so the next change to either step is caught here, not later.
_RESERVED_CHARACTERS = frozenset('<>:"/\\|?*') | frozenset(chr(code) for code in range(0x20))

#: Windows device names reserved regardless of case, exact-match on a whole
#: path segment (SEG-SREQ-052).
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{digit}" for digit in range(1, 10)}
    | {f"LPT{digit}" for digit in range(1, 10)}
)


class ScopeError(Exception):
    """A requested scope that cannot be collected.

    Raised rather than collected, the same discipline
    :class:`affirmatrix.graph.GraphError` already takes at graph construction:
    a scope that quietly dropped a request nobody could resolve would look
    complete and be wrong in a way nothing downstream could detect.
    """


@dataclass(frozen=True, slots=True)
class Scope:
    """One scope collection's answer: what it covers, and what it hands the gate.

    ``member_ids`` names every node the expansion collected, ``subgraph`` is
    the induced cut over exactly that set (see the module docstring for why a
    cut, not just the discovery edges), ``total`` is the partial-vs-total
    signal (SEG-SREQ-039), and ``snapshot_id`` is this scope's minted
    identifier (SEG-SREQ-052). ``requested_ids`` is kept alongside the
    collected set so a reader can see what was asked for versus what the
    expansion added on top.
    """

    requested_ids: frozenset[str]
    member_ids: frozenset[str]
    total: bool
    snapshot_id: str
    subgraph: Graph

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_ids", frozenset(self.requested_ids))
        object.__setattr__(self, "member_ids", frozenset(self.member_ids))


def collect_scope(
    graph: Graph, requested_ids: Iterable[str], *, snapshot_timestamp: datetime
) -> Scope:
    """Expand a set of requested requirements into the scope that judges them faithfully.

    :implements: SEG-SREQ-036
    :implements: SEG-SREQ-039
    :implements: SEG-SREQ-052

    Pure over ``graph``: no store write, no package file, no mutation of the
    graph or anything reachable from it — this function only reads.
    ``snapshot_timestamp`` must be timezone-aware; a naive value is refused
    rather than read against an assumed timezone, the same purity the
    ``evaluation_date`` precedent already keeps for the package gate.

    A requested identifier absent from ``graph``, or present as something
    other than a Requirement, is refused loudly with :class:`ScopeError`
    rather than silently dropped — see the class for why.
    """
    requested = frozenset(requested_ids)
    _check_requested(graph, requested)
    reachable = _reachable_ids(graph, requested)
    subgraph = graph.restricted_to(reachable)
    members = subgraph.node_ids()
    return Scope(
        requested_ids=requested,
        member_ids=members,
        total=_is_total(graph, members),
        snapshot_id=_mint_snapshot_id(subgraph, snapshot_timestamp),
        subgraph=subgraph,
    )


def _check_requested(graph: Graph, requested: frozenset[str]) -> None:
    """Refuse a requested scope loudly rather than quietly narrowing it."""
    for local_id in sorted(requested):
        try:
            node = graph.node(local_id)
        except KeyError:
            raise ScopeError(f"requested requirement {local_id!r} is not in the graph") from None
        if node.kind != _REQUIREMENT:
            raise ScopeError(
                f"requested requirement {local_id!r} is a {node.kind}, not a Requirement"
            )


def _reachable_ids(graph: Graph, requested: frozenset[str]) -> frozenset[str]:
    """Every id the total expansion order reaches, in the order the module docstring lays out.

    A far endpoint with no backing node record — the making of a broken edge
    — is still returned: the id is what decides which edges
    :meth:`~affirmatrix.graph.Graph.restricted_to` keeps, and a broken edge
    must stay visible to the gate exactly where a scope names it, not vanish
    because the node at the other end never existed.
    """
    requirements = set(requested)
    frontier = list(requirements)
    while frontier:
        current = frontier.pop()
        for edge in graph.incoming(current, _REFINES):
            if edge.from_id not in requirements:
                requirements.add(edge.from_id)
                frontier.append(edge.from_id)

    specifications: set[str] = set()
    implementations: set[str] = set()
    for requirement_id in requirements:
        specifications.update(edge.from_id for edge in graph.incoming(requirement_id, _VERIFIES))
        implementations.update(edge.from_id for edge in graph.incoming(requirement_id, _IMPLEMENTS))

    outcomes: set[str] = set()
    for specification_id in specifications:
        outcomes.update(edge.from_id for edge in graph.incoming(specification_id, _CONFIRMS))

    waivers: set[str] = set()
    for outcome_id in outcomes:
        waivers.update(edge.from_id for edge in graph.incoming(outcome_id, _EXCUSES))

    return frozenset(requirements | specifications | implementations | outcomes | waivers)


def _is_total(graph: Graph, members: frozenset[str]) -> bool:
    """Whether ``members`` includes every top-level requirement in the whole graph.

    A top-level requirement is one that is never the source of a ``refines``
    edge. Asked of ``graph``, never of the subgraph a scope built: a cut
    cannot know what it left out. A graph with no requirements at all makes
    this vacuously true for any scope, however small — an empty set of
    top-level requirements is trivially a subset of anything.
    """
    top_level = frozenset(
        node.local_id
        for node in graph.nodes_of_kind(_REQUIREMENT)
        if not graph.outgoing(node.local_id, _REFINES)
    )
    return top_level <= members


def _mint_snapshot_id(subgraph: Graph, snapshot_timestamp: datetime) -> str:
    """Mint this scope's identifier from an explicit timestamp and the subgraph's own content."""
    members = [subgraph.node(local_id) for local_id in subgraph.node_ids()]
    node_hashes = (commitment.node_hash(node.kind, node.content_hashes) for node in members)
    edge_tuples = ((edge.from_id, edge.to_id, edge.kind) for edge in subgraph.edges)
    fingerprint = commitment.design_root(b"", node_hashes, edge_tuples)
    candidate = f"{_render_timestamp(snapshot_timestamp)}-{records.hex_digest(fingerprint)[:12]}"
    return _checked_as_filename_safe(candidate)


def _render_timestamp(snapshot_timestamp: datetime) -> str:
    """The portable rendering of an explicit, timezone-aware timestamp.

    ISO 8601 basic format, UTC: the date and time separators (``-`` and
    ``:``) that the extended format carries are both dropped, so an instant
    that would otherwise spell as ``2024-03-15T14:32:00Z`` renders here as
    ``20240315T143200Z`` — safe in a Windows path segment, where a colon is
    not.
    """
    if snapshot_timestamp.tzinfo is None:
        raise ValueError(
            "snapshot_timestamp must be timezone-aware; a naive value would read "
            "against whichever timezone the caller's machine happens to be in"
        )
    return snapshot_timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _checked_as_filename_safe(candidate: str) -> str:
    """Refuse a minted identifier that is not safe as a filename on both POSIX and Windows.

    Stated as an active check rather than a passive hope: today's render and
    digest steps can only ever produce digits, ``T``, ``Z``, ``-`` and
    lowercase hex, so this cannot actually fire yet, but the guarantee is
    SEG-SREQ-052's to keep, and the next change to either step is one this
    check must catch, not a later reader.
    """
    reserved = _RESERVED_CHARACTERS & set(candidate)
    if reserved:
        raise ValueError(
            f"snapshot identifier {candidate!r} carries reserved characters: {sorted(reserved)}"
        )
    if candidate.upper() in _RESERVED_WINDOWS_NAMES:
        raise ValueError(f"snapshot identifier {candidate!r} is a reserved Windows device name")
    return candidate


__all__ = ["Scope", "ScopeError", "collect_scope"]
