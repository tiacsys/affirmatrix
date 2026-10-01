"""The taxonomy provider — the built-in safety-evidence graph type.

Single internal source for the node and edge kinds (SEG-SREQ-029), which edge
kinds propagate suspicion (SEG-SREQ-030), and the content-hash names each node
kind carries (SEG-SREQ-032). Nothing else in the engine hardwires a kind name;
a record declaring a kind this provider does not declare is rejected by the
graph builder (SEG-SREQ-031) — the provider declares, the builder refuses.

This version populates the provider from constants — the built-in
safety-evidence graph type. A user-definable graph vocabulary is out of scope
and would plug in here rather than anywhere else, which is the point of routing
every kind lookup through one place.

**The spellings below are part of the integrity surface.** ADR-0005 folds the
node kind and the content-hash names into the node-hash preimage, so renaming
one re-hashes every node of that kind and sends every edge touching them
suspect. They are local tokens, not serialized ones: ``Requirement``, never
``seg:Requirement`` (ADR-0007). Treat a rename as a migration, not a tidy-up.

Iteration-0 backlog item B6.
"""

from __future__ import annotations

from types import MappingProxyType

#: Node kind to the names of the content hashes that kind carries.
#:
#: The three single-hash kinds share the name ``contentHash``: each covers one
#: canonical content form and there is nothing to distinguish within them. They
#: do not collide, because the node kind is folded into the preimage alongside
#: the names — the disambiguation is structural, so per-kind coinages would add
#: vocabulary without adding separation.
#:
#: The two split kinds separate *intent* from *execution*, which is what lets a
#: suspect edge report which half moved: a changed ``apiHash`` or ``specHash``
#: asks whether the thing still satisfies its requirement, a changed
#: ``bodyHash`` or ``implHash`` asks whether it needs running again.
_CONTENT_HASH_NAMES: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        "Requirement": frozenset({"contentHash"}),
        "Implementation": frozenset({"apiHash", "bodyHash"}),
        "TestSpecification": frozenset({"specHash", "implHash"}),
        "TestOutcome": frozenset({"contentHash"}),
        "Waiver": frozenset({"contentHash"}),
    }
)

_EDGE_KINDS = frozenset(
    {
        "Refines",
        "Verifies",
        "Implements",
        "Confirms",
        "Witnesses",
        "Excuses",
        "Calls",
    }
)

#: Suspicion travels up the design edges and stops at the evidence boundary.
#: Propagating through ``Confirms`` would mark a test specification suspect
#: because an outcome went stale, inviting re-affirmation where re-execution is
#: what is actually needed.
_PROPAGATING_EDGE_KINDS = frozenset({"Refines", "Verifies", "Implements"})

#: The kinds that carry test evidence. The case stores none of them: evidence
#: is built from run bundles when a verdict is made.
_EVIDENCE_NODE_KINDS = frozenset({"TestOutcome"})
_EVIDENCE_EDGE_KINDS = frozenset({"Confirms", "Witnesses", "Excuses"})


def node_kinds() -> frozenset[str]:
    """The node kinds of the built-in safety-evidence graph type.

    :implements: SEG-SREQ-029
    """
    return frozenset(_CONTENT_HASH_NAMES)


def edge_kinds() -> frozenset[str]:
    """The edge kinds of the built-in safety-evidence graph type.

    :implements: SEG-SREQ-029
    """
    return _EDGE_KINDS


def propagating_edge_kinds() -> frozenset[str]:
    """The edge kinds that carry suspicion from one endpoint to the other.

    :implements: SEG-SREQ-030
    """
    return _PROPAGATING_EDGE_KINDS


def propagates(edge_kind: str) -> bool:
    """Whether suspicion travels along an edge of this kind.

    :implements: SEG-SREQ-030

    An undeclared kind raises rather than answering ``False``. A misspelling
    that quietly answered "does not propagate" would switch off suspicion for a
    whole class of edges and leave the graph looking healthier than it is,
    which is the one failure mode this component must not have.
    """
    if edge_kind not in _EDGE_KINDS:
        raise ValueError(f"{edge_kind!r} is not a declared edge kind")
    return edge_kind in _PROPAGATING_EDGE_KINDS


def content_hash_names(node_kind: str) -> frozenset[str]:
    """The names of the content hashes a node of this kind carries.

    :implements: SEG-SREQ-032

    This is the declaration a node hash is derived against (SEG-SREQ-005): the
    names travel into the preimage paired with their digests, so what this
    function returns is not merely descriptive.
    """
    try:
        return _CONTENT_HASH_NAMES[node_kind]
    except KeyError:
        raise ValueError(f"{node_kind!r} is not a declared node kind") from None


def evidence_node_kinds() -> frozenset[str]:
    """The node kinds that carry test evidence, which the case does not store.

    :implements: SEG-SREQ-227
    """
    return _EVIDENCE_NODE_KINDS


def evidence_edge_kinds() -> frozenset[str]:
    """The edge kinds that carry test evidence, which the case does not store.

    :implements: SEG-SREQ-227
    """
    return _EVIDENCE_EDGE_KINDS


__all__ = [
    "content_hash_names",
    "edge_kinds",
    "evidence_edge_kinds",
    "evidence_node_kinds",
    "node_kinds",
    "propagates",
    "propagating_edge_kinds",
]
