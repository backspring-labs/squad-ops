---
title: v1.7.3
---

# v1.7.3

**Released 2026-09-07** · [tag `v1.7.3`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.7.3)

**Boundaries — the third patch line of 1.7.** Plan: `docs/plans/1-7-3-plan.md` (rev 4). Record:
`docs/plans/1-7-3-verification-set-record.md`.

Validated by a pre-registered two-set verification run on frozen deploy `933aed95` (HEAD pinned
at `dcf69d3e`), **zero code drift between the deploy and the tag** — `933aed95..dcf69d3e` is the
pinned pre-registration under `docs/`, and the tag adds only the record and the release commit.
FastAPI+React **5 of 6** functional (roll 1 rejected for the builder's own omission of the
handoff, #1312's shape, declared before roll 1); Next.js+TS **3 of 3**. **The line's bar
held: 0 contentless qa first attempts across 163 emissions.** One counted roll was void before
the set restarted (#1364, §0 of the record). Every diagnostic seam was reached on the pinned
deploy's predecessor (deploy C = D minus #1364), and the record says which.

### The list — sixteen items, every one CI-verified

**Preconditions (4).** #1316 the regression gate runs all of `tests/unit` with a reasoned
exclusion list and a coverage guard. #1311/#1330 L8 read as two claims and every banked log line
the whole fact. #1310 fault scope — the absent-suite fault applies to every emission attempt and
a diagnostic is read by the seam it reached. #1323 write grants enforced where the executor admits
producer bytes into a tree it evaluates.

**The structural block (8).** #922 `capability_id` → `task_type`, `dev_capability` →
`development_profile`, with a retired-spellings guard. #559 `TaskType` — strings at the boundary,
constants at the core, properties over identity, tables over chains; a task-type literal outside
the enum fails CI. #377 `RunStatus` is the run's only status vocabulary inward of the Prefect
adapter. #381 `TaskResult.status` is the enum, normalised at the wire; the enum-shadow guard scans
`adapters/`. #1241 the dead ACI executor deleted. #154 the boundary guard covers every package with
declared composition roots; the NoOp observability port is a domain null object; the secrets
factory leaves the config loader. #218 `docs/architecture/api-route-lanes.md` — three lanes, no
v2, enforced by a test that enumerates every registered router. #219 the chat routes on `/api/v1`.

**The behavioural block (5).** #305 `network_status` retired — the heartbeat verdict is computed,
never stored (migration 1150). #225 the comms agent is `joi`. #999 `fill_merge_evidence.json`
beside `test_report.md`. #1087/#1112 the store hands the qa author root tables only, on both
stacks; projections by field containment.

**Added under the line's delegation (3, plan rev 4 §9).** #1351 the router restore re-homes the
route paths it strips a prefix from — half a statement was a file FastAPI refuses. #1359
`assertion_kinds_match` reads a `typeof` assertion by its literal's value — a correct Next.js
suite had been refused every round. #1364 the accepted patch of a contentless builder attempt
still gets its `required_files` row — the roll-up had read a booting app as `blocked_unverified`.

### What the line found

Nothing attributable to the sixteen items. Seven defects in the harness and its instrument, each
fixed on the line: #1347 the emission-retry marker rode every later dispatch; #1350 a repair's
grants were the failed task's, not the repairing step's; #1352 the Python own-frame fault was a
`NameError` the emission seam's own check refused — L7 on a pytest suite had never been exercised;
the driver's L4 readout was wired to the #1129 exclusion, not the refund (#1362); migration 1150
altered a table only `init.sql` creates, and main's integration job was red for six merges before
it was read (#1357, with a guard that a migration may only alter a table a migration creates).

### Instrument

The driver reads a diagnostic by the seam it reached (`seam_reached`), carries `refunded_rounds`,
`placeholder_strips`, `stored_under_placeholder`, `emission_tokens_by_handler` and
`fill_merge_evidence`; a driver-only fix re-renders a kept record from its stored identity.

## Merged pull requests (36)

| PR | Title | Closes |
|---|---|---|
| [#1368](https://github.com/backspring-labs/squad-ops/pull/1368) | chore(release): 1.7.3 — Boundaries | — |
| [#1367](https://github.com/backspring-labs/squad-ops/pull/1367) | docs(1.7.3): the verification set record — nine counted, eight functional, L1 held, nothing attributable to the list | — |
| [#1366](https://github.com/backspring-labs/squad-ops/pull/1366) | docs(1.7.3): the pins move to deploy D (933aed95) after the void roll 1; D's pair clean on the exit rule | — |
| [#1365](https://github.com/backspring-labs/squad-ops/pull/1365) | fix(executor): the accepted patch of a contentless builder attempt still gets its required_files row (#1364) | [#1364](https://github.com/backspring-labs/squad-ops/issues/1364) |
| [#1363](https://github.com/backspring-labs/squad-ops/pull/1363) | docs(1.7.3): pre-registration §3 — the three diagnostics on the pinned deploy, every seam reached; the L4 readout corrected and re-rendered | — |
| [#1362](https://github.com/backspring-labs/squad-ops/pull/1362) | fix(driver): L4 is read from the executor's refund, not from the #1129 exclusion | — |
| [#1361](https://github.com/backspring-labs/squad-ops/pull/1361) | docs(1.7.3): the pre-registration, pinned — deploy C (23c6a0ae) is the frozen deploy; the shakeout loop exited on its first pair | — |
| [#1360](https://github.com/backspring-labs/squad-ops/pull/1360) | fix(checks): assertion_kinds_match reads a typeof assertion by its literal's value — a correct Next.js suite was refused every round (#1359) | [#1359](https://github.com/backspring-labs/squad-ops/issues/1359) |
| [#1358](https://github.com/backspring-labs/squad-ops/pull/1358) | fix(scaffold): the router restore re-homes the route paths it strips a prefix from — half a statement is a file FastAPI refuses (#1351) | [#1351](https://github.com/backspring-labs/squad-ops/issues/1351) |
| [#1357](https://github.com/backspring-labs/squad-ops/pull/1357) | fix(migrations): 1150 tolerates an absent agent_status — the table is init.sql's, not a migration's | — |
| [#1356](https://github.com/backspring-labs/squad-ops/pull/1356) | docs(1.7.3): the #1087 loaded check runs on the runtime-api, not the builder image; deploy B's images recorded | — |
| [#1355](https://github.com/backspring-labs/squad-ops/pull/1355) | fix(fault-injection): the Python own-frame fault is an argument-binding TypeError that passes the emission seam (#1352) | [#1352](https://github.com/backspring-labs/squad-ops/issues/1352) |
| [#1354](https://github.com/backspring-labs/squad-ops/pull/1354) | fix(correction): a repair's write grants are the repairing step's, named on every repair artifact (#1350) | [#1350](https://github.com/backspring-labs/squad-ops/issues/1350) |
| [#1353](https://github.com/backspring-labs/squad-ops/pull/1353) | docs(1.7.3): the set configs and the pre-registration draft — pins blank until the last shakeout (merged under the wrong title; see body) | — |
| [#1349](https://github.com/backspring-labs/squad-ops/pull/1349) | docs(1.7.3): plan rev 3 — the decisions taken at the line's opening under delegation, recorded | — |
| [#1348](https://github.com/backspring-labs/squad-ops/pull/1348) | fix(executor): the emission-retry marker rides one dispatch — a correction re-take is not an emission retry | [#1347](https://github.com/backspring-labs/squad-ops/issues/1347) |
| [#1346](https://github.com/backspring-labs/squad-ops/pull/1346) | fix(scaffold): the frozen store hands the qa author root tables only — shapes and projections get none, on both stacks | [#1087](https://github.com/backspring-labs/squad-ops/issues/1087) [#1112](https://github.com/backspring-labs/squad-ops/issues/1112) |
| [#1344](https://github.com/backspring-labs/squad-ops/pull/1344) | fix(config): the comms agent's id is joi — the one agent whose id diverged from its persona and service | [#225](https://github.com/backspring-labs/squad-ops/issues/225) |
| [#1345](https://github.com/backspring-labs/squad-ops/pull/1345) | fix(qa): the fill-merge evidence is persisted — an artifact beside test_report.md, read by the record | [#999](https://github.com/backspring-labs/squad-ops/issues/999) |
| [#1343](https://github.com/backspring-labs/squad-ops/pull/1343) | refactor(health): network_status is retired — the heartbeat verdict is computed, never stored; runtime_status is the only health source | [#305](https://github.com/backspring-labs/squad-ops/issues/305) |
| [#1342](https://github.com/backspring-labs/squad-ops/pull/1342) | refactor(api): the console messaging routes are on /api/v1 — moved in lockstep through Caddy, the BFF and the plugin | [#219](https://github.com/backspring-labs/squad-ops/issues/219) |
| [#1341](https://github.com/backspring-labs/squad-ops/pull/1341) | docs(api): the runtime-api URL surface has an owning standard — lanes, no v2, and a test that holds every route to it | [#218](https://github.com/backspring-labs/squad-ops/issues/218) |
| [#1340](https://github.com/backspring-labs/squad-ops/pull/1340) | refactor(boundary): adapters are imported only from the composition roots — the guard covers every package | [#154](https://github.com/backspring-labs/squad-ops/issues/154) |
| [#1339](https://github.com/backspring-labs/squad-ops/pull/1339) | fix(adapters): delete the dead ACI executor — the capabilities adapter package imports again | [#1241](https://github.com/backspring-labs/squad-ops/issues/1241) |
| [#1338](https://github.com/backspring-labs/squad-ops/pull/1338) | refactor: TaskResult.status is TaskResultStatus — one typed vocabulary, normalized at the wire | [#381](https://github.com/backspring-labs/squad-ops/issues/381) |
| [#1337](https://github.com/backspring-labs/squad-ops/pull/1337) | refactor: RunStatus is the run's only status vocabulary — Prefect's state is the adapter's translation | [#377](https://github.com/backspring-labs/squad-ops/issues/377) |
| [#1336](https://github.com/backspring-labs/squad-ops/pull/1336) | refactor: task-type identifiers — strings at the boundary, constants at the core, properties over identity | [#559](https://github.com/backspring-labs/squad-ops/issues/559) |
| [#1335](https://github.com/backspring-labs/squad-ops/pull/1335) | refactor: "capability" means bindable agent competence — the task type and the development profile renamed for what they are | [#922](https://github.com/backspring-labs/squad-ops/issues/922) |
| [#1334](https://github.com/backspring-labs/squad-ops/pull/1334) | fix(driver): every emission's tokens by handler — the qa-token texture gets a producer | — |
| [#1333](https://github.com/backspring-labs/squad-ops/pull/1333) | fix(faults): a fault declares the scope of "once", and a diagnostic is read by the seam it reached | [#1310](https://github.com/backspring-labs/squad-ops/issues/1310) |
| [#1332](https://github.com/backspring-labs/squad-ops/pull/1332) | fix(executor): a producer's write grants are enforced where its bytes enter a tree the loop evaluates | [#1323](https://github.com/backspring-labs/squad-ops/issues/1323) |
| [#1331](https://github.com/backspring-labs/squad-ops/pull/1331) | fix(driver): L8 read from the extractor's strips, and every banked log line is the fact, not a window | [#1311](https://github.com/backspring-labs/squad-ops/issues/1311) [#1330](https://github.com/backspring-labs/squad-ops/issues/1330) |
| [#1329](https://github.com/backspring-labs/squad-ops/pull/1329) | fix(gate): the regression gate runs tests/unit whole — exclusions are named with reasons | [#1316](https://github.com/backspring-labs/squad-ops/issues/1316) |
| [#1317](https://github.com/backspring-labs/squad-ops/pull/1317) | docs(1.7.3): the Boundaries release — the CI-verified list as the line's subject | — |
| [#1328](https://github.com/backspring-labs/squad-ops/pull/1328) | docs(release): capture the v1.7.2 release package | — |
| [#1328](https://github.com/backspring-labs/squad-ops/pull/1328) | docs(release): capture the v1.7.2 release package | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0058-Capability-Contracts-Reference-Workloads](../../design/sips/SIP-0058-Capability-Contracts-Reference-Workloads.md) | new | implemented |
| [SIP-0072-Stack-Aware-Development-Capabilities](../../design/sips/SIP-0072-Stack-Aware-Development-Capabilities.md) | new | implemented |
| [SIP-0085-Console-Messaging-Capability-for](../../design/sips/SIP-0085-Console-Messaging-Capability-for.md) | new | implemented |

## Cycle evidence

### `cyc_597f5cb76fb2`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | required_files, acceptance:sections_present |
| Required unmet | — |
| Never executed | — |

### `cyc_4acd6ce64ca1`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_ce33e6a1da5f`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_b9961579f33b`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_52a2c7438d12`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:count_at_least, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_3270c790620e`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_2dfbb0f1af81`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_5cb087956ba9`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_57cdbad02f67`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |
