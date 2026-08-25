---
title: v1.6.3
---

# v1.6.3

**Released 2026-08-25** · [tag `v1.6.3`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.6.3)

**The measurement patch line.** 1.6.2 merged roughly twenty fixes and none of them had been
measured. This release ships three fixes and, for the first time, a **rate**.

### The evidence

A pre-registered eight-roll set on a frozen deploy — `docs/plans/1-6-3-repeatability-set-record.md`,
registered before roll 1 and unchanged throughout. **No voids, no resets.** Every gate was decided
by `system:no_open_questions`, so zero manual intervention is literally true rather than
true-by-ruling.

- **5 of 8 functional — 62.5%, 95% CI [30.6%, 86.3%]** (verdict *and* boot audit *and* zero
  intervention). The interval is wide and was pre-registered as such: this establishes a baseline,
  it does not claim an improvement it cannot detect at N=8.
- **8 of 8 delivered applications booted** and answered their declared status codes.
- **Zero framing re-rolls across all eight**, and ten consecutive cycles have now framed on the
  first attempt — against **three** framing runs for the pre-1.6.2 green roll. That is 1.6.2's
  success-status single-sourcing (#1067/#1070A), measured rather than asserted.

**Two of the three failures were the framework wrongly rejecting a working application** (#1087,
filed from the set). That is the release's most actionable finding, and it matters more than the
rate.

### Fixed

- **#971** — a failed task's emission is banked for triage instead of discarded. Before this, the
  one artifact guaranteed absent was the one that *caused* the failure. Triage-only, with three
  independent exclusions so known-bad bytes can never reach a workspace or the deliverable. The
  set banked 44/48/11/48/11 failed emissions on the rolls that needed them, and roll 1's root
  cause was traced by reading artifacts that would not previously have existed.
- **#1082** — an emission that stopped mid-construct is caught at the task that wrote it, rather
  than surfacing later as the consumer's test failure. Validated against all 4,513 scannable
  source artifacts in the banked corpus: 8 flags, every one a genuine truncation, zero false
  positives. Two false positives found *during* that validation drove real fixes (JSX punctuation
  read as a regex opener; parens counted inside JSX text) rather than a tuned threshold.
- **#1079** (parity half) — the boot-audit oracle and the in-cycle probe runner judge a contract
  with the same code. The oracle had re-implemented the expectation block and carried two of the
  three kinds, making the more trusted of two judges the more permissive one.
- **#1076** — the release package captures cycle evidence instead of reporting that it did.

### Known and named, not fixed

- **#1087** — the frozen store exports a table handle for every declared entity, including
  embedded shapes and response projections no correct application writes. Two of this set's three
  rejections. Fixing it moves the generator hash, so it is a deliberate 1.6.4 scaffold change.
- **#1079** (producer half) — `json_has` still has no producer, so **contract probes do not verify
  response bodies**. The boot audit certifies that an app boots and answers with the right status
  codes, not that it answers correctly. Roll 5 is the demonstration: rejected for a real missing
  field, audit passed.
- **#1021** — `criteria_unevidenced` never settled across eight rolls on one frozen deploy (1–5
  `vc-compiles-*` dropped per roll). Marked confounded before the set opened; the set is now the
  largest same-configuration sample the question has.
- **#1089** — the single-sourced framework version reads stale editable-install metadata. Found
  during this cut.

### Scope of the evidence

The set ran `full-38` (qwen3.8:27b) with `build_profile=nextjs_ts` and `dev_capability=nextjs_ts`
on `group_run`. `full` (qwen3.6) remains the canonical squad and the meaning of every historical
record; this set says nothing about it. Nothing in eight rolls was truncated, so #1082 demonstrated
only that it does not reject healthy work — its catching behaviour rests on the corpus sweep.

**Code drift between the tagged tree and the validated deploy: zero.** The freeze held from roll 1
to the tag.

## Merged pull requests (10)

| PR | Title | Closes |
|---|---|---|
| [#1090](https://github.com/backspring-labs/squad-ops/pull/1090) | chore(release): bump framework version to 1.6.3 + sync markers, rotate CHANGELOG | [#971](https://github.com/backspring-labs/squad-ops/issues/971) [#1076](https://github.com/backspring-labs/squad-ops/issues/1076) [#1082](https://github.com/backspring-labs/squad-ops/issues/1082) |
| [#1088](https://github.com/backspring-labs/squad-ops/pull/1088) | docs(plan): the 1.6.3 repeatability set closes at 5 of 8 functional | — |
| [#1086](https://github.com/backspring-labs/squad-ops/pull/1086) | docs(plan): the 1.6.3 set's preconditions are met — freeze recorded, both shakeouts read out | — |
| [#1085](https://github.com/backspring-labs/squad-ops/pull/1085) | docs(plan): the set's gate policy covers both approval paths, not just the human one | — |
| [#1084](https://github.com/backspring-labs/squad-ops/pull/1084) | fix(audit): the oracle and the runner judge a contract with the same code | [#1079](https://github.com/backspring-labs/squad-ops/issues/1079) |
| [#1083](https://github.com/backspring-labs/squad-ops/pull/1083) | fix(evidence): catch an emission that stopped mid-construct, at the task that wrote it | [#1082](https://github.com/backspring-labs/squad-ops/issues/1082) |
| [#1081](https://github.com/backspring-labs/squad-ops/pull/1081) | fix(evidence): a failed task's emission is banked for triage, and used for nothing | [#971](https://github.com/backspring-labs/squad-ops/issues/971) |
| [#1080](https://github.com/backspring-labs/squad-ops/pull/1080) | docs(plan): pre-register the 1.6.3 repeatability set — 8 rolls, frozen config | — |
| [#1078](https://github.com/backspring-labs/squad-ops/pull/1078) | docs: three release-cut lessons the 1.6.2 procedure did not carry | — |
| [#1077](https://github.com/backspring-labs/squad-ops/pull/1077) | fix(release): the package captures cycle evidence instead of reporting that it did | [#1076](https://github.com/backspring-labs/squad-ops/issues/1076) |

## Cycle evidence

### `cyc_9c43f56c5cd8`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |
