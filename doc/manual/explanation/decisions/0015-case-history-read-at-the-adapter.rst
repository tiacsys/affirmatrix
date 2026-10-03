0015. The command-line adapter reads the case history to say who recorded an affirmation
========================================================================================

Status
------

Accepted, 2026-10-02. Extends ADR-0010 by one read. Applies the identity rule
of ADR-0009. ADR-0008, ADR-0009 and ADR-0010 each carry a status line that
points here.

Context
-------

A review event records the role, the reason, the revision and the hashes of
both endpoints. It records no person and no time. ADR-0009 says why: the
commit that adds the event supplies who and when.

An operator who reviews an affirmed edge wants to see who affirmed it and
when. Only the history of the case holds that answer.

ADR-0010 admits three repository reads. All three are in content
repositories. It says that a fourth read is a new decision. It also says that
the affirmation lineage is not read, because that read has a different trust
model.

That trust model is the reason for care. A commit author, a committer and a
Signed-off-by line are text that the person who made the commit set. They are
not an authenticated identity. A signature proves more, but only when it is
verified with keys that the reader trusts. ADR-0009 does not require
signatures.

Decision
--------

**The command-line adapter can read the history of the case.** The read has
one purpose: to find the commit that added a review event, and to report that
commit's facts. This is a fourth read, next to the three of ADR-0010.

The rules of ADR-0010 apply to it:

- The adapter reads. The library and the affirmation store still run no git.
- The adapter writes nothing. A read must not write. In particular, a status
  read runs with optional locks off, so that it does not rewrite the index.
- A read that fails gives one repository error. It never gives a traceback.

**Which commit.** The recording commit is the earliest commit of the history
whose tree holds the review event. The adapter finds it by the event's
identifier inside the events file. The commit that created the file is not the
answer, because every event sits in that one file.

**Which identity.** The committer of the recording commit, and the date of
that commit. ADR-0009 names the committer as the identity that the authorised
committer list checks. The author, the author date, and every Signed-off-by
line are shown too, as written. The tool decides nothing between them.

**What the report claims.** The report says "recorded in the case history as".
It never says "affirmed by". It shows the signature status as the
version-control system gives it: none, good, bad, unknown validity, expired,
revoked, or cannot check. The tool runs no cryptography of its own. The
signature status never changes an exit status.

**When the history gives no answer.** The report says so, and it names the
case:

- The event is in the working tree and in no commit: "not committed".
- The case is not a repository of its own: "not available". The case counts as
  a repository of its own only when its root is the top level of a working
  tree. A case inside another repository must not be answered from that
  repository.
- The history is shallow: the report says so beside the identity.

**A rewrite of the history.** The report shows the history as it stands now. A
rebase or an amend changes the commit identifier, the dates, and maybe the
committer. The report shows the commit identifier, so that a later run shows
the change. ADR-0009 open question 4 on protection stays open.

**Exit status.** What the history records never changes an exit status.

Consequences
------------

- The adapter has four reads. A fifth is a new decision.
- A requirement about these reads can name commits, committers, authors and
  signatures. ADR-0009 allowed that for the store and the recorder. This
  record extends it to the command line.
- The answer depends on the history of the checkout. A case copied without its
  history, or cloned shallow, gives a weaker answer. The report says so.
- A history that was rewritten gives the answer of the rewritten history.
- The cost grows with the number of commits that touched the events file. One
  pass over that file can serve all the events of a selection.
- ADR-0009 open question 2 stands. A reader who holds only an exported package
  cannot see this answer.

Open questions
--------------

1. Check the committer against the authorised committer list, and show the
   result. ADR-0009 names the list as the check. This record does not build it.
2. Require signed store commits. ADR-0009 open question 3.
3. Show every affirmation of an edge, not only the last.
4. An entry that was removed and added again, a merge commit, and a mailmap.
