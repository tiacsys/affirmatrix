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

:func:`~affirmatrix.proof.check_readiness` collects a scope and judges it;
:func:`~affirmatrix.proof.assemble` composes that and builds the four
documents when the judgement is not blocked; :func:`~affirmatrix.proof.persist`
writes a :class:`~affirmatrix.proof.Package` through the affirmation store.
See :mod:`affirmatrix.proof._package` for the full account, including the
package's own sealed root — a second, distinct call to
:func:`affirmatrix.commitment.design_root`, never to be confused with the
scope's own snapshot-identifier fingerprint.

**Refusal precedes writing (SEG-SYS-008).** Because writes land in place
(ADR-0008), the gate runs to completion first: when it reports a scope
blocked, ``assemble`` raises :class:`~affirmatrix.proof.GenerationRefused` —
carrying the gate's own report as a typed attribute — before any document
body is built, so no package file is ever opened for one. A ``Package`` is
always complete; there is no partial one for ``persist`` to be asked to
write. Refusal and error are kept apart deliberately: a blocked scope is
refused, an input the generator cannot even judge (an absent requested
requirement, an ambiguous outcome) raises its own distinct type, and
neither is ever caught as the other.

**The verifier reads a package back.** :func:`~affirmatrix.proof.read_package`
reads the four documents of a package from any directory,
:func:`~affirmatrix.proof.summarize` states what they record, and
:func:`~affirmatrix.proof.verify` checks them. The verifier makes a fixed list
of named checks and reports each one as passed, failed, not judged or not made;
see :mod:`affirmatrix.proof._verify`. None of the three writes anything.

**Capability, not authority:** an operator runs generation; the engine does not
generate on its own.

Iteration-0 backlog items B16 (scope), B17 (the four documents), B18 (the
refusal).
"""

from __future__ import annotations

from affirmatrix.proof._package import (
    COVERAGE_REPORT,
    DESIGN_CONSISTENCY_PROOF,
    EVIDENCE_MANIFEST,
    EXECUTION_COVERAGE_RECORD,
    GenerationRefused,
    Package,
    assemble,
    check_readiness,
    coverage_report_document,
    persist,
)
from affirmatrix.proof._scope import Scope, ScopeError, collect_scope
from affirmatrix.proof._stored import (
    RequirementEntry,
    StoredPackage,
    Summary,
    read_package,
    summarize,
)
from affirmatrix.proof._verify import CHECK_NAMES, Check, CheckStatus, Verification, verify

__all__ = [
    "CHECK_NAMES",
    "COVERAGE_REPORT",
    "DESIGN_CONSISTENCY_PROOF",
    "EVIDENCE_MANIFEST",
    "EXECUTION_COVERAGE_RECORD",
    "Check",
    "CheckStatus",
    "GenerationRefused",
    "Package",
    "RequirementEntry",
    "Scope",
    "ScopeError",
    "StoredPackage",
    "Summary",
    "Verification",
    "assemble",
    "check_readiness",
    "collect_scope",
    "coverage_report_document",
    "persist",
    "read_package",
    "summarize",
    "verify",
]
