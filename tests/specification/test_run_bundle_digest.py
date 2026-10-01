"""Verification suite for the digest of a run bundle.

Each function below realizes one test specification (``SEG-TS-nnn``) and
demonstrates the software requirement named in its ``:verifies:`` marker. A run
bundle is a directory. Its digest is the identity of the bundle: the SHA-256 of
the list of the bundle's files, in the order of their paths, each given by its
path in the bundle and the SHA-256 of its bytes.

The tests compare the tool's digest with the recipe of the architecture page,
which ``evidence_support.recipe_digest`` writes a second time in plain Python
and which the first test also runs in the shell where the shell has the tools.
They change copies of the clean bundle in ``tmp_path`` and never the fixture.
The function that computes the digest is read inside the test bodies only, so
this module collects before the code carries it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .evidence_support import CLEAN_BUNDLE, CLEAN_DIGEST, copy_bundle, recipe_digest

SHELL_RECIPE = (
    "find . -type f -printf '%P\\n' | LC_ALL=C sort | xargs -d '\\n' sha256sum | sha256sum"
)


def _digest(path: Path) -> str:
    from affirmatrix.sources import outcomes

    return outcomes.bundle_digest(path)


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-220: the extractor computes no digest of a run bundle"
)
def test_a_bundle_digest_is_the_sha256_of_its_file_list_by_path_and_content(
    tmp_path: Path,
) -> None:
    """A run bundle's digest is the SHA-256 of its list of paths and file digests.

    The clean bundle fixture holds 11 files. Its digest by the recipe of the
    architecture page is the value named in the fixture's README. The recipe
    is run in plain Python, and in the shell with find, sort and sha256sum
    where the shell has them. Both give that value. The tool gives that value
    too, written as ``sha256:`` and the 64 hex digits, whatever the location of
    the bundle.

    :verifies: SEG-SREQ-220
    :test-id: SEG-TS-067
    """
    assert len(list(CLEAN_BUNDLE.iterdir())) == 11
    assert recipe_digest(CLEAN_BUNDLE) == CLEAN_DIGEST
    if shutil.which("sha256sum") and shutil.which("find") and shutil.which("xargs"):
        done = subprocess.run(
            ["bash", "-c", SHELL_RECIPE],
            cwd=CLEAN_BUNDLE,
            check=True,
            capture_output=True,
            text=True,
        )
        assert done.stdout.split()[0] == CLEAN_DIGEST

    assert _digest(CLEAN_BUNDLE) == f"sha256:{CLEAN_DIGEST}"
    assert _digest(copy_bundle(tmp_path, "elsewhere")) == f"sha256:{CLEAN_DIGEST}"


@pytest.mark.xfail(
    strict=True, reason="SEG-SREQ-220: the extractor computes no digest of a run bundle"
)
def test_a_changed_byte_a_renamed_file_or_a_new_file_changes_the_digest(tmp_path: Path) -> None:
    """A changed byte, a renamed file or an added file changes the digest of a bundle.

    Four copies of the clean bundle each differ from it in one way: one byte of
    the run artifact is changed, one file is renamed, one file is added, and one
    empty file is added. Each copy has a digest that differs from the clean
    bundle's digest and from every other copy's. Three more copies differ in
    no byte and no name: the files are created in the reverse order, the bundle
    lies in another directory under another name, and every file has another
    modification time. Each has the clean bundle's digest.

    :verifies: SEG-SREQ-220
    :test-id: SEG-TS-068
    """
    clean = _digest(CLEAN_BUNDLE)

    changed = copy_bundle(tmp_path, "changed")
    artifact = changed / "twister.json"
    payload = bytearray(artifact.read_bytes())
    payload[-2] ^= 0x01
    artifact.write_bytes(bytes(payload))
    renamed = copy_bundle(tmp_path, "renamed")
    (renamed / "command.txt").rename(renamed / "command.sh")
    added = copy_bundle(tmp_path, "added")
    (added / "notes.txt").write_text("a new file\n", encoding="utf-8")
    emptied = copy_bundle(tmp_path, "emptied")
    (emptied / "empty.flag").write_bytes(b"")
    different = [_digest(path) for path in (changed, renamed, added, emptied)]
    assert clean not in different
    assert len(set(different)) == 4

    reordered = tmp_path / "bundles" / "reordered"
    reordered.mkdir(parents=True)
    for source in sorted(CLEAN_BUNDLE.iterdir(), reverse=True):
        shutil.copyfile(source, reordered / source.name)
    moved = tmp_path / "somewhere" / "else" / "other-name"
    shutil.copytree(CLEAN_BUNDLE, moved)
    touched = copy_bundle(tmp_path, "touched")
    for path in touched.iterdir():
        os.utime(path, (1_000_000_000, 1_000_000_000))
    for same in (reordered, moved, touched):
        assert _digest(same) == clean
