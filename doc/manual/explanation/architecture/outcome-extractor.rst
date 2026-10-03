The outcome extractor
=====================

The engine consumes records. A test run leaves a report and two short records
beside it. :class:`affirmatrix.sources.outcomes.TwisterOutcomeExtractor` turns
them into one TestOutcome record for each test result the report holds, and
into the edges that tie each outcome to what it confirms and what it
witnesses. The command line composes it into the current stream (see the last section).

What it reads
-------------

.. code-block:: python

   extractor = TwisterOutcomeExtractor(
       Path("checkout"),
       [
           config.RunInputs(
               artifact=Path("checkout/run/report.json"),
               revision=Path("checkout/run/revision"),
               name=Path("checkout/run/name"),
           )
       ],
       repository="product",
       specifications=config.SpecificationInputs(
           export=Path("needs/test-specification/needs.json"),
           doxygen=Path("xml/dox-safe-data-testspec"),
       ),
       implementations=config.ImplementationInputs(
           export=Path("needs/api-traceability/needs.json"),
           doxygen=Path("xml/dox-safe-data-api"),
       ),
   )

Each input has one purpose:

* the **run artifact** is the authority on what a test did. Its ``testsuites``
  list holds one suite for each scenario. A suite names its scenario and its
  platform and lists its results, each with a test identifier and a status
  (:need:`SEG-SREQ-176`);
* the **revision record** and the **name record** are one-line files beside the
  artifact. The artifact holds neither the full revision nor the name of the
  run;
* the **test-case export** is the authority on which specification a result
  belongs to (:need:`SEG-SREQ-180`);
* the **implementation export** gives the witnesses (:need:`SEG-SREQ-189`). When
  ``implementations`` is ``None``, no Witnesses edge is supplied.

``repository`` is the configured name of the repository ``root`` belongs to,
never a path (:need:`SEG-SREQ-134`). The ``doxygen`` field of the two input classes
is not used. ``root`` must hold every artifact.

Twister is the format of the artifact. A pytest run would be a second format of
the same component. It is not built.

Identity
--------

An outcome is identified by its run identifier and its specification
identifier, joined by a slash (:need:`SEG-SREQ-177`). The run identifier joins the
name of the run, the platform and the scenario by hyphens (:need:`SEG-SREQ-178`). Each
slash of the platform becomes a hyphen, so ``native_sim/native/64`` is
``native_sim-native-64`` and the identity holds one slash. The specification
identifier is the identifier of the test-case need, verbatim (:need:`SEG-SREQ-179`).
For the first result of the scenario ``safe_data.api`` the identity is::

   twister-run-2026-09-29-native_sim-native-64-safe_data.api/TC_SAFE_DATA_INIT_AND_VERIFY

The identity is never split to recover its parts. A scenario name can hold
dots and hyphens, and a platform can do so as well, so the parts do not show
where they end.

The name record must hold one line, without a slash and without blanks around
it. The operator chooses the name and keeps it unique for each run.

Mapping a result to its need
----------------------------

The test-case export is read once. For each test-case need the extractor keeps
its suite and its test function without the prefix ``test_``. For each suite of
the artifact it forms, from every need, the identifier

   ``<scenario>.<suite of the need>.<test function without test_>``

and compares the result's test identifier with each formed identifier as a
whole (:need:`SEG-SREQ-180`). Exactly one need must form it. No need and more than one
need are both an error that names the result (:need:`SEG-SREQ-181`). The extractor
never cuts a test identifier into parts.

The reason is that one string can have two readings. Take the scenarios ``s``
and ``s.t``. One need has the suite ``t.u`` and another has the suite ``u``,
and both have the test function ``test_f``. The identifier ``s.t.u.f`` is the
one the first need forms in the scenario ``s``. It is the one the second need
forms in the scenario ``s.t``. The scenario is part of what is formed, so each
result finds its own need. Two needs with the same suite and the same test
function are ambiguous only when a result reaches them. A scenario without results supplies nothing.

The status
----------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Status in the artifact
     - Result of the outcome
   * - ``passed``
     - passed
   * - ``failed``
     - failed
   * - ``error``
     - error
   * - ``skipped``
     - skipped

The table is fixed (:need:`SEG-SREQ-183`). Any other status, such as ``blocked``, is an
error that names the result (:need:`SEG-SREQ-184`). A skipped result is recorded as an
outcome with the result skipped; it is not dropped (:need:`SEG-SREQ-185`). The
revision of each outcome is the text of the revision record, as it is
(:need:`SEG-SREQ-186`). The extractor does not check its length.

The canonical record
--------------------

The content hash of an outcome covers three values and nothing else
(:need:`SEG-SREQ-182`): the specification identifier, the run identifier and the
result. The execution time and the reason of a result are not hashed. The hash
is the SHA-256 of the canonical record, a JSON object in UTF-8 with sorted keys,
no blanks and no escaping of non-ASCII text (RFC 8785). For the result
``safe_data.api.safe_data.init_and_verify`` of the scenario ``safe_data.api``
the record is these 132 bytes:

.. code-block:: json

   {"result":"passed","run":"twister-run-2026-09-29-native_sim-native-64-safe_data.api","specification":"TC_SAFE_DATA_INIT_AND_VERIFY"}

Anyone can reproduce the hash without the tool:

.. code-block:: sh

   printf '%s' '{"result":"passed","run":"twister-run-2026-09-29-native_sim-native-64-safe_data.api","specification":"TC_SAFE_DATA_INIT_AND_VERIFY"}' | sha256sum

The command prints
``b21f9c415e6b2de8ea131a18c709acdface0c91c976041b752ae382bf3128869``. The hash
does not cover the bytes of the artifact, so recomputing it needs the name of
the run and the test-case export as well as the artifact. The function
:func:`~affirmatrix.sources.outcomes.canonical_record` is public so that an
auditor can call it.

The anchor
----------

Each outcome has one content hash, ``contentHash``, with an anchor of three
parts (:need:`SEG-SREQ-190`): the configured repository name; the path of the artifact
relative to ``root``, in posix form; and the locator ``nodeid:`` followed by
the result's test identifier, for example
``nodeid:safe_data.api.safe_data.init_and_verify``. An artifact that lies
outside ``root`` is refused. Links are resolved first, so the path names the
file that the extractor reads.

The edges
---------

Each outcome has one Confirms edge to the test-case need its result maps to
(:need:`SEG-SREQ-188`). It has a Witnesses edge to every implementation need that
satisfies a requirement that the test-case need verifies (:need:`SEG-SREQ-189`). A
skipped outcome has the same edges as a passed one. All edges are pending. A
target that an export does not hold is emitted all the same, and the graph
reports it as a broken edge. On the evidence fixture the four scenarios give 76
outcomes and 152 edges.

Errors
------

:class:`~affirmatrix.sources.outcomes.OutcomeError` is raised when the
extractor is built, and never later. The extractor reads every input and maps
every result there, so the records it supplies are never a short stream. The
message names the run artifact and, for one result, the result. The extractor
refuses:

* a revision record that is missing, empty or holds only a line feed
  (:need:`SEG-SREQ-187`), or that holds two lines or has blanks around its text;
* a name record that is missing, empty, has two lines or holds a slash;
* an artifact that cannot be read, is not a JSON object, has no
  ``testsuites`` list or holds a suite or a result without the fields it needs;
* an artifact outside ``root``;
* an export that cannot be read, holds no or several versions or carries a
  build timestamp;
* a result with a status outside the table, a result that maps to no need and
  a result that maps to more than one need;
* two results, in one run or in two, that give the same outcome identity. The
  message names both run artifacts.

A failure in one run stops the whole extractor. The operator corrects the
input and builds it again.

How the command line composes it
--------------------------------

The command line chains the requirements reader, the content extractor and
this extractor into the current stream, in that order. Each run in
``producer.outcomes`` has an optional ``repository`` key. The key names the
configured repository that the files of the run lie under, and the producer's
repository is the default. The composition builds one extractor for each
repository that the runs name. The ``root`` of the extractor is the path of that
repository. The runs keep their order in the configuration. The extractor needs
the test-case export, so ``producer.specifications`` must be set. The
implementation export is optional. Without it, no Witnesses edge is supplied.
