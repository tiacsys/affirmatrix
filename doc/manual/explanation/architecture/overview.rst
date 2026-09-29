Architecture overview
=====================

This page is the one to read first. It says what affirmatrix is for, what
stands around it, how it is cut into components, what holds across all of
them, and what the tool does not yet do. The pages beside it describe single
components; this one links to them and does not repeat them.

Purpose and quality goals
-------------------------

affirmatrix binds requirements, tests and code into a hash-anchored graph and
generates an integrity package over it. Each requirement, source definition,
test specification and test outcome is a node that carries hashes of its
content. Each relationship between two nodes is an edge that carries a hash of
both endpoints. A human affirms an edge, once, by recording a judgement that
the two ends belong together; from then on the tool recomputes hashes and says
whether the content the judgement was made over still holds.

Three workflows sit on that mechanism:

- **Consistency.** Build the graph from records and refuse it if it is not a
  well-formed graph: a kind the vocabulary does not declare, a cycle in the
  refines relation, a duplicated identifier.
- **Drift.** Compare what each edge was affirmed against with what its
  endpoints hold now, and report each edge as pending (never affirmed),
  active, directly outdated (its own content moved), transitively suspect (a
  strong edge it depends on is not active), doubly outdated (both at once) or
  broken (an endpoint is missing).
- **Evidence package.** For a chosen scope of requirements, check that the
  scope is ready, and if it is, seal it into four documents whose claims a
  reader can verify by recomputation.

Four goals shape every decision below.

- **A package verifies from its own contents.** The design root is
  recomputable from the design consistency proof's own fields (its node
  manifest, design edges, scope and revision), without the graph that
  produced it (:need:`SEG-SYS-005`).
- **The case stores hashes and references, never content.** The content a hash
  covers stays in its source repository (:need:`SEG-SYS-007`).
- **A link's state changes only by a human's recorded act.** The tool derives
  suspicion and clears it by recomputation, but it never affirms
  (:need:`SEG-SYS-011`).
- **A verdict is recomputed, never carried.** No record stores a conclusion
  that a reader could not reach again from the hashes it sits beside.

What these goals buy is bounded on :doc:`guarantee-boundary`: a clean case says
that every marked span still holds the content it was affirmed against.

Context and boundaries
----------------------

Four things stand around the tool.

- **The operator.** A person who runs the command line, decides which edges
  to affirm and supplies the reason and role for each affirmation, chooses the
  scope of a package, and commits the results. The tool builds the capability
  to affirm and to generate; the operator is the authority that uses it.
- **The case.** A directory, ``case/``, that the affirmation store alone
  writes, and the independent commit lineage that a human commits it to
  (:doc:`case-store`). The store never runs git; the commit is a separate act
  by someone entitled to make it, and the working tree is the review surface
  between the two.
- **The source repositories.** Where requirements, code and test results
  live. The library never opens one. The command-line adapter reads them for
  exactly three purposes: discovering the revision a working tree is at,
  checking that the paths an endpoint's anchors name match their committed
  content, and recovering the bytes an anchor named at a past revision so a
  reviewer can see what a judgement bound. The adapter never writes to a
  repository.
- **The record producers.** Whatever turns sources into node and edge
  records. Today the only producer is the would-be store, a hand-transcribed
  fixture under ``tests/fixtures/``; the requirements reader is built as a
  library component but not yet composed into the command line, and the
  content extractor and the outcome extractor are named and documented but not
  yet written.

Outside the tool: any write to git, continuous integration, and storage of
content of any kind. A pipeline that wants to run the tool runs the command
line like any other operator.

Solution strategy
-----------------

The decisions that carry the rest, in the order they build on each other:

- A **content hash** is a SHA-256 over canonical bytes. A **node hash** folds a
  node's kind and its named content hashes; an **edge hash** folds the
  endpoints, the kind and both node hashes; a **design root** folds the
  sorted node hashes and the sorted edge tuples (source, target, kind) under
  caller-supplied metadata into one flat seal, so edge hashes never enter the
  root. A leaf layer, the commitment layer, owns all three derivations, and
  each is written under its own domain tag so that one can never be read as
  another.
- Records arrive in **two streams**: the *recorded* one, which is what the case
  holds, and the *current* one, which a producer derives from today's content.
  **Drift is derived by comparing them**, never stored.
- An **affirmation is a recorded judgement**, bound to the hashes of both
  endpoints and to the source revision each stood at when the judgement was
  made. It is composed by one component and persisted by another.
- **Gates refuse rather than warn.** A blocked scope yields a report and no
  package; nothing is built in memory and nothing is opened on disk for it.
- The **adapter reads repositories and the library receives values.** Below the
  command line, revisions and content are arguments; no component learns where
  they came from.
- **Requirements lead code, and the code points back.** Implementation carries
  ``:implements:`` markers and tests carry ``:verifies:`` markers naming the
  requirement they realize, so the tool's own source can later be a producer's
  input for its own graph.

Building blocks
---------------

The engine is a library of sixteen components under ``src/affirmatrix`` and a
thin command line over them. The component names are the subjects that
requirement text quotes; the packages are where the code lives (the mapping is
fixed in ADR-0004). Each component's own page, where it has one, carries the
detail.

.. list-table::
   :header-rows: 1
   :widths: 24 24 52

   * - Component
     - Package
     - Responsibility
   * - taxonomy provider
     - ``taxonomy``
     - The one built-in vocabulary: node kinds, edge kinds, which edges
       propagate suspicion, which content hashes each kind carries.
   * - record source
     - ``records``
     - The input protocol, and the frozen record types the engine exchanges
       and the case persists.
   * - store loader
     - ``sources.store``
     - Reads the would-be store as a record source; the only producer today.
   * - requirements reader, content extractor, outcome extractor
     - ``sources.reqs``, ``sources.content``, ``sources.outcomes``
     - The requirements reader is built; the two extractors are named
       producers for the next iteration and docstring-only today.
   * - commitment layer
     - ``commitment``
     - Node hash, edge hash and design root as pure primitives.
   * - graph builder
     - ``graph``
     - Records to the in-memory graph; refuses what would make it unsound.
   * - satisfaction evaluator
     - ``satisfaction``
     - Requirement coverage by transitive closure, as a pure predicate.
       See :doc:`package-gate` for how the gate consumes it.
   * - suspect detector
     - ``drift``
     - Derives each edge's state from the recorded and current streams.
       See :doc:`drift-derivation`.
   * - affirmation recorder
     - ``affirmation``
     - Composes the review event and the affirmed edge record. See
       :doc:`affirmation-recorder`.
   * - gate evaluator
     - ``gates``
     - Judges a scope and reports it ready or blocked. See
       :doc:`package-gate`.
   * - proof generator
     - ``proof``
     - Collects a scope, assembles the four documents, seals the package. See
       :doc:`proof-scope` and :doc:`proof-package`.
   * - affirmation store
     - ``case``
     - The only writer and validator of persisted records; also the recorded
       stream's read face. See :doc:`affirmation-store-write-face` and
       :doc:`affirmation-store-read-face`.
   * - configuration loader
     - ``config``
     - Source topology and role vocabulary from one YAML file.
   * - command-line interface
     - ``cli``
     - Eleven commands over four nouns; renders outcomes, decides none. See
       :doc:`command-line-interface`.

Three modules are shared internals, not components, and never a requirement's
subject: ``_hashing`` (the byte framing and the content hash), ``identity``
(minting absolute identifiers) and ``diagnostics`` (the severity model and the
record a finding travels in).

The layering is a property the test suite enforces, not a convention. The
developer test ``tests/unit/test_import_layering.py`` parses the source tree
and compares every component's imports with an allow-list. It holds these
things:

- ``commitment`` is a leaf. It imports ``_hashing`` and nothing else in the
  engine, so its independence from configuration, identity and the graph is
  checkable rather than promised.
- ``_hashing`` is the only module that imports the hash library.
- ``cli/_repository.py`` is the only module that imports ``subprocess``, so the
  three repository reads are the only place git is run.
- The record sources and the affirmation store sit below the graph and never
  import it; the store also never imports ``proof`` or ``affirmation``, which
  depend on it instead.
- ``identity`` is never reachable from ``commitment``, directly or through
  another module, which keeps the revisable identifier base out of every hash
  preimage.
- Nothing imports ``cli``.

Above those rules the direction runs upward: ``_hashing`` and
``commitment``; the shared lower layers; the sources and the store; the graph;
satisfaction and drift; gates, proof and affirmation; the command line last.

Runtime
-------

Each workflow is a short sequence of commands, each command a thin call into
the components above. The tutorials walk every one of them against this
repository's own records; the sequences here only name the parts.

**Consistency and drift.** ``case init`` lays the store's layout and schemas
into a case. ``case sync`` reads the current stream from the producer, derives
edge states against the recorded stream and writes the result back through the
affirmation store. ``graph check`` builds the graph and reports whether it is
well formed; ``graph status`` derives every edge's state and names the
suspect ones. Walked through in :doc:`../../tutorials/build-the-graph` and
:doc:`../../tutorials/detect-drift`.

**Affirmation.** ``edge show`` compares an edge's endpoints with what its
affirming review event recorded, hash by hash. ``edge affirm`` resolves the
judgement's inputs (role, reason, and each endpoint's revision, either given
or discovered and checked), has the recorder compose the review event and the
affirmed edge record, and has the store persist both. Walked through in
:doc:`../../tutorials/affirm-an-edge`.

**Evidence package.** ``proof check`` collects a scope and asks the gate
whether it is ready, changing nothing. ``proof generate`` does the same, and
only if the scope is not blocked builds the four documents and writes them
under a snapshot directory in the case. A blocked scope is refused before any
document exists. Walked through in :doc:`../../tutorials/seal-and-prove`;
:doc:`../../tutorials/verify-a-proof` then takes the package to the reader's
side of the table and recomputes the root without the tool.

The exit statuses and configuration keys are on :doc:`command-line-interface`.

Crosscutting concepts
---------------------

**Identifiers.** A node's identifier inside the engine is case-local and
stable: the requirement's own identifier, a definition's dotted path, a test
outcome's run and specification identifiers joined by a slash. That string
enters every hash preimage. Absolute IRIs are minted only when a record is
serialized, by ``identity``, and are read back to case-local form when a record
is read. A record therefore cannot disagree with its own hash about what it
identifies, and the identifier base can change without moving a hash
(ADR-0007).

**Canonical bytes and domain separation.** A content hash is over the bytes of
the content in its canonical form, exactly as stored, with no normalization.
Every derived hash is over length-prefixed fields under a domain tag that leads
the preimage: one tag each for a node, an edge and a root, versioned so that a
future change mints new tags rather than changing what the old ones mean.
Content hashes are deliberately untagged, so an auditor can reproduce any of
them with a standard tool (ADR-0005). The spellings of node kinds and
content-hash names are part of the preimage, which is why renaming one is a
migration.

**Exit statuses.** Three values, and no others: 0 is the command's positive
verdict; 1 is its negative verdict, acted on; 2 is that the command could not
judge the request at all. One function funnels every command's final decision,
so the vocabulary cannot grow by accident.

**Refusal versus error.** Every exception the engine defines is named
``…Error`` for what cannot be done: ``GraphError``, ``DriftError``,
``ScopeError``, ``ConfigError``, ``StoreError``, ``AffirmationError``,
``AffirmationStoreError`` and their like. They mean an input could not be made
sense of. The one exception that carries no suffix, ``GenerationRefused``,
means something different: the gate judged a scope blocked, and refusing is the
correct outcome. It is a verdict acted on, not a malfunction, so it carries the
gate's report as data rather than as a message, and it shares no base with the
errors beyond ``Exception``. A reader who catches ``…Error`` catches a problem
with the request; a reader who catches ``GenerationRefused`` catches an answer.

**Where closed sets live.** A gate's set of conditions is declared beside the
gate: the package gate's seven conditions are an enumeration in ``gates``, and
every diagnostic it reports names a member of it, never an occurrence-specific
sentence. What varies between occurrences travels in a separate detail field.
The shared ``diagnostics`` module holds only vocabulary with no component's
conditions in it, the severity model and the shape of a finding. Declaring a
gate's set there would turn a shared internal into a requirement's subject.

**Package layout.** A component with more than one concern presents one public
face over private modules. ``proof/__init__.py`` names the public surface in
``__all__`` and its scope and package logic live in ``_scope.py`` and
``_package.py``; ``case`` keeps its layout, atomic-write, document, validation
and error code in underscore modules behind the ``AffirmationStore`` class;
``cli`` holds one private module per noun beside its shared outcome, selector,
judgement and repository modules. Callers import from the package, never from
the private modules, and a component with one concern stays a single module.

**Markers.** Source and tests point back at requirements with docstring
fields. An implementation carries ``:implements:`` for each requirement it
realizes; a test carries ``:verifies:`` for the requirement it demonstrates
and ``:test-id:`` for the specification it realizes. The two are separate in a
test because a specification's identity is stated, not derived from the test
function's name or file. Markers have no runtime behaviour. They live inside
the hashed docstring, so re-pointing one changes the content hash and trips
the edge it names.

**The docstring is the test specification.** A verification test's docstring
states the claim in prose and carries its markers, and that docstring is the
specification. The document under ``doc/test-specification/`` will be rendered
from the docstrings and is a placeholder today; it is never a second text to
keep in step. Developer tests under ``tests/unit/`` are a
different artifact: they drive the design and are not graph participants
(ADR-0006).

After iteration 0: state and known limits
-----------------------------------------

**What carries behaviour.** Every component in the table above except two:
the content extractor and the outcome extractor are docstring-only modules
under ``sources/`` that state what they will do. Of the
three gates the design names, only the package gate exists; the commit gate's
conditions are all extraction conditions and the release gate needs a sealed
package and a release to check.

**The would-be store is the only producer.** A case built today is built from a
transcription of this repository taken at one commit, not from the repository
as it stands. Its anchors name a path inside the fixture rather than a
configured repository, and every affirmation or generation over it therefore
takes an explicit revision.

**Limits to read carefully.**

- **Coverage is the marked span.** A change behind an unmarked helper moves no
  hash, and drift detection does not see it. The tests cover that gap without
  closing it. See :doc:`guarantee-boundary`.
- **One revision per endpoint per judgement.** A review event records a single
  source revision for each endpoint. An endpoint whose anchors name more than
  one repository has no single revision to discover, and one must be given.
- **A package binds its siblings by file name.** Only the design consistency
  proof is covered by the root; the evidence manifest names the other three
  documents without a digest, so editing one does not disturb the root.
- **A package carries no trace of who affirmed.** The root says which edges
  were sealed, not that anyone stood behind them; that record is the case's own
  commit history, which the package does not contain. For this reason there is
  no verification command yet, and :doc:`../../tutorials/verify-a-proof` shows
  the one check an outsider can make and the two they cannot.
- **A case's schema copy is seeded once.** The store writes the schemas into a
  fresh case and validates against that copy thereafter; it never writes over a
  schema the case already has; it is refreshed only on request, by ``case refresh``,
  which reports what differed, so replacing one is a deliberate act on the case.

**The swap ahead.** When the extractors replace the would-be store, the records
change in kind and the case must follow. Real spans replace the fixture's whole
content files, so every content hash moves; every node hash and edge hash
moves with them, so every affirmed edge goes suspect; and the operator
re-affirms each at the new revision. That is the designed behaviour and not a
defect: an affirmation was a judgement about specific content, and the content
is different. Test outcomes from real runs carry their own run identifiers, so
the transcribed outcomes do not move to new hashes; they vanish, and the new
ones stand in their place. An anchor's repository will name a configured
repository rather than a path, which removes the need for an explicit revision
wherever the configuration maps the name. Nothing else in the engine changes,
because the input seam is the one place this swap touches.

Where to go next
----------------

:doc:`iteration-0-backlog` lists the work items this iteration was cut into;
the decision records under :doc:`../decisions/index` state why the boundaries
are where they are.
