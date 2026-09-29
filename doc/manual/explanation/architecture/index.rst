Architecture
============

The overview is the page to read first: an arc42-shaped account of what the
tool is for, what stands around it, how it is decomposed, what holds across
every component, and what iteration 0 leaves as known limits. The pages after
it cover single components, what the tool guarantees, and what is currently in
scope to build.

The engine's decomposition into components is recorded in the decision
records: ADR-0004 maps the component vocabulary onto packages under
``src/affirmatrix``, and the per-module docstrings name the component each
module realizes.

.. toctree::
   :maxdepth: 1

   overview
   guarantee-boundary
   case-store
   requirements-reader
   affirmation-store-write-face
   affirmation-store-read-face
   drift-derivation
   affirmation-recorder
   package-gate
   proof-scope
   proof-package
   command-line-interface
   iteration-0-backlog
