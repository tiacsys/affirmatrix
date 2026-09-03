"""The proof generator — the evidence package.

Collects the scope, assembles the four documents (design consistency proof,
execution coverage record, coverage report, evidence manifest), and supplies
the snapshot metadata to the commitment layer's design-root primitive — it
holds no hashing logic of its own (ADR-0003).

Two invariants it must preserve, because composing cases across suppliers will
need them even though composition is out of scope here: the root is
recomputable from the package's own node manifest, so a package can be verified
without the graph that produced it (SEG-SYS-005), and every package publishes
its scope explicitly — including whether that scope covers every top-level
requirement in the graph or only some of them. A package that does not say how
much it covers invites being read as covering everything.

Scope expansion must be total — every transitive refiner of a requested
requirement (never an ancestor: a parent pulled in without the siblings
nobody requested would read as clean on a subtree nothing here checked), then
every specification and implementation that verifies or implements one of
those requirements, then every outcome confirming one of those
specifications, then every waiver excusing one of those outcomes. A missing
hop does not fail loudly; it silently narrows the scope, which is the more
dangerous outcome. :func:`~affirmatrix.proof.collect_scope` is this
expansion, together with the partial-vs-total signal and the snapshot
identifier a scope mints alongside it; see :mod:`affirmatrix.proof._scope`
for the full account, including what an evidence edge crossing the scope's
own cut reads as.

:func:`~affirmatrix.proof.assemble` judges a collected scope and builds the
four documents when it is not blocked; :func:`~affirmatrix.proof.persist`
writes a ready :class:`~affirmatrix.proof.Package` through the affirmation
store. See :mod:`affirmatrix.proof._package` for the full account, including
the package's own sealed root — a second, distinct call to
:func:`affirmatrix.commitment.design_root`, never to be confused with the
scope's own snapshot-identifier fingerprint.

**Refusal precedes writing (SEG-SYS-008).** Because writes land in place
(ADR-0008), the gate runs to completion first and no package file is opened for
a blocked scope — kept today by :func:`assemble` never building a document
body for one, ``persist`` refusing outright should it ever be asked to write
one anyway.

**Capability, not authority:** an operator runs generation; the engine does not
generate on its own.

Iteration-0 backlog items B16 (scope), B17 (the four documents), B18 (the
operator-facing refusal).
"""

from __future__ import annotations

from affirmatrix.proof._package import (
    COVERAGE_REPORT,
    DESIGN_CONSISTENCY_PROOF,
    EVIDENCE_MANIFEST,
    EXECUTION_COVERAGE_RECORD,
    Package,
    assemble,
    persist,
)
from affirmatrix.proof._scope import Scope, ScopeError, collect_scope

__all__ = [
    "COVERAGE_REPORT",
    "DESIGN_CONSISTENCY_PROOF",
    "EVIDENCE_MANIFEST",
    "EXECUTION_COVERAGE_RECORD",
    "Package",
    "Scope",
    "ScopeError",
    "assemble",
    "collect_scope",
    "persist",
]
