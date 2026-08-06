Installation
============

.. warning::

   **Parts of this page do not work yet.** Installing the package is real;
   the ``affirmatrix`` command is not — this tutorial series documents the
   target workflow, and the command-line interface is being designed at
   this surface before it is built.

The tutorials that follow tell one running story: affirmatrix proving
itself. You act as the maintainer of this very repository, building its
safety evidence graph out of its own requirements, code, and tests —
affirming the edges, drifting the content, watching the suspicion, and
sealing a proof an outsider can check. Self-hosting is the project's
long-term goal, so the tool's own case is the honest first example.

Install the package
-------------------

.. code-block:: console

   $ git clone <repository-url> affirmatrix && cd affirmatrix
   $ python -m venv .venv
   $ .venv/bin/pip install -e .
   $ .venv/bin/affirmatrix --version
   affirmatrix 0.1.0

Nothing here needs a registry, a service, or a daemon. affirmatrix is a
command-line tool over files in git repositories — the heavyweight
machinery it relies on is machinery you already run.

Mount the case
--------------

The evidence graph — the *case* — is not part of the code branch. Its
persisted state is an independent commit lineage in the same repository
(see :doc:`../explanation/architecture/case-store`), so a fresh clone has
code but no evidence. Mount it:

.. code-block:: console

   $ git fetch origin case
   $ git worktree add case case

``case/`` now holds the store: node and edge records, review events,
proofs. Everything the tool writes lands here as plain files; everything
that makes those files *count* is a git commit you make yourself. That
division is the deepest rule in the design — the tool computes, a human
affirms — and you will feel it in every tutorial that follows.

Starting from nothing
---------------------

If you were adopting affirmatrix for your own project instead, there would
be no lineage to fetch. The bootstrap is deliberately git-native rather
than hidden behind the tool:

.. code-block:: console

   $ git switch --orphan case
   $ git commit --allow-empty -m "case: initialise the affirmation lineage"
   $ git switch main
   $ git worktree add case case

The tool never runs git (ADR-0008), so there is no ``affirmatrix init``
that would do this invisibly. What the tool *can* do is tell you what it
expects:

.. code-block:: console

   $ affirmatrix case doctor
   case/            worktree of branch 'case'   ok
   case/nodes/      empty                       ok (nothing recorded yet)
   case/edges/      empty                       ok
   case/events/     empty                       ok
   case/proofs/     empty                       ok
   affirmatrix.yaml not found — defaults in effect

.. admonition:: Decisions this page forces

   - The entry point is ``affirmatrix`` with ``<noun> <verb>`` commands;
     is a short alias wanted, and who decides it?
   - What does bare ``affirmatrix`` (no arguments) print?
   - Is ``case doctor`` the right shape for "explain what you expect and
     what you found", given that an ``init`` verb is ruled out by the
     no-git policy?
   - What belongs in ``affirmatrix.yaml``, and what are the defaults such
     that the tutorials never need to show one?

Next: :doc:`build-the-graph` extracts this repository's own records and
runs the first consistency check.
