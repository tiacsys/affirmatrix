Affirmation Recorder
====================

An affirmation is a human judgement that an edge still holds, recorded
against the exact content it was judged against. The affirmation recorder
builds that record: what it binds, what anchors it in source history, and the
reason the reviewer gave. It originates nothing on its own, and it accepts an
affirmation only for an edge where one can mean something.

.. sreq:: Affirmations bind both endpoints
   :id: SEG-SREQ-024
   :refines: SEG-SYS-004

   The affirmation recorder shall record each affirmation as a review event
   carrying the content hashes of both endpoints of the affirmed edge.

.. sreq:: Affirmations carry their source anchor
   :id: SEG-SREQ-025
   :refines: SEG-SYS-004

   The affirmation recorder shall record in every review event the source
   commit of each endpoint at the moment of affirmation.

.. sreq:: Affirmations carry the role they were made in
   :id: SEG-SREQ-049
   :refines: SEG-SYS-004

   The affirmation recorder shall record in every review event the role in
   which the affirmation was made.

.. sreq:: The recorder originates nothing
   :id: SEG-SREQ-026
   :refines: SEG-SYS-004

   The affirmation recorder shall originate no affirmation of its own.

.. sreq:: Only unaffirmed or outdated edges are affirmable
   :id: SEG-SREQ-027
   :refines: SEG-SYS-004

   The affirmation recorder shall accept an affirmation only for an edge that
   is pending, directly outdated, or doubly outdated.

.. sreq:: Supplied reasons are preserved
   :id: SEG-SREQ-028
   :refines: SEG-SYS-004

   The affirmation recorder shall record the reason supplied with an
   affirmation in the review event without altering it.
