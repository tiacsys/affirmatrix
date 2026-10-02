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
  ``producer.specifications`` is set), chained in that order. Each reader has
  one repository: the one its own block names, else the one
  ``producer.repository`` names. It must be a key of ``repositories``, and it is
  the repository the reader anchors every record to and reads its paths in. A
  reader with none, or with one that is not a key, is refused, and the message
  names the reader by the name of its block.
* The configuration loader takes every relative path from the directory of the
  file, but the requirements reader wants its source directory, and each file
  of its source map, relative to the reader's repository, because an anchor's
  path is repository-relative. Each is therefore re-derived as its path
  relative to the repository's path (a lexical computation: nothing is opened,
  and the path need not exist), and one that does not lie under the repository
  is refused. The extractor reads each of its streams in that stream's
  repository path, since Doxygen names files relative to it, after the
  stream's prefix is removed.
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

from affirmatrix.config import Config, ProducerConfig
from affirmatrix.records import EdgeRecord, NodeRecord, RecordSource
from affirmatrix.sources import SourceError
from affirmatrix.sources.content import CSourceExtractor, Placement
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
    configured, when a reader has no repository or one that is not a configured
    repository, when the requirements source directory or a file of its source
    map does not lie under the reader's repository, when bundles are named
    without ``producer.specifications``, and (from the readers and the outcome
    extractor) when an input cannot be read.
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

    members: list[RecordSource] = []
    if producer.requirements is not None:
        requirements = producer.requirements
        placement = _placement(config, producer, "requirements", requirements.repository)
        source_directory = None
        source_map = None
        if requirements.source is not None:
            source_directory = _under(
                requirements.source, placement, "producer.requirements.source"
            )
        if requirements.source_map is not None:
            source_map = {
                docname: _under(
                    path, placement, f"producer.requirements.source-map entry {docname!r}"
                )
                for docname, path in requirements.source_map.items()
            }
        members.append(
            RequirementsReader(
                export=requirements.export,
                types=requirements.types,
                repository=placement.repository,
                source_directory=source_directory,
                source_map=source_map,
                parent_field=requirements.parent_field,
            )
        )
    if content_configured:
        members.append(
            CSourceExtractor(
                implementations=producer.implementations,
                specifications=producer.specifications,
                implementation_placement=(
                    None
                    if producer.implementations is None
                    else _placement(
                        config, producer, "implementations", producer.implementations.repository
                    )
                ),
                specification_placement=(
                    None
                    if producer.specifications is None
                    else _placement(
                        config, producer, "specifications", producer.specifications.repository
                    )
                ),
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


def _placement(config: Config, producer: ProducerConfig, block: str, own: str | None) -> Placement:
    """The repository of the reader ``block``: its own, else the default; or a refusal.

    The refusal names the reader by the name of its block in the configuration.

    :implements: SEG-SREQ-286
    :implements: SEG-SREQ-292
    """
    if own is not None:
        name, origin = own, f"producer.{block}.repository"
    elif producer.repository is not None:
        name, origin = producer.repository, "producer.repository"
    else:
        raise SourceError(
            f"producer.repository is not set and the {block} reader names no repository of its "
            f"own (producer.{block}.repository); a configured reader anchors its records to "
            "a named repository"
        )
    path = config.repository(name)
    if path is None:
        known = ", ".join(sorted(config.repositories)) or "none"
        raise SourceError(
            f"{origin} {name!r} is not a configured repository "
            f"(reader: {block}; configured: {known})"
        )
    return Placement(name, path)


def _under(source: Path, placement: Placement, what: str) -> Path:
    """``source`` relative to the repository's path; refused when it lies outside."""
    try:
        relative = Path(os.path.relpath(source, placement.root))
    except ValueError as error:
        raise SourceError(
            f"{what} {source} cannot be made relative to "
            f"repository {placement.repository!r} at {placement.root}: {error}"
        ) from error
    if relative.parts[:1] == ("..",):
        raise SourceError(
            f"{what} {source} does not lie under repository "
            f"{placement.repository!r} at {placement.root}"
        )
    return relative


__all__ = ["ComposedProducer", "evidence_bundles", "from_config"]
