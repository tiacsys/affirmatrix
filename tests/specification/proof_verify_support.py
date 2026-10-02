"""Shared helpers of the verification suites for ``proof show`` and ``proof verify``.

Not a specification. The modules that realize specifications import these
helpers: a package the generator writes over the frozen evidence, a private
copy of it, the tampers that change one thing in a copy, an independent
recomputation of the design root, and a reader of the report of ``proof verify``.

The root recipe here is the one of the tutorial on verifying a proof, written a
second time so that a test never asks the tool for the value it checks.

The tests call the library as ``affirmatrix.proof.verify(package, config=...,
bundles=..., case=...)`` and the command line as ``proof show`` and
``proof verify``. Both names are read inside test bodies only.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from affirmatrix import commitment, config
from affirmatrix.case import AffirmationStore

from .evidence_support import (
    EVALUATION_DATE,
    GOLDEN,
    REVISION,
    TIMESTAMP,
    Session,
    affirm_design,
    copy_bundle,
    load_json,
    run,
    scope_args,
    second_bundle,
    session,
)

#: Every check a report of ``proof verify`` holds, by name.
CHECK_NAMES = (
    "root",
    "identity",
    "agreement",
    "unblocked",
    "affirmations",
    "bundle-digests",
    "design-guard",
    "rebuilt-evidence",
    "snapshot-id",
    "sibling-digests",
)
#: The checks that need run bundles, and the one that needs the case.
BUNDLE_CHECKS = ("bundle-digests", "design-guard", "rebuilt-evidence", "snapshot-id")
PACKAGE_CHECKS = ("root", "identity", "agreement", "unblocked")

NODE_IRI = "https://affirmatrix.dev/case/node/"
DOCUMENTS = (
    "design_consistency_proof",
    "execution_coverage_record",
    "coverage_report",
    "evidence_manifest",
)


@dataclass(frozen=True)
class Sealed:
    """A case with a package in it, and what the generator was given."""

    opened: Session
    package: Path

    @property
    def case(self) -> Path:
        return self.opened.case


def seal(tmp_path: Path, capsys, *, second: bool = False, timestamp: str = TIMESTAMP) -> Sealed:
    """Generate the package for the golden scope into a case with every strong edge affirmed.

    With ``second`` a second bundle, recorded at another revision, is named too,
    and the package lists the digests of both bundles.
    """
    bundles = [copy_bundle(tmp_path, "first")]
    if second:
        bundles.append(second_bundle(tmp_path, "second"))
    opened = session(tmp_path, bundles, capsys)
    affirm_design(opened, capsys)
    sealed = Sealed(opened=opened, package=Path())
    return Sealed(opened=opened, package=generate_more(sealed, capsys, timestamp))


def generate_more(sealed: Sealed, capsys, timestamp: str) -> Path:
    """Generate one more package into the same case, at another timestamp."""
    status, out = run(
        capsys,
        "proof",
        "generate",
        *sealed.opened.evidence_args(),
        *scope_args(),
        "--revision",
        REVISION,
        "--timestamp",
        timestamp,
        "--evaluation-date",
        EVALUATION_DATE,
    )
    assert status == 0, out
    (identifier,) = re.findall(r"^snapshot: (\S+)$", out, flags=re.MULTILINE)
    return sealed.case / "proofs" / identifier


def copy_package(package: Path, tmp_path: Path, label: str, *, name: str | None = None) -> Path:
    """A private copy of a package directory, safe to change: one copy for each tamper."""
    target = tmp_path / "copies" / label / (name or package.name)
    shutil.copytree(package, target)
    return target


def golden_copy(tmp_path: Path, label: str = "golden", arm: str = "one_run") -> Path:
    """A private copy of the golden package. It was sealed before packages listed run bundles."""
    (package,) = sorted((GOLDEN / arm / "proofs").iterdir())
    return copy_package(package, tmp_path, label)


def read(package: Path, document: str) -> dict:
    return load_json(package / f"{document}.jsonld")


def edit(package: Path, document: str, change: Callable[[dict], None]) -> None:
    """Change one document of a package in place, as one hand edit would."""
    path = package / f"{document}.jsonld"
    body = json.loads(path.read_text(encoding="utf-8"))
    change(body)
    path.write_text(
        json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def independent_root(package: Path) -> str:
    """The design root by the recipe of the tutorial: nothing but the design consistency proof."""
    proof = read(package, "design_consistency_proof")
    metadata = json.dumps(
        {"scope": proof["scope"], "revision": proof["revision"]},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    node_hashes = [bytes.fromhex(node["hash"]) for node in proof["nodeManifest"]]
    edges = [(edge["from"], edge["to"], edge["kind"]) for edge in proof["designEdges"]]
    return commitment.design_root(metadata, node_hashes, edges).hex()


def reseal(package: Path) -> None:
    """Write the root of the current design into the package, so that only the design differs."""
    root = independent_root(package)
    edit(package, "design_consistency_proof", lambda body: body.update(root=root))


def flip_digit(digest: str) -> str:
    """The same hexadecimal string with its first digit changed."""
    return ("0" if digest[0] != "0" else "1") + digest[1:]


def missing_edge(package: Path) -> dict:
    """A Refines edge between two requirements of the package that the package does not hold."""
    proof = read(package, "design_consistency_proof")
    held = {(e["from"], e["to"], e["kind"]) for e in proof["designEdges"]}
    ids = [n["id"] for n in proof["nodeManifest"] if n["kind"] == "Requirement"]
    for source in ids:
        for target in ids:
            if source != target and (source, target, "Refines") not in held:
                return {"from": source, "to": target, "kind": "Refines"}
    raise AssertionError("every pair of requirements is joined")


def expected_requirements(package: Path) -> dict[str, dict]:
    """What the package records for each requirement, read from its documents by hand."""
    proof = read(package, "design_consistency_proof")
    record = read(package, "execution_coverage_record")
    requirements = sorted(n["id"] for n in proof["nodeManifest"] if n["kind"] == "Requirement")
    edges = proof["designEdges"]

    def sources(kind: str, target: str) -> list[str]:
        return sorted(e["from"] for e in edges if e["kind"] == kind and e["to"] == target)

    expected = {}
    for requirement in requirements:
        specifications = sources("Verifies", requirement)
        expected[requirement] = {
            "refinedBy": sources("Refines", requirement),
            "specifications": specifications,
            "implementations": sources("Implements", requirement),
            "outcomes": sorted(
                (o["id"], o["result"])
                for o in record["outcomes"]
                if o["confirms"] in specifications
            ),
        }
    return expected


# --- Reading the report of the command line ---------------------------------------------


def statuses(report) -> dict[str, str]:
    """The status of each check of a library report, by check name."""
    return {check.name: str(check.status) for check in report.checks}


def cli_statuses(document: dict) -> dict[str, str]:
    """The status of each check of a ``proof verify --json`` report, by check name."""
    return {check["name"]: check["status"] for check in document["checks"]}


def verify_args(opened: Session, package: Path | str, *extra: str) -> list[str]:
    return ["proof", "verify", "--json", *opened.args(), str(package), *extra]


def bundle_args(*bundles: Path) -> list[str]:
    return [item for bundle in bundles for item in ("--bundle", str(bundle))]


def verify_cli(capsys, opened: Session, package: Path | str, *extra: str) -> tuple[int, dict]:
    """Run ``proof verify --json`` and return the exit status and the parsed report."""
    status, out = run(capsys, *verify_args(opened, package, *extra))
    return status, json.loads(out)


def show_cli(capsys, opened: Session, package: Path | str) -> tuple[int, dict]:
    status, out = run(capsys, "proof", "show", "--json", *opened.args(), str(package))
    return status, json.loads(out)


def library_verify(opened: Session, package: Path, *, bundles=(), with_case: bool = False):
    """Call the library verifier as an application would."""
    from affirmatrix import proof

    loaded = config.load(opened.config, case=opened.case)
    kwargs: dict = {"config": loaded, "bundles": tuple(bundles)}
    if with_case:
        kwargs["case"] = AffirmationStore(root=loaded.case)
    return proof.verify(package, **kwargs)


# --- Review events of a case copy ---------------------------------------------------------


def is_edge_event(event: dict, edge: dict) -> bool:
    """Whether a review event binds the given design edge of a package."""
    return (
        event["seg:from"] == NODE_IRI + edge["from"]
        and event["seg:to"] == NODE_IRI + edge["to"]
        and event["seg:relation"] == "seg:" + edge["kind"]
    )


def case_copy(
    sealed: Sealed, tmp_path: Path, label: str, change: Callable[[list], list]
) -> Session:
    """A private copy of the case with its review events changed; a session that names the copy."""
    target = tmp_path / "cases" / label
    shutil.copytree(sealed.case, target)
    events = target / "events" / "review_events.jsonld"
    document = json.loads(events.read_text(encoding="utf-8"))
    document["@graph"] = change(document["@graph"])
    events.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return Session(config=sealed.opened.config, case=target, bundles=sealed.opened.bundles)


def without_event(edge: dict) -> Callable[[list], list]:
    """A change that removes the one review event of a design edge."""
    return lambda graph: [event for event in graph if not is_edge_event(event, edge)]


def with_other_hash(edge: dict) -> Callable[[list], list]:
    """A change that moves the content hash of the requirement end of an event by one digit."""

    def change(graph: list) -> list:
        for event in graph:
            if is_edge_event(event, edge):
                anchors = event["seg:toContentAnchors"]
                anchors["seg:contentHash"] = flip_digit(anchors["seg:contentHash"])
        return graph

    return change


def line_of(out: str, name: str) -> str:
    """The one line of a rendering that starts with a check name, ignoring leading blanks."""
    lines = [line for line in out.splitlines() if line.strip().startswith(name)]
    assert len(lines) == 1, (name, out)
    return lines[0]
