"""Shared helpers for the specifications of edge selection over evidence edges.

Not a specification. The modules that realize specifications import these
helpers. The store here is the would-be store of ``subtree_support`` and more: a
test outcome, the evidence edges that tie it to a test specification and an
implementation, a call edge between two implementations, a refinement edge whose
far end is no node, and three edges of an evidence kind that have a requirement
at one end.

Edges of the three evidence kinds reach the edge verbs only through the
``--current`` store, because a case holds none of them and the verbs read no run
bundle. The store is built by the test, inside ``tmp_path``. The expected sets of
edges are written out here by hand. No test asks the code under test for the
value that it checks.

The three edges with a requirement at one end are not edges that a producer
supplies: a producer ties an outcome to a specification and to an implementation,
never to a requirement. They are here because an edge selection by the subtree of
a requirement can meet an evidence edge only through a requirement at one end of
it, so the rule that the selection admits only three kinds of edge can be
observed only with them.
"""

from __future__ import annotations

from pathlib import Path

from . import subtree_support as base

OUTCOME = "OUT-1"
SPECIFICATION = "TS-LEAF"
IMPLEMENTATION = "IMP-LEAF"
DECOY = "REQ-DECOY"
#: A requirement with no requirement that refines it, and so no refiner.
NO_REFINERS = "REQ-ALONE"

#: Edges of an evidence kind that a producer supplies.
EVIDENCE: tuple[base.Edge, ...] = (
    ("Confirms", OUTCOME, SPECIFICATION),
    ("Witnesses", OUTCOME, IMPLEMENTATION),
    ("Calls", IMPLEMENTATION, "IMP-BOTH"),
)

#: Edges of an evidence kind with a requirement at one end. A producer supplies none.
AT_A_REQUIREMENT: tuple[base.Edge, ...] = (
    ("Confirms", OUTCOME, base.LEAF),
    ("Witnesses", OUTCOME, base.MID),
    ("Calls", IMPLEMENTATION, base.LEAF),
)

#: A refinement edge whose far end is no node of the store.
BROKEN = ("Refines", base.LEAF, DECOY)

#: Everything that the store holds in addition to the edges of ``subtree_support``.
ADDED: tuple[base.Edge, ...] = (*EVIDENCE, *AT_A_REQUIREMENT, BROKEN)

#: The leaf of the store has a Verifies and an Implements edge, so one of each is selected.
INSIDE_LEAF = frozenset({("Verifies", "TS-LEAF", base.LEAF), ("Implements", "IMP-LEAF", base.LEAF)})

#: The two edges that name the requirement with no refiner.
INSIDE_ALONE = frozenset(
    {("Verifies", "TS-ALONE", NO_REFINERS), ("Implements", "IMP-ALONE", NO_REFINERS)}
)


def build(tmp_path: Path) -> base.World:
    """The store of ``subtree_support`` with the additions of this module, and an empty case."""
    world = base.build(tmp_path)
    store = world.store
    content = store / "content"
    (content / "outcome").mkdir(parents=True, exist_ok=True)
    (content / "outcome" / f"{OUTCOME}.txt").write_text("passed\n", encoding="utf-8")
    (store / "nodes" / "outcomes.toml").write_text(
        'kind = "TestOutcome"\n\n[nodes]\n'
        f'"{OUTCOME}" = {{ contentHash = "outcome/{OUTCOME}.txt", result = "passed", '
        'revision = "abc" }\n',
        encoding="utf-8",
    )
    for name, fields, folder, kind in (
        (NO_REFINERS, ("contentHash",), "requirements", "Requirement"),
        ("TS-ALONE", ("specHash", "implHash"), "specifications", "TestSpecification"),
        ("IMP-ALONE", ("apiHash", "bodyHash"), "implementations", "Implementation"),
    ):
        for field in fields:
            path = content / folder / f"{name}.{field}.txt"
            path.write_text(f"the {field} of {name}\n", encoding="utf-8")
        entries = ", ".join(f'{field} = "{folder}/{name}.{field}.txt"' for field in fields)
        (store / "nodes" / f"{name}.toml").write_text(
            f'kind = "{kind}"\n\n[nodes]\n"{name}" = {{ {entries} }}\n', encoding="utf-8"
        )
    lines = ["[edges]"]
    kinds = ("Refines", "Verifies", "Implements", "Confirms", "Witnesses", "Calls")
    added = (
        *ADDED,
        ("Verifies", "TS-ALONE", NO_REFINERS),
        ("Implements", "IMP-ALONE", NO_REFINERS),
    )
    for kind in kinds:
        pairs = ", ".join(f'["{a}", "{b}"]' for k, a, b in added if k == kind)
        if pairs:
            lines.append(f"{kind} = [{pairs}]")
    (store / "edges" / "evidence.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return world


def everything() -> set[base.Edge]:
    """Every edge of the store."""
    return base.all_edges() | set(ADDED) | INSIDE_ALONE
