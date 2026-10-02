0011. C constructs located by Doxygen: the span each hash covers
=================================================================

Status
------

Accepted, 2026-09-29. Amended 2026-09-29: the search for a documentation
comment no longer steps over blank lines, so only guard lines may lie between
the comment's closer and the located line; the paragraph *Finding the
documentation comment* is rewritten and no worked digest changes. Amended 2026-10-02: for a test, the
search for the documentation comment also steps over blank lines, plain
comments and every conditional line, as Doxygen attaches a comment to the next
member. The rule for an Implementation does not change. No digest of a node
that the earlier rule accepted changes. Binds, for
C source, the principle of :need:`SEG-SREQ-001`: the
parser only locates a span, and the hash is over the verbatim bytes of the
source file. :need:`SEG-SREQ-163` to :need:`SEG-SREQ-170` state *what* each hash covers; this
record fixes *where each span starts and ends*. The Python binding of the same
principle, located by ``ast``, is unchanged.

Context
-------

:need:`SEG-SREQ-001` fixes the canonical content form of source-located nodes as the
verbatim byte span, and ADR-0005 adds the property that makes it auditable: a
content hash is the bare SHA-256 of that form, so anyone can reproduce it with
``sha256sum``. Until now the principle has had one binding, Python located by
``ast``, where the span is a cut of bytes between positions the interpreter's
own parser reports.

A second language needs its own cut, and the C side does not offer the same
material. The locator for C is Doxygen's XML output, and what it gives is
**lines, not bytes**: for each member a ``<location>`` element with the line
of the symbol and, where the definition lives elsewhere, the file and lines of
the declaration and of the body (``line``, ``bodyfile``, ``bodystart``,
``bodyend``, ``declfile``, ``declline``). A byte cut inside a line, after a
parameter list say, would need the extractor to parse C itself, which turns
the span into a function of our parser and no longer of the file. A span of
whole lines is a function of two line numbers and nothing else.

The other half of a node comes from elsewhere. Its identity and its edges are
taken from the need exports, never from the source (:need:`SEG-SREQ-153`), so the
source contributes content and only content. What remained open, and what the
content-extractor requirements leave to the architecture documentation, is the
cut: exactly which lines each of the four C hashes covers, for which kinds of
construct, and in which file.

Decision
--------

**Spans are runs of whole lines.** A span is a run of lines ``[a, b]``, 1-based
and inclusive. Its bytes are the concatenation of those lines, each with its
terminator: the terminator of line ``b`` is included, and if ``b`` is the
last line of the file and has none, none is added. Nothing is trimmed and
nothing is normalized: a CR before a line feed is content, and so are tabs and
trailing whitespace. Every C content hash is therefore reproducible with

.. code-block:: sh

   sed -n 'a,bp' <file> | sha256sum

and with no tool of ours. Line numbers are found at extraction time and never
enter a record: the locator a record carries names the symbol
(``symbol:<name>#api``, ``#body``, ``#spec`` or ``#impl``), and the anchor
names the file the span was read from (:need:`SEG-SREQ-171` to :need:`SEG-SREQ-174`).

**Finding the documentation comment.** Each construct below names a *located
line* ``L``, the line its declaration starts on. The search starts at line
``L - 1``. It has one rule for an Implementation and one rule for a test.

For an Implementation, step upward over every *guard line*, a line whose first
non-blank text is ``#if``, ``#ifdef`` or ``#ifndef``. A blank line is not a
guard line and ends the step. The line reached must end with ``*/``, ignoring
trailing whitespace, and it is the *closer*. The *opener* is the nearest line
at or above the closer that contains a comment opener, and that opener must be
``/**`` or ``/*!`` (``/**/`` and ``/***`` are plain comments). Anything else
means the node has no documentation comment: a blank line, a plain ``/*``,
code, any other preprocessor line, the top of the file. That is an error for
the node and never an empty hash (:need:`SEG-SREQ-169`). The span runs
contiguously from the opener downward, so guard lines between the closer and
``L`` are inside it. A guard line above the opener is outside it.

For a test, ``L`` is the ``ZTEST`` line. Doxygen attaches a documentation
comment to the next member, and a blank line, a plain comment or a conditional
line does not break that link. The extractor follows the same rule. Step upward
over every line of these three kinds:

- a *blank line*: a line that holds nothing, or white space only;
- a *conditional line*: a line whose first non-blank text is ``#if``,
  ``#ifdef``, ``#ifndef``, ``#elif``, ``#else`` or ``#endif``;
- a *plain comment*: a block comment that is not a documentation comment,
  from its closer line up to its opener line, where only white space comes
  before the opener on its line.

The first line that is none of these must end with ``*/``, ignoring trailing
whitespace. It is the closer. The opener is found as for an Implementation,
and it must be ``/**`` or ``/*!``. Any other line ends the search with no
documentation comment: code, a preprocessor line such as ``#include``,
``#define`` or ``#pragma``, a line comment (``//``, ``///`` or ``//!``), or the
top of the file. That is an error for the node and never an empty hash
(:need:`SEG-SREQ-283`). The span of a ``specHash`` runs from the opener to the
closer. The lines the search stepped over lie outside it. So a blank line, a
plain comment or a conditional line added or removed between the comment and
the test does not change the ``specHash``.

The forms ``///`` and ``//!``, whether a run of lines or trailing as ``///<``,
are not recognised as documentation comments, for an Implementation or for a
test.

**The span each hash covers.** ``declfile``, ``declline``, ``bodyfile``,
``bodystart`` and ``bodyend`` are the attributes of the member's
``<location>``; ``file`` and ``line`` are its own file and line.

.. list-table::
   :header-rows: 1
   :widths: 22 10 18 25 25

   * - Construct
     - Hash
     - Read from
     - First line
     - Last line
   * - A function declared in a header and defined in a source file
       (``declfile`` is present); ``L`` is ``declline``
     - ``apiHash``
     - ``declfile``
     - the opener of the comment above ``L``
     - the line holding the first ``;`` at parenthesis depth zero after
       ``L``, text inside comments skipped
   * -
     - ``bodyHash``
     - ``bodyfile``
     - ``bodystart``
     - ``bodyend``
   * - A function declared and defined in one file (no ``decl*``
       attributes); ``L`` is ``bodystart``
     - ``apiHash``
     - ``bodyfile``
     - the opener of the comment above ``L``
     - the line before the first line at or after ``bodystart`` whose first
       non-blank character is ``{``; an error if a line of the head contains
       ``{`` or if no such line lies at or before ``bodyend``
   * -
     - ``bodyHash``
     - ``bodyfile``
     - ``bodystart``
     - ``bodyend``
   * - A macro (``define``); ``L`` is ``line``
     - ``apiHash``
     - ``file``
     - the opener of the comment above ``L``, guard lines included
     - ``L`` itself: the ``#define`` line, continuation marker included
   * -
     - ``bodyHash``
     - ``bodyfile``
     - ``bodystart`` (the ``#define`` line)
     - ``bodyend`` (the last continuation line)
   * - A test defined with ``ZTEST`` (a member of kind ``function``, whose
       ``line`` equals ``bodystart``); ``L`` is ``line``
     - ``specHash``
     - ``file``
     - the opener of the comment the search for a test finds above ``L``
     - the closer of that comment
   * -
     - ``implHash``
     - ``bodyfile``
     - ``bodystart`` (the ``ZTEST(...)`` line)
     - ``bodyend`` (the closing ``}``)

The file a hash is read from is the file its anchor names.

**Two facts of Doxygen's numbering that the table relies on.** First,
``bodystart`` is the first line of a definition's *head* and not the line of
its opening brace, so a ``bodyHash`` includes the head: for ``safe_data_init``
the body is lines 224 to 237 of ``src/safe_data.c``, the head begins at 224
and the ``{`` is at 226. The rule about the line before the brace belongs to
the ``apiHash`` of a same-file definition only. Second, a macro's head and its
body overlap on the ``#define`` line, and the whole directive is the body. A
one-line macro therefore puts its entire text into both hashes: coarser than
necessary, never unsound.

**A body of -1.** Doxygen writes ``bodyend = -1`` for a member it records as having no
body; the evidence fixture's header has two one-line defines of that kind,
neither an implementation need. For a node this is an error, reported for the
node.

**Worked examples.** The toolbox evidence fixture under ``tests/fixtures``
holds the sources and the Doxygen XML these lines come from. Every digest below is ``sed -n 'a,bp' <file> | sha256sum`` over the
file named, and is the digest of exactly those lines.

.. list-table::
   :header-rows: 1
   :widths: 24 10 34 32

   * - Node
     - Hash
     - File and lines
     - SHA-256
   * - ``safe_data_init``
     - ``apiHash``
     - ``include/safe_data/safe_data.h`` 247-263
     - ``dcfd58ce00f23973afff2aa76f3b11cc422aad373981488c22b1745eb325ba9c``
   * -
     - ``bodyHash``
     - ``src/safe_data.c`` 224-237
     - ``edcd36bd22831759ddf6438f290cdb1c8feadaf9655ce1fa3b07034e2e93ff42``
   * - ``SAFE_CONTAINER_DEFINE``
     - ``apiHash``
     - ``include/safe_data/safe_data.h`` 477-498
     - ``4f58410b9b9b897a3808d3b3f59b74b8062fba26e53e97501251ea04ce2d4d44``
   * -
     - ``bodyHash``
     - ``include/safe_data/safe_data.h`` 498-506
     - ``adbf8892bfb18a364954fc6730954d13fca22cc0ae85019d792b6eed5914ae83``
   * - ``SAFE_SECTION``
     - ``apiHash``
     - ``include/safe_data/safe_data.h`` 595-633
     - ``2a068843d8dec88dde21c4ae07153d2413b2c81e1c700538581084f8a9b07f76``
   * -
     - ``bodyHash``
     - ``include/safe_data/safe_data.h`` 633-649
     - ``e6a2f6a9ec47c6a901867d1904f7e0f906c0112fd8f822002dde0bd4eaef95e1``
   * - ``test_init_and_verify``
     - ``specHash``
     - ``tests/safe_data/src/main.c`` 33-43
     - ``f35d5149cc93ad65ad33d8d95f33b0a0898ca9233ac0342a61b087922419c2b2``
   * -
     - ``implHash``
     - ``tests/safe_data/src/main.c`` 44-48
     - ``4d32eab783af84139a0961d1822d7937ea2a9b7f73e1ff5a2dffc6b25252ccb0``

In ``safe_data_init`` the declaration is located at line 262 of the header, the
comment opens at 247 and closes at 261 (its ``@satisfies`` line, 260, is
inside the span), and the first ``;`` at depth zero is on line 263, the
continuation of the parameter list. The body is located through
``bodyfile`` and is a different file from the api anchor: the two hashes of
one node are read from two files. ``SAFE_CONTAINER_DEFINE`` is located at line
498, its comment closes at 497, and its api span ends on the ``#define`` line
with the continuation backslash; its body span is the whole nine-line
directive. ``SAFE_SECTION`` is the case the guard-line allowance exists for:
its comment closes at 631, line 632 is ``#if defined(...) || defined(__DOXYGEN__)``,
and the ``#define`` is at 633. Stepping over the ``#if`` line finds the closer,
the span from the opener at 595 includes line 632, and the ``#endif`` at 650
lies outside the body. Contrast ``safe_data_commit``, whose ``#if`` guard is at
line 377 of the header, above the opener at 378, and so outside its api
span. In ``test_init_and_verify`` the comment holding ``@testid``,
``@verifies`` and ``@active`` spans 33 to 43 and the ``ZTEST`` line, at 44,
starts the body.

The per-need canonical form of a requirement export
---------------------------------------------------

The same principle, applied to a Requirement supplied from a reproducible need
export, has no source bytes to cut, so its canonical content form is derived
from the export. This section gives that form a home in the architecture
record, and the requirements reader's own requirements (:need:`SEG-SREQ-147`,
:need:`SEG-SREQ-148` and :need:`SEG-SREQ-151`) state what it covers.

A Requirement's content hash is the SHA-256 of the RFC 8785 canonical JSON, in
UTF-8, of the object ``{"content": <the need's content>, "refines": <the
identifiers of the needs it names as parents, sorted ascending byte-wise, duplicates
kept>, "title": <the need's title>}``. Its keys are exactly those three.
The parents are read from the need field that the configuration names for them,
and from the field called ``refines`` when it names none. The key in the object
stays ``refines`` whatever the field is called, so the same parents give the
same hash for every producer. The
need's ``id`` is excluded, because identity enters the graph through the
edges. Status, tags, sections, positions, back-links, timestamps and the
export's version key are excluded: each is derived by the build or is metadata
that changes as a review moves while the statement does not. An absent or null
parent field reads as the empty list. The forward links are part of the
content, so adding a second parent to a requirement makes its existing edges
directly outdated, exactly as adding a second ``@verifies`` to a C comment
does. The worked example, with the hash, is on
:doc:`../architecture/requirements-reader`. An export that carries a build
timestamp is refused (:need:`SEG-SREQ-150`); the version key that embeds the commit is
metadata and never a ground for refusal. The anchor of a Requirement names the
source file its need was written in, with the locator ``need:<id>``
(:need:`SEG-SREQ-151`), and recomputing the hash needs the documentation build, not
the file alone.

Consequences
------------

- For an Implementation, a documentation comment must sit directly above its
  declaration, behind at most guard lines. A blank line between them is an
  error for the node. Without this rule, deleting the comment above
  ``safe_data_init`` would hash the ``@addtogroup`` comment two lines earlier as
  though it were the function's own.
- For a test, the comment may stand further up, behind blank lines, plain
  comments and conditional lines. A test that loses its own comment can now take
  an earlier documentation comment, when only such lines lie between. Doxygen
  does the same. The extractor does not read the text of the comment, so it
  cannot tell a group comment from a test's own comment. A reviewer sees the
  mistake at the next affirmation, because the hash changes.
- A test whose Doxygen member lies in one branch of a conditional, with its
  comment above the other branch, is still an error. An example is a test
  defined in the ``#if`` branch and again as an empty stub in the ``#else``
  branch. The member sits in the branch the preprocessor keeps, and code lies
  between that member and the comment.
- No hash that the earlier rule produced changes. The new search steps over
  every line the old search stepped over, and it stops at the same closer. Only
  a node that was an error before can become a hash.
- A locator names a symbol and never a line. Moving a function within its
  file, or editing code above it, leaves the locator valid and changes no hash
  unless a covered line changed; the extractor finds the lines again from the
  Doxygen output each time.
- The granularity is honest rather than fine. Any change to a covered line,
  even to whitespace at its end, moves the hash, and a macro's one-line
  definition is hashed twice. The cost is a coarser tripwire; the gain is that
  no hash depends on a tool of ours cutting bytes correctly.
- The definition of a function declared and defined in one file is stated
  above but exercised by no member of the evidence fixture, which declares
  every implementation in a header. Tests cannot pin that row until a fixture
  file contains such a definition.
- The comment forms ``///``, ``//!`` and trailing ``///<`` are not recognised.
  A project that documents that way gets an error for every node
  (:need:`SEG-SREQ-169`), not a silent empty hash.
- The Doxygen output can be stale against the source. :need:`SEG-SREQ-175` guards the
  case where an edit moved a symbol off its recorded line, by requiring that
  line to contain the symbol; an edit that leaves the symbol on its line is
  not detectable from the output and is not guarded.
- The cut is part of the integrity surface, as the encoding of ADR-0005 is:
  changing where a span starts or ends changes every affected content hash,
  and with it every node hash and every affirmed edge. A change to this rule
  is an amendment to this record and an event for the maintainer, not a
  refactor.
- The Python binding is unchanged: docstring markers located by ``ast``, the
  verbatim byte span as the hash input. The two bindings are now visibly
  siblings of one principle, and both live under the one content extractor
  module of ADR-0004.
