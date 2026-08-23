---
title: v1.5.0
---

# v1.5.0

**Released 2026-08-07** · [tag `v1.5.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.5.0)

**Finish the Promises, Extract the Proven** — the odd-minor stabilization release.
Feature-free by rule and verified as such at the cut: no new contract fields, manifest
fields, request-profile capabilities, or squad-facing handler/workflow surfaces, and
**contract v9 / manifest v4 byte-stable line-wide**. 34 PRs, one per issue, across three
gates. Plan: `docs/plans/1-5-0-stabilization-plan.md`.

### Added — verification integrity, finished
- **SIP-0096 implemented**, not merely promoted. Gate waivers as additive schema plus CLI
  `--waive/--waiver-reason`, where a waived check is recorded and disclosed but the
  verdict itself is never rewritten (#682, migration 1030); wrap-up consumes the
  `CycleOutcome` seam and **clamps** over-claiming closeout prose to the evidence it cites
  (#683); inert-cycle detection derived on read — a squad that stops producing evidence is
  detected rather than read as passing (#684). The promotion PR also caught its own
  premise delta: the audit's fourth normative item (a SKIP-only pulse is zero evidence,
  not a pass) had been dropped from the plan and was implemented rather than waved through.
- **qa joins the typed-acceptance seam (#670)** — authored checks *and* framework
  injections now reach both authoring surfaces, closing the gap shk-3 found where
  `undefined_names` stopped at the qa boundary.
- **SIP-0101 Cycle Replay Harness, minimum slice** — maintainer-only replay from a
  recorded execution boundary, rails before mechanism (#735–#737, migration 1020).

### Added — correction evidence and termination
- **#687** captures the application's real traceback from the probe runner's spool delta;
  **#431** makes emission accounting explicit at four producer seams so extraction loss is
  *named* rather than silently truncated. Together: the correction loop's long-standing
  diagnosis blindness.
- **#435** progress-aware correction termination — a moving chain is never cut short, a
  repeating one never burns the budget.
- **#629** a test suite whose assertions contradict the frozen contract is a blocking
  failure; the prose half ships advisory by construction.

### Changed — the structural quarantine
- **#663** the executor's context assembly becomes a declared `ContextAssemblyContract`
  per task type, replacing five tables and three branches — landed in three golden-first
  slices, 19 goldens captured *before* each refactor and byte-identical through.
- **#331** the 1,887-line planning handler splits into a package by authoring stage; a
  pure move, AST-verified 20/20 top-level names, every pre-split test passing unmodified.
- **#730 + #504** every typed check declares its own governance metadata in one registry
  with required, no-default fields — a new check cannot be added without declaring who
  owns its failures and whether it replays — plus the blocking `fill_slot_signature` check
  and a generated menu pinned by drift tests.
- **#481** stranded-cycle detection as a fourth startup sweep, read-only, emitting the
  exact recovery command. Its first live boot surfaced two genuinely stranded cycles that
  had been invisible for weeks.
- **#734** every acceptance verdict names the workspace revision it measured.
- **#506** transport owns the full task lifecycle, fixing retry attempts that never
  re-entered RUNNING; **#724** ~20 config reads swept onto `resolved_config`; **#452** the
  last live-path prompt prose moved into managed assets with byte-equivalence pinned.

### Verified as a line
Two green confirmation shakedowns on integrated deploys — the Gate-2 exit
(`cyc_ea0b82cfbd17`, accepted, 17/17, zero corrections) and the cut shakedown
(`cyc_b07183b3cf5c`, accepted, 36/36 checks, 15/15 contract criteria, zero corrections,
zero machinery defects) — plus a live replay demonstration, a waiver end-to-end probe, and
a replay zero-diff over the stored green corpus.

### Filed forward
#761, #762, #668's suite half, #707, `package_builds` (declared-unbuilt with its trigger
recorded in the registry), SIP-0102 migration steps 3–7, SIP-0092's M3, and the #557
post-retest governance review (SIP drafted) → v1.6+.

## Merged pull requests (36)

| PR | Title | Closes |
|---|---|---|
| [#765](https://github.com/backspring-labs/squad-ops/pull/765) | chore(release): v1.5.0 — Finish the Promises, Extract the Proven | — |
| [#764](https://github.com/backspring-labs/squad-ops/pull/764) | docs(1.5): cut shakedown shk-7 green — matrix closed, cut authorized | — |
| [#763](https://github.com/backspring-labs/squad-ops/pull/763) | sips: Squad-Authored-Manifest — 1.5-boundary amendments (author/reviewer shape, chaos containment, benchmark ruling) | — |
| [#760](https://github.com/backspring-labs/squad-ops/pull/760) | sips: #557 post-retest review draft + Cross-Cycle Memory shakedown exhibits | — |
| [#759](https://github.com/backspring-labs/squad-ops/pull/759) | docs(1.5): evidence matrix — Gate-3 rows green, cut gate open | — |
| [#758](https://github.com/backspring-labs/squad-ops/pull/758) | feat(#730): fill_slot_signature — blocking injected check (D1; closes #730, #504) | [#504](https://github.com/backspring-labs/squad-ops/issues/504) [#730](https://github.com/backspring-labs/squad-ops/issues/730) |
| [#757](https://github.com/backspring-labs/squad-ops/pull/757) | feat(#730): typed-check governance — CheckSpec registry extension (A5 PR 1) | [#504](https://github.com/backspring-labs/squad-ops/issues/504) |
| [#756](https://github.com/backspring-labs/squad-ops/pull/756) | feat(#734): workspace-revision provenance — Slice A (closes #734) | [#734](https://github.com/backspring-labs/squad-ops/issues/734) |
| [#755](https://github.com/backspring-labs/squad-ops/pull/755) | fix(#481): startup sweep surfaces cycles stranded between workloads (closes #481) | [#481](https://github.com/backspring-labs/squad-ops/issues/481) |
| [#754](https://github.com/backspring-labs/squad-ops/pull/754) | refactor(#331): planning_tasks.py → handlers/planning package (closes #331) | [#331](https://github.com/backspring-labs/squad-ops/issues/331) |
| [#753](https://github.com/backspring-labs/squad-ops/pull/753) | refactor(#663): S3 — plan-time context through the registry + gate-seam ownership (closes #663) | [#663](https://github.com/backspring-labs/squad-ops/issues/663) |
| [#752](https://github.com/backspring-labs/squad-ops/pull/752) | refactor(#663): S2 — correction-path context through the context-assembly registry | — |
| [#751](https://github.com/backspring-labs/squad-ops/pull/751) | refactor(#663): S1 — dispatch-time context assembly to the capability-owned registry | — |
| [#750](https://github.com/backspring-labs/squad-ops/pull/750) | docs(1.5): Gate-2 exit shakedown GREEN — evidence matrix filled, Gate 3 open | — |
| [#749](https://github.com/backspring-labs/squad-ops/pull/749) | feat(sip): promote SIP-0096 to implemented — AC#6 pulse amendment + AC#11 test + full AC mapping | — |
| [#748](https://github.com/backspring-labs/squad-ops/pull/748) | fix(config): #724 resolved_config sweep — effective-config reads through the #426 single merge | [#724](https://github.com/backspring-labs/squad-ops/issues/724) |
| [#747](https://github.com/backspring-labs/squad-ops/pull/747) | refactor(prompts): #452 build-profile narratives externalized byte-identically | [#452](https://github.com/backspring-labs/squad-ops/issues/452) |
| [#746](https://github.com/backspring-labs/squad-ops/pull/746) | fix(observability): #506 in-flight task runs visible — transport owns the task-run lifecycle | [#506](https://github.com/backspring-labs/squad-ops/issues/506) |
| [#745](https://github.com/backspring-labs/squad-ops/pull/745) | feat(verification): #629 contract-expectation enforcement, split by determinism (A6/D2) | [#629](https://github.com/backspring-labs/squad-ops/issues/629) |
| [#744](https://github.com/backspring-labs/squad-ops/pull/744) | feat(verification): #684 SIP-0096 §9 inert-check detection — CycleOutcome.inert populated | [#684](https://github.com/backspring-labs/squad-ops/issues/684) |
| [#743](https://github.com/backspring-labs/squad-ops/pull/743) | feat(wrapup): #683 — wrap-up consumes CycleOutcome (SIP-0096 §10/§14) | [#683](https://github.com/backspring-labs/squad-ops/issues/683) |
| [#742](https://github.com/backspring-labs/squad-ops/pull/742) | feat(verification): #682 — the gate-waiver slice (SIP-0096 §6.5/AC#12) | [#682](https://github.com/backspring-labs/squad-ops/issues/682) |
| [#741](https://github.com/backspring-labs/squad-ops/pull/741) | fix(correction): #435 — progress-aware termination (the A4 bounded lever) | [#435](https://github.com/backspring-labs/squad-ops/issues/435) |
| [#740](https://github.com/backspring-labs/squad-ops/pull/740) | fix(correction): #431 — the extraction-loss signal (completes the A3 pair) | [#431](https://github.com/backspring-labs/squad-ops/issues/431) |
| [#739](https://github.com/backspring-labs/squad-ops/pull/739) | fix(correction): #687 — thread the app traceback into failure_evidence | [#687](https://github.com/backspring-labs/squad-ops/issues/687) |
| [#738](https://github.com/backspring-labs/squad-ops/pull/738) | fix(qa): #670 — qa.test joins the typed-acceptance seam | [#670](https://github.com/backspring-labs/squad-ops/issues/670) |
| [#737](https://github.com/backspring-labs/squad-ops/pull/737) | feat(replay): SIP-0101 Slice 3 — the replay mechanism (closes the Gate-1 minimum path) | — |
| [#736](https://github.com/backspring-labs/squad-ops/pull/736) | feat(replay): SIP-0101 Slice 2 — boundary retention (migration 1020) | — |
| [#735](https://github.com/backspring-labs/squad-ops/pull/735) | feat(replay): SIP-0101 Slice 1 — replay evidence rails (inert) | — |
| [#733](https://github.com/backspring-labs/squad-ops/pull/733) | docs(1.5): workspace-revision spike — promote the provenance slice, defer pinning | — |
| [#732](https://github.com/backspring-labs/squad-ops/pull/732) | docs(1.5): SIP-0092 M2→M3 gate evaluation — gate passes on 67 cycles | — |
| [#731](https://github.com/backspring-labs/squad-ops/pull/731) | docs(1.5): instantiate the release evidence matrix (Gate 1) | — |
| [#729](https://github.com/backspring-labs/squad-ops/pull/729) | docs(1.5): typed-check governance design — the A5 curated menu | — |
| [#728](https://github.com/backspring-labs/squad-ops/pull/728) | docs: ADR pinning the defended-bespoke architecture decisions | [#583](https://github.com/backspring-labs/squad-ops/issues/583) |
| [#727](https://github.com/backspring-labs/squad-ops/pull/727) | docs(1.5-plan): Gate-2 exit confirmation shakedown | — |
| [#726](https://github.com/backspring-labs/squad-ops/pull/726) | docs: 1.5.0 stabilization plan — finish the promises, extract the proven | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0096-Verification-Evidence-Integrity](../../design/sips/SIP-0096-Verification-Evidence-Integrity.md) | new | implemented |
| [SIP-Campaign-Orchestration](../../design/sips/SIP-Campaign-Orchestration.md) | new | proposed |
| [SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements](../../design/sips/SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md) | new | proposed |
| [SIP-Cross-Cycle-Memory](../../design/sips/SIP-Cross-Cycle-Memory.md) | new | proposed |
| [SIP-Cycle-Evaluation-Scorecard](../../design/sips/SIP-Cycle-Evaluation-Scorecard.md) | new | proposed |
| [SIP-Post-Retest-Governance-Acceptance-Review](../../design/sips/SIP-Post-Retest-Governance-Acceptance-Review.md) | new | proposed |
| SIP-Squad-Authored-Manifest | new | proposed |
