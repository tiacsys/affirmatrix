"""Verification suite for the outcome extractor over run bundles.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
extractor reads each run from its run bundle: the run artifact, one record of
the revision and one dirty flag for each checkout, and the run name. A caller
names the bundles; the configuration names none and no digest is expected.

Retired: SEG-TS-070 (the check of a bundle against a configured digest) and
SEG-TS-077 (run entries in the configuration). Their requirements are
withdrawn. The identifiers are never reused.

Every test writes a configuration over the frozen exports with
``evidence_support.write_config`` and takes the records the producer supplies
over the named bundles. A bundle is a copy of the clean bundle in ``tmp_path``,
changed in the way the test needs. The implementation checkout is the one the
top-level key ``implementation`` names: its revision is in ``<name>.sha`` and its
dirty flag in ``<name>.dirty``.

Each refusal test starts with a control: the unchanged bundle is accepted. A
test of a refusal therefore fails for the claim and never for a configuration
that cannot be read at all. The tests read the refusal as an error of the
sources (``SourceError``) whose text names what is wrong; they never pin the
wording beyond one keyword.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from affirmatrix import config
from affirmatrix.sources import SourceError

from .evidence_support import (
    OTHER_CHECKOUT_REVISION,
    OUTCOMES_PER_RUN,
    REVISION,
    RUN_NAME,
    TOOLBOX,
    copy_bundle,
    recipe_digest,
    run,
    session,
    streams,
    write_config,
)


def _accepted(tmp_path: Path, bundle: Path, **options) -> list:
    """The outcome nodes that the configuration over one bundle supplies."""
    nodes, _ = streams(write_config(tmp_path, **options), [bundle])
    return [node for node in nodes if node.kind == "TestOutcome"]


def _refused(tmp_path: Path, bundle: Path, word: str, **options) -> None:
    """The configuration over one bundle is refused with an error that holds ``word``."""
    with pytest.raises(SourceError, match=f"(?i){re.escape(word)}"):
        streams(write_config(tmp_path, **options), [bundle])


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-219: the producer takes no bundles named by the caller"
)
def test_a_run_is_read_from_its_bundle_and_from_no_other_record(tmp_path: Path) -> None:
    """A run is read from its bundle and from no other record.

    The bundle lies in a directory that also holds a revision record, a name
    record and a run artifact of the same names, with other content: another
    revision, another run name and an artifact whose every result failed. The
    configuration names the bundle. All 76 outcomes carry the revision and the
    run name of the bundle, and none carries a result of the other artifact.

    :verifies: SEG-SREQ-219
    :test-id: SEG-TS-069
    """
    bundle = copy_bundle(tmp_path)
    beside = bundle.parent
    (beside / "toolbox.sha").write_text("9" * 40 + "\n", encoding="utf-8")
    (beside / "run.name").write_text("decoy-name\n", encoding="utf-8")
    decoy = (bundle / "twister.json").read_text(encoding="utf-8").replace('"passed"', '"failed"')
    (beside / "twister.json").write_text(decoy, encoding="utf-8")

    outcomes = _accepted(tmp_path, bundle)

    assert len(outcomes) == OUTCOMES_PER_RUN
    assert {node.revision for node in outcomes} == {REVISION}
    assert all(node.local_id.startswith(RUN_NAME) for node in outcomes)
    assert {node.result.value for node in outcomes} == {"passed", "skipped"}


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-222: the producer takes no bundles named by the caller"
)
def test_a_run_whose_implementation_checkout_was_dirty_is_refused(tmp_path: Path) -> None:
    """A bundle that records a dirty implementation checkout is refused.

    The clean bundle is accepted. With the dirty file of the implementation
    checkout holding one line of ``git status`` output, the extractor refuses
    the run and names the dirty flag. With the dirty file of the other
    checkout holding such a line, the bundle is accepted and supplies 76
    outcomes. When the configuration names the other checkout as the
    implementation checkout, its dirty file refuses the run, and the dirty
    file of the first checkout does not.

    :verifies: SEG-SREQ-222
    :test-id: SEG-TS-071
    """
    assert len(_accepted(tmp_path, copy_bundle(tmp_path, "clean"))) == OUTCOMES_PER_RUN

    own = copy_bundle(tmp_path, "own")
    (own / "toolbox.dirty").write_text(" M src/safe_data.c\n", encoding="utf-8")
    _refused(tmp_path, own, "dirty")

    other = copy_bundle(tmp_path, "other")
    (other / "zephyr.dirty").write_text("?? build/\n", encoding="utf-8")
    assert len(_accepted(tmp_path, other)) == OUTCOMES_PER_RUN

    _refused(tmp_path, other, "dirty", implementation="zephyr")
    assert len(_accepted(tmp_path, own, implementation="zephyr")) == OUTCOMES_PER_RUN


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-223: the producer takes no bundles named by the caller"
)
def test_a_run_with_no_recorded_name_is_refused(tmp_path: Path) -> None:
    """A bundle that records no run name is refused.

    The clean bundle is accepted. With the name record deleted, empty, or
    holding only a line feed, the extractor refuses the run and names the run
    name.

    :verifies: SEG-SREQ-223
    :test-id: SEG-TS-072
    """
    assert len(_accepted(tmp_path, copy_bundle(tmp_path, "clean"))) == OUTCOMES_PER_RUN

    missing = copy_bundle(tmp_path, "missing")
    (missing / "run.name").unlink()
    _refused(tmp_path, missing, "name")
    for label, text in (("empty", ""), ("blank", "\n")):
        variant = copy_bundle(tmp_path, label)
        (variant / "run.name").write_text(text, encoding="utf-8")
        _refused(tmp_path, variant, "name")


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-224: the producer takes no bundles named by the caller"
)
def test_a_bundle_with_no_readable_run_artifact_is_refused(tmp_path: Path) -> None:
    """A bundle that holds no readable run artifact is refused.

    The clean bundle is accepted. With the run artifact deleted, the extractor
    refuses the run, although the bundle still holds a test plan, two XML
    reports, the revisions and the name. With the run artifact replaced by text
    that is not JSON, the extractor refuses the run.

    :verifies: SEG-SREQ-224
    :test-id: SEG-TS-073
    """
    assert len(_accepted(tmp_path, copy_bundle(tmp_path, "clean"))) == OUTCOMES_PER_RUN

    missing = copy_bundle(tmp_path, "missing")
    (missing / "twister.json").unlink()
    assert (missing / "testplan.json").exists()
    _refused(tmp_path, missing, "artifact")

    unreadable = copy_bundle(tmp_path, "unreadable")
    (unreadable / "twister.json").write_text("this is not a report", encoding="utf-8")
    _refused(tmp_path, unreadable, "artifact")


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-225: the producer takes no bundles named by the caller"
)
def test_an_export_with_a_build_timestamp_is_refused(tmp_path: Path) -> None:
    """A need export that carries a build timestamp is refused.

    The clean bundle with the frozen exports is accepted. A copy of the
    test-specification export with a ``created`` entry at its top level makes
    the extractor refuse the run and name the timestamp. So does a copy of the
    implementation export with such an entry.

    :verifies: SEG-SREQ-225
    :test-id: SEG-TS-074
    """
    bundle = copy_bundle(tmp_path)
    assert len(_accepted(tmp_path, bundle)) == OUTCOMES_PER_RUN

    for label, source, option in (
        ("specification", TOOLBOX / "needs/test-specification/needs.json", "specification_export"),
        ("implementation", TOOLBOX / "needs/api-traceability/needs.json", "implementation_export"),
    ):
        import json

        document = json.loads(source.read_text(encoding="utf-8"))
        document["created"] = "2026-10-01T12:00:00"
        stamped = tmp_path / f"{label}.json"
        stamped.write_text(json.dumps(document), encoding="utf-8")
        _refused(tmp_path, bundle, "timestamp", **{option: stamped})


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-186: the producer takes no bundles named by the caller"
)
def test_an_outcomes_revision_is_the_implementation_checkouts_revision_in_the_bundle(
    tmp_path: Path,
) -> None:
    """Each outcome's revision is the revision the bundle records for the implementation checkout.

    The clean bundle records a different revision for each of its two
    checkouts. With the first as the implementation checkout, all 76 outcomes
    carry the first revision. With the second, all carry the second revision.
    A record of the implementation checkout that holds a short word is taken
    exactly as recorded.

    :verifies: SEG-SREQ-186
    :test-id: SEG-TS-075
    """
    bundle = copy_bundle(tmp_path)

    toolbox = _accepted(tmp_path, bundle)
    zephyr = _accepted(tmp_path, bundle, implementation="zephyr")

    assert len(toolbox) == OUTCOMES_PER_RUN
    assert {node.revision for node in toolbox} == {REVISION}
    assert {node.revision for node in zephyr} == {OTHER_CHECKOUT_REVISION}

    word = copy_bundle(tmp_path, "word")
    (word / "toolbox.sha").write_text("a-word\n", encoding="utf-8")
    assert {node.revision for node in _accepted(tmp_path, word)} == {"a-word"}


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-187: the producer takes no bundles named by the caller"
)
def test_a_run_with_no_recorded_revision_is_refused(tmp_path: Path) -> None:
    """A bundle that records no revision for the implementation checkout is refused.

    The clean bundle is accepted. With the revision record of the
    implementation checkout deleted, empty, or holding only a line feed, the
    extractor refuses the run and names the revision. It refuses the run too
    when the configuration names an implementation checkout of which the
    bundle holds no record. A missing record of another checkout does not
    refuse the run.

    :verifies: SEG-SREQ-187
    :test-id: SEG-TS-076
    """
    assert len(_accepted(tmp_path, copy_bundle(tmp_path, "clean"))) == OUTCOMES_PER_RUN

    missing = copy_bundle(tmp_path, "missing")
    (missing / "toolbox.sha").unlink()
    _refused(tmp_path, missing, "revision")
    for label, text in (("empty", ""), ("blank", "\n")):
        variant = copy_bundle(tmp_path, label)
        (variant / "toolbox.sha").write_text(text, encoding="utf-8")
        _refused(tmp_path, variant, "revision")

    _refused(tmp_path, copy_bundle(tmp_path, "unnamed"), "revision", implementation="nowhere")

    other = copy_bundle(tmp_path, "other")
    (other / "zephyr.sha").unlink()
    assert len(_accepted(tmp_path, other)) == OUTCOMES_PER_RUN


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-234: the configuration still accepts a run entry")
def test_a_configuration_that_names_a_run_is_refused(tmp_path: Path, capsys) -> None:
    """A configuration that names a run is refused, whatever the entry holds.

    A configuration with no run loads. A configuration whose producer holds
    ``outcomes`` is refused with a configuration error: with a list of run
    entries that give a bundle and a digest, with a list of entries that give
    the old keys, and with an empty list. Graph check and case check, which read
    the configuration, exit with status 2 and print the refusal.

    :verifies: SEG-SREQ-234
    :test-id: SEG-TS-115
    """
    assert config.load(write_config(tmp_path)).producer is not None
    bundle = str(copy_bundle(tmp_path))
    kinds = {
        "entries": [{"bundle": bundle, "digest": "sha256:" + "a" * 64}],
        "old": [{"artifact": "twister.json", "revision": "toolbox.sha", "name": "run.name"}],
        "empty": [],
    }
    for label, outcomes in kinds.items():
        path = write_config(tmp_path, where=label)
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        document["producer"]["outcomes"] = outcomes
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
        with pytest.raises(config.ConfigError):
            config.load(path)
        for command in (["graph", "check"], ["case", "check"]):
            status, out = run(
                capsys, *command, "--case", str(tmp_path / f"case-{label}"), "--config", str(path)
            )
            assert status == 2, (label, command)
            assert out.strip()


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-224: the producer takes no bundles named by the caller"
)
def test_a_path_that_is_not_a_directory_is_refused(tmp_path: Path, capsys) -> None:
    """A path named as a run bundle that is not a directory with a readable artifact is refused.

    The clean bundle is accepted. A path that does not exist, a path that is a
    plain file, and an empty directory each make the extractor refuse the run.
    Graph status exits with status 2 when it names the plain file.

    :verifies: SEG-SREQ-224
    :test-id: SEG-TS-117
    """
    assert len(_accepted(tmp_path, copy_bundle(tmp_path, "clean"))) == OUTCOMES_PER_RUN

    plain = tmp_path / "bundles" / "plain-file"
    plain.write_text("not a bundle\n", encoding="utf-8")
    empty = tmp_path / "bundles" / "empty-directory"
    empty.mkdir()
    for path in (tmp_path / "bundles" / "not-there", plain, empty):
        with pytest.raises(SourceError):
            streams(write_config(tmp_path), [path])

    opened = session(tmp_path, [plain], capsys)
    status, out = run(capsys, "graph", "status", *opened.evidence_args(), "--revision", REVISION)
    assert status == 2
    assert out.strip()


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-190: the anchor names a repository, not the bundle"
)
def test_an_anchor_names_the_bundle_by_its_digest(tmp_path: Path) -> None:
    """An outcome's anchor names its run bundle by the digest, wherever the bundle lies.

    Each of the 76 outcomes of the clean bundle has an anchor whose repository
    member is the bundle's digest written as ``sha256:`` and 64 hex digits, whose
    path is the run artifact within the bundle (twister.json), and whose locator
    is ``nodeid:`` and a test identifier. A copy of the bundle in another
    directory under another name gives the same anchors. A copy with one added
    file has another digest and so another repository member, and the same path.

    :verifies: SEG-SREQ-190
    :test-id: SEG-TS-118
    """
    first = copy_bundle(tmp_path, "first")
    digest = f"sha256:{recipe_digest(first)}"

    def anchors(bundle: Path) -> set[tuple[str, str, str]]:
        found = set()
        for node in _accepted(tmp_path, bundle):
            anchor = node.content_anchors["contentHash"]
            found.add((anchor.repository, anchor.path, anchor.locator))
        return found

    base = anchors(first)
    assert len(base) == OUTCOMES_PER_RUN
    assert {repository for repository, _, _ in base} == {digest}
    assert {path for _, path, _ in base} == {"twister.json"}
    assert all(locator.startswith("nodeid:") for _, _, locator in base)

    assert anchors(copy_bundle(tmp_path / "elsewhere", "other-name")) == base

    added = copy_bundle(tmp_path, "added")
    (added / "notes.txt").write_text("a new file\n", encoding="utf-8")
    other = anchors(added)
    assert {repository for repository, _, _ in other} == {f"sha256:{recipe_digest(added)}"}
    assert {path for _, path, _ in other} == {"twister.json"}
    assert {repository for repository, _, _ in other} != {digest}
