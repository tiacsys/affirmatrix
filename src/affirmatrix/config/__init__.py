"""The configuration loader — source topology behind one seam.

The set of source repositories, their names and roles, the location of the
producer that supplies the current stream, and the optional role vocabulary
an affirmation is checked against, are read from one file — never scattered
as literals through the engine, the record sources, or the command line. This
version ships the single-repository mapping, with the multi-stream layout
(several named repositories at once) retained as a supported configuration
and exercised as a fixture.

No value loaded here reaches a hash preimage. The identifier base is a
serialization concern and the integrity mechanics are not configurable, so
configuration never has to be hashed into a package to make one reproducible
— which is exactly the obligation that would otherwise follow from letting
settings influence hashes. The import layering keeps this structural
(``commitment`` never imports ``config``, directly or transitively); the
command line's own test that mutates every configured value and recomputes
is this requirement's behavioural evidence, since a structural guarantee and
a demonstrated one are different claims.

The file is real YAML, read with ``yaml.safe_load``:

.. code-block:: yaml

   case: ./case
   producer:
     root: ./tests/fixtures/would_be_store
   repositories:
     implementation: /path/to/impl/repo
     requirements: /path/to/reqs/repo
   implementation: implementation
   roles: [SoftwareEngineer, TestEngineer]

The producer block may also name the inputs the extraction readers consume —
``repository``, ``requirements`` (``export``, ``types``, ``source``),
``specifications`` and ``implementations`` (each ``export`` and ``doxygen``),
and a list of ``outcomes`` (each ``artifact``, ``revision`` and ``name``, and
optionally ``repository``). Every named field of a sub-block present is
required, except the ``repository`` of a run. It names the configured
repository that the files of the run lie under, and the producer's repository
is the default. A missing or mistyped field raises, naming its dotted key.

A relative path the file gives (``case``, ``producer.root``, every
``repositories`` value and every location under the producer's readers) is
taken from the directory that holds the file, so the same file names the same
places from any working directory; the defaults an absent file yields, and a
caller's own ``case``, stay relative to the current directory.

An absent file defaults every parameter (SEG-SREQ-119); an empty one —
``safe_load`` reads it as ``None`` — does too, the same as absent. A file
whose top level is not a mapping, or whose keys carry the wrong shape (a
``repositories`` entry that is not a string, say), is not a configuration
this loader can make sense of, and it raises rather than guessing at one; the
command line renders that refusal and exits 2, a request it could not judge.

What describes a case itself, rather than one run of the tool over it, is
carried elsewhere and is no part of this component's own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import yaml

#: Where the configuration loader reads from when its caller names no file.
DEFAULT_CONFIG_PATH = Path("affirmatrix.yaml")

#: Where the case root defaults to when neither the file nor the caller names one.
DEFAULT_CASE = Path("case")


class ConfigError(Exception):
    """A configuration file exists but cannot be made sense of.

    Raised for a top level that is not a mapping, or a key whose value is
    not the shape this loader declares — never for an absent file, which
    SEG-SREQ-119 asks this loader to default through instead.
    """


@dataclass(frozen=True, slots=True)
class RequirementsInputs:
    """Where the requirements reader finds its inputs.

    ``export`` is the requirement export, ``types`` the need types treated as
    Requirements, and ``source`` the requirement document's source directory
    against which a need's docname and doctype resolve to a source file.
    """

    export: Path
    types: frozenset[str]
    source: Path


@dataclass(frozen=True, slots=True)
class SpecificationInputs:
    """Where the content extractor finds a test specification's inputs."""

    export: Path
    doxygen: Path


@dataclass(frozen=True, slots=True)
class ImplementationInputs:
    """Where the content extractor finds an implementation's inputs."""

    export: Path
    doxygen: Path


@dataclass(frozen=True, slots=True)
class RunInputs:
    """Where one run to be extracted is recorded.

    ``artifact`` is the run artifact, ``revision`` the record of the run's
    full revision and ``name`` the record of the run's name. ``repository``
    names the configured repository that the files of the run lie under, or
    is ``None`` for the producer's own repository.
    """

    artifact: Path
    revision: Path
    name: Path
    repository: str | None = None


@dataclass(frozen=True, slots=True)
class ProducerConfig:
    """The inputs of every stream of records the producer supplies.

    Each reader's block is ``None`` when the file does not configure it;
    ``outcomes`` is empty when no run is configured. ``repository`` names the
    repository against which the producer's anchors and paths are resolved.
    """

    repository: str | None = None
    requirements: RequirementsInputs | None = None
    specifications: SpecificationInputs | None = None
    implementations: ImplementationInputs | None = None
    outcomes: tuple[RunInputs, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    """Every value describing where source content and its history live.

    :implements: SEG-SREQ-117

    ``case`` is the case root a caller's own default may still override
    (command-line ``--case``, say); ``producer_root`` is where the current
    stream's producer is found, absent when none is configured — in which
    case a caller must supply one explicitly, a two-stream verb's own rule to
    enforce, not this loader's. ``repositories`` maps a name an anchor's
    ``repository`` field may carry to the path it names; a name absent from
    it resolves to no repository (:meth:`repository`) rather than raising.
    ``implementation`` names which configured repository is the
    implementation one; ``roles`` is the optional closed vocabulary an
    affirmation's role is checked against, ``None`` when none is configured
    (every role accepted). ``producer`` carries the extraction readers'
    inputs, ``None`` when the file names none of them — a ``producer`` block
    holding only ``root`` is the store loader's and configures no reader.
    """

    case: Path = DEFAULT_CASE
    producer_root: Path | None = None
    repositories: Mapping[str, Path] = field(default_factory=dict)
    implementation: str | None = None
    roles: frozenset[str] | None = None
    producer: ProducerConfig | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "repositories", MappingProxyType(dict(self.repositories)))

    def repository(self, name: str) -> Path | None:
        """The path a repository name maps to, or no repository at all.

        :implements: SEG-SREQ-121

        A lookup miss is data, not an error: an anchor naming a repository
        this configuration does not map is read as having no repository
        behind it, the fallback trigger a judgement's revision resolution
        acts on, never a special case checked for separately.
        """
        return self.repositories.get(name)

    def implementation_repository(self) -> Path | None:
        """The implementation repository's path, if one is named and mapped.

        :implements: SEG-SREQ-122

        ``None`` both when no repository is named as the implementation one
        and when it is named but absent from the map — the same no-repository
        reading :meth:`repository` already gives a lookup miss.
        """
        return None if self.implementation is None else self.repository(self.implementation)


def load(path: Path | None = None, *, case: Path | None = None) -> Config:
    """Read a configuration file, or default every parameter it carries.

    :implements: SEG-SREQ-118
    :implements: SEG-SREQ-119
    :implements: SEG-SREQ-120
    :implements: SEG-SREQ-123
    :implements: SEG-SREQ-124
    :implements: SEG-SREQ-125
    :implements: SEG-SREQ-135

    ``path`` is the file to read, defaulting to :data:`DEFAULT_CONFIG_PATH`
    when not given; while that file does not exist, every parameter this
    loader carries defaults rather than the load refusing — the case root to
    :data:`DEFAULT_CASE`, everything else to absent. ``case``, when given, is
    the caller's own value (the command line's ``--case``) and is preferred
    over the file's — the loader's keyword parameter is where a caller's
    override enters; a future flag overriding another field is the same
    shape, not a new mechanism. Raises :class:`ConfigError` for a file that
    exists but cannot be made sense of — never for one that is merely absent.

    A relative path the file gives (``case``, ``producer.root``, every
    ``repositories`` value and every location under ``producer``) is taken from
    the directory that holds the file read, so the same file names the same
    places from any working directory; a caller's ``case`` and the defaults an
    absent file yields stay relative to the current directory.
    """
    file = path if path is not None else DEFAULT_CONFIG_PATH
    values = _read_file(file)
    base = file.parent
    if case is not None:
        case_root = case
    elif "case" in values:
        case_root = _anchored(base, _string(values, "case", str(DEFAULT_CASE)))
    else:
        case_root = DEFAULT_CASE
    return Config(
        case=case_root,
        producer_root=_producer_root(values, base),
        repositories=_repositories(values, base),
        implementation=_optional_string(values, "implementation"),
        roles=_roles(values),
        producer=_producer(values, base),
    )


def _read_file(path: Path) -> Mapping[str, object]:
    """The file's own mapping, or empty if it does not exist or is empty.

    :implements: SEG-SREQ-119
    """
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not readable as YAML: {error}") from error
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ConfigError(f"{path} does not describe a mapping at its top level")
    return loaded


def _string(values: Mapping[str, object], key: str, default: str) -> str:
    value = values.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{key!r} must be a string, not {value!r}")
    return value


def _optional_string(values: Mapping[str, object], key: str) -> str | None:
    if key not in values or values[key] is None:
        return None
    return _string(values, key, "")


def _anchored(base: Path, value: str) -> Path:
    return base / value


def _producer_root(values: Mapping[str, object], base: Path) -> Path | None:
    producer = values.get("producer")
    if producer is None:
        return None
    if not isinstance(producer, Mapping):
        raise ConfigError("'producer' must be a mapping")
    root = producer.get("root")
    if root is None:
        return None
    if not isinstance(root, str):
        raise ConfigError(f"'producer.root' must be a string, not {root!r}")
    return _anchored(base, root)


def _repositories(values: Mapping[str, object], base: Path) -> dict[str, Path]:
    repositories = values.get("repositories")
    if repositories is None:
        return {}
    if not isinstance(repositories, Mapping):
        raise ConfigError("'repositories' must be a mapping of name to path")
    result: dict[str, Path] = {}
    for name, path in repositories.items():
        if not isinstance(name, str) or not isinstance(path, str):
            raise ConfigError(
                f"'repositories' entry {name!r}: {path!r} must be a string name and a string path"
            )
        result[name] = _anchored(base, path)
    return result


def _producer(values: Mapping[str, object], base: Path) -> ProducerConfig | None:
    """The producer's reader inputs, or none when the file names no reader key.

    :implements: SEG-SREQ-191

    A ``producer`` block holding only ``root`` (the store loader's own key)
    configures no reader and yields ``None``.
    """
    producer = values.get("producer")
    if producer is None:
        return None
    if not isinstance(producer, Mapping):
        raise ConfigError("'producer' must be a mapping")
    reader_keys = ("repository", "requirements", "specifications", "implementations", "outcomes")
    if not any(producer.get(key) is not None for key in reader_keys):
        return None
    return ProducerConfig(
        repository=_producer_repository(producer),
        requirements=_requirements_inputs(producer, base),
        specifications=_specification_inputs(producer, base),
        implementations=_implementation_inputs(producer, base),
        outcomes=_outcome_inputs(producer, base),
    )


def _producer_repository(producer: Mapping[str, object]) -> str | None:
    """The name of the repository the producer's anchors and paths resolve against.

    :implements: SEG-SREQ-192
    """
    value = producer.get("repository")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"'producer.repository' must be a string, not {value!r}")
    return value


def _requirements_inputs(
    producer: Mapping[str, object], base: Path
) -> RequirementsInputs | None:
    """The requirement export, the Requirement need types and the source directory.

    :implements: SEG-SREQ-193
    :implements: SEG-SREQ-194
    :implements: SEG-SREQ-198
    """
    block = _block(producer, "requirements")
    if block is None:
        return None
    types = _required(block, "producer.requirements", "types")
    if not isinstance(types, list) or not all(isinstance(item, str) for item in types):
        raise ConfigError("'producer.requirements.types' must be a list of strings")
    return RequirementsInputs(
        export=_path(block, "producer.requirements", "export", base),
        types=frozenset(types),
        source=_path(block, "producer.requirements", "source", base),
    )


def _specification_inputs(
    producer: Mapping[str, object], base: Path
) -> SpecificationInputs | None:
    """The test-case export and the Doxygen output read for test specifications.

    :implements: SEG-SREQ-195
    """
    block = _block(producer, "specifications")
    if block is None:
        return None
    return SpecificationInputs(
        export=_path(block, "producer.specifications", "export", base),
        doxygen=_path(block, "producer.specifications", "doxygen", base),
    )


def _implementation_inputs(
    producer: Mapping[str, object], base: Path
) -> ImplementationInputs | None:
    """The implementation export and the Doxygen output read for implementations.

    :implements: SEG-SREQ-196
    """
    block = _block(producer, "implementations")
    if block is None:
        return None
    return ImplementationInputs(
        export=_path(block, "producer.implementations", "export", base),
        doxygen=_path(block, "producer.implementations", "doxygen", base),
    )


def _outcome_inputs(producer: Mapping[str, object], base: Path) -> tuple[RunInputs, ...]:
    """Each run's artifact, revision record, name record and repository name, in file order.

    :implements: SEG-SREQ-197
    """
    runs = producer.get("outcomes")
    if runs is None:
        return ()
    if not isinstance(runs, list):
        raise ConfigError("'producer.outcomes' must be a list")
    result = []
    for index, run in enumerate(runs):
        where = f"producer.outcomes[{index}]"
        if not isinstance(run, Mapping):
            raise ConfigError(f"'{where}' must be a mapping")
        result.append(
            RunInputs(
                artifact=_path(run, where, "artifact", base),
                revision=_path(run, where, "revision", base),
                name=_path(run, where, "name", base),
                repository=_run_repository(run, where),
            )
        )
    return tuple(result)


def _run_repository(run: Mapping[str, object], where: str) -> str | None:
    """The name of the repository a run's files lie under, or ``None`` when not given."""
    value = run.get("repository")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"'{where}.repository' must be a string, not {value!r}")
    return value


def _block(producer: Mapping[str, object], key: str) -> Mapping[str, object] | None:
    block = producer.get(key)
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ConfigError(f"'producer.{key}' must be a mapping")
    return block


def _required(block: Mapping[str, object], where: str, key: str) -> object:
    if block.get(key) is None:
        raise ConfigError(f"'{where}.{key}' is required")
    return block[key]


def _path(block: Mapping[str, object], where: str, key: str, base: Path) -> Path:
    value = _required(block, where, key)
    if not isinstance(value, str):
        raise ConfigError(f"'{where}.{key}' must be a string path, not {value!r}")
    return _anchored(base, value)


def _roles(values: Mapping[str, object]) -> frozenset[str] | None:
    roles = values.get("roles")
    if roles is None:
        return None
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ConfigError("'roles' must be a list of strings")
    return frozenset(roles)


__all__ = [
    "Config",
    "ConfigError",
    "DEFAULT_CASE",
    "DEFAULT_CONFIG_PATH",
    "ImplementationInputs",
    "ProducerConfig",
    "RequirementsInputs",
    "RunInputs",
    "SpecificationInputs",
    "load",
]
