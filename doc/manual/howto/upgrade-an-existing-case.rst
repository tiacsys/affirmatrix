Upgrade an existing case
========================

A new release of affirmatrix can add a field to the records it writes. The
case keeps its own copy of the schemas, and that copy refuses every field it
does not know. So a case that an older release wrote needs a schema refresh
before its first sync with the new release.

This page uses one such field as its example: ``seg:extractedFrom``, the
extraction revision on each node record
(:doc:`../explanation/decisions/0016-node-extraction-revision`). The steps
are the same for every schema change.

Run every command from the directory that holds ``affirmatrix.yaml``. The
examples name the case ``case/``.

Before you start
----------------

- Commit every change in the case. The steps below give one commit each,
  and an earlier change mixed into them is hard to review.
- Map each content repository under ``repositories:`` in the configuration.
  The tool records a revision only for a repository the configuration maps.
- Commit the content in each content repository. A node whose anchored path
  has a change that is not committed, or that no commit holds, gets no
  revision.

The sync is refused until the refresh
-------------------------------------

A case with the old schema copy refuses the sync. The sync exits 2 and
writes nothing:

.. code-block:: console

   $ affirmatrix case sync
   node '<id>' does not validate against requirement.schema.json: Additional properties are not allowed ('seg:extractedFrom' was unexpected)
   $ echo $?
   2

``<id>`` is the first node record the sync tried to write. The case does not
change, so you can run the steps below at any time.

1. Refresh the schema copy
--------------------------

.. code-block:: console

   $ affirmatrix case refresh
   refreshed: implementation.schema.json
   refreshed: requirement.schema.json
   refreshed: test_outcome.schema.json
   refreshed: test_specification.schema.json
   refreshed: waiver.schema.json

The command names each schema that differed. A case that is older still can
show more lines. If the copy is already current, it prints ``schema copy up to
date``. Both outcomes exit 0.

2. Review the schema diff
-------------------------

.. code-block:: console

   $ git -C case diff --stat
   $ git -C case diff

For this release, each node schema gains one optional property,
``seg:extractedFrom``. Look for any other change you did not expect before
you go on. A refresh can also rewrite records of an older case
(:doc:`../explanation/decisions/0012-evidence-edge-states` gives one
example), and the diff shows those too.

3. Commit the refresh
---------------------

The commit is a store act. You make it; the tool runs no git.

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

4. Sync
-------

.. code-block:: console

   $ affirmatrix case sync
   synced case
   $ echo $?
   0

If the sync cannot record a revision for some node records, it prints one
line for each repository, with the number of node records:

.. code-block:: console

   no extraction revision: <repository>: <count> node records

The usual causes are in "Before you start": a repository the configuration
does not map, or an anchored path with a change that is not committed. Fix the
cause and sync again.

5. Review and commit the sync
-----------------------------

The first sync gives one large diff. It adds ``seg:extractedFrom`` to every
node record whose anchored paths were clean. If no content changed since the
last sync, that field is the only change. No hash changes, because the field
never enters a hash:

.. code-block:: console

   $ git -C case diff --stat
   $ git -C case diff

Each node record gains a block of this form:

.. code-block:: text

   "seg:extractedFrom": {
     "<repository>": "<revision>"
   },

Commit it, again as a store act:

.. code-block:: console

   $ git -C case add -A
   $ git -C case commit -m "<your message>"

A second sync with no content change writes nothing new. A recorded
revision changes only when the node's hashes change.
