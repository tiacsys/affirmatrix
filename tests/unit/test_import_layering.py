"""Import-direction checks over the engine's own source tree.

The component map (ADR-0004) declares a strict layering, and four ADRs each
rest on an import boundary staying intact:

* ADR-0003 / ADR-0005 — the commitment layer is a leaf, so its
  metadata-agnostic purity is mechanically checkable rather than conventional;
* ADR-0005 — ``_hashing`` is the single implementation site for the hash
  encoding, so it is the only module that may reach ``hashlib``;
* ADR-0004 / ADR-0007 — ``case`` sits *below* ``proof`` and ``affirmation`` in
  the layering, and ``identity`` never reaches the commitment layer, which is
  what keeps the revisable IRI base out of every hash preimage;
* ADR-0010 — ``cli/_repository.py`` is the one module the command-line
  adapter may run git from, so it is the only module that may reach
  ``subprocess``.

Prose cannot enforce any of that, so this module parses ``src/affirmatrix``
with ``ast`` and compares each component's direct imports against a declared
allow-list. A developer test, not a graph participant.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "affirmatrix"

# The sixteen top-level import names: thirteen component keys from the ADR-0004
# map (its four ``sources.*`` rows share one key) plus the three shared
# internals, which are not components and never requirement subjects.
COMPONENTS: frozenset[str] = frozenset(
    {
        "_hashing",
        "affirmation",
        "case",
        "cli",
        "commitment",
        "config",
        "diagnostics",
        "drift",
        "gates",
        "graph",
        "identity",
        "proof",
        "records",
        "satisfaction",
        "sources",
        "taxonomy",
    }
)

# Direct in-package imports each component may make. Read as a *ceiling*, not a
# forecast: a component need not use everything it is permitted.
ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    # Foundations — no engine dependencies at all.
    "_hashing": frozenset(),
    "diagnostics": frozenset(),
    "taxonomy": frozenset(),
    "config": frozenset(),
    # The commitment layer is a leaf (ADR-0003, ADR-0005).
    "commitment": frozenset({"_hashing"}),
    # Identifier minting and the persisted vocabulary.
    "identity": frozenset({"config"}),
    # Records validate digest shape at construction — a hex digest caught where
    # the record is built, rather than where it is finally hashed, names the
    # producer that supplied it.
    "records": frozenset({"_hashing", "diagnostics", "taxonomy"}),
    # Record sources and persistence sit BELOW the graph (ADR-0004).
    "sources": frozenset({"_hashing", "config", "diagnostics", "identity", "records", "taxonomy"}),
    "case": frozenset({"config", "diagnostics", "identity", "records", "taxonomy"}),
    # The graph.
    "graph": frozenset({"commitment", "diagnostics", "records", "taxonomy"}),
    # Derivations over the graph.
    "satisfaction": frozenset({"diagnostics", "graph", "records", "taxonomy"}),
    "drift": frozenset({"commitment", "diagnostics", "graph", "records", "taxonomy"}),
    # The components an operator drives.
    "gates": frozenset({"diagnostics", "drift", "graph", "records", "satisfaction", "taxonomy"}),
    "proof": frozenset(
        {
            "case",
            "commitment",
            "config",
            "diagnostics",
            "drift",
            "gates",
            "graph",
            "identity",
            "records",
            "satisfaction",
            "taxonomy",
        }
    ),
    "affirmation": frozenset(
        {"case", "commitment", "diagnostics", "graph", "identity", "records", "taxonomy"}
    ),
    # The thin CLI may reach anything; nothing may reach it.
    "cli": COMPONENTS - {"cli"},
}


def _module_files() -> list[Path]:
    """Every component source file.

    The package's own ``__init__.py`` is excluded: it belongs to no component,
    it only names the package.
    """
    package_init = PACKAGE_ROOT / "__init__.py"
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if path != package_init)


def _component_of_path(path: Path) -> str:
    """The top-level import name a source file belongs to."""
    relative = path.relative_to(PACKAGE_ROOT)
    return relative.parts[0] if len(relative.parts) > 1 else relative.stem


def _dotted_name_of_path(path: Path) -> str:
    """The absolute dotted module name of a source file."""
    relative = path.relative_to(PACKAGE_ROOT)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = relative.stem
    return ".".join(["affirmatrix", *parts])


def _package_of(dotted: str, path: Path) -> str:
    """The package a module resolves relative imports against."""
    return dotted if path.name == "__init__.py" else dotted.rsplit(".", 1)[0]


def _component_of_dotted(dotted: str) -> str | None:
    parts = dotted.split(".")
    if parts[0] != "affirmatrix" or len(parts) < 2:
        return None
    return parts[1]


def _imported_targets(tree: ast.AST, package: str) -> set[str]:
    """Absolute dotted names this module imports, relative imports resolved."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = ""
            else:
                segments = package.split(".")
                trimmed = segments[: len(segments) - (node.level - 1)]
                base = ".".join(trimmed)
            head = f"{base}.{node.module}" if base and node.module else (node.module or base)
            if head:
                targets.add(head)
            # ``from affirmatrix import identity`` carries the component in the
            # imported *name*, not the module, so record both forms. A symbol
            # import records a harmless extra target under the same component.
            targets.update(f"{head}.{alias.name}" if head else alias.name for alias in node.names)
    return targets


def _in_package_imports() -> dict[str, set[str]]:
    """Component -> the set of OTHER components it imports directly."""
    edges: dict[str, set[str]] = {name: set() for name in COMPONENTS}
    for path in _module_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        origin = _component_of_path(path)
        dotted = _dotted_name_of_path(path)
        for target in _imported_targets(tree, _package_of(dotted, path)):
            component = _component_of_dotted(target)
            if component is not None and component != origin:
                edges[origin].add(component)
    return edges


def _transitive_imports(start: str, edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = list(edges[start])
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(edges.get(current, set()))
    return seen


@pytest.fixture(scope="module")
def edges() -> dict[str, set[str]]:
    return _in_package_imports()


def test_the_tree_matches_the_declared_component_set() -> None:
    """Every module on disk belongs to a declared component, and vice versa."""
    on_disk = {_component_of_path(path) for path in _module_files()}
    assert on_disk == COMPONENTS


def test_every_component_declares_an_allow_list() -> None:
    assert set(ALLOWED_IMPORTS) == COMPONENTS


def test_imports_respect_the_declared_layering(edges: dict[str, set[str]]) -> None:
    violations = {
        component: sorted(imported - ALLOWED_IMPORTS[component])
        for component, imported in edges.items()
        if imported - ALLOWED_IMPORTS[component]
    }
    assert violations == {}, f"undeclared imports (ADR-0004 layering): {violations}"


def test_only_the_hashing_module_imports_hashlib() -> None:
    """ADR-0005: one implementation site for the hash encoding."""
    offenders = sorted(
        _component_of_path(path)
        for path in _module_files()
        if _component_of_path(path) != "_hashing"
        and "hashlib" in _imported_targets(ast.parse(path.read_text(encoding="utf-8")), "")
    )
    assert offenders == []


def test_only_the_repository_module_imports_subprocess() -> None:
    """ADR-0010: one adapter module runs git; nothing else may reach ``subprocess``."""
    offenders = sorted(
        str(path.relative_to(PACKAGE_ROOT))
        for path in _module_files()
        if str(path.relative_to(PACKAGE_ROOT)) != "cli/_repository.py"
        and "subprocess" in _imported_targets(ast.parse(path.read_text(encoding="utf-8")), "")
    )
    assert offenders == []


def test_the_commitment_layer_is_a_leaf(edges: dict[str, set[str]]) -> None:
    """ADR-0003: metadata-agnostic primitives, no engine dependencies but bytes."""
    assert edges["commitment"] <= {"_hashing"}


def test_the_affirmation_store_never_imports_proof_or_affirmation(
    edges: dict[str, set[str]],
) -> None:
    """ADR-0004: ``case`` stays below the components that produce its records."""
    assert edges["case"].isdisjoint({"proof", "affirmation"})


def test_identity_never_reaches_the_commitment_layer(edges: dict[str, set[str]]) -> None:
    """ADR-0007: the revisable IRI base cannot reach a hash preimage."""
    assert "identity" not in _transitive_imports("commitment", edges)


def test_record_sources_and_persistence_stay_below_the_graph(
    edges: dict[str, set[str]],
) -> None:
    """ADR-0004: the record-source adapters and the store sit under the builder."""
    assert "graph" not in edges["sources"]
    assert "graph" not in edges["case"]


def test_nothing_imports_the_cli(edges: dict[str, set[str]]) -> None:
    """The CLI is a presentation layer, never a dependency."""
    importers = sorted(component for component, imported in edges.items() if "cli" in imported)
    assert importers == []
