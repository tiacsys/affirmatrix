The requirements reader
========================

The requirement specification is authored in sphinx-needs; the engine consumes
records. :class:`affirmatrix.sources.reqs.RequirementsReader` sits between the
two: it reads the specification's built ``needs.json`` and supplies one
Requirement record per requirement need, with a content hash, and one Refines
edge per declared link. It is a library component; the command line does not
yet compose it with the other producers.

What it reads
-------------

.. code-block:: python

   reader = RequirementsReader(
       export=Path("build/needs.json"),
       types=frozenset({"requirement"}),
       repository="my-repository",
       source_directory=Path("doc"),
   )

``export`` is the ``needs.json`` of a clean build. ``types`` names the need
types that are requirements (SEG-SREQ-145): a need of any other type supplies
no record. ``repository`` is the configured name of the repository holding the
requirement document, never a path (SEG-SREQ-134). ``source_directory`` is the
directory of the document's sources relative to that repository.

Only forward links are read (SEG-SREQ-149). The ``*_back`` fields are derived
by sphinx-needs and can be stale after an incremental build, so no field of
that kind is consulted; a stale back link changes nothing.

What it supplies
----------------

Each Requirement is identified by its need identifier, verbatim
(SEG-SREQ-146): not prefixed, re-cased or normalised. Each declared
``refines`` link becomes an edge of kind Refines from the child to the parent,
in the pending state (SEG-SREQ-149), because nothing here has been affirmed.

A link whose target the export does not hold, or holds as a need of a type that
is not configured, is still emitted. The graph reports it as a broken edge,
which is where an operator looks; a reader that refused would hide the whole
graph over one stale link. The consequence: with only some requirement types
configured, every edge to a parent of another type is broken, and the reader
does not say so.

The canonical form
------------------

A Requirement's content hash is the SHA-256 of the UTF-8 canonical JSON of an
object holding exactly three fields of the need (SEG-SREQ-147): its
``content``, its ``refines`` links sorted, and its ``title``, with keys in
sorted order and no insignificant whitespace. The identifier, the status, the
tags and every derived field are not in it, so changing one of those changes
no hash. A need with no ``refines`` serializes an empty array. Sorting the
links is what makes the order the export lists them in irrelevant
(SEG-SREQ-148).

The form is RFC 8785 canonical JSON. The standard library's encoder,
called with sorted keys, compact separators and ``ensure_ascii=False``,
produces it for these value types: the members are strings and one array of
strings, so nothing but member order, whitespace, string escaping and encoding
is in play, and a non-ASCII character is written as its UTF-8 bytes rather
than as a ``\uXXXX`` escape. RFC 8785's number formatting never applies
because no number is in the object; a numeric field joining the form would
need this encoding revisited.

For the need ``SD-REQ-002`` of the frozen example export, the canonical form is
these 270 bytes (the ``\n`` are the two-character JSON escapes of a line
break, not line breaks)::

   {"content":"Every API entry point shall reject missing required pointer arguments and\nzero-length payloads with ``-EINVAL``. A ``NULL`` lock pointer is not an\nerror: it selects the lock-free single-context mode.","refines":["SD-TOP-006"],"title":"Argument validation"}

and its content hash is::

   e06df53acfbb9ca8cee15d0d46cb78d017d20694d915f97277b12fe6196e6fa0

Anyone can reproduce it with ``sha256sum`` over those bytes. The function
:func:`affirmatrix.sources.reqs.canonical_form` returns them for any need.

The anchor
----------

Every content hash is supplied with an anchor of three parts (SEG-SREQ-151).
The repository is the configured name. The path is the need's docname and
doctype joined to the source directory: with the repository ``toolbox`` and the
source directory ``doc``, ``SD-REQ-002`` is anchored at ``doc/detailed.rst``.
The locator is ``need:`` followed by the need identifier, the extraction key
the requirement schema expects. The join is pure; no file is opened.

The anchor names the source the hashed form is built from. It does not name a
span whose bytes were hashed, because the form is assembled from the export's
fields; recomputing the hash therefore needs the build, not just the file.

Refusal
-------

A reader that cannot serve the export raises
:class:`~affirmatrix.sources.reqs.ReaderError` when it is constructed, before
any record is supplied, so a stream is never silently short. It refuses:

* an export carrying a build timestamp, ``created``, at the top level or in
  the version entry (SEG-SREQ-150): a stamp means the export is not
  reproducible. The null timestamp fields inside needs are not this;
* an export with zero or more than one version. The reader serves one build,
  and choosing between two builds' hashes would be a silent decision;
* an export that is unreadable, not JSON, or without a ``needs`` object;
* a need of a configured type that lacks its identifier, title, content,
  docname or doctype, that declares an identifier other than its key, or whose
  ``refines`` is not a list of identifiers. The message names the need.
