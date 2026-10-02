0006. Test-tree ownership: developer tests, verification tests, fixtures
=========================================================================

Status
------

Accepted, 2026-07-25.

Context
-------

Path-based ownership (ADR-0002) gives the Software Engineer
``src/affirmatrix/`` and the Test Engineer ``tests/``. Two instructions
cut across that boundary. The Software Engineer is required to work
test-first, so the Software Engineer necessarily authors test code; and the
iteration-0 would-be store — a fixture the Software Engineer hand-authors —
is placed in ``tests/fixtures/``. As written, the Software Engineer cannot
follow the method without writing in the Test Engineer's path.

The two kinds of test are genuinely different artifacts, not merely
differently-authored ones. The Test Engineer's tests are **verification
evidence**:
each realizes a ``SEG-TS-nnn`` specification, states that specification in
a ``:test-id:`` marker and the requirement it demonstrates in a
``:verifies:`` marker, and becomes a TestOutcome node in the case. The
Software Engineer's tests are **developer tests**: they drive the design, they are not graph
participants, and nothing in the evidence graph refers to them.

Decision
--------

The test tree is partitioned by artifact kind, one directory per owner:

============================  =================  ==============================
Path                          Owner              Holds
============================  =================  ==============================
``tests/unit/``               Software Engineer  developer tests (test-first)
``tests/fixtures/``           Software Engineer  fixture data, incl. the
                                                 would-be store
``tests/specification/``      Test Engineer      the verification suite
                                                 realizing ``SEG-TS-nnn``
``tests/conftest.py``         shared             changed by proposal only
============================  =================  ==============================

A single pytest root is retained; ``testpaths = ["tests"]`` is unchanged.
Ownership stays **directory-granular**, so the standing rule — never two
agents in the same path — survives verbatim, one level deeper.

Rejected alternatives: a separate top-level tree for developer tests
(cleanest boundary, but two pytest roots and a layout an OSS contributor
would not expect, against ADR-0002's clone-and-build motive); and tests
inside ``src/affirmatrix/`` (no brief amendment needed, but it ships test
code and fixture data in the wheel and hides the suite from contributors).

Consequences
------------

- Software Engineer's brief, path scope: **Edit** gains ``tests/unit/`` and
  ``tests/fixtures/``; the line "``tests/`` … are the Test Engineer's
  paths" narrows to ``tests/specification/`` and
  ``doc/test-specification/``.
- Test Engineer's brief, path scope: **Edit** narrows from ``tests/`` to
  ``tests/specification/``; **Read** gains ``tests/unit/`` and
  ``tests/fixtures/``.
- ``tests/conftest.py`` follows the precedent already set for the shared
  documentation federation config: common infrastructure, changed by
  proposal at a checkpoint, not unilaterally.
- The tree documents the distinction it encodes: a reader can see which
  tests are evidence and which are development.
- The would-be store lands at ``tests/fixtures/would_be_store/``, exactly
  where the Software Engineer's brief says — the contradiction is removed by
  widening the Software Engineer's scope, not by moving the fixture.
- Amended 2026-09-29: ``pyproject.toml`` is owned by the maintainer who
  decides on dependencies. A dependency or tool-configuration change is
  such a decision, applied in whichever pass needs it; the file is in no
  role's edit scope by default.
