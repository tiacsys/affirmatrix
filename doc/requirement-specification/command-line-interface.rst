Command Line Interface
=======================

The command-line interface is the operator's front door onto the engine.
Every verb's outcome is the library's alone to decide; the interface only
renders it. What follows is organised by the thing an operator acts on — a
case, the graph, an edge, a package — one section per noun, one requirement
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
   it checked by its location: the root of the case, or the configuration
   file whose producer it read.

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
   an edge that has been affirmed, the content recovered at its last
   affirmation's revision.

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

.. sreq:: A configured role vocabulary is enforced
   :id: SEG-SREQ-113
   :refines: SEG-SREQ-105

   Where a role vocabulary is configured, the command-line interface shall
   refuse an affirmation whose role lies outside it.

.. sreq:: A comparison needs a current stream or a configured producer
   :id: SEG-SREQ-142
   :refines: SEG-SREQ-105

   If a verb that derives from both record sources is given no current
   stream and no producer is configured, then the command-line interface
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
   check, graph check, edge show and edge affirm.

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

.. sreq:: No version-control operation reaches the case
   :id: SEG-SREQ-116
   :refines: SEG-SREQ-114

   The command-line interface shall perform no version-control operation
   against the case.
