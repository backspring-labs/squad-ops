---
title: v1.4.1
---

# v1.4.1

**Released 2026-08-03** · [tag `v1.4.1`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.4.1)

**Hardening Patch** — the five hash-stable fixes filed as known-open at the 1.4.0 cut, one
PR per issue: **#672** runtime_activities reaper (startup + finalize sweeps through the
abort choke point); **#671** module-existence validation at the gate; **#673** the first
plan-wide cross-task rule, rejecting two tasks that claim the same expected artifact;
**#667** repair-envelope testid threading, with the surface re-derived from the manifest at
repair-input construction; **#669** framing re-rolls revise instead of re-dicing, turning
`framing_max_rerolls` into a revision budget.

Contract v9 / manifest v4 unchanged (hash-stable by construction). #668/#670 deliberately
held for the next window. Plan: `docs/plans/1-4-1-hardening-patch-plan.md`.

Confirmation shakedowns unscored by pre-declaration: **shk-1 green** — framing authored a
real dual claim, #673 auto-rejected it (a live true positive), #669 threaded the rejection
into a surgically revised re-roll, and implementation cleared all 14 criteria with zero
corrections. **shk-2** fired #667's trigger live, then surfaced a *pre-existing*
correction-chain loss mode diagnosed to root cause and filed as #687/#688/#689.

## Merged pull requests (9)

| PR | Title | Closes |
|---|---|---|
| [#690](https://github.com/backspring-labs/squad-ops/pull/690) | release: v1.4.1 — five-fix hardening patch, deploy-verified + live-confirmed | — |
| [#685](https://github.com/backspring-labs/squad-ops/pull/685) | chore(sips): promotion audit — 0096/0092/0093/0088 all stay accepted, gaps named + filed | — |
| [#681](https://github.com/backspring-labs/squad-ops/pull/681) | SIPs + post-1.4 roadmap reshuffle: Squad-Authored Manifest (1.6), Campaign retarget + Cross-Cycle Memory (1.8), Memory P2 (2.0) | — |
| [#680](https://github.com/backspring-labs/squad-ops/pull/680) | fix(framing): re-rolls carry the prior rejection — revise, don't re-dice (#669) | [#669](https://github.com/backspring-labs/squad-ops/issues/669) |
| [#679](https://github.com/backspring-labs/squad-ops/pull/679) | fix(correction): thread the #659 anchor surface into repair and retest envelopes (#667) | [#667](https://github.com/backspring-labs/squad-ops/issues/667) |
| [#677](https://github.com/backspring-labs/squad-ops/pull/677) | fix(plan-validation): reject import_present on modules the scaffold surface cannot provide (#671) | [#671](https://github.com/backspring-labs/squad-ops/issues/671) |
| [#678](https://github.com/backspring-labs/squad-ops/pull/678) | fix(plan-validation): reject two tasks claiming the same expected artifact (#673) | [#673](https://github.com/backspring-labs/squad-ops/issues/673) |
| [#676](https://github.com/backspring-labs/squad-ops/pull/676) | fix(runtime): reap stranded runtime_activities — finalize sweep + startup reaper (#672) | [#672](https://github.com/backspring-labs/squad-ops/issues/672) |
| [#675](https://github.com/backspring-labs/squad-ops/pull/675) | docs(plans): 1.4.1 hardening patch plan | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0090-Agent-Embodiment-Substrate](../../design/sips/SIP-0090-Agent-Embodiment-Substrate.md) | new | accepted |
| [SIP-0091-Duty-Durability-via-Temporal](../../design/sips/SIP-0091-Duty-Durability-via-Temporal.md) | new | accepted |
| [SIP-0096-Verification-Evidence-Integrity](../../design/sips/SIP-0096-Verification-Evidence-Integrity.md) | new | accepted |
| [SIP-Campaign-Orchestration](../../design/sips/SIP-Campaign-Orchestration.md) | new | proposed |
| [SIP-Cross-Cycle-Memory](../../design/sips/SIP-Cross-Cycle-Memory.md) | new | proposed |
| SIP-Squad-Authored-Manifest | new | proposed |
