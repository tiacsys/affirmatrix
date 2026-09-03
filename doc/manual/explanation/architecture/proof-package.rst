The evidence package
=====================

The proof scope's page describes a value that is never written down; the
package gate's page describes a function that judges it. This page is where
the two meet a filesystem: :func:`affirmatrix.proof.assemble` turns a judged
scope into the four documents an evidence package is made of, and
:func:`affirmatrix.proof.persist` writes them into a case, sealed under the
scope's own snapshot directory.

Two steps, kept apart
------------------------

.. code-block:: python

   from datetime import UTC, date, datetime

   from affirmatrix import proof
   from affirmatrix.case import AffirmationStore

   package = proof.assemble(
       built,
       {"SEG-SREQ-014"},
       snapshot_timestamp=datetime.now(UTC),
       evaluation_date=date.today(),
       current_revision=current_repository_revision,
   )

   if package.documents is not None:
       written = proof.persist(package, AffirmationStore(root="case"))

``assemble`` is pure and total: it collects the scope, hands it to the
package gate, and — only when the gate's report is not blocked — builds the
four document bodies in memory as a :class:`~affirmatrix.proof.Package`. It
never writes a file, and it never raises for a blocked scope: a blocked
scope's package simply carries ``documents=None``. That is what makes
SEG-SREQ-046 ("no part of a package for a blocked scope") true by
construction rather than by a check that could be forgotten — no
``DesignConsistencyProof`` or ``EvidenceManifest`` body is ever built for a
blocked scope, not merely built and then discarded.

``persist`` is the one function that writes, through the affirmation store's
proof-document face. Called on a blocked package it raises a plain error and
writes nothing — a stated stopgap, not the operator-facing refusal a later
slice adds; keeping the write from happening is this module's whole
obligation, explaining it well is the next one's.

Two hashes, two purposes
----------------------------

Scope collection already calls :func:`affirmatrix.commitment.design_root`
once, with an explicit empty ``metadata``, to mint the scope's own snapshot
identifier — a content fingerprint taken before any package exists, folded
over the *whole* induced subgraph, evidence included. ``assemble`` calls the
same primitive a **second**, entirely distinct time, with real metadata, to
seal the design consistency proof — folded over the *design* subset of the
same scope alone. The two calls answer different questions over
overlapping but different inputs, and neither is derivable from the other:
a scope's evidence changing — a test re-run, a waiver newly granted — mints
a new snapshot identifier without touching the package's own root, because
the root's claim is only ever about the design.

The canonical metadata the package root is folded with is RFC 8785 canonical
JSON over exactly three fields:

* ``snapshotId`` — the scope's own minted identifier;
* ``scope`` — the requested requirement identifiers, sorted;
* ``revision`` — the current revision the caller judged the scope against.

All three are plain strings or arrays of them, which is what lets the
standard library's own JSON encoder stand in for RFC 8785 here — sorted
keys, compact separators, UTF-8 without escaping non-ASCII characters. That
substitution holds for object member ordering and for string, boolean and
array values; it does **not** hold for RFC 8785's number formatting, which
never applies today because no field in this payload is ever a number.

The design consistency proof: self-contained by construction
------------------------------------------------------------------

A design consistency proof carries exactly what an auditor needs to
recompute its own root without the graph that produced it (SEG-SYS-005):
the three metadata fields above, a node manifest of every in-scope design
node's own identifier, kind and hash, the in-scope design edges as
⟨from, to, kind⟩ triples, and the root itself. "Design" is Requirement,
TestSpecification and Implementation nodes and the Refines, Verifies and
Implements edges among them — a TestOutcome or a Waiver never appears in
the node manifest, and a Confirms, Witnesses or Excuses edge never appears
among the design edges. The proof is a claim
about what was designed and how it composes, answered independently of
whether it was ever run; execution coverage is the next document's claim,
never this one's.

The execution coverage record: fresh evidence, once told
----------------------------------------------------------

Every fresh in-scope ``TestOutcome`` — one the package gate's own judgement
did **not** report stale — appears here with its result, the revision it
ran against, and the specification it confirms. An outcome the gate reports
stale is silently absent, exactly as if it had never been recorded: the
coverage report is where staleness is named, once, and this document does
not repeat the telling. A non-passing outcome the coverage report reports
validly excused additionally carries its waiver's identifier and a *copy*
of the waiver's own expiry — a copy kept deliberately so a later release
check needs no graph walk. The waiver record itself remains the single
source of truth for that date; the copy can only ever agree with it or be
visibly stale itself.

The coverage report: the gate's own report, and nothing more
--------------------------------------------------------------

The coverage report document is :class:`~affirmatrix.gates.CoverageReport`
serialized whole: the seven typed findings, the diagnostics each one
becomes — with ``condition``, ``subject`` and ``detail`` kept apart exactly
as the gate keeps them — and whether the scope is blocked. Single-authored:
``assemble`` adds nothing beyond what the gate itself already found, and a
reader comparing this document against a fresh call to
:func:`affirmatrix.gates.package_gate` over the same inputs sees the same
answer restated, never a second opinion.

The evidence manifest: scope, totality, and the siblings it binds
------------------------------------------------------------------

The evidence manifest is the package's own binder: the requested scope and
the member scope the expansion actually collected, whether that scope is
total (SEG-SREQ-039), the current revision, and a relative filename
reference to each of the other three documents. Scope (SEG-SREQ-038) and
totality live here, on the package as a whole, rather than on the coverage
report — the coverage report's seven fields are exactly, and only, the
gate's own findings, and growing them to carry scope too would blur that.
The single ``revision`` is the one source revision a single-repository
layout has (ADR-0002), where a multi-repository layout would anchor one
per repository.

Persisting a package
------------------------

``persist`` writes the four documents through
:meth:`affirmatrix.case.AffirmationStore.write_proof_document`, one call
per document, under ``proofs/{snapshot_id}/`` — the layout
``case/_layout.py`` already named before this pass had documents to put
there. Each write validates against the case's own schemas exactly as every
other write does; the four schemas are seeded into a fresh case alongside
the record schemas already there. Generation changes nothing about the
graph it read or the store's node, edge and review-event streams — every
document lands under its own snapshot directory and nowhere else.

The read face
-----------------

:meth:`~affirmatrix.case.AffirmationStore.read_proof_document` reads one
document back, validated against the case's own schemas and refusing
rather than skipping — the same SEG-SREQ-053 discipline every other read
here keeps. :meth:`~affirmatrix.case.AffirmationStore.read_package` reads
all four of one snapshot at once, refusing the whole package if any one is
missing or invalid: a package short one document is not a smaller package,
it is not one. A case whose own ``schema/`` directory predates these four
kinds refuses to read them through the same "no schema declared for this
kind" path the write face already used while the four schemas did not
exist yet — writing to such a case seeds them on the next call; reading
never seeds anything.

What still waits
---------------------

The refusal this page's ``persist`` performs for a blocked package is a
plain error, not an operator-facing one: no attached report, no message
shaped for a human to act on. SEG-SREQ-046 is kept; SEG-SREQ-047 (a
refusal explained by the gate's own report) and SEG-SREQ-048 (only a
blocked scope is ever refused) wait for the slice that builds that type.
