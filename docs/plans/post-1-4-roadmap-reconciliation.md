# Post-1.4 Roadmap Reconciliation — the 1.6 / 1.8 / 2.0 Reshuffle

**Established:** 2026-08-03 (owner-ratified in session) · **Partially supersedes:** the
Finding-5 feature-lane line of `docs/plans/2-0-roadmap-reconciliation.md` and the v1.6
shape in `docs/plans/1-4-evidence-arc-plan.md` (both written before the 1.4 cut-gate
supersession created the conflict resolved here).

## The conflict

At the 1.4.0 cut (2026-07-31), the original cut gate ("≥3 consecutive golden-benchmark
runs, squad-authored-manifest mode") was superseded by the pre-registered FAY
measurement in **seeded-manifest mode** — and the deliberately unmeasured
squad-authored-manifest rung was moved to **v1.6 as a headline**. But the v1.6 line
still carried everything the July-14 arc plan had assigned it: Campaign mechanic (whose
SIP header still said "the headline feature SIP that gates 1.6"), Generalized Build,
SIP-0091, and SIP-0090 Phase 2. That left **two Lane-M headliners in one release**
(Authored Manifest + Campaign), which the lane convention forbids, plus four riders.
The reshuffle was never reconciled after the cut.

## The principle

The roadmap's own trust ladder, applied recursively: **author over honest evidence;
automate and grade over the authored baseline; compound over trustworthy grades.**
The 1.4 cut inserted a new rung (authored-manifest capability) into the ladder, which
pushes the automation rung (Campaign) one slot up: a continuation policy that automates
relaunch over authored-mode cycles must not be tuned against a baseline being born in
the same release.

## The ratified progression

| Release | Identity | Headlines (M / S) | Rides along |
|---|---|---|---|
| **1.4.1** | confirmation patch | — | five-fix stack (#672/#671/#673/#667/#669), shakedown, bump |
| **1.5** | stabilization (feature-free) | — | #663 executor context-assembly extraction, curated typed-check menu, workspace-revision unification, #593/#598/#627/#628/#629 family, SIP-0101 replay-harness implementation, Atlas groundwork |
| **1.6** | **the Authorship release** | Squad-Authored Manifest (M) / Generalized Build (S) | SIP-0091, SIP-0090 P2, SIP-0102 steps 3–7, agent-comms delivery guarantees (hardening) |
| **1.7** | stabilization | — | debt from 1.6 |
| **1.8** | **the Automation + Learning release** | Campaign Orchestration (M) / scorecard + benchmark registry | Cross-Cycle Memory Phase 1 (thin, non-headline) |
| **2.0** | **the Compounding release** | Capability-Backed Agents umbrella | Self-Improvement + Test Bay, Campaign capability-augmentation, Memory Phase 2 (scoped-memory substrate) |

## Per-release rationale

- **1.6 — Authorship.** Squad-Authored Manifest is the 1.4 gate's own deferred
  condition and the earned next rung (`sips/proposed/SIP-Squad-Authored-Manifest.md`).
  Generalized Build (Stack Blueprint pluginization, second stack) is the natural S
  headline: both headliners extend the golden path, so a 1.6 regression is unambiguously
  golden-path work. Gate: authored-mode FAY repeatably > 0, banked as the authored-mode
  baseline. SIP-0102 steps 3–7 ride here (not 1.5) to keep the odd minor feature-free.
  Campaign moves out (below); its #316 request-profile-taxonomy dependency moves with it.
- **1.8 — Automation + Learning.** Campaign and the scorecard are complementary
  consumers of the same SIP-0096 `CycleOutcome` seam: one automates over evidence, the
  other grades it; landing them together hands 2.0 exactly what it compounds on.
  Cross-Cycle Memory Phase 1 rides as a thin non-headline feature (1.2.0 precedent:
  multiple feature SIPs, one release): by 1.8 it inherits two seed corpora
  (plan-validation classes + 1.6's new manifest-authoring rejection classes) and
  measures recurrence against the 1.6 authored-mode baseline without confounding that
  baseline's own measurement.
- **2.0 — Compounding.** Capability-Backed Agents consumes Memory **Phase 2**
  (consolidation, promotion, duty/ambient utilization) as the scoped-memory substrate
  its problem statement demands ("scope, provenance, promotion, disclosure") — proven
  at 1.8, not specified cold from inside an umbrella. Self-Improvement + Test Bay acts
  on `CycleAssessment` grades, never raw checks.

## Moves executed with this record (one PR)

1. `sips/proposed/SIP-Squad-Authored-Manifest.md` drafted — the 1.6 M headline
   previously existed only as a roadmap sentence.
2. `sips/proposed/SIP-Campaign-Orchestration.md` retargeted v1.6 → v1.8 (header +
   phasing section).
3. `docs/ROADMAP.md` Forward Cadence rewritten to the table above; drafts table and
   SIP-0102 target updated.
4. `sips/proposed/SIP-Cross-Cycle-Memory.md` placement rewritten (Phase 1 → 1.8 rider,
   Phase 2 → 2.0) + Campaign-interaction section (§7: provenance-not-scope,
   campaign-close consolidation clock, continuation-decision purity boundary).

## Addendum (2026-08-03, post-shk-1): the authoring-defect levers

shk-1 (the first 1.4.1 confirmation cycle) re-authored the fay-18 dual-claim class live
— caught by #673, revised via #669, but at the cost of one framing re-roll (~45 min,
half the re-roll budget). Owner-ratified slotting of the three non-memory levers,
layered so cross-cycle memory (1.8) measures only the uncodified tail:

| Lever | Slot | Home |
|---|---|---|
| Statics: render validator-family rules into authoring prompts | **1.5** | #686, beside the #629/#627 "show the author the contract" family |
| Shift-left: merge-time plan validation, revise before gate | **1.6** | SIP-0093 completion package (93.4 + §5.8 rules; rule 5 amended block→validate-and-revise) |
| Structural: produce-vs-verify declared, `expected_artifacts` derived | **1.6** | Generalized Build / Stack Blueprint scope (QA-decomposition anchor) |

Principle: validator-codified rules are *stated* (statics), authoring-time checks are
*cheap* (shift-left), derivable facts are *not authored* (structural), and only the
remainder is *learned* (memory).

## Not moved by this record

- Promotion audits for SIP-0088/0092/0093/0096 (maintainer housekeeping; 0096 matters
  soonest — it gates the 1.8 scorecard).
- 1.5 scope finalization (odd-minor rule: substance gates the cut, scope finalized at
  freeze-exit).
- Whether the 1.8→2.0 boundary is ultimately cut as numbered here is, as always, a
  cut-time decision; this record binds *sequencing*, not numbers-to-dates.
