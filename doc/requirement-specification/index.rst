Requirement Specification
=========================

The affirmatrix requirement specification — the first half of the repo's own
safety evidence graph (the dogfood case). IDs follow the SEG conventions:
``SEG-SYS-nnn`` (system), ``SEG-SREQ-nnn`` (software).

The system requirements are collected on one page. The software requirements
are grouped by the component that owns them, so each page reads as the
contract for one part of the engine. A requirement's page is decided by its
subject, not by its parent, so refinement links cross pages freely.

.. toctree::
   :maxdepth: 1

   system-requirements
   taxonomy-provider
   record-source
   requirements-reader
   content-extractor
   outcome-extractor
   commitment-layer
   graph-builder
   satisfaction-evaluator
   suspect-detector
   affirmation-recorder
   affirmation-store
   gate-evaluator
   proof-generator
   proof-verifier
   command-line-interface
   configuration-loader
   retired-identifiers
