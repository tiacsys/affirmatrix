"""The outcome extractor — TestOutcome records from run artifacts.

Reads one run artifact per configured run, in the runner's own format (a pytest
run and a twister run are two formats of the one component), and supplies a
TestOutcome for every test result the artifact records (SEG-SREQ-176). The
artifact is the authority on what a test did; the test-case export is the
authority on which specification a result belongs to. A result reaches its
specification by an exact match of its test identifier -- suite, test function
and the scenario the artifact records -- never by a name alone, and a result
that maps to no specification, or to more than one, is an error rather than a
dropped record (SEG-SREQ-180, SEG-SREQ-181).

An outcome's identity is ``<run>-<platform>-<scenario>/<spec>``: the run's name,
the platform and the scenario joined by hyphens, then a slash and the
identifier of the test-case need the result maps to (SEG-SREQ-177 to
SEG-SREQ-179). A scenario name can nest and a run's scenarios share platform
and tests, so an identity or a test identifier is never split to recover its
parts. The run's name and the full source revision are not in the artifact;
they are read from the records kept beside it, the name being the operator's
own and unique per run, and a run with no recorded revision is refused
(SEG-SREQ-186, SEG-SREQ-187). Skipped results are recorded, as outcomes whose
result is skipped (SEG-SREQ-185). The content hash covers the specification
identity, the run identifier and the result, not the artifact's bytes
(SEG-SREQ-182); ``confirms`` and ``witnesses`` edges are derived from the
mapping (SEG-SREQ-188, SEG-SREQ-189).

The recorded revision is the freshness mechanism: compared against the current
one when a package is generated, a mismatch makes the outcome stale, and a
stale outcome is *discarded* rather than failed -- it blocks only if its
removal opens a coverage gap. The current revision is supplied explicitly,
never inferred from the outcomes themselves; guessing it from whichever
revision happens to be most common across a run is how a prototype learns that
inference and evidence do not mix.

Not yet built: this module is documentation only.
"""
