"""Verification suite for the taxonomy provider's declared vocabulary.

Each function below realizes one test specification (``SEG-TS-nnn``)
and demonstrates the software requirement named in its ``:verifies:`` marker
by calling the taxonomy provider's public surface directly.
"""

from __future__ import annotations

from affirmatrix import taxonomy


def test_the_taxonomy_declares_exactly_the_built_in_kind_set() -> None:
    """The built-in kind set is closed.

    Querying the taxonomy provider's node-kind and edge-kind sets returns
    exactly the built-in vocabulary: the node kinds are Requirement,
    Implementation, TestSpecification, TestOutcome, and Waiver; the edge
    kinds are Refines, Verifies, Implements, Confirms, Witnesses, Excuses,
    and Calls. Neither set holds anything beyond this list, and neither
    omits an entry from it.

    :verifies: SEG-SREQ-029
    :test-id: SEG-TS-001
    """
    assert taxonomy.node_kinds() == frozenset(
        {"Requirement", "Implementation", "TestSpecification", "TestOutcome", "Waiver"}
    )
    assert taxonomy.edge_kinds() == frozenset(
        {"Refines", "Verifies", "Implements", "Confirms", "Witnesses", "Excuses", "Calls"}
    )


def test_exactly_refines_verifies_and_implements_propagate() -> None:
    """Exactly three edge kinds propagate.

    Querying the taxonomy provider for the edge kinds that propagate
    suspicion returns exactly three: Refines, Verifies, and Implements. No
    other declared edge kind is included, and none of these three is
    missing.

    :verifies: SEG-SREQ-030
    :test-id: SEG-TS-002
    """
    assert taxonomy.propagating_edge_kinds() == frozenset({"Refines", "Verifies", "Implements"})


def test_each_node_kind_declares_its_content_hash_names() -> None:
    """Each node kind declares its content hashes.

    For each of the five built-in node kinds, querying the taxonomy
    provider's content-hash names returns exactly the names that kind
    carries: ``contentHash`` alone for Requirement, TestOutcome, and
    Waiver; ``apiHash`` and ``bodyHash`` for Implementation; ``specHash``
    and ``implHash`` for TestSpecification.

    :verifies: SEG-SREQ-032
    :test-id: SEG-TS-003
    """
    assert taxonomy.content_hash_names("Requirement") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("TestOutcome") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("Waiver") == frozenset({"contentHash"})
    assert taxonomy.content_hash_names("Implementation") == frozenset({"apiHash", "bodyHash"})
    assert taxonomy.content_hash_names("TestSpecification") == frozenset({"specHash", "implHash"})
