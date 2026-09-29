"""The content extractor — Implementation and TestSpecification records.

Turns source into content hashes: one principle, two bindings. The parser only
*locates* a span; the hashed bytes are the verbatim bytes of the source file
(SEG-SREQ-001), never text a tool has normalized or reflowed. That rules out
hashing ``ast.get_docstring(clean=True)`` for Python, whose output normalizes
indentation, and Doxygen's own description text for C (SEG-SREQ-170). In both
bindings a node carries ``apiHash`` and ``bodyHash`` (an implementation) or
``specHash`` and ``implHash`` (a test specification), and the marker that
states an edge sits inside a hashed span, so re-pointing it changes the hash
and correctly trips the edge suspect.

**C, located by Doxygen.** Structure comes from the need exports, content from
the source (SEG-SREQ-152): an Implementation's or TestSpecification's identity
and edges are taken from the exports, verbatim, and never from the source
files (SEG-SREQ-153). The Doxygen XML then locates each node through the
member its symbol names (SEG-SREQ-159 to SEG-SREQ-162), and the extractor reads
the lines it names from the source file. Every span is a run of whole lines,
terminators included, so ``sed -n 'a,bp' <file> | sha256sum`` reproduces the
hash; where each span starts and ends, per construct and per hash, is fixed in
ADR-0011. A record's locator names the symbol (``symbol:<name>#api``,
``#body``, ``#spec``, ``#impl``), never a line.

**Python, located by ``ast``.** The docstring-field markers declare identity
and edges: ``:implements:`` on an implementation, ``:verifies:`` and
``:test-id:`` on a test. Both ``:implements:`` and ``:verifies:`` name a
requirement, so a ``Verifies`` edge runs from a test specification to the
requirement, never to another specification. A test carries ``:test-id:`` as
well, because implementation identity is the dotted path and needs no marker,
whereas a specification identity is manual and deliberately independent of the
test function's name and location, so for tests it has to be stated rather than
derived. Span boundaries are defined parser-independently, and the canonical
content form is the verbatim byte span.

Not yet built: this module is documentation only.
"""
