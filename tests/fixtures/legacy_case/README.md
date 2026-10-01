# The legacy case

A small case as the tool wrote it **while it still stored test evidence**.
It holds test outcome nodes and Confirms and Witnesses edges, all `pending`,
beside the strong edges, six review events and one stored proof. Tests copy it
to a temporary directory, run `case sync` and other verbs on the copy, and
check the result. Nothing writes this directory.

**Never regenerate it with newer code.** The tool no longer writes test
evidence into a case, so newer code cannot make this shape. A regenerated copy
would test nothing.

## What it holds

| Part | Content |
|---|---|
| `case/schema/` | The 18 packaged schemas, byte for byte as the tool wrote them |
| `case/context.jsonld` | The packaged context |
| `case/nodes/` | 3 requirements, 5 test specifications, 3 implementations, **10 test outcomes** |
| `case/edges/` | 32 edges: 2 Refines, 5 Verifies, 3 Implements, **10 Confirms, 12 Witnesses** |
| `case/events/` | 6 review events |
| `case/proofs/` | 1 evidence package for the scope `FX-SREQ-1` (four documents, no run bundle digest) |
| `stream/` | The would-be store the case was synced from. It holds the outcomes too. |

State of the edges:

- All 10 Confirms and 12 Witnesses edges are `pending`.
- Six strong edges are affirmed and `active`, each with its hash and a review
  event: Verifies `FX-TS-1`, `FX-TS-2`, `FX-TS-3` to `FX-SREQ-1`; Implements
  `fixture.f1`, `fixture.f2` to `FX-SREQ-1`; Refines `FX-SREQ-1` to `FX-SYS-1`.
- Four strong edges are `pending`: Verifies `FX-TS-4`, `FX-TS-5`; Implements
  `fixture.f3`; Refines `FX-SREQ-2`.
- The outcomes of `run-1` record the revision `fixture-rev-1`. The outcomes of
  `run-2` record `fixture-rev-2`.
- The stored package was generated with the revision `fixture-rev-2`. Its
  evidence manifest has no field for run bundles.

## The affirmations are test data

Every affirmation and review event is synthetic. The reviewer role is
`fixture-reviewer`. The recorded revisions (`0123…4567`) are not a real
commit. The affirmations bind nothing. They exist so that tests can check
that a sync leaves affirmed edges, review events and proofs alone.

This fixture was never made from the repository's own `case/` directory, and
no record in it comes from there. The identifiers (`FX-…`) and all content are
invented for the fixture.

## How it was made

Base: commit `12a1a6e` (its code is the code of `fe47355`, the last commit
that changed the sources). The stream was written by a short script as plain
TOML and text files. Then, from the directory that holds `case/` and `stream/`:

```
affirmatrix case init --case case
affirmatrix case sync --case case --current stream
affirmatrix edge affirm --case case --current stream --kind Verifies \
    --from FX-TS-1 --to FX-SREQ-1 --role fixture-reviewer \
    --reason "synthetic fixture affirmation; it binds nothing" \
    --revision 0123456789abcdef0123456789abcdef01234567
```

The same `edge affirm` command ran for the other five edges named above. The
stored package then came from:

```
affirmatrix proof generate --case case --current stream --scope FX-SREQ-1 \
    --revision fixture-rev-2 --timestamp 2026-10-01T00:00:00+00:00 \
    --evaluation-date 2026-10-01
```

The case records the stream's location as the relative path `stream/content`.
Keep the two directories side by side, as they are here.
