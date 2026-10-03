Iteration-0 backlog
===================

Scope is whatever this backlog says — nothing more. There is no standing
"deferred features" list: anything not below is out of scope by definition, and
work that surfaces a gap becomes a note to the Requirements Engineer rather
than code.

Iteration 0 builds the engine core against the would-be store and closes when
its own pytest suite is green and the three workflows — consistency, proof
generation, suspect detection — run end to end on that store. "No proof" means
no *self*-proof: proof generation is built and exercised, the tool is simply
not yet the subject of its own graph.

Working rules
-------------

- **Requirements lead code.** Every item below names the requirement it
  realizes. An item whose requirement is still in decomposition cites its
  parent system requirement and waits for the leaf.
- **Test first**, per item, following the python-patterns skill.
- Implementation functions carry ``:implements:`` docstring-field markers as
  they are written; ``:verifies:`` markers wait for the Test Engineer's slice
  and are re-pointed together with it.
- Components are named exactly as the component map (ADR-0004) names them,
  because those names are the requirement subjects.

The items
---------

===  =========================================================  ======================  ======================
Id   Work item                                                  Component               Requirement
===  =========================================================  ======================  ======================
B0   Package skeleton, pytest wiring, import-direction lint     — (infrastructure)      —
B1   Canonical byte encoding and the SHA-256 primitive          — (shared internal)     ADR-0005
B2   Node-hash derivation                                       commitment layer        :need:`SEG-SREQ-005`
B3   Two-sided edge hash                                        commitment layer        :need:`SEG-SREQ-002`
B4   Flat-sealed design root, caller-supplied metadata          commitment layer        :need:`SEG-SREQ-003`
B5   Persisted vocabulary and the record-source protocol        record source           :need:`SEG-SYS-001`/007
B6   The built-in safety-evidence graph type                    taxonomy provider       :need:`SEG-SYS-009`
B7   Records to the in-memory graph                             graph builder           :need:`SEG-SYS-001`
B8   Refines cycles and self-loops as graph-level errors        graph builder           :need:`SEG-SREQ-004`
B9   The would-be store dataset and its loader                  store loader            — (scaffolding)
B10  Persist nodes, edges, events, proofs; validate on write    affirmation store       :need:`SEG-SYS-007`
B11  Read-back as a record source                               affirmation store       :need:`SEG-SYS-007`
B12  Satisfaction by transitive closure                         satisfaction evaluator  :need:`SEG-SYS-002` (batch A)
B13  Link state derived from current content                    suspect detector        :need:`SEG-SYS-003` (batch A)
B14  ReviewEvent with the affirmation anchor                    affirmation recorder    :need:`SEG-SYS-004`
B15  Gate 2, the proof gate, and its CoverageReport             gate evaluator          :need:`SEG-SYS-006`
B16  Scope collection and the partial-vs-total signal           proof generator         :need:`SEG-SYS-005`
B17  The four proof documents                                   proof generator         :need:`SEG-SYS-005`
B18  Refuse to generate for a blocked scope                     proof generator         :need:`SEG-SYS-008`
B19  Minimal CLI over the three workflows                       command-line interface  :need:`SEG-SYS-010`
B20  Iteration architecture note; requirement gaps raised       —                       —
===  =========================================================  ======================  ======================

Sequencing
----------

The order above is the dependency order. Three joins are worth stating
explicitly:

- **B1 gates everything.** The byte encoding is irreversible once a hash is
  affirmed, which is why ADR-0005 preceded any code.
- **B11 gates B13.** Drift detection compares two record streams — the
  *recorded* one from the affirmation store and the *current* one from a
  producer — so read-back must exist before suspicion can be derived.
- **An operator affirms between B14 and B15.** A faithfully bootstrapped store
  starts every edge pending, and a pending edge blocks a package, so the gate
  has nothing to show until someone has run a bulk affirmation at a
  checkpoint. The tool never affirms on its own behalf.

Deferred out of iteration 0
---------------------------

- **Record production** — the content extractor, the requirements reader, and
  the outcome extractor. Only the span-hashing primitive lands early. This is
  the first self-hosting slice: it replaces the would-be store and retires the
  manual translation.
- **The commit gate and the release gate.** The commit gate's conditions are
  all extraction conditions, and record production is deferred; the release
  gate needs a sealed package and a release to check.
- **Implementation node identity**, which blocks the self-hosting slice rather
  than this one.
- **Composing cases across suppliers** — contract vectors, exchange formats,
  selectively openable commitments, third-party attestation. Out of scope
  entirely. Two invariants still constrain what is built here, because
  retrofitting them later would be a rewrite: a package must be verifiable by
  recomputation from its own contents, and it must publish its scope.
- **A user-definable graph vocabulary and user-definable satisfaction rules.**
  This version fixes both. They stay behind single interfaces — the taxonomy
  provider and the satisfaction evaluator — so that making them definable
  later is a substitution rather than a rewrite.

Decisions this backlog rests on
-------------------------------

ADR-0002 (mono-repo and the federated document set), ADR-0003 (the commitment
layer owns hash derivation), ADR-0004 (the component map), ADR-0005 (hash
encoding and domain separation), ADR-0006 (test-tree ownership), ADR-0007
(identifiers), ADR-0008 (write policy), and ADR-0009 (the store as a sidecar
commit lineage, proposed).
