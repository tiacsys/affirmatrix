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
    (every role accepted).
    """

    case: Path = DEFAULT_CASE
    producer_root: Path | None = None
    repositories: Mapping[str, Path] = field(default_factory=dict)
    implementation: str | None = None
    roles: frozenset[str] | None = None

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

    ``path`` is the file to read, defaulting to :data:`DEFAULT_CONFIG_PATH`
    when not given; while that file does not exist, every parameter this
    loader carries defaults rather than the load refusing — the case root to
    :data:`DEFAULT_CASE`, everything else to absent. ``case``, when given, is
    the caller's own value (the command line's ``--case``) and is preferred
    over the file's — the loader's keyword parameter is where a caller's
    override enters; a future flag overriding another field is the same
    shape, not a new mechanism. Raises :class:`ConfigError` for a file that
    exists but cannot be made sense of — never for one that is merely absent.
    """
    values = _read_file(path if path is not None else DEFAULT_CONFIG_PATH)
    return Config(
        case=case if case is not None else Path(_string(values, "case", str(DEFAULT_CASE))),
        producer_root=_producer_root(values),
        repositories=_repositories(values),
        implementation=_optional_string(values, "implementation"),
        roles=_roles(values),
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


def _producer_root(values: Mapping[str, object]) -> Path | None:
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
    return Path(root)


def _repositories(values: Mapping[str, object]) -> dict[str, Path]:
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
        result[name] = Path(path)
    return result


def _roles(values: Mapping[str, object]) -> frozenset[str] | None:
    roles = values.get("roles")
    if roles is None:
        return None
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ConfigError("'roles' must be a list of strings")
    return frozenset(roles)


__all__ = ["Config", "ConfigError", "DEFAULT_CASE", "DEFAULT_CONFIG_PATH", "load"]
