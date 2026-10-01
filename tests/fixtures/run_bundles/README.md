# Run bundles

One run bundle, copied from the frozen evidence fixture `../toolbox_evidence/`
(`twister/` and `revisions/`, put together in one directory). A bundle holds
the test report of one run, the revision and the dirty flag of each checkout the
run used, the run name and the command.

Nothing here is edited. Tests copy the bundle to a temporary directory and
change the copy to make every other variant (a dirty checkout, no name, no
report, another revision, a changed byte).

## `clean/`

| File | Content |
|---|---|
| `twister.json` | the run artifact: 76 results (65 passed, 11 skipped) |
| `testplan.json`, `twister_report.xml`, `twister_suite_report.xml` | other report files of the run |
| `command.txt` | the command of the run (provenance only) |
| `run.name` | `twister-run-2026-09-29` |
| `toolbox.sha` | `5847f3fdca777b8d62615d84b8926fdc8ce125ed` |
| `toolbox.dirty` | empty: clean |
| `zephyr.sha` | `77e25d8f3cb2e94adb5a44426b98e088f1bef3fe` |
| `zephyr.dirty` | empty: clean |
| `zdocs.sha` | `c079fb698cbca48d7b0fd633d4c50fba850f08bc` |

11 files, 54 854 bytes. Every file counts toward the digest.

## The digest

```
sha256:f960023c5eacbe8c4a2fc2867d4d78c38bede4c02b1df6ac150f5804c8ca0043
```

Made from the bundle directory with the recipe of the architecture page:

```
find . -type f -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum
```

(The same recipe over the five files of `../toolbox_evidence/twister/` gives
`0302a755…e0ce`. That checked the recipe before the bundle was made.)

A bundle's digest changes with a file's bytes, a file's name or a new file. It
does not change with the order of the files on disk, the location of the bundle
or the modification times.
