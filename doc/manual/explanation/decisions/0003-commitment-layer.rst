0003. The commitment layer owns hash derivation as metadata-agnostic primitives
================================================================================

Status
------

Accepted, 2026-07-25.

Context
-------

The engine decomposition named a component for hash derivation only
descriptively ("the hashing/commitment layer"), and the design record was
of two minds about its boundary: the engine breakdown assigns node hash,
edge hash and the flat-sealed design root to that component, while the
proof-generation pipeline computes the design root as a step of generation,
folding in snapshot metadata there. The first requirement slice
(:need:`SEG-SREQ-002`/003/005) needed a settled subject.

Decision
--------

The component is named **the commitment layer**. It owns node-hash
derivation (from a node's content hashes), the two-sided edge hash, and
the flat-sealed design-root computation — all as
**metadata-agnostic primitives**. The proof generator *calls* the root
primitive and supplies the snapshot metadata at proof time. Approved
component vocabulary alongside it: the content extractor, the graph
builder, the requirements reader.

Consequences
------------

- :need:`SEG-SREQ-002`, -003, and -005 use "the commitment layer" as subject;
  :need:`SEG-SREQ-003` treats the metadata term as a caller-supplied opaque
  input, deferring its semantics to the proof slice.
- The proof generator holds no hashing logic of its own.
- The engine's module decomposition must reflect this boundary (design
  round, iteration 0).
