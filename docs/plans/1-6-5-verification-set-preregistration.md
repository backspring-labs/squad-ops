# 1.6.5 — Verification Set: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Written 2026-08-26 (evening ET), after both shakeout pairs and before the first counted launch.
Merging it is the owner's act and does not change what it pre-registers; the branch commit is
the record.

This set is the 1.6.5 plan's §3 (`docs/plans/1-6-5-plan.md`, rev 3): **it tests mechanism,
not rate.** Everything not restated here is inherited **verbatim** from the 1.6.4
pre-registration (`docs/plans/1-6-4-verification-set-preregistration.md`) and, through it,
the 1.6.3 one: §1.3 (the honest limits of N=8), §5 (scoring), §5.1 (roll validity — void /
reset / counted), §6 and §6.1 (the gate constant and the two approval paths), §7 (prohibited
while open).

**What is new in this set's instrument.** The driver is `scripts/dev/verification_set_driver.py`
(PR #1117) and every fixed parameter below is read from
`docs/plans/verification-sets/1-6-5-nextjs.yaml` — the pins in that file and in this table are
the same values, written once. The driver refuses to launch a counting roll when the deploy's
image ids or HEAD differ from the pins.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **8 counted**, for comparability with the 1.6.3 (5/8) and 1.6.4 (8/8) sets |
| Bar | **none** on the rate; each prediction below is pass/fail on its own terms |
| Project / PRD / squad / request profile / overrides | identical to 1.6.4 §1: `group_run`, `full-38`, `validated-fullstack`, `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | `d4d4f66217d8` — **unchanged** from the 1.6.3/1.6.4 sets: this hash covers the request-profile side, and item E lives on the squad profile. The 1.6.5 plan (rev 3, §2.1 E) said E "changes `resolved_config_hash`"; it does not — corrected here |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — **new**: this is the identity E moved (eve `max_completion_tokens: 12288`); every 1.6.4 cycle carried `ab2965c78ccf2497…`. Recorded per roll; a roll on any other snapshot is not comparable |
| Deploy — commit | `7ebdb00e` (main at the #1121 merge: A+B+C+E #1115, D #1116, driver #1117/#1119, #772 #1118, #1120 #1121) |
| Deploy — 7 image ids | runtime-api `cdc7049d1e8e` · max `df6ca77549d4` · neo `02d8232c572b` · nat `eab4aae01876` · bob `a7dde4c8768b` · eve `803853cbb43c` · data `2796786aa8ec` — asserted at every launch by the driver; a rebuild mid-set voids comparability |
| Loaded, not built | verified in-container by the driver's `loaded_checks` before both shakeouts: `apply_followup_fills`, `recover_fills`, `_fill_observations`, `QATestHandler._suite_files`, `fill_mode_brief`; #1120's resolver change confirmed by source inspection in `squadops-runtime-api`; eve's `max_completion_tokens: 12288` confirmed on the resolved `full-38` profile |
| Gate policy | 1.6.3 §6 constant, verbatim text in the set config's `gate_notes`; `--as-agent`; both §6.1 paths satisfy zero-intervention and the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the frozen deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-6-5-nextjs.yaml --roll N` — one roll per invocation |

---

## 2. Preconditions

- **Both shakeouts green on THIS deploy** — met, 2026-08-26: the nextjs shakeout `cyc_6ce007ac2349`
  (accepted, audit PASS, 14/14, 0 corrections, 55 min; qa emission 7,006 tokens, fills first) and the
  stack #1 regression arm `cyc_549c040d985b` (accepted, audit PASS, 15/15, 0 corrections, 52 min). Both
  on squad snapshot `575707c58536cf3b…`, framed first time, gate by `system:no_open_questions`. If either failed, the set does not open and the failure is the first finding.
- **The first shakeout pair, on the previous deploy `9b725755`, is recorded and does not count as
  this precondition**: nextjs `cyc_0e81955001e0` was clean (accepted, 13/13, 0 corrections, Q0
  fills-first read from the LangFuse output, Q5 6,767 tokens); stack #1 `cyc_3cde35fa5204` was
  accepted 14/14 **by re-dispatch** after two empty-target repair rounds — the regression the arm
  exists to find, filed and fixed as #1120 (PR #1121). The deploy was rebuilt on the fix, hence
  this pair.
- Leases 0, nothing in flight, HEAD pinned at the deploy commit, working tree clean, at
  every launch (driver preflight).

---

## 3. Predictions — pass/fail each, read only from the evidence named

| # | prediction | falsified by | read from |
|---|---|---|---|
| **Q0** | every `qa.test` primary emission places all fill fences before any additive file (A) | one emission with an additive file ahead of a fill | the LangFuse generation output for the `qa.test` task (first `\`\`\`fill:` index < first path-fence index — readable within the 10k output cap because fills come first; the stored-artifact order is the handler's list order and says nothing about emission order, as shakeout 1 showed) |
| **Q1** | a qa primary emission that hits the cap loses only additive content: every fill slot merges (A) | a cap hit with any shell rendering "no fill received" | fill dispositions in the merged shells |
| **Q2** | a self-eval re-emission of fills is merged through the gate (C) | a self-eval emission with `fill: N>0` followed by a shell with no fill | eve log `self_eval fills: applied=…` + shells |
| **Q3** | the suite runs on the post-self-eval file set (B) | a failing `test_report.md` whose error names content the stored artifact of the same task does not contain | per-task `test_report.md` vs stored artifacts |
| **Q4** | an own-artifact qa repair whose failing test is a shell targets that shell (D) | a `correction_repair_locus: own_artifact — qa.test re-produces __tests__/…` line when the failed test was a scaffold file | runtime-api log (driver `loop_texture.fill_targets`) |
| **Q5** | no `qa.test` primary emission reaches its completion cap (E) | one primary at 12,288 tokens | eve `emission shape: … completion_tokens=` |
| **P0** | the seeded frozen tree agrees with the floor (#1096/#1087/#1079) | the driver's P0 `FALSIFIED` on any roll | driver `static_checks.p0` |
| **Coverage** | a green roll credits every criterion (#1021) | `criteria_verified < criteria_total` on an accepted roll | `run_verification_summaries` |
| **P1, P3, P5** | carried from 1.6.4 unchanged — unexercised is not passed | as pre-registered there | as there |

**Texture, no prediction attached:** the full qa primary completion-token distribution against
the ten from the 1.6.4 set (`4418 4947 5045 5498 5743 6292 7947 7963 8192 8192`); the cap-hit
count against 3/8; correction rounds against 1.6.4's 2 and 1.6.3's 0/1/3/4; wall clock; the
verdict rate against 8/8 and 5/8 (reported, no significance claimed).

**Pre-registered early stop, one direction.** A falsified Q0–Q5 or P0 stops the set: the fix did
not work and the remaining rolls teach nothing about it — stop, record, re-register. A good
result is never grounds to stop early.

---

## 4. The stack #1 regression arm — non-counting, recorded here

`docs/plans/verification-sets/1-6-5-stack1-regression.yaml`: same deploy, no overrides
(`validated-fullstack`'s defaults are `fullstack_fastapi_react`), its own config hash
`c4d6a2165acf`. One cycle at shakeout time (`cyc_549c040d985b`), the first on this stack since
`cyc_9e77f25820b5` (2026-08-09) and the first ever in authored-manifest mode there. It reports
P0 (models.py element types asserted; the per-entity store recorded as `stores_beyond_roots`,
#1087's open half), the ledger, the audit and the loop texture — **and no rate**. It is a
regression check on the shared surfaces, not a measurement of the stack. What it cannot do is
repair a qa-side failure in place — stack #1 has no fill slots — so a green that arrives by the
executor's full `qa.test` re-dispatch is recorded as such, never as a repair (#1123 for the
1.6.6 slate; #1122 on the 1.7 list).

---

## 5. Delegation

Executed by the assistant under the owner's standing delegation for this set: launch, gate
approval with the §6 constant, collection, and the per-roll record; **the counted/void/reset
reading is made at each roll boundary before the next launch**, and a reset or a falsified
prediction stops the set for the owner. No merges to main while the set is open (§7).
