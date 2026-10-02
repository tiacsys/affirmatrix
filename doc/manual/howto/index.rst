How-to guides
=============

Task-oriented recipes. (Diátaxis: how-to.)

.. toctree::
   :maxdepth: 1

   upgrade-an-existing-case

.. contents::
   :local:

Build the documentation federation
----------------------------------

.. code-block:: sh

   python -m doc build            # all documents, two-stage
   python -m doc build manual --no-index   # fast rebuild of one document
   python -m doc live manual      # live preview

Development setup
-----------------

.. code-block:: sh

   pip install -e . --group dev
   pytest
   ruff check .
