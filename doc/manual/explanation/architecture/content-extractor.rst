The content extractor
=====================

The engine consumes records; the code and the tests they cover are C files in
another repository. :class:`affirmatrix.sources.content.CSourceExtractor` sits
between the two: from the need exports, the Doxygen output and the source files
it supplies one Implementation or TestSpecification record per need, each with
two content hashes, and one edge per declared link. The command
line composes it, with the other configured readers, into the current stream
(see :doc:`command-line-interface`). The Python
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
           types=frozenset({"test_case"}),
           doxygen_prefix="checkout/",
       ),
       specification_placement=Placement("tests-repository", Path("tests-checkout")),
   )

Three kinds of input, each for one purpose:

* the **need exports** give the structure: which nodes exist, their identity
  and their links (:need:`SEG-SREQ-153`). Where need types are configured for an
  export, only the needs of those types supply a record, and a need of another
  type is never refused (:need:`SEG-SREQ-275`, :need:`SEG-SREQ-277`). Where none
  are configured, every need in the implementation export is an Implementation
  and every need in the test-case export a TestSpecification
  (:need:`SEG-SREQ-276`). The symbol a need names is its ``title`` on an
  implementation need and its ``test_function`` on a test-case need;
* the **Doxygen output** gives the location: the file and the lines of a
  symbol's declaration and body. Only names, kinds and ``<location>``
  attributes are read from it; none of its text reaches a hash (:need:`SEG-SREQ-170`);
* the **source files** under the stream's root give the bytes that are hashed.

Each stream has its own place: the configured name of the repository its files
belong to, never a path (:need:`SEG-SREQ-134`), and the path of that repository.
A stream without a ``Placement`` of its own takes ``repository`` and ``root`` as
its place. A stream set to ``None`` supplies nothing, and with both ``None`` the
extractor supplies nothing at all.

The paths in a Doxygen output come from Doxygen's own base directory. A stream
may name a prefix, the text that each of those paths begins with
(:need:`SEG-SREQ-279`). The extractor removes the prefix as written, and reads
the rest within the stream's repository. A path that does not begin with the
prefix is an error for its node and is not read (:need:`SEG-SREQ-280`). So is a
path whose remainder after the prefix is empty or begins with a separator. The
error names the path and the prefix (:need:`SEG-SREQ-342`). A prefix that ends
with the separator avoids that error. With no prefix, the path is used as it
stands. A prefix is text, not a path, so the configuration file's directory
plays no part in it. It should end with the path separator.

What it supplies
----------------

Each node is identified by its need identifier, verbatim (:need:`SEG-SREQ-154`,
:need:`SEG-SREQ-155`; ADR-0007): a renamed symbol does not rename the node. Each link in
``satisfies`` becomes an Implements edge from the implementation to the
requirement, each link in ``verifies`` a Verifies edge from the test
specification to the requirement, in the pending state (:need:`SEG-SREQ-156`,
:need:`SEG-SREQ-157`). Edges need neither the Doxygen output nor a source file. On
the toolbox evidence fixture that is 12 Implementations, 19 TestSpecifications
and 16 + 24 edges.

Finding the lines
-----------------

Each Doxygen tree is read once, when the extractor is built. Its members are
indexed by name, each tree separately, so an implementation's symbol is never
looked up in the test tree. A node is located through the one member whose name
is its symbol (:need:`SEG-SREQ-160`). "One" means one distinct definition: a member
listed in two compounds with the same ``id`` and location counts once, but two
``id`` values, or one ``id`` at two locations, are two. Where several members
share the symbol and a test-case need names a ``test_module``, the members
whose file lies within that directory are the candidates
(:need:`SEG-SREQ-278`). A ``test_module`` that is absent, null or empty text
names no module (:need:`SEG-SREQ-343`). One that is present and is neither null
nor text is an error for its node, found before the members are looked up
(:need:`SEG-SREQ-344`). The file is compared as a path inside the repository,
after the prefix is removed, and by whole path components: ``tests/a`` does not
contain ``tests/ab``. A member whose remainder after the prefix is no relative
path is an error for the node, not a member outside the module. After that
choice, a symbol with none or with several
members is an error for its node (:need:`SEG-SREQ-161`). Members no need names
are never consulted, which is why the test tree's duplicate
``SAFE_CONTAINER_DEFINE`` costs nothing. The index of Doxygen's own listing is
not followed: it lists members repeatedly and gives no location.

Before a file is opened, every path the node's location names has its prefix
removed and is resolved under the root of the node's stream (links included). It
must stay inside that root; ``..``, an absolute path and a link that leads out
are errors, and the file outside is not read (:need:`SEG-SREQ-162`). A path
inside the root of another stream is outside this one. Then the line each location names must contain the symbol as a
whole identifier: ``line`` and ``declline`` in the declaration file, and
``bodystart`` in the body file, never ``bodyend`` (:need:`SEG-SREQ-175`). A location
that Doxygen left stale, pointing at another function's lines, is refused
instead of hashed.

The four hashes
---------------

A hash is the SHA-256 of a run of whole lines of one source file, each with its
terminator (:need:`SEG-SREQ-168`); nothing is trimmed, so a CR before the line feed is
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
     - the opener of the comment the search for a test finds above it
     - the closer of that comment
   * - TestSpecification, ``implHash``
     - ``bodystart``
     - ``bodyend``

The documentation comment of an Implementation is found from the line above the
declaration, stepping over ``#if``, ``#ifdef`` and ``#ifndef`` lines only. The
next line must end the comment with ``*/``, and its opener must be ``/**`` or
``/*!``. A blank line, a plain comment or code there means the node has no
documentation comment, an error and never an empty hash
(:need:`SEG-SREQ-169`). A guard line between the comment and the declaration lies
inside the span; one above the comment lies outside.

The search for a test is wider, as Doxygen attaches a comment to the next
member (:need:`SEG-SREQ-166`). From the line above the test, it steps over blank
lines, over conditional lines (``#if``, ``#ifdef``, ``#ifndef``, ``#elif``,
``#else`` and ``#endif``) and over plain comments. A plain comment is a block
comment that is not a documentation comment, with only white space before its
opener on its line. The first other line must end a documentation comment. Code,
any other directive, a line comment or the top of the file there means the test
has no documentation comment, an error and never an empty hash
(:need:`SEG-SREQ-283`). The span runs from the opener to the closer, so the lines
stepped over lie outside it and changing them changes no hash. The search does
not read the text of the comment. A test that loses its own comment can
therefore take a group comment above it, when only such lines lie between.
A test whose member Doxygen finds in one branch of a conditional, with its
comment above the other branch, is still an error, because code lies between. When the end of a declaration is sought, text in comments is skipped,
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
came from: the configured name of the stream's repository; the path of the file
inside that repository (:need:`SEG-SREQ-281`), which is the file as Doxygen names
it with the prefix removed, and which for an ``apiHash`` is the declaration file
and for a ``bodyHash`` or ``implHash`` the body file; and the locator
``symbol:<name>#api``, ``#body``, ``#spec`` or ``#impl`` (:need:`SEG-SREQ-171` to
:need:`SEG-SREQ-174`). No line number is recorded, so moving a function within its
file changes no anchor.

The bytes behind a hash
-----------------------

The extractor meets the protocol :class:`~affirmatrix.records.ContentSource`
(:need:`SEG-SREQ-311`). The method ``content(local_id, hash_name)`` gives the
span that the hash covers. It finds the need in the stream. It locates the member
in the Doxygen index, which exists since the extractor was built. Then it cuts
the span from the source files as they are now. ``nodes()`` and ``content()`` read through
one function, so a hash and its bytes cannot follow two rules. A call reads at
most three source files and keeps nothing. The answer is ``None`` for an unknown
identifier and for a name that is not one of the stream's two hashes.

Errors
------

:class:`~affirmatrix.sources.content.ExtractorError` is raised in three places.
When the extractor is built it refuses what the exports and the Doxygen trees
alone show, before any record is supplied: an export that cannot be read, that
holds no or several versions or no ``needs``, or that carries a build timestamp
(:need:`SEG-SREQ-158`); a need with no symbol, or an identifier other than its key; a
Doxygen directory that is missing or a file of it that does not parse. The
export checks are the requirements reader's, shared through one private helper.

Everything that needs a location or a source is checked when
:meth:`~affirmatrix.sources.content.CSourceExtractor.nodes` reaches the node.
A node that fails does not stop the pass and is never skipped. The records of
the other nodes are supplied as they are reached. At the end of the stream the
extractor raises one :class:`~affirmatrix.sources.content.UnsuppliedNodesError`
that names every node it cannot supply (:need:`SEG-SREQ-282`). The first line
of its message gives the count. Each next line holds one need, its symbol and
its reason, so a reader finds one need on one line. The same facts are in the
``failures`` attribute. The stream is never silently short. A consumer that
writes as it reads could leave half a graph behind, so it must consume the whole
stream before it writes, as the drift derivation consumes both record streams
completely.

The third place is ``content()``. A node that cannot be located or cut raises an
``UnsuppliedNodesError`` that holds this one failure.

Reading the sources
-------------------

Each source file is read once for one pass of ``nodes()``, so every node of that
pass sees the same bytes; a second pass reads again, and so does each call of
``content()``. The functions that cut the
spans are public so that an auditor can call them without building an
extractor: ``split_lines``, ``span``, ``find_comment``, ``find_test_comment``,
``declaration_end`` and ``head_end``.

The Python binding
------------------

The other binding of the same principle, docstring markers located by ``ast``,
is not built. Its design is stated in the module docstring of
``affirmatrix.sources.content``: the marker declares identity and edges, the
parser only locates, and the hash is over the verbatim byte span.
