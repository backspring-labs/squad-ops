# Framework-smoke corpus

`cyc_02682aa4efa2/artifact_refs.json` — the 14 artifact references a real cycle stored,
copied verbatim from the deployment vault
(`data/artifacts/play_game/cyc_02682aa4efa2/run_19bf26169588/*/metadata.json`).

It is the cycle #176 documents: `lite`/7b, `builder-assemble`, `play_game`, 2026-06-14.
The run ended **FAILED** — a 7b builder under-produced (194 completion tokens) and the
output validator correctly rejected it — and **every framework invariant held anyway**.
That is exactly why it is the corpus: it is the case the smoke assertions must call PASS,
and a harness keyed on terminal status calls it FAIL.

Captured rather than read live because the vault is a live directory that gets pruned, and
a test that silently skips when its corpus is absent is a test that has gone vacuous.
Refs only — no artifact bodies; the invariants are about what was produced, by whom, not
about content.
