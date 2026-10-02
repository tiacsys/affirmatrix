The content extractor
=====================

The engine consumes records; the code and the tests they cover are C files in
another repository. :class:`affirmatrix.sources.content.CSourceExtractor` sits
between the two: from the need exports, the Doxygen output and the source files
it supplies one Implementation or TestSpecification record per need, each with
two content hashes, and one edge per declared link. It is a library component;
the command line does not yet compose it with the other producers. The Python
binding of the same principle is not built (see the last section).

What it reads
-------------

.. code-block:: python

   extractor = CSourceExtractor(
       Path("checkout"),
       repository="toolbox",
       implementations=config.ImplementationInputs(
           export=Path("needs/api-traceability/needs.json"),
           doxygen=Path("xml/dox-safe-data-api"),
       ),
       specifications=config.SpecificationInputs(
           export=Path("needs/test-specification/needs.json"),
           doxygen=Path("xml/dox-safe-data-testspec"),
       ),
   )

Three kinds of input, each for one purpose:

* the **need exports** give the structure: which nodes exist, their identity
  and their links (SEG-SREQ-153). Every need in the implementation export is an
  Implementation and every need in the test-case export a TestSpecification;
  no need type is configured for them. The symbol a need names is its ``title``
  on an implementation need and its ``test_function`` on a test-case need;
* the **Doxygen output** gives the location: the file and the lines of a
  symbol's declaration and body. Only names, kinds and ``<location>``
  attributes are read from it; none of its text reaches a hash (SEG-SREQ-170);
* the **source files** under ``root`` give the bytes that are hashed.

``repository`` is the configured name of the repository the files belong to,
never a path (SEG-SREQ-134). A stream set to ``None`` supplies nothing, and
with both ``None`` the extractor supplies nothing at all.

What it supplies
----------------

Each node is identified by its need identifier, verbatim (SEG-SREQ-154,
SEG-SREQ-155; ADR-0007): a renamed symbol does not rename the node. Each link in
``satisfies`` becomes an Implements edge from the implementation to the
requirement, each link in ``verifies`` a Verifies edge from the test
specification to the requirement, in the pending state (SEG-SREQ-156,
SEG-SREQ-157). Edges need neither the Doxygen output nor a source file. On
the toolbox evidence fixture that is 12 Implementations, 19 TestSpecifications
and 16 + 24 edges.

Finding the lines
-----------------

Each Doxygen tree is read once, when the extractor is built. Its members are
indexed by name, each tree separately, so an implementation's symbol is never
looked up in the test tree. A node is located through the one member whose name
is its symbol (SEG-SREQ-160). "One" means one distinct definition: a member
listed in two compounds with the same ``id`` and location counts once, but two
``id`` values, or one ``id`` at two locations, are two, and a symbol with none
or with several is an error for its node (SEG-SREQ-161). Members no need names
are never consulted, which is why the test tree's duplicate
``SAFE_CONTAINER_DEFINE`` costs nothing. The index of Doxygen's own listing is
not followed: it lists members repeatedly and gives no location.

Before a file is opened, every path the node's location names is resolved under
``root`` (links included) and must stay inside it; ``..``, an absolute path and
a link that leads out are errors, and the file outside is not read
(SEG-SREQ-162). Then the line each location names must contain the symbol as a
whole identifier: ``line`` and ``declline`` in the declaration file, and
``bodystart`` in the body file, never ``bodyend`` (SEG-SREQ-175). A location
that Doxygen left stale, pointing at another function's lines, is refused
instead of hashed.

The four hashes
---------------

A hash is the SHA-256 of a run of whole lines of one source file, each with its
terminator (SEG-SREQ-168); nothing is trimmed, so a CR before the line feed is
content. ADR-0011 fixes where each run starts and ends:

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Node and hash
     - First line
     - Last line
   * - Implementation, ``apiHash``, function declared in a header
     - the opener of the comment above the declaration
     - the line of the first ``;`` at parenthesis depth zero
   * - Implementation, ``apiHash``, function defined where it is declared
     - the opener of the comment above the definition
     - the line before the one that opens the body with ``{``
   * - Implementation, ``apiHash``, macro
     - the opener of the comment above the ``#define``
     - the ``#define`` line
   * - Implementation, ``bodyHash``
     - ``bodystart``
     - ``bodyend``
   * - TestSpecification, ``specHash``
     - the opener of the comment above the test
     - the closer of that comment
   * - TestSpecification, ``implHash``
     - ``bodystart``
     - ``bodyend``

The documentation comment is found from the line above the declaration,
stepping over ``#if``, ``#ifdef`` and ``#ifndef`` lines only. The next line
must end the comment with ``*/``, and its opener must be ``/**`` or ``/*!``. A
blank line, a plain comment or code there means the node has no documentation
comment, an error and never an empty hash (SEG-SREQ-169). A guard line between
the comment and the declaration lies inside the span; one above the comment lies
outside. When the end of a declaration is sought, text in comments is skipped,
and a ``{`` at parenthesis depth zero before the ``;``, an unbalanced ``)`` or
no ``;`` at all is an error: such a declaration is not one this rule can end. A
body that Doxygen records as ending at ``-1`` has no lines and is an error too.

Anyone can reproduce a hash without the tool:

.. code-block:: sh

   sed -n '247,263p' include/safe_data/safe_data.h | sha256sum

prints the ``apiHash`` of ``safe_data_init``,
``dcfd58ce00f23973afff2aa76f3b11cc422aad373981488c22b1745eb325ba9c``: the
comment opens at line 247 and the semicolon that ends the declaration is on
line 263.

The anchors
-----------

Each hash is supplied with an anchor of three parts, naming where its bytes
came from: the configured repository name; the file as Doxygen names it, which
for an ``apiHash`` is the declaration file and for a ``bodyHash`` or
``implHash`` the body file; and the locator ``symbol:<name>#api``, ``#body``,
``#spec`` or ``#impl`` (SEG-SREQ-171 to SEG-SREQ-174). No line number is
recorded, so moving a function within its file changes no anchor.

Errors
------

:class:`~affirmatrix.sources.content.ExtractorError` is raised in two places.
When the extractor is built it refuses what the exports and the Doxygen trees
alone show, before any record is supplied: an export that cannot be read, that
holds no or several versions or no ``needs``, or that carries a build timestamp
(SEG-SREQ-158); a need with no symbol, or an identifier other than its key; a
Doxygen directory that is missing or a file of it that does not parse. The
export checks are the requirements reader's, shared through one private helper.

Everything that needs a location or a source is checked when
:meth:`~affirmatrix.sources.content.CSourceExtractor.nodes` reaches the node,
and the message names the need. The stream raises there and never skips the
node, so it is never short; the records before the failing node have been
supplied already. A consumer that writes as it reads could leave half a graph
behind, so it must consume the whole stream before it writes, as the drift
derivation consumes both record streams completely.

Reading the sources
-------------------

Each source file is read once for one pass of ``nodes()``, so every node of that
pass sees the same bytes; a second pass reads again. The functions that cut the
spans are public so that an auditor can call them without building an
extractor: ``split_lines``, ``span``, ``find_comment``, ``declaration_end`` and
``head_end``.

The Python binding
------------------

The other binding of the same principle, docstring markers located by ``ast``,
is not built. Its design is stated in the module docstring of
``affirmatrix.sources.content``: the marker declares identity and edges, the
parser only locates, and the hash is over the verbatim byte span.
