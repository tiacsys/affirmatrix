# The toolbox evidence fixture

Frozen exports of the safety-toolbox project's documentation build, and of one
test run of its suite: the real inputs the evidence-graph readers are written
against. Where the would-be store (`../would_be_store/`) is hand-written
scaffolding, this is what a producer's tooling actually emits — sphinx-needs
exports, Doxygen XML, a twister report — so the requirements reader, the content
extractor and the outcome extractor can each be exercised on real bytes. The
toolbox is small enough to read in full, which is what makes it a unit-test
fixture rather than a scale test.

Nothing here is edited or regenerated. The directory is copied whole from a
frozen bundle; only this README is the repository's own. Every other file is
listed in `SHA256SUMS`, and `sha256sum -c SHA256SUMS` from this directory checks
them. A different freeze is a new directory, not a change to this one.

## Where it comes from

| Input | Revision |
|---|---|
| safety-toolbox (branch `zdocs-demo`) | `5847f3fdca777b8d62615d84b8926fdc8ce125ed`, tree clean |
| zephyr | `77e25d8f3cb2e94adb5a44426b98e088f1bef3fe`, tree clean |
| zdocs engine | `c079fb698cbca48d7b0fd633d4c50fba850f08bc` |

Toolchain: Sphinx 9.1.0, sphinx-needs 8.3.0 (`needs_reproducible_json` on),
Doxygen 1.16.1.

## Layout

```
needs/<document>/needs.json       sphinx-needs export, one per Sphinx document
needs/requirement-specification/needs.tag
                                  the requirements as a Doxygen tag file
needs/needs_config.toml           the shared sphinx-needs vocabulary (types, links, fields)
needs/documents.yaml              which document emits what
xml/dox-safe-data-api/            Doxygen XML of include/ and src/
xml/dox-safe-data-testspec/       Doxygen XML of tests/safe_data/src/main.c
twister/                          twister.json, twister_report.xml,
                                  twister_suite_report.xml, testplan.json, command.txt
revisions/                        toolbox.sha, toolbox.dirty, zephyr.sha, zephyr.dirty,
                                  zdocs.sha, run.name
sources/<repo-relative path>      the toolbox's own files, verbatim, at the revision above
SHA256SUMS
```

## The run record

A run is recorded beside its artifact, one value per file, one line each,
LF-terminated: the full revision of each checkout (`*.sha`), that checkout's
`git status --porcelain` output (`*.dirty`, empty for a clean tree), and the
run's own name (`run.name`). The name is the operator's choice, stable and
unique per run, and never a configured value: it becomes part of every
outcome's identity, `<name>-<platform>-<scenario>/<spec>`. Here it is
`twister-run-2026-09-29`, the tag placed on the run's commit.

## The sources rule

`sources/` holds every real file that a Doxygen `<location file=…>` or
`bodyfile=…` attribute names, each written verbatim with
`git show <revision>:<path>` — no reformatting, no line-ending change. That is
the three span sources (`include/safe_data/safe_data.h`, `src/safe_data.c`,
`tests/safe_data/src/main.c`) and four further files the XML locates
(`README.md`, `doc/dox/safe-data-api/groups.dox`,
`doc/dox/safe-data-testspec/groups.dox`, `doc/dox/safe-data-testspec/mainpage.md`).
The five other `<location file>` values (`kconfig_depends`, `testids`,
`test_active`, `test_draft`, `test_obsolete`) are Doxygen `xrefitem`
pseudo-files, not paths. The `.rst` requirement sources are not included: a
Requirement's canonical form is the per-need content of its export.

## Contents

| Export | Needs | Status | Links out |
|---|---|---|---|
| `requirement-specification` | 29 requirements: 7 `top_requirement` + 22 `requirement` (each `refines` a top requirement) | 29 approved | `refines` |
| `test-specification` | 19 `test_case` | 17 active, 1 draft, 1 obsolete | 24 `verifies` |
| `test-report` | 76 `test_result` | 65 passed, 11 skipped | `result_of`, `covers` |
| `api-traceability` | 12 `impl` | | 16 `satisfies`, two of them on macros |

The run is four scenarios of 19 tests on `native_sim/native/64`: 65 passed, 11
skipped, none failed. Skips follow the build configuration; a skipped result's
`reason` and its test case's `depends_on` say which option was missing.

## Reproducibility

- The exports carry no `created` stamps (every `created_at` is `null`), and the
  `version` key embeds the short commit.
- `<location>` paths in the Doxygen XML are repository-relative and name the
  three source files above, with `line`, `column`, `bodyfile`, `bodystart` and
  `bodyend`.
- Absolute build paths occur only in `Doxyfile.xml` and in the `external=`
  attributes of the tag-file cross-references; those are the only bytes that
  differ between two fresh builds.
- The four `needs.json` files are byte-identical over two fresh builds:

```
0aec8b9eed222530b13dabd6dbcd7ca86e0dfb9b0ef85e59384e3117a9a2213f  needs/requirement-specification/needs.json
2dd511715645c3b7c75d527d6066a6192edd24c19fd86ef946128993555f1c0f  needs/test-specification/needs.json
1d1749351f7a83680bb454688d861d956df9e38b0793791af6cdf1cafc43bdea  needs/test-report/needs.json
355f2a318b0688c91e5b9e0ddf14c6bbf4e92383d26b4ebdf5062942e07e9e64  needs/api-traceability/needs.json
```

## Recipes

Placeholders in angle brackets stand for local checkouts and output
directories.

The test run, from a west workspace that contains zephyr and the toolbox's
module wiring:

```
west twister -T <toolbox>/tests -p native_sim/native/64 -O <twister out>
git -C <toolbox> rev-parse HEAD     > <twister out>/toolbox.sha
git -C <toolbox> status --porcelain > <twister out>/toolbox.dirty
git -C <zephyr>  rev-parse HEAD     > <twister out>/zephyr.sha
git -C <zephyr>  status --porcelain > <twister out>/zephyr.dirty
git -C <zdocs>   rev-parse HEAD     > <twister out>/zdocs.sha
printf '<run name>\n'               > <twister out>/run.name
```

The documentation build (stage two is all-or-nothing, so `doc-index` runs
first):

```
cmake -S <toolbox>/doc -B <build> \
  -DEXTRA_ZEPHYR_MODULES=<zdocs> \
  -DZDOCS_TWISTER_OUT=<twister out> \
  -DZEPHYR_BASE=<zephyr>
cmake --build <build> --target doc-index
cmake --build <build> --target all-docs
cmake --build <build> --target doc-check
# exports: <build>/deploy/html/<document>/needs.json
# XML:     <build>/deploy/xml/<doxygen document>/
```

Both builds this fixture was checked against exited 0 with no Sphinx or Doxygen
warnings.
