"""Verification suite for ``proof verify`` on the command line.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests call the command line through ``affirmatrix.cli.main``, as an operator
would, and read the machine-readable report: a list of checks, each with a
``name``, a ``status`` (``passed``, ``failed``, ``not judged`` or ``not made``)
and a ``detail``. ``proof verify`` is read inside the test bodies only, so this
module collects before the code carries it.

The checks themselves have their own specifications in the modules of the
proof verifier. The tests here show what the command line does with them: it
names them, gives the verifier what the operator named, and turns the result
into an exit status.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from affirmatrix.cli import _judgement, main

from .evidence_support import REVISION, run, second_bundle, snapshot
from .proof_verify_support import (
    BUNDLE_CHECKS,
    CHECK_NAMES,
    PACKAGE_CHECKS,
    bundle_args,
    case_copy,
    cli_statuses,
    copy_package,
    edit,
    flip_digit,
    golden_copy,
    line_of,
    read,
    reseal,
    seal,
    verify_args,
    verify_cli,
    without_event,
)


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-256: proof verify does not exist yet")
def test_proof_verify_names_every_check_and_the_checks_it_did_not_make(
    tmp_path: Path, capsys
) -> None:
    """Proof verify names each check with its status, and names each check it did not make.

    For a generated package named with no run bundle and no request for the
    affirmations, the machine-readable report holds ten checks by name: root,
    identity, agreement, unblocked, affirmations, bundle-digests,
    design-guard, rebuilt-evidence, snapshot-id and sibling-digests. The
    first four are passed, and the other six are not made. With the clean
    bundle and the request for the affirmations, the first nine are passed
    and the check named sibling-digests is still not made. In the
    human-readable report one line starts with each name and holds the
    status. For a copy whose root is wrong, the line of the root check holds
    the word failed.

    :verifies: SEG-SREQ-256
    :test-id: SEG-TS-141
    """
    sealed = seal(tmp_path, capsys)
    opened = sealed.opened
    bare = verify_cli(capsys, opened, sealed.package.name)[1]
    assert [check["name"] for check in bare["checks"]] == list(CHECK_NAMES)
    found = cli_statuses(bare)
    assert {found[name] for name in PACKAGE_CHECKS} == {"passed"}
    not_made = ("affirmations", *BUNDLE_CHECKS, "sibling-digests")
    assert {found[name] for name in not_made} == {"not made"}

    full = cli_statuses(
        verify_cli(
            capsys,
            opened,
            sealed.package.name,
            *bundle_args(*opened.bundles),
            "--affirmations",
        )[1]
    )
    assert {name for name, status in full.items() if status == "passed"} == set(CHECK_NAMES[:-1])
    assert full["sibling-digests"] == "not made"

    _, text = run(
        capsys,
        "proof",
        "verify",
        *opened.args(),
        sealed.package.name,
        *bundle_args(*opened.bundles),
    )
    for name in CHECK_NAMES:
        assert ("not made" if name in ("affirmations", "sibling-digests") else "passed") in line_of(
            text, name
        ), name
    wrong = copy_package(sealed.package, tmp_path, "root")
    edit(wrong, "design_consistency_proof", lambda body: body.update(root="0" * 64))
    _, text = run(capsys, "proof", "verify", *opened.args(), str(wrong))
    assert "failed" in line_of(text, "root")


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-257: proof verify does not exist yet")
def test_proof_verify_gives_the_verifier_exactly_the_bundles_the_operator_names(
    tmp_path: Path, capsys
) -> None:
    """Proof verify judges the evidence by the run bundles named in the invocation and no others.

    One package lists the digests of two bundles, and another lists the
    digest of the clean bundle alone. Naming both bundles for the first gives
    exit status 0. Naming only the clean bundle for the first gives exit
    status 2. Naming no bundle gives exit status 0, with the bundle checks not
    made. For the second package, naming the clean bundle gives exit status 0,
    and naming the clean bundle and the second bundle gives exit status 1,
    because the second bundle is a bundle that the package does not list. The
    configuration names no bundle in any call.

    :verifies: SEG-SREQ-257
    :test-id: SEG-TS-142
    """
    (tmp_path / "both").mkdir()
    both = seal(tmp_path / "both", capsys, second=True)
    first, second = both.opened.bundles
    name = both.package.name

    assert verify_cli(capsys, both.opened, name, *bundle_args(first, second))[0] == 0
    assert verify_cli(capsys, both.opened, name, *bundle_args(first))[0] == 2
    status, none = verify_cli(capsys, both.opened, name)
    assert status == 0
    assert {cli_statuses(none)[check] for check in BUNDLE_CHECKS} == {"not made"}

    (tmp_path / "one").mkdir()
    one = seal(tmp_path / "one", capsys)
    unlisted = second_bundle(tmp_path / "one", "unlisted")
    clean = one.opened.bundles[0]
    assert verify_cli(capsys, one.opened, one.package.name, *bundle_args(clean))[0] == 0
    status, report = verify_cli(capsys, one.opened, one.package.name, *bundle_args(clean, unlisted))
    assert status == 1
    assert cli_statuses(report)["bundle-digests"] == "failed"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-258: proof verify does not exist yet")
def test_proof_verify_checks_the_affirmations_against_the_case_of_the_invocation(
    tmp_path: Path, capsys
) -> None:
    """Proof verify checks the affirmations only when asked, against the case that the call names.

    The case that holds a package binds every design edge. With the request
    for the affirmations, the check named affirmations is passed and the exit
    status is 0. A private copy of the case lacks the review event of one design
    edge. Naming that copy as the case, with the request, gives exit status 1
    and a failed affirmations check. Naming that copy without the request gives
    exit status 0 and the check not made.

    :verifies: SEG-SREQ-258
    :test-id: SEG-TS-143
    """
    sealed = seal(tmp_path, capsys)
    edge = read(sealed.package, "design_consistency_proof")["designEdges"][0]
    damaged = case_copy(sealed, tmp_path, "damaged", without_event(edge))
    package = str(sealed.package)

    status, report = verify_cli(capsys, sealed.opened, package, "--affirmations")
    assert status == 0
    assert cli_statuses(report)["affirmations"] == "passed"

    status, report = verify_cli(capsys, damaged, package, "--affirmations")
    assert status == 1
    assert cli_statuses(report)["affirmations"] == "failed"

    status, report = verify_cli(capsys, damaged, package)
    assert status == 0
    assert cli_statuses(report)["affirmations"] == "not made"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-259: proof verify does not exist yet")
def test_a_failed_check_gives_exit_status_1_even_when_another_check_is_not_judged(
    tmp_path: Path, capsys
) -> None:
    """Proof verify exits with status 1 when a check fails, even if another is not judged.

    Four private copies of a generated package fail one check each: a changed
    digit of a node hash (root), another requested scope in the evidence
    manifest (identity), a record that disagrees with the report
    (agreement), and a blocked scope (unblocked). Each gives exit status 1
    and names the failed check. A copy of a package that lists two bundles,
    with a wrong root, named with only one bundle, has a failed root check and
    a check that is not judged. It gives exit status 1.

    :verifies: SEG-SREQ-259
    :test-id: SEG-TS-144
    """
    sealed = seal(tmp_path, capsys)

    def digit(body: dict) -> None:
        body["nodeManifest"][0]["hash"] = flip_digit(body["nodeManifest"][0]["hash"])

    cases = (
        ("root", "design_consistency_proof", digit),
        (
            "identity",
            "evidence_manifest",
            lambda b: b.update(requestedScope=b["requestedScope"][:1]),
        ),
        (
            "agreement",
            "coverage_report",
            lambda b: b["staleOutcomes"].append(b["skippedOutcomes"][0]),
        ),
        ("unblocked", "coverage_report", lambda b: b.update(blocked=True)),
    )
    for name, document, tamper in cases:
        copy = copy_package(sealed.package, tmp_path, name)
        edit(copy, document, tamper)
        status, report = verify_cli(capsys, sealed.opened, copy)
        assert status == 1, name
        assert cli_statuses(report)[name] == "failed", name

    (tmp_path / "both").mkdir()
    both = seal(tmp_path / "both", capsys, second=True)
    wrong = copy_package(both.package, tmp_path, "wrong-and-unjudged")
    edit(wrong, "design_consistency_proof", digit)
    status, report = verify_cli(capsys, both.opened, wrong, *bundle_args(both.opened.bundles[0]))
    assert status == 1
    found = cli_statuses(report)
    assert found["root"] == "failed"
    assert found["bundle-digests"] == "not judged"


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-260: proof verify does not exist yet")
def test_a_check_that_cannot_be_judged_gives_exit_status_2_when_nothing_failed(
    tmp_path: Path, capsys
) -> None:
    """Proof verify exits with status 2 when an asked check is not judged and no check failed.

    A package lists two bundles and the call names one: the bundle checks are
    not judged, no check fails, and the exit status is 2. A copy of a
    package with one node hash changed and the root sealed again, named with
    the clean bundle, has a design guard that is not judged, no failed check, and
    exit status 2. The same two calls without any bundle give exit status 0.

    :verifies: SEG-SREQ-260
    :test-id: SEG-TS-145
    """
    both = seal(tmp_path, capsys, second=True)
    first = both.opened.bundles[0]

    status, report = verify_cli(capsys, both.opened, both.package, *bundle_args(first))
    assert status == 2
    assert "failed" not in cli_statuses(report).values()
    assert verify_cli(capsys, both.opened, both.package)[0] == 0

    (tmp_path / "one").mkdir()
    one = seal(tmp_path / "one", capsys)
    copy = copy_package(one.package, tmp_path, "node")

    def digit(body: dict) -> None:
        node = next(n for n in body["nodeManifest"] if n["id"] == "SD-REQ-001")
        node["hash"] = flip_digit(node["hash"])

    edit(copy, "design_consistency_proof", digit)
    reseal(copy)
    clean = one.opened.bundles[0]
    status, report = verify_cli(capsys, one.opened, copy, *bundle_args(clean))
    assert status == 2
    found = cli_statuses(report)
    assert found["design-guard"] == "not judged"
    assert "failed" not in found.values()
    assert verify_cli(capsys, one.opened, copy)[0] == 0


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-261: proof verify does not exist yet")
def test_a_package_whose_checks_all_pass_gives_exit_status_0(tmp_path: Path, capsys) -> None:
    """Proof verify exits with status 0 when every check made passed and every asked one was judged.

    For a generated package the exit status is 0 in four calls: with the
    package alone, with the clean bundle, with the request for the
    affirmations, and with both. A package that lists two bundles gives exit
    status 0 when both are named. The golden package, which lists none,
    gives exit status 0 with the package alone.

    :verifies: SEG-SREQ-261
    :test-id: SEG-TS-146
    """
    sealed = seal(tmp_path, capsys)
    clean = sealed.opened.bundles[0]
    package = sealed.package.name
    for extra in (
        [],
        bundle_args(clean),
        ["--affirmations"],
        [*bundle_args(clean), "--affirmations"],
    ):
        status, report = verify_cli(capsys, sealed.opened, package, *extra)
        assert status == 0, extra
        assert "failed" not in cli_statuses(report).values(), extra
        assert "not judged" not in cli_statuses(report).values(), extra

    (tmp_path / "both").mkdir()
    both = seal(tmp_path / "both", capsys, second=True)
    assert verify_cli(capsys, both.opened, both.package, *bundle_args(*both.opened.bundles))[0] == 0
    assert verify_cli(capsys, sealed.opened, golden_copy(tmp_path))[0] == 0


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-262: proof verify does not exist yet")
def test_proof_verify_obtains_no_implementation_revision(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proof verify takes no revision option and never asks for the revision of a repository.

    Naming an option --revision for proof verify is a usage error with exit
    status 2. The function that resolves the revision for the other proof
    verbs is replaced by one that records each call and fails. Proof verify,
    named with the clean bundle, still gives exit status 0 and the function
    was not called.

    :verifies: SEG-SREQ-262
    :test-id: SEG-TS-147
    """
    sealed = seal(tmp_path, capsys)
    clean = sealed.opened.bundles[0]
    with pytest.raises(SystemExit) as usage:
        main([*verify_args(sealed.opened, sealed.package.name), "--revision", REVISION])
    assert usage.value.code == 2
    capsys.readouterr()
    calls: list[str] = []

    def refuse(*args, **options):
        calls.append("resolve_gate_revision")
        raise AssertionError("proof verify asked for a revision")

    monkeypatch.setattr(_judgement, "resolve_gate_revision", refuse)

    status, _ = verify_cli(capsys, sealed.opened, sealed.package.name, *bundle_args(clean))

    assert status == 0
    assert calls == []


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-263: proof show and proof verify do not exist yet")
def test_proof_show_and_proof_verify_write_nothing(tmp_path: Path, capsys) -> None:
    """Proof show and proof verify leave every file of the case, bundles and configuration alone.

    A case holds a generated package, and its bundles and configuration lie
    beside it. Every file under the directory has its bytes recorded. Proof show,
    and proof verify with the package alone, with the bundle, with the
    request for the affirmations, and for a package that fails, each run
    with the machine-readable and the human-readable rendering. Afterwards
    the directory holds the same files with the same bytes, and no other.

    :verifies: SEG-SREQ-263
    :test-id: SEG-TS-148
    """
    sealed = seal(tmp_path, capsys)
    opened, name = sealed.opened, sealed.package.name
    clean = opened.bundles[0]
    failing = copy_package(sealed.package, tmp_path, "failing")
    edit(failing, "coverage_report", lambda body: body.update(blocked=True))
    before = snapshot(tmp_path)

    for rendering in (["--json"], []):
        run(capsys, "proof", "show", *rendering, *opened.args(), name)
        for extra in ([], bundle_args(clean), ["--affirmations"]):
            run(capsys, "proof", "verify", *rendering, *opened.args(), name, *extra)
        status, _ = run(capsys, "proof", "verify", *rendering, *opened.args(), str(failing))
        assert status == 1

    assert snapshot(tmp_path) == before


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-270: proof verify does not exist yet")
def test_proof_verify_judges_a_package_named_by_path_with_no_configuration_and_no_case(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proof verify judges the package checks of a package named by path from an empty directory.

    A generated package is copied to a place outside its case. The working
    directory is empty: it holds no configuration file and no case, and the
    call names neither. Given only the path of the copy, proof verify exits
    with status 0. The checks named root, identity, agreement and unblocked
    are passed, and the other six are not made. The directory is still empty
    afterwards.

    :verifies: SEG-SREQ-270
    :test-id: SEG-TS-159
    """
    sealed = seal(tmp_path, capsys)
    elsewhere = copy_package(sealed.package, tmp_path, "assessor")
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    status, out = run(capsys, "proof", "verify", "--json", str(elsewhere))

    assert status == 0, out
    found = cli_statuses(json.loads(out))
    assert {found[name] for name in PACKAGE_CHECKS} == {"passed"}
    assert {name for name, state in found.items() if state == "not made"} == set(CHECK_NAMES) - set(
        PACKAGE_CHECKS
    )
    assert list(empty.iterdir()) == []
