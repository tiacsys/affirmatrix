0008. Writes land in place; the tool never runs git
====================================================

Status
------

Accepted, 2026-07-25. Clarified by ADR-0010 (2026-09-16; reworded
2026-09-29) and ADR-0015: the "never runs git" clause was always about writes and about
keeping the library free of repository state. The command-line adapter's
three read-only repository operations, which that record names, are within
the clause, not an exception to it. Every other clause stands.

Context
-------

ADR-0004 named an unresolved tension and deliberately left it open. The
design record makes proof generation a pure computation that writes four
files to an ``--output-dir`` with no git operations, after which the
maintainer places them under ``proofs/{snapshotId}/`` and commits.
Affirmation pulls the other way: recording a ReviewEvent and setting an
edge active is naturally an edit to the working ``case/`` that the
maintainer then reviews and commits. Two workflows, two default
destinations, one component now owning both.

*The decision below was drafted as the coordinator's interpretation of the
maintainer's "no staging root" ruling and confirmed at ratification.*

Decision
--------

**All engine writes land in place in the working ``case/`` tree by
default** — ReviewEvents, updated edge records, and generated proof
packages alike. There is no staging root and no copy step.

**The tool never runs git.** No add, no commit, no branch, no
status-dependent behaviour, no reading of the index. The review surface is
the dirty working tree: the maintainer inspects it with ordinary git
tooling and commits. This is the same governance-plus-fingerprint posture
the design takes elsewhere — the commit, made by someone on the authorised
committer list, is the control, not a tool-enforced workflow.

**``--output-dir`` remains available** as an explicit override that
relocates the whole write root, for dry runs, comparisons and CI
inspection. It is the mechanism the design record and the command-line
reference describe; this ADR demotes it from default to option.

**The affirmation store is the only writer.** It owns the layout
(``nodes/``, ``edges/``, ``events/``, ``proofs/{snapshotId}/``), the file
naming, and schema validation on write. No other component opens a
file under the write root.

**Writes are atomic per file** — written to a temporary file in the same
directory and renamed into place — so an interrupted run never leaves a
half-written record that a later read-back would fail to validate.

**No implicit deletion.** The store never removes a record it did not write
in the current run. Retiring a node or an edge is an explicit operation.
With writes landing in place, a truncated input set must never be able to
silently prune the case.

Consequences
------------

- Affirmation and proof generation share one mental model, and the
  maintainer's review surface is ``git status`` / ``git diff`` for both.
- The design record's "no git side effects" is preserved **literally**: the
  engine runs no git. What this ADR changes is the default destination of
  the bytes, not the side-effect rule.
- The authority boundary is unaffected: the affirmation store provides the
  write capability; the maintainer operates it and decides what to commit.
  Nothing auto-affirms and nothing auto-commits.
- **Risk, named:** writing proofs in place means a failed or aborted
  generation can leave partial artifacts in a tracked directory. Two
  mitigations are load-bearing rather than optional — per-file atomicity
  above, and the :need:`SEG-SYS-008` refusal path must run the gate to completion
  and refuse **before any proof file is opened**, so a blocked scope
  produces no partial package at all. That couples this ADR to the refusal
  work item directly.
- Unblocks the affirmation store's write and read-back items.
