# Roll replays

Real emissions, copied byte-for-byte from the artifact vault, that a check is replayed
against before any new roll (`feedback: validate against real emissions`). Each file names
the roll it came from; the test that uses it names the defect it reproduces.

| file | cycle / artifact | what it is |
|---|---|---|
| `1-7-0-roll-4-fill-with-undeclared-name.scaffold.test.ts` | `cyc_58d92ca2b407` / `art_0e4eaa25d42d`, written by `repair-run_1a5833f6-00-qa.test_repair` at 2026-09-01 14:18:25Z | the scaffold shell whose fill slot used `created` without declaring it (line 30); it reached vitest and failed `ReferenceError: created is not defined` — the roll that cost #939 |
| `1-7-0-roll-6-green.scaffold.test.ts` | `cyc_2a88dabad94b` / `art_5ad70b6aacb9`, the gating roll's `qa.test` at 22:09:04Z | the same shell from the accepted roll, every name declared — the over-rejection control |
| `1-6-6-react-roll-3-backend-suite.py.txt` + `-interface_manifest.yaml` | `cyc_38d1e1689766` / `art_a286d9fe5c81` (the first qa emission, 21:55Z) and the run's manifest | the suite that asserted `body["removed"] == "Carol"` against `LeaveResult.removed: boolean` (line 167) — the roll that cost #1153. `.py.txt` so it is neither collected nor linted |
| `1-6-6-react-roll-1-backend-suite.py.txt` + `-interface_manifest.yaml` | `cyc_cdf91361702b` / `art_5343ab679c99` and its manifest | an accepted roll's suite — the assertion-kind gate's over-rejection control |
| `1-6-6-react-roll-5-backend-suite.py.txt` + `-interface_manifest.yaml` | `cyc_ae0631fddfc5` / the `qa.test` emission in `run_17bb82d60d1a` and its manifest | the second control |
| `1-7-0-1221-repair-00-app-api-runs-route.ts` | `cyc_05abfc7c1f00` / `art_e71d58a6e45c`, `repair-run_09b00c7c-00-development.correction_repair` | the first repair patch of the cycle #1221 was filed from — the #1229 verification replay |
