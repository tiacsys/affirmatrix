# The would-be store

The stand-in for the source repositories an evidence graph is built over. It
holds **content** — requirement statements, implementation spans, test
specifications, test results — and the store loader
(`affirmatrix.sources.store`) presents it to the engine as a record source.

It is scaffolding, and it is honest about that. Record production does not
exist yet: there is no requirements reader, no content extractor, no outcome
extractor. Until those land, the content they would locate is written out here
by hand, so the engine has something real to build a graph over. When they land,
this directory and its loader are deleted, and nothing else changes — that swap
is the point of routing every input through one record-source protocol.

Two consequences follow from holding content, and both are deliberate:

- **Nothing here is schema-validated.** The schemas describe the affirmation
  store, which holds hashes and references. This store holds the content those
  hashes cover, which the graph never sees.
- **Nothing here is synchronized with `src/`.** The implementation and
  test-specification entries are *about* the engine's own functions, because
  self-hosting is where this is going, but their content is a hand-written,
  deliberately abridged transcription — not a copy, and not kept in step with
  the tree. Read it as a plausible span, never as the authority on what the
  code says. The code is the authority on that.

## Layout

```
would_be_store/
├── nodes/*.toml       one manifest per node kind — identity and structure
├── edges/*.toml       edge manifests — what relates to what
└── content/<kind>/…   the bytes that are hashed
```

**A node manifest** declares the kind its entries share and maps each local
identifier to the content files it covers:

```toml
kind = "Requirement"

[nodes]
"SEG-SYS-001" = { contentHash = "requirement/SEG-SYS-001.txt" }
```

The keys inside the braces are content-hash field names and must be exactly the
ones the vocabulary declares for that kind — `contentHash` for a Requirement,
`apiHash` and `bodyHash` for an Implementation, and so on. Paths are relative to
`content/` and may not escape it. Nothing is derived from the filename: the
manifest says which file covers which field, because identifiers such as
`run-0001/SEG-TS-001` do not survive being turned into paths.

Two keys are not content paths: a TestOutcome entry also carries
`result = "passed"` — the recorded result of the execution, one of
`passed`/`failed`/`error`/`skipped` — and `revision = "r1"` — the revision of
the implementation repository the execution ran against. Both are record
fields, not content: the content file remains the authority on what the run
observed, a test asserts the two result spellings agree, and the revision's
spelling is open (no format this store's fixture pins).

**An edge manifest** groups pairs by edge kind, source first:

```toml
[edges]
Refines = [
    ["SEG-SREQ-001", "SEG-SYS-001"],
]
```

Manifests are read in filename order, entries in the order they are written, so
the record stream is reproducible.

## What is hashed

**A content hash is the SHA-256 of the content file's bytes exactly as
stored** — no stripping, no line-ending translation, no normalization, trailing
newline included. So the hash of any entry can be checked without the tool:

```console
$ sha256sum content/requirement/SEG-SYS-001.txt
```

Content in files rather than inline in the manifests is the whole reason that
command works, and it is why the format is what it is. An editor that trims
trailing whitespace on save changes a content hash — which is correct behaviour
(the content did change), and worth knowing before it surprises anyone.

The engine derives node hashes and edge hashes from these content hashes; the
store neither computes nor stores them.

**Every edge in this store is pending.** A pending edge is one that carries no
hash it was affirmed against, which is exactly the truth here: nobody has
affirmed anything, and a bootstrapped store that claimed otherwise would be
asserting an affirmation history that never happened. Affirmed state lives in
the affirmation store, which is the other record source — the recorded one.

## What the entries are, and where they came from

**Requirements — translated.** 59 nodes and 48 `Refines` edges, hand-translated
from the requirement specification's needs export: the entry id becomes the
local identifier, its statement becomes the stored content, its refines links
become edges. The stored content is the statement alone. Whether a requirement's
canonical content form should also cover its title is the requirements reader's
question to answer, not this fixture's; hashing the statement is the choice that
forecloses neither answer.

**Implementations, test specifications, test outcomes — authored.** There is
nothing to translate them from, so they are invented: 8 implementations, 9 test
specifications, 8 outcomes from one run, and the `Implements`, `Verifies`,
`Confirms` and `Witnesses` edges between them.

Each test specification's `implHash` content is a pytest function carrying the
two markers a verification test carries: `:verifies:` naming the requirement it
demonstrates, and `:test-id:` naming the specification it realizes. So the same
relation is stated twice in this store — once as a `Verifies` pair in
`edges/coverage.toml`, once inside the hashed content — and a test asserts the
two agree, because nothing else makes them.

The slice is uneven on purpose:

- The **taxonomy provider's** four requirements (SEG-SREQ-029, -030, -031, -032)
  are covered completely, so SEG-SYS-009 has a subtree that can come out
  satisfied.
- The **commitment layer's** and **graph builder's** requirements are covered in
  part. SEG-SYS-001 cannot be satisfied whatever this store says, because two of
  its children (SEG-SREQ-001, SEG-SREQ-017) belong to components iteration 0
  does not build.
- **SEG-TS-003 has no outcome**, so a specification exists that nothing
  executed — a coverage gap that is present because a report with nothing to
  report proves nothing.
- Everything else is uncovered, which is what makes the difference between a
  partial and a total scope visible.

Two identity conventions here are fixture conventions and nothing more. An
implementation's identity is the dotted path of the function it stands for,
because implementation identity is undecided and blocks the record-production
slice rather than this one. A test specification's identity is a manual
`SEG-TS-nnn` that does not yet correspond to any entry in the test
specification document, which does not exist yet.

## Changing it

Editing a content file changes that node's content hash, which changes the node
hash, which changes the edge hash of every edge touching it — so an affirmation
made against the old bytes no longer covers the new ones, and the edges go
suspect. That is the drift-detection workflow, and this store is where it is
exercised: pick a file, edit it, recompute.

Adding a node means adding its content file and one manifest line. Adding an
edge means adding a pair. Adding a *kind* of node means a new manifest with its
own `kind`, which the loader picks up without being told.
