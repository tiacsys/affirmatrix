0010. The command-line adapter may read repositories; the library still runs no git
=====================================================================================

Status
------

Accepted, 2026-09-16. Reads one clause of ADR-0008 — "the tool never runs
git" — as binding the library and the affirmation store; the write policy of
ADR-0008 and both stages of ADR-0009 stand unchanged. The review after
iteration 0 (2026-09-29) confirmed the narrow reading: this record clarifies
ADR-0008 rather than narrowing it.

Context
-------

ADR-0008 forbade the tool every git operation, reads included — "no
status-dependent behaviour, no reading of the index" — and the reasons it
gave were all about writes: the commit is the maintainer's act, nothing
auto-affirms, nothing auto-commits. Designing the command line against the
library as built surfaced three places where a **read** of repository
state is not a convenience but the only honest source of a value the
records require:

- **A review event records the source revision each endpoint stood at**
  when the judgement was made (SEG-SREQ-025). No record supplies it. A
  node record carries content anchors — repository, path, locator, digest
  — and no revision; only a test outcome carries one, and that comes from
  the run's own artifacts. Producers hash bytes from a checkout without
  learning which commit the checkout is at. Under ADR-0008 as written, the
  only source is the operator typing a commit hash into every affirmation.
- **A drift verdict cannot say what to look at.** The suspect detector
  compares the edge hash it recomputes with the one affirmed, two-sided by
  design. Which endpoint moved, and what its content was when it was
  judged, is answerable only from the anchors plus the revision the review
  event recorded — and rendering the bytes at that revision needs the
  repository.
- **A typed revision is a weaker fact than a discovered one, not a
  stronger one.** An operator supplying a hash asserts that the bytes they
  reviewed are that commit's bytes. A tool that discovers the revision can
  also check the assertion: if the anchored paths differ from the committed
  content, the revision would misdescribe what was hashed, and the tool can
  refuse to record it.

The alternative of extending the producer contract so that producers
report a revision was considered and rejected for iteration 0: it moves the
git read into the library layer ADR-0008 most wanted to keep clean, and the
would-be store — the only producer that exists today — has no repository
behind it at all.

Decision
--------

**The command-line adapter may read repository state.** Exactly three
reads are admitted, each named here so that a fourth is a new decision:

1. **Revision discovery.** For an endpoint whose anchor names a repository,
   the adapter resolves that name through the configured repository map
   (the configuration loader's, not the case's) and reads the revision the
   working tree is at. Each endpoint's revision comes from its own
   repository, so a review event's two revision fields are filled without
   two flags, in the single-repository layout and the multi-stream one
   alike.
2. **Cleanliness of the anchored paths.** Before a discovered revision is
   recorded, the adapter checks that every path the endpoint's anchors name
   matches the committed content at that revision. If any differs, the
   affirmation is refused with the paths named. A discovered revision is
   recorded only when it truly describes the bytes that were hashed.
3. **Before-content recovery.** For display only, the adapter may read the
   content an anchor names at the revision a review event recorded, so a
   reviewer sees what an affirmation bound beside what stands today.

**The adapter never writes.** No add, no commit, no branch, no checkout, no
stash, no edit to any tracked file outside the case's own write root. The
review surface remains the dirty working tree, and the commit remains the
operator's act (ADR-0009).

**The library and the affirmation store run no git, as before.** No
component below the adapter calls git or reads a repository's metadata;
they receive revisions and content as values and never learn where the
values came from. The recorder's contract is unchanged: every judgement
field is the caller's to supply.

**Explicit values remain the override and the fallback.** A revision given
on the command line is recorded as given, with the operator's assertion
standing in for the cleanliness check. Where no repository stands behind an
anchor — the would-be store, a fixture, a producer over an export — the
value must be given explicitly, and the adapter says so rather than
inventing one.

**The affirmation lineage is not read.** Reading the case's own commit
history — to check who committed an affirmation, or when — is a different
question with a different trust model, and this record does not admit it.

Consequences
------------

- ADR-0008's "the tool never runs git" now reads: *the library and the
  store never run git; the command-line adapter runs no git that writes,
  and reads only the three things above.* Every other clause of ADR-0008 —
  writes land in place, the store is the only writer, per-file atomicity,
  no implicit deletion, the output directory relocates the root — is
  untouched.
- Affirming becomes possible without typing a commit hash, and the
  recorded revision becomes a checked fact rather than an assertion. The
  refusal in point 2 is load-bearing: without it, discovery would be the
  inference-over-evidence shortcut the outcome extractor's design warns
  against.
- The configuration loader gains an obligation it did not have: the
  repository map must resolve every repository name an anchor can carry,
  and must name which repository is the implementation one whose revision
  the package gate compares outcomes against.
- Drift reports and the affirmation review surface can show, per named
  content hash, which endpoint moved and where its former content lives —
  the comparison itself is a library function over records, and only the
  final step of fetching old bytes is the adapter's.
- Tests of the adapter's three reads need a repository fixture; the
  library's tests do not change, since nothing below the adapter can tell
  the difference between a discovered value and a typed one.
- Whether a content anchor should itself carry the revision it was read
  at, so that a node record resolves to bytes without a review event
  beside it, is left to the requirement work that follows; this record
  does not decide it.
