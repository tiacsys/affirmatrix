Requirements Reader
===================

The requirements reader turns a build-published requirement export into
Requirement records. It reads the export a documentation build wrote, not the
source files the build read, and it accepts that export only when the build
was reproducible, because a hash over content that changes between two
builds of one commit would prove nothing. It serves this repository's own
export and any other producer's the same way; which need types are
Requirements is configuration, never inference.

A Requirement's content is what its authors wrote: the title, the statement
and the links to the requirements it refines. Its status and tags change as a
review moves, without the statement changing, so they are metadata; so are
the back-links, sections, positions and rendering the build derives. Because
the hashed form is built from the export, the anchor below names the source
file that form is built from; recomputing the hash needs the build.

.. sreq:: The requirements reader supplies Requirements from an export
   :id: SEG-SREQ-144
   :refines: SEG-SYS-001

   The requirements reader shall supply Requirement records from the
   requirement export it is given.

.. sreq:: Configured need types, and only those, are Requirements
   :id: SEG-SREQ-145
   :refines: SEG-SREQ-144

   The requirements reader shall supply a Requirement record for a need
   when, and only when, the need's type is one of the requirement types it
   is configured with.

.. sreq:: A Requirement is identified by its need identifier
   :id: SEG-SREQ-146
   :refines: SEG-SREQ-144

   The requirements reader shall identify each Requirement record by the
   identifier of its need, verbatim.

.. sreq:: A Requirement's content is its authored fields
   :id: SEG-SREQ-147
   :refines: SEG-SREQ-144

   The requirements reader shall compute each Requirement's content hash
   from the canonical serialization of the need's title, content and
   refines links, and from no other field of the need.

.. sreq:: Link order does not change a Requirement's content hash
   :id: SEG-SREQ-148
   :refines: SEG-SREQ-144

   The requirements reader shall compute the same content hash for a need
   irrespective of the order in which the export lists its refines links.

.. sreq:: Refines edges come from declared links only
   :id: SEG-SREQ-149
   :refines: SEG-SREQ-144

   The requirements reader shall derive Refines edges from the refines
   links each need declares, and from no back-link field.

.. sreq:: An export with build timestamps is refused
   :id: SEG-SREQ-150
   :refines: SEG-SREQ-144

   If the requirement export carries a build timestamp, then the
   requirements reader shall refuse the export instead of supplying
   records from it.

.. sreq:: A Requirement's anchor names its source file and its need
   :id: SEG-SREQ-151
   :refines: SEG-SREQ-143

   The requirements reader shall anchor each Requirement's content hash at
   the need's source file within its repository, the file the need's
   docname and doctype name under the configured source directory, with
   the locator need:<need identifier>.
