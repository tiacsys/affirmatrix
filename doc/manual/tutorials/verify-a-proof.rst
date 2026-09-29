Verifying a proof
=================

.. admonition:: Prerequisites

   - The package under ``case/proofs/<snapshot>/`` from :doc:`seal-and-prove`
     — four JSON documents, and nothing else but the library the tool is
     made of. That is the point.

Change seats. You are no longer the maintainer; you are an assessor at a
certification body, handed a directory of four JSON documents by a company
whose word you are professionally required not to take. What can you check
with only the package and the tool?

Today, one thing, and this page shows it working, shows it failing, and
then names what it cannot do. There is no verification command yet — no verb under ``proof`` for this.
What exists is the public library the generator itself is built from, and
a package designed so that the library can check one of its documents
without the graph that produced it (:doc:`../explanation/architecture/proof-package`).
The snapshot identifier below is the one from the run this page was made
with; yours differs in its timestamp, as on the last page.

Recompute the root
------------------

``design_consistency_proof.jsonld`` carries a ``root``, and everything
that root was sealed over: a hash for each of the fifteen design nodes,
the fourteen design edges as ``(from, to, kind)`` triples, and the three
metadata fields — ``snapshotId``, ``scope`` and ``revision``
(:need:`SEG-SREQ-037`). The commitment is public and deterministic
(:doc:`../explanation/decisions/0003-commitment-layer`), so a reader can
seal the same material again and compare. Save this as
``recompute_root.py``:

.. code-block:: python

   import json
   import sys
   from pathlib import Path

   from affirmatrix import commitment

   package = Path(sys.argv[1])
   proof = json.loads((package / "design_consistency_proof.jsonld").read_text())

   metadata = json.dumps(
       {"snapshotId": proof["snapshotId"], "scope": proof["scope"], "revision": proof["revision"]},
       sort_keys=True, separators=(",", ":"), ensure_ascii=False,
   ).encode("utf-8")
   node_hashes = [bytes.fromhex(node["hash"]) for node in proof["nodeManifest"]]
   edges = [(edge["from"], edge["to"], edge["kind"]) for edge in proof["designEdges"]]

   recomputed = commitment.design_root(metadata, node_hashes, edges).hex()
   print("root in the package:", proof["root"])
   print("root recomputed:    ", recomputed)
   matches = recomputed == proof["root"]
   print("match" if matches else "MISMATCH")
   sys.exit(0 if matches else 1)

The metadata is framed exactly as the generator framed it — sorted keys,
compact separators, UTF-8 — because the root is a hash over those bytes;
it is the recipe the repository's own ``samples/generate_package.py``
follows in its "auditor's check". Nothing in the script reads the graph,
the case or the other three documents. Run it over the package:

.. code-block:: console

   $ python recompute_root.py case/proofs/20260929T120940Z-0fbcfe027e43
   root in the package: c71e2a404a3b90d7c3d9b2922787ccd1f28c16cb99ce666a9b8a907a8d726346
   root recomputed:     c71e2a404a3b90d7c3d9b2922787ccd1f28c16cb99ce666a9b8a907a8d726346
   match
   $ echo $?
   0

The two digests are equal. The design the package describes — these
fifteen nodes, these fourteen edges, this scope at this revision — is the
design that was sealed, and you established it without asking the sealer
anything.

Tamper with it
--------------

Verification you cannot watch fail is theatre. Work on a copy, and change
one hexadecimal digit of one node hash in it:

.. code-block:: console

   $ cp -r case/proofs/20260929T120940Z-0fbcfe027e43 package-tampered
   $ sed -i '77s/"c37bd47b/"037bd47b/' package-tampered/design_consistency_proof.jsonld
   $ diff case/proofs/20260929T120940Z-0fbcfe027e43/design_consistency_proof.jsonld package-tampered/design_consistency_proof.jsonld
   77c77
   <       "hash": "c37bd47b3c56a5be57e91c9fe6aadb8d48e6508dbe0f56d3e30f5fcfbde05366",
   ---
   >       "hash": "037bd47b3c56a5be57e91c9fe6aadb8d48e6508dbe0f56d3e30f5fcfbde05366",
   $ python recompute_root.py package-tampered
   root in the package: c71e2a404a3b90d7c3d9b2922787ccd1f28c16cb99ce666a9b8a907a8d726346
   root recomputed:     9337b0a23b58bae2b9428f8d8c32034ceb37152e4155bc1332f720d85731cd6e
   MISMATCH
   $ echo $?
   1

One digit, and the recomputed root is a different value altogether. An
edited edge, a dropped node or a changed revision fails the same way.
Which side is lying is not the check's to guess — the sealer's root or the
document beside it — but that they disagree is mechanical, and no
assertion inside the package can talk its way around it. The copy is
scratch; delete it.

What the package does not let you check
---------------------------------------

The root covers one document. Two things the package claims sit outside
it, and they are known limits, not oversights.

**The other three documents are named, not bound.** The evidence manifest
refers to its siblings by file name and by nothing else:

.. code-block:: console

   $ grep -n Report case/proofs/20260929T120940Z-0fbcfe027e43/evidence_manifest.jsonld
   3:  "coverageReport": "coverage_report.jsonld",

There is no digest beside the name (:need:`SEG-SREQ-038` speaks of the
scope the manifest records, not of a binding). So a document that is not
the design consistency proof can be edited and the root will not notice.
Flip the coverage report's verdict in a second copy and run the same
check:

.. code-block:: console

   $ cp -r case/proofs/20260929T120940Z-0fbcfe027e43 package-sibling
   $ sed -i 's/"blocked": false/"blocked": true/' package-sibling/coverage_report.jsonld
   $ python recompute_root.py package-sibling
   root in the package: c71e2a404a3b90d7c3d9b2922787ccd1f28c16cb99ce666a9b8a907a8d726346
   root recomputed:     c71e2a404a3b90d7c3d9b2922787ccd1f28c16cb99ce666a9b8a907a8d726346
   match
   $ echo $?
   0

Still a match, because the edit touched a document the root does not
cover. The same goes for the execution coverage record: the outcomes and
the gate's report are exactly as trustworthy as the channel that carried
them, and no more.

**Nobody's affirmation is in the package.** The design root says the
fourteen edges are the ones that were sealed. It does not say anyone
stood behind them. The four documents carry no review event, no role, no
reason and no revision an affirmation was made at:

.. code-block:: console

   $ grep -c -i -e affirmed -e reason -e role -e review case/proofs/20260929T120940Z-0fbcfe027e43/*.jsonld
   case/proofs/20260929T120940Z-0fbcfe027e43/coverage_report.jsonld:0
   case/proofs/20260929T120940Z-0fbcfe027e43/design_consistency_proof.jsonld:0
   case/proofs/20260929T120940Z-0fbcfe027e43/evidence_manifest.jsonld:0
   case/proofs/20260929T120940Z-0fbcfe027e43/execution_coverage_record.jsonld:0

(The word ``affirmatrix`` does appear, in the names of the functions under
test; that is why the pattern says ``affirmed``.) Who reviewed which edge,
in which role, for what reason, is recorded in the case's own commit
history (:doc:`../explanation/decisions/0009-store-as-repository`), and
the package does not contain that history. An assessor handed the package
alone cannot establish it; they would need the case repository as well,
and today they would read its history by hand. This is the boundary
:doc:`../explanation/architecture/guarantee-boundary` draws — a design
stays hash-anchored, the standing-behind stays a human act on the record.

Both limits are why the command is not written yet: a verification verb
that printed "verified" over a package whose siblings can be swapped and
whose affirmations cannot be seen would say more than the package can
support. It waits until the package can carry more.

What the package does say for itself
------------------------------------

Within those limits, the package is candid about its own reach. Its
evidence manifest, shown on the last page, records the scope that was
requested and the scope actually collected (:need:`SEG-SREQ-038`), and
says whether that scope is total (:need:`SEG-SREQ-039`):

.. code-block:: console

   $ grep -n -A2 'requestedScope\|"total"' case/proofs/20260929T120940Z-0fbcfe027e43/evidence_manifest.jsonld
   27:  "requestedScope": [
   28-    "SEG-SYS-009"
   29-  ],
   --
   32:  "total": false

``"total": false`` and one requested requirement: a partial proof that
declares its partiality, so the claim you check is the claim it makes and
not a larger one. The revision it was sealed over is in the design
consistency proof, inside the root you recomputed, so it cannot be swapped
without the mismatch above. What you may conclude from a match is
therefore small and exact: this design, for this scope, at this revision,
is what was sealed.

This closes the story: content became records, records became a graph,
judgements bound the graph, drift was caught and cured, and a scope of it
was sealed into a package whose root an outsider can recompute — and
whose remaining claims are named as claims. That loop — measure, judge,
seal, verify what can be verified and say what cannot — is the whole tool.
