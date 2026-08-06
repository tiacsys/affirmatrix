Detecting drift
===============

.. warning::

   **This tutorial does not work yet.** The commands shown here document
   the target workflow; the command-line interface is being designed at
   this surface before it is built.

.. admonition:: Prerequisites

   - An affirmed graph (:doc:`affirm-an-edge`) — for this page, assume the
     bootstrap sweep covered everything: 84 edges active.

An affirmation binds a judgement to content *as it stood*. The moment the
content moves, the judgement is stale — and the point of this tool is that
staleness is detected, not remembered. Break your own graph and watch.

Move some content
-----------------

Edit the docstring of ``affirmatrix.graph.build`` — one word is enough.
The docstring is part of the function's marked span, so its bytes are part
of what every affirmation over this function committed to.

.. code-block:: console

   $ affirmatrix case status
   suspect edges (2):

   directlyOutdated (1)
     affirmatrix.graph.build -Implements-> SEG-SREQ-004
       apiHash moved: 41d0…9c2 → e83a…511   (affirmed 2026-08-06, maintainer)

   transitivelySuspect (1)
     SEG-SREQ-004 -Refines-> SEG-SYS-009
       inherits suspicion from the edge above

   active 82, pending 0
   exit 1 — the graph carries suspect edges

Read the two states apart, because they make different claims:

- **directlyOutdated** — recomputing the endpoint hashes no longer
  reproduces what the edge was affirmed against. The judgement pointed at
  bytes that are gone; someone must look again.
- **transitivelySuspect** — this edge's own endpoints are untouched, but
  it sits downstream of one that moved, along a relation whose kind
  propagates suspicion. Nobody claimed this edge is wrong; the graph
  refuses to let it stand as evidence while its foundation is in
  question.

Note what did *not* happen: no edge was deleted, no state was silently
repaired, and the 82 untouched edges are still active. Suspicion is
precise, not panicked.

Re-affirm
---------

If the edit was benign (a docstring typo does not change what the function
implements), the remedy is a fresh judgement over the new bytes:

.. code-block:: console

   $ affirmatrix edge affirm affirmatrix.graph.build Implements SEG-SREQ-004 \
       --role maintainer --comment "docstring wording only; behaviour unchanged"
   $ git -C case add -A && git -C case commit -m "affirm: re-bind after docstring edit"
   $ affirmatrix case status
   active 84, pending 0, suspect 0
   exit 0

The transitively suspect edge cleared itself. Derived suspicion is never
stored, only computed — once its cause is re-affirmed, there is nothing
left to derive it from. You never affirm a transitively suspect edge
directly; you cure the cause.

What status will not catch
--------------------------

Drift detection recomputes hashes over **marked spans**. A change to an
unmarked helper that a marked function calls moves nothing that is
hashed — the graph stays green while the behaviour behind a marked
surface has moved. A clean ``status`` therefore means *every marked span
still holds the content it was affirmed against*, and exactly that. The
boundary is stated in full in
:doc:`../explanation/architecture/guarantee-boundary`; the test suite,
ordinary engineering, covers the gap without closing it.

.. admonition:: Decisions this page forces

   - ``status`` output: grouped by state (shown here) or by scope? What
     does ``--verbose`` add — full hash pairs, affirmation history?
   - Exit codes as CI surface: ``0`` clean, ``1`` suspect edges present,
     ``2`` refusal — is ``status`` the command a pipeline gates on?
   - Hash rendering: truncated pairs with an arrow (shown here) — enough
     to act on, or noise to hide behind ``--verbose``?
   - Is there a ``case status --watch`` / machine-readable (``--json``)
     mode, and which of the two is the actual contract?
   - The six link states include ``doublyOutdated`` and ``broken``, not
     shown here — do they surface in the same listing, and what do their
     lines carry?

Next: :doc:`seal-and-prove` — turning a green graph into something you
can hand to someone who does not trust you.
