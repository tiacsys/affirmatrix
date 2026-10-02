Command line and configuration
================================

The command line is the thin adapter over the three workflows: consistency
(``graph check``), suspect detection (``graph status``), and evidence
generation (``proof check``/``generate``, and ``proof show``/``verify`` for a package that exists), with ``case``, ``node`` and ``edge`` around
them so an operator can drive all three on a real case without a Python
script. Every verb's outcome is the library's alone (:mod:`affirmatrix.cli`);
this page states what each verb calls, how an exit status is decided, the
four repository reads the adapter alone may perform, the configuration
loader's keys, and a few facts an operator needs that the requirement text
does not spell out on its own: the hex-shaped revision, the repository-name
lookup miss, and the two different scopes a cleanliness check can have.

Fourteen commands, one dispatch entry
---------------------------------------

``affirmatrix <noun> <verb>``, parsed and dispatched by
:func:`affirmatrix.cli.main`:

============  ==================  =============================================================
Noun          Verb                Library call
============  ==================  =============================================================
``case``      ``init``            :meth:`~affirmatrix.case.AffirmationStore.initialize`
``case``      ``check``           :meth:`~affirmatrix.case.AffirmationStore.layout`,
                                   :meth:`~affirmatrix.case.AffirmationStore.missing_schemas`,
                                   record counts
``case``      ``sync``            :func:`~affirmatrix.drift.derive`, then the extraction
                                   revisions (``cli/_extraction.py``), then
                                   :meth:`~affirmatrix.case.AffirmationStore.write_records`,
                                   then the removal of held test evidence
``case``      ``refresh``         :meth:`~affirmatrix.case.AffirmationStore.refresh_schemas`
``case``      ``remove``          :meth:`~affirmatrix.case.AffirmationStore.remove_edges`
``graph``     ``check``           :func:`affirmatrix.graph.build`
``graph``     ``status``          :func:`~affirmatrix.drift.derive`
``node``      ``show``            :func:`~affirmatrix.drift.compare_node`, then the
                                   checkout reads and the content of the current
                                   stream (``cli/_node.py``)
``edge``      ``show``            :func:`~affirmatrix.drift.compare` against
                                   :meth:`~affirmatrix.case.AffirmationStore.latest_review_event`,
                                   then the history of the case
                                   (``cli/_provenance.py``)
``edge``      ``affirm``          :func:`affirmatrix.affirmation.affirmable` /
                                   :func:`~affirmatrix.affirmation.compose`
``proof``     ``check``           :func:`affirmatrix.proof.check_readiness`
``proof``     ``generate``        :func:`affirmatrix.proof.assemble` /
                                   :func:`~affirmatrix.proof.persist`
``proof``     ``show``            :func:`affirmatrix.proof.read_package`,
                                   :func:`~affirmatrix.proof.summarize`
``proof``     ``verify``          :func:`affirmatrix.proof.verify`
============  ==================  =============================================================

A verb that needs the current stream (every one but ``case init``) resolves
it in one order. Only ``graph status``, ``proof check`` and ``proof generate``
read run bundles into it (see "Test evidence" below).

``--current <path>`` names a would-be store explicitly and wins. Otherwise the
producer is composed from the configuration: the requirements reader when
``producer.requirements`` is set, then the content extractor when
``producer.implementations`` or ``producer.specifications`` is set, then the
outcome extractor over the bundles named with ``--bundle``, chained in that
order into one stream (:func:`affirmatrix.sources.composed.from_config`). Only
when the configuration names no reader does ``producer.root`` (the would-be
store) apply. Absent all of them, or when a configured input cannot be read, the
command exits 2: it was asked to judge something with no second stream to
compare against.

Each reader anchors its records to one repository, by name and by
repository-relative path. That is the repository its own block names with
``repository``, or else the one ``producer.repository`` names
(:need:`SEG-SREQ-286`). The configuration file's paths are all taken from the
file's directory, so the composition re-derives the requirements source
directory, or each file of the source map, relative to the reader's repository.
A source path that does not lie under the repository, a reader with no
repository, a repository that is not in ``repositories``, an unreadable export
and a source file that cannot be read are each a request it could not judge
(exit 2). The message names the reader by the name of its block:
``requirements``, ``specifications`` or ``implementations`` (:need:`SEG-SREQ-292`).
A content extractor that cannot supply some nodes is the same request, and its
message names every such node, so one run shows every repair to make.
The configuration names no run bundle. A ``producer`` block that holds the key
``outcomes`` is refused when the file is read (exit 2). The operator names the
bundles with ``--bundle`` when a command runs, so a new run is a new option
value and needs no change to the file.

A run bundle often lies outside the source checkout, for example in a build
directory. It needs no repository name and no entry in ``repositories``:

.. code-block:: console

   $ affirmatrix graph status --bundle /path/to/build/bundles/run-2026-09-29 --revision <revision>

The bundle needs ``producer.specifications`` in the configuration, because a
result cannot map to a test specification without the test-case export. The
revision of each outcome is the revision the bundle records for the checkout
that the top-level key ``implementation`` names (for ``implementation: source``,
the file ``source.sha`` in the bundle). The key ``implementations`` is optional.
Without it, no Witnesses edge is supplied.

Test evidence
-------------

Test evidence is not stored in the case. A verb that judges evidence builds it
from the run bundles that the operator names, every time it runs
(:need:`SEG-SREQ-229`, :need:`SEG-SREQ-230`):

* ``graph status``, ``proof check`` and ``proof generate`` take the option
  ``--bundle PATH``, which may be given more than once. A relative path is taken
  from the working directory, while every path in the configuration file is
  taken from the file's directory. With no ``--bundle``, the stream holds no test
  evidence. Each named bundle is read and its digest is computed, whatever
  revision it records. The same directory named twice, also through a link, is
  read once (:need:`SEG-SREQ-232`). A bundle that is refused (a path that is not a
  directory, a dirty implementation checkout, no name, no run artifact, no
  revision) ends the verb with exit status 2 and no verdict
  (:need:`SEG-SREQ-231`).
* ``--bundle`` together with ``--current`` is refused with exit status 2: a given
  stream holds its own evidence (:need:`SEG-SREQ-233`). ``--bundle`` with no
  test-case export in the configuration, or with a store at ``producer.root``,
  is refused with exit status 2 (:need:`SEG-SREQ-235`).
* ``case sync``, ``case check``, ``graph check``, ``node show``, ``edge show``
  and ``edge affirm`` take no ``--bundle``. The option is an argument error for them, with
  exit status 2, and they read no bundle.

The proof verbs always need the implementation revision (:need:`SEG-SREQ-112`).
``graph status`` needs it only where the current stream holds a test outcome,
and without one it needs neither a revision nor a clean tree. Given as
``--revision`` it is used as it is. Otherwise it is discovered from the
implementation repository, which must be clean, an untracked file included. If
no revision can be obtained, including when git cannot read the configured
repository, the verb exits with status 2 (:need:`SEG-SREQ-208`).

``graph status`` reports the evidence apart from the strong edges. Its rows are
the strong edges only. After them, the plain form ends with one line,
``evidence: N at the current revision, N at another revision, N dangling``,
and the JSON form has the section ``"evidence": {"current", "stale",
"dangling"}`` (:need:`SEG-SREQ-210`). ``current`` and ``stale`` count test
outcomes by whether their revision equals the one obtained; ``dangling`` counts
evidence edges (Confirms, Witnesses, Excuses) that touch an absent node. An
outcome at any revision never turns the verdict negative. A dangling evidence
edge does, like a dangling strong edge (:need:`SEG-SREQ-083`).

``case sync`` and test evidence
-------------------------------

``case sync`` writes the derived stream with all or nothing: if a record of it
does not validate against the case's schema copy, it writes nothing and exits
with status 2 (:need:`SEG-SREQ-212`). It leaves test outcomes and evidence
edges that the stream holds out of what it writes, because the case stores
none. After it has written, it removes every test outcome node and every
evidence edge that the case still holds, and prints one ``removed:`` line for
each. The held records are read, and so checked, before the write, so every
refusal comes before the first removal; an interrupted run is finished by the
next sync. A second sync has nothing to remove. A vanished evidence edge is not
reported with the ``vanished:`` lines, because the removal covers it, and
nothing in the case changes after a commit of the implementation repository.

A refusal of the store to read a case (a record that fails its schema) is
exit status 2, for every verb, and the JSON form of ``graph status`` then holds
an ``error`` entry (:need:`SEG-SREQ-211`).

Showing a node
--------------

``node show ID`` compares the node record that the case holds with the node
record that the current stream supplies (:need:`SEG-SREQ-313`). The identifier
is the case-local identifier, verbatim. The verb takes ``--current``,
``--json`` and ``-v``. It takes no ``--bundle`` (:need:`SEG-SREQ-230`).

The case's record is the node as it stood at the last ``case sync``. It is not
the node as it stood at an affirmation. A match after a new sync therefore says
nothing about an affirmed link. ``edge show`` answers that question, with the
review event. The verb reads the node records of both sides and builds no graph.
So a hash that only one side holds reaches the report. The graph builder
refuses such a stream. The library call is
:func:`affirmatrix.drift.compare_node`, which gives one result for each hash
name (:need:`SEG-SREQ-312`).

The verb makes four checks, in this order. Each failed check is exit status 2,
with a message that names the cause:

1. The case holds exactly one node with the identifier
   (:need:`SEG-SREQ-322`).
2. A current stream is available: given, configured, or at its configured
   location (:need:`SEG-SREQ-202`, :need:`SEG-SREQ-142`).
3. The current stream can be read in full (:need:`SEG-SREQ-323`). An error
   that a reader raises while it supplies its records counts as unreadable.
4. The current stream holds the identifier at most once
   (:need:`SEG-SREQ-329`).

After these checks, the hashes alone decide the exit status. It is 0 while
every hash matches. It is 1 while a hash differs or exists on one side only. It is also 1
while the current stream holds no node with the identifier
(:need:`SEG-SREQ-320`, :need:`SEG-SREQ-321`). A repository that differs from its
commit, is not configured or cannot be read never changes it
(:need:`SEG-SREQ-331`).

The report has one block for each hash name that either record carries:

* The status, and the recorded and the current digest. The text shortens a
  digest unless ``-v`` is given. The JSON always gives it in full.
* ``extracted from``: the extraction revision that the case records for the
  repository the recorded anchor names, or ``none recorded``
  (:need:`SEG-SREQ-317`). No other revision stands in its place. A revision from
  a review event is never shown here.
* ``checkout``: the repository that the current anchor names, and the revision it
  is at. The line says ``no repository is configured`` when the configuration
  does not map the name (:need:`SEG-SREQ-318`). It says ``cannot be read``, with
  the reason that git gave, when a configured repository fails the reads
  (:need:`SEG-SREQ-331`).
* ``worktree``: ``clean``, or the anchored paths of the node in that repository
  that differ from their commit (:need:`SEG-SREQ-319`). A path that the commit
  does not hold counts as a difference. One read serves each repository, with
  the same function as ``case sync`` (``_extraction.read_repository``).
* The content that the current stream supplies. The text report shows it as
  UTF-8. A hash with no supplied content says ``none supplied``
  (:need:`SEG-SREQ-316`).

A hash that only the case records has no current anchor. Its block says ``no
current content`` and has no ``checkout`` and no ``worktree`` line
(:need:`SEG-SREQ-330`).

The JSON report has the keys ``id``, ``kind`` and ``hashes``. Each entry of
``hashes`` has ``name``, ``status``, ``recorded``, ``current``,
``recordedRevision``, ``checkout`` (``null`` without a current anchor, else
``repository``, ``configured``, ``revision``, ``dirtyPaths`` and ``error``),
``content`` and ``encoding``. The JSON is lossless (:need:`SEG-SREQ-328`):
``content`` is the text and ``encoding`` is ``utf-8`` when the bytes are valid
UTF-8. Otherwise ``content`` is their base64 form and ``encoding`` is
``base64``. Both are ``null`` when no content exists. A refusal is
``{"error": ...}``.

The content comes from the protocol :class:`~affirmatrix.records.ContentSource`,
which is separate from the record source. The verb asks the current stream for
the bytes of each hash that has a current anchor. A stream that does not meet
the protocol, such as the outcome reader, supplies none. The verb has a cost. It
reads the whole current stream, because it must know that the identifier occurs
once. Then it asks for the bytes of each hash, and the content extractor reads
its source files again for each question.

Showing an edge
---------------

``edge show`` reports each edge that the selection includes. It compares the
hashes that the last affirmation recorded with the current ones. With ``-v`` it
also recovers the content that the affirmation bound. For every edge that has a
last affirmation, the row also says who recorded that affirmation and when
(:need:`SEG-SREQ-293`). The state of the edge does not matter: an outdated edge
and a broken edge have the block too. An edge that was never affirmed has none.
There is no option for it.

A review event holds no person and no time. The history of the case holds them,
because the commit that adds an event is the act of affirming (ADR-0009). The
adapter reads that history (ADR-0015) to find the *recording commit*: the
earliest commit whose events document holds the event. The commit that created
the document is not the answer, because every event sits in that one document.

The adapter finds the commit in this way:

1. The store gives the identifier of the last event of each edge, as the events
   document holds it (:meth:`~affirmatrix.case.AffirmationStore.latest_review_event_identifiers`).
   One read of the document serves the whole selection. The identifier is never
   minted again from the position of the event.
2. The adapter runs ``git log --reverse`` over the events document with a
   pickaxe regular expression (``-S`` with ``--pickaxe-regex``). The expression
   matches the key ``"id"`` and the identifier together, as one JSON member,
   with any white space between the parts. The first commit that git lists is
   the earliest one.
3. A second call, ``git show``, reads the facts of that one commit.

The closing quote of the identifier is not a boundary on its own. A free-text
reason can end with the identifier of the next event, and the commit that adds
that reason can be an earlier commit. A reason holds a quote only as ``\"``, so
the key and the value together cannot occur inside another value.

The search is one ``git log`` for each event. The cost of a selection grows with
the number of events and with the number of commits that touched the events
document. A single pass over the history can serve all events, but it needs the
text of every diff and a parser for it. The checks of the whole case run once
for each command. They make sure that the case is the top level of a repository
and that the history has a commit. They also read whether the history is
shallow. A selection with no affirmed edge runs no git.

The JSON row has the key ``recordedInCaseHistory``. Its value always has the
keys ``status``, ``commit``, ``subject``, ``committer``, ``author``,
``signedOffBy``, ``signature`` and ``shallow``. ``status`` is one of three words:

* ``found``: a commit holds the event. The other keys describe the earliest
  such commit.
* ``notCommitted``: no commit holds the event, or the repository has no commit
  yet. The event is a draft in the working tree (:need:`SEG-SREQ-300`). An
  earlier affirmation of the same edge never stands in for it.
* ``unavailable``: the case is not a repository of its own, or git cannot read
  its history (:need:`SEG-SREQ-301`). A case that lies inside another repository
  counts as not a repository of its own, so the answer never comes from the
  enclosing repository. A case that is a worktree of another repository is its
  own repository. Git is never told where the repository is.

The keys describe the recording commit as the commit records it:

* ``commit`` and ``subject`` are the identifier of the commit and its subject
  line (:need:`SEG-SREQ-299`).
* ``committer`` and ``author`` are objects with ``name``, ``email`` and ``date``.
  The committer and the commit date are the identity and the time
  (:need:`SEG-SREQ-294`). ``author`` is ``null`` when the author has the name
  and the e-mail address of the committer, whatever the author date is
  (:need:`SEG-SREQ-295`). A date is ISO 8601 with the offset, as ``git log
  --format=%cI`` gives it. No mailmap is applied.
* ``signedOffBy`` lists the values of the Signed-off-by lines, as written and in
  order (:need:`SEG-SREQ-296`).
* ``signature`` is the status that git gives for the signature, as a word:
  ``none``, ``good``, ``bad``, ``unknownValidity``, ``expired``, ``revoked`` or
  ``cannotCheck``. An expired signature and an expired key both give ``expired``.
  Git runs the check and the tool runs no cryptography (:need:`SEG-SREQ-297`).
* ``shallow`` is ``true`` while the history is cut short, as in a clone made
  with ``--depth``. The commit that the block names can then be a later commit
  than the one that recorded the event (:need:`SEG-SREQ-302`).

The keys that describe the commit are ``null`` unless the status is
``found``. That includes ``signature`` and ``shallow``, and ``signedOffBy`` is
then an empty list.

In the text report the block follows the edge line and comes before the
comparison lines. A broken edge has no comparison, because an endpoint is
missing from the current records. For that edge the block is the only detail
under the edge line. The adapter finds the block from the event and not from
the stored hash, so the comparison does not decide whether the block exists.
For a ``found`` block the lines are:

.. code-block:: text

     recorded in the case history as: <committer name> <e-mail>, committed <date>
       commit <40 hex characters> "<subject>"
       author: <name> <e-mail>, authored <date>
       signed-off-by: <value>
       signature: <word>
       shallow history: <sentence>

The ``author`` line appears only when ``author`` is not ``null``. There is one
``signed-off-by`` line for each entry, and the ``shallow`` line appears only
while the history is shallow. Another status gives one line:
``recorded in the case history: not committed`` or ``... not available``, with
no identity and no date.

The words say what the history records. The text says "recorded in the case
history as" and never "affirmed by", and it never says "verified"
(:need:`SEG-SREQ-298`). A committer, an author and a Signed-off-by line are text
that the person who made the commit set. A signature is evidence only when the
reader verifies it with keys that the reader trusts. The report shows the
history as it stands now. After an amend or a rebase it shows the new commit
identifier.

What the history holds never changes the exit status (:need:`SEG-SREQ-303`). A
read that fails gives ``unavailable`` and never a traceback. Every git call runs
through one function with ``--no-optional-locks``, so no call changes the case,
its history, its index or its working tree (:need:`SEG-SREQ-116`).

Showing and verifying a package
---------------------------------

``proof show`` and ``proof verify`` take one package. The name is a snapshot
identifier, a unique prefix of one, or the path of the package directory
(:need:`SEG-SREQ-248`). A name that is a directory is read as a path. Any other
name is looked up among the packages of the case. A prefix that names two
packages is refused with exit status 2, and the refusal lists both
(:need:`SEG-SREQ-249`). A package that cannot be read, because a document is
missing, is not JSON or fails its schema, is refused the same way
(:need:`SEG-SREQ-254`).

A package named by path needs no case and no configuration file
(:need:`SEG-SREQ-270`). The package is read with the schemas that the tool
carries. A configuration file that exists but cannot be read still gives exit
status 2, also for a path.

``proof show`` reports what the package records and judges nothing. It reads
no run bundle and no current stream, and it exits with status 0 whatever the
package records (:need:`SEG-SREQ-252`, :need:`SEG-SREQ-253`). For a package
that records no run bundle digest it says "not recorded". Its JSON report has
the keys ``snapshotId``, ``requestedScope``, ``memberScope``, ``revision``,
``total``, ``designRoot``, ``runBundles`` (``null`` when none is recorded),
``findings`` and ``requirements``. It holds no path, so the three ways to name
a package give one report.

``proof verify`` runs the checks of the proof verifier
(:doc:`proof-verifier`) and prints each one with its status. ``--bundle PATH``
(repeatable) gives the verifier the run bundles that the invocation names, and
no others (:need:`SEG-SREQ-257`). ``--affirmations`` gives it the case of the
invocation (:need:`SEG-SREQ-258`). There is no ``--revision``: the verifier
judges at the revision the package records, and the command asks for no
revision (:need:`SEG-SREQ-262`). Its JSON report has ``snapshotId`` and a list
``checks``, each with ``name``, ``status`` and ``detail``.

Neither verb writes a file (:need:`SEG-SREQ-263`).

The exit-status vocabulary
------------------------------

Every verb funnels its final decision through
:func:`affirmatrix.cli._outcome.exit_for`, so the vocabulary is always
exactly these three values:

* **0** — the command's positive verdict (a buildable graph, a clean
  status, a ``node show`` whose hashes all match, an affirmation recorded, a
  ready package generated).
* **1** — the command's negative verdict, acted on (an unbuildable
  ``graph check``, a ``graph status`` naming a suspect or broken edge, a
  ``node show`` with a hash that differs, an
  ``edge affirm`` selection with no affirmable member, a blocked
  ``proof check``, a refused ``proof generate``, a ``proof verify`` with a
  failed check, a ``case check`` naming a
  missing schema or an unreadable producer).
* **2** — the command could not judge the request at all (a package that
  cannot be read, a ``node show`` for an identifier that the case does not hold, a prefix that names two packages, a ``proof verify`` with
  no failed check and a check that was asked for and not judged, a run bundle
  that is refused, an unbuildable
  current stream for ``graph status``, a selector matching nothing, an
  affirmation missing its selector, a revision that must be given
  explicitly but was not, no producer available for a two-stream verb, a
  configuration file that exists but cannot be made sense of).

``case check`` reports five judgements rather than one verdict about
content, so its own rule is simpler than the others': 0 while every
declared schema is present and the producer is readable, 1 otherwise —
never 2, since inspecting a case is always something ``case check`` can do.
When the producer cannot be read, ``case check`` gives the reason the library
gave (:need:`SEG-SREQ-290`): a line ``producer reason`` in the text, and the key
``producerReason`` in the structured rendering, which is ``null`` for a readable
producer.

A refusal always renders the library's own report — a ``GraphError``'s
message, the affirmation recorder's reason per non-affirmable edge, a
blocked package's coverage diagnostics — never a rewording of it. A refused
``graph check`` prints no count of anything, the one place a refusal's
rendering is *narrower* than a success's rather than merely present. A report
that is not a refusal names what it checked by its location
(:need:`SEG-SREQ-291`): the root of the case, or the path given to ``--current``.
The first line of the text does so, and the structured rendering carries the
key ``checked`` with the kind of the stream and its ``location``.
``--json`` on every read-only verb (``case check``, ``graph check``,
``graph status``, ``node show``, ``edge show``, ``proof check``) prints the same report as
a structured document; for ``proof check`` this is exactly
:func:`affirmatrix.proof.coverage_report_document`, the same serialization a
generated package's own ``coverage_report.jsonld`` uses.

The four repository reads
-----------------------------

The adapter, and only the adapter, may read a repository —
:mod:`affirmatrix.cli._repository`, the sole importer of ``subprocess`` in
the whole package. Four reads, no writes. Three are in source repositories:

* discovering the current revision of the working tree
* checking that the paths an endpoint's anchors name match their committed
  content
* recovering the bytes a path held at a past revision, for display

The fourth is in the repository of the case. It finds the commit that recorded
a review event, for ``edge show`` (see "Showing an edge" above, and ADR-0015).
Every git call runs with ``--no-optional-locks``. Without it, ``git status`` refreshes the index of
the repository, and a read must not write. ``node show`` uses the revision read and the cleanliness read too. It reports
their results and never refuses on them. Discovery and the cleanliness check together are how
``edge affirm`` and the proof gate's own revision fill a review event's
source-revision fields without an operator typing a commit hash; the
cleanliness check is what keeps a discovered revision honest — a dirty
anchored path refuses rather than silently misdescribing what was hashed.

A revision the operator gives with ``--revision`` bypasses all of this: it
is recorded exactly as given in the review event, never discovered, never
checked by the adapter. It is never recorded as an extraction revision (see
below). It is still a real fact about the record, though — the case's own
schema pins every recorded revision to the shape of a git commit hash, 40 or
64 lowercase hex characters, and refuses anything else on write. Passing
``--revision`` a value that is not shaped like a commit (a label such as
``rev1``, say) fails at that schema boundary, not at the command line —
useful to know since the would-be store's own anchors carry a literal
filesystem path as their "repository", which never resolves through the
configured map, so every affirmation and generation over it needs an
explicit, commit-shaped ``--revision`` today.

Extraction revisions
--------------------

``case sync`` and ``edge affirm`` write node records, and each writes them with
the extraction revisions of ADR-0016: for each repository that a node's anchors
name, the revision at which the content behind the node's hashes was read. One
function decides the map, :mod:`affirmatrix.cli._extraction`
(:need:`SEG-SREQ-306` to :need:`SEG-SREQ-310`). It compares each node with the
record the case holds, read before the write:

* The hashes differ, or the case holds no record: the discovered revision is
  recorded, and a held revision is dropped.
* The hashes are equal: a held revision for a repository that the anchors name
  is kept, even when the repository has moved on. If none is held, the
  discovered revision is recorded. A held revision for another repository is
  dropped.

A revision *can be discovered* for a node when the repository is configured and
can be read, and holds the committed content at every path the node's anchors
name in it. The adapter makes three git calls for each repository: the revision,
``git status`` over the anchored paths, and ``git ls-tree`` for the paths the
revision holds. ``git status`` says nothing about a path that git never saw, so
the ``ls-tree`` read is what keeps a path that no commit holds from passing as
clean. Each repository is read once for each run, for the paths of all the nodes
that the run writes. A repository that is not configured, or is not a git
repository, is the same as a revision that cannot be discovered.

When a revision cannot be discovered, the node is written with no revision for
that repository and the verb does not fail. It prints one line for each such
repository, ``no extraction revision: <repository>: <count> node records``,
after the ``synced`` line of ``case sync`` and after the ``affirmed`` lines of
``edge affirm``. A revision given with ``--revision`` goes into the review event
only (:need:`SEG-SREQ-327`).

The store refuses a revision that is not 40 or 64 lowercase hexadecimal
characters, at the write, through the schema of the case
(:need:`SEG-SREQ-325`). A case with a schema copy from before this field refuses
every write that records a revision, and writes nothing, so the maintainer runs
``case refresh`` and commits it first (:need:`SEG-SREQ-212`).

The cleanliness check's scope differs by which revision it is guarding.
An affirmation endpoint's cleanliness covers only the paths that endpoint's
own anchors name — a change anywhere else in that repository never refuses
an ``edge affirm`` whose selection does not touch it. The proof gate's own
revision has no anchor set to bound it: its cleanliness check covers the
whole implementation repository, since a package's implementation revision
is a claim about the repository as a whole, not about any one endpoint.

Configuration
----------------

:mod:`affirmatrix.config` reads a YAML file with ``yaml.safe_load``,
``./affirmatrix.yaml`` by default, every parameter defaulted when the file
is absent or empty:

.. code-block:: yaml

   case: ./case
   producer:
     root: ./tests/fixtures/would_be_store
   repositories:
     implementation: /path/to/impl/repo
     requirements: /path/to/reqs/repo
   implementation: implementation
   roles: [SoftwareEngineer, TestEngineer]

====================================  ===============================================================
Key                                   Carries
====================================  ===============================================================
``case``                              the case root (default ``./case``)
``producer.root``                     the current stream's producer (default: none configured)
``producer.repository`` and the       the readers' inputs; when any reader is set it supplies
reader blocks                         the current stream and ``producer.root`` is ignored
``repositories.<name>``               a repository name an anchor may carry, mapped to its path
``implementation``                    which configured repository is the implementation one, and
                                      the checkout of a named run bundle whose revision and dirty flag
                                      decide
``roles``                             a list, the accepted affirmation roles
====================================  ===============================================================

A name absent from ``repositories`` — including every name the would-be
store's own anchors carry, since those are literal paths, never configured
names — resolves to *no repository*, the fallback that makes ``--revision``
a requirement rather than a special case anywhere a revision is resolved
(``edge affirm``'s two endpoints, the proof gate's implementation revision).
``--case`` given on the command line overrides the file's own ``case``; no
value this loader carries ever reaches a content hash, a node hash, an edge
hash, or a design root. A file whose top level is not a mapping, or whose
keys carry the wrong shape (a ``repositories`` entry that is not a string,
say), is a refusal the loader raises and the command line renders as exit 2,
a request it could not judge — never a guess at what was meant.

See also
-----------

:doc:`affirmation-recorder` for what an affirmation binds, :doc:`drift-derivation`
for the states ``graph status`` and ``edge show`` report, and
:doc:`proof-scope` / :doc:`proof-package` for what ``proof check``/``generate``
compute over.
