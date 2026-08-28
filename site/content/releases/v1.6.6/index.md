---
title: v1.6.6
---

# v1.6.6

**Released 2026-08-28** · [tag `v1.6.6`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.6.6)

**The React-arm patch line.** Six fixes built from the 1.6.5 FastAPI+React rejections — the
nullable-field emission, the harness cleanup, the passing retest stored, a stack-aware
self-mocking check, a refused patch not counted as a round, and one request-body resolver — and
its evidence is the second two-stack pre-registered set, sized six where the fixes came from and
two where they were not supposed to reach.

### The evidence

Two counting sets on frozen deploy `e14a6ad4` —
`docs/plans/1-6-6-verification-set-record.md`, pre-registered before roll 1 (PR #1142, merged as
`873f4e50`; §2 completed by #1143 as `2448f5d1`, the HEAD pin) and unchanged throughout,
launched only from `main`, executed under delegation. **Eight counted rolls, no voids, no
resets; every pre-registered prediction held wherever a roll exercised it; the early stop never
fired. Zero code drift between the measured deploy and the tag.**

- **FastAPI+React: 4 of 6 (95% CI 30–90%)** against the 1.6.5 baseline of 2 of 6 — texture, no
  significance claimed at N=6. Two greens clean, **two by repair, none by re-dispatch.** The
  nullable-field fix was exercised on the three rolls whose manifest wrote `default: null` and
  held on all three (five of six such rolls opened with a 500 in 1.6.5); no report failed
  "Found multiple elements"; the refused-patch rule fired on two rolls and no run ended after
  zero applied repairs; the passing retest's report was what the task stored, twice. Both
  rejections are the same class and not a pack item: a free-authored qa suite asserting
  something the contract never said, a correct dev repair rejected by it, no route to the qa
  file (#1153 filed, #1130 and #1123 evidenced) — roll 6's application passed every contract
  probe.
- **Next.js+TS: 2 of 2** — zero correction rounds, fills first on every emission, no cap hit;
  the pack did not reach the stack it was not supposed to reach.

### 1.6.6 line — the React arm's round-0 defects (plan: `docs/plans/1-6-6-plan.md`)

- **A — an optional entity field freezes nullable** (#1125). A manifest field declared
  `required: false, default: null` froze as `distance: str = None` — a non-nullable annotation
  with a `None` default — because the declared null set `has_default` and the nullable branch
  only fired when no default key existed; the request shape was correctly `str | None`, so the
  route forwarded the request's `None` into the entity and pydantic answered 500 on POST /runs.
  Five of the six FastAPI+React rolls in the previous set opened with that failure; the three
  manifests that omitted the key were clean. The rule now: a declared null default and an
  optional field with no default both freeze `X | None = None`; a non-null default keeps
  `X = default`. Python emitter only — the TS emitter renders `distance?: string` and is
  untouched; every pinned fixture (the Next.js reference scaffold, the stack-#1 contract
  reference, the context goldens) is byte-identical.
- **B — the frozen React test harness unmounts between tests** (#1127). `test-setup.js`
  registers `afterEach(cleanup)`: under vitest's default `globals:false` Testing Library never
  auto-registers it, so any suite that renders in more than one test failed "Found multiple
  elements" unless the author added the line — the one suite that did was green. Moves the
  stack-#1 contract reference (v10 → v11, `reference_defect` per the M0 taxonomy: a harness
  that can only reject a working app, never pass a broken one, so the 1.4 figure carries no
  qualification) and the three context goldens' `frozen_surface_index` line for that file.
- **F — the passing retest is what the qa task stores** (#1111). An accepted patch re-stored
  the failed result's artifacts overlaid with the repair, so the failed run's `test_report.md`
  and typed-check evaluation landed under the task id seconds *after* the retest banked its
  passing report under its own — and on FastAPI+React roll 1 the next analysis read the
  failure and sent a repair at a file the loop had already fixed. Evidence artifacts in the
  re-store are now replaced by the passing retest's same-named artifact or dropped; work
  product is untouched and the retest's own suite files stay under the retest id.
- **C — "invokes the application" is the stack's own definition** (#1126). The
  self-mocking detector defined it as an `app/api/` import — the Next.js in-process model —
  inside a shared module, and failed a green FastAPI+React suite that rendered the real `App`
  with `fetch` stubbed while passing the one that `vi.mock`ed the app's own API client. Each
  `ScaffoldStack` now declares an `AppInvocation` (the import that proves the app is invoked,
  the mock that replaces the subject, the mock that replaces the network seam) in a leaf
  module; the detector only applies it, resolved through `app_invocation_for` beside
  `check_stack_for`. On React a rendered component or `App` invokes the app and a `fetch`
  stub or `api.js` mock under it is legitimate; mocking a view or `App` module is mocking
  the subject. An unregistered stack is judged not at all and its row is banked with an
  empty inspected inventory, never as clean. The discarded roll-1 suite is the replay test.
- **D — a refused repair patch is not a correction round** (#1129). When patch
  verification refused a repair nothing was applied and no retest ran, but the failed task
  re-ran against the unrepaired tree, its signature repeated by construction, and the
  progress-aware terminal read that as "the repair did not help" — two FastAPI+React rolls
  ended `plan_defect` after zero applied repairs, one of them holding the correct fix. A
  refused round now clears chain adjacency the way an infra round does (the attempt cap
  still bounds a repair that keeps being refused); the executor's refusal entry and the
  runner's reading of it share one marker. `endpoint_defined` resolves `APIRouter(prefix=…)`
  so a prefixed router serves the declared paths instead of failing a literal-path check,
  and the repair brief (v6) says to keep the router construction, decorators and handler
  names as they are — a rewrite is refused before it is tested.
- **E — an endpoint's request body has one resolver** (#1128). Manifest validation accepts
  a `request:` that names a declared shape *or an entity*; the contract generator resolved
  probe bodies only through `request_shapes`, so an entity-typed request shipped `json: {}`
  expecting 201 then 409 from a route whose payload class required `name` — unsatisfiable by
  construction, and the loop rightly called it `plan_defect`. `InterfaceManifest.request_body_fields`
  now answers for both (a shape's `required`; an entity's required, non-generated,
  undefaulted fields) and every probe-body site reads it. The route emitter no longer takes
  the entity class itself as the payload — its generated `id` is required, so it could never
  accept that body — but a synthesized `{Entity}Body` model shaped by the same resolver,
  with `NonBlankStr` required fields so the blank-input probe applies as it does to a
  declared shape. Pinned reference output (declared shapes throughout) is byte-identical.

## Merged pull requests (11)

| PR | Title | Closes |
|---|---|---|
| [#1154](https://github.com/backspring-labs/squad-ops/pull/1154) | chore(release): 1.6.6 — the React-arm patch line, measured on both stacks | — |
| [#1146](https://github.com/backspring-labs/squad-ops/pull/1146) | docs(plan): 1.7.0 plan rev 2 — stabilization packs (Reasoning, Stack Seams, Loop Honesty, Boundaries, Composition Root, Hardening), 83 open issues placed | — |
| [#1143](https://github.com/backspring-labs/squad-ops/pull/1143) | docs(plan): 1.6.6 pre-registration §2 — both shakeouts from main read; driver refused-patch readout per task | — |
| [#1142](https://github.com/backspring-labs/squad-ops/pull/1142) | docs(plan): pre-register the 1.6.6 sets (4+4) + driver readouts R1/R2/R4/R5 + pinned set configs | — |
| [#1141](https://github.com/backspring-labs/squad-ops/pull/1141) | fix(scaffold): an endpoint's request body has one resolver; an entity-typed request gets a body model (#1128) | [#1128](https://github.com/backspring-labs/squad-ops/issues/1128) |
| [#1140](https://github.com/backspring-labs/squad-ops/pull/1140) | fix(correction): a repair patch refused by patch verification is not a correction round (#1129) | [#1129](https://github.com/backspring-labs/squad-ops/issues/1129) |
| [#1139](https://github.com/backspring-labs/squad-ops/pull/1139) | fix(qa): the self-mocking detector judges through the stack's own definition of invoking the app (#1126) | [#1126](https://github.com/backspring-labs/squad-ops/issues/1126) |
| [#1138](https://github.com/backspring-labs/squad-ops/pull/1138) | fix(correction): the passing retest's evidence is what the repaired task stores (#1111) | [#1111](https://github.com/backspring-labs/squad-ops/issues/1111) |
| [#1137](https://github.com/backspring-labs/squad-ops/pull/1137) | fix(scaffold): the frozen React test harness registers afterEach(cleanup) (#1127) | [#1127](https://github.com/backspring-labs/squad-ops/issues/1127) |
| [#1136](https://github.com/backspring-labs/squad-ops/pull/1136) | fix(scaffold): an optional entity field with a declared null default freezes nullable (#1125) | [#1125](https://github.com/backspring-labs/squad-ops/issues/1125) |
| [#1134](https://github.com/backspring-labs/squad-ops/pull/1134) | docs(release): capture the v1.6.5 release package | — |

## Cycle evidence

### `cyc_cdf91361702b`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_4f6d873561a2`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_38d1e1689766`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs-leave, tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_ac15b6c6209f`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_ae0631fddfc5`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_0c4664c2ae9a`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:regex_match, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_68b0e1769526`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_06987a951236`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |
