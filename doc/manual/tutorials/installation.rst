Installation
============

The tutorials that follow tell one running story: affirmatrix proving
itself. You act as the maintainer of this very repository, building its
safety evidence graph out of its own requirements, code, and tests —
affirming the edges, drifting the content, watching the suspicion, and
sealing a proof that is meant, eventually, to be checkable by an outsider.
Self-hosting is the project's long-term goal, so the tool's own case is
the honest first example.

Install the package
-------------------

.. code-block:: console

   $ git clone https://github.com/tiacsys/affirmatrix.git && cd affirmatrix
   $ python -m venv .venv
   $ .venv/bin/pip install -e .
   $ .venv/bin/affirmatrix --version
   affirmatrix 0.0.1.dev0

Nothing here needs a registry, a service, or a daemon. affirmatrix is a
command-line tool over files in git repositories — the heavyweight
machinery it relies on is machinery you already run.

Mount the case
--------------

The evidence graph — the *case* — is not part of the code branch. Its
persisted state is an independent commit lineage
(see :doc:`../explanation/architecture/case-store`), so a fresh clone has
code but no evidence. The published repository carries the code branch
only, so you start the lineage yourself and mount it:

.. code-block:: console

   $ git switch --orphan case
   $ git commit --allow-empty -m "case: initialise the affirmation lineage"
   $ git switch main
   $ git worktree add case case

``case/`` is where the store lives: node and edge records, review events,
proofs. Everything the tool writes lands here as plain files; everything
that makes those files *count* is a git commit you make yourself. That
division is the deepest rule in the design — the tool computes, a human
affirms — and you will feel it in every tutorial that follows.

Starting from nothing
---------------------

The same four commands start a case for your own project. The bootstrap
is deliberately git-native rather than hidden behind the tool.

The tool never runs git (ADR-0008, ADR-0009): there is no ``affirmatrix
init`` that would do this invisibly. What the tool does once a worktree
exists to write into is the subject of the next two sections.

The configuration file
----------------------

Every command below reads ``affirmatrix.yaml``. This repository already
commits one at its root:

.. code-block:: yaml

   case: ./case
   producer:
     root: ./tests/fixtures/would_be_store

It names the case — ``./case``, the worktree just mounted — and the
producer: the source the current stream is read from, the subject of
:doc:`build-the-graph`. Nothing it carries ever enters a hash; changing
the file changes what the tool reads, never what it proves (see
:doc:`../explanation/architecture/command-line-interface`).

Both paths are relative, and the values inside the file resolve against
the **directory that holds the file**, not against the working directory
(:need:`SEG-SREQ-135`). A bare ``affirmatrix`` still looks for
``./affirmatrix.yaml`` in the working directory, so every command shown
across these tutorials runs from the repository root, where the committed
file is found — and runs flag-free. From any other directory — from
inside ``case/``, where you will later go to commit, say — pass the file
with ``--config``: ``affirmatrix --config <repository>/affirmatrix.yaml
case check`` names the same case and the same producer from there.

case init
---------

With the worktree mounted but nothing laid into it yet, ask what the tool
finds there:

.. code-block:: console

   $ affirmatrix case check
   layout: (none)
   missing schemas: coverage_report.schema.json, design_consistency_proof.schema.json, edge-calls.schema.json, edge-confirms.schema.json, edge-excuses.schema.json, edge-implements.schema.json, edge-refines.schema.json, edge-verifies.schema.json, edge-witnesses.schema.json, evidence_manifest.schema.json, execution_coverage_record.schema.json, implementation.schema.json, requirement.schema.json, review_event.schema.json, test_outcome.schema.json, test_specification.schema.json, waiver.schema.json
   record counts: nodes 0, edges 0, review events 0
   configuration found: True
   producer readable: True
   $ echo $?
   1

No layout, every schema missing: nothing is there yet. ``case init`` lays
the store's layout and schema set into the mounted worktree, and nothing
else (:need:`SEG-SREQ-070`):

.. code-block:: console

   $ affirmatrix case init
   case initialized at case

It is idempotent — run it again over a case that already carries the
layout and schema set, and it changes neither, printing the same line.

case check
----------

Ask again:

.. code-block:: console

   $ affirmatrix case check
   layout: edges, events, nodes, proofs, schema
   missing schemas: (none)
   record counts: nodes 0, edges 0, review events 0
   configuration found: True
   producer readable: True
   $ echo $?
   0

``case check`` reports five judgements about the case, not one verdict
about its content: the layout it finds, its schema set — naming any
schema missing rather than supplying one — its record counts, whether a
configuration file was found or defaults are in effect, and whether the
configured producer is readable (:need:`SEG-SREQ-071`). It exits 0 only
while every declared schema is present and the producer is readable;
every other outcome is 1.

Commit the layout
-----------------

What ``case init`` laid down is a draft: the graph's real state is its
committed state, and nothing in ``case/`` has been committed yet. The first
store act commits it, made by you in the case's own lineage
(:doc:`../explanation/decisions/0009-store-as-repository`):

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

The message is yours; the tool neither drafts nor runs it.

Next: :doc:`build-the-graph` syncs this repository's own records into the
case and runs the first consistency check.
