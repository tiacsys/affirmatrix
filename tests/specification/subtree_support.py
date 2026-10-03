"""Shared helpers for the specifications of edge selection inside a subtree.

Not a specification. The modules that realize specifications import these
helpers: one would-be store of the shape that makes a subtree selection go
wrong, a runner for the three verbs that share the selection, and readers of
what each verb did.

Every fixture is built by the test, inside ``tmp_path``. The store holds
requirements, implementations and test specifications, and it holds no
repository, so every affirmation is made with a revision that the test gives.
The expected sets of edges are written out here by hand, from the shape of the
store. No test asks the code under test for the value that it checks, with one
exception that the specification of the cut names: the scope that proof
collection takes is read from the library.

The shape of the store. An arrow runs from the refining requirement to the one
it refines, from an implementation to the requirement that it implements, and
from a test specification to the requirement that it verifies::

    REQ-TOP-PARENT <-- REQ-TOP <-- REQ-MID <-- REQ-LEAF
          ^                ^
          |                +------- REQ-TWO-PARENTS --> REQ-OTHER-PARENT
    REQ-SIBLING                                               ^
                                                    REQ-OUTSIDE-CHILD

``REQ-TOP`` has a parent that is outside its subtree. ``REQ-MID`` refines
``REQ-TOP`` and ``REQ-LEAF`` refines ``REQ-MID``, a chain of refinement.
``REQ-TWO-PARENTS`` refines ``REQ-TOP`` and also ``REQ-OTHER-PARENT``, which is
outside. ``REQ-OUTSIDE-CHILD`` refines only ``REQ-OTHER-PARENT``. ``REQ-SIBLING``
refines the parent of ``REQ-TOP``. One implementation implements a requirement
inside and one outside, and so does one test specification. ``REQ-LEAF`` has
both a Verifies edge and an Implements edge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from affirmatrix import case, graph
from affirmatrix.cli import main
from affirmatrix.sources.store import StoreLoader

GIVEN = "d" * 40
TOP = "REQ-TOP"
MID = "REQ-MID"
LEAF = "REQ-LEAF"

#: Every edge of the store, as (kind, from, to).
EDGES: tuple[tuple[str, str, str], ...] = (
    ("Refines", "REQ-TOP", "REQ-TOP-PARENT"),
    ("Refines", "REQ-MID", "REQ-TOP"),
    ("Refines", "REQ-LEAF", "REQ-MID"),
    ("Refines", "REQ-TWO-PARENTS", "REQ-TOP"),
    ("Refines", "REQ-TWO-PARENTS", "REQ-OTHER-PARENT"),
    ("Refines", "REQ-OUTSIDE-CHILD", "REQ-OTHER-PARENT"),
    ("Refines", "REQ-SIBLING", "REQ-TOP-PARENT"),
    ("Verifies", "TS-LEAF", "REQ-LEAF"),
    ("Verifies", "TS-BOTH", "REQ-TWO-PARENTS"),
    ("Verifies", "TS-BOTH", "REQ-OUTSIDE-CHILD"),
    ("Verifies", "TS-OUTSIDE", "REQ-OUTSIDE-CHILD"),
    ("Implements", "IMP-LEAF", "REQ-LEAF"),
    ("Implements", "IMP-BOTH", "REQ-MID"),
    ("Implements", "IMP-BOTH", "REQ-OUTSIDE-CHILD"),
    ("Implements", "IMP-OUTSIDE", "REQ-OTHER-PARENT"),
)

#: The requirements in the subtree of TOP.
SUBTREE_OF_TOP = frozenset({"REQ-TOP", "REQ-MID", "REQ-LEAF", "REQ-TWO-PARENTS"})

#: The edges that lie inside the subtree of TOP.
INSIDE_TOP = frozenset(
    {
        ("Refines", "REQ-MID", "REQ-TOP"),
        ("Refines", "REQ-LEAF", "REQ-MID"),
        ("Refines", "REQ-TWO-PARENTS", "REQ-TOP"),
        ("Verifies", "TS-LEAF", "REQ-LEAF"),
        ("Verifies", "TS-BOTH", "REQ-TWO-PARENTS"),
        ("Implements", "IMP-LEAF", "REQ-LEAF"),
        ("Implements", "IMP-BOTH", "REQ-MID"),
    }
)

#: The edges that lie inside the subtree of MID, a requirement that is not a top.
INSIDE_MID = frozenset(
    {
        ("Refines", "REQ-LEAF", "REQ-MID"),
        ("Verifies", "TS-LEAF", "REQ-LEAF"),
        ("Implements", "IMP-LEAF", "REQ-LEAF"),
        ("Implements", "IMP-BOTH", "REQ-MID"),
    }
)

Edge = tuple[str, str, str]


def _requirement_ids() -> list[str]:
    ids = {edge[2] for edge in EDGES if edge[0] == "Refines"}
    ids |= {edge[1] for edge in EDGES if edge[0] == "Refines"}
    ids |= {edge[2] for edge in EDGES if edge[0] != "Refines"}
    return sorted(ids)


def _manifest(kind: str, fields: tuple[str, ...], ids: list[str], folder: str) -> str:
    lines = [f'kind = "{kind}"', "", "[nodes]"]
    for local_id in ids:
        entries = ", ".join(f'{field} = "{folder}/{local_id}.{field}.txt"' for field in fields)
        lines.append(f'"{local_id}" = {{ {entries} }}')
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class World:
    """A would-be store of the shape above, and an empty case."""

    store: Path
    case: Path

    def arguments(self) -> list[str]:
        return ["--case", str(self.case), "--current", str(self.store)]


def build(tmp_path: Path) -> World:
    """The store of the shape in the module text, and an initialized case."""
    store = tmp_path / "store"
    content = store / "content"
    groups = (
        ("Requirement", ("contentHash",), _requirement_ids(), "requirements"),
        (
            "Implementation",
            ("apiHash", "bodyHash"),
            sorted({edge[1] for edge in EDGES if edge[0] == "Implements"}),
            "implementations",
        ),
        (
            "TestSpecification",
            ("specHash", "implHash"),
            sorted({edge[1] for edge in EDGES if edge[0] == "Verifies"}),
            "specifications",
        ),
    )
    for kind, fields, ids, document in groups:
        folder = document
        for local_id in ids:
            for field in fields:
                path = content / folder / f"{local_id}.{field}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"the {field} of {local_id}\n", encoding="utf-8")
        manifest = store / "nodes" / f"{document}.toml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(_manifest(kind, fields, ids, folder), encoding="utf-8")
    (store / "edges").mkdir(parents=True, exist_ok=True)
    kinds = ("Refines", "Verifies", "Implements")
    lines = ["[edges]"]
    for kind in kinds:
        pairs = ", ".join(f'["{a}", "{b}"]' for k, a, b in EDGES if k == kind)
        lines.append(f"{kind} = [{pairs}]")
    (store / "edges" / "design.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    case_root = tmp_path / "case"
    case.AffirmationStore(root=case_root).initialize()
    return World(store=store, case=case_root)


def _run(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    status = main(arguments)
    captured = capsys.readouterr()
    return status, captured.out + captured.err


def sync(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    """Write every node and every edge of the store into the case, as case sync does."""
    status, _ = _run(["case", "sync", *world.arguments()], capsys)
    assert status == 0


def show(
    world: World, capsys: pytest.CaptureFixture[str], *selection: str
) -> tuple[int, set[Edge]]:
    """Run ``edge show --json`` with the selection. Give the status and the edges it lists."""
    status, text = _run(["edge", "show", *world.arguments(), *selection, "--json"], capsys)
    try:
        rows = json.loads(text)["edges"]
    except (ValueError, KeyError, TypeError):
        return status, set()
    return status, {(row["kind"], row["from"], row["to"]) for row in rows}


def affirm(world: World, capsys: pytest.CaptureFixture[str], *selection: str) -> tuple[int, str]:
    """Run ``edge affirm`` with the selection, a given revision and a synthetic role."""
    return _run(
        [
            "edge", "affirm", *world.arguments(), *selection,
            "--role", "fixture-reviewer", "--reason", "synthetic", "--revision", GIVEN,
        ],
        capsys,
    )  # fmt: skip


def remove(world: World, capsys: pytest.CaptureFixture[str], *selection: str) -> tuple[int, str]:
    """Run ``case remove`` with the selection."""
    return _run(["case", "remove", "--case", str(world.case), *selection], capsys)


def affirmed_edges(world: World) -> set[Edge]:
    """The edges that the case holds a review event for."""
    store = case.AffirmationStore(root=world.case)
    return {
        (reference.kind, reference.from_id, reference.to_id)
        for reference in store.latest_review_event_identifiers()
    }


def held_edges(world: World) -> set[Edge]:
    """The edge records that the case holds."""
    store = case.AffirmationStore(root=world.case)
    return {(edge.kind, edge.from_id, edge.to_id) for edge in store.edges()}


def all_edges() -> set[Edge]:
    return set(EDGES)


def built_graph(world: World) -> graph.Graph:
    """The graph over the current records of the store, read with the library."""
    loader = StoreLoader(root=world.store)
    return graph.build(loader)
