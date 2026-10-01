0013. Test evidence comes from run bundles; the case stores none of it
======================================================================

Status
------

Accepted, 2026-10-01. Supersedes ADR-0012. Applies ADR-0010's rule for the
current revision to the verbs that build evidence.

Context
-------

Every edge carries a link state. The states come from affirmation:
``pending`` (never affirmed), ``active``, three suspect states, and
``broken``. Evidence edges carry a test outcome's evidence. Nobody affirms
them (SEG-SREQ-056). Up to now ``case sync`` stored them with the other
edges, and they showed ``pending``. An operator saw evidence edges counted
together with the edges that wait for a judgement. In one case this was
152 of 214 pending edges, where only 62 could take a judgement.

ADR-0012 gave evidence edges two states of their own, ``current`` and
``stale``, derived from the outcome's revision. That put evidence currency
into the one derivation that also serves affirmation. The affirmation
commands then began to need a revision, although an affirmation never
depends on evidence.

A check of the code showed more. The gate, the satisfaction evaluator and
the proof assembly all judge the graph built from the current stream. A
stored test outcome that is absent from the current stream never reaches
a verdict. Stored outcomes and evidence edges are read only by reports
about the store itself. The only stored data that decides anything is the
strong edges' hashes and the review events. And no proof document says
where the evidence came from, so a reader cannot fetch it again.

Decision
--------

**The run bundle is the unit of test evidence.** A run bundle holds the
test report, the revision of each checkout the run used, a dirty flag for
each checkout, the run name and the command. Its identity is the digest of
the stored bundle, not its name. A name is chosen by a person and can
repeat; a digest cannot. For now a bundle is a path and a digest. An
artifact in a registry, addressed by its digest, can replace the path
later.

**The case stores nothing about evidence.** It stores no test outcome
nodes, no evidence edges (``Confirms``, ``Witnesses``, ``Excuses``) and no
evidence state. It keeps what cannot be computed again: the strong edges
and their states, the node hashes, the review events and the proofs.

**Evidence is a view built at verdict time.** A command that needs
evidence reads the configured run bundles, checks each digest against the
configured one, and builds the outcomes and evidence edges from them. The
edge kinds and the gate's rules do not change.

**Evidence for a revision.** The evidence for revision R is the outcomes
of the bundles recorded at R. The implementation checkout decides: its
revision in the bundle must be R, and its dirty flag must be clear. A
bundle whose implementation checkout was dirty is an input error: the
command refuses it before it judges anything, because a dirty run has no
honest revision. A bundle whose digest differs from the configured one is
an input error too. A bundle recorded at another revision is not evidence
for R. "Stale" is this selection rule, not a stored state.

The current revision comes from ADR-0010's rule: a given revision wins,
otherwise it is discovered from the implementation repository, and a
dirty implementation tree is refused. Only the commands that build the
evidence view need it, and they all follow this one rule. Affirmation
never needs it.

**Proofs pin the bundles.** An evidence package records the digest of
every run bundle it used. With the digests, a reader can fetch the same
bundles, build the same graph and compute the verdict again. The package
root still binds the design alone. The digests are recorded beside it, and
no seal binds them yet.

**Link states.** Only strong edges are ``pending``. Evidence is counted in
a view of its own. The suspect detector derives states from the recorded
and the current record source alone; it needs no revision.

**Existing cases.** A case written before this decision holds test
outcome nodes and evidence edges. They are removed, all or nothing. After
that, a case holds no evidence record.

Consequences
------------

- ``graph status`` and ``graph check`` count ``pending`` for strong edges
  only. The evidence view shows its own counts and never turns
  ``graph status`` negative.
- Only ``graph status`` and the proof commands build the evidence view.
  They need the current revision and the run bundles, and they refuse a
  dirty implementation tree. ``graph status`` during editing therefore
  needs a given revision. ``case sync``, ``graph check`` and the ``edge``
  commands need neither a revision nor a bundle.
- The case does not change after each new commit; only the evidence view
  does.
- The configuration names run bundles by path and digest. A new run means
  a new digest in the configuration.
- A proof stays checkable only while its bundles can be fetched. Whoever
  keeps the bundles must keep each one as long as a proof cites it. That
  is a rule of operation, not of the tool.
- No seal binds which bundles a proof used. A separate seal over the
  evidence, or a signature over the package, can bind them later.
- Only the implementation checkout decides. The revisions of the other
  checkouts are recorded in the bundle but not judged yet.
- The mapping from results to specifications and implementations uses
  the exports at R, built again from source. That needs reproducible
  builds for as long as a proof is checked.

Alternatives considered
-----------------------

- **Stored states ``current`` and ``stale`` on evidence edges (ADR-0012).**
  This couples evidence to affirmation: the derivation that serves
  affirmation needs a revision, and every commit changes the case. And
  nothing stored was ever read for a verdict.
- Keep ``pending`` on stored evidence edges and let the command line
  group them apart. This is cheaper, but the case keeps records that
  nothing reads and a state that means "waiting for a judgement nobody
  can give".
- Keep the outcome nodes and drop only the evidence edges. The nodes are
  as derived as the edges, and no verdict reads them from the store.
- New edge kinds for stale evidence. This mixes state and kind.
- Staleness from content hashes. This needs a hash of the implementation
  recorded at run time. A run records a revision, and the revision is
  what the gate already compares.
- Identity by run name. A name can repeat, and a clock can give it a
  wrong date. A digest identifies the content.
