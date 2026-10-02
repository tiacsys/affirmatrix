0016. A node record carries the revision its content hashes were extracted at
=============================================================================

Status
------

Accepted, 2026-10-02. Settles the question ADR-0010 left open: whether a
content anchor carries the revision the content was read at.

Context
-------

A node record holds hashes and anchors. An anchor names a repository, a path
and a locator. It names no revision. The only revision in the case is in a
review event, and only for an endpoint that someone affirmed.

An operator who finds a node whose current hash differs from the recorded hash
needs one fact: which revision of the content repository gave the recorded
hash. Without it, nobody can find the old content.

Three ways to hold that fact were compared.

- A. A revision on each node record. It changes only when the hashes change.
- B. One record of repository revisions per sync. The tool finds the case
  commit where the node's hash last changed, and reads the sync record there.
  This needs the history of the case. It is wrong for a node record that
  ``edge affirm`` wrote, because no sync made that commit. It breaks under
  rebase and squash. It cannot be checked from the record.
- C. The commit subject. It is free text. It is not a record.

Decision
--------

**A node record can carry ``seg:extractedFrom``.** It is an object. Each key is
a repository name, as the node's content anchors name it. Each value is a
revision: 40 or 64 lowercase hex characters. The field is optional. No field
means "not recorded".

The field sits on the node record. It does not sit in each anchor, because a
review event uses the same anchor shape and already holds a revision of its own.

**Meaning.** The revision is one at which the paths the node's anchors name in
that repository matched the committed content, when the producer read the
content that gave the recorded hashes. It claims no more. For a requirement,
the hash comes from a build export. The check shows that the anchored source
file was committed. It does not show that the export was built from it.

**When the command-line adapter writes it.** The adapter writes node records at
``case sync`` and at ``edge affirm``. For each repository:

- It records the discovered revision when the node's hashes differ from the
  recorded ones, or when no revision is held.
- It keeps the held revision while the hashes are equal.
- It records none when the revision cannot be discovered, and it drops the held
  revision if the hashes changed. A stale revision next to a new hash would be
  false.
- It never records a revision that the operator gave on the command line. That
  revision is an assertion. It is not a checked fact.

The adapter discovers a revision with the two reads of ADR-0010, revision
discovery and cleanliness of the anchored paths. This record extends them to
the verbs that write node records. The cleanliness read includes whether the
repository holds each anchored path at the discovered revision. A path the
repository does not hold there is not clean. Nothing else changes in ADR-0010.

**No hash changes.** The field never enters a hash. The library and the store
carry it as a value and run no git.

Consequences
------------

- The node schemas gain one optional property. An old case reads with no
  revision. There is no migration.
- The first sync after the change writes the field into every node whose paths
  are clean. That is one large diff.
- The schema copy in a case forbids unknown properties. The maintainer runs
  ``case refresh`` and commits it before the first sync. Otherwise the sync
  refuses and writes nothing.
- A sync with a dirty working tree is not refused. The affected nodes get no
  revision, and the sync names each repository and the number of nodes.
- The adapter reads the cleanliness of each repository once for each run.
- The answer needs no history of the case. A rewrite of that history changes
  nothing.

Open questions
--------------

1. Bring back the content that belongs to a recorded hash. This needs the
   revision of this record, and a build of the export or the Doxygen output at
   that revision.
2. Bind a build export or a Doxygen output to the revision it was built from.
