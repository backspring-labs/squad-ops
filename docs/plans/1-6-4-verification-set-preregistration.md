# 1.6.4 — Verification Set: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Written 2026-08-26 (ET evening of 08-25), before the first launch, while
shakeout 2 (`cyc_692a52a8ad1e`) was still running. Merging it is the owner's act and does not
change what it pre-registers; the branch commit is the record.

This set is the 1.6.4 plan's §3 (`docs/plans/1-6-4-plan.md`, rev 4): **it tests mechanism,
not rate.** Everything not restated here is inherited from the 1.6.3 pre-registration
(`docs/plans/1-6-3-repeatability-set-preregistration.md`) **verbatim**: §1.3 (the honest
limits of N=8), §5 (scoring), §5.1 (roll validity — void / reset / counted), §6 and §6.1
(the gate constant and the two approval paths), §7 (prohibited while open).

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **8 counted**, for comparability with the 1.6.3 baseline of 5/8 |
| Bar | **none** on the rate; each prediction below is pass/fail on its own terms |
| Project / PRD / squad / request profile / overrides | identical to 1.6.3 §3: `group_run`, `full-38`, `validated-fullstack`, `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | `d4d4f66217d8` — the set's, shakeout 1's and shakeout 2's; asserted at every launch |
| Deploy — commit | `5a697dfa` (main at the #1103 merge; the full 1.6.4 pack: #1098, #1100, #1101, #1102, #1103) |
| Deploy — 7 image ids | runtime-api `5db73df0ed4c` · max `7e8f02591878` · neo `69fd811e7835` · nat `c5c6e8fb5810` · bob `ffb415ff3ecf` · eve `fef7b35fb9e2` · data `02f7c7490747` — asserted at every launch; a rebuild mid-set voids comparability |
| Loaded, not built | verified in-container before shakeout 2: generator 8, the #1021 identity, `slot_element_kinds`, `implicated_files`, `classify_empty_emission`, `_narrowed_or_scoped` |
| Gate policy | 1.6.3 §6 constant, verbatim text with "1.6.3 repeatability set" replaced by "1.6.4 verification set"; `--as-agent`; both §6.1 paths satisfy zero-intervention and the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the frozen deploy commit — judging with the shared `evaluate_expectations`, so it reads `json_has` |
| Driver | `scratchpad/set_driver.py` — one roll per invocation; preflights leases, in-flight runs, the seven image ids and the HEAD pin; applies the gate constant; collects the record; runs the audit and the checks below |

---

## 2. Preconditions

- **Shakeout 2 green**: verdict `accepted`, boot audit PASS, static P0 checks pass, and the
  #1021 ledger check passes (`criteria_verified == criteria_total`). If any fails, the set
  does not open and the failure is the morning's first finding.
- Leases 0, nothing in flight, HEAD pinned at `5a697dfa`, working tree clean, at every launch.

---

## 3. Predictions — pre-registered, each falsifiable on its own

| # | prediction | falsified by | how it is read |
|---|---|---|---|
| **P0** | The seeded frozen tree agrees with the floor: `lib/models.ts` types every `list[X]` field as `X[]`; `TABLES` exports only root-persisted entities; the harness addresses one of them; the derived contract's success probes carry `json_has` (#1096, #1087, #1079) | any seeded `models.ts` disagreeing with its manifest, at N=1 | the stored `scaffold.expand` artifacts and the framing's `verification_contract.yaml`, per roll |
| **P1** | No roll asserts on a table the store does not export (#1087) | a phantom-table assertion reaching a retest | the fill-merge dispositions (a phantom reference is rejected at merge with the tables named) and the final shells |
| **P2** | The audit and the suite agree on the response floor: no roll rejected on the floor whose audit passes (#1079) | a roll red on `expectShape` with audit PASS | verdict + audit per roll |
| **P3** | No repair candidate is rejected on fill assertions the floor contradicts (#1094) | a rejected candidate whose retest failed only on such a fill | fill-merge dispositions carrying `#1094`; correction-round test reports |
| **P4** | Every zero-character repair emission carries a named signature (#998) | the runtime-api `repair emitted no content` line reading `signature unreported` | runtime-api log lines for the roll's window |
| **P5** | Every repair round's target is the slot owning the failing probe, alone (#1015-A) — the language-wide surface withheld | a `correction_repair_target … falling back to same-language implementation source` line in a round whose decision named a probe-owned endpoint | runtime-api log lines for the roll's window |
| **Coverage (#1021)** | A green roll credits every criterion: no `vc-compiles-*` in `criteria_unevidenced`; `criteria_verified == criteria_total` | any accepted roll with a dropped compile criterion | `run_verification_summaries` per roll |

**Predictions are read per roll and only on the evidence named.** P3–P5 are exercised only by
rolls that enter the correction loop; a set with no corrections leaves them *unexercised*, and
the record says so rather than counting them passed.

**Early stop, one direction only** (plan §3, inherited): a falsified prediction stops the set
— the remaining rolls teach nothing about it — and the record says which and re-registers. A
good result is never grounds to stop early. Eight rolls, done.

**The rate is secondary.** Reported against 5/8 with 1.6.3 §1.3's interval discipline; no
significance is read into a small delta at this N.

---

## 4. Per-roll record

For each roll: cycle id, framing run count, gate decider verbatim, verdict, boot audit, the
P0/coverage check results, correction rounds with per-round (target list, emission signature
if empty, fill dispositions), `criteria_verified/total`, wall clock in ET, and the §5.1
disposition (counted / void / reset). Rendered by the driver; nothing inferred from analyzer
prose.

---

## 5. Overnight operation (delegation recorded)

The owner delegated the set's execution overnight (2026-08-25 ET) with the standing night
rules: no pushes; triage per roll (trace artifact versions, read the code path before naming a
mechanism); deploy frozen, work not frozen; detections recorded, not fixed; gates are the §6
constant. The morning report leads with the result. Every roll is launched only after the
previous one's record is read and its §5.1 disposition decided.
