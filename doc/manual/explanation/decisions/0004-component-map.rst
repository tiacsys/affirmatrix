0004. Engine component map and package decomposition
=====================================================

Status
------

Accepted, 2026-07-25. Amended 2026-09-29, as built:

- The requirements reader is built (``sources.reqs``).
- The content extractor carries two bindings of one principle -- Python
  located by ``ast``, and C located by Doxygen (ADR-0011) -- under the one
  module ``sources.content``. The outcome extractor reads run artifacts of more
  than one format, a pytest run and a twister run, under the one module
  ``sources.outcomes``. A binding or a format is not a component: neither gets
  a row in the table, and requirement text names the content extractor and the
  outcome extractor, never "the C extractor" or "the twister reader".
- The store loader retires when the extractors serve this repository's own
  case. The table and every other boundary below stand.

Context
-------

ADR-0003 settled one component boundary (the commitment layer) and left the
rest of the decomposition to the design round. Two things now depend on it.
First, the requirements layering criterion ratified 2026-07-25 makes a
software requirement's subject *a distinct component identified by the
software architecture* — so SREQ decomposition cannot proceed until the
component set exists and is named. Second, the SWE brief instructs the
engine to be scaffolded as ``affirmatrix.core``, which was never decided as
a namespace.

The names chosen here are consumed verbatim as requirement subjects ("the
graph builder shall …"), so they must read as EARS subjects, not as
programming-language artifacts. Interfaces are legitimate subjects
alongside concrete components.

Five **seams** shape the decomposition — the places where the design
expects variation and the engine must not hard-wire it: the **taxonomy**
(node and edge kinds, which of them propagate suspicion, which content
hashes each kind carries), **satisfaction** (the predicate that decides
whether a requirement is discharged), **input** (one interface through
which records arrive, whatever produced them), the **library/interface
split** (the engine is a library; the command line is a thin layer over
it), and **topology** (where content lives, read from configuration rather
than compiled in). Three further constraints are fixed rather than
variable: the graph stores only hashes, every emitted record validates
against its schema, and a package must be verifiable by recomputation from
its own contents while publishing the scope it covers.

Contract composition, SPDX exchange, and a configurable graph-type model
are out of scope for the first version entirely and get no reserved
structure.

Persistence is a first-class part of this map, not an output detail: the
engine's graph data — node and edge hash records, review events, sealed
proofs — is where the graph itself lives, and its blackbox claim is
SEG-SYS-007.

Decision
--------

**No ``core`` namespace.** ``affirmatrix.core`` was only ever shorthand for
"the engine modules", never a decided package level, and is rejected as
one. A ``core`` that contains every component except the CLI distinguishes
nothing; the library/interface split is already carried by
``affirmatrix.cli`` versus its siblings. "Core" is also not a component
name — "the core shall …" is
not a requirement subject — and admitting it as a path segment invites it
into requirement text. Components are therefore direct children of
``affirmatrix``.

**Component map.** Each row is a component: a nameable subject for
requirements, owning one module or package. "It." marks the iteration in
which the module first carries behaviour.

=============================  =================================  =====================  ===
Component                      Module                             Seam                   It.
=============================  =================================  =====================  ===
the taxonomy provider          ``affirmatrix.taxonomy``           taxonomy               0
the record source              ``affirmatrix.records``            input                  0
the store loader               ``affirmatrix.sources.store``      input adapter          0
the requirements reader        ``affirmatrix.sources.reqs``       input adapter          1
the content extractor          ``affirmatrix.sources.content``    input adapter          1
the outcome extractor          ``affirmatrix.sources.outcomes``   input adapter          1
the commitment layer           ``affirmatrix.commitment``         —                      0
the graph builder              ``affirmatrix.graph``              —                      0
the satisfaction evaluator     ``affirmatrix.satisfaction``       satisfaction           0
the suspect detector           ``affirmatrix.drift``              —                      0
the affirmation recorder       ``affirmatrix.affirmation``        —                      0
the gate evaluator             ``affirmatrix.gates``              —                      0
the proof generator            ``affirmatrix.proof``              verifiable packages    0
the affirmation store          ``affirmatrix.case``               input, hashes, schema  0
the configuration loader       ``affirmatrix.config``             topology               0
the command-line interface     ``affirmatrix.cli``                thin interface         0
=============================  =================================  =====================  ===

Module names denote the *domain artifact* a package owns; component names
denote the *actor* that acts on it. The map therefore does not require the
two to be spelled identically — as with ``drift`` / the suspect detector
and ``records`` / the record source, ``affirmatrix.case`` is retained for
the affirmation store because it maps one word to the ``case/`` directory
it is the sole writer of.

**Shared internals — not components, never requirement subjects:**
``affirmatrix._hashing`` (SHA-256 and the canonical byte encoding both the
commitment layer and the extractors depend on), ``affirmatrix.identity``
(IRI minting), ``affirmatrix.diagnostics`` (the Error/Warning/Info severity
model of the error-handling contract). They are implementation detail
shared by components; requirements about their behaviour attach to the
component that calls them.

**Boundaries that the map asserts.**

- **The record source is a role, not a component instance.** It is the
  input interface and a requirement subject in its own right; its adapters
  are the store loader, the requirements reader, the content extractor, the
  outcome extractor, and the read face of the affirmation store. The store
  loader is iteration 0's content adapter; the three extraction adapters
  arrive in the self-hosting slice. ``sources/`` is the only package that
  changes in that swap, which is how the input seam is demonstrated rather
  than asserted.
- **The affirmation store owns persisted graph data, both directions.** It
  reads and writes the node and edge hash records, the ReviewEvents, and
  the sealed proof documents that constitute the case. It is the only
  component that touches persisted graph artifacts, and the single point at
  which schema validation is applied — on write and on read-back. It stores
  hashes and references only; content never reaches it (SEG-SREQ-018).
- **The affirmation store presents its read face AS a record source.**
  Persisted edge records carrying stored ``edgeHash`` and ``linkState``
  enter the engine through the record-source protocol, not through a private
  interface. Drift detection is then symmetric by construction: two record
  sources in — one *recorded* (the affirmation store), one *current* (the
  extraction adapters, or the store loader in iteration 0) — and one
  derived link state out. The graph builder never learns whether a hash
  came from disk or from source, and both streams are faked identically in
  tests. Its write face is exclusive: no other component has one.
- **Content hashing is not the commitment layer's.** Producers emit content
  hashes; the commitment layer folds content hashes into node hashes, edge
  hashes and the design root. SEG-SREQ-001's subject (the content
  extractor) and SEG-SREQ-005's subject (the commitment layer) therefore
  sit on opposite sides of the record-source boundary, as the ratified
  slice already reads.
- **The commitment layer is a leaf.** It imports only ``_hashing`` and
  nothing else in the engine — no graph, no records, no config, no clock,
  no I/O. This makes ADR-0003's metadata-agnostic ruling mechanically
  checkable (an import rule), not merely a convention.
- **The graph builder assembles; the suspect detector derives.** The graph
  builder turns records into the in-memory graph and enforces ``refines``
  acyclicity (SEG-SREQ-004), carrying each edge's recorded link state. The
  suspect detector recomputes edge hashes, compares against the recorded
  stream, and derives the current state including transitive suspicion,
  which clears by recomputation rather than by a second affirmation. No
  component computes link state twice.
- **``records`` is the persisted vocabulary.** Because the affirmation
  store must serialize ReviewEvents and the four proof documents without
  importing the components that compute them, the record *types* — node
  records, edge records, review events, proof documents — are declared in
  ``affirmatrix.records``, while ``proof`` and ``affirmation`` hold only
  the computations that produce them.
- **Two stores, never one word.** The iteration-0 fixture is *the would-be
  store* (holds content, deliberately not schema-validated); the persisted
  graph under ``case/`` is *the affirmation store* (holds hashes and
  references). Requirement text uses the qualified term, never bare
  "store". The interim term "case store" is retired.

**Dependency direction** is strictly layered, no cycles: ``_hashing`` →
``commitment``; ``{records, taxonomy, identity, diagnostics, config}`` are
shared lower layers; ``sources.*`` and ``case`` depend on those but never
on ``graph``; ``graph`` → ``{satisfaction, drift}`` →
``{gates, proof, affirmation}`` → ``cli``. The affirmation store's
two-faced role does not invert this: because it exchanges only record types
declared in ``records``, ``case`` never imports ``proof`` or
``affirmation``, and those components depend on ``case`` rather than the
reverse. Persistence therefore stays in the low layer that ``graph``
consumes, and the layering remains acyclic.

Consequences
------------

- Every software requirement's subject is exactly one component name from
  the table. Renaming a module is therefore an ADR amendment, not a
  refactor — requirement text quotes these names.
- ``core`` appears in no import path and no requirement.
- Three components (requirements reader, content extractor, outcome
  extractor) are named now but implemented in the self-hosting slice; their
  SREQs wait for that iteration. Only the content extractor's span-hashing
  primitive lands in iteration 0.
- The record-source protocol carries two distinct roles (recorded, current), so
  its requirements must state the role, not merely the interface.
- The iteration-0 CLI is minimal — enough to drive the three workflows for
  the definition of done — and holds no logic.
- No package is reserved for composition, SPDX export, or the graph-type
  meta-model. The verifiability invariants constrain ``proof`` (root
  recomputable from the node manifest, scope published explicitly) and
  ``satisfaction`` (extensible with a discharge case for evidence proved
  elsewhere) without any structure of their own.
- **Persistence versus the no-side-effects rule — an unresolved tension,
  stated not smoothed.** The design record makes
  proof generation a pure computation that writes four files to an
  ``--output-dir`` with no git operations, after which the maintainer places them
  under ``proofs/{snapshotId}/`` and commits. Elevating persistence to a
  component keeps that rule intact only under two conditions: the
  affirmation store owns serialization, schema validation and layout but
  never version control (it runs no git and makes no commit), and its root
  path is always a caller parameter rather than a hardcoded ``case/``. Two
  workflows then pull in different directions: proof generation naturally
  writes to a scratch root the maintainer then places, whereas affirmation —
  recording a ReviewEvent and setting an edge active — naturally mutates
  the working ``case/`` in place before the maintainer commits. Whether those keep
  different default roots, or whether every write goes to a staging root,
  is not decided here; it is a sub-question of the pending write-policy
  item.
- The authority boundary is unaffected: the affirmation store provides the
  write capability; the maintainer operates it. Neither the store nor the recorder
  affirms on its own.
- **Naming adjacency to watch:** "the affirmation recorder" (builds a
  ReviewEvent) and "the affirmation store" (persists it) will appear in
  adjacent requirement sentences. If that proves ambiguous in EARS text,
  the recorder is the one to rename — "the review recorder" is the obvious
  candidate — since the store's name is ratified.
