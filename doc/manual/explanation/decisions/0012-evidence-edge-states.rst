0012. Evidence edges have their own link states
===============================================

Status
------

Accepted, 2026-10-01. Changes the states of the edges that carry a test
outcome's evidence. The decision of ADR-0010 on where a revision comes from
applies, with one difference per command (see *Where the revision comes
from*).

Context
-------

Every edge carries a link state. The states come from affirmation:
``pending`` (never affirmed), ``active``, three suspect states, and
``broken``. Evidence edges carry a test outcome's evidence, and nobody
affirms them (SEG-SREQ-056). A new run resolves them, not a judgement. Up
to now they took the same states. They are never affirmed, so they were
always ``pending``: the graph builder sets every edge that has no stored
hash to ``pending``. An operator saw evidence edges counted together with
the edges that wait for a judgement. In one case this was 152 of 214
pending edges, where only 62 could take a judgement.

The package gate already knows when an outcome's evidence is out of date.
An outcome whose recorded revision differs from the current revision of
the implementation repository is stale (SEG-SREQ-063). The gate leaves it
out and reports it (SEG-SREQ-067).

Decision
--------

**Two states of their own.** An evidence edge takes one of two states:

- ``current`` — the test outcome it touches records the current revision;
- ``stale`` — that outcome records a different revision.

``broken`` still applies to every edge with an absent endpoint, and it
comes first. An evidence edge is never ``pending`` and never ``active``. It
is never affirmed, and its record carries no edge hash. The states are link
states, not edge kinds. The edge kinds do not change.

**Which edges.** An evidence edge is an edge whose kind does not propagate
suspicion and which has a test outcome at one end: ``Confirms`` and
``Witnesses`` (the outcome is the source) and ``Excuses`` (the outcome is
the target). ``Calls`` has no outcome at either end. It keeps its present
treatment until it is activated.

For an ``Excuses`` edge, ``current`` says only that the outcome records the
current revision. It says nothing about whether the waiver is valid. Waiver
expiry stays a question for the gate.

**Who derives the state.** The suspect detector derives it. It gets the
current revision as a third explicit input, beside the recorded and the
current record source. The graph builder keeps the state that an evidence
edge's record carries. It sets only the other edges with no stored hash to
``pending``.

**Where the revision comes from.** The command line resolves it under the
rule the package gate uses (ADR-0010): a revision given on the command line
wins; otherwise it is discovered from the configured implementation
repository. The rule differs by what the command does:

- ``case sync``, ``proof check`` and ``proof generate`` record or judge.
  They refuse a dirty implementation tree, as ADR-0010 requires.
- ``graph status``, ``edge show`` and ``edge affirm`` compare against the
  discovered revision even when the tree is dirty. A change elsewhere in
  the repository must not refuse an affirmation whose endpoints it does
  not touch.
- A revision that cannot be resolved — none given and no implementation
  repository configured — is a request the command cannot judge (exit
  status 2), for every command that derives states.

The demand is lazy. A command needs the revision only when the current
records hold an evidence edge. A case with no test outcomes needs no
implementation repository.

When one command derives states and evaluates the gate, both use the one
resolved revision.

**The gate and the satisfaction evaluator do not change.** The gate does
not read evidence edge states. It keeps leaving out stale outcomes by
revision, so its input stays explicit. The satisfaction evaluator stays
unaware of revisions. No gate verdict and no satisfaction result changes.

**Existing cases.** The edge schemas narrow by kind: the strong kinds keep
their six states, and the evidence kinds allow ``current``, ``stale`` and
``broken`` only. A case written before this decision stores its evidence
edges as ``pending``. ``case refresh`` migrates them. When it refreshes the
schema copy, it rewrites every stored evidence edge in state ``pending`` to
``stale``, the value that cannot claim too much. It reads the stored
edges as they are, without the old copy, because a refresh must also
repair a case whose copy is missing. It checks every record of the case,
the rewritten edges included, against the new copy before it writes
anything. If one record fails, it refuses and changes nothing. Its report
gives the number of edges it migrated. It changes no strong edge and no
edge with a stored hash. A refresh that stops part-way (a crash between
files) is repaired by running it again. The next ``case sync`` then derives the true
state. The path for an existing case is ``case refresh``, then
``case sync``, then a commit of the case.

Consequences
------------

- ``graph check`` and ``graph status`` count evidence edges apart from the
  edges that can be affirmed. ``graph check`` has no revision, so it shows
  no evidence edge state. A stale evidence edge is information, not a
  negative verdict of ``graph status``.
- Every case needs ``case refresh`` and then ``case sync`` once.
- After each new implementation commit, a sync marks every evidence edge
  stale until the tests run again. The case history shows when evidence
  went stale.
- ``graph status`` and the ``edge`` commands now need a resolvable revision
  when the case holds evidence edges.
- Only the revision decides. A change to an implementation in a repository
  other than the implementation repository does not make its evidence
  stale. This is a known limit.
- On a dirty tree, ``graph status`` and the ``edge`` commands compare
  against the last commit, so evidence can show ``current`` for code with
  uncommitted changes. Only ``case sync`` and the proof commands record or
  judge, and they refuse a dirty tree.

Alternatives considered
-----------------------

- Keep ``pending`` and let the command line group evidence edges apart.
  This is cheaper, but the case keeps a state that means "waiting for a
  judgement nobody can give".
- New edge kinds for stale evidence. This mixes state and kind. A new run
  would have to replace an edge instead of changing its state.
- Staleness from content hashes. This needs a hash of the implementation
  recorded at run time. Outcomes do not record one.
- Refuse a dirty tree for every command. This is one rule, but a stray
  build directory would then block ``graph status`` and refuse an
  affirmation whose endpoints the change does not touch.
- Keep ``pending`` as an allowed old value on evidence edges for one step,
  and remove it later. This leaves a state that the decision says never
  occurs. Migration in ``case refresh`` removes it at once.
