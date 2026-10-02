0009. The affirmation store is a sidecar commit lineage; committing is affirming
=================================================================================

Status
------

Accepted, 2026-08-06 (proposed 2026-07-25). Read by the command-line adapter, as ADR-0015 says. Stage 1 is in force and describes
what is already true today; stage 2 is not yet scheduled, and the ADR-0008
clauses it would supersede stand unchanged until it is.

Context
-------

ADR-0008 settled where bytes land and forbade the tool from running git. It
did not say what a commit *means*. That question has now been answered at the
design level, and it changes the status of an act the project already performs
every day.

An affirmation is a content-bound human judgement (:need:`SEG-SYS-004`). Its record —
the ReviewEvent — is a file the affirmation store persists. But a file on disk
cannot say who wrote it, when, or whether they were entitled to. Today those
three things are supplied by the maintainer's commit, and by the authorised
committer list the design already defines for exactly this purpose in the
waiver case. The commit is therefore not incidental packaging around an affirmation.
It is where the affirmation acquires an author, a moment, and an authority.

Identifying the commit with the act only works if it is unambiguous *what* a
commit commits to. As things stand the store is a directory in the tool
repository, so one commit could carry a bug fix and an affirmation at once, and
the committer check would not know which it had authorised. That ambiguity
is resolved below, and resolving it deliberately reopens a small part of
the mono-repo decision recorded in ADR-0002.

Two repositories must be kept apart throughout, because both are git and only
one is new here:

* the **source repositories**, which hold the content the graph measures. Git
  was always assumed for these — :need:`SEG-SREQ-025` requires a *source* commit per
  endpoint, and that anchor cannot be backfilled;
* the **store lineage**, which holds the graph itself. That it is a git commit
  history is what this ADR ratifies.

A further consideration forces the ADR now rather than later: system
requirements must stay free of solution technology, and software requirements
may name git only once a decision record ratifies the realization. Until this
ADR is accepted, the affirmation store's requirements cannot say "commit".

Decision
--------

**The affirmation store's persisted state is an independent commit lineage in
this repository** — an orphan branch, conventionally ``case``, that shares no
history with ``main`` or ``tool`` and is **never merged into either**. It is a
sidecar: the same repository as a container, a separate history as a record.
The graph's state is the committed state of that lineage; anything uncommitted
is a draft.

This is the pattern the project already runs on. The ``tool`` branch is itself
an orphan lineage checked out as a worktree in the Phase-B workspace; the store
lineage is that arrangement applied once more, one level in.

**A commit to that lineage, made by an authorised committer, is a store act,
and an affirmation is the kind of store act that introduces review events.**
The act and its record are two halves that mean nothing apart:

* the **ReviewEvent record** states *what* was affirmed — the edge, the content
  hashes of both endpoints (:need:`SEG-SREQ-024`), the source anchor per endpoint
  (:need:`SEG-SREQ-025`), the role and the reasoning. This is affirmatrix's semantics
  and must be schema-valid and byte-stable on read-back (:need:`SEG-SREQ-019`, -020);
* the **commit** supplies *who*, *when*, and *that this was deliberate* — the
  committer identity checkable against the authorised committer list, the
  timestamp, and the act of election itself.

Before the commit, the same bytes are a proposal. After it, they are an
affirmation. Nothing about the record changes; its standing does.

:need:`SEG-SREQ-024` **and -025 are satisfied by the serialized record, not by commit
metadata.** Endpoint hashes and source anchors are hash-covered data that
proof generation consumes; they must validate against a schema, survive
read-back unchanged, and remain addressable as data. A commit message
satisfies none of that, and git history is rewritable in ways a tracked file
is not. A commit message **may** carry a denormalized, explicitly
non-authoritative summary — the affirmed edge, the anchor pair — for human
legibility at the review surface. That mirrors the deliberate denormalization
the design already sanctions for waiver expiry; the record remains the
single source of truth, and a disagreement between message and record is
resolved in favour of the record.

**Granularity.** One commit per store operation. A single-edge affirmation
introduces one ReviewEvent; a bulk sweep introduces many under one commit, with
the selecting query recorded in the message, as the design already
prescribes for the bootstrap sweep.

Mechanics
~~~~~~~~~

``case/`` in the working tree is expected to be a ``git worktree`` checkout of
the store lineage. Stated plainly, including the parts that are not free:

.. code-block:: console

   # bootstrap, once
   git switch --orphan case
   git commit --allow-empty -m "case: initialise the affirmation lineage"
   git switch tool
   git worktree add case case

* **The tool branch must stop tracking ``case/``.** It currently carries
  ``case/README.md``; that file is removed from ``tool`` and ``/case/`` is
  added to its ``.gitignore``, or every store file appears as untracked
  content of ``tool``. The explanation the README carried moves into the
  manual, where it belongs anyway.
* **A fresh clone has no case.** Clone-and-*build* is unaffected — the engine
  and its suite need no store. Clone-and-*verify* requires fetching the branch
  and adding the worktree. This is a real ergonomic cost and it trims a corner
  off the clone-and-build motive of ADR-0002; it trims it for the evidence,
  not for
  the code, which is the right side of the trade but should not be described as
  free.
* **Publishing the dogfood case means pushing the branch.** If the lineage is
  never pushed, a consumer of the repository sees a tool with no evidence.
* **CI sees one branch by default.** Testing the engine needs no case;
  exercising the store or a self-proof needs an explicit fetch-and-worktree
  step. CI must never hold write access to the lineage — a headless commit
  would be a headless affirmation, which the authority boundary forbids — and
  the sidecar makes that enforceable as ordinary branch protection rather than
  as a convention.
* **Nested versus sibling placement** is not load-bearing. ``case/`` nested in
  the tool worktree is the ergonomic default; a sibling worktree is equally
  supportable, because ADR-0008 already makes the write root a parameter. The
  tool writes files and does not know which it is in.

**Staging.**

*Stage 1 — iteration 0, the present.* Exactly the ADR-0008 posture: the tool
writes files in place and knows nothing of git; the maintainer stages,
reviews the dirty tree, and commits. The identification above already holds
— the maintainer's commit is already the affirmation — but no code depends
on it.

*Stage 2 — later, unscheduled.* The tool prepares the commit on the
maintainer's behalf: it stages the paths it wrote, drafts the message including the
denormalized summary, and presents the result for the maintainer to enact.
It may
execute ``git commit`` itself **only** in response to an explicit,
per-operation human authorization, and never in a non-interactive context —
which is the boundary the design already draws for any write path:
human-in-the-loop, git-committed review, never headless.

**What "on behalf" preserves**, precisely:

* the **judgement** is the human's; the recorder originates no affirmation of
  its own (:need:`SEG-SREQ-026`), and preparing a commit is not originating one;
* the **authorization** is explicit and per-operation — never a standing
  grant, never inferred from configuration, never exercised in CI;
* the **identity** recorded is the human's. affirmatrix must never appear as
  the author or committer of a store commit, and must add no co-authorship
  trailer. A bot identity in that field would make the committer check
  verify the tool instead of the maintainer, hollowing out the one mechanism
  that makes
  affirmation attributable. At most the tool may record its version in a
  trailer, as provenance about the *preparation*, not the act.

**Authorization mechanism.** The authorised committer list becomes the
check for store commits, as it already is for waivers: committer identity and
account must match one entry with a validity range covering the commit date.
This introduces no cryptographic signature; v1's posture remains
governance-plus-fingerprint, and a signature stays a separate,
additive, future decision.

Consequences
------------

- **The code-change/affirmation ambiguity dissolves structurally, not by
  discipline.** A commit on the store lineage can only touch the case, because
  the orphan tree contains nothing else; a commit on ``tool`` cannot touch the
  case, because ``case/`` is ignored there. No convention, no review vigilance,
  no path-prefix rule to remember.
- **The committer check becomes unambiguous.** What was authorised is exactly what
  the commit contains, because the commit cannot contain anything else.
- **History-rewriting protection is now scopeable.** Forbidding
  non-fast-forward updates applies to one branch with one purpose, rather than
  to the branch developers work on daily — which is what made the protection
  impractical to state before.
- **The mono-repo trade of ADR-0002 is partially and deliberately reopened:
  the graph stream returns as a lineage while the mono-repo stays the
  container.** The four-stream topology stays demoted — requirements,
  implementation and results remain paths, and the fixture remains the
  fixture — but the graph stream returns as a history, because history is
  what it was always for. This refinement stays a decision about *this
  repository* and is deliberately not raised into the design record, so
  that later realizations of the affirmation log remain unconstrained.
- **Affirmation becomes verifiable rather than merely asserted.** Today a
  ReviewEvent's affirming role is self-declared data in a file. Under this
  realization the identity behind it is git-attested and list-checked, which
  is a genuine strengthening of the mechanism the whole project rests on.
- **Software requirements may now name git** — commit, repository, committer,
  lineage — where they concern the affirmation store or the recorder. System
  requirements stay technology-free: :need:`SEG-SYS-004` and :need:`SEG-SYS-007` are unchanged
  and must remain so.
- **The affirmation concept is untouched.** A content-bound human judgement is
  what it always was. This ADR chooses a substrate; it makes no claim about
  meaning.
- **Nothing in the integrity layer changes.** Git object ids are not
  affirmatrix hashes, never enter a preimage, and the commitment layer remains
  unaware of any of this (ADR-0003, ADR-0005).
- **What this will supersede in ADR-0008, when stage 2 is scheduled** — and
  only then: the clause "The tool never runs git. No add, no commit, no
  branch, no status-dependent behaviour, no reading of the index", and the
  clause "the review surface is the dirty working tree … and commits", which
  becomes *the tool prepares; the maintainer enacts*. **Unaffected in both
  stages:**
  writes land in place, per-file atomicity, no implicit deletion, the
  ``--output-dir`` override, the affirmation store as sole writer, and the
  authority boundary.
- ADR-0008 is not amended by this draft. It is superseded in part on
  acceptance *and* scheduling of stage 2, not before.

Open questions
--------------

1. **Which store commits are affirmations.** Proofs are also written under
   ``case/`` (ADR-0008), so a commit on the lineage may be a proof placement
   rather than an affirmation. Both are store acts under committer
   authority; only
   one is a judgement. Whether they are distinguished by path (``events/`` and
   ``edges/`` against ``proofs/``), by trailer, or not at all, is unsettled —
   and it matters, because "committing is affirming" is precise only once the
   kinds are separated.
2. **Independent verifiability narrows.** A proof should be verifiable by
   recomputation from its own contents. If affirmation authority rests on
   commit metadata, a verifier holding only the sealed package cannot check
   it — they need the lineage. A partial remedy is to record, per review event
   in the proof, the introducing commit id and committer so the package is at
   least self-*describing*; whether that suffices, and what "independently
   verifiable" should mean for the affirmation layer as opposed to the design
   root, is open.
3. **Signature and authorship binding.** Committer identity strings are
   forgeable absent signing. Whether store commits must be signed, and whether
   verification requires a valid signature, is the natural place the deferred
   signature decision would land.
4. **Enforcement of the append-only property.** The sidecar makes
   non-fast-forward protection scopeable; whether it is actually enforced
   server-side, enforced by hook, or merely conventional is not decided.
5. **Detached proof output.** A package generated to ``--output-dir`` has no
   commit and therefore no attested moment. The design already has the
   maintainer place and commit proofs, which suggests a proof is authoritative only once committed —
   but that is currently an inference, not a ruling.
6. **Bulk granularity and authority scope.** One commit introducing N review
   events is one authorised act covering N judgements. Whether that is
   acceptable — as the design already assumes for the bootstrap sweep — or
   whether
   high-consequence edges warrant one act each, is a policy question the
   mechanism does not answer.
7. **Publication and discoverability.** With ``case/`` ignored on ``tool`` and
   the lineage unpushed by default, a cloner sees no evidence and no
   explanation of where it went. What the repository says about its own case,
   and whether the branch is published as a matter of course, needs deciding
   before the dogfood case is meant to be anyone else's evidence.
