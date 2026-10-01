"""The outcome extractor — TestOutcome records from run bundles.

Reads each run bundle the caller names and supplies a TestOutcome for every
test result the bundle's run artifact records (SEG-SREQ-176, SEG-SREQ-219). The
bundle is the only record of a run that is read. The artifact is the authority
on what a test did. The test-case export is the authority on which
specification a result belongs to. The implementation export, when it is
given, is the authority on which implementations a result witnesses.

A run bundle is a flat directory (see the architecture page). It holds the run
artifact ``twister.json``, the run's name in ``run.name``, the command in
``command.txt``, and for each checkout the run used a revision record
``<checkout>.sha`` and a dirty flag ``<checkout>.dirty``. Any other file of the
directory belongs to the bundle's identity and is not read.

The identity of a bundle is its digest (:func:`bundle_digest`), not its name
(SEG-SREQ-220). The extractor computes it and expects none: it is the
repository member of every outcome's anchor and the proof's record of the
bundle (SEG-SREQ-190). The checkout that decides is
the one the configuration names as the implementation checkout: its revision
record is the revision of every outcome of the run, and a run whose
implementation checkout was dirty is refused (SEG-SREQ-222, SEG-SREQ-186,
SEG-SREQ-187). The checks apply to every named bundle, whatever its revision. A bundle
named twice is read once (SEG-SREQ-232).

The one run format built is a JSON test report: an object with a
``testsuites`` list. Each suite names a scenario and a platform and lists its
test cases, each with a test identifier and a status. A pytest run is a second
format of the same component. It is not built.

An outcome's identity is ``<name>-<platform>-<scenario>/<specification>``. The
run identifier before the slash joins the run's name, the platform and the
scenario by hyphens. The platform has each slash replaced by a hyphen, so the
identity holds one slash. After the slash comes the identifier of the
test-case need that the result maps to (SEG-SREQ-177 to SEG-SREQ-179).

A result maps to a need when the scenario, the suite of the need and the test
function of the need without its ``test_`` prefix, joined by dots, equal the
result's test identifier. The extractor forms that identifier from each need
and compares it whole. It never splits a test identifier or an outcome
identity to recover its parts, because a scenario name can nest and so the
parts do not show where they end. A result that maps to no need, or to more
than one, is an error (SEG-SREQ-180, SEG-SREQ-181).

A status maps onto the closed result set by a fixed table. A status outside
the table is an error (SEG-SREQ-183, SEG-SREQ-184). A skipped result is
recorded as a skipped outcome (SEG-SREQ-185).

The name of the run is the operator's own and a run with no recorded name is
refused (SEG-SREQ-223). The recorded revision is the freshness mechanism: a
later step compares it with the current revision. The extractor only records
it. It runs no version-control command.

The content hash covers the specification identifier, the run identifier and
the result, and no other field of the artifact's record (SEG-SREQ-182). The
execution time and the reason of a result are not hashed, and neither are the
revision and the bundle's digest. Recomputing a hash needs the run's name and
the specification export as well as the artifact. The anchor names the
repository, the artifact's path in it and the locator ``nodeid:<test
identifier>`` (SEG-SREQ-190).

Every check that the inputs alone decide runs when the extractor is built, and
so does the mapping of every result. Two results that give one outcome identity,
in one run or in two, are refused and the message names both runs. The stream
that :meth:`nodes` and :meth:`edges` supply is therefore never short. An error
names the bundle, and for one result it names the result.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any

from affirmatrix import config
from affirmatrix._hashing import content_hash
from affirmatrix.records import ContentAnchor, EdgeRecord, LinkState, NodeRecord, TestResult
from affirmatrix.sources import SourceError, _exports

__all__ = ["OutcomeError", "TwisterOutcomeExtractor", "bundle_digest", "canonical_record"]

_TEST_OUTCOME = "TestOutcome"
_CONFIRMS = "Confirms"
_WITNESSES = "Witnesses"
_CONTENT_HASH = "contentHash"
_SPECIFICATION_LABEL = "test-case export"
_IMPLEMENTATION_LABEL = "implementation export"
_TEST_PREFIX = "test_"
_ARTIFACT_FILE = "twister.json"
_NAME_FILE = "run.name"
_REVISION_SUFFIX = ".sha"
_DIRTY_SUFFIX = ".dirty"
_DIGEST_PREFIX = "sha256:"

#: The statuses a run artifact records, and the member of the closed result set
#: each corresponds to (SEG-SREQ-183). A status not in this table has no
#: counterpart (SEG-SREQ-184).
_STATUSES = {
    "passed": TestResult.PASSED,
    "failed": TestResult.FAILED,
    "error": TestResult.ERROR,
    "skipped": TestResult.SKIPPED,
}


class OutcomeError(SourceError):
    """A run cannot be read as a record source.

    Raised when the extractor is built, for what the inputs show and for any
    one result. The message names the run and, for one result, the result.
    """


def canonical_record(specification: str, run: str, result: TestResult) -> bytes:
    """The canonical serialization of one outcome's content, as bytes.

    RFC 8785 canonical JSON, in UTF-8, of an object that holds the
    specification identifier, the run identifier and the result, and nothing
    else. The object is built from these three keys and is not filtered from
    the artifact's record, so no other field of that record can reach the hash.

    The standard library encoder produces RFC 8785's form for these value
    types. The three members are strings, so sorted keys (all ASCII, where
    code-point order and UTF-16 order agree), no insignificant whitespace,
    minimal string escaping and unescaped non-ASCII text (hence
    ``ensure_ascii=False``) are all that the standard asks for. RFC 8785's
    number rule never applies because no number is in the object. A number or
    an array joining the record would need this encoding revisited.

    :implements: SEG-SREQ-182
    """
    record = {"result": result.value, "run": run, "specification": specification}
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def bundle_digest(path: Path) -> str:
    """The digest of a run bundle: ``sha256:`` and the 64 hex digits of its file list.

    The list has one line for each regular file under ``path``: the SHA-256 of
    the file's bytes in lowercase hex, two blanks, the file's path relative to
    ``path`` with ``/`` as separator, and a line feed. The lines are in the
    byte order of the UTF-8 paths. The digest is the SHA-256 of all the lines.
    It changes with a byte, a name or a file, and with nothing else: not the
    order of the files on disk, the location of the bundle, a modification
    time or an empty directory. A link, a file that is neither regular nor a
    directory, an unreadable file, and a path with a backslash or a line feed
    are refused, because the shell recipe on the architecture page lists
    none of them as the tool does.

    :implements: SEG-SREQ-220
    """
    if not path.is_dir():
        raise OutcomeError(f"run bundle {path}: is not a directory")
    listed: list[tuple[bytes, str]] = []
    try:
        for entry in sorted(path.rglob("*")):
            name = entry.relative_to(path).as_posix()
            if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
                raise OutcomeError(f"run bundle {path}: {name!r} is a link or not a regular file")
            if entry.is_dir():
                continue
            if "\\" in name or "\n" in name:
                raise OutcomeError(
                    f"run bundle {path}: the path {name!r} holds a backslash or a line feed"
                )
            listed.append((name.encode("utf-8"), content_hash(entry.read_bytes()).hex()))
    except OSError as cause:
        raise OutcomeError(f"run bundle {path}: cannot be read: {cause}") from cause
    lines = "".join(f"{digest}  {name.decode('utf-8')}\n" for name, digest in sorted(listed))
    return _DIGEST_PREFIX + content_hash(lines.encode("utf-8")).hex()


def _named_once(bundles: Sequence[Path]) -> tuple[Path, ...]:
    """The bundles in the order named, each once.

    Two names for one directory (a link, a path that goes through another
    directory and back) are one bundle, and it is read once.

    :implements: SEG-SREQ-232
    """
    seen: dict[Path, Path] = {}
    for bundle in bundles:
        seen.setdefault(bundle.resolve(), bundle)
    return tuple(seen.values())


def _read_record(path: Path, what: str) -> str:
    """The one line that the record at ``path`` holds, without its line terminator.

    A missing or unreadable record, an empty one, one with more than one line
    and one with blanks around its text are all refused: a value that a
    stray blank or a second line can change is not a recorded value.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as cause:
        raise OutcomeError(f"{what} {path}: cannot be read: {cause}") from cause
    value = text.removesuffix("\n").removesuffix("\r")
    if not value.strip():
        raise OutcomeError(f"{what} {path}: is empty")
    if "\n" in value or "\r" in value:
        raise OutcomeError(f"{what} {path}: holds more than one line")
    if value != value.strip():
        raise OutcomeError(f"{what} {path}: has blanks around its text")
    return value


def _read_revision(path: Path) -> str:
    """The full revision recorded for a checkout, verbatim, or a refusal of the run.

    The extractor pins no length and no spelling: any one-line text is a
    revision. A run whose record is missing, empty or blank is refused, and
    none of its outcomes is supplied.

    :implements: SEG-SREQ-186
    :implements: SEG-SREQ-187
    """
    return _read_record(path, "revision record")


def _check_clean(path: Path, checkout: str) -> None:
    """Refuse a run whose implementation checkout was dirty.

    The dirty flag of a checkout is a file that is empty when the checkout was
    clean and holds the output of the status command when it was not. A flag
    that is missing is refused too: a bundle that says nothing about the
    implementation checkout does not show it clean.

    :implements: SEG-SREQ-222
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as cause:
        raise OutcomeError(f"dirty flag {path}: cannot be read: {cause}") from cause
    if text.strip():
        first = next(line for line in text.splitlines() if line.strip())
        raise OutcomeError(
            f"dirty flag {path}: the implementation checkout {checkout!r} was dirty "
            f"when the run was made: {first!r}"
        )


def _run_identifier(name: str, platform: str, scenario: str) -> str:
    """The run's name, the platform and the scenario, in that order, joined by hyphens.

    A slash of the platform becomes a hyphen, so no run identifier holds one.

    :implements: SEG-SREQ-178
    """
    return f"{name}-{platform.replace('/', '-')}-{scenario}"


def _identity(run_identifier: str, specification: str) -> str:
    """The outcome's local identifier: the run identifier, a slash, the need's identifier.

    The need's identifier is taken verbatim and never prefixed or re-cased.

    :implements: SEG-SREQ-177
    :implements: SEG-SREQ-179
    """
    return f"{run_identifier}/{specification}"


@dataclass(frozen=True, slots=True)
class _Outcome:
    """One result, mapped and hashed: what the two streams supply for it."""

    local_id: str
    specification: str
    result: TestResult
    revision: str
    anchor: ContentAnchor
    witnesses: tuple[str, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class _Specifications:
    """The test-case export's needs as (suite, test function, identifier) rows.

    Built once for the extractor. The test function is kept without its
    ``test_`` prefix, the form the test identifier holds.
    """

    rows: tuple[tuple[str, str, str], ...]
    verifies: Mapping[str, tuple[str, ...]]

    def formed(self, scenario: str) -> Mapping[str, list[str]]:
        """For a scenario, each identifier the needs form and the needs that form it.

        A result's identifier is compared whole with these keys. It is never
        split. Two needs with one suite and one test function share a key;
        that is ambiguous only for a result that reaches the key.

        :implements: SEG-SREQ-180
        """
        formed: dict[str, list[str]] = {}
        for suite, function, need_id in self.rows:
            formed.setdefault(f"{scenario}.{suite}.{function}", []).append(need_id)
        return formed


@dataclass(frozen=True, slots=True)
class TwisterOutcomeExtractor:
    """TestOutcome records from run bundles, with their Confirms and Witnesses edges.

    ``bundles`` are the run bundles, directories, in the order named; a bundle
    may lie anywhere. ``checkout`` is the
    name of the implementation checkout: the bundle's record of that checkout
    gives the revision and the dirty flag that decide. ``specifications``
    names the test-case export that maps each result to its need.
    ``implementations`` names the implementation export; when it is ``None``,
    no Witnesses edge is supplied. The Doxygen directory that each of the two
    input records names is not used here.

    The bundles and the exports are read and checked once, here, and every
    result is mapped here.

    :implements: SEG-SREQ-176
    :implements: SEG-SREQ-219
    """

    bundles: Sequence[Path]
    _: KW_ONLY
    checkout: str | None
    specifications: config.SpecificationInputs
    implementations: config.ImplementationInputs | None
    _outcomes: tuple[_Outcome, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Read and check every input, then map every result, refusing what cannot serve."""
        specifications = self._read_specifications()
        implementers = self._read_implementers()
        outcomes: list[_Outcome] = []
        supplied_by: dict[str, Path] = {}
        named = _named_once(self.bundles)
        for bundle in named:
            for outcome in self._read_run(bundle, specifications, implementers):
                if outcome.local_id in supplied_by:
                    raise OutcomeError(
                        f"run bundle {bundle}: the outcome identity {outcome.local_id!r} "
                        f"is already supplied by the run bundle {supplied_by[outcome.local_id]}"
                    )
                supplied_by[outcome.local_id] = bundle
                outcomes.append(outcome)
        object.__setattr__(self, "bundles", named)
        object.__setattr__(self, "_outcomes", tuple(outcomes))

    def _read_specifications(self) -> _Specifications:
        """The test-case export's needs, checked and indexed for the mapping."""
        export = self.specifications.export
        needs = _exports.read_needs(export, _SPECIFICATION_LABEL, OutcomeError)
        rows = []
        verifies = {}
        for key, need in needs.items():
            _exports.check_need(
                export,
                _SPECIFICATION_LABEL,
                OutcomeError,
                key,
                need,
                ("id", "suite", "test_function"),
                "verifies",
            )
            if not need["suite"] or not need["test_function"]:
                raise OutcomeError(
                    f"{_SPECIFICATION_LABEL} {export}: need {key!r} has an empty suite "
                    "or an empty test function"
                )
            rows.append((need["suite"], need["test_function"].removeprefix(_TEST_PREFIX), key))
            verifies[key] = tuple(need.get("verifies") or [])
        return _Specifications(rows=tuple(rows), verifies=verifies)

    def _read_implementers(self) -> Mapping[str, tuple[str, ...]]:
        """For each requirement an implementation need satisfies, the needs that satisfy it.

        Empty when no implementation export is given.
        """
        if self.implementations is None:
            return {}
        export = self.implementations.export
        needs = _exports.read_needs(export, _IMPLEMENTATION_LABEL, OutcomeError)
        implementers: dict[str, list[str]] = {}
        for key, need in needs.items():
            _exports.check_need(
                export, _IMPLEMENTATION_LABEL, OutcomeError, key, need, ("id",), "satisfies"
            )
            for requirement in need.get("satisfies") or []:
                implementers.setdefault(requirement, []).append(key)
        return {requirement: tuple(keys) for requirement, keys in implementers.items()}

    def _read_run(
        self,
        bundle: Path,
        specifications: _Specifications,
        implementers: Mapping[str, tuple[str, ...]],
    ) -> Iterator[_Outcome]:
        """Every result of one run, mapped and hashed, in artifact order.

        The checks come first and apply to every bundle: the digest, then the
        implementation checkout's dirty flag and revision, then the name.
        """
        actual = bundle_digest(bundle)
        checkout = self._checkout_name()
        revision = _read_revision(bundle / f"{checkout}{_REVISION_SUFFIX}")
        _check_clean(bundle / f"{checkout}{_DIRTY_SUFFIX}", checkout)
        name = _read_record(bundle / _NAME_FILE, "name record")
        if "/" in name:
            raise OutcomeError(
                f"name record {bundle / _NAME_FILE}: the name {name!r} holds a slash"
            )
        artifact = bundle / _ARTIFACT_FILE
        for suite in self._read_suites(artifact):
            scenario, platform = suite["name"], suite["platform"]
            identifiers = specifications.formed(scenario)
            run_identifier = _run_identifier(name, platform, scenario)
            for case in suite["testcases"]:
                identifier, status = case["identifier"], case["status"]
                result = self._result(artifact, identifier, status)
                specification = self._specification(
                    artifact, identifier, identifiers.get(identifier, [])
                )
                yield _Outcome(
                    local_id=_identity(run_identifier, specification),
                    specification=specification,
                    result=result,
                    revision=revision,
                    anchor=self._anchor(actual, identifier, specification, run_identifier, result),
                    witnesses=self._witnesses(specifications, implementers, specification),
                    digest=actual,
                )

    def _checkout_name(self) -> str:
        """The name of the implementation checkout, which must be one file-name stem."""
        name = self.checkout
        if not name:
            raise OutcomeError(
                "no implementation checkout is configured; the revision of a run is the "
                "revision its bundle records for that checkout"
            )
        if Path(name).name != name or name in {".", ".."}:
            raise OutcomeError(f"the implementation checkout {name!r} is not a plain name")
        return name

    @staticmethod
    def _read_suites(artifact: Path) -> list[Mapping[str, Any]]:
        """The suites of a run artifact, each checked to carry what the extractor reads."""
        try:
            document = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError) as cause:
            raise OutcomeError(f"run artifact {artifact}: cannot be read: {cause}") from cause
        suites = document.get("testsuites") if isinstance(document, dict) else None
        if not isinstance(suites, list):
            raise OutcomeError(f"run artifact {artifact}: has no 'testsuites' list")
        for suite in suites:
            if not isinstance(suite, dict) or not isinstance(suite.get("testcases"), list):
                raise OutcomeError(f"run artifact {artifact}: a suite has no 'testcases' list")
            for field_name in ("name", "platform"):
                if not isinstance(suite.get(field_name), str) or not suite[field_name]:
                    raise OutcomeError(
                        f"run artifact {artifact}: a suite has no text field {field_name!r}"
                    )
            for case in suite["testcases"]:
                if not isinstance(case, dict) or not isinstance(case.get("identifier"), str):
                    raise OutcomeError(
                        f"run artifact {artifact}: a result of the suite {suite['name']!r} "
                        "has no text field 'identifier'"
                    )
        return suites

    @staticmethod
    def _result(artifact: Path, identifier: str, status: object) -> TestResult:
        """The member of the closed result set that ``status`` corresponds to.

        :implements: SEG-SREQ-183
        :implements: SEG-SREQ-184
        """
        if not isinstance(status, str) or status not in _STATUSES:
            raise OutcomeError(
                f"run artifact {artifact}: the result {identifier!r} has the status {status!r}; "
                f"no result of the closed set corresponds to it (known: {', '.join(_STATUSES)})"
            )
        return _STATUSES[status]

    @staticmethod
    def _specification(artifact: Path, identifier: str, candidates: list[str]) -> str:
        """The one need that forms ``identifier``; no need and several needs are refused.

        :implements: SEG-SREQ-181
        """
        if not candidates:
            raise OutcomeError(
                f"run artifact {artifact}: the result {identifier!r} maps to no test-case need"
            )
        if len(candidates) > 1:
            raise OutcomeError(
                f"run artifact {artifact}: the result {identifier!r} maps to "
                f"{len(candidates)} test-case needs ({', '.join(map(repr, candidates))})"
            )
        return candidates[0]

    @staticmethod
    def _witnesses(
        specifications: _Specifications,
        implementers: Mapping[str, tuple[str, ...]],
        specification: str,
    ) -> tuple[str, ...]:
        """The implementation needs that satisfy a requirement ``specification`` verifies.

        Each is named once, in the order of the requirements the need verifies,
        then in the order of the export.
        """
        found: dict[str, None] = {}
        for requirement in specifications.verifies[specification]:
            for implementation in implementers.get(requirement, ()):
                found[implementation] = None
        return tuple(found)

    def _anchor(
        self,
        bundle_digest_text: str,
        identifier: str,
        specification: str,
        run_identifier: str,
        result: TestResult,
    ) -> ContentAnchor:
        """The content hash of one outcome, anchored at the run artifact and the result.

        The repository member is the digest of the bundle, ``sha256:`` and 64
        hex digits, wherever the bundle lies. The path is the run artifact
        within the bundle. The locator is ``nodeid:`` and the result's test
        identifier.

        :implements: SEG-SREQ-190
        :implements: SEG-SREQ-134
        """
        return ContentAnchor(
            digest=content_hash(canonical_record(specification, run_identifier, result)),
            repository=bundle_digest_text,
            path=_ARTIFACT_FILE,
            locator=f"nodeid:{identifier}",
        )

    def evidence_bundles(self) -> Mapping[str, str]:
        """For each outcome's local identifier, the digest of the bundle that supplied it.

        :implements: SEG-SREQ-226
        """
        return {outcome.local_id: outcome.digest for outcome in self._outcomes}

    def nodes(self) -> Iterator[NodeRecord]:
        """A TestOutcome record per result, in the order of the runs and of each artifact.

        The result is the one the status maps to, and a skipped result is
        recorded like any other. The revision is the one the bundle records for the
        implementation checkout.

        :implements: SEG-SREQ-185
        """
        for outcome in self._outcomes:
            yield NodeRecord(
                local_id=outcome.local_id,
                kind=_TEST_OUTCOME,
                content_anchors={_CONTENT_HASH: outcome.anchor},
                result=outcome.result,
                revision=outcome.revision,
            )

    def edges(self) -> Iterator[EdgeRecord]:
        """Pending edges: a Confirms edge per outcome, and its Witnesses edges.

        A Confirms edge runs from the outcome to its test-case need. A Witnesses
        edge runs from the outcome to each implementation need that satisfies a
        requirement the test-case need verifies. A skipped outcome has them too.
        With no implementation export, no Witnesses edge is supplied. Needs no
        artifact and cannot fail: the inputs were checked at construction.

        :implements: SEG-SREQ-188
        :implements: SEG-SREQ-189
        """
        for outcome in self._outcomes:
            yield EdgeRecord(outcome.local_id, outcome.specification, _CONFIRMS, LinkState.PENDING)
            for implementation in outcome.witnesses:
                yield EdgeRecord(outcome.local_id, implementation, _WITNESSES, LinkState.PENDING)
