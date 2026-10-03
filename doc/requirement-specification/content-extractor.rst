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

   If the Doxygen output does not hold exactly one member named by a
   node's symbol, then the content extractor shall report an error for
   that node instead of omitting it.

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

   If a path the Doxygen output names lies outside the repository the
   content extractor is configured to read, then the content extractor
   shall report an error instead of reading it.

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
   the verbatim bytes of the documentation comment that immediately
   precedes the test function.

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

   If no documentation comment immediately precedes a node's declaration,
   then the content extractor shall report an error for that node instead
   of hashing an empty comment.

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
