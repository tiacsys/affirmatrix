Narrow an implementation export
===============================

An export of implementation needs can hold many needs, and you may want only a
few of them in the graph. This page shows how to read only the needs you
name. A need that you do not name is not read, and it is not checked.

Before you start
----------------

- The export and the Doxygen output of the implementation exist. The content
  extractor reads both (see :doc:`../explanation/architecture/content-extractor`).
- The source files that the Doxygen output names are in a repository that the
  configuration maps under ``repositories:``.

Name the needs you want
-----------------------

Put the key ``need-ids`` in the implementations block. Its value is the list
of need identifiers to read. The example below also sets ``types`` and
``path-root``, because most real exports need them. All paths are relative to
the directory of the file.

.. code-block:: yaml

   case: ./case
   repositories:
     library: ../library
   producer:
     implementations:
       repository: library
       export: needs/api-needs.json
       doxygen: xml/api
       types: [impl]
       path-root: include/
       need-ids:
         - IMPL-QUEUE-DEFINE
         - IMPL-queue-put
         - IMPL-queue-get
         - IMPL-queue-peek

What each key does:

- ``types`` keeps the needs of the listed types.
- ``need-ids`` keeps the needs with the listed identifiers.
- ``path-root`` puts a directory in front of each path that the Doxygen output
  names (:need:`SEG-SREQ-349`).

When you give both ``types`` and ``need-ids``, a need is read only when both
admit it. Give ``need-ids`` alone, and the type of a need does not matter. Give
neither, and every need is read.

The names of all the keys, for every block, are in the key list of the
configuration loader: :external+srs:ref:`the-names-of-the-keys`. This page
does not repeat the list. A key that is not on that list is refused
(:need:`SEG-SREQ-376`).

What happens to a need you did not name
---------------------------------------

The extractor does not read it, and it does not check it. A need that has no
title, or a bad link, is not refused when it is not in the list
(:need:`SEG-SREQ-374`). A need that is in the list keeps every check.

An identifier that names no need
--------------------------------

Every identifier in the list must name a need of the export that the
configured types admit. If one does not, the extractor refuses the
configuration. The error names every such identifier, one on each line
(:need:`SEG-SREQ-360`). A typing error in an identifier then stops the run, and
the graph is never built without the need you wanted.

A mistyped key
--------------

The loader refuses a key that it does not know (:need:`SEG-SREQ-376`). If you
write ``need_ids`` and not ``need-ids``, the command exits with status 2. The
message names the key and where it stands, and it lists the keys of that
place. The case does not change.
