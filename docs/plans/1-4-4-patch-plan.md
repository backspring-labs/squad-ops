# 1.4.4 Patch Plan — No False Verdicts

**Established:** 2026-08-04 · successor to `docs/plans/1-4-3-patch-plan.md`
(same discipline: one PR per issue with `Closes`, targeted verification per fix,
ONE deploy window, bump only after live confirmation). **Opens:** after the v1.4.3
tag lands. Sequencing, not dates.

## Character

One coherent claim: **every verdict is earned — greens are enforced, reds are
explained, budgets are honored.** Where 1.4.3 stopped the machinery from stranding
state or hiding lifecycle failures, this line closes the ways a *verdict* lies:
checks that pass without running, plans that cannot satisfy the checks that judge
them, instrumentation that silently degrades, failures that die unexplained, and
budgets that don't gate the work they were bought for. Plus one enabling fix
outside the theme (#571) that the endorsed Cross-Cycle Memory direction must not
build on top of broken.

Every premise below was verified against current code on 2026-08-04, not read off
an issue title — the 1.4.3 lesson, now standing. One issue changed shape on
inspection: **#427 is half-fixed already** (its logging half shipped —
`api/runtime/main.py` carries a `#427`-tagged `configure_logging()`, and
application logs are demonstrably live; what remains is the persistence half).

**Hash-stable:** no fix touches the verification contract or interface manifest;
deploy window asserts contract v9 `art_4f368ea08799` / manifest v4
`art_8becd104e9fc` unchanged. **One candidate migration** (the line's only one):
#427's failure-reason field, *if* the column option is chosen over the
checkpoint-payload option at design review. Everything else is code-only
(rollback = image swap).

## The seven fixes (order = build order)

### 1. #427 — failed runs are black boxes (remaining half: persist the terminal reason)

**Premise correction (2026-08-04):** the issue's logging half is already fixed and
live — `docker logs squadops-runtime-api` now carries executor application logs
(verified across the entire 1.4.3 deploy window). What remains: `cycle_runs` has
no failure-reason field (schema verified — nothing between `status` and
`artifact_refs`), so `runs show` still reports a bare `status: failed` and the
run report still says "check task artifacts" even when no task ever started.

**Fix:** persist the terminal failure reason at run finalize (the `finally` path
already holds the exception), surface it in `runs show` and `run_report.md`.
**Design decision at review:** nullable `failure_reason` column on `cycle_runs`
(one additive migration, range 1000–1099) **vs** a terminal checkpoint payload in
the existing `run_checkpoints` table (no migration, but read-side assembly).
Recommendation: the column — the reason is a property of the run, not of
execution progress, and every consumer (`runs show`, report builder, future
analytics) reads the run row anyway.

**Why first:** every later fix's validation cycles get triage-grade failure
reasons, the same enablement logic that put the lease reaper first in 1.4.3.

**Verification:** a designed-failure probe (deliberately dead plan) shows the
exact `CycleError` text in `runs show` and the run report; regression on the
finalize path.

### 2. #426 — planner offers builder tasks the config cannot execute

**Premise re-verified:** `_plan_authoring_service.py:76` still keys the offer off
squad composition alone (`planner_build_task_types(has_builder=has_builder)`);
`generate_task_plan` (`task_plan.py:800`) still — correctly, per #291 — refuses
builder tasks without a configured `build_profile`. `validation` + any
builder-carrying squad still authors plans that pass the gate and die
deterministically at implementation start.

**Fix (both directions from the issue, they are complementary):**
(a) the offer keys off config: builder task types offered only when
`has_builder AND build_profile` — the author is never invited to write an
unsatisfiable task; (b) the gate-time net also checks the requirement, so a plan
that acquires a builder task any other way is rejected where a re-roll costs
minutes. The issue's third question (should `validation` carry a
`build_profile`?) is answered **no** for this line — the profile measures
plan/validation machinery, not assembly; changing its contract is out of scope.

### 3. #715 — plan validation accepts test tasks whose declared artifacts cannot satisfy `tests_pass`

Fresh from the 1.4.3 window (full evidence on the issue: three correction rounds
and ~2h to escape a statically-visible defect, by placebo-artifact sprawl, with
planned coverage silently narrowed under a green verdict).

**Fix:** plan-time check-applicability validation — reject (or force to the gate
as a named finding) any `qa.test` task subject to required `tests_pass` whose
`expected_artifacts` contain no pytest-discoverable file (`test_*.py`). Same
deterministic validator layer as #673's dual-claim net; builds adjacently to
fix 2's gate net (same seam, one PR each, shared test fixtures).

**Explicitly deferred inside the issue:** per-task `not_applicable` skip
semantics for `tests_pass` — it interacts with #423 (a skip that counts as a
pass is exactly the false-green bug) and must ride #423's resolution or later,
not precede it. The repair-loop structural lever (`structural_plan_change_candidate`
is advisory-only) stays 1.5.

### 4. #423 — typed checks skipped-but-counted-as-passed

**Premise re-verified at `handlers/cycle/base.py:455-457`:** `passed` is false
only for `severity=error` + `failed`/`error` status — **every `skipped` outcome
is `passed: true` regardless of reason**, so an authored contract the evaluator
cannot parse (`import_present` on `.tsx`, `field_present` under
`unsupported_stack_or_syntax`) is a free pass and the plan's enforcement surface
silently shrinks.

**Fix:** split skip causes into two accounting classes:
- **benign / non-applicable** — `typed_acceptance_disabled`,
  `command_acceptance_checks_disabled`, and the #605 property class
  (Python-parsing check on a non-Python *target it was never meant for*,
  framework-injected checks skipping out-of-family files). These stay
  non-blocking and out of the unverified roll-up; the #605 registry-wide test
  must still pass untouched.
- **evidence gap** — an *authored* check explicitly targeting a concrete file
  the evaluator cannot parse. Propagates as **unverified** (the
  `cycle_outcome.unverified` shape, reason `evaluator_gap:<skip_reason>`), never
  `passed: true`. Blocking-vs-advisory for `severity: error` eval-gaps is the
  RC-9 matrix decision to settle at design review — recommendation: they join
  `required_unmet` only when the check is contract-bound (`criterion_id` set),
  advisory otherwise.

Also reconciles the #422 polarity note (unsupported command → blocking error vs
unsupported extension → silent pass) by making both land in the same
evidence-gap class.

### 5. #424 — plan-merge fallback silently strips typed acceptance

**Premise re-verified at `_plan_authoring_service.py:295-301`:** manifest
exhaustion still logs a warning and returns `None`, degrading
`typed_acceptance: true` cycles to static steps with no artifact, no gate
surface, no cycle-level flag.

**Fix (issue direction 1 + 2):** for profiles with `typed_acceptance: true` or
`implementation_plan: true`, manifest exhaustion is a **framing failure** — the
run fails at the gate boundary with the last validation error as its reason
(which fix 1 now persists and surfaces), instead of spending a full
implementation run to be caught by the SIP-0096 throttle. A
`plan_authoring_collapsed` evidence artifact records the attempts. Direction 3
(raising the attempt budget for validation profiles) is a config default
decision, taken only if the fail-fast makes exhaustion visible enough to tune.

### 6. #511 — time budget not enforced at correction-chain dispatch

**Premise re-verified + mechanism localized:** the budget is consulted at the
main task-loop boundary (`dispatched_flow_executor.py:1788` — "budget exhausted
after N tasks") but correction-chain dispatches (analyze / decision / repair /
retest) do not pass through that check. shk-4 measured the shape live: round 2
admitted 2 minutes before expiry, then ran 39 minutes past it. The night-roll
evidence (#511) shows a whole chain dispatched *after* expiry.

**Fix:** the budget check gates **every** dispatch decision — main-loop tasks
and correction-chain tasks alike — terminating the run at the first boundary
past expiry with a persisted reason (`time_budget_exhausted`, via fix 1). The
existing semantic ("in-flight work completes; new work does not start") is kept
and documented; what changes is that *no* dispatch lane is exempt.

### 7. #571 — LanceDB search: post-limit filtering + metric mismatch

**Premise re-verified verbatim at `adapters/memory/lancedb.py` `search()`:**
`.limit(N)` runs before namespace/tags/threshold filtering (Python-side), so
in-namespace matches past the first N global rows are starved (can return zero
despite plentiful matches); score is `1.0 - _distance` assuming cosine while the
default metric is L2.

**Fix:** push filters into the query (`.where(..., prefilter=True)` for
namespace + tags) and select the metric explicitly (`.metric("cosine")`) so the
score transform is valid — both standard usage in the pinned lancedb version.
Outside the verdict theme, in the line deliberately: the endorsed Cross-Cycle
Memory SIP builds directly on this adapter and must not inherit these defects.

**Verification:** conformance-style unit tests (namespace starvation repro:
N+1 in-namespace rows behind N out-of-namespace nearer rows) + a live
store/recall smoke.

## Riders (no dedicated PRs)

- None planned. The #426 config question ("should `validation` carry a
  `build_profile`?") is answered inside fix 2 as a no-change decision, recorded
  in the PR body rather than a rider commit.

## Deploy window (after all seven merge)

1. Rebuild all + explicit restart + verify-LOADED behaviorally in-container
   (surfaces: fixes 2–5 live in framing/validation paths — agents + runtime-api;
   fixes 1, 6 in runtime-api; fix 7 in agent images via the memory adapter).
2. Assert contract v9 / manifest v4 unchanged (no re-seed). If the #427 column
   option was chosen: verify the migration applied idempotently at startup.
3. **Designed-failure probe** (fix 1 + 2 + 6 in one throwaway): a cycle
   configured to die (post-fix-2 the #426 repro no longer authors, so use a
   deliberately tiny `time_budget_seconds`) — assert the run terminates at the
   first boundary past expiry, `runs show` carries the persisted reason, and the
   run report echoes it.
4. **Gate-rejection probes** (fixes 2 + 3): replay-based where possible
   (stored shk-4 plan for #715's `.js`-only task shape; a builder-task plan
   against a no-build-profile config for #426) — assert rejection at the
   validator/gate with the named finding, not at implementation start.
5. **Skip-accounting replay** (fix 4): re-evaluate a stored plan with authored
   unparseable-target checks (`cyc_bc325a67417d`'s shape) — assert those rows
   roll up `unverified`/evidence-gap, while shk-4's stored artifacts still
   evaluate green (no benign-skip regression).
6. **One unfiltered confirmation shakedown** (standard seeded launcher, full,
   bind mode, unscored) — proves the new validators and skip accounting don't
   disturb a well-formed roll.
7. Bump 1.4.4 via `version_cli.py` + marker sync + amend this doc as-built + tag.

## Deliberately out

- **#687** (traceback into failure_evidence) and analyzer diagnosis quality —
  cross-component, 1.5.
- **#707** (dual command allowlists) — 1.5.
- **Repair-loop structural lever** (actionable `structural_plan_change`) — 1.5,
  folds into the repair-loop direction.
- **`tests_pass` per-task skip semantics** — deferred inside #715, gated on
  #423's resolution landing first.
- **#668** — hash-moving; still held on the seed-roll window + #670 ruling.
- **The 1.5 refactor population** (#663/#331/#567/#559/#576/#577) and packaging
  (#598/#582/#637) — untouched.

## Ledger

| Issue | Fix | Surface | Verification |
|---|---|---|---|
| #427 | persist terminal failure reason (logging half already shipped) | run finalize + `runs show` + report | designed-failure probe shows exact reason |
| #426 | builder offer keys off config; gate net checks build_profile | plan authoring + gate validator | builder-plan replay rejected at gate |
| #715 | check-applicability validation for `tests_pass` tasks | plan validator layer | shk-4 plan replay rejected with named finding |
| #423 | skip causes split: benign vs evidence-gap → unverified | typed-check aggregation (base.py) | replay: authored unparseable-target rows roll up unverified; #605 test untouched |
| #424 | manifest exhaustion = framing failure + collapse artifact | plan authoring service + gate | exhaustion path fails fast with persisted reason |
| #511 | budget gates every dispatch lane incl. corrections | executor + correction runner | tiny-budget probe terminates at first boundary past expiry |
| #571 | prefilter `.where()` + explicit cosine metric | memory adapter | starvation repro unit test + live recall smoke |

## As built (2026-08-05, amended at the 1.4.4 cut)

Seven fixes, seven PRs, in the planned order: #717 (#427) → #718 (#426) → #719 (#715)
→ #720 (#423) → #721 (#424) → #722 (#511) → #723 (#571). Design decisions ratified at
the plan review held: #427 took the **column** (migration 1010, the line's only one);
#423's error-severity evidence-gaps join `required_unmet` **only when contract-bound**;
`validation` did not gain a `build_profile`.

### Premise corrections found at build time

1. **#427 was half-fixed already** — the logging half had shipped (`configure_logging`
   in the API entrypoint); only the persistence half was built.
2. **#426's two seams**: the executor has TWO gate seams, and multi-workload cycles
   traverse only `_reject_invalid_plan_before_workload_gate` — #718's net initially
   landed on the other one; #719 closed the gap and both the #426 and #715 nets now
   run on both seams.
3. **#423's aggregation was healthier than the issue's era**: SIP-0096 already made
   skips non-creditable at cycle_outcome — the surviving false greens were the
   per-task `passed` flag and the missing required-escalation for contract-bound
   gaps. Also: `frontend_acceptance_checks_disabled` is not config (no such flag
   exists) — it marks the unimplemented JS/TS analyzer and is classified as a gap.
4. **#424's sole-author leg had closed since filing** (exhaustion fails the task
   loudly); the surviving holes were the silent static fallback at dispatch and the
   gate approving a plan-less framing. The planned `plan_authoring_collapsed`
   *artifact* was superseded by the #473 gate-decision recording + #427 persistence.
5. **#511's mechanism localized**: the budget was checked only at the main task-loop
   boundary; the fix gates the CorrectionRunner's single dispatch choke point.

### Deploy-window results (2026-08-05, integration deploy of all seven pre-merge)

- Migration 1010 applied idempotently at first boot; contract v9 / manifest v4
  payload hashes unchanged.
- **In-container replays**: the deployed #715 validator rejects the *stored shk-4
  plan* with the named finding (and passes it when `tests_pass` is not required);
  #426 rejects a builder mutation of the same plan; #423's authored-`.tsx` exhibit
  row reads `passed: false, evidence_gap: true` with the task not failed; **#571
  verified against the agent image's pinned lancedb 0.8.2** (namespace starvation
  repro + exact cosine score) — closing the dev-0.29 vs image-0.8.2 risk.
- **Designed-failure probe** (`cyc_c110af382480`, 60s budget): terminated at the
  first dispatch boundary past expiry; `runs show` surfaces
  `failure_reason: Time budget exhausted (60s) after 1 tasks` (#427 + #511 live).
- **Confirmation shakedown shk-5** (`cyc_07ae691af9d6`): **green — verdict
  `accepted`, zero failed, zero unverified, zero correction rounds**; a compliant
  6-task plan on the first framing roll (both qa tasks pytest-discoverable); the
  new nets silent throughout — no false reds on a well-formed roll; 9/9 leases
  released, zero lifecycle residue.

### Filed forward

- **#724** — `time_budget_seconds` (and siblings) read from `applied_defaults`
  directly, bypassing `Cycle.resolved_config()`; an `execution_overrides` budget is
  silently ignored. The #426 class; sweep the executor's direct reads with the fix.
