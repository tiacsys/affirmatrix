Test Specification
==================

Test specifications for the affirmatrix requirements (``SEG-TS-nnn``). The
``verifies`` links target needs imported from the requirement specification
(cross-document, via the registry).

Each specification is a pytest function's docstring under
``tests/specification/``: its first line is the title, the paragraph beneath
states the claim, and two docstring fields carry its identity and the
requirement it verifies. Until the rendering step lands in ``python -m doc``,
this document is a placeholder that establishes the document's place in the
federation.
