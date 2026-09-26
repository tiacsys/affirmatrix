Configuration Loader
=====================

The configuration loader is the one seam between where content lives and
everything that reads it: the case root, the map from a repository name to
its path, and which of those repositories carries the revision a package's
readiness is judged against. It reads one file by default and needs none at
all, because every parameter it carries has a default; a value given by its
caller always wins over the file's own. Nothing it carries reaches a hash —
source topology changes what the tool reads, never what the tool proves.
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
