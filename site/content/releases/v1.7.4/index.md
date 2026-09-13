---
title: v1.7.4
---

# v1.7.4

**Released 2026-09-09** · [tag `v1.7.4`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.7.4)

**The recovery half — the fourth patch line of 1.7.** Plan: `docs/plans/1-7-4-plan.md` (rev 3).
Record: `docs/plans/1-7-4-verification-set-record.md`.

Ten pack rows on the recovery path, and the request that fed it. The retired `qa_handoff.md`
leaves the framework *and* the request: #1312/#1254 replace it with optional assembly notes and a
consumer contract, and #1430 finishes SIP-0098 §6.7 by stopping the group_run PRD naming it in
seven places — a document the framework had dropped and the request kept demanding, so the framing
role wrote it into every definition of done. Framework rows are owed by contract rather than by
task (#1374); the builder retries a contentless emission *with its fact* (#1372); a rewind is not
a repair (#994); the locus classifier answers by task-type property (#1054); an accepted repair is
not disputed by the classifier that preceded it (#936/#933); and a capability with two output
shapes declares one reasoning level per shape (#1285).

Validated by a pre-registered two-set verification run on frozen deploy `dfe9a6f2` (HEAD pinned at
`be2e9dea`), **zero image drift across all nine rolls**. FastAPI+React **4 of 6** functional;
Next.js+TS **3 of 3**. **Functional App Yield 7 of 9, zero human interventions.** Every accepted
roll credited all of its criteria; no roll anywhere carried an unevidenced criterion; both
rejections named the criterion they lost.

**The line's bar was amended before the set opened, not after.** L1 breached in the shakeouts, and
the owner's ruling — recorded as the pre-registration's sixth §3a entry — split it: blocking on a
contentless emission that is *not recovered*, tracked otherwise. The set read **7 contentless of
160 emissions**, all seven on one Next.js roll that recovered fully through five correction rounds
to accepted, 16/16, functional. No counted roll was lost to one.

Stated at the cut, not implied: **the diagnostics were not re-run on the pinned deploy** (plan step
10), so L2, L4, L7, L8 and A1 were proven on earlier deploys and not on the one the numbers come
from — the experimental gate is amended on the owner's ruling, and the record §4 names exactly what
is and is not covered. R1 and D1, the two invariants the pack could plausibly have regressed, both
have live readings on the pinned deploy. #1406 recurred on one roll, demoting nothing, and that
roll's coverage figure is never quoted as whole.

The instrument was fixed five times while the line ran, each time because a readout could not tell
*did not happen* from *could not be asked*: three loaded-check probes had never run and recorded
like probes that answered (#1425); a field counted artifacts and called them emissions (#1431, and
the first fix for it was falsified within the hour and reverted, #1436); and the driver, which
imports framework modules to judge P0 and B1, could have judged a roll with code the deploy never
ran (#1438 — `frozen_deploy_commit` had been typed and read by nothing).

## Merged pull requests (33)

| PR | Title | Closes |
|---|---|---|
| [#1416](https://github.com/backspring-labs/squad-ops/pull/1416) | sip(0106): §1.2f — the diagnosis is not established, and the record does not claim it | — |
| [#1409](https://github.com/backspring-labs/squad-ops/pull/1409) | docs(1.7.4): §6a re-places the seven unnamed issues; SIP-0106 gains §1.2e/§1.2f and is promoted to implemented | — |
| [#1404](https://github.com/backspring-labs/squad-ops/pull/1404) | docs(1.7.4): pre-registration — the 1.7.3 re-runs on deploy A | — |
| [#1403](https://github.com/backspring-labs/squad-ops/pull/1403) | instrument(driver): the A1 echoes are the claim's own phrases | — |
| [#1402](https://github.com/backspring-labs/squad-ops/pull/1402) | instrument(driver): the log window is bounded at both ends; foreign affected_task_types are D1's texture | — |
| [#1400](https://github.com/backspring-labs/squad-ops/pull/1400) | docs(1.7.4): pre-registration draft (pins blank) with deploy A and the first diagnostic; plan rev 4 | — |
| [#1401](https://github.com/backspring-labs/squad-ops/pull/1401) | instrument(driver): the A1 readout sees the claim's substance, not only its marker (#968) | — |
| [#1397](https://github.com/backspring-labs/squad-ops/pull/1397) | ops: runtime-api log hygiene — the audit sink apart, milestone heartbeats, httpx quiet (#560) | [#560](https://github.com/backspring-labs/squad-ops/issues/560) |
| [#1398](https://github.com/backspring-labs/squad-ops/pull/1398) | instrument(driver): F1's field — the framework rows the accepted-patch path re-derived (#1374) | — |
| [#1399](https://github.com/backspring-labs/squad-ops/pull/1399) | docs(1.7.4): the two counting set configs, pins empty until pre-registration | — |
| [#1393](https://github.com/backspring-labs/squad-ops/pull/1393) | deps: refresh ci-constraints.txt and the locks (2026-09-08, #1204) | [#1204](https://github.com/backspring-labs/squad-ops/issues/1204) |
| [#1396](https://github.com/backspring-labs/squad-ops/pull/1396) | ops: the Prefect notification service off; loop-service overruns read per cycle (#330) | — |
| [#1395](https://github.com/backspring-labs/squad-ops/pull/1395) | ops: re-sync the realm exports into existing Keycloak realms at deploy (#372) | — |
| [#1394](https://github.com/backspring-labs/squad-ops/pull/1394) | feat(prompts): an agent refuses to boot against a registry that lacks an asset its image ships (#352) | — |
| [#1392](https://github.com/backspring-labs/squad-ops/pull/1392) | refactor(api): domain errors become the standard envelope in one place (#576) | [#576](https://github.com/backspring-labs/squad-ops/issues/576) |
| [#1391](https://github.com/backspring-labs/squad-ops/pull/1391) | fix(persistence): one asyncpg pool factory with the JSON codecs; the parse_jsonb / json.dumps scatter retired (#577) | [#577](https://github.com/backspring-labs/squad-ops/issues/577) |
| [#1390](https://github.com/backspring-labs/squad-ops/pull/1390) | ci: a scheduled, dispatchable dependency refresh (#1204) | — |
| [#1389](https://github.com/backspring-labs/squad-ops/pull/1389) | fix(cycles): graphlib for the plan-DAG check; the authored order must honour depends_on (#578) | [#578](https://github.com/backspring-labs/squad-ops/issues/578) |
| [#1388](https://github.com/backspring-labs/squad-ops/pull/1388) | ops: compose healthchecks and `up -d --wait` replace the deploy script's sleep-and-poll (#581) | [#581](https://github.com/backspring-labs/squad-ops/issues/581) |
| [#1387](https://github.com/backspring-labs/squad-ops/pull/1387) | fix(config): the orchestrator's per-task wait is its own setting (#1147) | [#1147](https://github.com/backspring-labs/squad-ops/issues/1147) |
| [#1386](https://github.com/backspring-labs/squad-ops/pull/1386) | fix(migrations): a session advisory lock around the migration loop (#300) | [#300](https://github.com/backspring-labs/squad-ops/issues/300) |
| [#1385](https://github.com/backspring-labs/squad-ops/pull/1385) | fix(health): parse the AMQP URL with urllib and let httpx own basic auth (#574) | [#574](https://github.com/backspring-labs/squad-ops/issues/574) |
| [#1384](https://github.com/backspring-labs/squad-ops/pull/1384) | fix(audit): the boot audit keeps the response it judged (#1324) | [#1324](https://github.com/backspring-labs/squad-ops/issues/1324) |
| [#1383](https://github.com/backspring-labs/squad-ops/pull/1383) | fix(lineage): real trace context and whole ids, no placeholders or truncated uuids (#575) | [#575](https://github.com/backspring-labs/squad-ops/issues/575) |
| [#1382](https://github.com/backspring-labs/squad-ops/pull/1382) | ci: dependency vulnerability audit against the lock files the images install (#1205) | [#1205](https://github.com/backspring-labs/squad-ops/issues/1205) |
| [#1381](https://github.com/backspring-labs/squad-ops/pull/1381) | test(agents): the identity-permutation test over the roster (#1373) | [#1373](https://github.com/backspring-labs/squad-ops/issues/1373) |
| [#1380](https://github.com/backspring-labs/squad-ops/pull/1380) | fix(release-package): SIP moves are frontmatter status transitions; a PR is listed once (#1369) | [#1369](https://github.com/backspring-labs/squad-ops/issues/1369) |
| [#1379](https://github.com/backspring-labs/squad-ops/pull/1379) | instrument(faults): contentless-builder and false-source-claim faults at the builder's and analyzer's seams (1.7.4 plan §3.1) | — |
| [#1378](https://github.com/backspring-labs/squad-ops/pull/1378) | instrument(driver): B1 and R1 as record fields (1.7.4 plan §3.1) | — |
| [#1377](https://github.com/backspring-labs/squad-ops/pull/1377) | ci: integration is a required status check (1.7.4 plan §3.1) | — |
| [#1375](https://github.com/backspring-labs/squad-ops/pull/1375) | docs(1.7.4): plan rev 3 — the recovery-half line: two strata, three gates, no fault no prediction | — |
| [#1371](https://github.com/backspring-labs/squad-ops/pull/1371) | docs(release): the v1.7.3 package carries every cycle the record cites, each with its role | — |
| [#1370](https://github.com/backspring-labs/squad-ops/pull/1370) | docs(release): capture the v1.7.3 release package | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0106-Atlas-Provider-Adapter](../../design/sips/SIP-0106-Atlas-Provider-Adapter.md) | accepted | implemented |

## Improvement proposals amended in place

No lifecycle change — each was edited under the status it already had (a post-acceptance amendment, CLAUDE.md step 5a).

| Proposal | Status |
|---|---|
| [SIP-0071-Builder-Role-Dedicated-Product](../../design/sips/SIP-0071-Builder-Role-Dedicated-Product.md) | implemented |
| [SIP-0072-Stack-Aware-Development-Capabilities](../../design/sips/SIP-0072-Stack-Aware-Development-Capabilities.md) | implemented |
| [SIP-0102-Ephemeral-Application-Sandbox](../../design/sips/SIP-0102-Ephemeral-Application-Sandbox.md) | accepted |

## Cycle evidence

### `cyc_a17ee1347743`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_e4e818ee8196`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:container_packaging, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs-seed |
| Required unmet | — |
| Never executed | — |

### `cyc_ece3e9d2f3c8`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_cdf3c674a49a`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_e60b855d0e7a`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_08117e841446`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-leave-duplicate, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_a142ccb92b6a`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-leave-duplicate, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_153ef2eaace5`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:container_packaging, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_4f2693c9f281`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:container_packaging, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_69d34bc41c20`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:container_packaging, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_c45d60c9eb16`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_057c598c10de`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:assertion_kinds_match, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-runs-rejects-blank |
| Failed | vc-probe-runs, vc-probe-runs-participants, vc-probe-runs-participants-duplicate, tests_pass |
| Required unmet | — |
| Never executed | — |
