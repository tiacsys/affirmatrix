# Golden evidence results

What the tool decided over the evidence of `../toolbox_evidence/`, as the code
decided it **before** test evidence came from run bundles. Tests compare the
results of newer code with these files. **Never regenerate them with newer
code.** A regenerated golden would agree with whatever the code does.

## How they were made

Base: commit `12a1a6e` (its sources are the sources of `fe47355`). The run was
read through the old configuration keys (`artifact`, `revision`, `name`) from
`../toolbox_evidence/twister/` and `../toolbox_evidence/revisions/`. In
`two_runs/` a second run reads the same artifact with the revision
`1111111111111111111111111111111111111111` and the name `twister-run-second`.
All other inputs are the exports and Doxygen output of `../toolbox_evidence/`.

From an empty directory, with a configuration `affirmatrix.yaml` for those
inputs (`<R>` is `5847f3fdca777b8d62615d84b8926fdc8ce125ed`):

```
affirmatrix case init --case case
affirmatrix case sync --case case
affirmatrix edge affirm --case case --kind Refines    --role fixture-reviewer --reason "synthetic golden affirmation" --revision <R>
affirmatrix edge affirm --case case --kind Verifies   --role fixture-reviewer --reason "synthetic golden affirmation" --revision <R>
affirmatrix edge affirm --case case --kind Implements --role fixture-reviewer --reason "synthetic golden affirmation" --revision <R>
affirmatrix proof check    --case case --revision <R> --scope SD-TOP-001 --scope SD-TOP-003 --json > gate_report.json
affirmatrix proof generate --case case --revision <R> --scope SD-TOP-001 --scope SD-TOP-003 \
    --timestamp 2026-10-01T00:00:00+00:00 --evaluation-date 2026-10-01 --output-dir out
```

`leaf_verdicts.json` came from a short script over the library: the graph built
from the case and the configured producer, then the satisfaction verdict of
every requirement and the outcomes the evaluator set aside. Two runs from empty
directories gave identical bytes.

The affirmations are synthetic test data. They bind nothing.

## What is here

| Path | Content |
|---|---|
| `design_root.txt` | the design root of the package (the same in both arms) |
| `one_run/` | one run bundle's worth of evidence |
| `two_runs/` | the same, plus a second run at another revision (24 outcomes set aside as stale in scope) |
| `*/gate_report.json` | the gate's coverage report for the scope |
| `*/leaf_verdicts.json` | each requirement's verdict (18 of 29 satisfied) |
| `*/proofs/<snapshot>/` | the four documents of the evidence package |

The scope `SD-TOP-001` and `SD-TOP-003` holds two top requirements, six
requirements, six test specifications, four implementations and, per run, 24
test outcomes (three of them skipped). The outcomes are in the package's member
scope. The design root is still the same in both arms: evidence stays out of the
root.

## How tests compare

- Files that hold the design or the verdict as bytes (`design_consistency_proof`,
  `coverage_report`, `execution_coverage_record`): byte for byte.
- The gate report and the leaf verdicts: as parsed JSON.
- The evidence manifest: as parsed JSON. It has every field of the golden with
  the same value, and one more field that lists the digests of the run bundles
  used.
