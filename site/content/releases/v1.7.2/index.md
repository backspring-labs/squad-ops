---
title: v1.7.2
---

# v1.7.2

**Released 2026-09-06** · [tag `v1.7.2`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.7.2)

**Loop Honesty — the second patch line of 1.7.** Plan: `docs/plans/1-7-2-plan.md`. Record:
`docs/plans/1-7-2-verification-set-record.md`.

Validated by a pre-registered two-set verification run on frozen deploy `d95af712` (HEAD pinned
at `b5e8fe12`), **zero code drift between the deploy and the tag** — the tag adds only the record
and this release commit: **FastAPI+React 5 of 6 functional** and **Next.js+TS 3 of 3**. The one
rejection is an application defect (join/leave returned a response missing the Run body); the
delivered app passed the boot audit on **eight of nine** rolls.

**The line's bar was L1, and it held: 0 contentless qa first attempts across 172 emissions.**
That is what #1268 fixed — on the 1.7.1 tree the qa role's first attempt had become a sentence of
intent and nothing else, on three of five React rolls and both Next.js rolls, and it was reaching
four pre-existing recovery-path seams for the first time.

**Stated rather than implied:** five of the eight predictions (L2, L5, L6, L7, L8) entered the
set unexercised and left it unexercised — no absent-suite repair, no re-dispatched suite, no app
runtime error, no qa-owned failure and no path-prefix emission arose in nine rolls. They are held
only by the shakeout loop's injected diagnostics. And the shakeout loop is reported as two
numbers: **five rounds against a budget of three, zero attributable to the pack** — twelve
instrument defects, none in the items being measured.

### The pack

- **The qa authoring pair gets the reasoning channel back** (#1268) — the contentless first
  attempt, the condition every other prediction is measured through.
- **A qa-owned defect is detected per runner** (#1270) — the own-frame detector was pytest-shaped
  and the vitest side had none; and **the fullstack merge stopped discarding every
  `suite_defect`** (#1305), which is why 1.7.1's R2 looked unfixable.
- **A passing qa task hands its evidence to the ledger** (#1271); **the retest is keyed on what
  the patch contains** (#1269); **a prose-only repair is refunded and the termination says which
  absence** (#1273).
- **The failing cases reach the model** — on the re-dispatch and at all (#1260, #1289) — and
  **the repairer reads the traceback**, with the fence example naming the task's own file
  (#788, #1272).
- **An accepted patch supersedes the failed attempt's rows** (#1318) — the ledger's supersession
  identity had gained a criterion since #1021 and the patch row never carried it, so a run could
  be rejected on a defect its own accepted patch had fixed. Found by voiding a counted roll.
- **The rejects-blank probe derives its status from the authored mapping on both stacks** (#1321)
  — stack 1 hardcoded 422 on a premise its own frozen error seam falsifies, so any manifest
  declaring 400 produced an unwinnable probe.
- **The Next.js qa namespace is the co-located convention, not the application** (#1292).

### Instrument

- **A cycle can be made to fail on purpose, on its own path** (#1251) — fault injection, so a
  recovery-path prediction can be exercised rather than waited for.
- The retry path says whether the remedy reached the prompt (#1110); one home for the gate rule
  (#1150); the fan-out path records verification evidence (#1148); a fault that cannot bite says
  so instead of claiming an exercise (#1300); a fault declaration survives the wire it arrives on
  (#1298); a record names the deploy it observed rather than the one someone typed (#1296).

### Known and open at the cut

- **#1323** — a builder's unrequested source file is admitted because the failed-emission storage
  route performs no write authorization, and the repair that fixes it is dropped. Found on
  counted roll 1.
- **#1324** — the boot audit discards the response it judged, so a failed probe cannot be
  root-caused from the record.
- **#1312** — `qa_handoff.md` is required, multiply-verified and read by nothing; its declared
  signature was not hit in this set.
- **#1316** — nine unit-test directories (437 tests) are outside the regression gate.
- The driver's `refused_patches` truncates mid-word, and **"qa primary tokens" is declared as
  texture in the pre-registration with no producer** — which is why #1285's reading cannot be
  made from this set.

## Merged pull requests (33)

| PR | Title | Closes |
|---|---|---|
| [#1327](https://github.com/backspring-labs/squad-ops/pull/1327) | chore(release): 1.7.2 — Loop Honesty | — |
| [#1326](https://github.com/backspring-labs/squad-ops/pull/1326) | docs(1.7.2): the verification set record — nine counted, L1 held, five of eight unexercised | — |
| [#1322](https://github.com/backspring-labs/squad-ops/pull/1322) | docs(1.7.2): pin the round-5 deploy and carry #1318's evidence into every record | — |
| [#1321](https://github.com/backspring-labs/squad-ops/pull/1321) | fix(contract): stack 1 derives the blank-rejection status from the mapping | — |
| [#1320](https://github.com/backspring-labs/squad-ops/pull/1320) | fix(driver): P0 stops demanding nullable for a declared non-null default | — |
| [#1319](https://github.com/backspring-labs/squad-ops/pull/1319) | fix(correction): an accepted patch supersedes the failed attempt's rows | [#1318](https://github.com/backspring-labs/squad-ops/issues/1318) |
| [#1315](https://github.com/backspring-labs/squad-ops/pull/1315) | test(verification-sets): the pin guard covers the line that is about to launch | — |
| [#1314](https://github.com/backspring-labs/squad-ops/pull/1314) | docs(1.7.2): fill the set-config pins from the round-4 deploy | — |
| [#1313](https://github.com/backspring-labs/squad-ops/pull/1313) | docs(1.7.2): the verification set pre-registration — frozen, pins from the round-4 deploy | — |
| [#1309](https://github.com/backspring-labs/squad-ops/pull/1309) | fix(diagnostics): the fault is deterministic — runner-aware, and once per task (#1304) | [#1304](https://github.com/backspring-labs/squad-ops/issues/1304) |
| [#1308](https://github.com/backspring-labs/squad-ops/pull/1308) | docs(1.7.2): freeze the CI-verified list at three, move eleven to 1.7.3 | — |
| [#1307](https://github.com/backspring-labs/squad-ops/pull/1307) | fix(executor): the fan-out path records verification evidence (#1148) | [#1148](https://github.com/backspring-labs/squad-ops/issues/1148) |
| [#1306](https://github.com/backspring-labs/squad-ops/pull/1306) | fix(test-runner): the fullstack merge keeps both sides' evidence (#1305) | [#1305](https://github.com/backspring-labs/squad-ops/issues/1305) |
| [#1303](https://github.com/backspring-labs/squad-ops/pull/1303) | fix(observability): the retry path says whether the remedy reached the prompt (#1110) | [#1110](https://github.com/backspring-labs/squad-ops/issues/1110) |
| [#1302](https://github.com/backspring-labs/squad-ops/pull/1302) | refactor(lifecycle): one home for the gate rule (#1150) | [#1150](https://github.com/backspring-labs/squad-ops/issues/1150) |
| [#1301](https://github.com/backspring-labs/squad-ops/pull/1301) | fix(diagnostics): a fault that cannot bite says so instead of claiming an exercise (#1300) | [#1300](https://github.com/backspring-labs/squad-ops/issues/1300) |
| [#1299](https://github.com/backspring-labs/squad-ops/pull/1299) | fix(diagnostics): a fault declaration survives the wire it arrives on (#1298) | [#1298](https://github.com/backspring-labs/squad-ops/issues/1298) |
| [#1297](https://github.com/backspring-labs/squad-ops/pull/1297) | fix(driver): a record names the deploy it observed, not the one someone typed (#1296) | [#1296](https://github.com/backspring-labs/squad-ops/issues/1296) |
| [#1295](https://github.com/backspring-labs/squad-ops/pull/1295) | fix(evidence): failing_case_lines' docstring is a raw string | — |
| [#1294](https://github.com/backspring-labs/squad-ops/pull/1294) | docs(1.7.2): the verification set configs — React N=6, Next.js N=3 | — |
| [#1293](https://github.com/backspring-labs/squad-ops/pull/1293) | fix(scaffold): the Next.js qa namespace is the co-located convention, not the application (#1292) | [#1292](https://github.com/backspring-labs/squad-ops/issues/1292) |
| [#1291](https://github.com/backspring-labs/squad-ops/pull/1291) | feat(correction): the repairer reads the traceback, and the fence example names the task's own file (#788, #1272) | [#788](https://github.com/backspring-labs/squad-ops/issues/788) [#1272](https://github.com/backspring-labs/squad-ops/issues/1272) |
| [#1290](https://github.com/backspring-labs/squad-ops/pull/1290) | fix(correction): the failing cases reach the model — on the re-dispatch, and at all (#1260, #1289) | [#1260](https://github.com/backspring-labs/squad-ops/issues/1260) [#1289](https://github.com/backspring-labs/squad-ops/issues/1289) |
| [#1288](https://github.com/backspring-labs/squad-ops/pull/1288) | fix(correction): a prose-only repair is refunded, and the termination says which absence (#1273) | — |
| [#1287](https://github.com/backspring-labs/squad-ops/pull/1287) | fix(correction): the retest is keyed on what the patch contains (#1269) | [#1269](https://github.com/backspring-labs/squad-ops/issues/1269) |
| [#1281](https://github.com/backspring-labs/squad-ops/pull/1281) | fix(correction): the own-frame detector is a per-runner declaration, and the vitest side had none (#1270, #1279, #1280) | [#1270](https://github.com/backspring-labs/squad-ops/issues/1270) [#1279](https://github.com/backspring-labs/squad-ops/issues/1279) [#1280](https://github.com/backspring-labs/squad-ops/issues/1280) |
| [#1282](https://github.com/backspring-labs/squad-ops/pull/1282) | feat(verification): a cycle can be made to fail on purpose, on its own path (#1251) | [#1251](https://github.com/backspring-labs/squad-ops/issues/1251) |
| [#1283](https://github.com/backspring-labs/squad-ops/pull/1283) | fix(verification): a passing qa task hands its evidence to the ledger (#1271) | [#1271](https://github.com/backspring-labs/squad-ops/issues/1271) |
| [#1286](https://github.com/backspring-labs/squad-ops/pull/1286) | fix(reasoning): the qa authoring pair gets the channel back (#1268) | [#1268](https://github.com/backspring-labs/squad-ops/issues/1268) |
| [#1284](https://github.com/backspring-labs/squad-ops/pull/1284) | docs(plan): 1.7.2 §8a — the #1268 reading, and the fix it selects | — |
| [#1278](https://github.com/backspring-labs/squad-ops/pull/1278) | feat(verification): every readout is read by its reason, not its count (#1276) | [#1276](https://github.com/backspring-labs/squad-ops/issues/1276) |
| [#1277](https://github.com/backspring-labs/squad-ops/pull/1277) | docs(plan): the 1.7.2 line plan — Loop Honesty, first half, re-cut around the 1.7.1 record | — |
| [#1275](https://github.com/backspring-labs/squad-ops/pull/1275) | docs(release): capture the v1.7.1 release package | — |

## Cycle evidence

### `cyc_1f292d1953c6`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_58279e83c19b`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_eafdc918e8b0`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join-duplicate, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs-join, vc-probe-runs-leave |
| Required unmet | — |
| Never executed | — |
