# Roll replays

Real emissions, copied byte-for-byte from the artifact vault, that a check is replayed
against before any new roll (`feedback: validate against real emissions`). Each file names
the roll it came from; the test that uses it names the defect it reproduces.

| file | cycle / artifact | what it is |
|---|---|---|
| `1-7-0-roll-4-fill-with-undeclared-name.scaffold.test.ts` | `cyc_58d92ca2b407` / `art_0e4eaa25d42d`, written by `repair-run_1a5833f6-00-qa.test_repair` at 2026-09-01 14:18:25Z | the scaffold shell whose fill slot used `created` without declaring it (line 30); it reached vitest and failed `ReferenceError: created is not defined` — the roll that cost #939 |
| `1-7-0-roll-6-green.scaffold.test.ts` | `cyc_2a88dabad94b` / `art_5ad70b6aacb9`, the gating roll's `qa.test` at 22:09:04Z | the same shell from the accepted roll, every name declared — the over-rejection control |
