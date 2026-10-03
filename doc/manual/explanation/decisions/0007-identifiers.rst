0007. Case-local identifiers in preimages; absolute IRIs in serialization
==========================================================================

Status
------

Accepted, 2026-07-25. Amended 2026-09-29: the two identities this record left
open or stated only for the repository's own tests -- an Implementation's and a
TestSpecification's when a need export supplies the node -- are settled in the
Amendment section below. Nothing else in the record changes: the other
identities, the local type tokens, the IRI rule and the uniqueness rule stand.

Context
-------

:need:`SEG-SREQ-002` puts an edge's endpoint identifiers into its hash, so whatever
string identifies a node becomes irreversible the moment an edge is
affirmed. The design of record identifies nodes by absolute IRI over a
project namespace, and the design record's own open questions note
that this namespace is project-specific and its relocation is deferred —
while the project has already been renamed once. The input most likely
to change was about to become the input least able to.

A configurable base was considered and rejected: it would make node and
edge hashes a function of configuration, so editing one line of YAML would
re-hash the graph and trip every strong edge to suspect with no content
having changed, and it would oblige every proof to record and bind the
configuration that produced it — an obligation the design reserves for a
later phase.

Decision
--------

**Preimages carry case-local stable identifiers.** The strings that enter
the ``edgeTuple`` of ADR-0005 are identities within one case, not IRIs:

- a Requirement's is its **need ID verbatim** — ``SEG-SREQ-001``;
- a TestSpecification's is its manual ``SEG-TS-nnn``, independent of test
  function name and file location;
- a TestOutcome's is ``{runId}/{specId}``;
- a Waiver's is the identifier its author assigns;
- an Implementation's is pending a separate ruling; until it is taken, only
  hand-authored fixture identities exist, since record production is
  deferred past iteration 0.

**Type tokens are local too, and the mapping is prefix-only.** The local
token is the serialized token minus the ``seg:`` prefix — local
``Requirement`` serializes as ``seg:Requirement``, local ``Refines`` as
``seg:Refines``. One rule, no translation table. Node kinds are
``Requirement``, ``Implementation``, ``TestSpecification``, ``TestOutcome``,
``Waiver``; edge kinds are ``Refines``, ``Verifies``, ``Implements``,
``Confirms``, ``Witnesses``, ``Excuses``, ``Calls``. The taxonomy provider
owns both spellings (:need:`SEG-SREQ-029`), and per ADR-0005 those spellings are
integrity-relevant.

**Absolute IRIs are serialization, minted by ``affirmatrix.identity``.**
Instance documents continue to carry absolute IRIs for every ``id``,
``seg:from``, ``seg:to`` and cross-reference field, as the design record
requires and the schemas enforce. ``identity`` mints them from a base that
is free to change, and is the only module that knows the base. It never
participates in hashing; an import rule keeps ``commitment`` independent of
it. Minted IRIs remain **opaque keys** — their parts may themselves contain
the separator, so splitting one back up is not reliably reversible; tooling
reads endpoints from ``seg:from``/``seg:to`` and never parses an ``id``
back into parts.

**The ``seg:`` vocabulary prefix stays.** "Safety evidence graph" remains
the artifact term even though the tool is named affirmatrix; the vocabulary
namespace is a project constant and never enters a preimage.

**Local identifiers must be unique within a case.** A duplicate is a
graph-level error reported by the graph builder, consistent with the
design's existing duplicate-ID error conditions. Their lexical shape is
validated at the taxonomy and schema layer; to the commitment layer a local
identifier is an opaque byte string.

Consequences
------------

- The namespace base becomes a serialization concern. A rebrand, a domain
  move, or a per-project base is a re-serialization: no hash changes, no
  affirmation is invalidated, no edge goes suspect.
- No configuration value reaches any preimage, so the integrity mechanics
  stay unconfigurable without qualification, and the obligation to bind
  configuration into proofs stays dormant, as intended for the first
  version.
- The published identifiers keep the property that matters to a consumer:
  the IRIs in proofs remain globally unique and stable.
- **The trade, stated plainly.** Preimage uniqueness is case-local. Two
  organizations whose cases each contain ``SEG-SREQ-001`` can compute equal
  edge hashes for structurally identical edges. This is invisible in v1,
  where composition is out of scope, and the remedy when Phase C arrives is
  to fold a case identifier into the design root's caller-supplied metadata
  — which sits outside every per-edge preimage, so it costs nothing now and
  requires no re-hashing of edges then. What it does *not* support is
  treating two cases' edge hashes as globally distinct without that step.
- Implementation identity is the one gap: it blocks the self-hosting slice,
  not iteration 0, and it interacts with the design record's claim
  that a function rename is not a meaningful change — which is false once
  the identifier is hashed. Settling it will want a requirement, not just a
  decision here.

Amendment, 2026-09-29: identity of Implementations and TestSpecifications
--------------------------------------------------------------------------

When the structure of an Implementation or a TestSpecification is supplied by
a need export (:need:`SEG-SREQ-153`), its identity is not derived from the source:

- An **Implementation's** identity is the identifier of its implementation
  need, verbatim. The toolbox evidence fixture under ``tests/fixtures`` mints
  ``IMPL-<symbol>`` for it, which is that producer's spelling and not a rule of
  this tool. A renamed symbol is a new need and so a new
  node. (:need:`SEG-SREQ-154`.)
- A **TestSpecification's** identity is the identifier of its test-case need,
  verbatim: in that fixture the value of the test's ``@testid`` tag. The
  ``SEG-TS-nnn`` form stated above is this repository's own spelling of the same
  rule, where the test states it with the ``:test-id:`` marker. A renamed or
  moved test function is not a new TestSpecification, because the function's
  name is not its identity. (:need:`SEG-SREQ-155`.)

Neither identity is recomputed from the source; both are taken from the export.
Both enter the ``edgeTuple`` of ADR-0005 as recorded. The
record of an Implementation located in Python by ``ast`` is not touched by this
amendment.
