"""A package read back from a directory, and what it says about itself.

:func:`read_package` reads the four documents of an evidence package from any
directory, with or without a case, and :func:`summarize` states what they
record. Neither judges anything. The verifier (:mod:`affirmatrix.proof._verify`)
and ``proof show`` both start here, so they read a package the same way.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from affirmatrix import case


@dataclass(frozen=True, slots=True)
class StoredPackage:
    """The four documents of one evidence package, as written, valid against the schemas.

    Each document is the plain mapping the file holds, without its ``@context``.
    """

    design: Mapping[str, object]
    record: Mapping[str, object]
    report: Mapping[str, object]
    manifest: Mapping[str, object]


def read_package(directory: Path) -> StoredPackage:
    """Read the four documents of the package in ``directory``.

    :implements: SEG-SREQ-254
    :implements: SEG-SREQ-270

    Needs no case and no configuration: the documents are checked against the
    schemas the tool carries. Raises :class:`~affirmatrix.case.AffirmationStoreError`
    for a directory that holds no package, a document that is missing, is not
    JSON or is not valid. Writes nothing.
    """
    documents = case.read_package_directory(directory)
    return StoredPackage(
        design=documents["design_consistency_proof"],
        record=documents["execution_coverage_record"],
        report=documents["coverage_report"],
        manifest=documents["evidence_manifest"],
    )


@dataclass(frozen=True, slots=True)
class RequirementEntry:
    """What a package records for one requirement of its scope."""

    identifier: str
    refined_by: tuple[str, ...]
    specifications: tuple[str, ...]
    implementations: tuple[str, ...]
    outcomes: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Summary:
    """What a package records about itself. It holds no judgement of the package."""

    snapshot_id: str
    requested_scope: tuple[str, ...]
    member_scope: tuple[str, ...]
    revision: str
    total: bool
    design_root: str
    run_bundles: tuple[str, ...] | None
    findings: tuple[Mapping[str, object], ...]
    requirements: tuple[RequirementEntry, ...]

    def as_document(self) -> Mapping[str, object]:
        """The summary as the machine-readable report of ``proof show``.

        ``runBundles`` is ``None`` for a package that records no digest list.
        """
        return {
            "snapshotId": self.snapshot_id,
            "requestedScope": list(self.requested_scope),
            "memberScope": list(self.member_scope),
            "revision": self.revision,
            "total": self.total,
            "designRoot": self.design_root,
            "runBundles": None if self.run_bundles is None else list(self.run_bundles),
            "findings": [dict(finding) for finding in self.findings],
            "requirements": [
                {
                    "id": entry.identifier,
                    "refinedBy": list(entry.refined_by),
                    "specifications": list(entry.specifications),
                    "implementations": list(entry.implementations),
                    "outcomes": [{"id": name, "result": result} for name, result in entry.outcomes],
                }
                for entry in self.requirements
            ],
        }


def summarize(stored: StoredPackage) -> Summary:
    """State what a package records, for each requirement of its scope and for the whole.

    :implements: SEG-SREQ-250
    :implements: SEG-SREQ-251

    Reads the four documents and nothing else: no run bundle, no current
    stream, no case. It states what is recorded and does not judge it, so a
    package with a wrong root or a blocked scope is summarized like any other.
    """
    manifest, design, record = stored.manifest, stored.design, stored.record
    edges = design["designEdges"]

    def sources(kind: str, target: str) -> tuple[str, ...]:
        return tuple(sorted(e["from"] for e in edges if e["kind"] == kind and e["to"] == target))

    entries = []
    for node in sorted(design["nodeManifest"], key=lambda item: item["id"]):
        if node["kind"] != "Requirement":
            continue
        identifier = node["id"]
        specifications = sources("Verifies", identifier)
        entries.append(
            RequirementEntry(
                identifier=identifier,
                refined_by=sources("Refines", identifier),
                specifications=specifications,
                implementations=sources("Implements", identifier),
                outcomes=tuple(
                    sorted(
                        (outcome["id"], outcome["result"])
                        for outcome in record["outcomes"]
                        if outcome["confirms"] in specifications
                    )
                ),
            )
        )
    bundles = manifest.get("runBundles")
    return Summary(
        snapshot_id=manifest["snapshotId"],
        requested_scope=tuple(manifest["requestedScope"]),
        member_scope=tuple(manifest["memberScope"]),
        revision=manifest["revision"],
        total=manifest["total"],
        design_root=design["root"],
        run_bundles=None if bundles is None else tuple(bundles),
        findings=tuple(stored.report["diagnostics"]),
        requirements=tuple(entries),
    )


__all__ = ["RequirementEntry", "StoredPackage", "Summary", "read_package", "summarize"]
