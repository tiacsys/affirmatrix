The outcome extractor
=====================

The engine consumes records. A test run leaves a **run bundle**: a directory
that holds the test report, the revision and the dirty flag of each checkout
the run used, the run name and the command.
:class:`affirmatrix.sources.outcomes.TwisterOutcomeExtractor` turns each bundle
into one TestOutcome record for each test result the report holds, and into
the edges that tie each outcome to what it confirms and what it witnesses. The
command line composes it into the current stream, and only for the verbs that
judge evidence (see the last section).

The case stores none of these records. They are built when a verdict is made,
from the bundles the command line names, and they are not kept
(:need:`SEG-SYS-013`).

The run bundle
--------------

A run bundle is a flat directory. The extractor reads these files and no other
(:need:`SEG-SREQ-219`):

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - File
     - Content
   * - ``twister.json``
     - the run artifact: a JSON object with a ``testsuites`` list
   * - ``run.name``
     - the name of the run, one line
   * - ``<checkout>.sha``
     - the full revision of the checkout, one line, for each checkout the run used
   * - ``<checkout>.dirty``
     - empty when the checkout was clean; otherwise the output of the status command
   * - ``command.txt``
     - the command of the run (provenance only; not read)

Every other file of the directory belongs to the identity of the bundle (see
the next section) and is not read. A bundle that the repository ``evidence``
holds, for example, looks like this:

.. code-block:: text

   clean/
     command.txt
     run.name
     testplan.json
     twister.json
     twister_report.xml
     twister_suite_report.xml
     toolbox.dirty
     toolbox.sha
     zdocs.sha
     zephyr.dirty
     zephyr.sha

The top-level configuration key ``implementation`` names the checkout that
decides. Its ``.sha`` file is the revision of every outcome of the run
(:need:`SEG-SREQ-186`), and its ``.dirty`` file decides whether the run is
refused (:need:`SEG-SREQ-222`). A dirty flag of any other checkout is accepted:
the bundle records it and nothing judges it. A missing ``.sha`` file of the
implementation checkout refuses the run (:need:`SEG-SREQ-187`). So does a missing
``.dirty`` file of it, because a bundle that says nothing about that checkout
does not show it clean. A flag that holds only blanks is clean. When no
``implementation`` is configured, a named bundle is refused.

.. code-block:: python

   extractor = TwisterOutcomeExtractor(
       [Path("evidence/clean")],
       checkout="toolbox",
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
  (:need:`SEG-SREQ-176`, :need:`SEG-SREQ-224`);
* the **name** and the **revision** come from the bundle's own records, never
  from a loose file beside it. The artifact holds neither the full revision nor
  the name of the run (:need:`SEG-SREQ-223`);
* the **test-case export** is the authority on which specification a result
  belongs to (:need:`SEG-SREQ-180`);
* the **implementation export** gives the witnesses (:need:`SEG-SREQ-189`). When
  ``implementations`` is ``None``, no Witnesses edge is supplied.

Each of the two exports is filtered by the ``types`` of its input before any
need is checked. Only a need of a configured type is a test-case need or an
implementation need (:need:`SEG-SREQ-336`, :need:`SEG-SREQ-339`). A need of
another type is not checked, not mapped and gives no edge, so a bad field in it
cannot refuse a run (:need:`SEG-SREQ-338`). The extractor reads the types from
the input classes it already holds, so it needs no argument of its own. With no
types, every need is read (:need:`SEG-SREQ-337`, :need:`SEG-SREQ-340`).

The ``doxygen`` field of the two input classes is not used. A bundle can lie
anywhere; the extractor needs no root and no repository name for it
(:need:`SEG-SREQ-134`). The report format built is a JSON test report; a pytest
run would be a second format of the same component. It is not built.

The digest of a bundle
----------------------

A bundle is identified by its digest, not by its name. A name is chosen by a
person and can repeat; a digest follows the bytes. Nobody gives the extractor
a digest to check: it computes the digest of every bundle it is given,
whatever its revision, on every run of a verb that reads bundles, and it reads
every file each time. The digest is the repository member of the anchor of each
outcome (see below), and a proof records it (see :doc:`proof-package`).

The digest is built from a list with one line for each regular file under the
bundle directory:

* the SHA-256 of the file's bytes, in 64 lowercase hex digits;
* two blanks;
* the path of the file relative to the bundle directory, with ``/`` as the
  separator;
* one line feed.

The lines are in the byte order of the UTF-8 paths (``LC_ALL=C`` order). The
digest is the SHA-256 of all the lines, written as ``sha256:`` and 64 hex
digits (:need:`SEG-SREQ-220`). A changed byte, a renamed file and an added
file, an empty one included, each change the digest. The order of the files on
disk, the location of the bundle and the modification times do not.

Anyone can make the same digest without the tool. From the bundle directory:

.. code-block:: sh

   find . -type f -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum

For the bundle ``clean`` above the command prints
``f960023c5eacbe8c4a2fc2867d4d78c38bede4c02b1df6ac150f5804c8ca0043``.

The function :func:`~affirmatrix.sources.outcomes.bundle_digest` makes the same
value. Some cases would make the shell recipe and the tool differ, so the tool
refuses them: a link, a file that is neither regular nor a directory, a file
it cannot read, and a path that holds a backslash or a line feed (``sha256sum``
writes such a name in an escaped form). An empty directory holds no file and
does not count.

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

The name must be one line, without a slash and without blanks around it. The
operator chooses it and keeps it unique for each run.

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

The table is fixed (:need:`SEG-SREQ-183`). Any other status, such as ``blocked``
or ``not run``, is an error that names the result (:need:`SEG-SREQ-184`). The
extractor checks the status of every result of an artifact first, before any
result is mapped to a need. If any status has no counterpart, one error names
every such result, each with its status, its board and its scenario, and no
result is reported as unmapped in that error. A skipped result is recorded as an
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
parts (:need:`SEG-SREQ-190`): the digest of the run bundle, written as
``sha256:`` and 64 hex digits, as the repository member; the path of the run
artifact within the bundle, ``twister.json``; and the locator ``nodeid:``
followed by the result's test identifier, for example
``nodeid:safe_data.api.safe_data.init_and_verify``. The bundle can lie anywhere:
a copy in another directory under another name gives the same anchors, and a
copy with one added file has another digest and so another repository member.
The path never depends on where the bundle is.

The edges
---------

Each outcome has one Confirms edge to the test-case need its result maps to
(:need:`SEG-SREQ-188`). It has a Witnesses edge to every implementation need that
satisfies a requirement that the test-case need verifies (:need:`SEG-SREQ-189`). A
skipped outcome has the same edges as a passed one. All edges are pending. A
target that an export does not hold is emitted all the same, and the graph
reports it as a broken edge, and ``graph status`` exits with status 1 for it.
On the evidence fixture the four scenarios give 76
outcomes and 152 edges.

Errors
------

:class:`~affirmatrix.sources.outcomes.OutcomeError` is raised when the
extractor is built, and never later. The extractor reads every input and maps
every result there, so the records it supplies are never a short stream. The
message names the bundle and, for one result, the result. The extractor
refuses:

* a path that is not a directory, or a bundle that holds a link or an unreadable
  file (:need:`SEG-SREQ-224`, :need:`SEG-SREQ-220`);
* a dirty implementation checkout, or a missing dirty flag of it
  (:need:`SEG-SREQ-222`);
* a revision record that is missing, empty or holds only a line feed
  (:need:`SEG-SREQ-187`), or that holds two lines or has blanks around its text;
* a name record that is missing, empty, has two lines or holds a slash
  (:need:`SEG-SREQ-223`);
* an artifact that cannot be read, is not a JSON object, has no
  ``testsuites`` list or holds a suite or a result without the fields it needs
  (:need:`SEG-SREQ-224`);
* an export that cannot be read, holds no or several versions or carries a
  build timestamp (:need:`SEG-SREQ-225`);
* a result with a status outside the table, named all at once with the count
  first (see "The status");
* a result that maps to no need or to more than one need. One error names every
  such result of an artifact (:need:`SEG-SREQ-354`). The first line gives the
  count. Each next line holds one result, its board and its scenario, in the
  order of the artifact, so the same artifact always gives the same text. The
  same unmapped test on two boards gives two lines;
* a misshapen need in the test-case export or in the implementation export, named
  all at once for each export in the order of the export
  (:need:`SEG-SREQ-353`);
* two results, in one run or in two, that give the same outcome identity. The
  message names both bundles.

A failure in one run stops the whole extractor. The operator corrects the
input and builds it again. A bundle that fails gives its errors at once, and the
extractor does not read the next bundle.

How the command line composes it
--------------------------------

The command line chains the requirements reader, the content extractor and
this extractor into the current stream, in that order, but it builds this
extractor only for ``graph status``, ``proof check`` and ``proof generate``,
and only when the operator names bundles with the option ``--bundle PATH``
(:need:`SEG-SREQ-229`). The option may be given more than once. A relative path
is taken from the working directory. With no ``--bundle``, the stream holds no
test evidence. The same directory named twice, also through a link, is read
once (:need:`SEG-SREQ-232`); two copies of one bundle give the same outcome
identities and are refused.

``case sync``, ``case check``, ``graph check``, ``node show``, ``edge show`` and
``edge affirm`` take no ``--bundle`` (:need:`SEG-SREQ-230`): the option is an argument
error for them, with exit status 2, and they never open a bundle. A bundle that
the extractor refuses ends the verb with exit status 2 and no verdict
(:need:`SEG-SREQ-231`). Naming bundles together with ``--current`` is refused
with exit status 2, because a given stream holds its own evidence
(:need:`SEG-SREQ-233`). Naming bundles with no test-case export in the
configuration, or with a store at ``producer.root``, is refused with exit status
2 (:need:`SEG-SREQ-235`): the extractor needs ``producer.specifications``. The
implementation export is optional; without it, no Witnesses edge is supplied.

This extractor supplies no content behind its hashes. Its hash covers a record
that it builds from a run bundle, so it does not meet the protocol
:class:`~affirmatrix.records.ContentSource` (:need:`SEG-SREQ-311`).

The configuration names no run. A ``producer`` block that holds the key
``outcomes`` is refused when the file is read, whatever the key holds
(:need:`SEG-SREQ-234`).

A proof records the digest of each bundle that supplied an outcome in its scope
(see :doc:`proof-package`), so a reader can fetch the same bundles and build the
same evidence again. The extractor keeps, for each outcome, the digest of the
bundle that supplied it, for that purpose.
