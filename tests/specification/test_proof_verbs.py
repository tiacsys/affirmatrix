"""Verification suite for the verbs of the proof noun and the recipe of the design root.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests call the command line through ``affirmatrix.cli.main``, as an operator
would. The first and the last test pass against the code that exists before
``proof show`` and ``proof verify``: they guard what the generator already does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .evidence_support import (
    REVISION,
    affirm_design,
    copy_bundle,
    run,
    scope_args,
    session,
)
from .proof_verify_support import (
    copy_package,
    edit,
    flip_digit,
    golden_copy,
    independent_root,
    read,
    seal,
    show_cli,
    verify_cli,
)


def test_proof_check_and_proof_generate_are_verbs_of_their_own(tmp_path: Path, capsys) -> None:
    """The operator asks the gate about a scope and generates the package, each as its own verb.

    Over the frozen evidence and a case with every strong edge affirmed, proof
    check reports the gate's coverage report as machine-readable output and
    exits with status 0, and writes nothing. Proof generate, as a separate
    verb, writes the four documents of a package under the case and exits with
    status 0.

    :verifies: SEG-SREQ-089
    :test-id: SEG-TS-149
    """
    opened = session(tmp_path, [copy_bundle(tmp_path)], capsys)
    affirm_design(opened, capsys)
    revision = ["--revision", REVISION]

    status, out = run(
        capsys,
        "proof",
        "check",
        "--json",
        *opened.evidence_args(),
        *scope_args(),
        *revision,
    )
    assert status == 0
    assert '"blocked": false' in out
    assert not (opened.case / "proofs").exists() or not list((opened.case / "proofs").iterdir())

    status, out = run(
        capsys, "proof", "generate", *opened.evidence_args(), *scope_args(), *revision
    )
    assert status == 0
    (package,) = sorted((opened.case / "proofs").iterdir())
    assert len(list(package.glob("*.jsonld"))) == 4


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-089: proof show and proof verify do not exist yet")
def test_proof_show_and_proof_verify_are_verbs_of_their_own(tmp_path: Path, capsys) -> None:
    """The operator shows and verifies an evidence package, each as its own verb.

    For a generated package, proof show exits with status 0 and its
    machine-readable report holds a list of requirements and no list of
    checks. Proof verify, as a separate verb, exits with status 0 and its
    machine-readable report holds a list of checks and no list of
    requirements.

    :verifies: SEG-SREQ-089
    :test-id: SEG-TS-150
    """
    sealed = seal(tmp_path, capsys)

    shown_status, shown = show_cli(capsys, sealed.opened, sealed.package.name)
    verified_status, verified = verify_cli(capsys, sealed.opened, sealed.package.name)

    assert (shown_status, verified_status) == (0, 0)
    assert "requirements" in shown and "checks" not in shown
    assert "checks" in verified and "requirements" not in verified


def test_the_design_root_of_a_package_is_recomputed_from_its_own_design_consistency_proof(
    tmp_path: Path, capsys
) -> None:
    """The root of a package is the root that the design consistency proof's own contents give.

    Two packages are generated, one over the clean bundle and one over the
    clean bundle and a second bundle at another revision. For each, the recipe
    of the tutorial gives the recorded root from the node hashes, the design
    edges, the scope and the revision of the design consistency proof, and from
    nothing else. The golden package gives the root of the golden file. A
    copy of a package with one digit of a node hash changed gives another
    root than the recorded one.

    :verifies: SEG-SREQ-037
    :test-id: SEG-TS-151
    """
    one = seal(tmp_path, capsys)
    (tmp_path / "two").mkdir()
    two = seal(tmp_path / "two", capsys, second=True)
    golden = golden_copy(tmp_path)

    for package in (one.package, two.package, golden):
        recorded = read(package, "design_consistency_proof")["root"]
        assert independent_root(package) == recorded, package.name

    changed = copy_package(one.package, tmp_path, "digit")

    def digit(body: dict) -> None:
        body["nodeManifest"][0]["hash"] = flip_digit(body["nodeManifest"][0]["hash"])

    edit(changed, "design_consistency_proof", digit)
    assert independent_root(changed) != read(changed, "design_consistency_proof")["root"]
