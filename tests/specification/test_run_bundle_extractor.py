"""Verification suite for the outcome extractor over run bundles and the configured runs.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
extractor reads each run from its run bundle: the run artifact, one record of
the revision and one dirty flag for each checkout, and the run name. It checks
the bundle's digest against the configured one.

Every test writes a configuration over the frozen exports with
``evidence_support.write_config`` and takes the records the configured producer
supplies. A bundle is a copy of the clean bundle in ``tmp_path``, changed in the
way the test needs. The configuration names the bundle and its digest; the
digest is computed for the changed copy, unless the test is about a digest. The
implementation checkout is the one the top-level key ``implementation`` names:
its revision is in ``<name>.sha`` and its dirty flag in ``<name>.dirty``.

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
from affirmatrix.cli import main
from affirmatrix.sources import SourceError

from .evidence_support import (
    OTHER_CHECKOUT_REVISION,
    OUTCOMES_PER_RUN,
    REVISION,
    RUN_NAME,
    TOOLBOX,
    copy_bundle,
    recipe_digest,
    streams,
    write_config,
)


def _accepted(tmp_path: Path, bundle: Path, **options) -> list:
    """The outcome nodes that the configuration over one bundle supplies."""
    nodes, _ = streams(write_config(tmp_path, [bundle], **options))
    return [node for node in nodes if node.kind == "TestOutcome"]


def _refused(tmp_path: Path, bundle: Path, word: str, **options) -> None:
    """The configuration over one bundle is refused with an error that holds ``word``."""
    with pytest.raises(SourceError, match=f"(?i){re.escape(word)}"):
        streams(write_config(tmp_path, [bundle], **options))


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-219: the extractor reads three loose records")
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


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-221: the extractor checks no digest")
def test_a_digest_that_differs_from_the_configured_one_is_refused(tmp_path: Path) -> None:
    """A bundle whose digest differs from the configured digest is refused.

    The configuration gives the clean bundle's digest: the extractor supplies
    76 outcomes. The configuration then gives a digest that differs in its last
    digit: the extractor refuses the run and names the digest. A bundle with
    one byte of its run artifact changed, under the configured digest of the
    unchanged bundle, is refused the same way.

    :verifies: SEG-SREQ-221
    :test-id: SEG-TS-070
    """
    bundle = copy_bundle(tmp_path)
    right = recipe_digest(bundle)
    assert len(_accepted(tmp_path, bundle)) == OUTCOMES_PER_RUN

    wrong = right[:-1] + ("0" if right[-1] != "0" else "1")
    _refused(tmp_path, bundle, "digest", digests=[wrong])

    artifact = bundle / "twister.json"
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    _refused(tmp_path, bundle, "digest", digests=[right])


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-222: no code reads a dirty flag")
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
    strict=True, reason="SEG-SREQ-223: the extractor reads the name from a loose record"
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


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-224: the extractor is given the artifact path")
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


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-225: the extractor takes no bundle")
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


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-186: the revision comes from a loose record")
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


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-187: the revision comes from a loose record")
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


def _old_style(tmp_path: Path, file: str) -> Path:
    """A configuration whose one run names its artifact, revision record and name record."""
    path = write_config(tmp_path, [copy_bundle(tmp_path, "old-bundle")], where=file)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["producer"]["outcomes"] = [
        {
            "artifact": str(tmp_path / "run" / "twister.json"),
            "revision": str(tmp_path / "run" / "toolbox.sha"),
            "name": str(tmp_path / "run" / "run.name"),
            "repository": "evidence",
        }
    ]
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _without_digest(tmp_path: Path, file: str) -> Path:
    path = write_config(tmp_path, [copy_bundle(tmp_path, "other")], where=file)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    del document["producer"]["outcomes"][0]["digest"]
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-197: a run carries an artifact, a revision and a name"
)
def test_a_run_carries_a_bundle_and_a_digest_and_an_old_run_entry_is_refused(
    tmp_path: Path,
) -> None:
    """A run in the configuration carries a bundle location and a digest.

    A configuration whose run gives a bundle and a digest loads. A
    configuration whose run gives a bundle and no digest is refused with a
    configuration error. A configuration whose run gives the old keys
    (``artifact``, ``revision`` and ``name``) is refused with a configuration
    error. Each of the two refused files gives exit status 2 to a command
    that reads it, ``graph check`` and ``case check`` among them.

    :verifies: SEG-SREQ-197
    :test-id: SEG-TS-077
    """
    good = write_config(tmp_path, [copy_bundle(tmp_path)], where="good")
    assert config.load(good).producer is not None

    refused = (_without_digest(tmp_path, "no-digest"), _old_style(tmp_path, "old"))
    for path in refused:
        with pytest.raises(config.ConfigError):
            config.load(path)
        for command in (["graph", "check"], ["case", "check"]):
            case_root = str(tmp_path / "case-refused")
            assert main([*command, "--case", case_root, "--config", str(path)]) == 2
