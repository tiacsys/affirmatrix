"""Verification suite for the requirements reader over exports that differ from the first fixture.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. The
tests read the small synthetic export under ``tests/fixtures/capture_shape/``.
Its requirements keep their parent links in a field called ``trace``. A field
called ``refines`` holds a decoy link. No test follows the decoy when the
configuration names ``trace``. Each variant of the export is built in the test,
in a temporary directory. The reader is reached through the configuration file,
the way the command line reaches it. The expected digests come from the
standard library alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from affirmatrix.sources import SourceError

from . import capture_support as support

REFINES = "Refines"


def _refines_edges(edges) -> set[tuple[str, str]]:
    return {(edge.from_id, edge.to_id) for edge in edges if edge.kind == REFINES}


def _file(tmp_path: Path, **keys: Any) -> Path:
    return support.configuration(
        tmp_path, requirements=support.requirements_block(**keys), default_repository="docs"
    )


def _with_refines_field(needs: dict[str, dict[str, Any]]) -> None:
    """Hold each need's parents in ``refines`` instead of ``trace``, as the first fixture does."""
    for need in needs.values():
        need["refines"] = list(need.pop("trace"))


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-271: the parent field is fixed to refines")
def test_parent_links_come_from_the_configured_field(tmp_path: Path) -> None:
    """Parent links come from the configured need field.

    The configuration names the field trace. Reading the fixture export gives
    exactly three Refines edges: R-2 to R-1, R-3 to R-1 and R-3 to R-2. No edge
    goes to R-DECOY, the link in the field refines of R-2.

    :verifies: SEG-SREQ-271
    :test-id: SEG-TS-160
    """
    _, edges = support.records(_file(tmp_path, **{support.KEY_PARENT: "trace"}))
    assert _refines_edges(edges) == {("R-2", "R-1"), ("R-3", "R-1"), ("R-3", "R-2")}


def test_the_parent_field_defaults_to_refines(tmp_path: Path) -> None:
    """The parent-link field defaults to refines.

    The configuration names no parent field. Reading the fixture export gives
    exactly one Refines edge, R-2 to R-DECOY, the link in the field refines. The
    links in the field trace are not followed.

    :verifies: SEG-SREQ-272
    :test-id: SEG-TS-161
    """
    _, edges = support.records(_file(tmp_path))
    assert _refines_edges(edges) == {("R-2", "R-DECOY")}


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-273: the anchor is the generated document path")
def test_a_requirement_is_anchored_at_its_mapped_source_file(tmp_path: Path) -> None:
    """A Requirement is anchored at its mapped source file.

    The configuration holds a source map and no source directory. The content
    hash anchor of R-1 and R-2 names the repository docs, the path reqs/alpha.sdoc
    and the locator need:R-1 or need:R-2. That of R-3 names reqs/beta.sdoc. The
    digest of each equals the digest of the source directory form for the same
    need. So the map changes the anchor and never the hash.

    :verifies: SEG-SREQ-273
    :test-id: SEG-TS-162
    """
    base = support.requirements_block()
    mapped = support.without(base, "source")
    mapped[support.KEY_MAP] = support.SOURCE_MAP
    nodes, _ = support.records(
        support.configuration(
            tmp_path, requirements=mapped, default_repository="docs", name="mapped.yaml"
        )
    )
    plain, _ = support.records(
        support.configuration(
            tmp_path, requirements=base, default_repository="docs", name="plain.yaml"
        )
    )
    expected = {"R-1": "reqs/alpha.sdoc", "R-2": "reqs/alpha.sdoc", "R-3": "reqs/beta.sdoc"}
    for ident, path in expected.items():
        anchor = nodes[ident].content_anchors[support.CONTENT_HASH]
        assert (anchor.repository, anchor.path, anchor.locator) == ("docs", path, f"need:{ident}")
        assert anchor.digest == plain[ident].content_anchors[support.CONTENT_HASH].digest


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-274: a source map is not read")
def test_a_docname_the_source_map_does_not_cover_is_refused(tmp_path: Path) -> None:
    """A docname the source map does not cover is refused, and every one is named.

    In a copy of the export, two needs of the configured type req sit in the
    documents docs/delta and docs/epsilon. The map does not name them. Building
    the reader raises a source error that names both docnames. It names none of
    docs/alpha, docs/beta and docs/gamma. The first two are mapped. The third holds
    only a need of the type info, and that type is not configured.

    :verifies: SEG-SREQ-274
    :test-id: SEG-TS-163
    """

    def move(needs: dict[str, dict[str, Any]]) -> None:
        needs["R-2"]["docname"] = "docs/delta"
        needs["R-3"]["docname"] = "docs/epsilon"

    export = support.variant(tmp_path, support.REQUIREMENTS_EXPORT, move, "uncovered")
    block = support.without(support.requirements_block(export=str(export)), "source")
    block[support.KEY_MAP] = support.SOURCE_MAP
    path = support.configuration(tmp_path, requirements=block, default_repository="docs")
    with pytest.raises(SourceError) as caught:
        support.producer_of(path)
    message = str(caught.value)
    assert "docs/delta" in message and "docs/epsilon" in message
    for covered in ("docs/alpha", "docs/beta", "docs/gamma"):
        assert covered not in message


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-147: the parent field is fixed to refines")
def test_a_content_hash_covers_the_parent_links_of_the_configured_field(tmp_path: Path) -> None:
    """A content hash covers the parent links of the configured field.

    The configuration names the field trace. For each requirement, the contentHash
    digest equals a SHA-256 that the test computes. The test hashes the canonical
    JSON of the title, the content and the sorted parent links, under the key
    refines.
    The digest also equals the digest from a copy of the export whose parents sit
    in the field refines, read with the default. The decoy link of R-2 changes
    nothing.

    :verifies: SEG-SREQ-147
    :test-id: SEG-TS-184
    """
    nodes, _ = support.records(_file(tmp_path, **{support.KEY_PARENT: "trace"}))
    needs = support.needs_of(support.document_of(support.REQUIREMENTS_EXPORT))
    renamed = support.variant(tmp_path, support.REQUIREMENTS_EXPORT, _with_refines_field, "renamed")
    twin, _ = support.records(_file(tmp_path, export=str(renamed)))
    for ident, parents in support.REFERENCE_PARENTS.items():
        need = needs[ident]
        digest = nodes[ident].content_anchors[support.CONTENT_HASH].digest
        assert digest == support.canonical_digest(need["content"], parents, need["title"])
        assert digest == twin[ident].content_anchors[support.CONTENT_HASH].digest


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-148: the parent field is fixed to refines")
def test_the_order_of_parent_links_does_not_change_the_hash(tmp_path: Path) -> None:
    """The order of the parent links does not change the content hash.

    The configuration names the field trace. In a copy of the export, the links of
    R-3 are listed in the other order. The contentHash digest of R-3 is the digest
    the fixture gives. Both equal the SHA-256 of the canonical form of R-3 with its
    parents sorted. The test computes that digest.

    :verifies: SEG-SREQ-148
    :test-id: SEG-TS-185
    """
    keys = {support.KEY_PARENT: "trace"}
    before, _ = support.records(_file(tmp_path, **keys))

    def reverse(needs: dict[str, dict[str, Any]]) -> None:
        needs["R-3"]["trace"].reverse()

    export = support.variant(tmp_path, support.REQUIREMENTS_EXPORT, reverse, "reversed")
    after, _ = support.records(_file(tmp_path, export=str(export), **keys))
    key = support.CONTENT_HASH
    assert after["R-3"].content_anchors[key].digest == before["R-3"].content_anchors[key].digest
    need = support.needs_of(support.document_of(support.REQUIREMENTS_EXPORT))["R-3"]
    expected = support.canonical_digest(need["content"], ["R-1", "R-2"], need["title"])
    assert after["R-3"].content_anchors[key].digest == expected


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-149: Refines edges are read from refines only")
def test_refines_edges_come_from_declared_parent_links_only(tmp_path: Path) -> None:
    """Refines edges come from the declared parent links, and from no back-link field.

    The configuration names the field trace. R-1 holds the back-links R-2 and R-3
    in the field trace_back. Reading the export gives one pending Refines edge per
    declared link, from the child to the parent: three edges, and none from R-1.

    :verifies: SEG-SREQ-149
    :test-id: SEG-TS-186
    """
    _, edges = support.records(_file(tmp_path, **{support.KEY_PARENT: "trace"}))
    refines = [edge for edge in edges if edge.kind == REFINES]
    assert len(refines) == 3
    assert {edge.state.value for edge in refines} == {"pending"}
    assert not [edge for edge in refines if edge.from_id == "R-1"]


@pytest.mark.xfail(strict=True, reason="SEG-SREQ-151: a reader has no repository of its own")
def test_a_requirement_is_anchored_in_the_repository_of_the_reader(tmp_path: Path) -> None:
    """A Requirement is anchored in the repository configured for the requirements reader.

    The default repository is suite. The requirements reader names the repository
    docs and a source directory in it. The content hash anchor of R-1 names the
    repository docs and the path reqs/docs/alpha.rst. That path joins the source
    directory, the docname and the doctype, within docs.

    :verifies: SEG-SREQ-151
    :test-id: SEG-TS-187
    """
    block = support.requirements_block(**{support.KEY_REPOSITORY: "docs"})
    path = support.configuration(tmp_path, requirements=block, default_repository="suite")
    nodes, _ = support.records(path)
    anchor = nodes["R-1"].content_anchors[support.CONTENT_HASH]
    assert (anchor.repository, anchor.path) == ("docs", "reqs/docs/alpha.rst")
