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
| `1-6-5-react-roll-3-round-0-test_report.md` | `cyc_184b3a1d194e` / `art_a34a7bb3973b`, `task-run_da1156df-m005-qa.test` at 2026-08-27 05:26:55Z | the pytest report whose three `TestClient.delete(json=…)` TypeErrors were raised in the suite's own frame and sent to the dev chain 3/3 rounds — the roll that cost #1130 |
| `1-6-6-react-roll-6-round-0-test_report.md` | `cyc_0c4664c2ae9a` / `art_0b00eb45585f`, `task-run_5ebd18b7-m004-qa.test` at 2026-08-28 00:49:43Z | nine failures whose innermost frame is `backend/routes.py` (`uuid.uuid4().str`) — the app raised; the routing control. Its rootdir sat below the workspace, so pytest printed `tests/test_runs.py` |
| `1-6-6-react-roll-6-assert-test_report.md` | `cyc_0c4664c2ae9a` / `art_dad9f441800c`, `retest-run_5ebd18b7-00-qa.test` at 00:52:23Z | one rewritten `assert 200 == 409` — an assertion is the suite judging the app; control |
| `collection-error-cyc_1d2e21ab0cfb-test_report.md` | `cyc_1d2e21ab0cfb` / `art_a48dcb4569ba`, `run_766248665eb5` at 2026-07-01 20:08:19Z | `ERROR collecting backend/tests/test_api.py` — `ModuleNotFoundError: No module named 'main'`, an import the app should satisfy; stays ambiguous (the pf-35 lesson); control |
