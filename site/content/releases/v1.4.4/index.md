---
title: v1.4.4
---

# v1.4.4

**Released 2026-08-05** · [tag `v1.4.4`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.4.4)

**No False Verdicts** (verification integrity). Every verdict is earned: greens are
enforced, reds are explained, budgets are honored. Seven premise-verified fixes, one PR
each — **#427** terminal failure reason persisted on the run row and surfaced by
`runs show` (migration 1010); **#426** builder offer and gate net both key off configured
`build_profile` via the new single-source `Cycle.resolved_config()`; **#715** a qa task
whose declared artifacts can never satisfy required `tests_pass` is rejected at authoring,
on both gate seams; **#423** an authored check the evaluator cannot run is an evidence gap
and never `passed: true`; **#424** plan-authoring collapse is a gate rejection, never a
silent static-step fallback; **#511** the time budget gates every dispatch lane including
correction chains; **#571** semantic-memory recall prefilters in-query with a valid cosine
metric.

Verified as a line on an integrated overnight deploy: in-container validator replays
against stored artifacts, a designed-failure probe budget-killed at the first boundary,
and confirmation shakedown **shk-5 green** — verdict accepted, zero corrections, the new
nets silent on a well-formed roll.

## Merged pull requests (9)

| PR | Title | Closes |
|---|---|---|
| [#725](https://github.com/backspring-labs/squad-ops/pull/725) | chore(release): cut v1.4.4 — No False Verdicts (version bump + marker sync + as-built record) | — |
| [#723](https://github.com/backspring-labs/squad-ops/pull/723) | fix(memory): LanceDB search prefilters in-query and scores with an explicit cosine metric (#571) | [#571](https://github.com/backspring-labs/squad-ops/issues/571) |
| [#722](https://github.com/backspring-labs/squad-ops/pull/722) | fix(executor): time budget gates correction-chain dispatch, not just the main task loop (#511) | [#511](https://github.com/backspring-labs/squad-ops/issues/511) |
| [#721](https://github.com/backspring-labs/squad-ops/pull/721) | fix(planning): plan authoring collapse is a rejection, never a silent static fallback (#424) | [#424](https://github.com/backspring-labs/squad-ops/issues/424) |
| [#720](https://github.com/backspring-labs/squad-ops/pull/720) | fix(verification): split skipped typed checks into benign vs evidence-gap — gaps never read passed (#423) | [#423](https://github.com/backspring-labs/squad-ops/issues/423) |
| [#719](https://github.com/backspring-labs/squad-ops/pull/719) | fix(plan-validation): reject qa.test tasks whose artifacts cannot satisfy required tests_pass (#715) | [#715](https://github.com/backspring-labs/squad-ops/issues/715) |
| [#718](https://github.com/backspring-labs/squad-ops/pull/718) | fix(planning): builder offer and gate net both key off configured build_profile (#426) | [#426](https://github.com/backspring-labs/squad-ops/issues/426) |
| [#717](https://github.com/backspring-labs/squad-ops/pull/717) | fix(runs): persist the terminal failure reason on the run row (#427) | [#427](https://github.com/backspring-labs/squad-ops/issues/427) |
| [#716](https://github.com/backspring-labs/squad-ops/pull/716) | docs(plan): 1.4.4 patch plan — No False Verdicts (7 fixes, premise-verified) | — |
