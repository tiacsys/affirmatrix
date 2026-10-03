# Source

Copied 2026-10-03 from https://github.com/moeru-ai/airi/tree/main/.agents/skills/simple-english
(MIT, see LICENSE). Version 1.0.0, ASD-STE100 Issue 9. Unchanged. Update by
copying the upstream files again.

# How this repository applies it

This directory is a port of that copy. SKILL.md, LICENSE and references/ are
the upstream files, unchanged.

- Mode: **pragmatic**. The terms of the tool (affirm, witness, refines, case,
  store act, gate, anchor, need) are technical nouns and verbs. Keep them.
- Scope: the prose of the documentation pages, docstrings, commit messages
  and the docstrings of tests.
- Precedence: **inside a requirement statement, the EARS pattern wins
  completely.** The binding verb is `shall`. Never rewrite it to `must` or to
  an imperative. The pattern keywords `While`, `When`, `Where` and `If … then`
  stay. EARS also gives `should`, `would`, `will` and `may` their own
  meaning, so the modal rule of simple-english (3.x) does not apply to
  requirement text. Simple-english applies to the prose around the
  requirements: page introductions, rationale and notes. Code follows the
  python-patterns skill. Quoted text, identifiers, commands and error text
  stay as they are (Untouchables).
- Run the self-check before you deliver.
