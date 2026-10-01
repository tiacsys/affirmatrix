"""Verification suite for the command line over run bundles and evidence.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests call the command line through ``affirmatrix.cli.main``, as an operator
would.

Three small worlds serve the tests. A *bundle session* is a configuration over
the frozen exports, an empty case, and the run bundles an invocation names with
``--bundle`` (copies of the clean bundle in ``tmp_path``); it serves the verbs
that judge evidence. The configuration names no run. A *store world* is a
would-be store, given with ``--current``, whose content directory is a real git
repository that the configuration names as the implementation repository; it
serves the tests of the revision rule, the evidence counts and the exit
statuses, because its outcomes record the revision of that repository. The
*legacy case* (``tests/fixtures/legacy_case/``) is a case written while the
tool still stored test evidence.

The tests read the new names (the ``--revision`` option of ``graph status``,
the ``evidence`` section of its report) inside the test bodies only, so this
module collects before the code carries them. Every refusal test starts with a
control that is accepted, so a test fails for the claim and not because the
configuration cannot be read.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from .evidence_support import (
    LEGACY_CASE,
    OUTCOMES_PER_RUN,
    REVISION,
    RUN_NAME,
    SECOND_RUN_NAME,
    Session,
    copy_bundle,
    make_dirty,
    make_world,
    run,
    scope_args,
    second_bundle,
    session,
    snapshot,
)

STRONG_KINDS = {"Refines", "Verifies", "Implements"}


def _status(opened: Session, capsys, *extra: str) -> tuple[int, dict | str]:
    status, out = run(capsys, "graph", "status", "--json", *opened.evidence_args(), *extra)
    try:
        return status, json.loads(out)
    except ValueError:
        return status, out


def _check(opened: Session, capsys, *extra: str) -> tuple[int, dict | str]:
    status, out = run(
        capsys, "proof", "check", "--json", *opened.evidence_args(), *scope_args(), *extra
    )
    try:
        return status, json.loads(out)
    except ValueError:
        return status, out


def _spoil_dirty(bundle: Path) -> Path:
    (bundle / "toolbox.dirty").write_text(" M src/safe_data.c\n", encoding="utf-8")
    return bundle


def _spoil_name(bundle: Path) -> Path:
    (bundle / "run.name").unlink()
    return bundle


def _spoil_artifact(bundle: Path) -> Path:
    (bundle / "twister.json").unlink()
    return bundle


def _spoil_revision(bundle: Path) -> Path:
    (bundle / "toolbox.sha").unlink()
    return bundle


def _spoil_directory(bundle: Path) -> Path:
    """Name a plain file instead of a directory."""
    plain = bundle.parent / "plain-file"
    plain.write_text("not a bundle\n", encoding="utf-8")
    return plain


def _naming(opened: Session, *bundles: Path) -> Session:
    return Session(config=opened.config, case=opened.case, bundles=tuple(bundles))


def test_a_refused_bundle_gives_exit_status_2_and_no_verdict(tmp_path: Path, capsys) -> None:
    """A run bundle that the extractor refuses gives exit status 2 and no verdict.

    Graph status, proof check and proof generate each name the clean bundle
    with a revision given, and each gives a verdict: graph status prints its
    edges, proof check prints its coverage report, and proof generate prints a
    refusal of the gate or a snapshot. Five spoiled copies replace the bundle in
    turn: a dirty implementation checkout, no run name, no run artifact, no
    recorded revision, and a path that is a file and no directory. For each copy
    and each verb the exit status is 2. The output holds a refusal and no edge
    rows, no coverage report, no snapshot and no written document.

    :verifies: SEG-SREQ-231
    :test-id: SEG-TS-078
    """
    opened = session(tmp_path, [], capsys)
    revision = ["--revision", REVISION]
    verbs = (
        ("status", ["graph", "status", "--json"], []),
        ("check", ["proof", "check", "--json", *scope_args()], []),
        ("generate", ["proof", "generate", *scope_args()], ["--output-dir", str(tmp_path / "out")]),
    )
    control = _naming(opened, copy_bundle(tmp_path, "control"))
    for _, command, extra in verbs:
        status, _ = run(capsys, *command, *control.evidence_args(), *revision, *extra)
        assert status != 2

    spoilers = {
        "dirty": _spoil_dirty,
        "name": _spoil_name,
        "artifact": _spoil_artifact,
        "revision": _spoil_revision,
        "directory": _spoil_directory,
    }
    for label, spoil in spoilers.items():
        spoiled = _naming(opened, spoil(copy_bundle(tmp_path, label)))
        for name, command, extra in verbs:
            status, out = run(capsys, *command, *spoiled.evidence_args(), *revision, *extra)
            assert status == 2, (label, name)
            assert out.strip(), (label, name)
            for verdict in ('"edges"', '"blocked"', "snapshot:", "wrote "):
                assert verdict not in out, (label, name, verdict)
    assert not (tmp_path / "out" / "proofs").exists()


def test_the_other_verbs_take_no_run_bundle(tmp_path: Path, capsys) -> None:
    """Case sync, case check, graph check, edge show and edge affirm take no run bundle.

    The three verbs that judge evidence list ``--bundle`` in their help. The
    other five verbs do not. Each of the five, given ``--bundle`` and a
    directory, ends with an argument error and exit status 2, and changes
    nothing. Without that option each of the five works and exits with status 0:
    case sync, case check (which reports the producer as readable), graph check,
    edge show over the Refines edges, and edge affirm over the Refines edges.

    :verifies: SEG-SREQ-230
    :test-id: SEG-TS-079
    """
    opened = session(tmp_path, [], capsys)
    bundle = str(copy_bundle(tmp_path))
    affirm = ["--kind", "Refines", "--role", "fixture-reviewer", "--reason", ""]
    five = (
        ["case", "sync"],
        ["case", "check"],
        ["graph", "check"],
        ["edge", "show", "--kind", "Refines"],
        ["edge", "affirm", *affirm, "--revision", REVISION],
    )

    for command in (["graph", "status"], ["proof", "check"], ["proof", "generate"]):
        with pytest.raises(SystemExit) as stopped:
            run(capsys, *command, "--help")
        assert stopped.value.code == 0
        assert "--bundle" in capsys.readouterr().out
    for command in five:
        with pytest.raises(SystemExit) as stopped:
            run(capsys, *command[:2], "--help")
        assert stopped.value.code == 0
        assert "--bundle" not in capsys.readouterr().out

    before = snapshot(opened.case)
    for command in five:
        with pytest.raises(SystemExit) as stopped:
            run(capsys, *command, *opened.args(), "--bundle", bundle)
        assert stopped.value.code == 2, command
    assert snapshot(opened.case) == before

    assert run(capsys, "case", "sync", *opened.args())[0] == 0
    status, out = run(capsys, "case", "check", "--json", *opened.args())
    assert status == 0
    assert json.loads(out)["producerReadable"] is True
    for command in five[2:]:
        assert run(capsys, *command, *opened.args())[0] == 0


def test_the_verbs_that_judge_evidence_include_exactly_the_named_bundles(
    tmp_path: Path, capsys
) -> None:
    """Graph status and proof check include the test evidence of exactly the bundles named.

    With no bundle named, graph status counts no outcome and proof check lists
    no skipped and no stale outcome. Naming the clean bundle, proof check lists
    three skipped outcomes of that bundle's run and no stale outcome. Naming it
    and a second bundle, recorded at another revision under another run name,
    proof check lists the same three skipped outcomes and 24 outcomes of the
    second run as stale, and graph status counts the outcomes of both runs. A
    third bundle that lies beside the others and is not named supplies no outcome
    to any report.

    :verifies: SEG-SREQ-229
    :test-id: SEG-TS-080
    """
    opened = session(tmp_path, [], capsys)
    first, second = copy_bundle(tmp_path, "first"), second_bundle(tmp_path, "second")
    decoy = copy_bundle(tmp_path, "decoy")
    (decoy / "run.name").write_text("twister-run-decoy\n", encoding="utf-8")

    status, report = _check(opened, capsys, "--revision", REVISION)
    assert status in (0, 1)
    assert report["skippedOutcomes"] == [] and report["staleOutcomes"] == []
    status, document = _status(opened, capsys, "--revision", REVISION)
    assert status == 0
    assert document["evidence"] == {"current": 0, "stale": 0, "dangling": 0}

    status, report = _check(_naming(opened, first), capsys, "--revision", REVISION)
    assert status in (0, 1)
    assert len(report["skippedOutcomes"]) == 3
    assert report["staleOutcomes"] == []

    both = _naming(opened, first, second)
    status, report = _check(both, capsys, "--revision", REVISION)
    assert status in (0, 1)
    assert all(name.startswith(RUN_NAME) for name in report["skippedOutcomes"])
    assert len(report["skippedOutcomes"]) == 3
    assert len(report["staleOutcomes"]) == 24
    assert all(name.startswith(SECOND_RUN_NAME) for name in report["staleOutcomes"])
    text = json.dumps(report)
    assert "twister-run-decoy" not in text

    status, document = _status(both, capsys, "--revision", REVISION)
    assert status == 0
    assert document["evidence"]["current"] + document["evidence"]["stale"] == 2 * OUTCOMES_PER_RUN


def test_graph_status_reports_the_evidence_apart_with_its_counts(tmp_path: Path, capsys) -> None:
    """Graph status reports outcomes at the current revision and at another, and dangling edges.

    Graph status names the clean bundle and a second bundle recorded at
    another revision. Graph status runs with the revision of the first. Its
    machine-readable report holds an evidence section. The section counts 76
    outcomes at the current revision, 76 at another revision, and no edge that
    touches an absent node. The rows of the report hold no edge of kind
    Confirms, Witnesses or Excuses.

    :verifies: SEG-SREQ-210
    :test-id: SEG-TS-081
    """
    opened = session(tmp_path, [copy_bundle(tmp_path, "a"), second_bundle(tmp_path, "b")], capsys)

    status, document = _status(opened, capsys, "--revision", REVISION)

    assert status == 0
    assert document["evidence"] == {"current": 76, "stale": 76, "dangling": 0}
    assert {row["kind"] for row in document["edges"]} <= STRONG_KINDS


def test_a_dangling_evidence_edge_gives_the_negative_status_verdict(tmp_path: Path, capsys) -> None:
    """A Confirms, Witnesses or Excuses edge that touches an absent node gives exit status 1.

    The current stream is a store that holds two outcomes, one recorded at the
    revision of the implementation repository and one at another, and one
    Confirms edge to a test specification that the store does not hold. Graph
    status runs with the revision of the repository. It exits with status 1,
    its negative verdict. The same store without that edge gives exit status 0.

    :verifies: SEG-SREQ-083
    :test-id: SEG-TS-082
    """
    sound = make_world(tmp_path / "sound", outcomes=("head", "old"))
    status, _ = run(capsys, "graph", "status", *sound.args(), "--revision", sound.head)
    assert status == 0

    dangling = make_world(
        tmp_path / "dangling", outcomes=("head", "old"), absent_specification=True
    )
    status, _ = run(capsys, "graph", "status", *dangling.args(), "--revision", dangling.head)

    assert status == 1


def test_graph_status_counts_the_dangling_evidence_edges(tmp_path: Path, capsys) -> None:
    """The evidence section counts each evidence edge that touches an absent node.

    The current stream is the store of the previous test: two outcomes, one at
    the revision of the repository and one at another, and one Confirms edge to
    an absent test specification. Graph status runs with the revision of the
    repository. The evidence section counts one outcome at the current
    revision, one at another revision and one dangling edge.

    :verifies: SEG-SREQ-210
    :test-id: SEG-TS-083
    """
    world = make_world(tmp_path, outcomes=("head", "old"), absent_specification=True)

    status, out = run(capsys, "graph", "status", "--json", *world.args(), "--revision", world.head)

    assert status == 1
    assert json.loads(out)["evidence"] == {"current": 1, "stale": 1, "dangling": 1}


def test_graph_status_lists_strong_edges_only(tmp_path: Path, capsys) -> None:
    """Graph status gives a state for every strong edge and for no evidence edge.

    The current stream is a store with two outcomes, each with a Confirms edge
    and a Witnesses edge, and one Verifies and one Implements edge. Graph status
    runs with the revision of the repository. Its rows are the two strong
    edges, both pending. No row has the kind Confirms or Witnesses.

    :verifies: SEG-SREQ-080
    :test-id: SEG-TS-084
    """
    world = make_world(tmp_path, outcomes=("head", "old"))

    status, out = run(capsys, "graph", "status", "--json", *world.args(), "--revision", world.head)

    assert status == 0
    rows = json.loads(out)["edges"]
    assert sorted((row["kind"], row["state"]) for row in rows) == [
        ("Implements", "pending"),
        ("Verifies", "pending"),
    ]


def test_pending_strong_edges_leave_the_status_verdict_positive(tmp_path: Path, capsys) -> None:
    """When the only edges that are not active are pending, graph status exits with status 0.

    The current stream is a store with two outcomes, one at the revision of the
    implementation repository and one at another, and a clean repository that
    the configuration names. Its two strong edges are pending and nothing is
    affirmed. Graph status runs and exits with status 0.

    :verifies: SEG-SREQ-082
    :test-id: SEG-TS-085
    """
    world = make_world(tmp_path, outcomes=("head", "old"))

    status, _ = run(capsys, "graph", "status", *world.args())

    assert status == 0


def test_graph_status_refuses_a_dirty_implementation_repository(tmp_path: Path, capsys) -> None:
    """Graph status refuses a discovered revision when the repository holds an untracked file.

    The current stream holds an outcome. The implementation repository holds
    one untracked file. Graph status runs with no revision given. It exits
    with status 2 and its report names the untracked path. With a revision
    given, graph status exits with status 0.

    :verifies: SEG-SREQ-112
    :test-id: SEG-TS-086
    """
    world = make_world(tmp_path)
    make_dirty(world)

    status, out = run(capsys, "graph", "status", *world.args())
    assert status == 2
    assert "stray.txt" in out

    status, _ = run(capsys, "graph", "status", *world.args(), "--revision", world.head)
    assert status == 0


def test_proof_verbs_refuse_a_dirty_implementation_repository(tmp_path: Path, capsys) -> None:
    """Proof check and proof generate refuse a discovered revision when the repository is dirty.

    The implementation repository holds one untracked file. Proof check and
    proof generate run with no revision given. Each exits with status 2 and its
    report names the untracked path. Run with a revision given, neither exits
    with status 2.

    :verifies: SEG-SREQ-112
    :test-id: SEG-TS-087
    """
    world = make_world(tmp_path)
    make_dirty(world)
    scope = ["--scope", "SREQ-1"]
    output = ["--output-dir", str(tmp_path / "out")]

    for verb, extra in (("check", []), ("generate", output)):
        status, out = run(capsys, "proof", verb, *world.args(), *scope, *extra)
        assert status == 2
        assert "stray.txt" in out

        status, _ = run(
            capsys, "proof", verb, *world.args(), *scope, *extra, "--revision", world.head
        )
        assert status != 2


def test_no_obtainable_revision_cannot_be_judged(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an outcome in the stream and no obtainable revision, the verbs exit with status 2.

    The current stream holds an outcome. No revision is given and no
    implementation repository is configured. Graph status, proof check and
    proof generate each exit with status 2.

    :verifies: SEG-SREQ-208
    :test-id: SEG-TS-088
    """
    world = make_world(tmp_path)
    monkeypatch.chdir(tmp_path)
    arguments = world.args(config=False)
    scope = ["--scope", "SREQ-1"]

    for command in (
        ["graph", "status", *arguments],
        ["proof", "check", *arguments, *scope],
        ["proof", "generate", *arguments, *scope, "--output-dir", str(tmp_path / "out")],
    ):
        status, _ = run(capsys, *command)
        assert status == 2, command


def test_a_stream_without_an_outcome_needs_no_revision(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Graph status asks for no revision when the current stream holds no outcome.

    The current stream holds a requirement, a specification, an implementation
    and two strong edges, and no outcome. No revision is given and no
    configuration is read. Graph status exits with status 0.

    :verifies: SEG-SREQ-112
    :test-id: SEG-TS-089
    """
    world = make_world(tmp_path, outcomes=())
    monkeypatch.chdir(tmp_path)

    status, _ = run(capsys, "graph", "status", *world.args(config=False))

    assert status == 0


def _invalid_case(world) -> None:
    """Replace the case's refines document with one record that fails its schema."""
    record = {
        "id": "https://affirmatrix.dev/case/edge/refines/A/B",
        "type": "seg:Refines",
        "seg:from": "https://affirmatrix.dev/case/node/A",
        "seg:to": "https://affirmatrix.dev/case/node/B",
        "seg:linkState": "bogus",
    }
    document = {"@context": "../context.jsonld", "@graph": [record]}
    (world.case / "edges" / "refines.jsonld").write_text(json.dumps(document), encoding="utf-8")


def test_a_refused_store_read_is_a_request_the_command_cannot_judge(tmp_path: Path, capsys) -> None:
    """A verb that reads a case whose record fails its schema exits with status 2.

    One edge record in the case holds a link state that the case's schema copy
    does not allow. Graph status, edge show, graph check on the case itself,
    and proof check each exit with status 2 and print the refusal with text.
    The machine-readable form of graph status holds an error entry.

    :verifies: SEG-SREQ-211
    :test-id: SEG-TS-090
    """
    world = make_world(tmp_path)
    _invalid_case(world)
    revision = ["--revision", world.head]

    for command in (
        ["graph", "status", *world.args(), *revision],
        ["edge", "show", *world.args(), "--kind", "Refines"],
        ["graph", "check", "--case", str(world.case)],
        ["proof", "check", *world.args(), *revision, "--scope", "SREQ-1"],
    ):
        status, out = run(capsys, *command)
        assert status == 2, command
        assert out.strip()

    status, out = run(capsys, "graph", "status", "--json", *world.args(), *revision)
    assert status == 2
    assert json.loads(out)["error"]


def test_graph_check_counts_pending_strong_edges_only(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Graph check counts the pending strong edges and counts evidence edges by kind only.

    The legacy case holds 32 edges: four strong edges are pending, six are
    active, and 22 evidence edges are pending. Graph check on the case reports
    a pending count of four, and counts of 10 Confirms and 12 Witnesses edges
    by kind. A store with two outcomes, each with a Confirms and a Witnesses
    edge, and two strong edges, none affirmed, gives a pending count of two
    when it is the current stream. The report holds the node counts, the edge
    counts and the pending count, and no count of dangling endpoints.

    :verifies: SEG-SREQ-077
    :test-id: SEG-TS-091
    """
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "legacy-case"
    shutil.copytree(LEGACY_CASE / "case", legacy)

    status, out = run(capsys, "graph", "check", "--json", "--case", str(legacy))

    assert status == 0
    document = json.loads(out)
    assert document["pending"] == 4
    assert document["edgesByKind"]["Confirms"] == 10
    assert document["edgesByKind"]["Witnesses"] == 12
    assert set(document) == {"nodesByKind", "edgesByKind", "pending"}

    world = make_world(tmp_path / "world", outcomes=("head", "old"))
    status, out = run(capsys, "graph", "check", "--json", *world.args(config=False))
    assert status == 0
    document = json.loads(out)
    assert document["pending"] == 2
    assert document["edgesByKind"]["Confirms"] == 2
    assert set(document) == {"nodesByKind", "edgesByKind", "pending"}


def test_a_bundle_named_twice_is_read_once(tmp_path: Path, capsys) -> None:
    """A bundle named more than once in one invocation is read once.

    Graph status and proof check name the clean bundle twice, once as a path
    and once as a path that goes through another directory and back. Each
    gives the result of naming it once: graph status counts 76 outcomes at the
    current revision, and proof check lists three skipped outcomes. Two copies
    of the bundle named together are refused, because they supply the same
    outcome identities twice.

    :verifies: SEG-SREQ-232
    :test-id: SEG-TS-113
    """
    opened = session(tmp_path, [], capsys)
    bundle = copy_bundle(tmp_path, "first")
    (bundle.parent / "elsewhere").mkdir()
    again = bundle.parent / "elsewhere" / ".." / bundle.name
    twice = _naming(opened, bundle, again)

    status, document = _status(twice, capsys, "--revision", REVISION)
    assert status == 0
    assert document["evidence"] == {"current": OUTCOMES_PER_RUN, "stale": 0, "dangling": 0}
    status, report = _check(twice, capsys, "--revision", REVISION)
    assert status in (0, 1)
    assert len(report["skippedOutcomes"]) == 3

    copies = _naming(opened, bundle, copy_bundle(tmp_path, "copy"))
    status, _ = _status(copies, capsys, "--revision", REVISION)
    assert status == 2


def test_a_named_bundle_and_a_given_stream_cannot_be_judged_together(
    tmp_path: Path, capsys
) -> None:
    """A run bundle and a current stream given in one invocation give exit status 2.

    The current stream is a would-be store. Graph status, proof check and proof
    generate each run with the stream alone and are not refused. Each run with
    the stream and a named bundle exits with status 2, and the output holds a
    refusal and no verdict.

    :verifies: SEG-SREQ-233
    :test-id: SEG-TS-114
    """
    world = make_world(tmp_path / "world")
    bundle = ["--bundle", str(copy_bundle(tmp_path, "named"))]
    revision = ["--revision", world.head]
    scope = ["--scope", "SREQ-1"]
    verbs = (
        ["graph", "status", "--json"],
        ["proof", "check", "--json", *scope],
        ["proof", "generate", *scope, "--output-dir", str(tmp_path / "out")],
    )

    for command in verbs:
        status, _ = run(capsys, *command, *world.args(), *revision)
        assert status != 2, command
    for command in verbs:
        status, out = run(capsys, *command, *world.args(), *revision, *bundle)
        assert status == 2, command
        assert out.strip()
        for verdict in ('"edges"', '"blocked"', "snapshot:", "wrote "):
            assert verdict not in out, (command, verdict)
    assert not (tmp_path / "out" / "proofs").exists()


def test_a_named_bundle_needs_a_test_case_export(tmp_path: Path, capsys) -> None:
    """A run bundle named with no test-case export in the configuration gives exit status 2.

    A configuration that gives a test-case export lets graph status, proof
    check and proof generate judge the clean bundle (none exits with status 2).
    A configuration that gives none makes each of them exit with status 2 when
    the bundle is named, with a refusal and no verdict.

    :verifies: SEG-SREQ-235
    :test-id: SEG-TS-116
    """
    bundle = copy_bundle(tmp_path)
    revision = ["--revision", REVISION]
    verbs = (
        ["graph", "status", "--json"],
        ["proof", "check", "--json", *scope_args()],
        ["proof", "generate", *scope_args(), "--output-dir", str(tmp_path / "out")],
    )
    sound = session(tmp_path / "sound", [bundle], capsys)
    for command in verbs:
        status, _ = run(capsys, *command, *sound.evidence_args(), *revision)
        assert status != 2, command

    bare = session(tmp_path / "bare", [bundle], capsys, specifications=False)
    for command in verbs:
        status, out = run(capsys, *command, *bare.evidence_args(), *revision)
        assert status == 2, command
        for verdict in ('"edges"', '"blocked"', "snapshot:", "wrote "):
            assert verdict not in out, (command, verdict)
