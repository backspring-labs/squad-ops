---
title: v1.1.0
---

# v1.1.0

**Released 2026-06-28** · [tag `v1.1.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.1.0)

## Merged pull requests (129)

| PR | Title | Closes |
|---|---|---|
| [#252](https://github.com/backspring-labs/squad-ops/pull/252) | chore(release): 1.1.0 — Agent Runtime State (SIP-0089) + 1.0.x hardening | — |
| [#251](https://github.com/backspring-labs/squad-ops/pull/251) | fix(api): enforce cycles:read/write scopes on cycle routes (#150) | [#150](https://github.com/backspring-labs/squad-ops/issues/150) |
| [#249](https://github.com/backspring-labs/squad-ops/pull/249) | fix(cycles): propagate cycle/run cancel to Prefect (#77) | [#77](https://github.com/backspring-labs/squad-ops/issues/77) |
| [#248](https://github.com/backspring-labs/squad-ops/pull/248) | SIP-0089 Phase 4: RuntimeActivity | — |
| [#247](https://github.com/backspring-labs/squad-ops/pull/247) | fix(handlers): stop in-place mutation of frozen HandlerResult in planning retry (#155) | [#155](https://github.com/backspring-labs/squad-ops/issues/155) |
| [#246](https://github.com/backspring-labs/squad-ops/pull/246) | test(comms): regression tests for RabbitMQ channel recovery (#146) | — |
| [#243](https://github.com/backspring-labs/squad-ops/pull/243) | fix(tests): integration config — env precedence + creds match the stack (#209) | [#209](https://github.com/backspring-labs/squad-ops/issues/209) |
| [#241](https://github.com/backspring-labs/squad-ops/pull/241) | fix(tests): repair test_pulse_check_e2e.py — event loop + 3 stale-API layers (#211) | [#211](https://github.com/backspring-labs/squad-ops/issues/211) |
| [#238](https://github.com/backspring-labs/squad-ops/pull/238) | test(ci): add tests/unit/adapters/ to the regression gate (#207) | [#207](https://github.com/backspring-labs/squad-ops/issues/207) |
| [#240](https://github.com/backspring-labs/squad-ops/pull/240) | style+ci: repo-wide ruff format sweep + enforce format gate (#196) | [#196](https://github.com/backspring-labs/squad-ops/issues/196) |
| [#236](https://github.com/backspring-labs/squad-ops/pull/236) | fix(bootstrap): standardize local dev + CI on Python 3.12 (#217) | — |
| [#235](https://github.com/backspring-labs/squad-ops/pull/235) | SIP-0089 Phase 3: Focus Lease | — |
| [#232](https://github.com/backspring-labs/squad-ops/pull/232) | fix(deps): make the postgres extra truly optional — TYPE_CHECKING-guard sqlalchemy in ports/db.py (#206) | — |
| [#229](https://github.com/backspring-labs/squad-ops/pull/229) | fix(deps): declare sqlalchemy and python-jose (unblock unit collection) | [#206](https://github.com/backspring-labs/squad-ops/issues/206) |
| [#228](https://github.com/backspring-labs/squad-ops/pull/228) | SIP-0089: mirror offline runtime_status in reconciliation so the duty guard sees dead agents (#159) | [#159](https://github.com/backspring-labs/squad-ops/issues/159) |
| [#227](https://github.com/backspring-labs/squad-ops/pull/227) | SIP-0089 §2.4: activate the in-process duty scheduler (+ close-sweep fix, #226) | [#226](https://github.com/backspring-labs/squad-ops/issues/226) |
| [#221](https://github.com/backspring-labs/squad-ops/pull/221) | SIP-0089 Phase 2 — Agent Runtime State (assignments, scheduler, coordinator, reserve guard) | [#220](https://github.com/backspring-labs/squad-ops/issues/220) |
| [#215](https://github.com/backspring-labs/squad-ops/pull/215) | sip: propose Duty Continuity & Handoff Ledger (DutyLog) | — |
| [#214](https://github.com/backspring-labs/squad-ops/pull/214) | chore(release): bump to v1.0.6 + document SIP-0094 | — |
| [#213](https://github.com/backspring-labs/squad-ops/pull/213) | sip: promote SIP-0094 → implemented (per-agent reply queues) | — |
| [#212](https://github.com/backspring-labs/squad-ops/pull/212) | SIP-0094 94.3: ReplyRouter cutover — _publish_and_await onto per-agent reply queues | — |
| [#210](https://github.com/backspring-labs/squad-ops/pull/210) | SIP-0094 94.2b: native RabbitMQ subscribe() + channel-close resubscribe | — |
| [#208](https://github.com/backspring-labs/squad-ops/pull/208) | SIP-0094 94.2a: QueuePort.subscribe() primitive + SubscriptionHandle (inert) | — |
| [#204](https://github.com/backspring-labs/squad-ops/pull/204) | refactor(SIP-0094): rename per-agent reply queue _results → _replies | — |
| [#203](https://github.com/backspring-labs/squad-ops/pull/203) | ci: pin CI dependencies via ci-constraints.txt for reproducible installs (closes #202) | [#202](https://github.com/backspring-labs/squad-ops/issues/202) |
| [#201](https://github.com/backspring-labs/squad-ops/pull/201) | test(ci): gate tests/unit/comms + tests/unit/agents in the regression suite (closes #200) | [#200](https://github.com/backspring-labs/squad-ops/issues/200) |
| [#199](https://github.com/backspring-labs/squad-ops/pull/199) | feat(SIP-0094 PR 94.1): declare per-agent {agent_id}_results queue at startup (inert, deploy-first) | — |
| [#197](https://github.com/backspring-labs/squad-ops/pull/197) | fix(#195): sync prompt-fragment manifest hashes + prevent future drift (+ first CI gate) | [#149](https://github.com/backspring-labs/squad-ops/issues/149) [#195](https://github.com/backspring-labs/squad-ops/issues/195) |
| [#193](https://github.com/backspring-labs/squad-ops/pull/193) | sip: accept SIP-0094 — Per-Agent Reply Queues + Long-Lived Subscription Model | — |
| [#192](https://github.com/backspring-labs/squad-ops/pull/192) | fix(#185): prefix Prefect task labels with agent name; extract task_naming module | [#185](https://github.com/backspring-labs/squad-ops/issues/185) |
| [#190](https://github.com/backspring-labs/squad-ops/pull/190) | fix(#189): normalize cross-proposal dependency keys (role display-name vs role-id) | [#189](https://github.com/backspring-labs/squad-ops/issues/189) |
| [#188](https://github.com/backspring-labs/squad-ops/pull/188) | fix(#187): tolerate malformed optional sections in proposer parser | [#187](https://github.com/backspring-labs/squad-ops/issues/187) |
| [#184](https://github.com/backspring-labs/squad-ops/pull/184) | fix: single-quote proposer acceptance-check examples so regex patterns parse | — |
| [#183](https://github.com/backspring-labs/squad-ops/pull/183) | fix(#182): generate proposer typed-acceptance vocabulary from CHECK_SPECS | — |
| [#181](https://github.com/backspring-labs/squad-ops/pull/181) | docs(sip): reply-channel subscription model — Rev 3 (lazy subscription) | — |
| [#180](https://github.com/backspring-labs/squad-ops/pull/180) | fix(sip-0093): enable multi-role plan authoring via plan_authoring_contributors | — |
| [#179](https://github.com/backspring-labs/squad-ops/pull/179) | fix(tests): retarget builder-squad tests to spark-squad-with-builder (green the regression suite) | — |
| [#178](https://github.com/backspring-labs/squad-ops/pull/178) | docs(plan): wire 1.0.x hardening plan tables to GitHub issues (#170) | — |
| [#177](https://github.com/backspring-labs/squad-ops/pull/177) | docs(hardening): framework smoke integration test section (issue #176) | — |
| [#175](https://github.com/backspring-labs/squad-ops/pull/175) | chore(profiles): remove stale full-squad-with-builder profile | — |
| [#174](https://github.com/backspring-labs/squad-ops/pull/174) | feat(cycles): lite profile + filter builder-only task types by squad capability | — |
| [#169](https://github.com/backspring-labs/squad-ops/pull/169) | chore(cycles): finish DispatchedFlowExecutor rename in docstrings + docs | — |
| [#171](https://github.com/backspring-labs/squad-ops/pull/171) | docs: v1.1 runtime track roadmap (MacBook lane) | — |
| [#167](https://github.com/backspring-labs/squad-ops/pull/167) | chore(SIP-0092): wire ruff into regression as fail-stop + clear lint debt | — |
| [#165](https://github.com/backspring-labs/squad-ops/pull/165) | fix(SIP-0093): plan-authoring brief handler retries + fence-stripping (PR 93.3 follow-on) | — |
| [#164](https://github.com/backspring-labs/squad-ops/pull/164) | refactor(cycles): rename DistributedFlowExecutor -> DispatchedFlowExecutor (#82) | [#82](https://github.com/backspring-labs/squad-ops/issues/82) |
| [#163](https://github.com/backspring-labs/squad-ops/pull/163) | fix(tests): use asyncio.run in telemetry health tests (#161) | [#161](https://github.com/backspring-labs/squad-ops/issues/161) |
| [#162](https://github.com/backspring-labs/squad-ops/pull/162) | fix(tests): restore green regression baseline on main | [#160](https://github.com/backspring-labs/squad-ops/issues/160) |
| [#147](https://github.com/backspring-labs/squad-ops/pull/147) | feat: SIP-0089 Phase 1 — Minimal runtime state | — |
| [#145](https://github.com/backspring-labs/squad-ops/pull/145) | feat(SIP-0093 PR 93.3 cutover): merger + dynamic PLANNING_TASK_STEPS | — |
| [#144](https://github.com/backspring-labs/squad-ops/pull/144) | feat(SIP-0093 PR 93.2): role proposer handlers + RC-23 failure records | — |
| [#143](https://github.com/backspring-labs/squad-ops/pull/143) | docs(SIP-0093): amend Rev 2 parallel-fan-out section for Spark reality | — |
| [#142](https://github.com/backspring-labs/squad-ops/pull/142) | fix(SIP-0084 #140): prompt-registry cleanup for plan authoring service | [#140](https://github.com/backspring-labs/squad-ops/issues/140) |
| [#141](https://github.com/backspring-labs/squad-ops/pull/141) | feat(SIP-0093 PR 93.1): proposal/guidance/merge_decisions schemas | — |
| [#139](https://github.com/backspring-labs/squad-ops/pull/139) | feat(SIP-0093 PR 93.0): extract PlanAuthoringService + brief schema/handler | — |
| [#138](https://github.com/backspring-labs/squad-ops/pull/138) | refactor(SIP-0092/0093): drop multi_role_plan_authoring flag, single runtime route | — |
| [#137](https://github.com/backspring-labs/squad-ops/pull/137) | docs(SIP-0093/0092): initial plan doc + tightening from review | — |
| [#136](https://github.com/backspring-labs/squad-ops/pull/136) | docs(SIP-0092/0093): tighten SIP-0093 Rev 2 + rewrite SIP-0092 §6.2 to use it | — |
| [#135](https://github.com/backspring-labs/squad-ops/pull/135) | docs(SIP-0092): reframe M2→M3 gate criteria for SIP-0093 in M2 slot | — |
| [#131](https://github.com/backspring-labs/squad-ops/pull/131) | fix(prompts): register SIP-0079 task_type fragments missing from manifest | — |
| [#129](https://github.com/backspring-labs/squad-ops/pull/129) | fix(impl): suppress role-identity prepend on JSON-emitting impl handlers | — |
| [#128](https://github.com/backspring-labs/squad-ops/pull/128) | fix(impl): tolerant JSON extraction + raw-response logging in SIP-0079 handlers | — |
| [#127](https://github.com/backspring-labs/squad-ops/pull/127) | fix(governance): repair merge-conflict resolution between #124 and #126 | — |
| [#126](https://github.com/backspring-labs/squad-ops/pull/126) | refactor: externalize SIP-0079 impl handler system prompts to task_type fragments | — |
| [#125](https://github.com/backspring-labs/squad-ops/pull/125) | feat(plan-authoring): SIP-0093 schema + helpers (scaffolding, no behavior change) | — |
| [#123](https://github.com/backspring-labs/squad-ops/pull/123) | refactor: drop proper agent names from source comments and docstrings | — |
| [#122](https://github.com/backspring-labs/squad-ops/pull/122) | fix(governance): make Max's structured outputs reliable enough for M2 (#109) | [#109](https://github.com/backspring-labs/squad-ops/issues/109) |
| [#121](https://github.com/backspring-labs/squad-ops/pull/121) | fix(repair): surface repaired artifact contents to qa.validate_repair | — |
| [#120](https://github.com/backspring-labs/squad-ops/pull/120) | fix(repair): plumb failed-task contract into correction-loop repair envelope | — |
| [#117](https://github.com/backspring-labs/squad-ops/pull/117) | docs(SIP-0092): revise M1→M2 gate eval to proceed (cycles 5-6 evidence) | — |
| [#118](https://github.com/backspring-labs/squad-ops/pull/118) | refactor(SIP-0092): align code names with the SIP-0092 plan vocabulary (M2.1 prep) | — |
| [#119](https://github.com/backspring-labs/squad-ops/pull/119) | fix(executor): persist correction-task and repair-task output artifacts | — |
| [#116](https://github.com/backspring-labs/squad-ops/pull/116) | fix(framing): wire PRD coverage discipline into the manifest prompt actually used (#112 real fix) | — |
| [#115](https://github.com/backspring-labs/squad-ops/pull/115) | feat(observability): typed_check_evaluation artifact + identifying plan_delta trigger (#114) | [#114](https://github.com/backspring-labs/squad-ops/issues/114) |
| [#113](https://github.com/backspring-labs/squad-ops/pull/113) | fix(framing): require PRD↔acceptance coverage in implementation_plan (#112) | [#112](https://github.com/backspring-labs/squad-ops/issues/112) |
| [#111](https://github.com/backspring-labs/squad-ops/pull/111) | fix(correction-loop): propagate squad-profile model to correction & repair envelopes | [#110](https://github.com/backspring-labs/squad-ops/issues/110) |
| [#108](https://github.com/backspring-labs/squad-ops/pull/108) | fix(builder): scope required_files by task expected_artifacts (#107) | [#107](https://github.com/backspring-labs/squad-ops/issues/107) |
| [#106](https://github.com/backspring-labs/squad-ops/pull/106) | fix(correction-loop): enrich failure_evidence with validation context (#84) | [#84](https://github.com/backspring-labs/squad-ops/issues/84) |
| [#105](https://github.com/backspring-labs/squad-ops/pull/105) | chore(model-registry): register qwen3.6:27b for spark-squad cycles | — |
| [#104](https://github.com/backspring-labs/squad-ops/pull/104) | fix(correction-loop): persist repair source files + route by failed task type | — |
| [#103](https://github.com/backspring-labs/squad-ops/pull/103) | fix(builder-prompt): mark qa_handoff section list non-negotiable + worked skeleton | — |
| [#102](https://github.com/backspring-labs/squad-ops/pull/102) | feat(crp): add validation request profile for SIP-0092 M1 → M2 gate evidence | — |
| [#101](https://github.com/backspring-labs/squad-ops/pull/101) | fix(repair): split development.repair into pulse-check vs correction-loop variants (#100) | [#100](https://github.com/backspring-labs/squad-ops/issues/100) |
| [#99](https://github.com/backspring-labs/squad-ops/pull/99) | fix(bootstrap): register QAValidateRepairHandler — closes #93 (qa.validate_repair 13ms failure) | [#93](https://github.com/backspring-labs/squad-ops/issues/93) |
| [#98](https://github.com/backspring-labs/squad-ops/pull/98) | fix(builder): make required_files/optional_files the single source of truth (#92) | [#92](https://github.com/backspring-labs/squad-ops/issues/92) |
| [#96](https://github.com/backspring-labs/squad-ops/pull/96) | fix(correction-loop): preserve analyze_failure outputs through to PlanDelta (#95) | [#95](https://github.com/backspring-labs/squad-ops/issues/95) |
| [#91](https://github.com/backspring-labs/squad-ops/pull/91) | fix(parser): tolerate common LLM fenced-block format drift | — |
| [#90](https://github.com/backspring-labs/squad-ops/pull/90) | sip(rev2): per-agent reply queues replace per-run cycle_results scoping | — |
| [#89](https://github.com/backspring-labs/squad-ops/pull/89) | fix(cycle-reply): recover lost agent replies via long-block consume + cache invalidation | — |
| [#87](https://github.com/backspring-labs/squad-ops/pull/87) | fix(m1.3): emit observability log lines for typed-acceptance evaluation (#83) | [#83](https://github.com/backspring-labs/squad-ops/issues/83) |
| [#88](https://github.com/backspring-labs/squad-ops/pull/88) | fix(correction-loop): pydantic-validate FailureAnalysis output (#84) | — |
| [#86](https://github.com/backspring-labs/squad-ops/pull/86) | fix(executor): use manifest focus in Prefect task names (#81) | [#81](https://github.com/backspring-labs/squad-ops/issues/81) |
| [#85](https://github.com/backspring-labs/squad-ops/pull/85) | chore(squad-profiles): spark-squad-with-builder all roles → qwen3.6:27b | — |
| [#76](https://github.com/backspring-labs/squad-ops/pull/76) | feat(sip-0092 m1.3): wire typed-acceptance evaluation into _validate_focused | — |
| [#75](https://github.com/backspring-labs/squad-ops/pull/75) | feat(sip-0092 m1.2): typed-acceptance evaluator framework + six checks | — |
| [#74](https://github.com/backspring-labs/squad-ops/pull/74) | refactor(sip-0092): rename WorkloadType.PLANNING → FRAMING | — |
| [#73](https://github.com/backspring-labs/squad-ops/pull/73) | docs(sip): propose SIP-Multi-Role-Plan-Authoring; wire into SIP-0092 M1→M2 gate | — |
| [#72](https://github.com/backspring-labs/squad-ops/pull/72) | feat(sip-0092 m1.1): implementation plan rename + typed acceptance schema/parser | — |
| [#71](https://github.com/backspring-labs/squad-ops/pull/71) | docs(plan): SIP-0092 Implementation Plan Improvement — plan doc (rev 1–3) | — |
| [#70](https://github.com/backspring-labs/squad-ops/pull/70) | chore(sip): accept SIP-0092 Build Manifest Maturation | — |
| [#69](https://github.com/backspring-labs/squad-ops/pull/69) | docs(sip): Build Manifest Maturation rev 2 — reviewer feedback | — |
| [#68](https://github.com/backspring-labs/squad-ops/pull/68) | docs(plan): 1.0.x hardening plan rev 2 — reviewer feedback | — |
| [#67](https://github.com/backspring-labs/squad-ops/pull/67) | docs(plan): 1.0.x build-reliability hardening plan + Build Manifest Maturation SIP | — |
| [#66](https://github.com/backspring-labs/squad-ops/pull/66) | docs(sip-0088): add Future Considerations — duty/cycle composition | — |
| [#64](https://github.com/backspring-labs/squad-ops/pull/64) | docs(plan): SIP-0089 agent runtime state implementation plan (review) | — |
| [#65](https://github.com/backspring-labs/squad-ops/pull/65) | config(squad): add smoke profile (5x qwen2.5:3b-instruct) | — |
| [#63](https://github.com/backspring-labs/squad-ops/pull/63) | chore(sip): accept runtime modes package (SIP-0088 through SIP-0091) | — |
| [#60](https://github.com/backspring-labs/squad-ops/pull/60) | SIP-0087: Prefect task-scoped log streaming + v1.0.5 | — |
| [#62](https://github.com/backspring-labs/squad-ops/pull/62) | docs(sip): split agent runtime modes into three SIPs (v1.1/1.2/1.3) | — |
| [#61](https://github.com/backspring-labs/squad-ops/pull/61) | docs(sip): propose agent runtime modes (Duty/Cycle/Ambient) | — |
| [#59](https://github.com/backspring-labs/squad-ops/pull/59) | sip(accept): SIP-0087 Prefect Task-Scoped Log Streaming | — |
| [#58](https://github.com/backspring-labs/squad-ops/pull/58) | config(spark): upgrade max/neo/nat/bob to qwen3.6:27b | — |
| [#57](https://github.com/backspring-labs/squad-ops/pull/57) | chore(release): promote SIP-0086 and bump to v1.0.4 | — |
| [#55](https://github.com/backspring-labs/squad-ops/pull/55) | SIP-0086: Build Convergence Loop — Dynamic Task Decomposition, Output Validation & Correction Activation | — |
| [#56](https://github.com/backspring-labs/squad-ops/pull/56) | chore: post-1.0 docs hygiene | — |
| [#54](https://github.com/backspring-labs/squad-ops/pull/54) | SIP: Build Convergence Loop — dynamic task decomposition & correction activation | — |
| [#53](https://github.com/backspring-labs/squad-ops/pull/53) | feat: streaming LLM with usage metadata, Spark 32b profile tuning | — |
| [#52](https://github.com/backspring-labs/squad-ops/pull/52) | fix: Spark squad profile, LLM timeouts, and token throughput telemetry | — |
| [#49](https://github.com/backspring-labs/squad-ops/pull/49) | refactor: tighten C901 complexity threshold to 12 | — |
| [#51](https://github.com/backspring-labs/squad-ops/pull/51) | fix(executor): artifact handoff in multi-workload runs | — |
| [#50](https://github.com/backspring-labs/squad-ops/pull/50) | fix(bootstrap): auto-provision LangFuse on local-spark | — |
| [#48](https://github.com/backspring-labs/squad-ops/pull/48) | refactor: enforce C901 complexity limit of 15 | — |
| [#47](https://github.com/backspring-labs/squad-ops/pull/47) | chore: bump Continuum to v1.0.2 | — |
| [#46](https://github.com/backspring-labs/squad-ops/pull/46) | fix(infra): include Joi in default agent deploy list | [#45](https://github.com/backspring-labs/squad-ops/issues/45) |
| [#44](https://github.com/backspring-labs/squad-ops/pull/44) | feat(sip-0085): Console messaging — chat with Joi via A2A | — |
| [#43](https://github.com/backspring-labs/squad-ops/pull/43) | chore: accept SIP-0085 — Console Messaging Capability via A2A | — |
| [#42](https://github.com/backspring-labs/squad-ops/pull/42) | fix(bootstrap): one-click setup on DGX Spark | [#41](https://github.com/backspring-labs/squad-ops/issues/41) |
| [#40](https://github.com/backspring-labs/squad-ops/pull/40) | feat: Prompt Registry Integration Using Langfuse (SIP-0084) | — |
| [#39](https://github.com/backspring-labs/squad-ops/pull/39) | Restructure examples with numeric prefixes + add agent_chess benchmark | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0081-Profile-Driven-Bootstrap](../../design/sips/SIP-0081-Profile-Driven-Bootstrap.md) | new | implemented |
| [SIP-0084-Prompt-Registry-Integration-Using](../../design/sips/SIP-0084-Prompt-Registry-Integration-Using.md) | new | implemented |
| [SIP-0085-Console-Messaging-Capability-for](../../design/sips/SIP-0085-Console-Messaging-Capability-for.md) | new | implemented |
| [SIP-0086-Build-Convergence-Loop-Dynamic](../../design/sips/SIP-0086-Build-Convergence-Loop-Dynamic.md) | new | implemented |
| [SIP-0087-Prefect-Task-Scoped-Log-Streaming](../../design/sips/SIP-0087-Prefect-Task-Scoped-Log-Streaming.md) | new | implemented |
| [SIP-0088-Agent-Runtime-Modes](../../design/sips/SIP-0088-Agent-Runtime-Modes.md) | new | accepted |
| [SIP-0089-Agent-Runtime-State](../../design/sips/SIP-0089-Agent-Runtime-State.md) | new | implemented |
| [SIP-0090-Agent-Embodiment-Substrate](../../design/sips/SIP-0090-Agent-Embodiment-Substrate.md) | new | accepted |
| [SIP-0091-Duty-Durability-via-Temporal](../../design/sips/SIP-0091-Duty-Durability-via-Temporal.md) | new | accepted |
| [SIP-0092-Implementation-Plan-Improvement](../../design/sips/SIP-0092-Implementation-Plan-Improvement.md) | new | accepted |
| [SIP-0093-Multi-Role-Plan-Authoring](../../design/sips/SIP-0093-Multi-Role-Plan-Authoring.md) | new | accepted |
| [SIP-0094-Per-Agent-Reply-Queues-Long-Lived](../../design/sips/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md) | new | implemented |
| [SIP-Duty-Continuity-and-Handoff-Ledger](../../design/sips/SIP-Duty-Continuity-and-Handoff-Ledger.md) | new | proposed |
| [SIP-Planning-Sequence-Strategy-First](../../design/sips/SIP-Planning-Sequence-Strategy-First.md) | new | proposed |
| [SIP-Version-Bump-Hardening](../../design/sips/SIP-Version-Bump-Hardening.md) | new | proposed |
