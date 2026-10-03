"""Verification suite for the configuration examples that the documentation shows.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A
reader who copies a configuration example from a page must get a file that the
loader accepts. The loader refuses a key it does not know, so an example with a
mistyped key, or with a key of another block, would stop that reader. The test
reads the sources of the pages and does not build them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from affirmatrix import config

DOCUMENTATION = Path(__file__).resolve().parents[2] / "doc"
PAGES = ("manual", "requirement-specification")
_DIRECTIVE = re.compile(r"^(?P<indent>\s*)\.\. code-block::\s+ya?ml\s*$")


def _blocks(page: Path) -> list[str]:
    """The text of each YAML code block of a page, with the indentation of the block removed."""
    lines = page.read_text(encoding="utf-8").splitlines()
    found: list[str] = []
    for number, line in enumerate(lines):
        opened = _DIRECTIVE.match(line)
        if opened is None:
            continue
        outer = len(opened["indent"])
        body: list[str] = []
        for text in lines[number + 1 :]:
            if text.strip() and len(text) - len(text.lstrip()) <= outer:
                break
            body.append(text)
        body = [text for text in body if not text.strip().startswith(":")]
        margin = min((len(t) - len(t.lstrip()) for t in body if t.strip()), default=0)
        found.append("\n".join(text[margin:] for text in body))
    return found


def _examples() -> list[tuple[str, str]]:
    pages = sorted(path for name in PAGES for path in (DOCUMENTATION / name).rglob("*.rst"))
    return [
        (f"{page.relative_to(DOCUMENTATION)}:{index}", block)
        for page in pages
        for index, block in enumerate(_blocks(page), 1)
    ]


EXAMPLES = _examples()


def test_the_pages_show_at_least_one_configuration_example() -> None:
    """The scan for YAML examples in the pages finds at least one.

    The manual shows its configuration file in a YAML code block at least once, in
    the installation tutorial. The scan reads every page of the manual and of the
    requirement specification and finds that block among the examples. A scan
    that finds none would let the next test pass for the wrong reason.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-442
    """
    assert [name for name, _ in EXAMPLES if "installation" in name]


@pytest.mark.parametrize(("name", "text"), EXAMPLES, ids=[name for name, _ in EXAMPLES])
def test_every_configuration_example_of_the_pages_loads(
    name: str, text: str, tmp_path: Path
) -> None:
    """Every YAML configuration example that a page shows is accepted by the loader.

    A page of the manual or of the requirement specification shows a
    configuration in a YAML code block. The block is written to a file, as it
    stands, and the loader reads the file. Loading raises no configuration error,
    so that no example holds a key that the loader refuses. This is tried for each
    YAML block of each page, one at a time.

    :verifies: SEG-SREQ-376
    :test-id: SEG-TS-443
    """
    assert isinstance(yaml.safe_load(text), dict), name
    path = tmp_path / "affirmatrix.yaml"
    path.write_text(text, encoding="utf-8")

    config.load(path)
