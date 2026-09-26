"""The configuration loader (SEG-SREQ-117…126).

Every parameter defaults when the file is absent (or empty); a caller's
value (the command line's own ``--case``) overrides the file's; a
repository name absent from the map resolves to no repository rather than
raising; a file that exists but cannot be made sense of — the wrong shape
at the top level, or a key of the wrong type — is a refusal. Nothing this
loader carries reaches a hash — proven at the command-line level in
``test_cli_proof.py``, since ``commitment`` never imports this module at all
(``test_import_layering.py``'s own structural check) and a demonstrated
guarantee is a different claim from a structural one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from affirmatrix import config


def test_every_parameter_defaults_when_the_file_is_absent(tmp_path: Path) -> None:
    """SEG-SREQ-119."""
    loaded = config.load(tmp_path / "no-such-file.yaml")
    assert loaded == config.Config()


def test_every_parameter_defaults_when_the_file_is_empty(tmp_path: Path) -> None:
    """SEG-SREQ-119: ``safe_load`` reads an empty file as ``None``, the same as absent."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("", encoding="utf-8")
    assert config.load(path) == config.Config()


def test_the_case_root_defaults_to_dot_case() -> None:
    """SEG-SREQ-120."""
    assert config.Config().case == Path("case")


def test_configuration_is_read_from_a_given_file(tmp_path: Path) -> None:
    """SEG-SREQ-118."""
    path = tmp_path / "custom.yaml"
    path.write_text("case: ./elsewhere\n", encoding="utf-8")
    loaded = config.load(path)
    assert loaded.case == Path("./elsewhere")


def test_configuration_defaults_to_the_conventional_path(tmp_path: Path, monkeypatch) -> None:
    """SEG-SREQ-118: no path given reads ``./affirmatrix.yaml`` from the cwd."""
    (tmp_path / config.DEFAULT_CONFIG_PATH).write_text(
        "case: ./from-default-path\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    loaded = config.load()
    assert loaded.case == Path("./from-default-path")


def test_a_name_absent_from_the_repository_map_resolves_to_no_repository(tmp_path: Path) -> None:
    """SEG-SREQ-121."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("repositories:\n  implementation: /a/repo\n", encoding="utf-8")
    loaded = config.load(path)
    assert loaded.repository("implementation") == Path("/a/repo")
    assert loaded.repository("no-such-name") is None


def test_the_implementation_repositorys_path_is_resolved_through_the_map(tmp_path: Path) -> None:
    """SEG-SREQ-122."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text(
        "repositories:\n  implementation: /a/repo\nimplementation: implementation\n",
        encoding="utf-8",
    )
    loaded = config.load(path)
    assert loaded.implementation_repository() == Path("/a/repo")


def test_an_implementation_name_absent_from_the_map_carries_no_repository(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("implementation: never-configured\n", encoding="utf-8")
    loaded = config.load(path)
    assert loaded.implementation_repository() is None


def test_the_producer_location_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-123."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text(
        "producer:\n  root: ./tests/fixtures/would_be_store\n", encoding="utf-8"
    )
    loaded = config.load(path)
    assert loaded.producer_root == Path("./tests/fixtures/would_be_store")


def test_the_producer_location_defaults_to_none(tmp_path: Path) -> None:
    assert config.load(tmp_path / "absent.yaml").producer_root is None


def test_an_optional_role_vocabulary_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-124."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("roles: [SoftwareEngineer, TestEngineer]\n", encoding="utf-8")
    loaded = config.load(path)
    assert loaded.roles == frozenset({"SoftwareEngineer", "TestEngineer"})


def test_no_role_vocabulary_configured_carries_none(tmp_path: Path) -> None:
    assert config.load(tmp_path / "absent.yaml").roles is None


def test_a_callers_case_overrides_the_files(tmp_path: Path) -> None:
    """SEG-SREQ-125."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("case: ./from-file\n", encoding="utf-8")
    loaded = config.load(path, case=Path("./from-caller"))
    assert loaded.case == Path("./from-caller")


def test_comments_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("# a comment\n\ncase: ./case-two  # trailing comment\n", encoding="utf-8")
    loaded = config.load(path)
    assert loaded.case == Path("./case-two")


def test_the_multi_stream_layout_is_a_supported_configuration(tmp_path: Path) -> None:
    """Several named repositories at once, exercised as a fixture."""
    path = tmp_path / "affirmatrix.yaml"
    path.write_text(
        "\n".join(
            [
                "case: ./case",
                "repositories:",
                "  implementation: /repos/impl",
                "  requirements: /repos/reqs",
                "  tests: /repos/tests",
                "implementation: implementation",
            ]
        ),
        encoding="utf-8",
    )
    loaded = config.load(path)
    assert loaded.repository("implementation") == Path("/repos/impl")
    assert loaded.repository("requirements") == Path("/repos/reqs")
    assert loaded.repository("tests") == Path("/repos/tests")
    assert loaded.implementation_repository() == Path("/repos/impl")


# ── Refusals: a file that exists but cannot be made sense of ───────────────


def test_a_top_level_that_is_not_a_mapping_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="mapping"):
        config.load(path)


def test_case_of_the_wrong_type_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("case: [not, a, string]\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="case"):
        config.load(path)


def test_repositories_of_the_wrong_type_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("repositories: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="repositories"):
        config.load(path)


def test_a_repositories_path_of_the_wrong_type_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("repositories:\n  implementation: 42\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="repositories"):
        config.load(path)


def test_roles_of_the_wrong_type_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("roles: SoftwareEngineer\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="roles"):
        config.load(path)


def test_producer_of_the_wrong_type_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("producer: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="producer"):
        config.load(path)


def test_malformed_yaml_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "affirmatrix.yaml"
    path.write_text("case: [unterminated\n", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load(path)
