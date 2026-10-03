"""Schema validation, against the copy of the schemas the case itself carries.

The store validates every entry before writing it (SEG-SREQ-019), and it
validates against ``{root}/schema/`` — the same files an auditor reads — rather
than against the copy inside the installed package. Tool and auditor then agree
by construction. The packaged copy seeds a case that has none yet and is never
written over one that does: replacing a case's schemas would be a store act,
and the tool takes none unbidden.

The schemas are read at the moment of the write, not cached for the process.
A case's schema directory is data on disk that anything may have changed since
the last write, and a validator held over from an earlier one would be judging
records against rules the case no longer states.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from affirmatrix.case._errors import AffirmationStoreError

_SCHEMA_GLOB = "*.json"


@dataclass(frozen=True, slots=True)
class SchemaSet:
    """The schemas one case declares, ready to validate against.

    The registry resolves the cross-file references the edge schemas compose
    by, from this set alone. Nothing reaches the network to validate a record:
    a case must be checkable by someone who has only the case.
    """

    directory: Path
    registry: Registry
    schemas: Mapping[str, Mapping[str, object]]

    def validator(self, schema_name: str) -> Draft202012Validator:
        """The validator for one schema, by file name."""
        try:
            schema = self.schemas[schema_name]
        except KeyError:
            raise AffirmationStoreError(
                f"the case at {self.directory} declares no schema {schema_name!r}, "
                "so a record of that kind cannot be shown to be valid"
            ) from None
        return Draft202012Validator(schema, registry=self.registry)


def load(directory: Path) -> SchemaSet:
    """Read a case's schema directory.

    A schema that is present but unreadable raises. Skipping it would leave the
    store validating against a smaller set than the case advertises, which is
    the one outcome worse than refusing to write at all.
    """
    schemas: dict[str, Mapping[str, object]] = {}
    registry: Registry = Registry()
    for path in sorted(directory.glob(_SCHEMA_GLOB)):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AffirmationStoreError(f"{path} cannot be read as a schema: {error}") from error
        if not isinstance(document, dict):
            raise AffirmationStoreError(f"{path} is not a schema: it is not an object")
        schemas[path.name] = document
        resource = Resource.from_contents(document, default_specification=DRAFT202012)
        registry = registry.with_resource(str(document.get("$id", path.name)), resource)
    return SchemaSet(directory=directory, registry=registry, schemas=MappingProxyType(schemas))


def validate_entry(
    schema_set: SchemaSet, entry: Mapping[str, object], schema_name: str, label: str
) -> None:
    """Refuse ``entry`` unless it validates against the named schema.

    :implements: SEG-SREQ-019
    :implements: SEG-SREQ-325

    Reports the first violation in document order, naming the record and the
    field. A refusal that named only the schema would leave the operator to
    find which record of a batch was wrong, and a batch is the usual size of a
    write.
    """
    errors = sorted(schema_set.validator(schema_name).iter_errors(entry), key=_position)
    if not errors:
        return
    first = errors[0]
    where = f" at {first.json_path}" if first.json_path != "$" else ""
    raise AffirmationStoreError(
        f"{label} does not validate against {schema_name}{where}: {first.message}"
    )


def _position(error: object) -> tuple[int, str]:
    """Order violations by depth, so the outermost one is reported first."""
    path = getattr(error, "json_path", "$")
    return len(path.split(".")), path


__all__ = ["SchemaSet", "load", "validate_entry"]
