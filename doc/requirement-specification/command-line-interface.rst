Command Line Interface
=======================

The command-line interface is the operator's front door onto the engine.
Every verb's outcome is the library's alone to decide; the interface only
renders it. What follows is organised by the thing an operator acts on — a
case, the graph, an edge, a node, a package — one section per noun, one requirement
per verb, stating what that verb is for. A shared set of rules then covers
everything every verb obeys alike: how an outcome is reported, how an edge
selection is built, how a judgement's inputs are supplied, and that every
write stays a draft until the operator commits it.

.. sreq:: Only the library decides an outcome
   :id: SEG-SREQ-068
   :refines: SEG-SYS-010

   The command-line interface shall determine every verb's outcome by
   invoking the library alone, performing no judgement of its own beyond
   rendering that outcome.

Case
----

A case written before ADR-0013 can hold test outcome nodes and evidence edges.
The first case sync after the change removes them. The case needs no other
migration step, and its verdicts do not depend on them.

.. sreq:: A case is brought into being, inspected, synced, refreshed, and trimmed
   :id: SEG-SREQ-069
   :refines: SEG-SYS-010

   The command-line interface shall let the operator bring a case into
   being, inspect it, mirror the current stream into it, refresh its
   schema copy, and remove named records from it, each as its own verb.

.. sreq:: case init creates a case
   :id: SEG-SREQ-070
   :refines: SEG-SREQ-069

   The command-line interface shall have case init create a case's layout
   and schema set, succeeding without altering either when the case root
   it is given already carries them.

.. sreq:: case check reports a case's five judgements
   :id: SEG-SREQ-071
   :refines: SEG-SREQ-069

   The command-line interface shall have case check report the case's
   layout, its schema set — naming any schema missing rather than
   supplying one — its record counts, whether its configuration was found
   or defaults were used, and whether its producer is readable.

.. sreq:: case sync writes the derived stream
   :id: SEG-SREQ-072
   :refines: SEG-SREQ-069

   The command-line interface shall write, in response to case sync, the
   derived stream the suspect detector produces from both record sources,
   never the current stream a producer supplies unmodified.

.. sreq:: Syncing never requests a demotion
   :id: SEG-SREQ-073
   :refines: SEG-SREQ-072

   The command-line interface shall never request the demotion of an edge
   when writing case sync's derived stream to the case.

.. sreq:: An unbuildable current stream stops case sync without a write
   :id: SEG-SREQ-136
   :refines: SEG-SREQ-072

   If case sync cannot build the current stream it is given, or cannot
   build a graph from it, then the command-line interface shall write
   nothing to the case and exit with status 2, a request it could not
   judge.

.. sreq:: Vanished edges are reported, not silently dropped
   :id: SEG-SREQ-074
   :refines: SEG-SREQ-072

   The command-line interface shall report every vanished edge case sync's
   derivation finds, other than an edge of kind Confirms, Witnesses or
   Excuses, without removing it from the case.

.. sreq:: case sync writes all or nothing
   :id: SEG-SREQ-212
   :refines: SEG-SREQ-072

   If a record of the derived stream does not validate against the case's schema
   copy, then the command-line interface shall write nothing to the case in
   response to case sync and exit with status 2, a request it could not judge.

.. sreq:: case sync clears the test evidence a case holds
   :id: SEG-SREQ-228
   :refines: SEG-SREQ-072

   When case sync has written the derived stream, the command-line interface
   shall remove from the case every test outcome node and every edge of kind
   Confirms, Witnesses or Excuses that the case holds, naming each.

.. sreq:: case remove takes only what its selector names
   :id: SEG-SREQ-075
   :refines: SEG-SREQ-069

   The command-line interface shall remove, in response to case remove,
   only the edge records its selector names.

.. sreq:: The schema copy is refreshed on request
   :id: SEG-SREQ-141
   :refines: SEG-SREQ-069

   The command-line interface shall let the operator request the refresh of
   a case's schema copy, rendering the differences the affirmation store
   reports.

.. sreq:: case check says why a producer cannot be read
   :id: SEG-SREQ-290
   :refines: SEG-SREQ-069

   If the producer cannot be read, then the command-line interface shall
   have case check report the reason the library gave, in the
   human-readable and in the machine-readable rendering.

Graph
-----

.. sreq:: The operator judges the graph's consistency and every edge's state
   :id: SEG-SREQ-076
   :refines: SEG-SYS-010

   The command-line interface shall let the operator judge whether a
   record stream forms a graph and derive the state of every edge in it,
   each as its own verb.

.. sreq:: graph check reports what the builder knows
   :id: SEG-SREQ-077
   :refines: SEG-SREQ-076

   The command-line interface shall have graph check report node and edge
   counts by kind and the count of pending strong edges, never a count of
   dangling endpoints.

.. sreq:: An unbuildable current stream is graph check's verdict
   :id: SEG-SREQ-078
   :refines: SEG-SREQ-077

   If graph check cannot build a graph from the records it is given, then
   the command-line interface shall exit with status 1, its negative
   verdict.

.. sreq:: A refused graph check prints no counts
   :id: SEG-SREQ-079
   :refines: SEG-SREQ-077

   If graph check refuses, then the command-line interface shall render
   that refusal's report with no count of anything.

.. sreq:: graph status derives every strong edge's state from both streams
   :id: SEG-SREQ-080
   :refines: SEG-SREQ-076

   The command-line interface shall have graph status report, for every
   strong edge, the state the suspect detector derives for it from the
   recorded and the current record sources.

.. sreq:: An unbuildable current stream is graph status's precondition
   :id: SEG-SREQ-081
   :refines: SEG-SREQ-080

   If graph status cannot build a graph from the current stream it is
   given, then the command-line interface shall exit with status 2, a
   request it could not judge.

.. sreq:: Pending edges do not affect graph status's verdict
   :id: SEG-SREQ-082
   :refines: SEG-SREQ-080

   While the only edges graph status reports as not active are pending, the
   command-line interface shall exit with status 0, its positive verdict.

.. sreq:: Graph status's negative verdict names the suspect states and broken
   :id: SEG-SREQ-083
   :refines: SEG-SREQ-080

   While graph status reports any edge as directly outdated, transitively
   suspect, doubly outdated, or broken, or counts an edge of kind Confirms,
   Witnesses or Excuses that touches an absent node, the command-line
   interface shall exit with status 1, its negative verdict.

.. sreq:: graph status lists an edge that has vanished
   :id: SEG-SREQ-137
   :refines: SEG-SREQ-080

   The command-line interface shall have graph status list, without a
   state, every recorded edge that is absent from the current stream.

.. sreq:: A vanished edge does not affect graph status's verdict
   :id: SEG-SREQ-138
   :refines: SEG-SREQ-080

   The command-line interface shall leave a recorded edge that is absent
   from the current stream out of graph status's verdict.

.. sreq:: graph status reports the test evidence apart
   :id: SEG-SREQ-210
   :refines: SEG-SREQ-080

   The command-line interface shall have graph status report the test
   evidence apart from the strong edges, with the count of test outcomes
   recorded at the current revision, the count of test outcomes recorded at
   another revision, and the count of edges of kind Confirms, Witnesses or
   Excuses that touch an absent node.

.. sreq:: graph check says which stream it checked
   :id: SEG-SREQ-291
   :refines: SEG-SREQ-076

   The command-line interface shall have graph check report whether it
   checked the case or the current stream the operator gave, and name what
   it checked by its location: the root of the case, or the location of
   the current stream the operator gave.

Edge
----

.. sreq:: The operator inspects an edge selection and affirms it
   :id: SEG-SREQ-084
   :refines: SEG-SYS-010

   The command-line interface shall let the operator inspect an edge
   selection and record an affirmation over it, each as its own verb.

.. sreq:: edge show renders the per-hash comparison and recovered before-content
   :id: SEG-SREQ-085
   :refines: SEG-SREQ-084

   The command-line interface shall have edge show render, for every edge
   a selection includes, the per-hash comparison of its endpoints and, for
   an edge that has been affirmed, when the verbose rendering is asked for,
   the content recovered at its last affirmation's revision.

When the before-content of an endpoint cannot be read, the entry for that
endpoint in the machine-readable report keeps its ``revision`` and has
``content`` null. It also has an ``error`` key, a text that names the
repository and gives the reason. The key is null or absent when the read
worked. The text rendering prints one line for the endpoint, ``before-content
@ <endpoint> (revision <revision>): not available: <repository>: <reason>``.
The other endpoint keeps its own content.

.. sreq:: edge show reports before-content it cannot read as not available
   :id: SEG-SREQ-365
   :refines: SEG-SREQ-085

   If the content repository that holds an endpoint's before-content cannot
   be read, then the command-line interface shall have edge show report that
   the before-content of that endpoint is not available, naming the
   repository and giving the reason.

.. sreq:: An unreadable before-content does not change the exit of edge show
   :id: SEG-SREQ-366
   :refines: SEG-SREQ-085

   If the content repository that holds an endpoint's before-content cannot
   be read, then the command-line interface shall derive the exit status of
   edge show without regard to it.

.. sreq:: edge affirm records an affirmation over its affirmable members
   :id: SEG-SREQ-086
   :refines: SEG-SREQ-084

   The command-line interface shall, for each affirmable edge a selection
   includes, record an affirmation under the given role and reason,
   writing the review event, the affirmed edge record, and both
   endpoints' current node records.

.. sreq:: A mixed selection affirms its affirmable members
   :id: SEG-SREQ-087
   :refines: SEG-SREQ-086

   While an edge-affirm selection includes at least one affirmable edge,
   the command-line interface shall record an affirmation for each
   affirmable edge in it, list every other selected edge together with the
   reason it is not affirmable, and exit with status 0.

.. sreq:: A selection with no affirmable member is a refusal
   :id: SEG-SREQ-088
   :refines: SEG-SREQ-086

   If an edge-affirm selection includes no affirmable edge, then the
   command-line interface shall list every selected edge with the reason
   it is not affirmable and exit with status 1, its negative verdict.

Who recorded an affirmation
---------------------------

A review event holds the role, the reason, the revisions and the hashes of an
affirmation. It holds no person and no time. The history of the case holds
them: ADR-0009 makes the commit that adds a review event the act of affirming,
and ADR-0015 lets the command line read that history.

The *recording commit* of an affirmation is the earliest commit of the history
of the case whose tree holds the affirmation's review event. The commit that
created the file of review events is not the answer, because every event sits
in that one file. What the history records is text that the committer set. It
is not an authenticated identity, unless the commit is signed and the
signature is verified.

.. sreq:: edge show reports who made the last affirmation and when
   :id: SEG-SREQ-293
   :refines: SEG-SYS-014

   The command-line interface shall have edge show report, for every edge a
   selection includes that has a last affirmation, whatever its current
   state, who made that last affirmation and when, as the recording commit of
   that affirmation records it.

.. sreq:: The committer and the commit date are the identity and the time
   :id: SEG-SREQ-294
   :refines: SEG-SREQ-293

   The command-line interface shall report the committer of an affirmation's
   recording commit as the identity, and the date of that commit as the time.

.. sreq:: A different author is reported too
   :id: SEG-SREQ-295
   :refines: SEG-SREQ-293

   Where the author (name and e-mail) of an affirmation's recording commit
   differs from its committer, the command-line interface shall report the
   author and the author date as well.

.. sreq:: Signed-off-by lines are reported as written
   :id: SEG-SREQ-296
   :refines: SEG-SREQ-293

   Where the message of an affirmation's recording commit carries Signed-off-by
   lines, the command-line interface shall report each of them as written.

.. sreq:: The signature status is reported
   :id: SEG-SREQ-297
   :refines: SEG-SREQ-293

   The command-line interface shall report whether an affirmation's recording
   commit is signed and, where it is, the result of the verification the
   version-control system gives for the signature.

.. sreq:: The identity is what the history records, never verified
   :id: SEG-SREQ-298
   :refines: SEG-SREQ-293

   The command-line interface shall present the identity and the time of an
   affirmation as what the history of the case records, and shall not present
   either as verified.

.. sreq:: The recording commit is named
   :id: SEG-SREQ-299
   :refines: SEG-SREQ-293

   The command-line interface shall report the identifier and the subject line
   of an affirmation's recording commit.

.. sreq:: An affirmation no commit holds is reported as not committed
   :id: SEG-SREQ-300
   :refines: SEG-SREQ-293

   If no commit of the history of the case holds the review event of an edge's
   last affirmation, then the command-line interface shall report that the
   affirmation is not committed, and shall report no identity and no time for
   it.

.. sreq:: A case without readable history reports none
   :id: SEG-SREQ-301
   :refines: SEG-SREQ-293

   If the case is not a repository of its own, or its history cannot be read,
   then the command-line interface shall report that the history of the case
   is not available, and shall report no identity and no time.

.. sreq:: A shallow history is reported
   :id: SEG-SREQ-302
   :refines: SEG-SREQ-293

   While the history of the case is shallow, the command-line interface shall
   report that it is shallow with every identity it reports.

.. sreq:: The history never changes edge show's exit status
   :id: SEG-SREQ-303
   :refines: SEG-SREQ-293

   The command-line interface shall derive edge show's exit status without
   regard to what the history of the case records.

Node
----

A node is addressed by its case-local identifier. ``node show`` compares what
the case recorded for the node with what the current stream supplies now. It
reads the node records of both and builds no graph, so a hash that one side
holds and the other does not reaches its report.

.. sreq:: The operator shows a node by its identifier
   :id: SEG-SREQ-313
   :refines: SEG-SYS-015

   The command-line interface shall let the operator show a node by its
   identifier, as its own verb.

.. sreq:: node show compares every named content hash
   :id: SEG-SREQ-314
   :refines: SEG-SREQ-313

   The command-line interface shall have node show report, for each named
   content hash of the node, the comparison the suspect detector gives between
   the current digest and the digest the case records for it.

.. sreq:: node show shows the current content of every hash
   :id: SEG-SREQ-315
   :refines: SEG-SREQ-313

   The command-line interface shall have node show report, for each named
   content hash of the node, the content the record source of the current
   stream supplies for it.

.. sreq:: A hash with no supplied content says so
   :id: SEG-SREQ-316
   :refines: SEG-SREQ-313

   If the record source of the current stream supplies no content for a content
   hash, then the command-line interface shall have node show report that none
   is supplied for it.

.. sreq:: node show reports the recorded extraction revision
   :id: SEG-SREQ-317
   :refines: SEG-SREQ-313

   The command-line interface shall have node show report, with each named
   content hash, the extraction revision the case records for the repository
   that the hash's recorded anchor names, or report that none is recorded.

.. sreq:: node show reports the checkout's revision
   :id: SEG-SREQ-318
   :refines: SEG-SREQ-313

   The command-line interface shall have node show report, for the repository
   each content hash's current anchor names, the revision that repository is
   at, or report that no repository is configured for it.

.. sreq:: node show reports the checkout's cleanliness
   :id: SEG-SREQ-319
   :refines: SEG-SREQ-313

   The command-line interface shall have node show report, for each such
   repository, whether the content at the paths the node's anchors name matches
   its committed content, naming each path that differs.

.. sreq:: Matching hashes are the positive verdict
   :id: SEG-SREQ-320
   :refines: SEG-SREQ-313

   While every named content hash of the node is reported as matching, the
   command-line interface shall exit with status 0 from node show, its positive
   verdict, whether or not a repository differs from its committed content.

.. sreq:: A differing hash is the negative verdict
   :id: SEG-SREQ-321
   :refines: SEG-SREQ-313

   While a named content hash of the node is reported as differing or as on one
   side only, or the current stream holds no such node, the command-line
   interface shall exit with status 1 from node show, its negative verdict.

.. sreq:: An identifier the case does not hold cannot be judged
   :id: SEG-SREQ-322
   :refines: SEG-SREQ-313

   If the case holds no node with the identifier given to node show, then the
   command-line interface shall exit with status 2, a request it could not
   judge, naming the identifier.

.. sreq:: An unreadable current stream cannot be judged
   :id: SEG-SREQ-323
   :refines: SEG-SREQ-313

   If node show cannot read the current stream it is given, then the
   command-line interface shall exit with status 2, a request it could not
   judge.

.. sreq:: node show writes nothing
   :id: SEG-SREQ-324
   :refines: SEG-SREQ-313

   The command-line interface shall write nothing in response to node show.

.. sreq:: node show renders content without loss
   :id: SEG-SREQ-328
   :refines: SEG-SREQ-315

   The command-line interface shall render the content node show reports for
   a content hash, in the machine-readable rendering, as the text the bytes
   encode where they are valid UTF-8, and otherwise as their base64 encoding
   together with the name of that encoding.

.. sreq:: An identifier the current stream holds twice cannot be judged
   :id: SEG-SREQ-329
   :refines: SEG-SREQ-313

   If the current stream holds more than one node with the identifier given
   to node show, then the command-line interface shall exit with status 2, a
   request it could not judge, naming the identifier.

.. sreq:: A hash recorded only in the case has no current content
   :id: SEG-SREQ-330
   :refines: SEG-SREQ-313

   If a named content hash of the node is recorded only in the case's node
   record, then the command-line interface shall have node show report that
   it has no current content, and report no checkout for it.

.. sreq:: A repository that cannot be read is reported with the reason
   :id: SEG-SREQ-331
   :refines: SEG-SREQ-318

   If a configured repository that a content hash's current anchor names
   cannot be read, then the command-line interface shall have node show
   report that it cannot be read, with the reason, and derive node show's
   exit status without regard to it.

Proof
-----

.. sreq:: The operator asks the gate about a scope, generates the package, and shows and verifies a package
   :id: SEG-SREQ-089
   :refines: SEG-SYS-010

   The command-line interface shall let the operator ask the proof gate
   about a scope's readiness, generate an evidence package for it, and show
   and verify an evidence package, each as its own verb.

.. sreq:: proof check reports the gate's coverage verdict
   :id: SEG-SREQ-090
   :refines: SEG-SREQ-089

   The command-line interface shall have proof check report the coverage
   the gate finds for a requested scope, without generating a package.

.. sreq:: Proof check's machine-readable output is the coverage report
   :id: SEG-SREQ-091
   :refines: SEG-SREQ-090

   For proof check, the command-line interface shall render its
   machine-readable output as exactly the coverage report the gate
   produced.

.. sreq:: proof generate assembles and persists the package, or refuses
   :id: SEG-SREQ-092
   :refines: SEG-SREQ-089

   The command-line interface shall have proof generate assemble and
   persist an evidence package for a requested scope when the gate finds
   it ready, and refuse with the gate's report otherwise.

.. sreq:: Generation defaults to the case
   :id: SEG-SREQ-093
   :refines: SEG-SREQ-092

   While proof generate is given no output directory, the command-line
   interface shall write the generated package under the case.

.. sreq:: An output directory relocates generation's write root
   :id: SEG-SREQ-094
   :refines: SEG-SREQ-092

   Where proof generate is given an output directory, the command-line
   interface shall write the whole generated package under it instead of
   the case.

.. sreq:: proof show reports a package
   :id: SEG-SREQ-247
   :refines: SEG-SREQ-089

   The command-line interface shall let the operator show an evidence
   package, as its own verb.

.. sreq:: A package is named three ways
   :id: SEG-SREQ-248
   :refines: SEG-SREQ-247

   The command-line interface shall let the operator name an evidence
   package for proof show and proof verify by its snapshot identifier, by a
   unique prefix of that identifier, or by the path of its directory.

.. sreq:: An ambiguous prefix is refused
   :id: SEG-SREQ-249
   :refines: SEG-SREQ-247

   If a prefix names more than one evidence package, then the command-line
   interface shall exit with status 2, a request it could not judge, naming
   the packages.

.. sreq:: proof show reports what the package records
   :id: SEG-SREQ-250
   :refines: SEG-SREQ-247

   The command-line interface shall have proof show report an evidence
   package's snapshot, requested scope, member scope, revision, totality,
   design root, run bundle digests and the gate's recorded findings, and, for
   each requirement in the scope, the specifications, outcomes and
   implementations the package records for it.

.. sreq:: A legacy package says its digests are not recorded
   :id: SEG-SREQ-251
   :refines: SEG-SREQ-247

   Where an evidence package records no run bundle digest, the command-line
   interface shall have proof show report that none is recorded.

.. sreq:: proof show reads the package alone
   :id: SEG-SREQ-252
   :refines: SEG-SREQ-247

   The command-line interface shall read no run bundle and no current stream
   in proof show.

.. sreq:: proof show judges nothing
   :id: SEG-SREQ-253
   :refines: SEG-SREQ-247

   When proof show has read the package, the command-line interface shall
   exit with status 0, whatever the package records.

.. sreq:: proof verify checks a package
   :id: SEG-SREQ-255
   :refines: SEG-SREQ-089

   The command-line interface shall let the operator verify an evidence
   package with the checks of the proof verifier, as its own verb.

.. sreq:: Every check is named
   :id: SEG-SREQ-256
   :refines: SEG-SREQ-255

   The command-line interface shall have proof verify report each check by
   name as passed, failed or not judged, and name each check it did not make.

.. sreq:: Bundles are named at invocation for verification
   :id: SEG-SREQ-257
   :refines: SEG-SREQ-255

   Where an invocation of proof verify names run bundles, the command-line
   interface shall give exactly those run bundles to the proof verifier.

.. sreq:: Affirmations are checked on request
   :id: SEG-SREQ-258
   :refines: SEG-SREQ-255

   Where an invocation of proof verify asks for the affirmations to be
   checked, the command-line interface shall give the case of that
   invocation to the proof verifier.

.. sreq:: A failed check is the negative verdict
   :id: SEG-SREQ-259
   :refines: SEG-SREQ-255

   If a check of proof verify fails, then the command-line interface shall
   exit with status 1, its negative verdict.

.. sreq:: An unjudged check is a request it could not judge
   :id: SEG-SREQ-260
   :refines: SEG-SREQ-255

   While no check of proof verify has failed and a check it was asked to make
   cannot be judged, the command-line interface shall exit with status 2, a
   request it could not judge.

.. sreq:: A verified package is the positive verdict
   :id: SEG-SREQ-261
   :refines: SEG-SREQ-255

   While every check of proof verify that was made has passed and every
   check it was asked to make was judged, the command-line interface shall
   exit with status 0, its positive verdict.

.. sreq:: proof verify needs no revision
   :id: SEG-SREQ-262
   :refines: SEG-SREQ-255

   The command-line interface shall obtain no implementation revision for
   proof verify.

.. sreq:: show and verify write nothing
   :id: SEG-SREQ-263
   :refines: SEG-SREQ-089

   The command-line interface shall write nothing in response to proof show
   and proof verify.

.. sreq:: A package named by its path is read without a configuration or a case
   :id: SEG-SREQ-270
   :refines: SEG-SREQ-089

   Where an invocation of proof show or proof verify names an evidence
   package by the path of its directory, the command-line interface shall
   read that package whether or not a configuration file or a case exists.

Outcome vocabulary
-------------------

.. sreq:: Every verb reports its outcome through one vocabulary
   :id: SEG-SREQ-095
   :refines: SEG-SYS-010

   The command-line interface shall report every verb's outcome through one
   shared vocabulary of exit status and rendered report, distinguishing a
   positive verdict, a negative verdict, and a request it could not judge.

.. sreq:: Exit status names three classes of outcome
   :id: SEG-SREQ-096
   :refines: SEG-SREQ-095

   The command-line interface shall exit with one of three statuses: 0 for
   the command's positive verdict, 1 for its negative verdict acted on, and
   2 when it could not judge the request at all.

.. sreq:: A refusal is rendered with its report
   :id: SEG-SREQ-097
   :refines: SEG-SREQ-095

   If a verb's outcome is a refusal, then the command-line interface shall
   render to the operator the report the library returned with that
   refusal.

.. sreq:: Machine-readable output mirrors the report
   :id: SEG-SREQ-098
   :refines: SEG-SREQ-095

   The command-line interface shall offer, for every read-only verb, a
   machine-readable rendering that structures the same report its
   human-readable rendering presents.

.. sreq:: A refused store read is a request it could not judge
   :id: SEG-SREQ-211
   :refines: SEG-SREQ-095

   If the affirmation store refuses a read, then the command-line interface shall
   render that refusal and exit with status 2, a request it could not judge.

.. sreq:: A refused run bundle cannot be judged
   :id: SEG-SREQ-231
   :refines: SEG-SREQ-095

   If the outcome extractor refuses a run, then the command-line interface
   shall exit with status 2, a request it could not judge, and report no
   verdict.

.. sreq:: An unreadable package cannot be judged
   :id: SEG-SREQ-254
   :refines: SEG-SREQ-095

   If the evidence package named to proof show or proof verify cannot be
   read, then the command-line interface shall exit with status 2, a request
   it could not judge.

Edge selection
--------------

.. sreq:: An edge selection is built from one grammar
   :id: SEG-SREQ-099
   :refines: SEG-SYS-010

   The command-line interface shall address every edge selection — for
   show, affirm, and remove alike — through one grammar of narrowing
   fields, rather than a distinct address form per verb.

.. sreq:: An edge selector narrows uniformly
   :id: SEG-SREQ-100
   :refines: SEG-SREQ-099

   The command-line interface shall narrow an edge selection by any
   combination of kind, either endpoint, and subtree, each restricting the
   set the others admit.

A selection by subtree takes only the edges inside the subtree. The subtree
of a requirement is that requirement and every requirement that refines it.
The edge from the named requirement to its own parent is not selected. An
edge that leaves the subtree is reached with ``--from`` and ``--to``.

.. sreq:: The subtree of a requirement
   :id: SEG-SREQ-345
   :refines: SEG-SREQ-100

   The command-line interface shall take the subtree of a requirement as
   that requirement and every requirement that refines it, directly or
   through other requirements, and no other node.

.. sreq:: A Refines edge is in a subtree when both ends are
   :id: SEG-SREQ-346
   :refines: SEG-SREQ-100

   When an edge selection narrows by subtree, the command-line interface
   shall admit a Refines edge when, and only when, both of its endpoints
   lie in the subtree.

.. sreq:: A Verifies or Implements edge is in a subtree by its requirement
   :id: SEG-SREQ-347
   :refines: SEG-SREQ-100

   When an edge selection narrows by subtree, the command-line interface
   shall admit a Verifies edge or an Implements edge when, and only
   when, the requirement that edge names lies in the subtree.

.. sreq:: A subtree selection admits only Refines, Verifies and Implements edges
   :id: SEG-SREQ-371
   :refines: SEG-SREQ-100

   When an edge selection narrows by subtree, the command-line interface
   shall admit no edge of a kind other than Refines, Verifies and
   Implements.

.. sreq:: A subtree of a node that is not a requirement admits no edge
   :id: SEG-SREQ-372
   :refines: SEG-SREQ-100

   When an edge selection narrows by subtree and the identifier it names
   is not that of a requirement of the graph, the command-line interface
   shall admit no edge.

.. sreq:: Kind and both endpoints together address at most one edge
   :id: SEG-SREQ-101
   :refines: SEG-SREQ-099

   While an edge selection narrows by kind and by both its source and its
   target, the command-line interface shall select at most one edge.

.. sreq:: A selector's fields are never one joined token
   :id: SEG-SREQ-102
   :refines: SEG-SREQ-099

   The command-line interface shall accept an edge selector's kind, source,
   and target as separate values, never as one combined token.

.. sreq:: A selector matching nothing cannot be judged
   :id: SEG-SREQ-103
   :refines: SEG-SREQ-099

   If an edge selector matches no edge, then the command-line interface
   shall exit with status 2, a request it could not judge.

.. sreq:: An affirmation needs an explicit selection
   :id: SEG-SREQ-104
   :refines: SEG-SREQ-099

   If edge affirm is given no selector at all, then the command-line
   interface shall exit with status 2, a request it could not judge.

Judgement inputs
-----------------

``graph status``, ``proof check`` and ``proof generate`` take a run bundle as the
option ``--bundle``, which may be given more than once. A relative path is taken
from the working directory.

.. sreq:: A judgement's inputs are explicit, discovered, or refused
   :id: SEG-SREQ-105
   :refines: SEG-SYS-010

   The command-line interface shall supply every value a judgement depends
   on — an affirmation's role, reason, and source revisions, the package
   gate's implementation revision, the run bundles that supply the test
   evidence, and the current stream a comparison is made
   against — either as an explicit input, as
   a value it discovers under one checked rule, or as a refusal when
   neither is available.

.. sreq:: A role and a reason, possibly empty, are required to affirm
   :id: SEG-SREQ-106
   :refines: SEG-SREQ-105

   The command-line interface shall require an explicit role and an
   explicit reason — which may be empty — for every affirmation, supplying
   neither as a default.

.. sreq:: A source revision is discovered by default
   :id: SEG-SREQ-107
   :refines: SEG-SREQ-105

   Where an endpoint's anchor names a repository and no revision is given,
   the command-line interface shall discover that endpoint's source
   revision from the repository the anchor names.

.. sreq:: A dirty anchor refuses a discovered revision
   :id: SEG-SREQ-108
   :refines: SEG-SREQ-105

   If the content an endpoint's anchors name differs from the content
   committed at a discovered revision, then the command-line interface
   shall refuse to record that revision, naming the differing paths.

.. sreq:: A given revision overrides discovery
   :id: SEG-SREQ-109
   :refines: SEG-SREQ-105

   While a revision is given for an endpoint, the command-line interface
   shall record that revision as given, neither discovering nor checking
   it.

.. sreq:: An anchor with no repository needs an explicit revision
   :id: SEG-SREQ-110
   :refines: SEG-SREQ-105

   Where no repository stands behind an endpoint's anchor, the
   command-line interface shall require a revision to be given explicitly
   for that endpoint.

.. sreq:: Before-content is recovered for display
   :id: SEG-SREQ-111
   :refines: SEG-SREQ-105

   When an edge is rendered for a reviewer's judgement or for inspection,
   the command-line interface shall recover, for display only, the content
   an anchor names as it stood at a review event's recorded revision.

.. sreq:: The implementation revision is given, or discovered from a clean repository
   :id: SEG-SREQ-112
   :refines: SEG-SREQ-105

   The command-line interface shall obtain the implementation repository's
   revision for proof check, proof generate and, where the current stream
   holds a test outcome, graph status as given when given, and otherwise by
   discovery, refused when the repository's content differs from its
   committed content, an untracked file included, naming the differing
   paths.

A revision given with ``--revision`` is neither discovered nor checked. So an
unreadable content repository does not stop edge affirm when a revision is
given. The rules for extraction revisions apply to the node records it writes.

.. sreq:: edge affirm refuses when it cannot read a repository it needs
   :id: SEG-SREQ-363
   :refines: SEG-SREQ-105

   If edge affirm reads a content repository to discover or to check the
   source revision of an endpoint, and that repository cannot be read, then
   the command-line interface shall refuse the request, naming the repository
   and giving the reason, and exit with status 2, a request it could not
   judge.

.. sreq:: A refused edge affirm writes nothing
   :id: SEG-SREQ-364
   :refines: SEG-SREQ-086

   If the command-line interface refuses edge affirm because a content
   repository cannot be read, then it shall write no review event, no edge
   record and no node record.

.. sreq:: The implementation repository that cannot be read is named
   :id: SEG-SREQ-367
   :refines: SEG-SREQ-208

   If proof check, proof generate or, where the current stream holds a test
   outcome, graph status needs the implementation revision and the
   implementation repository cannot be read, then the command-line interface
   shall report that it cannot be read, naming the repository and giving the
   reason.

.. sreq:: A proof generate that cannot read the implementation repository writes nothing
   :id: SEG-SREQ-368
   :refines: SEG-SREQ-208

   If the implementation repository cannot be read, then the command-line
   interface shall have proof generate write no evidence package.

.. sreq:: A configured role vocabulary is enforced
   :id: SEG-SREQ-113
   :refines: SEG-SREQ-105

   Where a role vocabulary is configured, the command-line interface shall
   refuse an affirmation whose role lies outside it.

.. sreq:: A comparison needs a current stream or a configured producer
   :id: SEG-SREQ-142
   :refines: SEG-SREQ-105

   If a verb that derives from, or compares, both record sources is given
   no current stream and no producer is configured, then the command-line interface
   shall exit with status 2, a request it could not judge.

.. sreq:: The current stream comes from the first source that is present
   :id: SEG-SREQ-202
   :refines: SEG-SREQ-105

   When a verb needs the current stream, the command-line interface shall
   take it from the first of these that is present: the stream the operator
   gives, the streams read from the producer's configured inputs, the
   producer at its configured location.

.. sreq:: No obtainable revision cannot be judged
   :id: SEG-SREQ-208
   :refines: SEG-SREQ-105

   If the command-line interface can obtain no implementation revision for
   proof check, proof generate or, where the current stream holds a test
   outcome, graph status, then it shall exit with status 2, a request it
   could not judge.

.. sreq:: The verbs that judge evidence build it from the run bundles the invocation names
   :id: SEG-SREQ-229
   :refines: SEG-SYS-013

   Where an invocation of graph status, proof check or proof generate names
   run bundles, the command-line interface shall include the test evidence of
   exactly those run bundles in the current stream of that invocation.

.. sreq:: The other verbs read no run bundle
   :id: SEG-SREQ-230
   :refines: SEG-SYS-013

   The command-line interface shall read no run bundle in case sync, case
   check, graph check, node show, edge show and edge affirm.

.. sreq:: A bundle named twice is read once
   :id: SEG-SREQ-232
   :refines: SEG-SYS-013

   When an invocation of graph status, proof check or proof generate names
   one run bundle more than once, the command-line interface shall read that
   run bundle once.

.. sreq:: A named bundle and a given stream cannot be judged together
   :id: SEG-SREQ-233
   :refines: SEG-SYS-013

   If an invocation of graph status, proof check or proof generate names a
   run bundle and gives a current stream, then the command-line interface
   shall exit with status 2, a request it could not judge.

.. sreq:: Named bundles need a test-case export
   :id: SEG-SREQ-235
   :refines: SEG-SYS-013

   If an invocation of graph status, proof check or proof generate names a
   run bundle and the configuration gives no test-case export, then the
   command-line interface shall exit with status 2, a request it could not
   judge.

.. sreq:: A reader with no usable repository cannot be judged
   :id: SEG-SREQ-292
   :refines: SEG-SREQ-105

   If a configured reader has no repository, or the repository it names is
   absent from the repository map, then the command-line interface shall
   exit with status 2, a request it could not judge, naming the reader.

Extraction revisions
--------------------

An *extraction revision* is the revision of a repository at which the content
behind a node record's content hashes was read (ADR-0016). The revision of a
repository *can be discovered* for a node when the repository is configured and
can be read, and holds the committed content at every path the node's content
anchors name in it. A revision the operator gives is an assertion. The command
line never records it as an extraction revision.

.. sreq:: A written node record carries the extraction revisions of its repositories
   :id: SEG-SREQ-306
   :refines: SEG-SYS-007

   When the command-line interface writes a node record whose content hashes
   are not those the case holds for that node, or holds none, it shall record
   with the node record, for each repository the node's content anchors name
   whose revision can be discovered, that revision as the extraction revision.

.. sreq:: A missing extraction revision is added when the hashes are unchanged
   :id: SEG-SREQ-307
   :refines: SEG-SREQ-306

   When the command-line interface writes a node record whose content hashes
   equal those the case holds for that node, and the case holds no extraction
   revision for a repository the node's content anchors name whose revision can
   be discovered, it shall record that revision as the extraction revision.

.. sreq:: A held extraction revision is kept while the hashes are unchanged
   :id: SEG-SREQ-308
   :refines: SEG-SREQ-306

   When the command-line interface writes a node record whose content hashes
   equal those the case holds for that node, it shall keep the extraction
   revision the case holds for each repository the node's content anchors
   name, and keep none for another repository.

.. sreq:: A stale extraction revision is dropped
   :id: SEG-SREQ-309
   :refines: SEG-SREQ-306

   If a node record's content hashes are not those the case holds for it, and
   the revision of a repository its content anchors name cannot be discovered,
   then the command-line interface shall write the node record with no
   extraction revision for that repository, and shall not keep the one the case
   holds.

.. sreq:: Records written without an extraction revision are reported
   :id: SEG-SREQ-310
   :refines: SEG-SREQ-306

   When the command-line interface writes node records with no extraction
   revision for a repository because its revision cannot be discovered, it
   shall report each such repository and the number of node records written
   without a revision for it.

.. sreq:: A revision the operator gives is never an extraction revision
   :id: SEG-SREQ-327
   :refines: SEG-SREQ-306

   The command-line interface shall not record a revision the operator gives
   on the command line as an extraction revision.

Draft posture
-------------

.. sreq:: Every write is a draft the operator commits
   :id: SEG-SREQ-114
   :refines: SEG-SYS-010

   The command-line interface shall leave every write it makes short of a
   repository or version-control act, so nothing it does becomes
   irreversible without the operator's own act.

.. sreq:: No write reaches a source repository
   :id: SEG-SREQ-115
   :refines: SEG-SREQ-114

   The command-line interface shall perform no write operation against a
   source repository.

.. sreq:: No version-control write reaches the case
   :id: SEG-SREQ-116
   :refines: SEG-SREQ-114

   The command-line interface shall perform no version-control operation
   against the case that changes the case, its history, its index or its
   working tree.

Repository reads
----------------

A content repository cannot be read when a read of it fails. A read fails when
the version-control system is not on the path, when the repository is absent
or is not a repository, when its objects are missing, when it does not hold
the revision or the path asked for, or when any part of a read made in parts
fails. A repository that is not configured is a different case.

This meaning belongs to reads made through the version-control system. It
differs from the check of the content extractor, which reads files: that
check refuses a repository path that does not exist or is not a directory,
and a directory that holds the files but no history passes it.

The command line reads a content repository, and the history of the case,
by running the version-control system in that repository. The answer must
come from the repository at the path the read is given. It must not come
from a repository that the environment of the operator names.


.. sreq:: A repository read answers from the repository at its path
   :id: SEG-SREQ-332
   :refines: SEG-SYS-010

   The command-line interface shall answer every repository read from the
   repository at the path the read is given, whatever repository the
   environment names.

.. sreq:: A repository read drops the variables that name a repository
   :id: SEG-SREQ-333
   :refines: SEG-SREQ-332

   The command-line interface shall perform every repository read, in a
   content repository and in the repository of the case, with the
   environment variables GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE,
   GIT_OBJECT_DIRECTORY, GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_COMMON_DIR
   and GIT_NAMESPACE removed.

.. sreq:: A read of very many paths is made in parts
   :id: SEG-SREQ-334
   :refines: SEG-SREQ-332

   If a repository read names more paths than one call of the
   version-control system accepts, then the command-line interface shall
   perform the read in parts and give the answer that one call would give.

.. sreq:: A part that fails fails the read
   :id: SEG-SREQ-335
   :refines: SEG-SREQ-332

   If any part of a read made in parts fails, then the command-line
   interface shall treat the repository as one that cannot be read.
