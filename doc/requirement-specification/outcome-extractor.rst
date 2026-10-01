Outcome Extractor
=================

The outcome extractor reads one run artifact per run bundle it is given and supplies
one TestOutcome for each test result the artifact records. The artifact is the
authority on what a test did; the test-case export is the authority on which
specification a result belongs to, so a result reaches its specification by
an exact match of a test identifier, never by a name alone. A run artifact's
format is the runner's own, a twister run, say.

A run bundle is the unit of test evidence. It holds the run artifact (the
runner's report), a revision and a dirty flag for each checkout the run used,
the name of the run and the command. The bundle's identity is its digest. The
command line names each bundle by its path. The extractor computes the digest
of every bundle it reads. No digest is expected beforehand. The proof records
the digest of each bundle it used, and from then on the digest is the identity
of the bundle. The extractor reads a run from its bundle and from no other
record.

A TestOutcome's content hash covers the record read from the artifact's entry
for the test, projected onto the specification identity, the run identifier
and the result. Its result and revision are claims recorded beside the hash.
The projection is not the entry's bytes, so recomputing an outcome's hash
needs the run's name and the specification export as well as the artifact.
Because a run's scenarios share platform and tests, and scenario names can
nest, a test identifier or an outcome identity is never split to recover its
parts.

.. sreq:: The outcome extractor supplies a TestOutcome per recorded result
   :id: SEG-SREQ-176
   :refines: SEG-SYS-001

   The outcome extractor shall supply a TestOutcome record for every test
   result a run artifact records.

.. sreq:: A TestOutcome is identified by its run and its specification
   :id: SEG-SREQ-177
   :refines: SEG-SREQ-176

   The outcome extractor shall identify each TestOutcome record by its run
   identifier and its specification identifier, joined by a slash.

.. sreq:: A run identifier joins the run's name, platform and scenario
   :id: SEG-SREQ-178
   :refines: SEG-SREQ-177

   The outcome extractor shall form each run identifier from the run's
   name, the platform and the scenario the run artifact records for the
   result, in that order, joined by hyphens.

.. sreq:: The specification identifier is the test-case need's identifier
   :id: SEG-SREQ-179
   :refines: SEG-SREQ-177

   The outcome extractor shall take a TestOutcome's specification
   identifier from the identifier of the test-case need the result maps
   to.

.. sreq:: A result maps by suite, test function and scenario
   :id: SEG-SREQ-180
   :refines: SEG-SREQ-177

   The outcome extractor shall map each result to the test-case need whose
   suite and test function, joined to the scenario the run artifact
   records for the result, form the result's test identifier, and to no
   other need.

.. sreq:: An unmapped or ambiguous result is an error
   :id: SEG-SREQ-181
   :refines: SEG-SREQ-177

   If a result maps to no test-case need, or to more than one, then the
   outcome extractor shall report an error for that result instead of
   dropping it.

.. sreq:: A TestOutcome's content is its identity, run and result
   :id: SEG-SREQ-182
   :refines: SEG-SREQ-176

   The outcome extractor shall compute each TestOutcome's content hash
   from the canonical serialization of the specification identifier, the
   run identifier and the result taken from the run artifact's record of
   that test, and from no other field of that record.

Results
-------

.. sreq:: A recorded status maps onto the closed result set
   :id: SEG-SREQ-183
   :refines: SEG-SREQ-176

   The outcome extractor shall record the result of each TestOutcome as
   the member of the closed result set that the run artifact's status for
   that test corresponds to.

.. sreq:: A status with no counterpart is an error
   :id: SEG-SREQ-184
   :refines: SEG-SREQ-176

   If the run artifact records a status to which no member of the closed
   result set corresponds, then the outcome extractor shall report an
   error for that result instead of recording it.

.. sreq:: A skipped result is recorded
   :id: SEG-SREQ-185
   :refines: SEG-SREQ-176

   The outcome extractor shall record each skipped result as a TestOutcome
   whose result is skipped.

Revision
--------

.. sreq:: A TestOutcome's revision is the implementation checkout's revision in the run bundle
   :id: SEG-SREQ-186
   :refines: SEG-SREQ-132

   The outcome extractor shall record as each TestOutcome's revision the
   revision that the run bundle records for the implementation repository's
   checkout, exactly as recorded.

.. sreq:: A run with no recorded revision is refused
   :id: SEG-SREQ-187
   :refines: SEG-SREQ-132

   If the run bundle records no revision for the implementation
   repository's checkout, then the outcome extractor shall refuse the run
   instead of supplying outcomes for it.

Edges and anchor
----------------

.. sreq:: Confirms edges run to the specification
   :id: SEG-SREQ-188
   :refines: SEG-SREQ-176

   The outcome extractor shall derive a Confirms edge from each
   TestOutcome to the TestSpecification its result maps to.

.. sreq:: Witnesses edges run to the implementations of what the specification verifies
   :id: SEG-SREQ-189
   :refines: SEG-SREQ-176

   The outcome extractor shall derive a Witnesses edge from each
   TestOutcome to every Implementation whose implementation need satisfies
   a requirement that the outcome's test-case need verifies.

.. sreq:: A TestOutcome's anchor names the run artifact and the result
   :id: SEG-SREQ-190
   :refines: SEG-SREQ-143

   The outcome extractor shall anchor each TestOutcome's content hash at
   the path of the run artifact within its run bundle, naming the run
   bundle by its digest, with the locator nodeid:<the result's test
   identifier>.

Run bundle
----------

.. sreq:: A run is read from its run bundle and from no other record
   :id: SEG-SREQ-219
   :refines: SEG-SYS-013

   The outcome extractor shall read each run from the run's bundle and from
   no other record of that run.

.. sreq:: A run bundle's digest covers every file in it and its path
   :id: SEG-SREQ-220
   :refines: SEG-SREQ-219

   The outcome extractor shall compute the digest of a run bundle as the
   SHA-256 of the list of the bundle's files, in the order of their paths,
   each given by its path in the bundle and the SHA-256 of its bytes.

.. sreq:: A run whose implementation checkout was dirty is refused
   :id: SEG-SREQ-222
   :refines: SEG-SREQ-219

   If a run bundle records that the checkout of the implementation
   repository was dirty, then the outcome extractor shall refuse the run
   instead of supplying outcomes for it.

.. sreq:: A run with no recorded name is refused
   :id: SEG-SREQ-223
   :refines: SEG-SREQ-219

   If a run bundle records no name for the run, then the outcome extractor
   shall refuse the run instead of supplying outcomes for it.

.. sreq:: A bundle with no readable run artifact is refused
   :id: SEG-SREQ-224
   :refines: SEG-SREQ-219

   If a path named as a run bundle is not a directory that holds a run
   artifact the outcome extractor can read, then the outcome extractor shall
   refuse the run instead of supplying outcomes for it.

.. sreq:: An export with build timestamps is refused by the outcome extractor
   :id: SEG-SREQ-225
   :refines: SEG-SREQ-176

   If a need export the outcome extractor reads carries a build timestamp,
   then the outcome extractor shall refuse the export instead of supplying
   records from it.
