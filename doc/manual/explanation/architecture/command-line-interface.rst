Command line and configuration
================================

The command line is the thin adapter over the three workflows: consistency
(``graph check``), suspect detection (``graph status``), and evidence
generation (``proof check``/``generate``), with ``case`` and ``edge`` around
them so an operator can drive all three on a real case without a Python
script. Every verb's outcome is the library's alone (:mod:`affirmatrix.cli`);
this page states what each verb calls, how an exit status is decided, the
three repository reads the adapter alone may perform, the configuration
loader's keys, and a few facts an operator needs that the requirement text
does not spell out on its own: the hex-shaped revision, the repository-name
lookup miss, and the two different scopes a cleanliness check can have.

Eleven commands, one dispatch entry
-------------------------------------

``affirmatrix <noun> <verb>``, parsed and dispatched by
:func:`affirmatrix.cli.main`:

============  ==================  =============================================================
Noun          Verb                Library call
============  ==================  =============================================================
``case``      ``init``            :meth:`~affirmatrix.case.AffirmationStore.initialize`
``case``      ``check``           :meth:`~affirmatrix.case.AffirmationStore.layout`,
                                   :meth:`~affirmatrix.case.AffirmationStore.missing_schemas`,
                                   record counts
``case``      ``sync``            :func:`~affirmatrix.drift.derive`, then
                                   :meth:`~affirmatrix.case.AffirmationStore.write_records`,
                                   then the removal of held test evidence
``case``      ``refresh``         :meth:`~affirmatrix.case.AffirmationStore.refresh_schemas`
``case``      ``remove``          :meth:`~affirmatrix.case.AffirmationStore.remove_edges`
``graph``     ``check``           :func:`affirmatrix.graph.build`
``graph``     ``status``          :func:`~affirmatrix.drift.derive`
``edge``      ``show``            :func:`~affirmatrix.drift.compare` against
                                   :meth:`~affirmatrix.case.AffirmationStore.latest_review_event`
``edge``      ``affirm``          :func:`affirmatrix.affirmation.affirmable` /
                                   :func:`~affirmatrix.affirmation.compose`
``proof``     ``check``           :func:`affirmatrix.proof.check_readiness`
``proof``     ``generate``        :func:`affirmatrix.proof.assemble` /
                                   :func:`~affirmatrix.proof.persist`
============  ==================  =============================================================

A verb that needs the current stream (every one but ``case init``) resolves
it in one order. Only ``graph status``, ``proof check`` and ``proof generate``
read run bundles into it (see "Test evidence" below). ``--current <path>`` names a would-be store explicitly and
wins. Otherwise the producer is composed from the configuration: the
requirements reader when ``producer.requirements`` is set, then the content
extractor when ``producer.implementations`` or ``producer.specifications`` is
set, then the outcome extractor when ``producer.outcomes`` lists a run, chained
in that order into one stream
(:func:`affirmatrix.sources.composed.from_config`). Only when the
configuration names no reader and no run does ``producer.root`` (the would-be
store) apply. Absent all of them, or when a configured input cannot be read, the
command exits 2: it was asked to judge something with no second stream to
compare against.

The readers anchor every record to the repository ``producer.repository``
names, by name and by repository-relative path. The configuration file's
paths are all taken from the file's directory, so the composition re-derives
the requirements source directory relative to the repository's path. A source
directory that does not lie under the repository, a ``producer.repository``
that is missing or not in ``repositories``, an unreadable export and a source
file that cannot be read are each a request it could not judge (exit 2).
Each run in ``producer.outcomes`` lies under the repository that its
``repository`` key names. The producer's repository is the default. The
composition reads the runs of one repository with one outcome extractor,
rooted at the path of that repository, and the anchor of an outcome names that
repository. The outcomes need ``producer.specifications``, because a result
cannot map to a test specification without that export. A run that names a
repository missing from ``repositories``, and outcomes without
``producer.specifications``, are each a request it could not judge (exit 2).

A run bundle often lies outside the source checkout, for example in a build
directory. Map that directory to a repository name and give each run that name:

.. code-block:: yaml

   repositories:
     source: /path/to/source
     results: /path/to/build/bundles
   implementation: source
   producer:
     repository: source
     specifications:
       export: /path/to/needs/test-specification/needs.json
       doxygen: /path/to/xml/dox-testspec
     implementations:
       export: /path/to/needs/api-traceability/needs.json
       doxygen: /path/to/xml/dox-api
     outcomes:
       - bundle: /path/to/build/bundles/run-2026-09-29
         digest: sha256:f960023c5eacbe8c4a2fc2867d4d78c38bede4c02b1df6ac150f5804c8ca0043
         repository: results

The bundle lies under the path of ``results``, so the anchor of an outcome
reads ``run-2026-09-29/twister.json`` in the repository ``results``. The
``digest`` is the one the bundle must have (:doc:`outcome-extractor`). The
revision of each outcome is the revision the bundle records for the checkout
that the top-level key ``implementation`` names (here ``source``, so the file
``source.sha`` in the bundle). A new run is a new bundle and a new digest in the
configuration. A run that still gives ``artifact``, ``revision`` or ``name`` is
a refusal when the file is read. The key ``implementations`` is optional.
Without it, no Witnesses edge is supplied.

Test evidence
-------------

Test evidence is not stored in the case. A verb that judges evidence builds it
from the configured run bundles every time it runs
(:need:`SEG-SREQ-229`, :need:`SEG-SREQ-230`):

* ``graph status``, ``proof check`` and ``proof generate`` read every
  configured bundle and check its digest. Every bundle is checked, whatever
  revision it records. A bundle that is refused (a wrong digest, a dirty
  implementation checkout, no name, no run artifact, no revision) ends the verb
  with exit status 2 and no verdict (:need:`SEG-SREQ-231`).
* ``case sync``, ``case check``, ``graph check``, ``edge show`` and ``edge
  affirm`` read no bundle. A configuration that names a bundle that does not
  exist does not disturb them.

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

The exit-status vocabulary
------------------------------

Every verb funnels its final decision through
:func:`affirmatrix.cli._outcome.exit_for`, so the vocabulary is always
exactly these three values:

* **0** — the command's positive verdict (a buildable graph, a clean
  status, an affirmation recorded, a ready package generated).
* **1** — the command's negative verdict, acted on (an unbuildable
  ``graph check``, a ``graph status`` naming a suspect or broken edge, an
  ``edge affirm`` selection with no affirmable member, a blocked
  ``proof check``, a refused ``proof generate``, a ``case check`` naming a
  missing schema or an unreadable producer).
* **2** — the command could not judge the request at all (an unbuildable
  current stream for ``graph status``, a selector matching nothing, an
  affirmation missing its selector, a revision that must be given
  explicitly but was not, no producer available for a two-stream verb, a
  configuration file that exists but cannot be made sense of).

``case check`` reports five judgements rather than one verdict about
content, so its own rule is simpler than the others': 0 while every
declared schema is present and the producer is readable, 1 otherwise —
never 2, since inspecting a case is always something ``case check`` can do.

A refusal always renders the library's own report — a ``GraphError``'s
message, the affirmation recorder's reason per non-affirmable edge, a
blocked package's coverage diagnostics — never a rewording of it. A refused
``graph check`` prints no count of anything, the one place a refusal's
rendering is *narrower* than a success's rather than merely present.
``--json`` on every read-only verb (``case check``, ``graph check``,
``graph status``, ``edge show``, ``proof check``) prints the same report as
a structured document; for ``proof check`` this is exactly
:func:`affirmatrix.proof.coverage_report_document`, the same serialization a
generated package's own ``coverage_report.jsonld`` uses.

The three repository reads
------------------------------

The adapter, and only the adapter, may read a source repository —
:mod:`affirmatrix.cli._repository`, the sole importer of ``subprocess`` in
the whole package. Three reads, no writes: discovering the working tree's
current revision, checking that the paths an endpoint's anchors name match
their committed content, and recovering the bytes a path held at a past
revision for display. Discovery and the cleanliness check together are how
``edge affirm`` and the proof gate's own revision fill a review event's
source-revision fields without an operator typing a commit hash; the
cleanliness check is what keeps a discovered revision honest — a dirty
anchored path refuses rather than silently misdescribing what was hashed.

A revision the operator gives with ``--revision`` bypasses all of this: it
is recorded exactly as given, never discovered, never checked by the
adapter. It is still a real fact about the record, though — the case's own
schema pins every recorded revision to the shape of a git commit hash, 40 or
64 lowercase hex characters, and refuses anything else on write. Passing
``--revision`` a value that is not shaped like a commit (a label such as
``rev1``, say) fails at that schema boundary, not at the command line —
useful to know since the would-be store's own anchors carry a literal
filesystem path as their "repository", which never resolves through the
configured map, so every affirmation and generation over it needs an
explicit, commit-shaped ``--revision`` today.

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
``producer.repository``, the reader   the readers' inputs; when any reader or run is set it supplies
blocks and ``producer.outcomes``      the current stream and ``producer.root`` is ignored
``producer.outcomes[].bundle``        the run bundle, a directory
``producer.outcomes[].digest``        the digest the bundle must have, ``sha256:`` and 64 hex digits
``producer.outcomes[].repository``    the repository a run's bundle lies under (default: the
                                      producer's repository)
``repositories.<name>``               a repository name an anchor may carry, mapped to its path
``implementation``                    which configured repository is the implementation one, and
                                      the checkout of a run bundle whose revision and dirty flag
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
