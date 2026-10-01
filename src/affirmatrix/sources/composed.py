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
  ``root`` or ``repository`` — is the would-be store over ``producer.root``, or
  a refusal when that is not set either. A configured reader always wins over
  ``producer.root``; ``root`` is the store loader's own key and is used only
  when no reader is configured.
* Otherwise the requirements reader (when ``producer.requirements`` is set),
  then the content extractor (when ``producer.implementations`` or
  ``producer.specifications`` is set), chained in that order. Both anchor every
  record to the repository ``producer.repository`` names, which must be a key
  of ``repositories``.
* The configuration loader takes every relative path from the directory of the
  file, but the requirements reader wants its source directory relative to the
  repository, because an anchor's path is repository-relative. The source
  directory is therefore re-derived as its path relative to the repository's
  path (a lexical computation: nothing is opened, and the directory need not
  exist), and a source directory that does not lie under the repository is
  refused. The extractor's root is the repository's path itself, since Doxygen
  names files relative to it.
* The run bundles the caller names (``bundles``) are the evidence view. They
  go to one outcome extractor, chained last, which reads and checks every one
  of them (SEG-SREQ-229). With none named, no extractor is built, no bundle is
  read and the stream holds no test evidence. The extractor needs
  ``producer.specifications``, because a result cannot map to a test
  specification without the test-case export; without it, and for a store at
  ``producer.root``, the composition is refused (SEG-SREQ-235).
  ``producer.implementations`` is optional: without it no Witnesses edge is
  supplied.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from affirmatrix.config import Config
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


def from_config(config: Config, *, bundles: Sequence[Path] = ()) -> RecordSource:
    """The producer the configuration describes, or a refusal.

    ``bundles`` are the run bundles the caller names. With none, no outcome
    extractor is built, so no run bundle is read and the stream holds no test
    evidence. With some, one outcome extractor over all of them is chained
    after the readers (SEG-SREQ-229); that needs ``producer.specifications``,
    and it is refused when the producer is the would-be store or when there is
    none.

    :implements: SEG-SREQ-229
    :implements: SEG-SREQ-235

    Raises :class:`~affirmatrix.sources.SourceError` when no producer is
    configured, when ``producer.repository`` is missing or not a configured
    repository, when the requirements source directory does not lie under
    that repository, when bundles are named without ``producer.specifications``,
    and (from the readers and the outcome extractor) when an input cannot be
    read.
    """
    producer = config.producer
    if bundles and (producer is None or producer.specifications is None):
        raise SourceError(
            "run bundles are named, but the configuration gives no test-case export "
            "(producer.specifications); a result maps to a test specification through it"
        )
    content_configured = producer is not None and (
        producer.implementations is not None or producer.specifications is not None
    )
    if producer is None or (
        producer.requirements is None and not content_configured
    ):
        if config.producer_root is None:
            raise SourceError(
                "no producer is available: give --current or configure producer.root"
            )
        return StoreLoader(root=config.producer_root)

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
    if bundles and producer.specifications is not None:
        members.append(
            TwisterOutcomeExtractor(
                bundles,
                checkout=config.implementation,
                specifications=producer.specifications,
                implementations=producer.implementations,
            )
        )
    return ComposedProducer(members)


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
