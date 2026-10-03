"""Shared helpers for the specifications of the Doxygen path root.

A path root is a directory inside the repository that the content extractor puts
in front of each path a Doxygen output names. Every fixture is built in
``tmp_path``: a small header with a documentation comment and a macro of several
lines, a small test source, the Doxygen output that locates them, and the
configuration file. No file of a real project is read.

An expected digest is the SHA-256 of a run of whole lines of a file the test
wrote. The test finds the lines by scanning that file. It never calls the
extractor or its span functions for that.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr
from zlib import crc32

from . import capture_support as support

#: The path a Doxygen output names for the header, and the path inside the repository.
NAMED = "zephyr/queue.h"
ROOT = "include/"
JOINED = "include/zephyr/queue.h"
MACRO = "QUEUE_MAKE"
NEED = "I-QUEUE"

HEADER = (
    "/* Queue interface. */\n"
    "\n"
    "/**\n"
    " * @brief Define a queue and its storage.\n"
    " *\n"
    " * @satisfies{R-1}\n"
    " */\n"
    "#define QUEUE_MAKE(name, depth)\t\t\\\n"
    "\tstatic struct queue name = {\t\\\n"
    "\t\t.depth = (depth),\t\\\n"
    "\t\t.count = 0,\t\t\\\n"
    "\t}\n"
    "\n"
    "/** @brief A later macro. */\n"
    "#define QUEUE_LIMIT 4\n"
)

TEST_SOURCE = (
    "#include <ztest.h>\n"
    "\n"
    "/**\n"
    " * @brief {brief}\n"
    " *\n"
    " * @testid{{T-SHARED}}\n"
    " */\n"
    "ZTEST(suite, test_shared)\n"
    "{{\n"
    "\tzassert_true(true);\n"
    "}}\n"
)

#: The lines of the header, 1-based: the doc comment and the whole macro.
HEADER_COMMENT_FIRST = 3
HEADER_DEFINE = 8
HEADER_DEFINE_LAST = 12


def write_file(repository: Path, relative: str, text: str) -> None:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_in(repository: Path, relative: str = JOINED, text: str = HEADER) -> None:
    write_file(repository, relative, text)


def _member(name: str, kind: str, file: str, first: int, last: int) -> str:
    where = (
        f'file={quoteattr(file)} line="{first}" column="1" '
        f'bodyfile={quoteattr(file)} bodystart="{first}" bodyend="{last}"'
    )
    return (
        f'      <memberdef kind="{kind}" id="m_{crc32((name + file).encode()) % 10**6}" '
        f'prot="public" static="no">\n        <name>{name}</name>\n'
        f"        <location {where}/>\n      </memberdef>\n"
    )


def doxygen_tree(directory: Path, members: list[tuple[str, str, str, int, int]]) -> Path:
    """A Doxygen output holding the members ``(name, kind, file, first, last)``."""
    body = "".join(_member(*member) for member in members)
    text = (
        "<?xml version='1.0' encoding='UTF-8' standalone='no'?>\n"
        '<doxygen version="1.16.1" xml:lang="en-US">\n'
        '  <compounddef id="members" kind="file" language="C++">\n'
        "    <compoundname>members</compoundname>\n"
        f'    <sectiondef kind="func">\n{body}    </sectiondef>\n'
        "  </compounddef>\n</doxygen>\n"
    )
    write_file(directory, "members.xml", text)
    return directory


def macro_tree(directory: Path, named: str = NAMED) -> Path:
    """A Doxygen output that names the header macro in the file ``named``."""
    return doxygen_tree(directory, [(MACRO, "define", named, HEADER_DEFINE, HEADER_DEFINE_LAST)])


def implementations(tmp_path: Path, repository: Path, tree: Path, **keys: Any) -> Path:
    """A configuration whose implementation stream reads ``tree`` in ``repository``."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    export = support.export_of(tmp_path, [support.implementation_need(NEED, MACRO)], "impl")
    block = support.implementations_block(
        export=str(export), doxygen=str(tree), **{support.KEY_REPOSITORY: "lib"}
    )
    block.update(keys)
    return support.configuration(
        tmp_path,
        implementations=block,
        repositories={"lib": repository, "suite": repository},
    )


def specifications(
    tmp_path: Path, repository: Path, tree: Path, needs: list[dict[str, Any]], **keys: Any
) -> Path:
    """A configuration whose test stream reads ``tree`` in ``repository``."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    export = support.export_of(tmp_path, needs, "cases")
    block = support.specifications_block(
        export=str(export), doxygen=str(tree), **{support.KEY_REPOSITORY: "suite"}
    )
    block.update(keys)
    return support.configuration(
        tmp_path,
        specifications=block,
        repositories={"lib": repository, "suite": repository},
    )


@dataclass(frozen=True)
class Expected:
    """The digests of the header macro, computed from the file the test wrote."""

    api: bytes
    body: bytes


def expected_macro(repository: Path, relative: str = JOINED) -> Expected:
    """The digests of the macro in ``relative``: comment through the define line; the whole macro.

    The lines are found by scanning the file for the first comment opener, the
    line that names the macro and the last line of the continuation.
    """
    lines = support.file_lines(repository, relative)
    opener = next(n for n, text in enumerate(lines, 1) if text.startswith(b"/**"))
    define = next(n for n, text in enumerate(lines, 1) if f"#define {MACRO}".encode() in text)
    last = define
    while lines[last - 1].rstrip(b"\n").endswith(b"\\"):
        last += 1
    return Expected(
        api=support.sha(support.run_of(lines, opener, define)),
        body=support.sha(support.run_of(lines, define, last)),
    )


def source_with(brief: str) -> str:
    return TEST_SOURCE.format(brief=brief)


def case_need_for(ident: str = "T-SHARED", module: str | None = None) -> dict[str, Any]:
    need = support.case_need(ident, "test_shared")
    if module is None:
        del need["test_module"]
    else:
        need["test_module"] = module
    return need


def expected_test(repository: Path, relative: str) -> Expected:
    """The digests of the test in ``relative``: its comment; the test from its line to its end."""
    lines = support.file_lines(repository, relative)
    opener = next(n for n, text in enumerate(lines, 1) if text.startswith(b"/**"))
    closer = next(n for n, text in enumerate(lines, 1) if text.rstrip().endswith(b"*/"))
    first = next(n for n, text in enumerate(lines, 1) if b"ZTEST(" in text)
    last = next(n for n, text in enumerate(lines, 1) if text.startswith(b"}"))
    return Expected(
        api=support.sha(support.run_of(lines, opener, closer)),
        body=support.sha(support.run_of(lines, first, last)),
    )


def shared_tree(directory: Path, files: Mapping[str, str]) -> Path:
    """A Doxygen output that names the shared test in each file of ``files``."""
    members = [("test_shared", "function", name, 8, 11) for name in files]
    return doxygen_tree(directory, members)
