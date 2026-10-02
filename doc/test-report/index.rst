Test Report
===========

The results of one pytest run of this repository's tests (``SEG-OUT-…``).
Each test case is one need with its result; a test that has a test
specification links to it (``reports``), and through it to the requirements
it verifies. The run is a directory in the shape of a run bundle:
``junit.xml``, the revision of the checkout and its dirty flag, the run name
and the command. ``python -m doc test-run`` makes one in ``build/test-run``;
``python -m doc build --test-run DIR`` names another.

.. include:: _generated/report.inc
