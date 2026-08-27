---
title: v1.6.5
---

# v1.6.5

**Released 2026-08-27** · [tag `v1.6.5`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.6.5)

**The qa-emission patch line, measured on two stacks.** The pack (A–E) makes a truncated qa
emission rarer and cheaper on the Next.js verification scaffold; #772 gives the success-status
default one home; #1120 stops a qa-side failure from emptying the dev repair target; and the
verification-set driver is promoted with its parameters as data. Its evidence is the first
**two-stack** pre-registered set.

### The evidence

Two counting sets on frozen deploy `7ebdb00e` —
`docs/plans/1-6-5-verification-set-record.md`, pre-registered before roll 1 (PR #1124, merged
as `fea4b5d6`) and unchanged throughout, executed overnight under delegation. **Twelve counted
rolls, no voids, no resets, every pre-registered prediction held on both sets; the early stop
never fired. Zero code drift between the measured deploy and the tag.**

- **Next.js+TS: 6 of 6 functional (95% CI 61.0–100%), zero correction rounds, zero cap hits
  (0 of 7 qa primaries against 3 of 8 under the old cap; max 9,148 of 12,288), fills first on
  7 of 7 emissions, every criterion credited on every roll.** Q1/Q2/Q4 — items C and D live —
  were not exercised, which is not passed.
- **FastAPI+React: 2 of 6 (95% CI 9.7–70.0%) — the stack's first authored-mode baseline, no bar.**
  Both greens **by repair**, none by re-dispatch. #1120 held 6 of 6. One scaffold defect sits
  under five of the six rolls' round 0 (#1125: `default: null` freezes a non-nullable field);
  two rolls ended after a **refused** repair patch counted as a round (#1129); roll 1's green
  re-dispatch was discarded by a Next.js-shaped check (#1126) after a harness gap (#1127); roll 3's
  contract was unsatisfiable by construction (#1128) and its qa-owned test defect was never
  routed (#1130). Filed with #1131 (the structural cause, 1.7); the fixes are the 1.6.6 plan.

### 1.6.5 line — the qa emission under the completion cap (plan: `docs/plans/1-6-5-plan.md`)

- **A — fills first** (#998 ask 2, ordering half). The qa fill-mode brief (appendix v4) states
  the emission order: every fill block, then any additive file. A cut at the completion cap now
  lands on the additive file — which #1082 detects and the self-eval re-emits — never on a fill.
  Roll 6 of the previous verification set (`docs/plans/1-6-4-verification-set-record.md`) lost all eight fills to an additive file written first.
- **B — the suite runs on what the task stores** (#1109). `qa.test` derived its suite-execution
  set before the self-eval loop, so a self-eval re-emission that fixed a blocking typed check was
  stored but never run; roll 8 failed on a truncated file whose replacement was already in hand,
  and a correction round was spent rediscovering it. The set is now derived from the artifacts at
  the moment of the run.
- **C — the self-eval merges fills** (#947). Under fill mode the self-eval prompt carries a
  fill-mode addendum naming the slots still unfilled (from the merge record), and its fills fold
  into the primary emission per slot — a missing or rejected slot takes the followup fill, an
  already-filled slot keeps its fill and the re-emission is recorded — then pass through the
  same merge gate (#1087 phantom tables, #1094 element kinds). Replayed on roll 6's banked
  self-eval fills: 8/8 merged where the handler had discarded all eight.
- **E — a qa-only completion budget** (#998 ask 2, budget half). `full-38`'s `eve` entry carries
  `config_overrides: {max_completion_tokens: 12288}`; four of ten qa primary emissions in that
  set sat at or within 3% of the 8,192 cap. The registry clamp (the V38 pin) and the dev
  budget are untouched. Changes `resolved_config_hash`; measured by prediction Q5.
- **#772 — the success-status default has one home.** The contract deriver asserted 201 for an
  undeclared collection POST while the stack #1 skeleton omitted `status_code=` and FastAPI
  answered 200 — an unwinnable contract, gate-mitigated since 08-10 and never fixed. The rule
  (`capabilities/success_status.py`: declared wins, else collection POST 201 / child POST 200,
  else HTTP's 200) had seven homes — three deriver sites, the skeleton, the framing mirror, the
  scaffold gate's allowed set, the Next.js route stub; every one now calls the seam, the
  decorator pins the derived status too, and a structural test fails if a copy returns.
  Reference fixtures unchanged (they declare their statuses).
- **#1120 — a qa-side failure no longer empties the dev repair target.** The analyzer half of
  #1015-A let the failed task's *own* artifact (a free-authored frontend suite the analyzer
  honestly implicated) act as a narrowing site: the language-wide surface was withheld, the #884
  veto removed the qa-owned file from the dev-role target, and every round was dispatched with
  nothing to produce and refunded — found on the first stack #1 cycle since 08-09
  (`cyc_3cde35fa5204`). Own artifacts ride the target but never narrow it; the package-scoped
  surface applies as it did before the analyzer half shipped.
- **D — an own-artifact qa repair can reach a fill** (#970, with #969's brief). Under fill mode
  the shells are merge products, never in `expected_artifacts`, so the own-artifact repair aimed
  at the plan's declared file and a failing fill was structurally unreachable. Now: the target is
  the failing slot's shell, read from the scaffold evidence's fill-layer observations; the repair
  authors under the **same** fill-mode brief as `qa.test` (one composition seam,
  `fill_mode_brief`, plus a repair addendum naming the failed slots with the runner's reason);
  it emits fill blocks, and the handler recovers every other slot's fill from the task's current
  shells, folds the repair's fills in, passes the same merge gate (#1087, #1094) and emits the
  merged shell at the shell path, so the patch overlay supersedes the failed one and the retest
  runs it. Round-trip pinned: recovering the fills from a merged shell and re-merging reproduces
  it byte for byte. Measured by prediction Q4.
- **Tooling — the verification-set driver is promoted** (`scripts/dev/verification_set_driver.py`).
  The scratchpad copies that drove sixteen counted rolls carried the stack, the deploy pins and
  the gate constant as code constants and were hand-edited per set; the promoted driver reads
  every fixed parameter from a set-config YAML (`docs/plans/verification-sets/`, the
  pre-registration's §1 as data), derives the stack from the request profile plus overrides,
  dispatches the P0 seeded-tree check per stack (an unregistered stack is refused, not passed),
  and reads the runtime log window with an explicit UTC zone — the `docker logs --since` defect
  the previous set's record logged against the instrument.

## Merged pull requests (12)

| PR | Title | Closes |
|---|---|---|
| [#1132](https://github.com/backspring-labs/squad-ops/pull/1132) | docs(plan): 1.6.6 plan rev 1 — FastAPI+React fixes ranked by rolls flipped | — |
| [#1133](https://github.com/backspring-labs/squad-ops/pull/1133) | chore(release): 1.6.5 — the qa-emission patch line, measured on two stacks | — |
| [#1124](https://github.com/backspring-labs/squad-ops/pull/1124) | docs(plan): pre-register the 1.6.5 verification set (deploy 7ebdb00e, both hash identities) | — |
| [#1121](https://github.com/backspring-labs/squad-ops/pull/1121) | fix(correction): the failed task's own artifact never narrows the repair target (#1120) | [#1120](https://github.com/backspring-labs/squad-ops/issues/1120) |
| [#1119](https://github.com/backspring-labs/squad-ops/pull/1119) | tooling(driver): records live under var/, not the root-owned data/ volume | — |
| [#1118](https://github.com/backspring-labs/squad-ops/pull/1118) | fix(scaffold): the success-status default has one home — the skeleton pins what the contract asserts (#772) | [#772](https://github.com/backspring-labs/squad-ops/issues/772) |
| [#1117](https://github.com/backspring-labs/squad-ops/pull/1117) | tooling: promote the verification-set driver — parameters as data, stack as the cycle's fact, UTC log window | — |
| [#1116](https://github.com/backspring-labs/squad-ops/pull/1116) | fix(correction): 1.6.5 D — an own-artifact qa repair can reach a fill (#970, #969) | [#969](https://github.com/backspring-labs/squad-ops/issues/969) [#970](https://github.com/backspring-labs/squad-ops/issues/970) |
| [#1115](https://github.com/backspring-labs/squad-ops/pull/1115) | fix(qa): 1.6.5 A+B+C+E — fills first, suite runs on what is stored, self-eval merges fills, qa-only budget | [#947](https://github.com/backspring-labs/squad-ops/issues/947) [#998](https://github.com/backspring-labs/squad-ops/issues/998) [#1109](https://github.com/backspring-labs/squad-ops/issues/1109) |
| [#1114](https://github.com/backspring-labs/squad-ops/pull/1114) | ci: PR closure references are checked, not assumed — template + required check | [#1113](https://github.com/backspring-labs/squad-ops/issues/1113) |
| [#1108](https://github.com/backspring-labs/squad-ops/pull/1108) | docs(plan): 1.6.5 rev 2 — qa-only completion budget (eve 12,288) alongside fills-first | — |
| [#1107](https://github.com/backspring-labs/squad-ops/pull/1107) | docs(release): capture the v1.6.4 release package | — |

## Cycle evidence

### `cyc_a306b4e858d9`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_9b17553ce9d5`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-participants, vc-probe-api-runs-participants-duplicate, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_0d85a682881a`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:count_at_least, acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_face9e37d93a`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_345268417e31`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-participants, vc-probe-api-runs-participants-duplicate, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_47cd83559c4a`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_b9296c255dfc`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_f84649c68646`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-participants, vc-probe-runs-participants-duplicate, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_184b3a1d194e`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-runs, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs-participants, vc-probe-runs-participants-duplicate, tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_5ef83cc6fc2b`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_0e7bc622169a`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_d43c644e52d0`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, tests_pass |
| Required unmet | — |
| Never executed | — |
