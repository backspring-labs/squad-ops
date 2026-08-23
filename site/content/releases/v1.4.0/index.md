---
title: v1.4.0
---

# v1.4.0

**Released 2026-07-31** · [tag `v1.4.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.4.0)

**The Verified Canonical App Build** (133 merges since 1.3.1) — first dual-lane-headline
feature release. Lane M's golden-path stack (scaffold + verification contracts +
frozen-file enforcement) plus Lane S's Ephemeral Application Sandbox 1.4 floor.

**Exit evidence, pre-registered:** Functional App Yield window 3 — **6/6 functional
(100%), 5/6 fully green, five consecutive greens**, unfiltered, on frozen deploy
`9522ef4d`, in **seeded-manifest (bind) mode**; the bar was ≥4/6. The cut gate's original
condition ("≥3 consecutive golden-benchmark runs, squad-authored-manifest mode") was
superseded by owner decision 2026-07-28 and executed at the cut.

**What this honestly demonstrates:** given a PRD **and a fully specified interface
manifest**, the squad implements, verifies, and delivers a working app. What remains
unmeasured — by the original gate's own correct reasoning — is squad-authored-manifest
mode; that rung moved to v1.6 as a headline. The claim is *a specified contract, not
PRD-to-app*.

Entries are grouped by arc rather than listed per-PR; the volume
here is dominated by the correction/repair loop, which had to converge before any of the
scaffold work could be measured at all. Bare `#NNN` references in this section are **pull
requests**; the issues they close are named in the PR bodies.

### Added — the golden-path scaffold stack (Lane M)
- **SIP-0099 Contract-First Build Scaffolding** — an interface manifest expands to a
  deterministic walking skeleton, and dev tasks *fill declared slots* instead of
  authoring structure. Phase-0.5 spike (#428 hand-written group_run manifest, #429
  `fullstack_fastapi_react` expander proving the empty skeleton builds and boots) then
  phases 99.1–99.3 (#482 expander canonicalization + skeleton CI gate, #486 manifest in
  framing, #487 executor materialization + fill-only develop).
- **SIP-0098 Verification Contracts** — acceptance criteria now come from a contract the
  cycle is *bound* to, not authored per-plan. Proposed #475, accepted with implementation
  plans #477; phases 98.1–98.4 (#478 contract schema, #483 expander emission +
  emission-time gates, #488 orchestration binding — "bind, don't author", #489 behavioral
  probe runner + coverage accounting); 98.5 migration slices (#491 live probe emission +
  PRD v0.4 split, #493 `contract_gate emit` mode for operator seeding).
- **SIP-0100 Scaffolded Test Harness and Frozen-File Enforcement** — frozen scaffold
  files are restored when a producer rewrites them, and unauthorized slot emissions are
  dropped. Prototype #538, accepted #539 with plan #540; phases 0–4 (#541 characterization,
  #542 harness contract, #544 authorization spine + live frozen-ownership enforcement,
  #547 evidence + QA write-scope, #548 contract-compliance circuit breaker, #549/#550
  deterministic replay, path/atomicity matrix, no-regression).
- **SIP-0101 Cycle Replay Harness** — proposed #594, revised #595, accepted with a
  Phase-1 plan #596. Implementation deliberately held until the 98.5 baseline closes.
- **`function_defined` acceptance check (#533)** — a style-immune "this file defines N
  functions matching a prefix", replacing regex-on-source criteria that failed on
  formatting rather than behavior.

### Added — verification evidence integrity (SIP-0096, Phases 1–3)
- **Phase 1 (#369):** the integrity core — pure aggregation, evidence families, and the
  `blocked_unverified` verdict. Cycle-level `request_profile` provenance (#367).
- **Phase 2:** task-result verification normalized into the ledger with honest-red guards
  (#378); final-state resolution for re-verified checks (#386).
- **Phase 3:** `CycleOutcome` roll-up pure core (#412), per-run `RunVerificationSummary`
  persistence (#416), derive-on-read `CycleOutcome` + cycle-detail surface (#418).
- **Check governance:** canonical framework-check registry rejecting unknown
  `required_checks` ids (#396); required-check tooling parity at preflight + a `doctor`
  verification category (#398); `required_files` enforced at run completion (#390) and
  recorded as a `CheckResult` (#402, corrected builder seam #405); fullstack
  `frontend_build` as evidence (#408).
- **Honest verdicts:** a non-succeeded run never reads `accepted` on zero evidence
  (#409); cycle outcome reconciles per-check evidence across runs (#446); typed
  acceptance reaches the builder seam with wire-shape criteria coercion (#421).

### Fixed — correction and repair convergence
- **Repairs are verified behaviorally, not structurally.** Re-run the failed check on a
  patch (#385); accept behaviorally-verified patches instead of re-rolling repaired tasks
  (#413); re-execute repaired `qa.test` suites before acceptance (#461); reject patches
  whose intra-package imports can't resolve (#592).
- **Repair targeting** — a correct diagnosis is useless if the repair edits the wrong
  file. Retarget onto the drifted source rather than the failing check's tests (#532);
  target the union of drift files and the failing artifact (#534); dependency-scoped
  targeting so no-drift `qa.test` failures reach the source under test (#536); the drift
  branch reaches the fill-slot source (#554); repair artifacts re-homed onto expected
  paths before overlay (#517).
- **Repair context** — the recurring root cause was the system holding an authoritative
  fact and never putting it in front of the agent that needed it. The dev repair gets the
  same fill-only constraint as develop (#555); `resolved_config` threading + frozen
  enforcement on the repair path (#562); deterministic interface-drift diagnosis feeds the
  repair (#527); contract expectations, emission integrity and candidate-free workspaces
  (#564); error-contract block, exit-4 locus, initial-QA expectations (#585); the initial
  dev prompt carries the scaffold contract it was filling (#589); repairs are told the real
  model names instead of guessing them (#604).
- **Workspace correctness:** the correction workspace is re-resolved from live stored
  artifacts each attempt, so the loop can see its own progress (#535).
- **Policy and routing:** `continue` cannot discard executed-failed required checks (#449);
  locus-keyed QA repair routing + emission recovery with aimed retry (#569); cancel reaches
  the dispatch boundary so repairs stop on a cancelled run (#587); four shakedown fixes
  raising roll-success odds (#505).
- **Removed** the unconsumed `qa.validate_repair` step (#558) — its verdict was never read.

### Fixed — the scaffold's own contract
- Success status is declared in the manifest so the skeleton can satisfy its own probe
  (#600), and is included in the content hash (#601).
- The scaffold-owned status code is held inside fill slots (#602); the router takes no
  prefix — stated in the stub and enforced on emission (#608).
- The in-memory store the manifest already declares is emitted rather than left for the
  planner to invent (#606).
- The seeded scaffold reaches `qa.test` and `builder.assemble` (#445).

### Fixed — acceptance checks and emission parsing
- `import_present` matches relative imports (#437) and dotless specs (#442); the backend
  import check imports package members by qualified name (#471); the delivered backend is
  verified to import, not just its tests (#393).
- `regex_match` criteria restricted to document artifacts — the style-lottery guard
  (#468); AST checks skip non-Python files instead of erroring (#607).
- A missing command binary skips instead of erroring (#463); failed suites disclose
  exit-code meaning (#514); the coverage denominator comes from the bound contract rather
  than dispatched checks (#513); behavioral rows are stamped with their contract criterion
  ids (#519); unbound criteria attach to the tail `qa.test` at dispatch (#516).
- Package dirs stay off the test runner's `PYTHONPATH` (#455); the runner refuses
  non-pytest suites precisely, and the QA fragment gained a discovery contract (#518).
- Fenced-parser hardening: nested fences (#432), path-prefix on the first body line (#490),
  path-labelled headers and unterminated-at-EOF fences (#528).
- Probe readiness accepts any HTTP response rather than only 200 on `/health` (#521);
  create-probes expect 201, resolving a contract that contradicted the PRD it verifies
  (#523); typed sample values for probes (#526).

### Fixed — plan authoring and framing
- A system plan-validation rejection re-rolls framing instead of killing the cycle (#525);
  pre-gate plan rejection records a system gate decision instead of dying silently (#476);
  the inter-workload gate stops the sequence on `returned_for_revision` (#467).
- Plan substitution preserves the workload-invariant tail (#440); invariant tasks run in
  canonical order, assemble before `qa.test` (#459); warning/info-severity criteria
  violations are tolerated rather than rejecting the plan (#530).
- Command-safelist lint at the authoring boundary + manifest retry runway (#425);
  style-dependent regex criteria forbidden in guidance (#438); the bind-criteria proposer
  leaves `criteria_refs` empty for contract-owned files (#537); the strategy proposer
  supplies `guidance_id`, unblocking multi-role framing (#485); `qa.test` prompt content
  routed through the fragment system (#450); test-isolation doctrine in the QA fragment
  (#460).
- Bind mode requires a framing-emitted interface manifest (#495) and seeds the canonical
  one (#497).
- Deterministic fill-slot binding at plan authoring landed (#552) and was **reverted**
  (#553) to keep the measurement baseline free of an unvalidated confound.

### Fixed — runtime and ops
- Agent identity is never fabricated (#387); the agent secret is provisioned on deploy and
  fails honestly when absent (#391); runtime-api application logging reaches stdout (#492);
  `init: true` on agent containers reaps subprocess zombies (#543).
- `runs retry` resolves `workload_type` positionally instead of defaulting to `None`
  (#479); forwarding overrides are rebuilt from durable state on mid-sequence entry (#480).
- group_run manifest path param renamed `{id}` → `{run_id}` (#565); anchored hash
  replacement in `regen_fragment_manifest.py` (#453).

### Removed
- Vestigial analysis skills and their dead JSON parsing (#400).
- The dead SIP-0.8.8 skill handler layer, end to end (#403).
- Warmboot operational artifacts, with the era's lessons distilled for the book (#406).

### Docs & SIP lifecycle
- **Proposed:** Contract-First Build Scaffolding (#383), Verification Contracts (#475),
  Cycle Replay Harness (#594), LLM Emission Contracts (#570), fine-grained issue
  enumeration (#384), process lexicon (#599).
- **Accepted:** SIP-0098 + SIP-0099 with both implementation plans (#477), SIP-0100
  (#539, plan #540), SIP-0101 (#596).
- Night triage runbook (#609); RuntimeActivity lifecycle requirements (#546); enum-shadow
  architecture guardrail failing CI on status string-literal comparisons (#382); idea and
  vision drafts tracked under `docs/ideas` (#366); CLI cheatsheet corrections (#499).

## Merged pull requests (172)

| PR | Title | Closes |
|---|---|---|
| [#674](https://github.com/backspring-labs/squad-ops/pull/674) | release: v1.4.0 — the Verified Canonical App Build | — |
| [#666](https://github.com/backspring-labs/squad-ops/pull/666) | fix(locus): missing test suite routes to its owning role — zero-suite verdict survives the executed gate (#665) | [#665](https://github.com/backspring-labs/squad-ops/issues/665) |
| [#664](https://github.com/backspring-labs/squad-ops/pull/664) | fix(verification): passing dev tasks record validation evidence — criteria credit on success (#597) | [#597](https://github.com/backspring-labs/squad-ops/issues/597) |
| [#662](https://github.com/backspring-labs/squad-ops/pull/662) | feat(scaffold): DOM testid contract — manifest-pinned anchors into both dev and qa prompts (#659) | [#659](https://github.com/backspring-labs/squad-ops/issues/659) |
| [#661](https://github.com/backspring-labs/squad-ops/pull/661) | fix(plan-validation): frozen files rejected as expected_artifacts for every role (#658) | [#658](https://github.com/backspring-labs/squad-ops/issues/658) |
| [#660](https://github.com/backspring-labs/squad-ops/pull/660) | fix(planning): thread brief + upstream docs + peer proposal into planning-chain prompts (#657) | [#657](https://github.com/backspring-labs/squad-ops/issues/657) |
| [#656](https://github.com/backspring-labs/squad-ops/pull/656) | feat(checks): frontend_compiles — real bundler at view-task acceptance (#648) | [#648](https://github.com/backspring-labs/squad-ops/issues/648) |
| [#655](https://github.com/backspring-labs/squad-ops/pull/655) | feat(contract): v8 — chained join/leave probes with response capture (#651) | [#651](https://github.com/backspring-labs/squad-ops/issues/651) |
| [#654](https://github.com/backspring-labs/squad-ops/pull/654) | fix(correction): frontend_build failures widen repair scope to frontend source (#650) | [#650](https://github.com/backspring-labs/squad-ops/issues/650) |
| [#653](https://github.com/backspring-labs/squad-ops/pull/653) | fix(scaffold): builder write authorization — refuse net-new source at assembly (#649) | [#649](https://github.com/backspring-labs/squad-ops/issues/649) |
| [#652](https://github.com/backspring-labs/squad-ops/pull/652) | fix(plan): reject unexecutable command checks + directory expected artifacts (#645) | [#645](https://github.com/backspring-labs/squad-ops/issues/645) |
| [#647](https://github.com/backspring-labs/squad-ops/pull/647) | docs(sip): capability packs — owner decisions on taxonomy, pack mechanics, trust scope | — |
| [#646](https://github.com/backspring-labs/squad-ops/pull/646) | docs(sip): Stack-Blueprint draft — stack-pack intent + FAY window evidence | — |
| [#644](https://github.com/backspring-labs/squad-ops/pull/644) | fix(acceptance): typed checks evaluate inside the accepted workspace tree (#643) | [#643](https://github.com/backspring-labs/squad-ops/issues/643) |
| [#642](https://github.com/backspring-labs/squad-ops/pull/642) | feat(locus): runner-owned suite-health verdict — vitest failures stop reading as pytest exit codes (#626) | [#626](https://github.com/backspring-labs/squad-ops/issues/626) |
| [#641](https://github.com/backspring-labs/squad-ops/pull/641) | feat(plan): criterion binding derived from the contract, not transcribed by the author (#509) | [#509](https://github.com/backspring-labs/squad-ops/issues/509) |
| [#640](https://github.com/backspring-labs/squad-ops/pull/640) | fix(retest): contract probes ride the retest against the patched tree (#639) | [#639](https://github.com/backspring-labs/squad-ops/issues/639) |
| [#638](https://github.com/backspring-labs/squad-ops/pull/638) | docs: Functional App Yield measurement design — the 1.4 exit number | — |
| [#636](https://github.com/backspring-labs/squad-ops/pull/636) | fix(sandbox): service boots under the locked dependency pair — shakedown finding #3 (SIP-0102) | — |
| [#635](https://github.com/backspring-labs/squad-ops/pull/635) | fix(sandbox): run operations as the workspace owner — Spark shakedown findings (SIP-0102) | — |
| [#634](https://github.com/backspring-labs/squad-ops/pull/634) | feat(scaffold): blank-input rejection is scaffold-owned AND probe-pinned (#593) | [#593](https://github.com/backspring-labs/squad-ops/issues/593) |
| [#633](https://github.com/backspring-labs/squad-ops/pull/633) | feat(scaffold): frontend test harness is scaffold-owned (#627) | [#627](https://github.com/backspring-labs/squad-ops/issues/627) |
| [#632](https://github.com/backspring-labs/squad-ops/pull/632) | feat(qa): contract's pinned HTTP behavior reaches suite authoring (#629) | — |
| [#630](https://github.com/backspring-labs/squad-ops/pull/630) | feat(checks): module_imports — runtime-level check static analysis cannot fake (#628) | [#628](https://github.com/backspring-labs/squad-ops/issues/628) |
| [#631](https://github.com/backspring-labs/squad-ops/pull/631) | SIP-0102: Spark shakedown handoff — floor smoke promoted to scripts/dev | — |
| [#623](https://github.com/backspring-labs/squad-ops/pull/623) | SIP-0102 phase 102.2: environment is a pinned, validated contract — live-smoke green | [#622](https://github.com/backspring-labs/squad-ops/issues/622) |
| [#625](https://github.com/backspring-labs/squad-ops/pull/625) | docs(sip): test-type taxonomy requirement for the Stack Blueprint (pf-47/49 evidence) | — |
| [#624](https://github.com/backspring-labs/squad-ops/pull/624) | fix(checks): declare check applicability; behavioral retest decides when no structural check applies | — |
| [#621](https://github.com/backspring-labs/squad-ops/pull/621) | SIP-0102: rename the execution domain to sandbox | — |
| [#620](https://github.com/backspring-labs/squad-ops/pull/620) | SIP-0102 phase 102.1: the execution boundary exists (slices a–d) | — |
| [#619](https://github.com/backspring-labs/squad-ops/pull/619) | fix(dev): the initial author gets the model surface, field-level (pf-45) | — |
| [#618](https://github.com/backspring-labs/squad-ops/pull/618) | fix(correction): a work_product rewind is escalated to patch (pf-45) | — |
| [#617](https://github.com/backspring-labs/squad-ops/pull/617) | SIP-0102: Ephemeral Application Sandbox — revise + promote to accepted | — |
| [#616](https://github.com/backspring-labs/squad-ops/pull/616) | fix(scaffold): never append a status_code the decorator already carries | — |
| [#615](https://github.com/backspring-labs/squad-ops/pull/615) | fix(cycles): let the framing re-roll supersede a completed run (#522 never fired live) | — |
| [#614](https://github.com/backspring-labs/squad-ops/pull/614) | fix(scaffold): name a frozen module's state, not only its functions | — |
| [#613](https://github.com/backspring-labs/squad-ops/pull/613) | fix(plan): show the plan author what the frozen files declare | — |
| [#612](https://github.com/backspring-labs/squad-ops/pull/612) | fix(plan): prove frozen-file checks can pass before dispatching the run | — |
| [#611](https://github.com/backspring-labs/squad-ops/pull/611) | docs: 1.4 cut gate, the unreleased changelog, and the SIPs the roadmap forgot | — |
| [#610](https://github.com/backspring-labs/squad-ops/pull/610) | sip(proposed): Stack Blueprint Contract — give a stack a type | — |
| [#609](https://github.com/backspring-labs/squad-ops/pull/609) | docs(ops): night triage runbook — root cause, not narrative | — |
| [#608](https://github.com/backspring-labs/squad-ops/pull/608) | fix(scaffold): the router takes no prefix — state it, and enforce it | — |
| [#607](https://github.com/backspring-labs/squad-ops/pull/607) | fix(checks): AST checks skip non-Python files instead of erroring | — |
| [#606](https://github.com/backspring-labs/squad-ops/pull/606) | fix(scaffold): emit the in-memory store the manifest already declares | [#603](https://github.com/backspring-labs/squad-ops/issues/603) |
| [#604](https://github.com/backspring-labs/squad-ops/pull/604) | fix(correction): tell repairs the real model names instead of letting them guess | — |
| [#602](https://github.com/backspring-labs/squad-ops/pull/602) | fix(scaffold): hold the scaffold-owned status code inside fill slots | — |
| [#601](https://github.com/backspring-labs/squad-ops/pull/601) | fix(scaffold): include success_status in the manifest content hash | — |
| [#600](https://github.com/backspring-labs/squad-ops/pull/600) | fix(scaffold): declare success status in the manifest; reject qa tasks owning others' files | — |
| [#599](https://github.com/backspring-labs/squad-ops/pull/599) | docs(ideas): process lexicon — one seeded vocabulary across all domains | — |
| [#596](https://github.com/backspring-labs/squad-ops/pull/596) | sip(0101): accept Cycle Replay Harness + Phase-1 implementation plan | — |
| [#595](https://github.com/backspring-labs/squad-ops/pull/595) | sip(replay-harness): revision 3 — correct the FAY enforcement claim, add implementation order | — |
| [#594](https://github.com/backspring-labs/squad-ops/pull/594) | sip: propose Cycle Replay Harness — pinned fast-forward for phase-targeted iteration | — |
| [#592](https://github.com/backspring-labs/squad-ops/pull/592) | fix(verification): reject patches whose intra-package imports can't resolve (#591) | [#591](https://github.com/backspring-labs/squad-ops/issues/591) |
| [#589](https://github.com/backspring-labs/squad-ops/pull/589) | fix(dev): the initial focused prompt carries the scaffold contract it was filling (#588) | [#588](https://github.com/backspring-labs/squad-ops/issues/588) |
| [#587](https://github.com/backspring-labs/squad-ops/pull/587) | fix(cycles): cancel reaches the dispatch boundary — repairs stop on a cancelled run (#586) | [#586](https://github.com/backspring-labs/squad-ops/issues/586) |
| [#585](https://github.com/backspring-labs/squad-ops/pull/585) | fix(correction): night-window stack — ERROR CONTRACT block, exit-4 locus, initial-qa expectations | — |
| [#584](https://github.com/backspring-labs/squad-ops/pull/584) | fix(qa): harness_boundary expectation instructed the violation; qa prompt diet; failed-check names in patch logs | — |
| [#570](https://github.com/backspring-labs/squad-ops/pull/570) | SIP: LLM Emission Contracts — provider-agnostic structured output + hardened code extraction | — |
| [#569](https://github.com/backspring-labs/squad-ops/pull/569) | fix(emission): #566 recovery + aimed retry, #568 locus-keyed qa repair routing | [#566](https://github.com/backspring-labs/squad-ops/issues/566) [#568](https://github.com/backspring-labs/squad-ops/issues/568) |
| [#565](https://github.com/backspring-labs/squad-ops/pull/565) | feat(manifest): rename group_run path param {id} -> {run_id} | — |
| [#564](https://github.com/backspring-labs/squad-ops/pull/564) | feat(correction): pf-31 convergence fixes A+D+E — contract expectations, emission integrity, candidate-free workspaces | — |
| [#563](https://github.com/backspring-labs/squad-ops/pull/563) | docs: pf-31 correction-convergence fix plan (A: contract expectations, D: emission integrity, E: rejected-candidate accounting) | — |
| [#562](https://github.com/backspring-labs/squad-ops/pull/562) | fix(correction): repair-path hardening — resolved_config threading + SIP-0100 3.4b frozen enforcement (restore+signal) | — |
| [#558](https://github.com/backspring-labs/squad-ops/pull/558) | refactor(correction): remove the unconsumed qa.validate_repair step | [#556](https://github.com/backspring-labs/squad-ops/issues/556) |
| [#555](https://github.com/backspring-labs/squad-ops/pull/555) | fix(correction): give the dev repair the same scaffold fill-only constraint as develop | — |
| [#554](https://github.com/backspring-labs/squad-ops/pull/554) | fix(correction): drift branch reaches the fill-slot source (drift+behavioral-bug combo) | — |
| [#553](https://github.com/backspring-labs/squad-ops/pull/553) | Revert #552: authoring target-binding (A+B) — clean baseline for green-roll hunt | — |
| [#552](https://github.com/backspring-labs/squad-ops/pull/552) | feat: deterministic fill-slot binding at plan authoring (Phases A+B) | — |
| [#551](https://github.com/backspring-labs/squad-ops/pull/551) | docs: fix + dev plan — deterministic fill-slot binding at plan authoring | — |
| [#550](https://github.com/backspring-labs/squad-ops/pull/550) | test(sip-0100): Phase 4.5 — no-regression + flag D3 fail-open deviation | — |
| [#549](https://github.com/backspring-labs/squad-ops/pull/549) | test(sip-0100): Phase 4.1-4.3 — deterministic replay & path/atomicity matrix | — |
| [#548](https://github.com/backspring-labs/squad-ops/pull/548) | feat(sip-0100): Phase 3 Task 3.4a — contract-compliance circuit-breaker | — |
| [#547](https://github.com/backspring-labs/squad-ops/pull/547) | feat(sip-0100): Phase 3 (3.3 evidence + 3.1 QA write-scope) | — |
| [#545](https://github.com/backspring-labs/squad-ops/pull/545) | docs(sip-0100): correct 2026-07-23 finding — model-capacity, run 4.4 on full | — |
| [#546](https://github.com/backspring-labs/squad-ops/pull/546) | docs(runtime-status): requirements for RuntimeActivity lifecycle integrity | — |
| [#544](https://github.com/backspring-labs/squad-ops/pull/544) | feat(sip-0100): Phase 2 — authorization spine + live frozen-ownership enforcement | — |
| [#543](https://github.com/backspring-labs/squad-ops/pull/543) | fix(docker): init: true on agent containers to reap subprocess zombies | — |
| [#542](https://github.com/backspring-labs/squad-ops/pull/542) | feat(sip-0100): Phase 1 — scaffolded test harness contract | — |
| [#541](https://github.com/backspring-labs/squad-ops/pull/541) | feat(sip-0100): Phase 0 — characterization & decisions | — |
| [#540](https://github.com/backspring-labs/squad-ops/pull/540) | docs(plan): SIP-0100 implementation plan (scaffold integrity) | — |
| [#539](https://github.com/backspring-labs/squad-ops/pull/539) | docs(sip): revise + accept SIP-0100 (Scaffolded Test Harness and Frozen-File Enforcement) | — |
| [#538](https://github.com/backspring-labs/squad-ops/pull/538) | scaffold: seed a frozen test harness to pin the import root (prototype + proposed SIP) | — |
| [#537](https://github.com/backspring-labs/squad-ops/pull/537) | fix(framing): bind-criteria proposer must leave criteria_refs EMPTY for contract-owned files | — |
| [#536](https://github.com/backspring-labs/squad-ops/pull/536) | fix(RC2): dependency-scoped repair target — no-drift qa.test failures reach the source under test | — |
| [#535](https://github.com/backspring-labs/squad-ops/pull/535) | fix(correction): re-resolve the correction workspace from live stored_artifacts (RC3) | — |
| [#534](https://github.com/backspring-labs/squad-ops/pull/534) | fix(correction): target the union of drift files + the failing check's artifact | — |
| [#533](https://github.com/backspring-labs/squad-ops/pull/533) | feat(checks): add function_defined — a style-immune tool for "file defines functions" | — |
| [#532](https://github.com/backspring-labs/squad-ops/pull/532) | fix(#531): retarget patch-path repair onto the drifted source, not the failed check's tests | [#531](https://github.com/backspring-labs/squad-ops/issues/531) |
| [#530](https://github.com/backspring-labs/squad-ops/pull/530) | fix(plan-validation): tolerate warning/info-severity criteria violations instead of rejecting the plan | — |
| [#528](https://github.com/backspring-labs/squad-ops/pull/528) | fix(fenced_parser): recover path:-labelled headers and unterminated-at-EOF fences | — |
| [#527](https://github.com/backspring-labs/squad-ops/pull/527) | feat: deterministic interface-drift diagnosis feeds the correction repair (piece 1) | — |
| [#526](https://github.com/backspring-labs/squad-ops/pull/526) | fix(#524): probe request bodies carry type/name-appropriate sample values, not "x" | [#524](https://github.com/backspring-labs/squad-ops/issues/524) |
| [#525](https://github.com/backspring-labs/squad-ops/pull/525) | fix(#522): system plan-validation rejection re-rolls framing instead of killing the cycle | [#522](https://github.com/backspring-labs/squad-ops/issues/522) |
| [#523](https://github.com/backspring-labs/squad-ops/pull/523) | fix: create-probes expect 201 — the contract contradicted the PRD it verifies | — |
| [#521](https://github.com/backspring-labs/squad-ops/pull/521) | fix(#520): probe readiness accepts any HTTP response, not only 200 on /health | [#520](https://github.com/backspring-labs/squad-ops/issues/520) |
| [#519](https://github.com/backspring-labs/squad-ops/pull/519) | fix: behavioral check rows are stamped with their contract criterion ids | — |
| [#518](https://github.com/backspring-labs/squad-ops/pull/518) | fix: test-authorship gap — runner refuses non-pytest suites precisely; qa fragment gains the discovery contract | — |
| [#517](https://github.com/backspring-labs/squad-ops/pull/517) | fix(#507): repair artifacts are re-homed onto expected paths before the overlay | [#507](https://github.com/backspring-labs/squad-ops/issues/507) |
| [#513](https://github.com/backspring-labs/squad-ops/pull/513) | fix(#508): coverage denominator comes from the bound contract, not dispatched checks | [#508](https://github.com/backspring-labs/squad-ops/issues/508) |
| [#514](https://github.com/backspring-labs/squad-ops/pull/514) | fix(#510): failed test suites disclose exit-code meaning in the check reason | [#510](https://github.com/backspring-labs/squad-ops/issues/510) |
| [#515](https://github.com/backspring-labs/squad-ops/pull/515) | fix(#512): probe boot failures disclose exit state and stderr tail | [#512](https://github.com/backspring-labs/squad-ops/issues/512) |
| [#516](https://github.com/backspring-labs/squad-ops/pull/516) | fix(#509): unbound contract criteria attach to the tail qa.test at dispatch | — |
| [#505](https://github.com/backspring-labs/squad-ops/pull/505) | Shakedown-3 findings: four fixes that raise genuine roll-success odds | [#500](https://github.com/backspring-labs/squad-ops/issues/500) [#501](https://github.com/backspring-labs/squad-ops/issues/501) [#502](https://github.com/backspring-labs/squad-ops/issues/502) [#503](https://github.com/backspring-labs/squad-ops/issues/503) |
| [#499](https://github.com/backspring-labs/squad-ops/pull/499) | docs: fix stale CLI syntax in CLAUDE.md cheatsheet | — |
| [#497](https://github.com/backspring-labs/squad-ops/pull/497) | fix(#496): bind mode seeds the canonical interface manifest | [#496](https://github.com/backspring-labs/squad-ops/issues/496) |
| [#495](https://github.com/backspring-labs/squad-ops/pull/495) | fix(#494): bind mode requires a framing-emitted interface manifest | [#494](https://github.com/backspring-labs/squad-ops/issues/494) |
| [#493](https://github.com/backspring-labs/squad-ops/pull/493) | feat(sip-0098/98.5): contract_gate emit mode — contract-seeding wiring (operator-seed decided) | — |
| [#492](https://github.com/backspring-labs/squad-ops/pull/492) | fix(#427): runtime-api application logging reaches stdout | — |
| [#491](https://github.com/backspring-labs/squad-ops/pull/491) | feat(sip-0098): 98.5 slices 1–2 — live probe emission + PRD v0.4 split | — |
| [#490](https://github.com/backspring-labs/squad-ops/pull/490) | fix(#470): fenced parser tolerates path-prefix-on-first-body-line | [#470](https://github.com/backspring-labs/squad-ops/issues/470) |
| [#489](https://github.com/backspring-labs/squad-ops/pull/489) | feat(sip-0098): behavioral probe runner + coverage accounting (98.4) | — |
| [#488](https://github.com/backspring-labs/squad-ops/pull/488) | feat(sip-0098): orchestration binding — bind, don't author (98.3) | — |
| [#487](https://github.com/backspring-labs/squad-ops/pull/487) | feat(sip-0099): executor materialization + fill-only develop (phase 99.3) | — |
| [#486](https://github.com/backspring-labs/squad-ops/pull/486) | feat(sip-0099): interface manifest in framing (phase 99.2) | — |
| [#485](https://github.com/backspring-labs/squad-ops/pull/485) | fix(#484): strategy proposer supplies guidance_id (unblocks multi-role framing) | [#484](https://github.com/backspring-labs/squad-ops/issues/484) |
| [#483](https://github.com/backspring-labs/squad-ops/pull/483) | feat(sip-0098): expander emission + emission-time contract gates (phase 98.2) | — |
| [#482](https://github.com/backspring-labs/squad-ops/pull/482) | feat(sip-0099): expander canonicalization + skeleton CI gate (phase 99.1) | — |
| [#480](https://github.com/backspring-labs/squad-ops/pull/480) | fix(#434): rebuild forwarding overrides from durable state on mid-sequence entry | [#434](https://github.com/backspring-labs/squad-ops/issues/434) |
| [#479](https://github.com/backspring-labs/squad-ops/pull/479) | fix(#433): runs retry resolves workload_type positionally instead of defaulting to None | [#433](https://github.com/backspring-labs/squad-ops/issues/433) |
| [#478](https://github.com/backspring-labs/squad-ops/pull/478) | feat(sip-0098): contract schema, loader, and linter (phase 98.1) | — |
| [#477](https://github.com/backspring-labs/squad-ops/pull/477) | sip: accept SIP-0098 + SIP-0099 (1.4 Lane M Scaffold headline) with both implementation plans | — |
| [#476](https://github.com/backspring-labs/squad-ops/pull/476) | re-land fix(#473) + fix(#472): stranded by stacked-base merge (#474) | [#472](https://github.com/backspring-labs/squad-ops/issues/472) [#473](https://github.com/backspring-labs/squad-ops/issues/473) |
| [#475](https://github.com/backspring-labs/squad-ops/pull/475) | SIP proposal: Verification Contracts — contract-owned acceptance criteria | — |
| [#474](https://github.com/backspring-labs/squad-ops/pull/474) | fix(#473): pre-gate plan rejection records a system gate decision instead of dying silently | [#473](https://github.com/backspring-labs/squad-ops/issues/473) |
| [#471](https://github.com/backspring-labs/squad-ops/pull/471) | fix(#469): backend import check imports package members by qualified name | [#469](https://github.com/backspring-labs/squad-ops/issues/469) |
| [#468](https://github.com/backspring-labs/squad-ops/pull/468) | fix(#464): regex_match criteria restricted to document artifacts (style-lottery guard) | [#464](https://github.com/backspring-labs/squad-ops/issues/464) [#472](https://github.com/backspring-labs/squad-ops/issues/472) |
| [#467](https://github.com/backspring-labs/squad-ops/pull/467) | fix(#466): inter-workload gate stops the sequence on returned_for_revision | [#466](https://github.com/backspring-labs/squad-ops/issues/466) |
| [#463](https://github.com/backspring-labs/squad-ops/pull/463) | fix(#462): missing command binary skips instead of erroring; env-aware authoring guidance | [#462](https://github.com/backspring-labs/squad-ops/issues/462) |
| [#461](https://github.com/backspring-labs/squad-ops/pull/461) | fix(#456): repaired qa.test suites are re-executed before patch acceptance | [#456](https://github.com/backspring-labs/squad-ops/issues/456) |
| [#460](https://github.com/backspring-labs/squad-ops/pull/460) | fix(#457): test-isolation doctrine in the qa.test fragment | [#457](https://github.com/backspring-labs/squad-ops/issues/457) |
| [#459](https://github.com/backspring-labs/squad-ops/pull/459) | fix(#458): plan-authored invariant tasks run in canonical order (assemble before qa.test) | [#458](https://github.com/backspring-labs/squad-ops/issues/458) |
| [#455](https://github.com/backspring-labs/squad-ops/pull/455) | fix(#454): package dirs stay off the test runner's PYTHONPATH | [#454](https://github.com/backspring-labs/squad-ops/issues/454) |
| [#453](https://github.com/backspring-labs/squad-ops/pull/453) | fix(#451): anchored hash replacement in regen_fragment_manifest.py | [#451](https://github.com/backspring-labs/squad-ops/issues/451) |
| [#450](https://github.com/backspring-labs/squad-ops/pull/450) | fix(#448): qa.test prompt content routed through the fragment system | [#448](https://github.com/backspring-labs/squad-ops/issues/448) |
| [#449](https://github.com/backspring-labs/squad-ops/pull/449) | fix(#447): correction policy guard — continue cannot discard executed-failed required checks | [#447](https://github.com/backspring-labs/squad-ops/issues/447) |
| [#446](https://github.com/backspring-labs/squad-ops/pull/446) | fix(#444): cycle outcome reconciles per-check evidence across runs | [#444](https://github.com/backspring-labs/squad-ops/issues/444) |
| [#445](https://github.com/backspring-labs/squad-ops/pull/445) | fix(#443): seeded scaffold reaches qa.test and builder.assemble | [#443](https://github.com/backspring-labs/squad-ops/issues/443) |
| [#442](https://github.com/backspring-labs/squad-ops/pull/442) | fix(#441): dotless import_present spec matches relative imports | [#441](https://github.com/backspring-labs/squad-ops/issues/441) |
| [#440](https://github.com/backspring-labs/squad-ops/pull/440) | fix(#439): plan substitution preserves the workload-invariant tail (assemble + qa.test) | [#439](https://github.com/backspring-labs/squad-ops/issues/439) |
| [#438](https://github.com/backspring-labs/squad-ops/pull/438) | fix: plan-authoring guidance forbids style-dependent regex criteria | — |
| [#437](https://github.com/backspring-labs/squad-ops/pull/437) | fix(#436): import_present matches relative imports | [#436](https://github.com/backspring-labs/squad-ops/issues/436) |
| [#432](https://github.com/backspring-labs/squad-ops/pull/432) | fix(#430): fenced_parser tracks nested fences instead of clipping at the first bare close | [#430](https://github.com/backspring-labs/squad-ops/issues/430) |
| [#429](https://github.com/backspring-labs/squad-ops/pull/429) | spike(phase-0.5): fullstack_fastapi_react expander — skeleton builds + boots | — |
| [#428](https://github.com/backspring-labs/squad-ops/pull/428) | spike(phase-0.5): hand-written group_run interface manifest | — |
| [#425](https://github.com/backspring-labs/squad-ops/pull/425) | fix(#422): command-safelist lint at the plan-authoring boundary + manifest retry runway | [#422](https://github.com/backspring-labs/squad-ops/issues/422) |
| [#421](https://github.com/backspring-labs/squad-ops/pull/421) | fix(#419/#420): typed acceptance at the builder seam + wire-shape criteria coercion | [#419](https://github.com/backspring-labs/squad-ops/issues/419) [#420](https://github.com/backspring-labs/squad-ops/issues/420) |
| [#418](https://github.com/backspring-labs/squad-ops/pull/418) | feat(#417): derive-on-read CycleOutcome + cycle-detail surface (SIP-0096 Phase 3 slice 2b) | [#417](https://github.com/backspring-labs/squad-ops/issues/417) |
| [#416](https://github.com/backspring-labs/squad-ops/pull/416) | feat(#415): persist per-run RunVerificationSummary (SIP-0096 Phase 3 slice 2a) | [#415](https://github.com/backspring-labs/squad-ops/issues/415) |
| [#413](https://github.com/backspring-labs/squad-ops/pull/413) | fix(#389): accept behaviorally-verified patches — stop re-rolling repaired tasks | [#389](https://github.com/backspring-labs/squad-ops/issues/389) |
| [#412](https://github.com/backspring-labs/squad-ops/pull/412) | feat(#411): CycleOutcome roll-up — pure aggregation core (SIP-0096 Phase 3 slice 1) | [#411](https://github.com/backspring-labs/squad-ops/issues/411) |
| [#408](https://github.com/backspring-labs/squad-ops/pull/408) | feat(#407): fullstack frontend_build as SIP-0096 evidence + declare required_checks (throttle ON) | — |
| [#409](https://github.com/backspring-labs/squad-ops/pull/409) | fix(#388): a non-succeeded run never reads `accepted` on zero evidence | [#388](https://github.com/backspring-labs/squad-ops/issues/388) |
| [#406](https://github.com/backspring-labs/squad-ops/pull/406) | chore(#404): sunset warmboot operational artifacts; distill era lessons for the book | [#404](https://github.com/backspring-labs/squad-ops/issues/404) |
| [#405](https://github.com/backspring-labs/squad-ops/pull/405) | fix(#399): apply the live-validated required_files builder-task seam (PR #402 merged the wrong cut) | [#399](https://github.com/backspring-labs/squad-ops/issues/399) |
| [#403](https://github.com/backspring-labs/squad-ops/pull/403) | refactor(#401): remove the dead SIP-0.8.8 skill layer end to end | [#401](https://github.com/backspring-labs/squad-ops/issues/401) |
| [#402](https://github.com/backspring-labs/squad-ops/pull/402) | feat(#399): record required_files as SIP-0096 evidence at the builder-task seam | [#399](https://github.com/backspring-labs/squad-ops/issues/399) |
| [#400](https://github.com/backspring-labs/squad-ops/pull/400) | fix(#394): remove the vestigial analysis skills instead of polishing dead JSON parsing | [#394](https://github.com/backspring-labs/squad-ops/issues/394) |
| [#398](https://github.com/backspring-labs/squad-ops/pull/398) | feat(#397): required-check tooling parity (preflight) + doctor verification category | [#397](https://github.com/backspring-labs/squad-ops/issues/397) |
| [#396](https://github.com/backspring-labs/squad-ops/pull/396) | feat(#395): canonical framework-check registry + reject unknown required_checks ids | [#395](https://github.com/backspring-labs/squad-ops/issues/395) |
| [#393](https://github.com/backspring-labs/squad-ops/pull/393) | fix(#276): verify the delivered backend imports, not just the tests | [#276](https://github.com/backspring-labs/squad-ops/issues/276) |
| [#390](https://github.com/backspring-labs/squad-ops/pull/390) | feat(#291): enforce build profile required_files at run completion | [#291](https://github.com/backspring-labs/squad-ops/issues/291) [#392](https://github.com/backspring-labs/squad-ops/issues/392) |
| [#391](https://github.com/backspring-labs/squad-ops/pull/391) | fix(#370,#371): provision the agent secret on deploy and fail honestly | [#370](https://github.com/backspring-labs/squad-ops/issues/370) [#371](https://github.com/backspring-labs/squad-ops/issues/371) |
| [#385](https://github.com/backspring-labs/squad-ops/pull/385) | fix(#374): re-run the failed check on a patch (pure-behavioral repair verification) | [#374](https://github.com/backspring-labs/squad-ops/issues/374) |
| [#387](https://github.com/backspring-labs/squad-ops/pull/387) | fix(#333): never fabricate agent identity (id + role); document intentional defaults | [#333](https://github.com/backspring-labs/squad-ops/issues/333) |
| [#386](https://github.com/backspring-labs/squad-ops/pull/386) | feat(SIP-0096 Phase 2 slice 2): final-state resolution for re-verified checks (#379) | [#379](https://github.com/backspring-labs/squad-ops/issues/379) |
| [#384](https://github.com/backspring-labs/squad-ops/pull/384) | docs: checks-as-issue-ledger vision + fine-grained issue-enumeration SIP stub | — |
| [#378](https://github.com/backspring-labs/squad-ops/pull/378) | feat(SIP-0096 Phase 2 slice 1): normalize task-result verification into the ledger (+ #376 honest-red guards) | — |
| [#383](https://github.com/backspring-labs/squad-ops/pull/383) | docs(SIP): propose Contract-First Build Scaffolding (+ interface-vs-implementation lesson) | — |
| [#382](https://github.com/backspring-labs/squad-ops/pull/382) | test(#380): enum-shadow architecture guardrail — fail CI on status string-literal comparisons | [#380](https://github.com/backspring-labs/squad-ops/issues/380) |
| [#369](https://github.com/backspring-labs/squad-ops/pull/369) | feat(SIP-0096 Phase 1): verification-integrity core — pure aggregation, evidence families, blocked_unverified verdict | [#368](https://github.com/backspring-labs/squad-ops/issues/368) |
| [#367](https://github.com/backspring-labs/squad-ops/pull/367) | feat: capture request_profile at the cycle level (SIP-0096 provenance) | [#365](https://github.com/backspring-labs/squad-ops/issues/365) |
| [#366](https://github.com/backspring-labs/squad-ops/pull/366) | docs: track 8 idea/vision drafts under docs/ideas | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0098-Verification-Contracts-Contract-Owned-Acceptance](../../design/sips/SIP-0098-Verification-Contracts-Contract-Owned-Acceptance.md) | new | implemented |
| [SIP-0099-Contract-First-Build-Scaffolding](../../design/sips/SIP-0099-Contract-First-Build-Scaffolding.md) | new | implemented |
| [SIP-0100-Scaffolded-Test-Harness-and](../../design/sips/SIP-0100-Scaffolded-Test-Harness-and.md) | new | implemented |
| [SIP-0101-Cycle-Replay-Harness](../../design/sips/SIP-0101-Cycle-Replay-Harness.md) | new | accepted |
| [SIP-0102-Ephemeral-Application-Sandbox](../../design/sips/SIP-0102-Ephemeral-Application-Sandbox.md) | new | accepted |
| [SIP-Capability-Backed-Agents](../../design/sips/SIP-Capability-Backed-Agents.md) | new | proposed |
| [SIP-Fine-Grained-Issue-Enumeration](../../design/sips/SIP-Fine-Grained-Issue-Enumeration.md) | new | proposed |
| [SIP-LLM-Emission-Contracts](../../design/sips/SIP-LLM-Emission-Contracts.md) | new | proposed |
| [SIP-Skill-Layer-For-Capabilities](../../design/sips/SIP-Skill-Layer-For-Capabilities.md) | new | proposed |
| SIP-Stack-Blueprint-Contract | new | proposed |
