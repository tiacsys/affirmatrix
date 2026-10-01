"""The configuration loader (SEG-SREQ-117…126, 135, 191…198).

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

DIGEST_ONE = "sha256:" + "1" * 64
DIGEST_TWO = "sha256:" + "2" * 64


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
    assert loaded.case == tmp_path / "elsewhere"


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
    assert loaded.producer_root == tmp_path / "tests/fixtures/would_be_store"


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
    assert loaded.case == tmp_path / "case-two"


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


# ── Relative paths resolve against the file's directory ────────────────────


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_relative_case_resolves_against_the_files_directory(tmp_path: Path) -> None:
    """SEG-SREQ-135."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "case: ./the-case\n")
    assert config.load(path).case == tmp_path / "repo" / "the-case"


def test_a_relative_producer_root_resolves_against_the_files_directory(tmp_path: Path) -> None:
    """SEG-SREQ-135."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "producer:\n  root: ./store\n")
    assert config.load(path).producer_root == tmp_path / "repo" / "store"


def test_a_relative_repository_path_resolves_against_the_files_directory(tmp_path: Path) -> None:
    """SEG-SREQ-135."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "repositories:\n  impl: ../impl\n")
    assert config.load(path).repository("impl") == tmp_path / "repo" / ".." / "impl"


def test_an_absolute_path_in_the_file_is_carried_unchanged(tmp_path: Path) -> None:
    """SEG-SREQ-135."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "case: /an/absolute/case\n")
    assert config.load(path).case == Path("/an/absolute/case")


def test_a_file_in_a_subdirectory_yields_the_same_paths_from_any_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    """SEG-SREQ-135."""
    path = _write(
        tmp_path / "repo" / "affirmatrix.yaml", "case: ./case\nproducer:\n  root: ./store\n"
    )
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    monkeypatch.chdir(tmp_path / "one")
    from_one = config.load(path)
    monkeypatch.chdir(tmp_path / "two")
    assert config.load(path) == from_one


def test_the_defaults_of_an_absent_file_stay_relative_to_the_working_directory(
    tmp_path: Path,
) -> None:
    """SEG-SREQ-135."""
    assert config.load(tmp_path / "sub" / "absent.yaml").case == Path("case")


def test_a_file_lacking_a_case_key_defaults_the_case_against_the_working_directory(
    tmp_path: Path,
) -> None:
    """SEG-SREQ-135: a default is the loader's, not a path the file gives."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "roles: [A]\n")
    assert config.load(path).case == Path("case")


def test_a_callers_case_is_not_resolved_against_the_files_directory(tmp_path: Path) -> None:
    """SEG-SREQ-135."""
    path = _write(tmp_path / "repo" / "affirmatrix.yaml", "case: ./from-file\n")
    assert config.load(path, case=Path("mine")).case == Path("mine")


# ── The producer's reader inputs ───────────────────────────────────────────

_PRODUCER = """\
producer:
  root: ./store
  repository: sample-repo
  requirements:
    export: needs/needs.json
    types: [sreq, sys]
    source: doc
  specifications:
    export: twister/testcases.json
    doxygen: xml/tests
  implementations:
    export: needs/impl.json
    doxygen: xml/src
  outcomes:
    - bundle: run1
      digest: sha256:1111111111111111111111111111111111111111111111111111111111111111
    - bundle: run2
      digest: sha256:2222222222222222222222222222222222222222222222222222222222222222
"""


def _producer(tmp_path: Path, text: str = _PRODUCER) -> config.ProducerConfig | None:
    return config.load(_write(tmp_path / "repo" / "affirmatrix.yaml", text)).producer


def test_a_configuration_without_a_producer_block_carries_no_producer(tmp_path: Path) -> None:
    """SEG-SREQ-191."""
    assert _producer(tmp_path, "case: ./case\n") is None


def test_a_producer_block_naming_only_a_root_carries_no_producer(tmp_path: Path) -> None:
    """SEG-SREQ-191: ``root`` is the store loader's key and configures no reader."""
    assert _producer(tmp_path, "producer:\n  root: ./store\n") is None


def test_a_producer_root_is_still_carried_beside_the_new_keys(tmp_path: Path) -> None:
    """SEG-SREQ-191."""
    loaded = config.load(_write(tmp_path / "repo" / "affirmatrix.yaml", _PRODUCER))
    assert loaded.producer_root == tmp_path / "repo" / "store"


def test_the_producers_repository_name_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-192."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.repository == "sample-repo"


def test_the_requirement_export_location_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-193."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.requirements is not None
    assert producer.requirements.export == tmp_path / "repo" / "needs/needs.json"


def test_the_requirement_types_are_carried_as_a_set(tmp_path: Path) -> None:
    """SEG-SREQ-194."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.requirements is not None
    assert producer.requirements.types == frozenset({"sreq", "sys"})


def test_the_requirement_source_directory_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-198."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.requirements is not None
    assert producer.requirements.source == tmp_path / "repo" / "doc"


def test_the_test_specification_export_and_doxygen_locations_are_carried(tmp_path: Path) -> None:
    """SEG-SREQ-195."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.specifications is not None
    assert producer.specifications == config.SpecificationInputs(
        export=tmp_path / "repo" / "twister/testcases.json",
        doxygen=tmp_path / "repo" / "xml/tests",
    )


def test_the_implementation_export_and_doxygen_locations_are_carried(tmp_path: Path) -> None:
    """SEG-SREQ-196."""
    producer = _producer(tmp_path)
    assert producer is not None and producer.implementations is not None
    assert producer.implementations == config.ImplementationInputs(
        export=tmp_path / "repo" / "needs/impl.json",
        doxygen=tmp_path / "repo" / "xml/src",
    )


def test_each_runs_bundle_and_digest_are_carried_in_file_order(tmp_path: Path) -> None:
    """SEG-SREQ-197."""
    producer = _producer(tmp_path)
    assert producer is not None
    base = tmp_path / "repo"
    assert producer.outcomes == (
        config.RunInputs(base / "run1", DIGEST_ONE),
        config.RunInputs(base / "run2", DIGEST_TWO),
    )


def test_no_runs_configured_carries_an_empty_tuple(tmp_path: Path) -> None:
    """SEG-SREQ-197."""
    producer = _producer(tmp_path, "producer:\n  repository: sample-repo\n")
    assert producer is not None and producer.outcomes == ()


def test_a_reader_block_not_configured_is_none(tmp_path: Path) -> None:
    """SEG-SREQ-191."""
    producer = _producer(tmp_path, "producer:\n  repository: sample-repo\n")
    assert producer is not None
    assert (producer.requirements, producer.specifications, producer.implementations) == (
        None,
        None,
        None,
    )


def test_an_absolute_producer_path_is_carried_unchanged(tmp_path: Path) -> None:
    """SEG-SREQ-135, SEG-SREQ-195."""
    producer = _producer(
        tmp_path,
        "producer:\n  specifications:\n    export: /abs/t.json\n    doxygen: /abs/xml\n",
    )
    assert producer is not None and producer.specifications is not None
    assert producer.specifications.export == Path("/abs/t.json")


def test_producer_configuration_is_immutable(tmp_path: Path) -> None:
    """SEG-SREQ-191."""
    producer = _producer(tmp_path)
    assert producer is not None
    with pytest.raises(AttributeError):
        producer.repository = "other"  # type: ignore[misc]


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


def test_a_requirements_block_missing_its_source_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.requirements\.source"):
        _producer(
            tmp_path, "producer:\n  requirements:\n    export: e.json\n    types: [sreq]\n"
        )


def test_requirement_types_that_are_not_strings_are_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.requirements\.types"):
        _producer(
            tmp_path,
            "producer:\n  requirements:\n    export: e\n    types: [1]\n    source: s\n",
        )


def test_outcomes_that_are_not_a_list_are_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.outcomes"):
        _producer(tmp_path, "producer:\n  outcomes: nope\n")


def test_an_outcome_missing_its_digest_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.outcomes\[0\]\.digest"):
        _producer(tmp_path, "producer:\n  outcomes:\n    - {bundle: a}\n")


def test_a_producer_sub_block_that_is_not_a_mapping_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.specifications"):
        _producer(tmp_path, "producer:\n  specifications: nope\n")


def test_a_producer_path_that_is_not_a_string_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.implementations\.doxygen"):
        _producer(tmp_path, "producer:\n  implementations:\n    export: e\n    doxygen: 3\n")


def test_a_producer_repository_that_is_not_a_string_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.repository"):
        _producer(tmp_path, "producer:\n  repository: [a]\n")


def test_a_runs_repository_name_is_carried(tmp_path: Path) -> None:
    """SEG-SREQ-197."""
    producer = _producer(
        tmp_path,
        "producer:\n  outcomes:\n"
        f"    - {{bundle: a, digest: {DIGEST_ONE}, repository: evidence}}\n",
    )
    assert producer is not None and producer.outcomes[0].repository == "evidence"


def test_a_run_without_a_repository_name_carries_none(tmp_path: Path) -> None:
    """SEG-SREQ-197."""
    producer = _producer(
        tmp_path, f"producer:\n  outcomes:\n    - {{bundle: a, digest: {DIGEST_ONE}}}\n"
    )
    assert producer is not None and producer.outcomes[0].repository is None


def test_a_runs_repository_that_is_not_a_string_is_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match=r"producer\.outcomes\[0\]\.repository"):
        _producer(
            tmp_path,
            f"producer:\n  outcomes:\n    - {{bundle: a, digest: {DIGEST_ONE}, repository: 3}}\n",
        )


@pytest.mark.parametrize("digest", ["abc", "sha256:ABC", "sha1:" + "1" * 40, "sha256:" + "1" * 63])
def test_a_digest_that_is_not_sha256_and_64_lowercase_hex_digits_is_a_refusal(
    tmp_path: Path, digest: str
) -> None:
    """SEG-SREQ-197."""
    with pytest.raises(config.ConfigError, match=r"producer\.outcomes\[0\]\.digest"):
        _producer(tmp_path, f"producer:\n  outcomes:\n    - {{bundle: a, digest: '{digest}'}}\n")


def test_a_run_with_one_of_the_old_keys_is_refused_naming_it(tmp_path: Path) -> None:
    """SEG-SREQ-197: the keys of a run before bundles are no longer read."""
    text = f"producer:\n  outcomes:\n    - {{bundle: a, digest: {DIGEST_ONE}, revision: r}}\n"
    with pytest.raises(config.ConfigError, match="'revision'"):
        _producer(tmp_path, text)
