"""The composed producer: chaining, and building it from a configuration (SEG-SREQ-142).

The configuration tests write a file in ``tmp_path`` (the ``composed_config``
fixture) that points at the frozen toolbox evidence fixture by absolute path:
the repository is the fixture's ``sources`` tree and the requirement source
directory is a path beneath it. An anchor's path is computed from that
directory and the need's document name, so no requirement source file has to
exist.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from affirmatrix import config, graph
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord
from affirmatrix.sources import SourceError
from affirmatrix.sources.composed import ComposedProducer, evidence_bundles, from_config
from affirmatrix.sources.content import ExtractorError
from affirmatrix.sources.outcomes import TwisterOutcomeExtractor, bundle_digest
from affirmatrix.sources.store import StoreLoader

ConfigWriter = Callable[..., Path]

EVIDENCE_SOURCES = Path(__file__).resolve().parents[1] / "fixtures" / "toolbox_evidence" / "sources"

_DIGEST = bytes(32)
SUBSTREAM_REQUIREMENT = "doc/requirement-specification/detailed.rst"


def _node(local_id: str, kind: str = "Requirement") -> NodeRecord:
    anchor = ContentAnchor(digest=_DIGEST, repository="r", path="p", locator="l")
    return NodeRecord(local_id=local_id, kind=kind, content_anchors={"contentHash": anchor})


def _edge(from_id: str, to_id: str) -> EdgeRecord:
    return EdgeRecord(from_id=from_id, to_id=to_id, kind="Refines", state=LinkState.PENDING)


class _Source:
    def __init__(self, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> None:
        self._nodes, self._edges = nodes, edges

    def nodes(self) -> Iterator[NodeRecord]:
        yield from self._nodes

    def edges(self) -> Iterator[EdgeRecord]:
        yield from self._edges


def _anchors(source) -> list[ContentAnchor]:
    return [a for node in source.nodes() for a in node.content_anchors.values()]


def _load(path: Path) -> config.Config:
    return config.load(path)


# --- chaining ---------------------------------------------------------------


def test_composed_producer_yields_nodes_in_member_order() -> None:
    first = _Source([_node("A"), _node("B")], [])
    second = _Source([_node("C")], [])
    assert [n.local_id for n in ComposedProducer([first, second]).nodes()] == ["A", "B", "C"]


def test_composed_producer_yields_edges_in_member_order() -> None:
    first = _Source([], [_edge("A", "B")])
    second = _Source([], [_edge("C", "D")])
    edges = ComposedProducer([first, second]).edges()
    assert [(e.from_id, e.to_id) for e in edges] == [("A", "B"), ("C", "D")]


def test_composed_producer_can_be_walked_twice() -> None:
    producer = ComposedProducer([_Source([_node("A")], [_edge("A", "B")])])
    assert list(producer.nodes()) == list(producer.nodes())
    assert list(producer.edges()) == list(producer.edges())


def test_composed_producer_of_no_members_supplies_nothing() -> None:
    producer = ComposedProducer([])
    assert list(producer.nodes()) == []
    assert list(producer.edges()) == []


def test_composed_producer_leaves_a_duplicate_identifier_to_the_graph_builder() -> None:
    producer = ComposedProducer([_Source([_node("A")], []), _Source([_node("A")], [])])
    assert [n.local_id for n in producer.nodes()] == ["A", "A"]
    with pytest.raises(graph.GraphError):
        graph.build(producer)


def test_composed_producer_lets_a_member_failure_while_streaming_propagate() -> None:
    class Failing:
        def nodes(self) -> Iterator[NodeRecord]:
            yield _node("A")
            raise ExtractorError("the source file vanished")

        def edges(self) -> Iterator[EdgeRecord]:
            return iter(())

    stream = ComposedProducer([Failing()]).nodes()
    next(stream)
    with pytest.raises(SourceError, match="vanished") as caught:
        next(stream)
    assert isinstance(caught.value, ExtractorError)


# --- from_config -------------------------------------------------------------


def test_from_config_without_a_producer_block_or_root_is_refused() -> None:
    with pytest.raises(SourceError, match="no producer is available"):
        from_config(config.Config())


def test_from_config_with_only_producer_root_is_the_store_loader(
    would_be_store_copy: Path,
) -> None:
    source = from_config(config.Config(producer_root=would_be_store_copy))
    assert isinstance(source, StoreLoader)
    assert source.root == would_be_store_copy


def test_from_config_requirements_only_supplies_29_nodes_and_22_edges_anchored_at_the_repository(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config(content=False)))
    nodes = list(source.nodes())
    assert (len(nodes), len(list(source.edges()))) == (29, 22)
    anchors = {a.path for a in _anchors(source)}
    assert SUBSTREAM_REQUIREMENT in anchors
    assert all(path.startswith("doc/requirement-specification/") for path in anchors)
    assert {a.repository for a in _anchors(source)} == {"toolbox"}
    first = next(iter(nodes))
    assert first.content_anchors["contentHash"].locator == f"need:{first.local_id}"


def test_from_config_extractor_only_supplies_31_nodes_and_40_edges_anchored_at_the_repository(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config(requirements=False)))
    assert (len(list(source.nodes())), len(list(source.edges()))) == (31, 40)
    assert {a.path for a in _anchors(source)} == {
        "include/safe_data/safe_data.h",
        "src/safe_data.c",
        "tests/safe_data/src/main.c",
    }
    assert {a.repository for a in _anchors(source)} == {"toolbox"}


def test_from_config_with_all_three_blocks_chains_requirements_before_content(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config()))
    kinds = [n.kind for n in source.nodes()]
    assert len(kinds) == 60
    assert len(list(source.edges())) == 62
    assert kinds[:29] == ["Requirement"] * 29
    assert "Requirement" not in kinds[29:]


def test_from_config_reader_keys_win_over_producer_root(
    composed_config: ConfigWriter, would_be_store_copy: Path
) -> None:
    path = composed_config(producer={"root": str(would_be_store_copy)})
    loaded = _load(path)
    assert loaded.producer_root == would_be_store_copy
    assert isinstance(from_config(loaded), ComposedProducer)


def test_from_config_with_outcomes_only_is_refused_not_read_from_the_root(
    composed_config: ConfigWriter, would_be_store_copy: Path
) -> None:
    path = composed_config(
        requirements=False,
        content=False,
        outcomes=True,
        producer={"root": str(would_be_store_copy)},
    )
    with pytest.raises(SourceError, match=r"producer\.specifications"):
        from_config(_load(path))


def test_from_config_refuses_a_repository_name_missing_from_the_map(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(repositories={"other": "."})
    with pytest.raises(SourceError, match="'toolbox' is not a configured repository"):
        from_config(_load(path))


def test_from_config_refuses_a_reader_with_no_producer_repository(
    composed_config: ConfigWriter,
) -> None:
    loaded = _load(composed_config())
    unset = config.Config(
        producer=config.ProducerConfig(
            requirements=loaded.producer.requirements,  # type: ignore[union-attr]
        ),
        repositories=loaded.repositories,
    )
    with pytest.raises(SourceError, match="producer.repository is not set"):
        from_config(unset)


def test_from_config_refuses_a_source_directory_outside_the_repository(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    path = composed_config(repositories={"toolbox": str(tmp_path / "elsewhere")}, content=False)
    with pytest.raises(SourceError, match="does not lie under repository 'toolbox'"):
        from_config(_load(path))


def test_from_config_accepts_a_source_directory_equal_to_the_repository(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    fixture_doc = Path(_load(composed_config()).producer.requirements.source)  # type: ignore[union-attr]
    path = composed_config(repositories={"toolbox": str(fixture_doc)}, content=False)
    anchors = {a.path for a in _anchors(from_config(_load(path)))}
    assert "detailed.rst" in anchors


def test_from_config_relativizes_a_configuration_in_a_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    export = tmp_path / "needs.json"
    need = {
        "id": "REQ-1",
        "type": "requirement",
        "title": "t",
        "content": "c",
        "docname": "spec",
        "doctype": ".rst",
        "refines": [],
    }
    export.write_text(
        json.dumps({"versions": {"1": {"needs": {"REQ-1": need}}}}), encoding="utf-8"
    )
    file = tmp_path / "sub" / "affirmatrix.yaml"
    file.write_text(
        "repositories: {r: ..}\n"
        "producer:\n"
        "  repository: r\n"
        "  requirements:\n"
        f"    export: {export}\n"
        "    types: [requirement]\n"
        "    source: ../doc\n",
        encoding="utf-8",
    )
    source = from_config(config.load(file))
    assert [a.path for a in _anchors(source)] == ["doc/spec.rst"]


def test_from_config_refuses_a_missing_export_as_a_source_error(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    path = composed_config(content=False)
    document = path.read_text(encoding="utf-8").replace(
        "needs.json", "absent.json"
    )
    path.write_text(document, encoding="utf-8")
    with pytest.raises(SourceError, match="cannot be read"):
        from_config(_load(path))


def test_from_config_surfaces_a_missing_source_file_as_a_source_error_when_streamed(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    empty = tmp_path / "empty-repository"
    empty.mkdir()
    path = composed_config(repositories={"toolbox": str(empty)}, requirements=False)
    source = from_config(_load(path))  # the exports and Doxygen trees read; no source yet
    with pytest.raises(SourceError):
        list(source.nodes())


# --- outcomes -----------------------------------------------------------------

RUN_BUNDLES = Path(__file__).resolve().parents[1] / "fixtures" / "run_bundles"


def _run(bundle: Path = RUN_BUNDLES / "clean", **extra: str) -> dict[str, str]:
    """One configured run: the bundle and the digest it has."""
    return {"bundle": str(bundle), "digest": bundle_digest(bundle), **extra}


_MIRRORED = {
    "toolbox": str(EVIDENCE_SOURCES),
    "evidence": str(RUN_BUNDLES),
    "mirror": str(RUN_BUNDLES),
}


def _second_bundle(directory: Path, name: str) -> Path:
    """A copy of the clean bundle under ``directory``, with another run name."""
    target = directory / name
    shutil.copytree(RUN_BUNDLES / "clean", target)
    (target / "run.name").write_text(f"{name}\n", encoding="utf-8")
    return target


def _extractors(source) -> list[TwisterOutcomeExtractor]:
    return [m for m in source.sources if isinstance(m, TwisterOutcomeExtractor)]


def test_from_config_with_outcomes_supplies_136_nodes_and_214_edges(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config(outcomes=True)))
    assert (len(list(source.nodes())), len(list(source.edges()))) == (136, 214)


def test_from_config_chains_the_outcome_extractor_after_the_content_extractor(
    composed_config: ConfigWriter,
) -> None:
    kinds = [n.kind for n in from_config(_load(composed_config(outcomes=True))).nodes()]
    assert "TestOutcome" not in kinds[:60]
    assert kinds[60:] == ["TestOutcome"] * 76


def test_from_config_anchors_an_outcome_at_its_repository_name_and_the_bundles_artifact_path(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config(outcomes=True)))
    outcomes = [n for n in source.nodes() if n.kind == "TestOutcome"]
    anchors = [a for n in outcomes for a in n.content_anchors.values()]
    assert {(a.repository, a.path) for a in anchors} == {("evidence", "clean/twister.json")}
    assert all(a.locator.startswith("nodeid:") for a in anchors)


def test_from_config_takes_the_producers_repository_for_a_run_with_no_repository_key(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(
        requirements=False,
        repositories={"toolbox": str(RUN_BUNDLES)},
        producer={"outcomes": [_run()]},
    )
    (extractor,) = _extractors(from_config(_load(path)))
    assert extractor.repository == "toolbox"
    anchors = {a.repository for n in extractor.nodes() for a in n.content_anchors.values()}
    assert anchors == {"toolbox"}


def test_from_config_reads_the_runs_of_one_repository_with_one_extractor_in_file_order(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    bundles = tmp_path / "bundles"
    first, second = _second_bundle(bundles, "run-one"), _second_bundle(bundles, "run-two")
    runs = [_run(first, repository="evidence"), _run(second, repository="evidence")]
    path = composed_config(
        outcomes=True,
        repositories={"toolbox": str(EVIDENCE_SOURCES), "evidence": str(bundles)},
        producer={"outcomes": runs},
    )
    (extractor,) = _extractors(from_config(_load(path)))
    assert [run.bundle.name for run in extractor.runs] == ["run-one", "run-two"]


def test_from_config_builds_one_extractor_for_each_repository_the_runs_name(
    composed_config: ConfigWriter, tmp_path: Path
) -> None:
    path = composed_config(
        outcomes=True,
        repositories=_MIRRORED,
        producer={"outcomes": [_run(repository="evidence"), _run(repository="mirror")]},
    )
    extractors = _extractors(from_config(_load(path)))
    assert [(e.repository, e.root, len(e.runs)) for e in extractors] == [
        ("evidence", RUN_BUNDLES, 1),
        ("mirror", RUN_BUNDLES, 1),
    ]


def test_from_config_refuses_a_run_naming_a_repository_that_is_not_configured(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(producer={"outcomes": [_run(repository="nowhere")]})
    with pytest.raises(SourceError, match=r"clean names repository 'nowhere'"):
        from_config(_load(path))


def test_from_config_refuses_outcomes_without_specifications(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(content=False, outcomes=True)
    with pytest.raises(SourceError, match=r"producer\.specifications"):
        from_config(_load(path))


def test_from_config_without_implementations_supplies_no_witnesses_edge(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(requirements=False, outcomes=True, producer={"implementations": None})
    (extractor,) = _extractors(from_config(_load(path)))
    assert [e.kind for e in extractor.edges()] == ["Confirms"] * 76


def test_from_config_leaves_a_duplicate_identity_across_repositories_to_the_graph_builder(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(
        outcomes=True,
        repositories=_MIRRORED,
        producer={"outcomes": [_run(repository="evidence"), _run(repository="mirror")]},
    )
    source = from_config(_load(path))
    with pytest.raises(graph.GraphError):
        graph.build(source)


def test_from_config_without_evidence_reads_no_bundle(composed_config: ConfigWriter) -> None:
    """SEG-SREQ-230: a bundle that does not exist refuses nothing until a verb needs it."""
    path = composed_config(outcomes=True, producer={"outcomes": [_run()]})
    document = path.read_text(encoding="utf-8").replace("clean", "absent")
    path.write_text(document, encoding="utf-8")
    source = from_config(_load(path), evidence=False)
    assert _extractors(source) == []
    with pytest.raises(SourceError, match="absent"):
        from_config(_load(path))


def test_from_config_without_evidence_still_checks_the_runs_repository_names(
    composed_config: ConfigWriter,
) -> None:
    path = composed_config(producer={"outcomes": [_run(repository="nowhere")]})
    with pytest.raises(SourceError, match="nowhere"):
        from_config(_load(path), evidence=False)


def test_a_composed_producer_gives_the_bundle_digest_of_each_outcome(
    composed_config: ConfigWriter,
) -> None:
    source = from_config(_load(composed_config(outcomes=True)))
    digests = evidence_bundles(source)
    assert len(digests) == 76
    assert set(digests.values()) == {bundle_digest(RUN_BUNDLES / "clean")}


def test_a_source_that_is_not_composed_gives_no_bundle_digest(would_be_store_copy: Path) -> None:
    assert evidence_bundles(StoreLoader(root=would_be_store_copy)) == {}
