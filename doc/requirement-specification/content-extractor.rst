Content Extractor
=================

The content extractor turns source into content hashes. It locates the span
a node covers and hashes it, so the hash binds the exact bytes a reviewer
reads rather than any reconstruction of them. Its first requirement fixes the
canonical content form for source-located nodes as the verbatim byte span and
stays the principle; the claims for C source specialise it. The requirements
reader and the outcome extractor, the other two extraction adapters, have
pages of their own.

.. sreq:: Content hashes over verbatim byte spans
   :id: SEG-SREQ-001
   :refines: SEG-SYS-001

   The content extractor shall compute each content hash as the SHA-256 of
   the verbatim source byte span it covers.

C located by Doxygen
--------------------

A parser only locates. For C the Doxygen output says where each symbol sits;
the hashed bytes are always read from the source file, never taken from
Doxygen's own text, which is reflowed. A *symbol* is the name that an
implementation need carries in its title, or that a test-case need carries as
its test function. Identity and edges come from the need exports; the source
supplies content and nothing else. Where exactly a span starts and ends is
fixed in the architecture documentation, not here; these requirements say what
each hash covers.

A *plain comment* is a block comment that is not a documentation comment. A
*conditional line* is a line whose first non-blank text is ``#if``,
``#ifdef``, ``#ifndef``, ``#elif``, ``#else`` or ``#endif``. A test's
documentation comment may lie above the test behind blank lines, plain
comments and conditional lines, as Doxygen attaches it; ADR-0011 fixes the
exact search.

Doxygen names a file by a path from its own base directory. A configured
path prefix maps such a path into the repository: the extractor removes the
prefix and reads the rest within the repository of the stream. Each stream
names its own repository, and an anchor holds the path inside that
repository.

A path root is a directory inside the repository. Doxygen can name a file
relative to a directory below the repository root, for example ``a/b.h`` for
the file ``include/a/b.h``. The extractor puts the path root in front of the
remainder, after it removes the prefix.

.. sreq:: The content extractor supplies C nodes from exports and located source
   :id: SEG-SREQ-152
   :refines: SEG-SYS-001

   The content extractor shall supply Implementation and TestSpecification
   records for C source, taking each node's structure from the need
   exports and its content from the source files the Doxygen output
   locates.

.. sreq:: Identity and edges come from the exports
   :id: SEG-SREQ-153
   :refines: SEG-SREQ-152

   The content extractor shall take the identity and the edges of every
   Implementation and TestSpecification from the need exports, never from
   the source files.

.. sreq:: An Implementation is identified by its need identifier
   :id: SEG-SREQ-154
   :refines: SEG-SREQ-153

   The content extractor shall identify each Implementation record by the
   identifier of its implementation need, verbatim.

.. sreq:: A TestSpecification is identified by its need identifier
   :id: SEG-SREQ-155
   :refines: SEG-SREQ-153

   The content extractor shall identify each TestSpecification record by
   the identifier of its test-case need, verbatim.

.. sreq:: Implements edges come from satisfies links
   :id: SEG-SREQ-156
   :refines: SEG-SREQ-153

   The content extractor shall derive an Implements edge from each
   implementation need to each requirement the need's satisfies links
   name.

.. sreq:: Verifies edges come from verifies links
   :id: SEG-SREQ-157
   :refines: SEG-SREQ-153

   The content extractor shall derive a Verifies edge from each test-case
   need to each requirement the need's verifies links name.

.. sreq:: An export with build timestamps is refused
   :id: SEG-SREQ-158
   :refines: SEG-SREQ-153

   If a need export the content extractor reads carries a build timestamp,
   then the content extractor shall refuse the export instead of supplying
   records from it.

.. sreq:: Source is located through the Doxygen output
   :id: SEG-SREQ-159
   :refines: SEG-SREQ-152

   The content extractor shall locate the source lines of every
   Implementation and TestSpecification through the Doxygen output for the
   source.

.. sreq:: A node is located by the member named by its symbol
   :id: SEG-SREQ-160
   :refines: SEG-SREQ-159

   The content extractor shall locate each node through the Doxygen member
   whose name is the symbol the node's need names.

.. sreq:: An unlocatable or ambiguous symbol is an error
   :id: SEG-SREQ-161
   :refines: SEG-SREQ-159

   If, after the choice by test module where that applies, the Doxygen
   output does not hold exactly one member named by a node's symbol, then
   the content extractor shall report an error for that node instead of
   omitting it.

.. sreq:: An Implementation's symbol is its need's title
   :id: SEG-SREQ-200
   :refines: SEG-SREQ-159

   The content extractor shall take the symbol of each Implementation from
   the title of its implementation need.

.. sreq:: A TestSpecification's symbol is its need's test function
   :id: SEG-SREQ-201
   :refines: SEG-SREQ-159

   The content extractor shall take the symbol of each TestSpecification
   from the test function of its test-case need.

.. sreq:: A location outside the repository is an error
   :id: SEG-SREQ-162
   :refines: SEG-SREQ-159

   If a path the Doxygen output names lies outside the repository
   configured for the node's stream, then the content extractor shall
   report an error for that node instead of reading it.

.. sreq:: apiHash covers the declaration and its documentation comment
   :id: SEG-SREQ-163
   :refines: SEG-SREQ-152

   The content extractor shall compute an Implementation's apiHash over
   the verbatim bytes of the symbol's declaration together with the
   documentation comment that immediately precedes it.

.. sreq:: A macro's apiHash covers its definition head and its documentation comment
   :id: SEG-SREQ-164
   :refines: SEG-SREQ-152

   The content extractor shall compute the apiHash of an Implementation
   that is a macro over the verbatim bytes of the macro's definition head
   together with the documentation comment that immediately precedes it.

.. sreq:: bodyHash covers the located body
   :id: SEG-SREQ-165
   :refines: SEG-SREQ-152

   The content extractor shall compute an Implementation's bodyHash over
   the verbatim bytes of the lines its symbol's body occupies in the
   source file.

.. sreq:: specHash covers the test's documentation comment
   :id: SEG-SREQ-166
   :refines: SEG-SREQ-152

   The content extractor shall compute a TestSpecification's specHash over
   the verbatim bytes of the documentation comment above the test
   function, which has only blank lines, plain comments and conditional
   lines between it and the test function, and over no other line.

.. sreq:: implHash covers the test's located body
   :id: SEG-SREQ-167
   :refines: SEG-SREQ-152

   The content extractor shall compute a TestSpecification's implHash over
   the verbatim bytes of the lines the test function's body occupies in
   the source file.

.. sreq:: Spans are whole lines
   :id: SEG-SREQ-168
   :refines: SEG-SREQ-152

   The content extractor shall include in every span it hashes each line
   it covers in full, with that line's terminator, and no part of any
   other line.

.. sreq:: A missing documentation comment is an error
   :id: SEG-SREQ-169
   :refines: SEG-SREQ-152

   If no documentation comment immediately precedes an Implementation's
   declaration, then the content extractor shall report an error for that
   node instead of hashing an empty comment.

.. sreq:: No hashed byte comes from the Doxygen output's text
   :id: SEG-SREQ-170
   :refines: SEG-SREQ-152

   The content extractor shall compute every hash over bytes of the source
   files only, never over text taken from the Doxygen output.

.. sreq:: An Implementation's api anchor
   :id: SEG-SREQ-171
   :refines: SEG-SREQ-143

   The content extractor shall anchor each Implementation's apiHash at the
   file holding the symbol's declaration, with the locator
   symbol:<symbol>#api.

.. sreq:: An Implementation's body anchor
   :id: SEG-SREQ-172
   :refines: SEG-SREQ-143

   The content extractor shall anchor each Implementation's bodyHash at
   the file holding the symbol's body, with the locator
   symbol:<symbol>#body.

.. sreq:: A TestSpecification's spec anchor
   :id: SEG-SREQ-173
   :refines: SEG-SREQ-143

   The content extractor shall anchor each TestSpecification's specHash at
   the file holding the test function's documentation comment, with the
   locator symbol:<symbol>#spec.

.. sreq:: A TestSpecification's impl anchor
   :id: SEG-SREQ-174
   :refines: SEG-SREQ-143

   The content extractor shall anchor each TestSpecification's implHash at
   the file holding the test function's body, with the locator
   symbol:<symbol>#impl.

.. sreq:: A location that does not name its symbol is an error
   :id: SEG-SREQ-175
   :refines: SEG-SREQ-159

   If the source line a Doxygen location names does not contain the symbol
   that location is for, then the content extractor shall report an error
   for that node instead of hashing it.

.. sreq:: A member with no recorded body is an error
   :id: SEG-SREQ-350
   :refines: SEG-SREQ-159

   If the Doxygen output records no body for the member that a node's
   symbol names, then the content extractor shall report an error for
   that node instead of hashing it.

.. sreq:: Configured need types, and only those, supply records
   :id: SEG-SREQ-275
   :refines: SEG-SREQ-153

   Where need types are configured for an export, the content extractor
   shall supply a record for a need of that export when, and only when,
   the need's type is one of those types.

.. sreq:: Without configured types, every need supplies a record
   :id: SEG-SREQ-276
   :refines: SEG-SREQ-153

   While no need type is configured for an export, the content extractor
   shall supply a record for every need of that export.

.. sreq:: A need of another type is not refused
   :id: SEG-SREQ-277
   :refines: SEG-SREQ-153

   Where need types are configured for an export, the content extractor
   shall not refuse the export because of a need whose type is not one of
   those types.

.. sreq:: A listed identifier narrows the implementation records
   :id: SEG-SREQ-358
   :refines: SEG-SREQ-153

   Where a list of need identifiers is configured for the implementation
   export, the content extractor shall supply a record for a need of
   that export when, and only when, the need's identifier is in the
   list.

.. sreq:: A listed identifier that names no need is refused by the content extractor
   :id: SEG-SREQ-360
   :refines: SEG-SREQ-153

   If a need identifier in the list configured for the implementation
   export names no need of that export, then the content extractor shall
   refuse the configuration when it reads the export, naming the
   identifier.

.. sreq:: A symbol that several members share is narrowed by the test module
   :id: SEG-SREQ-278
   :refines: SEG-SREQ-159

   Where the Doxygen output holds several members named by the symbol of a
   test-case need and the need names a test module, the content extractor
   shall locate the need through the member whose file lies within the
   directory the test module names. The file's path is the path within the
   repository, after any configured path prefix is removed and any
   configured path root is put in front.

.. sreq:: An absent or empty test module names none
   :id: SEG-SREQ-343
   :refines: SEG-SREQ-159

   While the test module of a test-case need is absent, null or the
   empty text, the content extractor shall treat the need as naming no
   test module.

.. sreq:: A test module that is not text is an error
   :id: SEG-SREQ-344
   :refines: SEG-SREQ-159

   If the test module of a test-case need is present and is neither null
   nor text, then the content extractor shall report an error for that
   node instead of locating it.

.. sreq:: A Doxygen path is mapped into the repository by a configured prefix
   :id: SEG-SREQ-279
   :refines: SEG-SREQ-159

   Where a path prefix is configured for a Doxygen output, the content
   extractor shall resolve each path that output names by removing the
   prefix and reading the remainder within the repository configured for
   that output's stream.

.. sreq:: A path outside the prefix is an error
   :id: SEG-SREQ-280
   :refines: SEG-SREQ-159

   If a path a Doxygen output names does not begin with the path prefix
   configured for that output, then the content extractor shall report an
   error for that node instead of reading it.

.. sreq:: A path root is put in front of the remainder
   :id: SEG-SREQ-349
   :refines: SEG-SREQ-159

   Where a path root is configured for a Doxygen output, the content
   extractor shall resolve each path that output names by removing the
   configured path prefix, if any, putting the path root in front of the
   remainder, and reading the result within the repository configured
   for that output's stream.

.. sreq:: A remainder that is not a relative path is an error
   :id: SEG-SREQ-342
   :refines: SEG-SREQ-159

   If the remainder of a path after the configured path prefix is
   removed is empty or begins with a path separator, then the content
   extractor shall report an error for that node, naming the path and
   the prefix, instead of reading it.

.. sreq:: An anchor names the repository of its stream and the path within it
   :id: SEG-SREQ-281
   :refines: SEG-SREQ-143

   The content extractor shall name, in the anchor of each node's content
   hash, the repository configured for the node's stream and the path of
   the anchored file within that repository.

.. sreq:: Every node that cannot be supplied is reported in one error
   :id: SEG-SREQ-282
   :refines: SEG-SREQ-152

   If the content extractor cannot supply one or more nodes, then it shall
   report every one of them in a single error, each with its reason.

.. sreq:: A test without a documentation comment is an error
   :id: SEG-SREQ-283
   :refines: SEG-SREQ-152

   If a test function has no documentation comment above it with only
   blank lines, plain comments and conditional lines between them, then
   the content extractor shall report an error for that node instead of
   hashing an empty comment.

.. sreq:: Every misshapen need of an export is reported in one error
   :id: SEG-SREQ-351
   :refines: SEG-SREQ-152

   If one or more needs of an export the content extractor reads lack a
   text field it reads, declare an id other than their key, or carry a
   link field that is not a list of identifiers, then the content
   extractor shall report every such need in one error, each with its
   reason.
