Configuration Loader
=====================

The configuration loader is the one seam between where content lives and
everything that reads it: the case root, the map from a repository name to its
path, and which of those repositories carries the revision a package's
readiness is judged against. It reads one file by default and needs none at
all, because every parameter it carries has a default; a value given by its
caller always wins over the file's own. Nothing it carries reaches a hash —
source topology changes what the tool reads, never what the tool proves. A
relative path in the file means the same thing from any working directory.
What describes a case itself, rather than one run of the tool over it, is
carried elsewhere and is no part of this component's own.

.. sreq:: Configuration supplies the command line's source topology and defaults
   :id: SEG-SREQ-117
   :refines: SEG-SYS-010

   The configuration loader shall supply the command-line interface with
   every value describing where source content and its history live and
   how the command line's own defaults are drawn, so no such value must be
   given on every invocation.

.. sreq:: Configuration is read from one file
   :id: SEG-SREQ-118
   :refines: SEG-SREQ-117

   The configuration loader shall read its configuration from a file given
   by its caller, or from ./affirmatrix.yaml when none is given.

.. sreq:: Every parameter defaults when the file is absent
   :id: SEG-SREQ-119
   :refines: SEG-SREQ-117

   While the file it would read does not exist, the configuration loader
   shall supply a default value for every parameter it carries rather than
   refuse.

.. sreq:: The case root defaults to ./case
   :id: SEG-SREQ-120
   :refines: SEG-SREQ-117

   While the case root is not given, the configuration loader shall
   default it to ./case.

.. sreq:: A name absent from the repository map resolves to no repository
   :id: SEG-SREQ-121
   :refines: SEG-SREQ-117

   Where a content anchor names a repository absent from the configuration
   loader's repository map, the configuration loader shall resolve that
   anchor to no repository.

.. sreq:: One configured repository is the implementation repository
   :id: SEG-SREQ-122
   :refines: SEG-SREQ-117

   The configuration loader shall carry the name of the repository whose
   revision the proof gate compares every test outcome's recorded revision
   against.

.. sreq:: The producer supplying the current stream is configured
   :id: SEG-SREQ-123
   :refines: SEG-SREQ-117

   The configuration loader shall carry the location of the producer that
   supplies the current stream.

.. sreq:: An optional role vocabulary narrows accepted roles
   :id: SEG-SREQ-124
   :refines: SEG-SREQ-117

   Where a role vocabulary is configured, the configuration loader shall
   carry it as the set of roles the command-line interface accepts for an
   affirmation.

.. sreq:: A caller's value overrides the file's
   :id: SEG-SREQ-125
   :refines: SEG-SREQ-117

   The configuration loader shall prefer a value given by its caller over
   the corresponding value in its file.

.. sreq:: No configured value enters a hash
   :id: SEG-SREQ-126
   :refines: SEG-SREQ-117

   The configuration loader shall supply no value it carries to the
   computation of a content hash, a node hash, an edge hash, or a design
   root.

.. sreq:: A relative path resolves against the file's directory
   :id: SEG-SREQ-135
   :refines: SEG-SREQ-117

   Where the configuration file gives a relative path, the configuration
   loader shall resolve that path against the directory that holds the
   file.

The producer
------------

The extraction adapters read a producer's exports and Doxygen output. The
command line names the run bundles; the configuration names none. The
configuration loader carries where each of those inputs lives and
which repository their anchors name; every path is resolved as any other path
in the file is.

A reader may name a repository of its own. A reader that names none uses the
default repository. The Doxygen path prefix is text, not a path: the loader
does not resolve it against the file's directory. The values of the source
map follow the same rule as every other relative path in the file
(SEG-SREQ-135).

.. sreq:: The configuration loader carries where the producer's inputs are
   :id: SEG-SREQ-191
   :refines: SEG-SREQ-117

   The configuration loader shall carry, for each stream of records the
   producer supplies other than test outcomes, the locations of the inputs
   that stream is read from.

.. sreq:: The default repository is named
   :id: SEG-SREQ-192
   :refines: SEG-SREQ-191

   The configuration loader shall carry the name of the repository against
   which the anchors and paths of every reader without a repository of its
   own are resolved.

.. sreq:: The requirement export's location is carried
   :id: SEG-SREQ-193
   :refines: SEG-SREQ-191

   The configuration loader shall carry the location of the requirement
   export the requirements reader reads.

.. sreq:: The Requirement types are carried
   :id: SEG-SREQ-194
   :refines: SEG-SREQ-191

   The configuration loader shall carry the need types the requirements
   reader treats as Requirements.

.. sreq:: The test-specification inputs are carried
   :id: SEG-SREQ-195
   :refines: SEG-SREQ-191

   The configuration loader shall carry the location of the test-case
   export and of the Doxygen output that the content extractor reads for
   test specifications.

.. sreq:: The implementation inputs are carried
   :id: SEG-SREQ-196
   :refines: SEG-SREQ-191

   The configuration loader shall carry the location of the implementation
   export and of the Doxygen output that the content extractor reads for
   implementations.

.. sreq:: The requirement source directory is carried
   :id: SEG-SREQ-198
   :refines: SEG-SREQ-191

   Where the configuration names a source directory for the requirements
   reader, the configuration loader shall carry its location, against
   which a need's docname and doctype resolve to the source file.

.. sreq:: A configuration that names a run is refused
   :id: SEG-SREQ-234
   :refines: SEG-SREQ-191

   If the configuration names a run, then the configuration loader shall
   refuse the configuration.

.. sreq:: The parent-link field is carried
   :id: SEG-SREQ-284
   :refines: SEG-SREQ-191

   The configuration loader shall carry the name of the need field from
   which the requirements reader takes parent links.

.. sreq:: The types of test-case and implementation needs are carried
   :id: SEG-SREQ-285
   :refines: SEG-SREQ-191

   The configuration loader shall carry, for the test-case export and for
   the implementation export, the need types the content extractor treats
   as test cases and as implementations.

.. sreq:: A reader may name its own repository
   :id: SEG-SREQ-286
   :refines: SEG-SREQ-191

   Where the configuration names a repository for a reader, the
   configuration loader shall carry that name for that reader.

.. sreq:: The Doxygen path prefix is carried
   :id: SEG-SREQ-287
   :refines: SEG-SREQ-191

   The configuration loader shall carry, for each Doxygen output the
   content extractor reads, the path prefix by which that output's paths
   are mapped into the repository.

.. sreq:: The source map is carried
   :id: SEG-SREQ-288
   :refines: SEG-SREQ-191

   The configuration loader shall carry the map from need docnames to the
   source files of the requirement document.

.. sreq:: A source directory and a source map exclude each other
   :id: SEG-SREQ-289
   :refines: SEG-SREQ-191

   If the configuration names both a source directory and a source map for
   the requirements reader, or neither, then the configuration loader
   shall refuse the configuration.

.. sreq:: Need types that are empty or not text are refused
   :id: SEG-SREQ-341
   :refines: SEG-SREQ-191

   If the configuration gives the need types of an export as anything
   other than a non-empty list of text values, then the configuration
   loader shall refuse the configuration, naming the block.

.. sreq:: The Doxygen path root is carried
   :id: SEG-SREQ-348
   :refines: SEG-SREQ-191

   The configuration loader shall carry, for each Doxygen output the
   content extractor reads, the directory inside the repository that the
   content extractor puts in front of each path of that output, after
   any path prefix is removed.
