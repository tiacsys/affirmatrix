# The would-be store

The stand-in for the source repositories an evidence graph is built over. It
holds **content** — requirement statements, implementation spans and test
specifications — and the store loader
(`affirmatrix.sources.store`) presents it to the engine as a record source.

It is scaffolding, and it is honest about that. Until the readers of the real
sources serve every input of this repository's own case, the content they would
locate is written out here by hand, so the engine has something real to build a
graph over. When they do, this directory and its loader are deleted, and nothing
else changes — that swap is the point of routing every input through one
record-source protocol.

**It holds no test evidence.** An earlier version of this store also held ten
test outcomes and the edges that tie them to the specifications and the
implementations they confirm and witness. Test evidence now comes from run
bundles only, read when a verdict is judged, so this store no longer carries
test outcomes, and it no longer carries `Confirms` or `Witnesses` edges. The
requirement, implementation and test-specification files are unchanged, byte for
byte, so no content hash of an affirmed edge's endpoint moved. This repository's
own case has no test evidence until its own test run is read as a run bundle.

Two consequences follow from holding content, and both are deliberate:

- **Nothing here is schema-validated.** The schemas describe the affirmation
  store, which holds hashes and references. This store holds the content those
  hashes cover, which the graph never sees.
- **Nothing here is synchronized with `src/`.** The implementation and
  test-specification entries are *about* the engine's own functions, because
  self-hosting is where this is going, but their content is a verbatim
  transcription taken at one named commit — not a copy that tracks the tree,
  and not kept in step with it afterwards. This transcription was taken from
  the tree at commit 678f72f. Read it as what the code said at that commit,
  never as the authority on what it says now. The code is the authority on
  that.

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
manifest says which file covers which field, because identifiers do
not always survive being turned into paths.

Every key inside the braces is a content path. A manifest entry carries no
recorded result and no revision: a record that says what a test run observed
is not content of this store.

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

**Requirements — translated.** 139 nodes and 128 `Refines` edges, translated
from the requirement specification's needs export: the entry id becomes the
local identifier, its statement becomes the stored content, its refines links
become edges. The stored content is the statement alone. Whether a requirement's
canonical content form should also cover its title is the requirements reader's
question to answer, not this fixture's; hashing the statement is the choice that
forecloses neither answer.

**Implementations — found.** 79 nodes, one per function, method, or class in
`src/affirmatrix/` whose docstring carries an `:implements:` field, found by
walking the source tree at the named commit. The identity is the dotted path
from the package root, class-qualified for a method (for example
`affirmatrix.case.AffirmationStore.nodes`). A definition can carry more than
one `:implements:` field, one per requirement it realizes, so the 79 nodes
carry 141 `Implements` edges between them.

**Test specifications — found.** 10 nodes: one test specification per pytest
function under the verification suite carrying both a `:verifies:` and a
`:test-id:` field. `Verifies` (10) completes the edges between them and the
requirements.

**The span each content field covers is one rule, whole source lines, for all
four hash fields a definition can carry:**

- `apiHash` (Implementation) — the `def`/`class` line(s) through the line
  holding the docstring's closing quotes.
- `bodyHash` (Implementation) — the following lines through the end of the
  block.
- `specHash` (TestSpecification) — the docstring's opening-quote line through
  its closing-quote line. A test function's `def` line belongs to neither of
  its spans — the marker fields live in the docstring, not the name, so the
  docstring is what the specification's identity and intent hash cover.
- `implHash` (TestSpecification) — the following lines through the end of the
  block.

Every span is taken **verbatim**, line terminators staying with their lines —
no re-flowing, no re-indenting. This is a fixture convention, stated here so
the next transcription can repeat it exactly; it says nothing about the span
rule an eventual content extractor would use.

Because the marker fields live inside the hashed docstring, `implHash` never
carries them — only `specHash` does. The `Verifies` edge each specification's
marker states is also declared as a pair in `edges/coverage.toml`, so the same
relation is stated twice in this store, and a test asserts the two agree,
because nothing else makes them.

The coverage this slice carries is uneven, and reading it needs one more
distinction than "covered" and "not":

- The **taxonomy provider's** four requirements (SEG-SREQ-029, -030, -031, -032)
  are covered by both an implementation and a specification, so SEG-SYS-009
  has a subtree that can come out satisfied.
- 13 software requirements carry no `:implements:` field anywhere in the tree.
  Six of them (SEG-SREQ-069, -076, -084, -089, -105, -114) are non-leaf:
  coverage for a non-leaf requirement never runs through a marker of its own,
  it flows through the requirements refining it, so these six are absent from
  the marker set by the convention itself — their absence says nothing about
  whether their own subtree is covered (SEG-SREQ-114's own children,
  SEG-SREQ-115 and -116, are two of the seven below). The other seven
  (SEG-SREQ-001, -053, -059, -066, -115, -116, -126) are leaves with no marker
  at all — genuine gaps. One of the seven has its own stated reason:
  SEG-SREQ-059 names a check the code does not yet perform, and the source
  says so where the function that half-realizes it lives, rather than
  claiming the marker.
- System-level requirements (`SEG-SYS-nnn`) never carry a direct
  `:implements:` field or a specification's `:verifies:` field — coverage for
  a non-leaf requirement always flows through the software requirements
  refining it. Reading them as "uncovered" by the same test as a leaf would
  count a structural fact as a gap.
- Past the ten leaves the verification suite covers, every other software
  requirement has no specification verifying it — the difference between a
  partial and a total scope stays visible.

Implementation identity is the dotted path of the function, method, or class
carrying the marker — settled, not a placeholder. Test-specification identity
is the manual `SEG-TS-nnn` each docstring states, independent of the test
function's name and file location.

## Changing it

Editing a content file changes that node's content hash, which changes the node
hash, which changes the edge hash of every edge touching it — so an affirmation
made against the old bytes no longer covers the new ones, and the edges go
suspect. That is the drift-detection workflow, and this store is where it is
exercised: pick a file, edit it, recompute.

Adding a node means adding its content file and one manifest line. Adding an
edge means adding a pair. Adding a *kind* of node means a new manifest with its
own `kind`, which the loader picks up without being told.
