"""The composed producer — the configured readers presented as one current stream.

:class:`ComposedProducer` chains record sources: its nodes are every member's
nodes in member order, then its edges every member's edges in member order.
It checks nothing across members. A local identifier two members both supply
is the graph builder's to refuse, and an edge to an identifier no member
supplies is the builder's to report as broken; neither is this class's
business. It wraps nothing either: an error a member raises while its records
are being taken is already a :class:`~affirmatrix.sources.SourceError`.

:func:`from_config` builds the producer a configuration describes:

* No reader configured — a ``producer`` block absent, or naming only
  ``root`` or ``repository``, or an empty ``outcomes`` — is the would-be store over
  ``producer.root``, or a refusal when that is not set either. A configured
  reader always wins over ``producer.root``; ``root`` is the store loader's own
  key and is used only when no reader is configured.
* Otherwise the requirements reader (when ``producer.requirements`` is set),
  then the content extractor (when ``producer.implementations`` or
  ``producer.specifications`` is set), then one outcome extractor for each
  repository that the runs of ``producer.outcomes`` name, chained in that
  order. The outcome extractors are the evidence view. They are built only
  when the caller asks for evidence, and building one reads and checks every
  run bundle it is given, so a verb that needs no evidence leaves it out and
  reads no bundle (SEG-SREQ-229, SEG-SREQ-230). The first two anchor every record to the repository
  ``producer.repository`` names, which must be a key of ``repositories``.
* The configuration loader takes every relative path from the directory of the
  file, but the requirements reader wants its source directory relative to the
  repository, because an anchor's path is repository-relative. The source
  directory is therefore re-derived as its path relative to the repository's
  path (a lexical computation: nothing is opened, and the directory need not
  exist), and a source directory that does not lie under the repository is
  refused. The extractor's root is the repository's path itself, since Doxygen
  names files relative to it.
* Each run of ``producer.outcomes`` has a bundle that lies under the repository its
  ``repository`` key names. The producer's repository is the default. The runs
  of one repository go to one outcome extractor, rooted at the path of that
  repository, with the runs in configuration order. The anchors of its
  outcomes name that repository. The outcomes need ``producer.specifications``.
  Without it the composition is refused, because a result cannot map to a test
  specification without the test-case export. ``producer.implementations`` is
  optional: without it no Witnesses edge is supplied.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from affirmatrix.config import Config, ProducerConfig, RunInputs, SpecificationInputs
from affirmatrix.records import EdgeRecord, NodeRecord, RecordSource
from affirmatrix.sources import SourceError
from affirmatrix.sources.content import CSourceExtractor
from affirmatrix.sources.outcomes import TwisterOutcomeExtractor
from affirmatrix.sources.reqs import RequirementsReader
from affirmatrix.sources.store import StoreLoader


@dataclass(frozen=True, slots=True)
class ComposedProducer:
    """Several record sources chained into one, in the order they are given."""

    sources: Sequence[RecordSource]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))

    def nodes(self) -> Iterator[NodeRecord]:
        """Every member's nodes, member by member."""
        for source in self.sources:
            yield from source.nodes()

    def edges(self) -> Iterator[EdgeRecord]:
        """Every member's edges, member by member."""
        for source in self.sources:
            yield from source.edges()

    def evidence_bundles(self) -> Mapping[str, str]:
        """For each outcome a member supplies, the digest of the run bundle it came from.

        Members that supply no outcomes from bundles add nothing.
        """
        provenance: dict[str, str] = {}
        for source in self.sources:
            if isinstance(source, TwisterOutcomeExtractor):
                provenance.update(source.evidence_bundles())
        return provenance


def evidence_bundles(source: RecordSource) -> Mapping[str, str]:
    """The run bundle digest of each outcome a record source supplies from a bundle.

    Empty for a source that is not a composed producer, such as a would-be
    store, whose outcomes come from no bundle.

    :implements: SEG-SREQ-226
    """
    return source.evidence_bundles() if isinstance(source, ComposedProducer) else {}


def from_config(config: Config, *, evidence: bool = True) -> RecordSource:
    """The producer the configuration describes, or a refusal.

    With ``evidence`` false no outcome extractor is built, so no run bundle is
    read and a bundle that cannot be read refuses nothing. The shape of the
    configuration is checked either way.

    Raises :class:`~affirmatrix.sources.SourceError` when no producer is
    configured, when ``producer.repository`` is missing or not a configured
    repository, when the requirements source directory does not lie under
    that repository, when runs are configured without
    ``producer.specifications``, when a run names a repository that is not
    configured, and (from the readers, and from the outcome extractors when
    ``evidence`` is true) when a configured input cannot be read.
    """
    producer = config.producer
    content_configured = producer is not None and (
        producer.implementations is not None or producer.specifications is not None
    )
    if producer is None or (
        producer.requirements is None and not content_configured and not producer.outcomes
    ):
        if config.producer_root is None:
            raise SourceError(
                "no producer is available: give --current or configure producer.root"
            )
        return StoreLoader(root=config.producer_root)

    if producer.outcomes and producer.specifications is None:
        raise SourceError(
            "producer.outcomes is set but producer.specifications is not; a result "
            "maps to a test specification through the test-case export"
        )
    name = producer.repository
    if name is None:
        raise SourceError(
            "producer.repository is not set; the configured readers anchor their "
            "records to a named repository"
        )
    repository_path = config.repository(name)
    if repository_path is None:
        known = ", ".join(sorted(config.repositories)) or "none"
        raise SourceError(
            f"producer.repository {name!r} is not a configured repository (configured: {known})"
        )

    members: list[RecordSource] = []
    if producer.requirements is not None:
        requirements = producer.requirements
        members.append(
            RequirementsReader(
                export=requirements.export,
                types=requirements.types,
                repository=name,
                source_directory=_under(requirements.source, repository_path, name),
            )
        )
    if content_configured:
        members.append(
            CSourceExtractor(
                repository_path,
                repository=name,
                implementations=producer.implementations,
                specifications=producer.specifications,
            )
        )
    if producer.outcomes and producer.specifications is not None:
        members.extend(
            _outcome_extractors(
                producer,
                producer.specifications,
                name,
                config.repositories,
                checkout=config.implementation,
                evidence=evidence,
            )
        )
    return ComposedProducer(members)


def _outcome_extractors(
    producer: ProducerConfig,
    specifications: SpecificationInputs,
    default: str,
    repositories: Mapping[str, Path],
    *,
    checkout: str | None,
    evidence: bool,
) -> list[RecordSource]:
    """One outcome extractor for each repository the runs name, in order of first appearance.

    The names are checked in every case, since that reads nothing. Without
    ``evidence`` no extractor is built, and so no bundle is read.
    """
    groups: dict[str, list[RunInputs]] = {}
    for run in producer.outcomes:
        groups.setdefault(run.repository or default, []).append(run)
    extractors: list[RecordSource] = []
    for name, runs in groups.items():
        path = repositories.get(name)
        if path is None:
            known = ", ".join(sorted(repositories)) or "none"
            raise SourceError(
                f"producer.outcomes: the run bundle {runs[0].bundle} names repository "
                f"{name!r}, which is not a configured repository (configured: {known})"
            )
        if not evidence:
            continue
        extractors.append(
            TwisterOutcomeExtractor(
                path,
                runs,
                repository=name,
                checkout=checkout,
                specifications=specifications,
                implementations=producer.implementations,
            )
        )
    return extractors


def _under(source: Path, repository_path: Path, name: str) -> Path:
    """``source`` relative to the repository's path; refused when it lies outside."""
    try:
        relative = Path(os.path.relpath(source, repository_path))
    except ValueError as error:
        raise SourceError(
            f"producer.requirements.source {source} cannot be made relative to "
            f"repository {name!r} at {repository_path}: {error}"
        ) from error
    if relative.parts[:1] == ("..",):
        raise SourceError(
            f"producer.requirements.source {source} does not lie under repository "
            f"{name!r} at {repository_path}"
        )
    return relative


__all__ = ["ComposedProducer", "evidence_bundles", "from_config"]
