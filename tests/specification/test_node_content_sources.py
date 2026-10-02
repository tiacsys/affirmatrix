"""Verification suite for the bytes that a record source supplies behind a hash.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A record
source that reads the content a hash covers gives, for a node and the name of
one hash, the bytes it hashed. Each test takes every node of one source and every
hash name of the node. It asks the source for the bytes and takes their SHA-256.
The digest must be the one in the anchor of the node record. The expected value is
read from the record the source supplies, never from the source's own hashing code.

Four sources read content: the requirements reader, the content extractor (test
specifications and implementations), the would-be store, and the composed producer
that chains the readers. The outcome reader does not. Its hash covers a record
that it builds from a run bundle, so it has no content to supply (see the record
source page of the requirement specification).

The name of the method that gives the bytes is in ``node_show_support``.
"""

from __future__ import annotations

from pathlib import Path

from . import capture_support as shape
from . import node_show_support as support

WOULD_BE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "would_be_store"


def _assert_bytes_match_every_hash(source, nodes) -> set[str]:
    """Check each hash of each node. Return the hash names that were seen."""
    seen: set[str] = set()
    for record in nodes:
        for name, anchor in record.content_anchors.items():
            data = support.content_of(source, record.local_id, name)
            assert data is not None, (record.local_id, name)
            assert support.digest_of(data) == anchor.digest, (record.local_id, name)
            seen.add(name)
    return seen


def test_the_requirements_reader_supplies_the_bytes_it_hashed(tmp_path: Path) -> None:
    """The requirements reader supplies the bytes from which it computed each hash.

    The reader reads the requirement export of the capture-shape fixture. It
    supplies three requirement records, each with the hash contentHash. For each
    record, asking the reader for the bytes behind contentHash gives bytes whose
    SHA-256 is the digest in the anchor of that record. The bytes are not empty.

    :verifies: SEG-SREQ-311
    :test-id: SEG-TS-223
    """
    from affirmatrix.sources.reqs import RequirementsReader

    path = shape.configuration(
        tmp_path,
        requirements=shape.requirements_block(**{shape.KEY_REPOSITORY: "docs"}),
    )
    (reader,) = support.members(shape.producer_of(path), RequirementsReader)
    nodes = list(reader.nodes())
    assert {record.local_id for record in nodes} == set(shape.REFERENCE_PARENTS)
    assert _assert_bytes_match_every_hash(reader, nodes) == {"contentHash"}
    for record in nodes:
        assert support.content_of(reader, record.local_id, "contentHash")


def test_the_content_extractor_supplies_the_bytes_it_hashed(tmp_path: Path) -> None:
    """The content extractor supplies the bytes from which it computed each hash.

    The extractor reads the test-case export and the implementation export of the
    capture-shape fixture, with their Doxygen output and their C sources. It
    supplies test specification records with specHash and implHash, and
    implementation records with apiHash and bodyHash. Take each record and each
    hash name. The bytes that the extractor gives for the hash have a SHA-256.
    That SHA-256 is the digest in the anchor of the record.

    :verifies: SEG-SREQ-311
    :test-id: SEG-TS-224
    """
    from affirmatrix.sources.content import CSourceExtractor

    producer = shape.producer_of(support.composed_configuration(tmp_path, requirements=False))
    (extractor,) = support.members(producer, CSourceExtractor)
    nodes = list(extractor.nodes())
    seen = _assert_bytes_match_every_hash(extractor, nodes)
    assert seen == {"specHash", "implHash", "apiHash", "bodyHash"}


def test_the_would_be_store_supplies_the_bytes_it_hashed() -> None:
    """The would-be store supplies the bytes from which it computed each hash.

    The store loader reads the would-be store fixture. It supplies requirement,
    test specification and implementation records. Take each record and each
    hash name. The bytes that the loader gives for the hash have a SHA-256.
    That SHA-256 is the digest in the anchor of the record.

    :verifies: SEG-SREQ-311
    :test-id: SEG-TS-225
    """
    from affirmatrix.sources.store import StoreLoader

    loader = StoreLoader(root=WOULD_BE_STORE)
    nodes = list(loader.nodes())
    assert {record.kind for record in nodes} == {
        "Requirement",
        "TestSpecification",
        "Implementation",
    }
    seen = _assert_bytes_match_every_hash(loader, nodes)
    assert seen == {"contentHash", "specHash", "implHash", "apiHash", "bodyHash"}


def test_the_composed_producer_supplies_the_bytes_it_hashed(tmp_path: Path) -> None:
    """The composed producer supplies the bytes from which any of its readers computed a hash.

    The producer chains the requirements reader and the content extractor over
    the capture-shape fixture. It supplies records of three kinds. Take each
    record and each hash name. The bytes that the producer gives for the hash
    have a SHA-256. That SHA-256 is the digest in the anchor of the record. The
    reader of the record gives the same bytes.

    :verifies: SEG-SREQ-311
    :test-id: SEG-TS-226
    """
    producer = shape.producer_of(support.composed_configuration(tmp_path))
    nodes = list(producer.nodes())
    assert {record.kind for record in nodes} == {
        "Requirement",
        "TestSpecification",
        "Implementation",
    }
    seen = _assert_bytes_match_every_hash(producer, nodes)
    assert seen == {"contentHash", "specHash", "implHash", "apiHash", "bodyHash"}
    for record in nodes:
        (answering,) = [
            member
            for member in producer.sources
            if record.local_id in {one.local_id for one in member.nodes()}
        ]
        for name in record.content_anchors:
            assert support.content_of(producer, record.local_id, name) == support.content_of(
                answering, record.local_id, name
            )
