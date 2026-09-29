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

   If case sync cannot build a graph from the current stream it is given,
   then the command-line interface shall write nothing to the case and exit
   with status 2, a request it could not judge.

.. sreq:: Vanished edges are reported, not silently dropped
   :id: SEG-SREQ-074
   :refines: SEG-SREQ-072

   The command-line interface shall report every vanished edge case sync's
   derivation finds, without removing it from the case.

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
   counts by kind and the count of pending edges, never a count of dangling
   endpoints.

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

.. sreq:: graph status derives every edge's state from both streams
   :id: SEG-SREQ-080
   :refines: SEG-SREQ-076

   The command-line interface shall have graph status report, for every
   edge, the state the suspect detector derives for it from the recorded
   and the current record sources.

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
   suspect, doubly outdated, or broken, the command-line interface shall
   exit with status 1, its negative verdict.

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

.. sreq:: The operator asks the gate about a scope and generates the package
   :id: SEG-SREQ-089
   :refines: SEG-SYS-010

   The command-line interface shall let the operator ask the proof gate
   about a scope's readiness and generate an evidence package for it, each
   as its own verb.

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

.. sreq:: A judgement's inputs are explicit, discovered, or refused
   :id: SEG-SREQ-105
   :refines: SEG-SYS-010

   The command-line interface shall supply every value a judgement depends
   on — an affirmation's role, reason, and source revisions, the package
   gate's implementation revision, and the current stream a comparison is
   made against — either as an explicit input, as
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

.. sreq:: The gate's revision follows the same rule as an affirmation endpoint's
   :id: SEG-SREQ-112
   :refines: SEG-SREQ-105

   The command-line interface shall obtain the implementation repository's
   revision for proof check and proof generate under the same rule as an
   affirmation endpoint's revision: recorded as given when given, otherwise
   discovered and refused when the anchored content differs from the
   committed content.

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
