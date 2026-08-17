Architecture
============

arc42-shaped architecture documentation (introduction, context, solution
strategy, building blocks, crosscutting concepts) — to be populated as the
engine lands.

The engine's decomposition into components is ratified in the decision
records: ADR-0004 maps the component vocabulary onto packages under
``src/affirmatrix``, and the per-module docstrings name the component each
module realizes. The pages below cover what the tool guarantees and what is
currently in scope to build.

.. toctree::
   :maxdepth: 1

   guarantee-boundary
   case-store
   affirmation-store-write-face
   affirmation-store-read-face
   drift-derivation
   affirmation-recorder
   iteration-0-backlog
