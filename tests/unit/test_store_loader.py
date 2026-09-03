"""The store loader, and the would-be store it reads.

Two things are under test here, and they fail differently. The loader is code:
it must hash content verbatim, keep its reads inside the store, and refuse a
malformed or misplaced store loudly rather than yielding a short record stream
nobody notices. The would-be store is data: it must build, and it must still
contain the uneven coverage the later workflows are exercised against — a
subtree that comes out satisfied, one that cannot, and a specification nothing
executed.

Neither is a requirement subject. The loader is scaffolding that record
production retires, so these are developer tests over a fixture, with no
``:verifies:`` context to point at.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

import pytest

from affirmatrix import graph, records, taxonomy
from affirmatrix.sources import store

WOULD_BE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "would_be_store"


def make_store(root: Path, *, nodes: str = "", edges: str = "", content: dict[str, str]) -> Path:
    """Write a minimal store and return its root.

    Built from literals rather than by copying the fixture: a test that needs a
    malformed manifest should say what is malformed about it in the test.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "nodes").mkdir()
    (root / "edges").mkdir()
    (root / "content").mkdir()
    if nodes:
        (root / "nodes" / "nodes.toml").write_text(nodes, encoding="utf-8")
    if edges:
        (root / "edges" / "edges.toml").write_text(edges, encoding="utf-8")
    for relative, text in content.items():
        path = root / "content" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


ONE_REQUIREMENT = """
kind = "Requirement"

[nodes]
"SEG-SYS-001" = { contentHash = "r.txt" }
"""


# ── Nodes ───────────────────────────────────────────────────────────────────


def test_a_node_manifest_yields_a_record_of_the_declared_kind(tmp_path: Path) -> None:
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={"r.txt": "a statement\n"})
    (node,) = store.StoreLoader(root).nodes()
    assert node.local_id == "SEG-SYS-001"
    assert node.kind == "Requirement"


def test_a_content_hash_is_the_digest_of_the_stored_bytes(tmp_path: Path) -> None:
    """Reproduced here with ``hashlib`` alone, as an auditor would."""
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={"r.txt": "a statement\n"})
    (node,) = store.StoreLoader(root).nodes()
    assert node.content_hashes == {"contentHash": hashlib.sha256(b"a statement\n").digest()}


def test_content_is_hashed_verbatim(tmp_path: Path) -> None:
    """No stripping and no normalization: the bytes on disk are the content.

    A loader that trimmed whitespace would be canonicalizing content on the way
    in, which would make the hash a function of the loader rather than of what
    the store holds.
    """
    first = make_store(tmp_path / "a", nodes=ONE_REQUIREMENT, content={"r.txt": "a statement\n"})
    second = make_store(
        tmp_path / "b", nodes=ONE_REQUIREMENT, content={"r.txt": "a statement  \n\n"}
    )
    (left,) = store.StoreLoader(first).nodes()
    (right,) = store.StoreLoader(second).nodes()
    assert left.content_hashes != right.content_hashes


def test_a_loaded_node_locates_each_hash_in_the_store(tmp_path: Path) -> None:
    """The location is honest scaffolding: an unversioned content directory
    plays the repository, the manifest's path is the path, and the whole file
    is the span — which is literally what was hashed."""
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={"r.txt": "a statement\n"})
    (node,) = store.StoreLoader(root).nodes()
    location = node.content_anchors["contentHash"]
    assert location.repository == str(root / "content")
    assert location.path == "r.txt"
    assert location.locator == "file"


def test_a_node_carries_every_content_hash_its_entry_declares(tmp_path: Path) -> None:
    manifest = """
    kind = "Implementation"

    [nodes]
    "pkg.function" = { apiHash = "api.txt", bodyHash = "body.txt" }
    """
    root = make_store(
        tmp_path,
        nodes=manifest,
        content={"api.txt": "def function() -> None:\n", "body.txt": "    return None\n"},
    )
    (node,) = store.StoreLoader(root).nodes()
    assert set(node.content_hashes) == {"apiHash", "bodyHash"}
    assert node.content_hashes["apiHash"] != node.content_hashes["bodyHash"]


def test_manifests_are_read_in_filename_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record stream is reproducible, so a design root over it is too.

    A filesystem is free to hand back directory entries in any order, and one
    that happens to hand them back sorted would let an unsorted loader pass this
    on one machine and fail on another. So the adverse order is imposed rather
    than hoped for.
    """
    root = make_store(tmp_path, content={"r.txt": "x\n"})
    for name in ("first", "second"):
        (root / "nodes" / f"{name}.toml").write_text(
            f'kind = "Requirement"\n[nodes]\n"{name}" = {{ contentHash = "r.txt" }}\n',
            encoding="utf-8",
        )
    listing = Path.glob
    monkeypatch.setattr(
        Path, "glob", lambda self, pattern: iter(sorted(listing(self, pattern), reverse=True))
    )
    assert [node.local_id for node in store.StoreLoader(root).nodes()] == ["first", "second"]


def test_entries_keep_the_order_they_are_written_in(tmp_path: Path) -> None:
    manifest = """
    kind = "Requirement"

    [nodes]
    "third" = { contentHash = "r.txt" }
    "first" = { contentHash = "r.txt" }
    "second" = { contentHash = "r.txt" }
    """
    root = make_store(tmp_path, nodes=manifest, content={"r.txt": "x\n"})
    assert [node.local_id for node in store.StoreLoader(root).nodes()] == [
        "third",
        "first",
        "second",
    ]


def test_a_duplicate_identifier_is_left_for_the_builder_to_refuse(tmp_path: Path) -> None:
    """Duplicate identity is a graph-level error, and the graph reports it.

    The loader is a producer: it says what the store holds. Refusing here as
    well would put the same rule in two places and let them disagree.
    """
    root = make_store(tmp_path, content={"r.txt": "x\n"})
    for name in ("a", "b"):
        (root / "nodes" / f"{name}.toml").write_text(
            'kind = "Requirement"\n[nodes]\n"same" = { contentHash = "r.txt" }\n',
            encoding="utf-8",
        )
    loader = store.StoreLoader(root)
    assert len(list(loader.nodes())) == 2
    with pytest.raises(graph.GraphError, match="same"):
        graph.build(loader)


# ── Edges ───────────────────────────────────────────────────────────────────


def test_an_edge_manifest_yields_an_edge_per_pair(tmp_path: Path) -> None:
    manifest = """
    [edges]
    Refines = [["SEG-SREQ-001", "SEG-SYS-001"], ["SEG-SREQ-002", "SEG-SYS-001"]]
    Verifies = [["SEG-TS-001", "SEG-SREQ-001"]]
    """
    root = make_store(tmp_path, edges=manifest, content={})
    edges = list(store.StoreLoader(root).edges())
    assert [(edge.from_id, edge.to_id, edge.kind) for edge in edges] == [
        ("SEG-SREQ-001", "SEG-SYS-001", "Refines"),
        ("SEG-SREQ-002", "SEG-SYS-001", "Refines"),
        ("SEG-TS-001", "SEG-SREQ-001", "Verifies"),
    ]


def test_every_edge_from_the_store_is_pending(tmp_path: Path) -> None:
    """The store holds content, not affirmations; nothing in it was affirmed."""
    manifest = '[edges]\nRefines = [["a", "b"]]\n'
    root = make_store(tmp_path, edges=manifest, content={})
    (edge,) = store.StoreLoader(root).edges()
    assert edge.state is records.LinkState.PENDING
    assert edge.edge_hash is None


def test_a_pair_that_is_not_two_endpoints_is_refused(tmp_path: Path) -> None:
    manifest = '[edges]\nRefines = [["a", "b", "c"]]\n'
    root = make_store(tmp_path, edges=manifest, content={})
    with pytest.raises(store.StoreError, match="Refines"):
        list(store.StoreLoader(root).edges())


# ── Refusals ────────────────────────────────────────────────────────────────


def test_a_root_that_is_not_a_store_is_refused_at_construction(tmp_path: Path) -> None:
    """A mistyped root must not read as a store that happens to be empty.

    An empty record stream builds an empty graph, which seals to a perfectly
    valid root over nothing at all.
    """
    with pytest.raises(store.StoreError):
        store.StoreLoader(tmp_path / "nowhere")


def test_a_store_missing_its_manifest_directories_is_refused(tmp_path: Path) -> None:
    (tmp_path / "nodes").mkdir()
    with pytest.raises(store.StoreError, match="edges"):
        store.StoreLoader(tmp_path)


def test_a_missing_content_file_names_the_node_and_the_path(tmp_path: Path) -> None:
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={})
    with pytest.raises(store.StoreError, match="SEG-SYS-001") as caught:
        list(store.StoreLoader(root).nodes())
    assert "r.txt" in str(caught.value)


def test_a_content_path_leaving_the_store_is_refused(tmp_path: Path) -> None:
    """The store is a fixture, and a fixture must not become a file reader."""
    (tmp_path / "secret.txt").write_text("not content\n", encoding="utf-8")
    manifest = """
    kind = "Requirement"

    [nodes]
    "SEG-SYS-001" = { contentHash = "../../secret.txt" }
    """
    root = make_store(tmp_path / "store", nodes=manifest, content={})
    with pytest.raises(store.StoreError, match="outside"):
        list(store.StoreLoader(root).nodes())


def test_an_absolute_content_path_is_refused(tmp_path: Path) -> None:
    manifest = f'''
    kind = "Requirement"

    [nodes]
    "SEG-SYS-001" = {{ contentHash = "{tmp_path / "elsewhere.txt"}" }}
    '''
    (tmp_path / "elsewhere.txt").write_text("not content\n", encoding="utf-8")
    root = make_store(tmp_path / "store", nodes=manifest, content={})
    with pytest.raises(store.StoreError, match="outside"):
        list(store.StoreLoader(root).nodes())


def test_a_malformed_manifest_names_the_file(tmp_path: Path) -> None:
    root = make_store(tmp_path, nodes="kind = = \n", content={})
    with pytest.raises(store.StoreError, match="nodes.toml"):
        list(store.StoreLoader(root).nodes())


def test_a_node_manifest_without_a_kind_is_refused(tmp_path: Path) -> None:
    root = make_store(tmp_path, nodes='[nodes]\n"a" = { contentHash = "r.txt" }\n', content={})
    with pytest.raises(store.StoreError, match="kind"):
        list(store.StoreLoader(root).nodes())


def test_a_content_declaration_that_is_not_a_path_is_refused(tmp_path: Path) -> None:
    """Named where the mistake is, rather than as a file that cannot be read."""
    root = make_store(
        tmp_path, nodes='kind = "Requirement"\n[nodes]\n"a" = { contentHash = 7 }\n', content={}
    )
    with pytest.raises(store.StoreError, match="contentHash"):
        list(store.StoreLoader(root).nodes())


def test_an_entry_declaring_no_content_is_refused(tmp_path: Path) -> None:
    """A node with no content hash has nothing for the graph to anchor to."""
    root = make_store(tmp_path, nodes='kind = "Requirement"\n[nodes]\n"a" = {}\n', content={})
    with pytest.raises(store.StoreError, match="content"):
        list(store.StoreLoader(root).nodes())


# ── Test results (SEG-SREQ-055) ─────────────────────────────────────────────


ONE_OUTCOME = """
kind = "TestOutcome"

[nodes]
"run-1/TS-1" = { contentHash = "o.txt", result = "failed", revision = "r1" }
"""


def test_a_declared_result_reaches_the_record(tmp_path: Path) -> None:
    """The manifest's one non-content key, passed through the closed vocabulary."""
    root = make_store(tmp_path, nodes=ONE_OUTCOME, content={"o.txt": "result: failed\n"})
    (node,) = store.StoreLoader(root).nodes()
    assert node.result is records.TestResult.FAILED


def test_a_result_the_vocabulary_does_not_contain_is_refused(tmp_path: Path) -> None:
    root = make_store(
        tmp_path,
        nodes='kind = "TestOutcome"\n[nodes]\n"run-1/TS-1" = '
        '{ contentHash = "o.txt", result = "green" }\n',
        content={"o.txt": "result: green\n"},
    )
    with pytest.raises(store.StoreError, match="green"):
        list(store.StoreLoader(root).nodes())


def test_a_test_outcome_without_a_result_is_refused(tmp_path: Path) -> None:
    """The refusal names the manifest and the entry, where the fix is."""
    root = make_store(
        tmp_path,
        nodes='kind = "TestOutcome"\n[nodes]\n"run-1/TS-1" = { contentHash = "o.txt" }\n',
        content={"o.txt": "result: passed\n"},
    )
    with pytest.raises(store.StoreError, match="run-1/TS-1"):
        list(store.StoreLoader(root).nodes())


def test_a_result_on_a_kind_that_records_no_execution_is_refused(tmp_path: Path) -> None:
    root = make_store(
        tmp_path,
        nodes='kind = "Requirement"\n[nodes]\n"a" = { contentHash = "r.txt", result = "passed" }\n',
        content={"r.txt": "a statement\n"},
    )
    with pytest.raises(store.StoreError, match="result"):
        list(store.StoreLoader(root).nodes())


# ── The loader is a record source ───────────────────────────────────────────


def test_the_loader_satisfies_the_record_source_protocol(tmp_path: Path) -> None:
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={"r.txt": "x\n"})
    assert isinstance(store.StoreLoader(root), records.RecordSource)


def test_the_streams_can_be_walked_again_from_a_fresh_call(tmp_path: Path) -> None:
    """Nothing may assume a second pass, but a second *call* must work.

    The three workflows each build the graph, and a loader that emptied itself
    after one build would make every workflow after the first read a graph with
    no nodes in it.
    """
    root = make_store(tmp_path, nodes=ONE_REQUIREMENT, content={"r.txt": "x\n"})
    loader = store.StoreLoader(root)
    assert [node.local_id for node in loader.nodes()] == ["SEG-SYS-001"]
    assert [node.local_id for node in loader.nodes()] == ["SEG-SYS-001"]


# ── The would-be store itself ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def would_be_store() -> store.StoreLoader:
    return store.StoreLoader(WOULD_BE_STORE)


def test_the_would_be_store_builds(would_be_store: store.StoreLoader) -> None:
    built = graph.build(would_be_store)
    assert len(built.node_ids()) == 59 + 8 + 9 + 8
    assert len(built.edges) == 48 + 10 + 9 + 8 + 9


def test_every_kind_in_the_store_is_one_the_vocabulary_declares(
    would_be_store: store.StoreLoader,
) -> None:
    """Otherwise the graph builder refuses the store, which is a worse test."""
    assert {node.kind for node in would_be_store.nodes()} == taxonomy.node_kinds() - {"Waiver"}
    assert {edge.kind for edge in would_be_store.edges()} <= taxonomy.edge_kinds()


def test_the_store_contains_no_dangling_endpoint(would_be_store: store.StoreLoader) -> None:
    """A dangling endpoint is a broken edge, and this store has none by design.

    The suspect detector is exercised on broken edges by deleting a node, so the
    starting point has to be a store where nothing is broken yet.
    """
    declared = {node.local_id for node in would_be_store.nodes()}
    endpoints = {
        endpoint for edge in would_be_store.edges() for endpoint in (edge.from_id, edge.to_id)
    }
    assert endpoints <= declared


def test_every_declared_content_file_exists(would_be_store: store.StoreLoader) -> None:
    """Reading the whole store is the check: a missing file raises."""
    assert all(node.content_hashes for node in would_be_store.nodes())


def test_the_store_carries_the_uneven_coverage_the_workflows_need(
    would_be_store: store.StoreLoader,
) -> None:
    """The gaps are data under test, not accidents of authoring.

    Each of these is load bearing for a later item: a subtree that comes out
    satisfied, one that cannot because its children have no implementation at
    all, and a specification nothing executed.
    """
    built = graph.build(would_be_store)
    covered = {edge.to_id for edge in built.edges if edge.kind in {"Implements", "Verifies"}}
    taxonomy_children = {"SEG-SREQ-029", "SEG-SREQ-030", "SEG-SREQ-031", "SEG-SREQ-032"}
    assert taxonomy_children <= covered
    assert {"SEG-SREQ-001", "SEG-SREQ-017"}.isdisjoint(covered)
    confirmed = {edge.to_id for edge in built.edges if edge.kind == "Confirms"}
    assert "SEG-TS-003" not in confirmed


def test_every_requirement_in_the_store_is_a_requirement_of_this_repository(
    would_be_store: store.StoreLoader,
) -> None:
    """The translation is only meaningful if the identifiers are the real ones.

    Checked against the manifest rather than against the needs export: the
    export is a build artifact and a test may not depend on one having been
    produced. What this catches is a typo, which is the realistic mistake in a
    hand translation.
    """
    manifest = tomllib.loads(
        (WOULD_BE_STORE / "nodes" / "requirements.toml").read_text(encoding="utf-8")
    )
    identifiers = set(manifest["nodes"])
    assert len(identifiers) == 59
    assert all(
        identifier.startswith(("SEG-SYS-", "SEG-SREQ-")) and identifier[-3:].isdigit()
        for identifier in identifiers
    )


def test_every_realization_marks_the_requirement_its_specification_verifies(
    would_be_store: store.StoreLoader,
) -> None:
    """The markers in the content must agree with the edges in the manifest.

    Two ways of saying the same thing sit in this store: an edge manifest
    declaring ``SEG-TS-001 → SEG-SREQ-005``, and a docstring field inside the
    hashed content saying which requirement that test verifies. Nothing forces
    them to agree, and they are edited in different files, so the check is here.

    ``:verifies:`` names the requirement, matching the direction of the
    ``Verifies`` edge; ``:test-id:`` names the specification the function
    realizes, which a test's identity needs stated because it is manual and
    deliberately independent of the function's name and location. Pointing
    ``:verifies:`` at the specification instead would make one word mean two
    things, and an extractor honouring it would emit a self-loop.
    """
    declared = dict(
        tomllib.loads((WOULD_BE_STORE / "edges" / "coverage.toml").read_text(encoding="utf-8"))[
            "edges"
        ]["Verifies"]
    )
    specifications = WOULD_BE_STORE / "content" / "test-specification"
    marked = {}
    for realization in sorted(specifications.glob("*.impl.txt")):
        fields = dict(
            re.findall(r"^\s*:(verifies|test-id): (\S+)$", realization.read_text(), re.MULTILINE)
        )
        assert set(fields) == {"verifies", "test-id"}, realization.name
        assert fields["test-id"] == realization.name.removesuffix(".impl.txt")
        marked[fields["test-id"]] = fields["verifies"]
    assert marked == declared


def test_every_outcome_result_agrees_with_the_content_it_hashes(
    would_be_store: store.StoreLoader,
) -> None:
    """The manifest's result and the hashed result record must say one thing.

    The record field is the claim the graph carries; the content file is the
    authority it summarizes. They are edited in different files and nothing
    else forces them to agree, so the check is here.
    """
    outcomes = [node for node in would_be_store.nodes() if node.kind == "TestOutcome"]
    assert outcomes
    for node in outcomes:
        text = (WOULD_BE_STORE / "content" / node.content_anchors["contentHash"].path).read_text(
            encoding="utf-8"
        )
        assert node.result is not None, node.local_id
        assert f"result: {node.result.value}" in text, node.local_id


def test_the_store_is_reproducible_across_loads(would_be_store: store.StoreLoader) -> None:
    """Two loads of an unchanged store give byte-identical hashes.

    The whole apparatus rests on this: a hash that varied per run would make
    every edge suspect on the next look for no reason at all.
    """
    again = store.StoreLoader(WOULD_BE_STORE)
    assert [(node.local_id, dict(node.content_hashes)) for node in would_be_store.nodes()] == [
        (node.local_id, dict(node.content_hashes)) for node in again.nodes()
    ]
