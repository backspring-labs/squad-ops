---
sip_uid: '17922606138197288'
sip_number: 112
title: Project Lifecycle Management
status: accepted
author: Framework Committee
approver: jladd
created_at: '2026-10-16T00:00:00Z'
updated_at: '2026-10-17T22:57:20.587980Z'
original_filename: SIP-Project-Lifecycle-Management.md
---
# SIP-0112 — Project Lifecycle Management
## External Product Development, Managed Clones, and Governed Continuity

**Status:** Accepted (the owner, 2026-10-17, PR #2401)  
**Target Version:** 2.4, the MacBook lane's feature (the owner's direction, 2026-10-17), beside Outcome Evaluation on the Spark lane (§8); the shared fixture and E.4.1–E.4.4 and E.4.6 placed in 2.4.0 at acceptance (the ledger)  
**Author:** Framework Committee  
**Roles Impacted:** External Product Owner/Maintainer; Lead, Strategy, Dev, QA, Data  
**Date:** 2026-10-16  
**Revised:** 2026-10-17  
**Document Revision:** 8 — aligned with Outcome Evaluation's revision 2 (PR #2406: its terms and its §4.8) and the adopted 2.4 plan (`docs/plans/2-4-0-plan.md`). Revision 7: the tightening review: the contracts' details (§8.2.1), the sandbox boundary (§8.2.2), the shared fixture (§8.2.3), status vocabularies (§8.3.1), evidence tiers (§8.5), FR-02's two levels, E.4's dependencies and F.4's classes. Revision 6: the Spark lane's compatibility review of §8 applied (§8.6). Revision 5: the owner's design review of 2026-10-17 (PR #2401) reconciled: SIP-0047 retired as a runtime contract (Q30), instruction records owned by SIP-0110 (Q31), *Project Record* and a development configuration record in place of *Project Manifest* (Q32), that record named the *Project Development Configuration* (Q36), the Pulse IDEAs non-normative and SIP-0070's Pulse kept (Q33), greenfield creation required (Q34), and the 2.4 ownership and integration contract (Q35, §8)  
**Source Baseline:** `backspring-labs/squad-ops`, `main`, commit `7aecfa0b3ff6576f115eba10c2ee3465774e997d` (freshly pulled and inspected 2026-10-17); revisions 6 and 7's added claims read at `9fa8b5e8`; revision 5's added claims read at `c294ec79`, one docs-only commit later  
**Related SIPs:** SIP-0047 (Cycle Data Layout, Project Registry and `CycleDataStore`: implemented, retired as a runtime contract, Q30); SIP-0064 (Project Cycle Request API); SIP-0065 (CLI for Cycle Execution); SIP-0070 (Pulse Checks: the Cycle and Pulse this SIP keeps); SIP-0072 (its *development profile*, kept to one meaning by Q36); SIP-0074 (Console Cycle Operations UX); SIP-0102 (sandbox workspaces); SIP-0103 (Squad-Authored Manifest: owns the word *manifest*); SIP-0105 (stack blueprints); SIP-0108 (benchmark registry); SIP-0109 (Campaign Orchestration); SIP-0110 (Cross-Cycle Memory: project instructions); Outcome Evaluation (proposed, PR #1963: the Spark lane's 2.4 feature); Game Development Platform (proposed, PR #2405: the Godot/Roblox SIP, filed separately; builds on FR-17)  
**SIP Number:** 0112, assigned at acceptance (2026-10-17). The owner titled it *Project Lifecycle Management* at acceptance; revision 4's draft was titled *Independent Project Lifecycle Management*.

## Intake check

Checked against `sips/PORTFOLIO.md` on 2026-10-17, before this draft was recorded (CLAUDE.md, "SIP
System"). Revision 4 was filed as the owner wrote it, and its findings were Q30–Q33 in the portfolio's
§4. **The owner ruled on all four on 2026-10-17** (the design review of PR #2401), adding a greenfield
ruling (Q34) and the 2.4 parallel development agreement (Q35). Revision 5 reconciles the body with the
rulings. Revision 5's own intake found one more overlap (Q36), and the owner ruled it the same day.
Revision 6 applies the Spark lane's compatibility review of §8 (§8.6) and finds no new overlap. Its
gates read the 2.4 plan draft (#2387: D2, D3, D4), which places both lanes' features. Revision 7
tightens §8 for parallel implementation and finds no new overlap: three changes inside SIP-0102's
sandbox, which the Spark lane owns, are named as cross-lane tasks (§8.2.2).

- **Overlaps, and the boundary each gets:**
  - **SIP-0047** (Cycle Data Layout, Project Registry and `CycleDataStore`, implemented 2025-11-29) is
    the document revision 4 cited as `SIP_CYCLE_DATA_STORE.md`, its original filename. Its
    `CycleDataStore` was built in the v0 tree and removed with `_v0_legacy/` (`dd105d1a`). **Ruled
    (Q30):** retired as a runtime contract, its implemented status kept as history and its principles
    carried forward here (§A.1, §E.2). SIP-0047 §12a records the retirement.
  - **SIP-0109** (Campaign): the launcher, accepted trees, increment seeding and the brownfield reference
    scenario (§11a). The boundary is stated here (FR-08): Campaign keeps its state machine, budgets,
    launch and promotion; this SIP supplies the project's eligibility and source context, and maps
    accepted trees to Git revisions.
  - **SIP-0102** (sandbox): `WorkspaceStore`'s live trees, revisions and leases. The boundary is stated
    here (FR-05, §B.3): a managed clone reaches the sandbox through its existing boundaries, never as a
    second live tree, and a sandbox content hash is never a Git commit. It is one of the seven contracts
    shared with the Spark lane (§8.2).
  - **SIP-0110** (Cross-Cycle Memory): its *project instructions* record kind, pinned in the unit
    snapshot (Appendix A §A.3.6–§A.3.7, placed in 2.4.0 as #2179). **Ruled (Q31):** SIP-0110 owns
    project-instruction records, their versioning, applicability and snapshot binding; this SIP owns
    the external product's authority, the discovery of instructions in its repository, the development
    configuration and drift detection. There is one instruction store, SIP-0110's (§4, §B.5.1, FR-21).
    SIP-0110 §5k records the same boundary.
  - **SIP-0103's manifest:** one word, two meanings. **Ruled (Q32):** this SIP's records are the
    *Project Record* and the *Project Development Configuration* (§B.5), and the existing registry stays the
    authoritative source of Project identity and lifecycle.
  - **SIP-0072's *development profile*** (§10a, implemented: `DevelopmentProfile`, `DEVELOPMENT_PROFILES`,
    and the cycle request's `development_profile` key, which names the stack and which `prepare_cycle()`
    checks against `build_profile`) shared two words with Q32's *Project Development Profile*. **Ruled (Q36):**
    the record is the *Project Development Configuration*, so *development profile* keeps SIP-0072's one
    meaning (§B.5).
  - **SIP-0105** (stack blueprint) and the technical part of the Development Configuration; **SIP-0108**'s
    benchmark registry and the reference/benchmark profile: where a stack and a benchmark are declared.
    The boundary is stated in §B.4.1.
  - **SIP-0070** (Pulse Checks): its cadence-bounded Pulse is the one this SIP keeps (§A.2, Q33).
  - **Outcome Evaluation** (proposed, PR #1963; the Spark lane's 2.4 feature): seven shared contracts
    (§8.2), six named by the owner (Q35) and one added by the Spark lane's review and approved by the owner as written, 2026-10-17 (§8.6). This SIP evaluates no outcomes, and Outcome Evaluation takes a Project as any registered
    product (§8.3). Its *quality baselines* (Lighthouse, axe, lint) and this SIP's *inherited
    verification baseline* (the product's own checks on unmodified source) are different records, named
    in full each time.
  - **SIP-0064, SIP-0065, SIP-0074:** the project API, CLI and console this draft extends. The boundary
    is stated here (Appendix D): existing routes, commands and aliases are kept, and lifecycle writes
    are added beside them.
- **Conflict, ruled:** SIP-0047 prescribes the `cycle_data/<project_id>/<execution cycle ID>/` layout and a
  `CycleDataStore`, which this SIP does not restore (Q30).
- **Cited sources, now in the repository:** `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md` and
  `docs/ideas/IDEA_Cycle_and_Pulse_Execution_Model.md` are kept as non-normative history (Q33), each with
  a header saying so and an intake row in the portfolio. The Godot/Roblox game development SIP is filed
  as its own draft, `sips/proposed/SIP-Game-Development-Platform.md` (PR #2405).

**Ruled 2026-10-17** (the owner's design review of PR #2401; the portfolio's §4 records each):
- **Q30:** SIP-0047 is retired as an active runtime contract. Its implemented status stays as history and
  its retirement is recorded in it. Its principles of project identity, traceability and durable evidence
  are kept. Neither its `CycleDataStore` nor its filesystem layout is restored.
- **Q31:** the instruction split above. Changed upstream instructions never silently modify an execution
  snapshot already admitted (§B.5.1).
- **Q32:** *Project Record* and *Project Development Profile*; the existing registry stays authoritative
  for Project identity and lifecycle.
- **Q33:** the historical IDEAs are kept and marked non-normative. Their Pulse is not canonical where it
  differs from SIP-0070's cadence-based Pulse, and this SIP preserves current Cycle and Pulse behavior.
  The game SIP is filed separately, and FR-17 describes what this SIP offers future game adapters.
- **Q34:** greenfield Project creation is a required capability and stays in the completion scope.
  Brownfield development is the first acceptance benchmark. Game-specific adapters stay separate.
  **Greenfield ships in 2.4:** the 2.4 cut requires E.4.6 shipped (G6; the owner, 2026-10-17).
- **Q36:** the second record is renamed the *Project Development Configuration*, the owner's own phrase in
  Q31, so that *development profile* keeps SIP-0072 §10a's one meaning (the owner agreed the
  recommendation the same day).
- **Q35:** the 2.4 parallel development agreement (§8): the MacBook lane owns this SIP, the Spark lane owns
  Outcome Evaluation, and the two meet at six shared contracts. A seventh, added by the Spark lane's
  review, was approved by the owner as written, 2026-10-17 (§8.2 contract 7). This PR stays proposal-only until the
  owner approves it, and no integration branch is created yet.

## Delivery ledger (current as of 2026-10-21)

One row per part that ships separately, from Appendix E.4. Statuses: *shipped* (the release, the PR,
and the issue it closed), *placed* (the release and the open issue tracking it, labelled `sip:NNNN` once
numbered), *unplaced* (said deliberately), *dropped* (by the numbered amendment that dropped it), or
*deferred to N.x (ruled <date>)*. Updated in the PR that ships or re-places a part
(`tests/unit/architecture/test_sip_ledgers.py` holds it). The owner's direction of 2026-10-17 is a 2.4
feature on the MacBook lane, beside Outcome Evaluation's feature half on the Spark; the rows were placed at
acceptance (2026-10-17), each with its issue labelled `sip:0112`. Greenfield (E.4.6) ships in 2.4: the cut requires it (G6, the owner's
ruling of 2026-10-17). 2.4 carries E.4.1–E.4.4 and E.4.6, the two demonstrations; E.4.5 is required
before the SIP closes and need not ship in 2.4 (the owner, the same day). Dependencies are in E.4. Game-specific adapters have no row here: they are their own SIPs' (Q34).

| part | status | where |
|---|---|---|
| §8.2.3 the shared fixture product and contract tests, landing before either lane's first shared-contract PR (the MacBook lane writes it; the Spark lane adds its recorded reference, the 2.4 plan's D12) | **shipped**: Tally, with each lane's recorded outputs in four forms and the fixture's own checks (`tests/fixtures/shared_contract/`). Each contract test lands with the PR that builds its seam (agreed on #2407) | 2.4.0, PR #2440, issue #2407 |
| E.4.1 existing-product registration and authority: the writable registry cutover, its validated rollback and minimum enrollment | **shipped**: the writable registry with its cutover from `config/projects.yaml` and guarded rollback (#2444), and registration through `POST /api/v1/projects` and `squadops projects import` behind the locator rules and the write gate (#2452). The owner's R1–R6 are on #2408. Owner decisions take the event table's `owner_decision` operation, written from E.4.4 (#2411) | 2.4.0, PRs #2444 and #2452, issue #2408 |
| E.4.2 repository-native discovery and the inherited baseline, with the start declaration (§8.2 contract 7) | **shipped**: the managed clone and validation; the versioned Development Configuration with contract 7's start declaration and the repository's instruction sources; seeding with the commit-to-revision mapping (contract 3's seeding half); the inherited baseline through X-3a. Capture back to Git is E.4.3's (#2410) | 2.4.0, PR #2468, issue #2409 |
| E.4.3 the first scoped feature through the shared cycle path | **shipped**: the source-backed run, from the product's tree to a verified change contributed through its own process (#2484); the sync's attribution of SquadOps's own contributions and its hold on Cycles until drift is reconciled (#2610, H.2); the brownfield demonstration read against its pre-registration, with IR-2 passing live (#2611). The deletion form and a regression's repair round are deferred follow-ups, each with its own issue | 2.4.0, PRs #2484, #2610 and #2611, issue #2410 |
| E.4.4 the second feature after an outside contribution | **shipped**: a product's upstream read against its approved baseline, its contributions' standing, and the repository reference resolver (#2565); the sync's attribution and its hold on Cycles until drift is reconciled (#2610, H.2); the brownfield demonstration's second feature after an outside change, read (#2611); IR-3 as H.3 restates it (#2616) | 2.4.0, PRs #2565, #2610 and #2611, issue #2411 |
| H.4 a repository-backed Project's development profile derived from its tree, its capability gaps named, and Campaigns run on it (found as #2619; the owner, 2026-10-21) | **placed** | 2.5.0, #2619 |
| E.4.5 lifecycle completeness: update history, archive/restore, concurrency and conflict recovery (before close; not required in 2.4) | **unplaced**, deliberately: placed by a later plan, before the SIP closes | — |
| E.4.6 greenfield Project creation at an owner-approved external destination (required, Q34; shipped by the 2.4 cut, G6) | **placed** | 2.4.0, #2412 |
| E.4.7 direct attachment: writing in place in an existing checkout (optional, FR-02) | **unplaced**, deliberately: optional | — |

**What closes this SIP:** the shared fixture and E.4.1–E.4.6 shipped, and E.4.7 shipped or dropped. Greenfield creation (E.4.6)
is in the completion scope by the owner's ruling of 2026-10-17 (Q34), and leaves it only by a numbered
amendment the owner rules. The 2.4 cut requires it shipped (G6, ruled the same day).

---

**Decision:** SquadOps will act as a governed development team for independently owned products. The product repository remains authoritative and independently usable. SquadOps maintains a durable Project identity, development configuration, Cycles/Campaigns and evidence, and uses managed clones/worktrees to perform authorized work.

**Revision 4:** Clarifies external owner decision rights, establishes inherited quality before source changes, defines precedence and drift handling for development instructions, and makes an existing external product the first end-to-end proof. The detailed CLI reconciliation and implementation contracts are retained in the appendices.

**Revision 5:** Reconciles the owner's design review of 2026-10-17. SIP-0047 is retired as a runtime contract. Instruction records belong to SIP-0110, and this SIP discovers repository instructions, holds development configuration and detects drift. The *Project Manifest* becomes the Project Record and the Project Development Configuration (Q32, named by Q36). SIP-0070's Cycle and Pulse are kept. Greenfield creation is required. §8 records the 2.4 ownership and integration contract with Outcome Evaluation: shared contracts, integration regression scenarios and gates.

**Revision 6:** Applies the Spark lane's compatibility review of §8 (§8.6). No outcome result reaches a squad role through the Project Context or the handoff before Outcome Evaluation's phase 2, and after it only the proposal run. A scenario never runs against a live tree. The independence list covers squad task inputs and squad containers. Each lane's feature is done on its own evidence. Contract 7, how a product is started for evaluation, is added, and contracts 1, 2, 3 and 5 and IR-7 are corrected.

**Revision 7:** Tightens §8 for parallel implementation without changing its boundaries. Each contract states when its data is available, what a consumer does when it is absent or stale, how it is versioned and its minimum test; contracts 1, 5 and 7 get illustrative schemas. The sandbox boundary names three Spark-owned changes as cross-lane tasks. A shared fixture lets each lane test against the other's recorded outputs. FR-02 separates registration with managed clones (required) from writing in place in an existing checkout (optional, E.4.7). The owner ruled two refinements: *not run* never covers a lane's own demonstration, and E.4.5's lifecycle extras ship before the SIP closes, not necessarily in 2.4.

**Revision 8:** Follows Outcome Evaluation's revision 2 (PR #2406) and the adopted 2.4 plan. Its renamed terms replace the old *outcome* wording here: *scenario evidence*, *scenario result*, *contribution*, the *scenario measure* (`scenario_suite`, `scenario_target`). Contract 2 states its phase-1 and phase-2 fields as its §4.7 does, and contract 5 is renamed *evaluation references*. The plan's D12 rulings name who builds X-1 to X-3 and who writes the shared fixture. No boundary changes.

# 1. Direction and intended outcome

A product owner can bring an existing repository to SquadOps, request an improvement, review the resulting contribution and return later for further development. The product keeps its source structure, native tools, history and contribution process. Other developers remain able to work on the same repository.

The first success case is an unfamiliar, supported external repository enhanced through two governed iterations, with an outside contribution between them. Greenfield creation, a new product at an owner-approved external source destination with a product-appropriate structure, is a required capability (Q34): it follows the existing-product proof, ships in 2.4 (G6) and is part of what completes this SIP.

A SquadOps Project is the persistent development engagement record. It references the product and its repository; it is not the product's source container. The same Project ID persists across checkouts, branches, Cycles, Campaigns and accepted improvements.

# 2. Ownership and authority

| Party or location | Responsibility |
|---|---|
| External Product Owner/Maintainer | Product intent, priorities, scope, constraints, quality expectations and final product acceptance; may explicitly delegate engineering/contribution decisions. |
| External product repository | Authoritative source/history, native layout/build tools and product-defined integration refs/rules. |
| SquadOps Project and evidence stores | Stable ID, source/ref bindings, versioned development/acceptance configuration, instructions, baseline evidence, decisions and Cycle/Campaign history. |
| SquadOps managed clones/worktrees | Isolated development copies at pinned revisions, with controlled leases, source contributions and retained pending work. |
| Strategy / Lead / Dev / QA / Data | Propose, implement, verify and govern engineering work within the owner's delegation; preserve source/evidence provenance. |

The owner may delegate candidate acceptance or integration under established policy. Routine work already within that delegation does not require repeated permission requests. Internal candidate acceptance, final product acceptance and confirmed upstream integration are distinct decisions/states.

# 3. Development flow

1. **Register:** create a stable Project ID and record the external repository/ref, owner mandate, contribution policy and development metadata outside product source.
2. **Discover:** clone/fetch approved source and inspect native structure, toolchain, build/test commands and the repository's own instruction sources (contribution rules, maintainer guidance) without onboarding source edits.
3. **Establish the inherited baseline:** pin the unmodified source and effective development configuration; run agreed build/test checks and retain failures, environment gaps and UNVERIFIED checks.
4. **Implement:** start through the existing Project-targeted Cycle path, optionally under an existing Campaign, using isolated branches/worktrees and the agreed scope.
5. **Verify and accept a candidate:** compare relevant results with inherited evidence and evaluate the owner's acceptance policy. Retain exact tested source/configuration and any remaining defects.
6. **Contribute and confirm integration:** deliver through the product's permitted branch/review-request/patch/direct-integration process. Record the actual resulting upstream revision; a push or internal PASS alone is not integration.
7. **Continue:** fetch external changes, reconcile relevant source/instruction drift, refresh affected evidence and perform the next iteration against the same Project.

Approved but unintegrated development commits may seed later work under explicit continuation policy. Keep the development baseline separate from the last confirmed integrated-upstream revision; retain pending changes before workspace cleanup.

# 4. Quality baseline and development instructions

**Observe the product before changing it.** Baseline evidence binds the repository commit, applicable commands/working directories, the Development Configuration revision and instruction sources, dependency/toolchain/environment identity and actual results. An inherited FAIL stays FAIL. A check that could not execute stays UNVERIFIED. Neither is silently converted to a successful result because the squad did not cause it.

Check results and regression attribution are separate: a candidate may retain an inherited defect, introduce a regression, resolve a defect or have insufficient evidence for attribution. Owner-approved policy determines whether scoped development can proceed with identified inherited issues. The squad is not automatically tasked with fixing every pre-existing defect, and missing evidence does not grant a waiver. These are verification records of the product's own checks; scenario evidence (independent held-out scenarios, quality baselines, contribution) is Outcome Evaluation's (§8.3).

**Bind SquadOps configuration to the product's instructions.** Applicable runtime access restrictions and authorized owner/maintainer decisions govern the work; applicable contribution rules and repository-native build/test definitions govern product execution; the Project Development Configuration records how to execute them. Explicit, authorized exceptions are versioned and auditable. A stale profile cannot silently override current product instructions, and repository content cannot grant runtime privileges.

**Instructions are SIP-0110's records** (Q31). This SIP finds the instruction sources in the product's repository, holds the development configuration and detects drift. SIP-0110 records the instructions themselves: their revisions, their applicability, and the snapshot that pins them when a standalone Cycle is created or a Campaign is admitted. There is one instruction store, SIP-0110's. A changed upstream instruction reaches Cycles and Campaigns admitted afterwards. One already admitted keeps what it bound, and changes only through SIP-0110's authorized, recorded re-binding (§B.5.1).

Before feature-source changes, inspect relevant upstream changes to instructions, build/test scripts, dependencies and toolchains. Reconcile/revalidate the affected Development Configuration and baseline checks before relying on them. Unresolved policy conflicts stop the affected operation and are reported through existing governance. Verification is scoped to relevant changes and the agreed contract rather than requiring an indiscriminate rerun of every check.

Registration readiness, development eligibility, engineering-candidate acceptance and external integration remain separately visible. A registered Project can have pending baseline work; that state is not a claim that the product passes its checks.

# 5. Mandatory integration boundaries

- Extend the existing plural `squadops projects` CLI and `/api/v1/projects` resources. Preserve `projects list/show`, existing aliases and shared client/config/auth/output behavior.
- Preserve `squadops cycles create <project_id> --squad-profile ...`, request-profile/PRD behavior and immediate first-Run execution. Standalone and Campaign launches share Project context/eligibility checks; preserve the Campaign launcher and control authority.
- Keep one selected authoritative Project registry; it stays the source of Project identity and lifecycle, and a Project Record is its entry (Q32). The current inspected provider is YAML-backed; lifecycle writes require an explicit writable-provider migration/cutover, with existing IDs and history preserved.
- Keep one instruction store, SIP-0110's (Q31). Repository instruction sources reach a task only through its records, bound when the unit is admitted.
- Keep SIP-0070's Cycle and Pulse behavior (Q33): cadence-bounded pulses, their boundary checks and repair loop, and the correction loop's decisions (SIP-0086) are unchanged. No Project, Campaign, repository or workspace closes a pulse or changes cadence.
- Keep outcome evaluation in Outcome Evaluation (Q35): this SIP stores references to its results and builds no scenario store, scenario runner, quality baseline or contribution reading (§8.3).
- Keep SIP-0047 retired (Q30): neither its `CycleDataStore` nor its `cycle_data/<project_id>/<execution cycle ID>/` layout returns.
- Keep external Git commits, sandbox revision hashes, artifact baseline pointers and Campaign accepted-tree identities distinct and linked by evidence. Preserve existing artifact/sandbox contracts and historical readers.
- Store required SquadOps metadata outside product source by default. No sample conversion, mandatory `.squadops` files, prescribed source directories or replacement build system is required. Unsupported tooling/layout produces an explicit capability gap.
- Honor product integration policy and expected-target-head checks at the actual write boundary. Bind verification to tested content/configuration and revalidate affected results after changes, including rebase/merge/squash.
- Archive the SquadOps engagement without changing external repository ownership/lifecycle or losing unintegrated contributions. Product builds remain usable with native tooling independently of SquadOps.

# 6. Scope and delivery priority

The lifecycle includes create, import/clone, attach, list/show, validate, update, history, archive/restore, source/workspace management and durable handoff. Technical targets use adapters; repository layout remains product-defined. Production hosting, a new source-control system and replacement Campaign/orchestration semantics are excluded.

Prioritize existing-product registration, managed cloning, native discovery/baseline verification, a first feature contribution, and a second feature after an outside update. Complete lifecycle/rollout hardening and additional onboarding modes as subsequent slices. Greenfield creation is required (Q34, E.4.6) and follows the existing-product proof, which it never substitutes for; direct attachment is a later slice (E.4.7). Game-specific adapters belong to their own SIPs and build on the capabilities in FR-17. Operations enabled in any slice already need their applicable authorization, idempotency and integrity checks.

The implementation details, proposed schemas/routes and migration choices live in the appendices. They are explicitly distinguished from verified contracts at the pinned source revision.

# 7. Primary acceptance demonstration

An external product maintainer supplies an unfamiliar supported repository with a non-sample layout and a scoped feature request. Demonstrate all of the following:

- Registration assigns a stable Project ID and complete out-of-repository metadata with no onboarding changes to product source or required SquadOps files.
- The squad records owner delegation, effective instructions and the agreed build/test results at the pinned unmodified source, including inherited defects or UNVERIFIED checks where present.
- A first Cycle delivers a scoped feature, relevant QA and a traceable contribution through the product's normal acceptance/integration process.
- An outside developer advances the repository or relevant development instructions. A later Cycle detects/reconciles the change, refreshes affected Development Configuration and baseline evidence and delivers another feature through the same Project.
- Internal candidate approval, check results/regression attribution, pending contributions and confirmed integrated revisions remain distinguishable throughout.
- Handoff/archival retains pending work and evidence while the product remains usable with its native toolchain. Existing registered references such as `group_run` retain compatibility.

Greenfield creation is the second required demonstration, after this one (Q34). Target adapters, games among them, are demonstrated by their own SIPs. The detailed Definition of Done is in Appendix E.7.

# 8. The 2.4 parallel development agreement

**Ruled by the owner, 2026-10-17** (Q35, the design review of PR #2401). This SIP is 2.4's feature on the MacBook lane. Outcome Evaluation (proposed, PR #1963) is 2.4's feature on the Spark lane. The lanes develop independently and meet at the contracts in §8.2: the six the owner named, and a seventh the Spark lane's review added, approved by the owner as written, 2026-10-17. Outcome Evaluation's column in §8.2 matches its revision 2's §4.8 (PR #2406, for the owner's acceptance), which turned the Spark lane's review (§8.6) into its design.

## 8.1 Ownership

| | MacBook lane | Spark lane |
|---|---|---|
| owns | Project Lifecycle Management (this SIP) | Outcome Evaluation |
| builds | the Project Record and the registry cutover; the Project Development Configuration; managed clones; inherited verification baselines; Git revisions and their mappings; repository instruction discovery and drift detection; the project CLI and API writes | the held-out scenario store and runner; quality baselines; the intervention ledger's classifications; contribution and the derived metrics; the campaign objective's scenario measure (its §4.7, a SIP-0109 amendment) |
| never builds | an outcome evaluation subsystem: scenarios, a scenario runner, quality baselines or contribution readings | a project model of its own, or behavior that assumes a Project is a predefined sample application |

A change to a file the other lane owns goes through that lane's review (CLAUDE.md, "Versioning & Release Cadence": features are pinned by file ownership). The sandbox (`src/squadops/sandbox/`, SIP-0102) is the Spark lane's. The MacBook lane owns external repository management, managed clones, Git mappings and Project source promotion. Both lanes integrate through the sandbox's existing seams, `WorkspaceStore` and `ExecutionSandboxPort`, and neither creates a second workspace authority or live tree. A change inside the sandbox is a cross-lane task (§8.2.2), never a side effect of either feature.

## 8.2 Shared contracts

| contract | today's seam | this SIP adds | Outcome Evaluation reads or adds | the rule |
|---|---|---|---|---|
| 1. Project identity and source revision | `Project` (`src/squadops/cycles/models.py:293`); `ProjectRegistryPort`; `config/projects.yaml` | the Project Record as the registry entry; the development-baseline and integrated-upstream Git revisions | records the Project ID and the identity of the tree it evaluated; the Git revision is resolved through contract 4's mapping, joined by the cycle ID, and never copied into a result | one registry for every reader; Project IDs immutable; a Git commit is never stored as a sandbox hash or an accepted-tree identity |
| 2. `prepare_cycle()` input and context | `prepare_cycle()` (`src/squadops/api/routes/cycles/cycles.py:387`); `CycleCreateRequest` (`src/squadops/api/cycle_schemas.py:40`, `extra="forbid"`); `cycle_request_body()`; the Campaign launcher (`src/squadops/campaigns/launch_requests.py`); Campaign admission: `CampaignCreateRequest` (`src/squadops/api/campaign_schemas.py:55`) setting `CampaignObjective` (`src/squadops/campaigns/models.py:273`) | typed source context and source preconditions, persisted before dispatch (§D.3); the Development Configuration revision | nothing at `prepare_cycle()` or in a launch request. Phase 1: an optional `scenario_suite` on `CampaignCreateRequest`, stored in Outcome Evaluation's own record and keyed by the campaign. Phase 2: `scenario_suite`, `scenario_target` and `quality_baseline` on `CampaignObjective`. Each lands with a numbered SIP-0109 amendment (its §4.7) | each lane adds its own typed fields and repurposes none of the other's; FR-08's Project eligibility and Outcome Evaluation's objective fields meet at Campaign admission; the standalone and Campaign preparation tests run on every change; SIP-0110's #2179 changes this seam in 2.4.0 too |
| 3. `WorkspaceStore` integration | `src/squadops/sandbox/workspace.py` (SIP-0102) | a Git checkout at a pinned commit exposed as the live tree; verified changes captured back to Git; a mapping from sandbox revision to Git commit | stands up the evaluated tree from its identity (SIP-0109's `FileTree.identity`, `src/squadops/campaigns/evaluator_trees.py:60`) and names it by that identity, never by sandbox revision | sandbox revisions stay content hashes; no second live tree; no scenario file enters a workspace. A sandbox revision ID (`compute_revision_id`, `src/squadops/sandbox/models.py:78`) and a tree identity are different hashes of the same files, and are never compared. A scenario never runs against a live tree: the evaluated tree is started in a disposable copy whose writes are discarded, so nothing a scenario caused is captured into a revision or a commit |
| 4. Campaign accepted-tree identities | `infra/migrations/1630_campaign_accepted_tree.sql`; `src/squadops/campaigns/increment_tree.py` (SIP-0109) | a mapping from each accepted tree to the Git revision it became | reads regression against the previous accepted tree (its §4.1) | SIP-0109 owns the identity; both lanes read it as SIP-0109 defines it; the mapping lives in this SIP's records |
| 5. Evaluation references | Outcome Evaluation's evaluation records (to be built): one per evaluation run, a cycle against one suite | references to them in Project history (FR-09) | produces them: the evaluation ID and suite digest, with the Project ID, the campaign and cycle IDs, and the evaluated and previous accepted tree identities | this SIP stores the reference in Project history. It never stores steps and never recomputes a reading. No scenario result reaches a squad role's inputs through the Project Context or the handoff until Outcome Evaluation's phase 2 is ruled, and after it only the proposal run's (its §4.5) |
| 6. Project instructions and snapshot binding | SIP-0110 §0.7, §A.3.6–§A.3.8; #2179 (2.4.0) | repository instruction discovery; drift findings; the resolver for a repository reference at the unit's pinned commit (§B.5.1) | compared increments read the instruction sets their units pinned; a set that differs between them is a changed listed input (SIP-0110 §0.12) | one store, SIP-0110's; an admitted snapshot changes only by SIP-0110's re-binding |
| 7. Starting the product for evaluation (added by the Spark lane's review; approved by the owner as written, 2026-10-17) | the Development Configuration's `technical.commands_ref` (§B.5); for a blueprint Project, the stack's probe and render profiles (`profile_for_stack`, `src/squadops/capabilities/handlers/probe_runner.py:133`; `render_profile_for`, `src/squadops/capabilities/handlers/route_rendering.py:77`) | the commands to install, build and start the product at a given tree, its readiness check, and the base URLs or entry points it serves, versioned with the Development Configuration | reads those commands at the Development Configuration revision the unit pinned | Outcome Evaluation never infers how to start a product from a sample application; a Project with no declaration reports every scenario `blocked_unverified`, with that reason |

**Every change to a shared contract** names the contract in its PR body, carries the other lane's review, adds a wiring test that enters at the caller the live cycle uses (`docs/TEST_QUALITY_STANDARD.md`, anti-pattern 6a), and is additive: no field is repurposed or removed.

### 8.2.1 What each contract guarantees

The table above gives each contract's owner, producer and consumer. This one gives what an
implementation needs to build against it alone. Fields live with the contract's owner: contracts 3, 4
and 6 use SIP-0102's, SIP-0109's and SIP-0110's as those SIPs define them, and only the three contracts
whose data this SIP or Outcome Evaluation creates get a schema here.

| contract | available | absent, stale or unavailable | versioning | minimum contract test |
|---|---|---|---|---|
| 1 | when the Project is `READY`; pinned into a Cycle's source context before dispatch (FR-09) | a Project not `READY` is refused at `prepare_cycle()` with a typed error; an explicit stale precondition is rejected (FR-09); a tree whose Git revision has no mapping yet is recorded by identity alone, marked unresolved, never guessed | `ProjectSourceContext` carries a schema version; fields are only added | `prepare_cycle()` with the fixture's Project: `READY`, not `READY`, and a stale pinned commit |
| 2 | at `prepare_cycle()` for a standalone Cycle; at Campaign creation for a Campaign | an unknown field is refused (`extra="forbid"`); each lane's fields are optional to the other lane | additive typed fields, each owned by one lane | the standalone and Campaign preparation tests, on every change to this seam |
| 3 | when a Git checkout is seeded into the live tree (§8.2.2) | a product the seam cannot carry yet is refused with a named capability gap, never seeded in part | `WorkspaceRevision` as SIP-0102 defines it; the sandbox revision to Git commit mapping is this SIP's record | seed the fixture at a pinned commit; capture a change back to a commit; the mapping resolves both ways |
| 4 | when SIP-0109 records a promotion | an accepted tree with no Git mapping yet is reported as unmapped | SIP-0109's identity, unchanged; the mapping is this SIP's record | IR-5 |
| 5 | when Outcome Evaluation writes an evaluation record | Project history shows *not evaluated*, never an inferred result; a reference whose record cannot be read is kept and marked unresolved | `OutcomeEvaluationRef` carries a schema version; it keeps its name while Outcome Evaluation keeps its own (that SIP's A1) | write the fixture's recorded reference into Project history; read it back; refuse an unknown major version |
| 6 | when SIP-0110 pins the unit's snapshot | as SIP-0110 rules: a binding instruction that cannot be resolved holds dispatch | SIP-0110's | IR-3 |
| 7 | when a Development Configuration revision is confirmed (E.4.2) | no declaration: every scenario is `blocked_unverified`, reason "no start declaration"; a start or readiness failure: `blocked_unverified`, reason "start failed"; a secret the Project has not declared for evaluation, or the owner has not approved: `blocked_unverified`, reason "secret not available" (Q40); a newer revision never applies to a unit already pinned | part of the Development Configuration's schema version | start the fixture from its declaration; a missing declaration; a readiness timeout |

**Identifiers never substitute for one another.** A Project ID, a Git commit (40 hexadecimal
characters), a sandbox revision ID (`compute_revision_id`), a Campaign tree identity
(`FileTree.identity`) and an evaluation ID each name one kind of thing. A record that needs another kind
resolves it through a mapping, and a consumer that receives an unknown schema major version refuses it
with a typed error rather than reading part of it.

**Secrets in an evaluation (Q40, ruled by the owner 2026-10-17; Outcome Evaluation's A4 is the same question).** The runner resolves only the secret references a Project declares for evaluation and the owner approves for that Project: test credentials, never the product's production secrets. They are resolved into the disposable copy's environment when it starts, are never written to a file, a log, a record or a squad agent's input, and are discarded with the copy.

Illustrative schemas (names may change in the PRs that build them; the meanings may not):

```yaml
# Contract 1: produced by this SIP, read by Cycle preparation, the Campaign launcher and Outcome Evaluation
ProjectSourceContext:
  schema: project-source-context/v1
  project_id: str                          # the registry's ID, immutable
  record_version: int                      # the Project Record's version
  development_configuration_revision: int
  repo_uri: str                            # the authoritative external locator
  development_baseline_commit: str         # Git commit, 40 hex characters
  integrated_upstream_commit: str | null   # last confirmed integrated revision

# Contract 5: produced by Outcome Evaluation, stored by this SIP in Project history
OutcomeEvaluationRef:
  schema: outcome-evaluation-ref/v1
  evaluation_id: str                       # Outcome Evaluation's record ID, opaque here
  suite_digest: str                        # the suite's content digest
  project_id: str
  campaign_id: str | null                  # null only outside a campaign: the reference scenario (SIP-0109 §11a, #1804) and #1959 replays
  cycle_id: str
  evaluated_tree_identity: str             # SIP-0109 FileTree.identity
  previous_accepted_tree_identity: str | null

# Contract 7: in the Development Configuration, under technical.commands_ref; read by Outcome Evaluation's runner
start:
  working_directory: .                     # repository-relative
  install: [[argv...]]                     # optional
  build: [[argv...]]                       # optional
  start: [argv...]                         # required for evaluation
  readiness: {kind: http | tcp | command, target: str, timeout_seconds: int}
  entry_points:                            # at least one
    - {kind: http_base | ui_base | other, url: str}
  evaluation_environment: {NAME: secret://ref}   # test credentials declared for evaluation, owner-approved per Project; never production secrets (Q40)
```

### 8.2.2 How a Git checkout becomes the live tree

- **Seeding:** the MacBook lane checks out the pinned commit in its managed clone and seeds the Cycle's
  live tree through `WorkspaceStore.seed(cycle_id, files, origin=…)`
  (`src/squadops/sandbox/workspace.py:180`). The sandbox cuts the first revision, and this SIP records
  the sandbox revision ID beside the commit.
- **Capture:** a verified change is read back through the sandbox's revisions (`current_files()`,
  `get_revision()`), written into the managed clone and committed there. This SIP records the commit
  beside the sandbox revision it came from. The sandbox never runs Git.
- **Three changes inside the sandbox, each a cross-lane task:** the Spark lane owns the files and reviews
  them, and the 2.4 plan's D12, ruled 2026-10-17, has the Spark lane build them and the MacBook lane review each
  as its consumer (`docs/plans/2-4-0-plan.md`).
  - **X-1, a revision origin for a Git checkout.** `RevisionOrigin` is a closed set: `scaffold_seed`,
    `agent_patch`, `promoted_outputs`, `acceptance_assembly` (`src/squadops/sandbox/models.py:23`).
  - **X-2, binary files.** `seed()`, `current_files()` and revision persistence read and write UTF-8 text
    only. Until X-2 ships, a product with binary files is refused at seeding with that capability gap,
    and none of its files are dropped.
  - **X-3, a product's declared commands, in a disposable copy.** `ExecutionSandboxPort` runs a stack's
    install, build, tests and start (`src/squadops/ports/sandbox.py:33`), and `start_application` mounts
    the cycle's live tree and runs the app as its owner, so the app can write its state there
    (`adapters/sandbox/container_backend.py:157-164`, `:316-321`). Contract 7 needs the sandbox, or the
    evaluation runner, to run a product's own declaration at the revision the unit pinned, and to start
    that revision in a disposable copy built from it and discarded afterwards, never the live tree
    (contract 3). Declared commands keep the sandbox's least-privilege posture (`cap_drop_all`,
    `no_new_privileges`, the workspace owner's uid).
- **Neither feature waits on the other's internals:** E.4.2 works for text-only products before X-2, and
  the fixture (§8.2.3) stands in for each lane's outputs until they ship.

### 8.2.3 The shared fixture and contract tests

- **One fixture product,** small and unfamiliar: its own layout (no SquadOps scaffold), native build, test
  and start commands, one check that fails before any change (IR-9's inherited failure) and one binary
  asset (X-2). It is kept as files and made into a Git repository by the test that uses it, so either
  machine runs it alone.
- **Each lane's outputs, recorded beside it:** a `ProjectSourceContext`, a Development Configuration with
  its start declaration, a workspace-to-commit mapping and an inherited baseline (the MacBook lane's), and
  an `OutcomeEvaluationRef` (the Spark lane's). Each comes valid, with a required field missing, with an
  unknown schema major version and with a stale commit.
- **Contract tests enter at the production seams:** `prepare_cycle()` and the Campaign launcher
  (contracts 1 and 2), `WorkspaceStore.seed()` (contract 3), the Project history write (contract 5) and
  the evaluation runner's start (contract 7). Contracts 4 and 6 keep SIP-0109's and SIP-0110's tests,
  with IR-5 and IR-3.
- **It lands first,** as one PR both lanes review, before either lane's first contract PR. The MacBook
  lane writes it, and the Spark lane adds its recorded `OutcomeEvaluationRef` in the same PR (the 2.4
  plan's D12). A change to it is a shared-contract change (G4).

## 8.3 What each lane may rely on

- **This SIP evaluates no outcomes.** Its checks are the product's own build and test checks, run through the existing verification path (FR-10, FR-20) and reported as check results (PASS, FAIL, UNVERIFIED) with regression attribution. They are verification records. Independent held-out scenarios, quality baselines (Lighthouse, axe, lint), the intervention ledger and contribution are Outcome Evaluation's, and this SIP stores references to them.
- **Outcome Evaluation takes a Project as any registered product:** an existing external repository with its own layout and tooling, a greenfield product, or a reference application. Scenario surfaces come from the scenario's authors and the Project's own interface; a scenario that cannot run reports `blocked_unverified` (its §4.1). A sample application's routes, fixtures or interface manifest are never a default.
- **Held-out scenario independence, as this SIP keeps it:**
  1. Scenario steps and checks never enter the Project Record, the Development Configuration, the Project Context (FR-04), handoff metadata (FR-09), a project instruction or its references (SIP-0110), a managed clone, a workspace, the product repository, a squad task's inputs or any squad agent's container. The scenario runner runs outside every squad agent's container.
  2. Scenarios are stored outside every location this SIP manages: the product repository, the managed clone cache and the workspace roots.
  3. Repository instruction discovery reads the product repository only. A scenario store is never an instruction source.
  4. This SIP's records hold the evaluation record's reference (contract 5). No scenario result reaches a squad role through the Project Context or the handoff until Outcome Evaluation's phase 2 is ruled; after it, only the proposal run sees each scenario's goal and result (its §4.5).
  5. IR-4 (§8.4) tests 1–4.

### 8.3.1 Status vocabularies

Four vocabularies, each recorded where it is produced, and none standing in for another. They map onto
SIP-0096's evidence families rather than adding a scheme.

| vocabulary | values | recorded by | SIP-0096 | rules |
|---|---|---|---|---|
| native check result | `PASS`, `FAIL`, `UNVERIFIED`, each with an attribution: `inherited`, `introduced/regressed`, `resolved`, `unverified attribution` (FR-10, FR-20) | this SIP, per check | executed-and-passed, executed-and-failed, not-executed | an inherited `FAIL` is never an introduced regression; `UNVERIFIED` never credits |
| evaluation result | passed, failed, `blocked_unverified` (Outcome Evaluation's revision 2, §4.1) | Outcome Evaluation's record | the same three families | a missing runner, a missing start declaration or a failed start is `blocked_unverified`, never passed; an evaluation never rewrites the inherited baseline |
| scenario applicability | applicable, not applicable | Outcome Evaluation, per scenario | none: *not applicable* is not evidence | counted in no rate; never reported as `blocked_unverified` or as passed |
| integration execution | run, *not run* | the integration record (§8.4) | none | a *not run* record carries §8.5's four fields |

The phase-1 boundary holds across all four: no evaluation result reaches a squad role before Outcome
Evaluation's phase 2, and after it only the proposal run (§8.2 contract 5).

## 8.4 Integration regression scenarios

Each enters at the seam the live cycle uses and asserts what reaches the other lane.

| id | scenario | what it proves | lane |
|---|---|---|---|
| IR-1 | After the registry cutover, `group_run`, `hello_squad`, `run_crysis`, `play_game` and `agent_chess` create Cycles through `cycles create` and `POST /api/v1/projects/{project_id}/cycles` | the same IDs, PRD resolution, cycle and run IDs and artifact paths; `projects list/show` changed only by added fields | MacBook |
| IR-2 | One Project at one pinned revision, launched standalone and through the Campaign launcher | both reach `prepare_cycle()` with the same typed source context and Development Configuration revision, and each pins a SIP-0110 snapshot under its own snapshot owner | MacBook, with SIP-0110's #2179 |
| IR-3 | A Campaign is admitted; an outside commit then changes a repository instruction source | the Campaign's later Cycles keep the admission binding and carry a drift finding; a standalone Cycle created afterwards binds the new content; a re-binding changes the Campaign only as a recorded intervention (restated by H.3, after SIP-0110 §5ad and H.2) | MacBook, with SIP-0110's #2179 |
| IR-4 | An increment of an external Project runs with a scenario suite | no scenario step in any rendered prompt (Outcome Evaluation §7, prediction 2), any stored squad task envelope, any squad agent's container, the Project Context, handoff metadata, a project instruction, the managed clone, a workspace or the product repository; no scenario result in the Project Context or the handoff before phase 2 | both |
| IR-5 | An accepted increment of an external Project | sandbox revision, Git commit, Campaign accepted tree and Outcome Evaluation result resolve to one another through this SIP's mappings, and none is stored in another's field | both |
| IR-6 | An external Project with its own layout and no SquadOps interface manifest runs through Outcome Evaluation, started by contract 7's commands | scenarios run on the surfaces their authors declare or report `blocked_unverified`; a surface kind the product lacks is recorded not applicable; nothing falls back to a sample application | Spark |
| IR-7 | A greenfield Project, created at an owner-approved external destination, runs its first Campaign (after E.4.6 ships) | Outcome Evaluation reads it as it reads any other Project | both |
| IR-8 | A Project registered after the cutover | `projects show`, standalone creation, the Campaign launcher and Outcome Evaluation's reads see it at once, with no YAML shadow | MacBook |
| IR-9 | A product with an inherited failing native check | the check stays FAIL with attribution `inherited`; Outcome Evaluation's reading of the same increment is its own; neither record derives from or rewrites the other | both |
| IR-10 | The counted regression pair on a deploy carrying both lanes, with `lessons: disabled` (SIP-0110) | the cadence policy, pulse-boundary checks and correction paths are unchanged, and the pair holds its verdict; a difference in pulse or correction behavior is a finding | both |

## 8.5 Release and integration gates

| gate | when | condition | status |
|---|---|---|---|
| G1 | until acceptance | this PR stays proposal-only: no SIP number, no issues, no placement | ruled 2026-10-17 |
| G2 | until the owner creates one | no integration branch | ruled 2026-10-17 |
| G3 | before acceptance | the Spark lane's compatibility review of §8.2 recorded in §8.6 | ruled 2026-10-17 |
| G4 | every PR touching a shared contract | §8.2's rule: the contract named, the other lane's review, a wiring test, additive only | ruled 2026-10-17 (approved as written) |
| G5 | on the integration branch, when the owner opens it | IR-1 to IR-10 are the integration's evidence, run on a deploy carrying both lanes. Each lane's 2.4 feature is done on its own evidence; an IR scenario whose other-lane prerequisite has not shipped reports *not run*, with its reason, in the cut record | ruled 2026-10-17 (approved as written, as the Spark lane's review revised it) |
| G6 | the 2.4 cut | IR-1 to IR-10 pass on the cut deploy, or report *not run* with the missing prerequisite named (G5). IR-4 to IR-9 need Outcome Evaluation's phase 1 only; its phase 2 is conditional (the 2.4 plan's D4) and not required; the brownfield demonstration (§7) is pre-registered and read; greenfield (E.4.6) is shipped; the cut record states what each lane's evidence does not cover (CLAUDE.md, "Release cut") | ruled 2026-10-17 (approved as written, with the Spark lane's phase 2 clause; its greenfield clause ruled the same day: shipped) |
| G7 | the 2.4 measurement window (the 2.4 plan's D3) | both lanes agree on the window's frozen deploy, and neither lane deploys a change inside the window | ruled 2026-10-17 (approved as written; proposed by the Spark lane's review) |

**Evidence tiers and *not run*** (the owner's clarification of G5 and G6, 2026-10-17):
- *development integration evidence:* the integration scenarios, run on a deploy carrying both lanes (G5);
- *feature completion evidence:* each feature's own acceptance criteria. For this SIP, those are E.7,
  the brownfield demonstration (§7) and the greenfield proof;
- *release acceptance evidence:* the cut record (G6).

*Not run* applies only to an integration scenario whose prerequisite from the other lane has not shipped.
It never covers a lane's own acceptance demonstration: the brownfield demonstration and the greenfield
proof are run and read. A *not run* record names the missing prerequisite, the shared contract affected,
the capability whose evidence is absent, and whether the release claim is affected. Outcome Evaluation's
phase 2 stays conditional on its measurement and is not required for this SIP's completion.

**The 2.4 plan** (`docs/plans/2-4-0-plan.md`, adopted 2026-10-17, #2387) schedules what this section states: the lanes (§8.1), the seven contracts and
the fixture (§8.2), IR-1 to IR-10, G4 to G7, both demonstrations, phase 2's condition and the frozen
window deploy. This SIP states them; the plan sequences them.

## 8.6 The Spark lane's compatibility review

**Given 2026-10-17** (19:20 ET), by the Spark lane's supervisor session (Claude Code on the Spark), on §8.1–§8.6 at `b4bbeb56`: PR #2401's comment of 2026-10-17 (`issuecomment-6242996612`). Gate G3 is met.

**It rests on** Outcome Evaluation revision 1 (`sips/proposed/SIP-Outcome-Evaluation.md` on `main` at `9fa8b5e8`, last changed in `903c046f`: §4.1–§4.7, §6, §7), the 2.4 plan draft (#2387 at `11066598`, §1.2–§1.4) and `main`'s code at `9fa8b5e8`. Outcome Evaluation's design review (the 2.4 plan's D2) is not ruled, so an answer past revision 1 is the Spark lane's **intent**, not ruled design. It found nothing in conflict with the owner's four constraints.

| question | the Spark lane's answer | where this SIP takes it |
|---|---|---|
| 1. Does Outcome Evaluation pin anything at `prepare_cycle()` or at Campaign admission? | Nothing at `prepare_cycle()` or in a launch request. At Campaign admission, its §4.7 fields on `CampaignObjective`, set by `CampaignCreateRequest`; phase 1's suite is pinned on the campaign at creation (intent) | contract 2 |
| 2. How is the evaluated tree named? | By SIP-0109's tree identity with its cycle ID: `FileTree.identity` for the tree it ran on, `AcceptedTree.identity` (`src/squadops/campaigns/progress.py:612`) for the one it compares against. Never by sandbox revision (a different hash of the same files) and never by Git commit (a candidate has none yet). **Unverified:** whether a candidate's evaluated identity equals the identity its promotion records; the join to the accepted tree goes through the cycle ID | contracts 1 and 3 |
| 3. Surfaces for a Project with no interface manifest or no browser surface? | Revision 1 can evaluate only a SquadOps blueprint app; revision 2 changes that (intent). A scenario declares its own surfaces by kind (HTTP endpoints, browser pages, later others such as FR-17's game surfaces); a manifest, where one exists, only checks they exist; a scenario sets up its own data. With no browser surface, browser scenarios, Lighthouse and axe are *not applicable*, apart from `blocked_unverified`; a surface kind with no runner yet is `blocked_unverified`. Lint is recorded as not measured off the scaffold stacks, and the product's own linter is never used in its place (that is FR-20's inherited check). Starting the product needs a declaration Outcome Evaluation cannot own | contract 7; IR-6 |
| 4. Where are held-out scenarios stored? | A store of their own in the runtime API's Postgres, behind their own port, with no route a squad agent's identity can read; not the artifact vault. The runner fetches the steps by suite digest per run, holds them in memory, and runs outside every squad agent's container (intent; where, is for Outcome Evaluation's design review) | §8.3 item 1; IR-4 |
| 5. Which identifier does Project history reference? | The evaluation record's ID with the suite's content digest: one record per evaluation run, since one cycle can be evaluated more than once (a re-run after `blocked_unverified`, a #1959 replay, a second suite) | contract 5 |
| 6. Do compared units' pinned instruction sets need to match? | Not for a per-increment reading: a scenario reads the app, and a campaign's increments share its admission binding. For a comparison of squad behaviour across units, they are a listed input, never a gate (SIP-0110 §0.12) | contract 6, as drafted |

**Changes it asked for, all applied in revision 6:**
- *Conflicts:* outcome results kept out of squad roles' inputs before phase 2, and after it given only to the proposal run (contract 5, FR-04, FR-09 item 4, §8.3 item 4); no scenario against a live tree (contract 3); squad task inputs and squad containers added to the independence list and IR-4 (§8.3 item 1); each lane done on its own evidence, with a *not run* allowance in the cut record (G5, G6), and the window's frozen deploy (G7).
- *Corrections:* contracts 1, 2 and 3; IR-7 reads "its first Campaign", since Outcome Evaluation's unit is a campaign's calibration and its increments (its revision 1 §4.1–§4.2).
- *Missing:* contract 7, how the product is started for evaluation; approved by the owner as written, 2026-10-17.
- *Agreed as drafted:* §8.1; contracts 4 and 6; §8.3 items 2, 3 and 5; IR-1 to IR-3, IR-5, IR-8 to IR-10 (IR-10's pair is standalone cycles, so Outcome Evaluation does not run in it); IR-6 once contract 7 exists; G1 to G4; G6 with its phase-2 change.

**Its review of revision 7** (2026-10-17, PR #2401's comment `issuecomment-6244205163`, read at `3755c352`) agrees with §8.2.1, §8.3.1 and the fixture, and found nothing that conflicts with Outcome Evaluation's revision 2 as the Spark lane intends it. Its two changes are applied: X-3 starts a pinned revision in a disposable copy, and `OutcomeEvaluationRef.campaign_id` is nullable. It raised Q40, how secrets reach an evaluation, which the owner ruled the same day as recommended: evaluation-scoped, owner-approved test credentials only (§8.2.1). Its design notes on X-1 to X-3 are for their G4 reviews.

**What the Spark lane changes on its side,** in Outcome Evaluation's revision 2 for the owner's design review: scenarios declare their surfaces, a manifest is optional, and the runner runs outside the squad's containers (its §4.1); phase 1's suite is pinned on the campaign; the evaluation record and its ID; *not applicable* kept apart from `blocked_unverified`; and its *outcome* term renamed before phase 1 ships (the portfolio's Q3), which contract 5's names follow.

# 9. Detailed contracts and implementation appendices

The directional requirements above and the functional requirements below are normative. Tables/examples explicitly labeled illustrative or proposed describe unimplemented additions; Appendix A records inspected implementation facts. Appendix F preserves the pinned source evidence.

| Appendix | Contents |
|---|---|
| A | Verified implementation baseline, execution semantics and problem statements |
| B | Detailed source/workspace design, the Project Record and Development Configuration, and the external repository contract |
| C | Functional requirements FR-01 through FR-21 and non-functional requirements |
| D | Existing CLI/API contracts, proposed additions and compatibility checks |
| E | Implementation plan, primary delivery path, migration, roles and Definition of Done |
| F | Concept/traceability models, related SIPs, remaining decisions and source references |
| G | Document revision history |

# Appendix A — Verified implementation baseline and problem statements

## A.1 Verified implementation baseline

The source baseline above was inspected after a fast-forward pull. Repository-relative evidence is recorded in Appendix F.5.

| Area | Implemented at the inspected revision | Required lifecycle delta |
|---|---|---|
| CLI | Typer groups `projects`, `cycles`, `campaigns`, `artifacts` and `baseline` are registered in the existing `squadops` executable. `projects list/show` have hidden `ls/cat` aliases. | Extend `projects` with lifecycle writes and richer reads. Preserve existing names and aliases. |
| Project API | `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}`, and `GET /api/v1/projects/{project_id}/prd-content`. | Add authenticated lifecycle writes on the existing resource surface; evolve responses compatibly. |
| Registry | `ProjectRegistryPort` exposes `list_projects()` and `get_project()`. Runtime constructs `create_project_registry("config")`. `ConfigProjectRegistry` loads and caches `config/projects.yaml`, which it identifies as the canonical runtime source. | Add durable writes and an explicit provider cutover; do not introduce a registry that existing readers bypass. |
| Project model | `project_id`, `name`, `description`, `created_at`, `tags`, `prd_path`. Existing entries include `hello_squad`, `run_crysis`, `group_run`, `play_game`, and `agent_chess`. | Add lifecycle, ownership, source, quality and accepted-source metadata (the Project Record) and a Development Configuration reference while preserving existing fields/IDs. |
| Cycle creation | `squadops cycles create <project_id> --squad-profile <id>` uses request profiles, optional `--prd`, `--set`, and `--notes`; posts to `/api/v1/projects/{project_id}/cycles`. Creation starts the first run immediately. Server-side `prepare_cycle()` resolves the Project through the existing registry. | Enrich that shared preparation path with Project eligibility and pinned source/workspace context. No alternate launch command or execution path. |
| Cycle persistence | The implemented table is `cycle_registry`, with `project_id TEXT NOT NULL`; Runs have their own records. The inspected migrations do not define the earlier draft's `projects` table or `execution_cycle` table. | Add the Project persistence migration and backfill before enforcing database referential integrity. Preserve `cycle_id` and `run_id`. |
| Artifacts | `ArtifactVaultPort`, runtime-selected filesystem adapter, project/cycle/run-scoped artifact APIs and PRD ingestion already exist. Default artifact root is `data/artifacts`. | Store new lifecycle evidence through existing artifact contracts, adding metadata only where needed. |
| Workspaces | Sandbox `WorkspaceStore` already provisions per-Cycle live trees, hash-pinned revision manifests, HEAD pointers, stale-base protection and leases. The configured default root is `cycle_data/sandbox`. | Add external repository bindings and managed clone/branch management integrated with these sandbox boundaries. |
| Version control | `VersionControlPort` and the Git adapter already provide status, commit and push; `PathValidatedVCS` applies the existing path policy. | Reuse those boundaries and add the missing repository provisioning/import, exact-revision checkout/worktree and expected-base promotion capabilities. |
| Baselines and continuity | `baseline set/get/list` manage per-type artifact pointers. Campaigns already retain accepted tree identities, accepted Cycle IDs, promotion decisions and increment seeding. | Add a Project-level accepted Git revision and explicit mapping to artifact/Campaign/sandbox identities. Preserve existing promotion authority. |
| Campaigns | SIP-0109 CLI/API, policy, control log and launcher already exist. Campaign launches use the shared cycle request builder and preparation path. | Carry Project eligibility/source context through that launcher; preserve Campaign control semantics. |

No `CycleDataStore` exists in `src/` or `adapters/`. SIP-0047 (`sips/implemented/SIP-0047-Cycle-Data-Layout-Project.md`, originally `SIP_CYCLE_DATA_STORE.md`) specified it, a `projects`/`execution_cycle` schema and the `cycle_data/<project_id>/<ECID>/` layout, where ECID is its execution cycle ID. Its store was built in the v0 tree and removed with `_v0_legacy/` (`dd105d1a`, 2026-02-01); no migration creates its tables; and its one remnant is `CycleDataConfig` (`cycle_data.root`, `src/squadops/config/schema.py:723`), which nothing reads. **Retired as a runtime contract (Q30, the owner, 2026-10-17; SIP-0047 §12a):** its implemented status stays as history, its principles of durable Project identity, traceability and durable evidence carry into this SIP (E.2), and neither its store nor its layout is restored. This SIP requires no storage-layout replacement and no second artifact service.

**Reuse is mandatory:** existing CLI commands call the existing API client; existing API readers continue through `ProjectRegistryPort`; standalone and Campaign-launched Cycles use the same Project-aware preparation path. Implementation planning identifies missing capabilities and integration changes, rather than reconsidering whether to reuse the existing CLI.

## A.2 Execution semantics: SIP-0070's Cycle and Pulse

The implemented Cycle/Run orchestration remains the execution authority, and SIP-0070 defines its terms (§4 and §4.1, as built in `src/squadops/execution/pulse_boundary_runner.py`):

- **Cycle:** the governed execution container, with its Runs, gates and correction loop (SIP-0086).
- **Pulse:** a bounded execution interval set by cadence limits (`max_pulse_seconds`, `max_tasks_per_pulse`, overridable in a request profile's `defaults.cadence_policy`). The executor closes it between dispatches and never preempts a task in flight. Guardrail checks run at its boundary, with their bounded repair loop. A Pulse means "safe to continue", and is not an outcome container.
- **Task:** the atomic unit of work.

Recovery is the repair loop at a pulse boundary and the correction loop's decisions, its rewind included (SIP-0086). Projects, Campaigns, repositories, workspaces and reference benchmarks MUST NOT introduce alternative Cycle lifecycle authority, close a pulse or change cadence. This SIP preserves current Cycle and Pulse behavior (IR-10).

**The Pulse IDEAs are history (Q33).** `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md` and `docs/ideas/IDEA_Cycle_and_Pulse_Execution_Model.md` are kept as non-normative design history, each headed as such. Their Pulse is a coordination-topology change that only the orchestrator emits and that marks the legal rewind boundary, and their Surge groups the tasks begun at one Pulse. SIP-0070's Pulse is cadence-bounded instead, and the code holds no Surge. Where they differ, SIP-0070 and the code govern.

## A.3 Why this matters now

Godot and Roblox support is useful only if SquadOps can build genuine applications independently of its test fixtures. A game development SIP, filed separately (Q33; `sips/proposed/SIP-Game-Development-Platform.md`, PR #2405), builds on this one through the capabilities FR-17 lists. Game engines are technical targets of ordinary Projects, with no project registry or orchestration of their own.

This SIP also supports web applications, APIs, utilities, and subsequent supported development domains.

## A.4 Problem statements

**P-01 — Manual enrollment.** The current YAML registry contains predefined Projects and exposes lookup operations. Operators can configure additional entries, but there is no implemented CLI/API lifecycle flow to provision and enroll a new product from intent or an existing repository.

**P-02 — Unclear Project vs execution scope.** A transient Cycle/run can be mistaken for the persistent identity of the application being built.

**P-03 — Insufficient workspace ownership.** Cycle artifact directories and agent scratch directories do not by themselves define who owns an application's persistent source or how a subsequent Cycle resumes from it.

**P-04 — Repository authority and targeting.** The external product repository must remain the source of truth. A Project record needs an explicit upstream, branch/revision and clone/workspace mapping so internal development copies cannot be mistaken for product ownership or silently replace external changes.

**P-05 — Repository-neutral onboarding.** Independent products need safe registration and clone/attach flows that preserve existing layout, history, tooling and contribution rules. A managed clone must not require conversion into a sample app or a prescribed SquadOps source structure.

**P-06 — Project-level source continuity.** Artifact baselines, sandbox revisions and Campaign accepted-tree continuity already exist. The missing contract binds those identities to an external product repository, approved development revision and confirmed upstream integration, including standalone Cycles and work across Campaigns.

**P-07 — Benchmark execution may be a special case.** Reference-app fixtures must not become the only way to launch, test, or score projects.

**P-08 — Integrate existing Campaign authority.** Campaign orchestration is implemented. Project lifecycle must supply eligibility and source context to its launcher without creating a competing launch/promotion path. Existing budget and safety limits remain valid; they are not a predetermined schedule of Cycles.

**P-09 — Missing project governance.** Project state, archival semantics, authorization, allowed workspace roots, permitted repository operations, and multi-project isolation need explicit rules.

**P-10 — Weak promotion/recovery boundaries.** A failed or rewound Cycle must not silently replace accepted Project source or destroy committed work and history.

**P-11 — Extend existing observability.** Project list/show and Campaign/Cycle history views already exist. They need lifecycle, source baseline, workspace readiness and independent-project metadata rather than a separate portfolio registry.

# Appendix B — Detailed Project and external source design

## B.1 Canonical concepts and cardinality

| Concept | Meaning | Persistence / relationship |
|---|---|---|
| **Project** | SquadOps identity and development engagement record for an independently owned product | Persistent metadata; may have many Campaigns and Cycles; references external source |
| **Project Record** | The registry's entry for a Project: identity, lifecycle status, external product authority and delegation, the external source binding, and the development-baseline and integrated-upstream revisions | Authoritative in the selected Project registry (`ProjectRegistryPort`), which stays the source of Project identity and lifecycle (Q32); versioned; extends today's `Project` fields |
| **Project Development Configuration** | Versioned: repository-native commands, working directories and toolchain, the technical target, workspace mode, the repository's instruction sources, and quality-contract and benchmark-profile references | Stored with SquadOps Project metadata; no required file in product source; its revision is pinned when a unit is admitted (§B.5.1) |
| **Product Source** | Externally owned authoritative repository and its product-defined structure | Can be maintained independently of SquadOps; referenced by Project metadata |
| **Managed clone/cache** | SquadOps-controlled copy used to obtain and stage product source | Rebuildable from pinned revisions; does not replace external repository authority |
| **Project Workspace** | Isolated working copy used to build or inspect a Project | Managed; can be recreated from known source revision |
| **Campaign** | Outcome-oriented initiative for a Project | Optional; zero-to-many per Project; adaptive Cycles, not predetermined count |
| **Cycle** | Governed experiment/configuration record operating on exactly one Project | One Project per Cycle; may have multiple Runs and optionally reference one Campaign |
| **Run** | Single execution attempt for a Cycle | Retains existing `run_id`, sequence, status and evidence associations |
| **Reference application** | Project with repeatable evaluation configuration | Metadata/classification; **not** a parallel execution type |
| **Benchmark run** | Evaluation of a Project against an identified fixture/quality contract | A Cycle or linked evaluation result; separate from the Project's core identity |
| **Artifact vault / Cycle evidence** | Implemented artifact storage and evidence references | Project/Cycle/Run association through `ArtifactVaultPort`; preserve IDs and current readers |
| **Artifact baseline** | Existing per-type Project artifact pointer | Managed by `baseline set/get/list`; does not itself update a Git branch |
| **Campaign accepted tree** | Existing accepted content identity and manifest for Campaign increments | Retains Campaign promotion authority; explicitly map to Project source revisions |

**Invariants:**

- Every new governed Cycle MUST continue to resolve exactly one valid `project_id` through the existing registry; add eligibility and source-context checks to that resolution.
- A Project MUST NOT be identified by its current Cycle ID, Campaign ID, directory basename, or Git branch.
- A Project MAY exist without a Campaign.
- A Campaign MUST NOT be treated as a container with a predetermined fixed count of Cycles. Existing policy limits on cost, time or maximum Cycles remain enforceable.
- A Project MAY participate in multiple sequential or overlapping Campaigns subject to execution/branch safety policies.
- Reference-app status MUST NOT change which Cycle orchestration path is used.
- Project source locations are independent of artifact storage and the framework repository by default. Existing sandbox roots are preserved unless explicitly migrated.
- A completed Cycle is **not automatically** an accepted Project baseline; promotion requires its own policy and evidence.
- Product source remains portable and independently usable. SquadOps registration imposes no application layout, build system or required repository files.
- The SquadOps Project owns development metadata and execution records; the external product repository owns authoritative source history and integration rules.
- An approved development candidate and an integrated upstream revision are distinct states; internal acceptance does not imply an external merge or push.

## B.2 Logical architecture

```text
Existing squadops CLI: projects / cycles / campaigns / artifacts / baseline
                              |
                 Existing API client + authentication
                              |
             Existing /api/v1 resource routes, extended
                              |
        Project Lifecycle service + existing ProjectRegistryPort
                              |
  Single selected registry provider: Project Record + Development Configuration
                              |
      External authoritative repo + pinned development/integrated refs
                              |
       Managed clone/worktree + repository-native build/test adapter
                              |
       Existing standalone create or Campaign-governed launcher
                              |
           Shared Project-aware Cycle/Run preparation
                              |
             Existing orchestration, build and QA
                              |
           Existing ArtifactVaultPort + evidence records
                              |
       Reviewed candidate -> authorized external contribution/integration
```

The CLI remains an API client. Filesystem/Git operations run in authorized runtime services or workers, not as a second lifecycle implementation embedded in the command handler.

## B.3 Repository, workspace, and Cycle output are distinct

**Authoritative product repository:** durable, externally owned Git source and assets, remote-hosted or at an external local path. The SquadOps Project records its locator, product-defined refs and relevant subdirectory boundaries. Product maintainers retain control of its layout, build/test tooling, contribution rules and integration policy.

**Managed clone and workspace:** SquadOps may clone the external repository into its own configured cache, then use isolated branches/worktrees at pinned revisions for Cycles and Campaigns. Management controls the checkout location, lease, permissions and evidence capture. It does not grant authority to restructure the product. Disposable working copies can be recreated after all unintegrated work is durably retained; the external repository remains authoritative.

**Cycle evidence:** immutable or versioned artifacts and references associated with Project, Cycle and Run through existing artifact and telemetry services. New Development Configuration revisions, handoffs and source-promotion evidence reuse `ArtifactVaultPort` where appropriate.

Current default layouts (preserved by this SIP):

```text
data/artifacts/
  <project_id>/<cycle_id>/<run_id>/<artifact_id>/
    metadata.json
    <content filename>
  <project_id>/_unattached/<artifact_id>/   # artifacts without Cycle/Run linkage
    metadata.json
    <content filename>
  <project_id>/.baselines.json

cycle_data/sandbox/
  <cycle_id>/
    workspace/
    revisions/<revision_id>.json
    revisions/HEAD
    lease.json
```

Managed product clones and Git-backed workspaces are a **new capability**. Their host-side layout is an internal storage detail, independent of the product repository's internal tree. Illustrative configured locations are:

```text
/var/lib/squadops/repo_cache/<project_id>.git/    # clone/cache of external upstream
/var/lib/squadops/project_workspaces/<project_id>/<cycle_id>/
```

The repository/workspace adapter must state how a checked-out source revision is exposed to the existing sandbox, and how verified changes are captured back into Git. Reuse sandbox path checks, revision preconditions and lease semantics; do not create a second conflicting live tree or reinterpret a sandbox content hash as a Git commit SHA.

The authoritative product source may reside on any approved external Git host or filesystem root. A managed clone is the normal development option for existing products; writing in place in an approved existing checkout is the optional direct attachment (FR-02, E.4.7), within explicit permissions and isolation policy. Never presume the framework repository or sample tree is the product destination.

## B.4 Single project representation; optional benchmark profile

`group_run` and `hello_squad` are already registered Projects. Preserve their IDs, tags and PRD resolution; new independent Projects and future `GameBench-01` use that same registry model.

A benchmark profile attaches:

- immutable fixture/brief version;
- known expected behaviors;
- runner/test fixture identifier;
- expected scoring contract and baseline;
- classification tags such as `reference`, `benchmark`, or `internal`.

These attributes are **optional** and do not determine whether Project creation or Cycle execution is permitted.

Reference source MAY remain at its legacy path until migrated. The registry/source adapter must represent this without special-casing the project's Cycle FSM.

### B.4.1 Where a stack and a benchmark are declared (SIP-0105, SIP-0108)

- **SIP-0105's stack blueprints** describe the stacks SquadOps scaffolds (`fullstack_fastapi_react`, `nextjs_ts`). A greenfield Project built on one names the blueprint in its Development Configuration and does not restate it. An existing product's layout and tooling are its own: its Development Configuration records them, and no blueprint is applied to it.
- **SIP-0108's benchmark registry** holds graded counted rolls, each with its assessment and code lineage. A Project's benchmark profile (above) names what a reference Project is evaluated against. The profile holds no grades and the registry defines no Project. A registry row cites the Project ID, as its cycle does, and once this SIP ships it can cite the Project's source revision and Development Configuration revision as lineage.
- **Outcome Evaluation's held-out scenarios** are a third corpus, in their own store (§8.3). A benchmark profile never holds scenario steps.

## B.5 Project Record and Project Development Configuration

Two records take the place of revision 4's *Project Manifest* (Q32; SIP-0103 owns the word *manifest*):

- the **Project Record**, the registry's entry: identity, lifecycle, external product authority (the owner/maintainer, delegated engineering authority, the versioned acceptance policy and owner decisions) and the external source binding. The existing registry stays the authoritative source of Project identity and lifecycle;
- the **Project Development Configuration**, versioned, which the Record references.

Both are **SquadOps Project metadata**, stored in its registry/artifact storage by default. An in-repository export is optional and explicitly opt-in; enrollment does not create `.squadops/`, rewrite existing metadata or require either record to live in the product tree.

*Project Development Configuration* is the ruled name (Q36). Q32 first named the record the *Project Development Profile*, which shared two words with SIP-0072 §10a's *development profile*: a stack's settings bundle, selected per Cycle by the cycle request's `development_profile` key. The rename keeps *development profile* to that one meaning. The Development Configuration names its stack in a field called `stack`, and none of its keys reuse `development_profile`.

The fields below are proposed schema additions, not a claim that the current CLI accepts them:

```yaml
# The Project Record: the registry's entry
api_version: squadops.project/v1
project:
  id: prj-space-adventure
  name: Space Adventure
  description: Godot exploration game
  lifecycle_status: READY
  record_version: 4
  ownership:
    scope: user
    product_authority: external
    acceptance_policy_ref: project-metadata/owner-approved-policy-v1
  source:
    kind: git
    authority: external
    repo_uri: ssh://git@code.example.org/products/space-adventure.git
    base_ref: refs/heads/main
    contribution_mode: review_request
    repository_root: .
  governance:
    promotion: approval_required
    publishing: approval_required
  classification:
    reference_app: false
  development_configuration_ref: project-metadata/development-configuration@7
```

```yaml
# The Project Development Configuration, versioned
api_version: squadops.project-development-configuration/v1
configuration:
  project_id: prj-space-adventure
  revision: 7
  technical:
    project_type: game
    target: godot
    stack: null                 # a SIP-0105 blueprint, for a greenfield Project built on one
    commands_ref: project-metadata/technical-commands-v1   # install, build, test and start; readiness; entry points (§8.2 contract 7)
  workspace:
    mode: managed_clone
    preserve_repository_layout: true
  instruction_sources:          # found in the repository; the instructions are SIP-0110's records
    - path: CONTRIBUTING.md
      digest: sha256:<content-digest>
      at_commit: <commit>
  quality:
    contract_ref: project-metadata/quality-contract-v1
  benchmark_profile_ref: null
```

**Authority.** After the provider cutover in FR-03, the selected writable registry is authoritative for the Project Record: SquadOps identity, lifecycle status, access/engagement ownership and the configured external source locator. The product repository remains authoritative for source history and integrated refs. The Development Configuration is versioned configuration that the Record references. An exported file of either is a declaration, and never a second registry. Before cutover, YAML remains the implemented lookup authority, and nothing shadows it. Conflicts MUST be rejected or reconciled by an explicit, auditable operation.

`commands_ref` and `contract_ref` in this example resolve through SquadOps Project metadata, not mandatory product files. The actual default branch is discovered/configured per product; `main` is illustrative. Repository commands, working directories and toolchain/environment bindings are recorded in the versioned Development Configuration and reference existing product tooling. Record the repository revision and the instruction-source and build-definition digests that informed the Development Configuration; stale metadata must be revalidated under FR-21. Record inherited build/test evidence separately under FR-20. Engine-specific keys belong under a versioned technical target, not in core Project Lifecycle logic.

### B.5.1 Product authority, repository instructions and SIP-0110's records

The external product owner/maintainer owns product intent, priorities, scope, constraints, quality expectations and final product acceptance. The owner may delegate engineering decisions, candidate acceptance and contribution/integration actions through explicit Project policy. Strategy interprets intent and proposes work; Lead acts within that delegation. A SquadOps role has no implicit authority to replace the owner's roadmap or acceptance criteria. Existing valid delegation remains effective across Cycles; this is not a requirement to request a new approval for every routine authorized action.

**Precedence among the product's authorities** (this SIP's): applicable runtime access restrictions and authorized owner/maintainer decisions first; then the product's applicable contribution/development rules and native build/test definitions; then the Development Configuration, which records how to execute them. The profile is an execution binding, not an independent source of product policy. Owner-approved exceptions are explicit, versioned owner decisions in the Project Record, each referenceable by revision. Runtime access restrictions are enforced at the API, tool and worker boundaries (FR-13), so no instruction text can widen them, and repository instructions cannot grant credentials, widen runtime permissions or override access restrictions. If an unresolved conflict affects execution or contribution, block the affected operation and surface the conflict; do not silently choose a stale profile or infer permission from repository text.

**How instructions reach a task** (Q31). SIP-0110 owns project-instruction records, their versioning, their applicability and their snapshot binding. This SIP owns the external product's authority, the discovery of instructions in its repository, the development configuration and the detection of drift. There is one instruction store, SIP-0110's:

- **Discovery** (this SIP) lists the repository's instruction sources at a pinned commit, each with its path and content digest, in the Development Configuration. The list is configuration, and reaches no task by itself.
- **The record** (SIP-0110 §A.3.2) is a project instruction, confirmed under `memory:instruct` with its applicability (task types, roles, stacks) by a person acting within the owner's recorded delegation. Where it cites a repository source, that source is a required reference. This SIP may propose a record's text and applicability; SIP-0110's confirmation puts it in force.
- **Binding** (SIP-0110 §0.7, §A.3.7) happens when a unit is admitted: a standalone Cycle when it is created, a Campaign when it is admitted. A repository reference resolves to the source at the commit the unit's source context pins at that moment, and the resolved content digest is recorded with the binding. The Development Configuration revision and the source revision are pinned at the same moment, in the unit's source context (FR-04), so a unit's instructions and the commands they describe come from the same commit.
- **Precedence in the prompt** is SIP-0110's slot precedence (§A.3.6): authoritative records outrank task instructions, which outrank project instructions, which outrank lessons. The product's owner decisions and its repository rules are authoritative records there, ordered among themselves by the paragraph above.
- **Drift detection** (this SIP), before dispatch: compare the instruction sources, build/test scripts, dependency/toolchain definitions and contribution policy at the unit's pinned commit with those the Development Configuration and the inherited verification baseline were validated against. Changed relevant inputs invalidate the affected profile and baseline evidence until reconciled and revalidated. Unrelated changes need no blanket rerun, because the quality contract names the affected checks. Refresh the profile within existing authority where the change is routine; surface a policy conflict when a new owner decision is actually required.

**Instruction changes against admitted snapshots:**

| change | a unit admitted afterwards | a running standalone Cycle | a running Campaign, with its later proposals and Cycles |
|---|---|---|---|
| an outside edit to a repository instruction source | binds the new content at its pinned commit; drift detection names the change, and the affected checks are revalidated before they are relied on (FR-21) | keeps what it bound; the change is recorded as a drift finding on the Cycle | keeps what it bound at admission; the drift finding is recorded on the Campaign |
| a project instruction confirmed, revised, narrowed or withdrawn in SIP-0110 | binds the in-force revision | keeps its pinned revision unless re-bound | keeps its pinned revision unless re-bound |
| a new Development Configuration revision | pins the new revision | keeps its pinned revision | keeps the revision it pinned at admission |
| a drift finding that needs an owner decision | the affected operation waits for the decision | the affected operation is held | the affected operation is held and escalated through SIP-0109's queue |

**Changed upstream instructions never modify an admitted snapshot.** A running unit changes what it bound only by SIP-0110's re-binding (§A.3.7): an authorized, recorded intervention, forward when no dispatched task used the old binding and a restart otherwise, with the unit's measurements set apart from the first affected task. Routine upstream edits need no re-confirmation, because a confirmed instruction that cites a repository source binds that source's content afresh at each admission.

**A Campaign's repository references are bound per Cycle, against the Campaign's snapshot (the owner, 2026-10-20: "Approve your recommendations"; SIP-0110 §5ad, which resolves §5z).**
- **The conflict.** The binding bullet above bound a Campaign's repository references when it's admitted, at the commit its source context pins. But a Campaign has no source context of its own. Each of its Cycles pins one when it's prepared (contract 1, FR-04, #2410), after the Campaign's snapshot.
- **Neither way out named before the ruling was taken:**
  - a source pin at the Campaign's admission would bind every Cycle's instructions to the starting commit while each increment's code moves on;
  - plain per-Cycle binding would give up the Campaign's one shared snapshot.
- **The ruling.**
  - The Campaign's snapshot still fixes which instruction revisions are in force, for every Cycle.
  - Each Cycle binds those instructions' `@current` repository references at its own pinned source commit when the Campaign launches it. The binding is recorded with the Cycle, and every dispatch reads it; nothing is bound at dispatch.
  - A reference a Cycle can't bind is handled as at admission: a required one holds the tasks it applies to.
  - A standalone Cycle is unchanged: it pins its source context and its snapshot together.
- **Who builds it.** The launcher's per-Cycle binding and its record are SIP-0110's, on #2179. The repository family's resolver (contract 6, #2411) is unchanged: it binds at whatever commit its `BindingContext` carries, which for a Campaign's Cycle is that Cycle's own.

## B.6 Project lifecycle state model

Proposed project state machine:

```text
REGISTERING -> READY <-> ACTIVE
                  |        |
                  |        +--> ARCHIVED
                  +------------> ARCHIVED
ARCHIVED -> READY
REGISTERING -> FAILED_REGISTRATION
FAILED_REGISTRATION -> REGISTERING (explicit retry)
```

- **REGISTERING:** provisioning/import/validation is underway.
- **READY:** registered, source accessible, no required active operation.
- **ACTIVE:** at least one authorized Cycle or ongoing project activity is underway. This is descriptive Project state and MUST NOT replace Cycle FSM state.
- **ARCHIVED:** no new ordinary Cycles may start; source/history retained and can be restored.
- **FAILED_REGISTRATION:** enrollment failed; diagnostic record retained and any partial resources are reconciled safely.

Use separate provisioning-operation state for granular failures; do not add transient internal step states to the public Project lifecycle. `ACTIVE` should be derived from active work where possible, not maintained as an independent conflicting flag.

**Destructive deletion is not part of the initial SIP.** Archive/restore governs access without erasing source or audit history.

## B.7 External product ownership and repository contract

The authoritative product repository, SquadOps development metadata and managed working copy have separate responsibilities:

| Location | Responsibility | Persistence |
|---|---|---|
| External product repository | Source, assets, product documentation, history, layout, native build/test definitions and contribution rules | Product-owned; usable by other developers and tools without SquadOps |
| SquadOps Project record and evidence storage | Stable Project ID, repository/ref bindings, permissions, technical/quality configuration, Cycle/Campaign history, decisions and source/evidence mappings | Durable engagement metadata; does not require changing product source |
| SquadOps managed clone/worktree | Pinned source for implementation and verification, proposed branches/commits and temporary dependencies/build outputs | Managed development copy; unintegrated work must be retained before cleanup |

For an existing external product, the normal flow is:

```text
External product repository, with its own layout and contribution policy
  -> register SquadOps Project ID + out-of-repository development metadata
  -> fetch/clone approved source and pin a starting revision
  -> isolated Cycle/Campaign work using the product's native commands
  -> reviewed development candidate + durable QA evidence
  -> authorized branch push / review request / patch delivery
  -> external integration confirmed and integrated revision recorded
  -> subsequent work resolves current upstream and retained development baseline
```

No adapter may require the product to use `src/`, `frontend/`, a sample name, framework-specific filenames or a particular runtime. Preserve existing relative paths and configured repository/subdirectory roots, including supported monorepos. The Git repository root, optional product subdirectory and host workspace container are distinct configuration values; a subdirectory binding must not flatten or relocate the repository tree. Repository restructuring is an ordinary product change only when explicitly within the authorized scope; it is not an onboarding step. If the current sandbox or target adapter cannot build the repository as structured, record the capability gap and either adapt the tooling or mark execution blocked/unsupported. Do not reorganize source to hide that limitation. The acceptance proof must include at least one supported pre-existing repository whose layout differs from the samples; this does not assert universal toolchain support.

SquadOps must fetch/check the configured upstream before new work and before integration. Other developers may advance the repository between Cycles. Detect changed refs and apply an explicit update/rebase/merge policy; never reset the external repository to SquadOps's last recorded revision. Upstream refresh must preserve approved but unintegrated work; choose continuation, rebase or merge explicitly. Any changed candidate revision must receive the applicable verification again before acceptance/integration. A durable `development_baseline_revision` may support successive approved iterations before integration, while `integrated_upstream_revision` records what is actually present in the authoritative destination. Both must identify repository/ref and commit; neither is a sandbox hash or a Campaign tree identity. An internal approval or artifact promotion alone cannot advance integrated-upstream status.

Product changes may be delivered as an authorized branch plus review request, a patch, or a permitted direct integration according to product policy. Creating a review request or pushing a branch does not by itself prove integration into the target ref. Record external confirmation and the resulting revision when integration occurs. SquadOps retirement, archival or clone cleanup must leave the external repository and product's native build path usable, while retaining unresolved/unintegrated work and its evidence according to policy.

At the actual upstream write/integration boundary, enforce the expected target-ref/head precondition or the hosting provider's equivalent guarded integration rule; an earlier fetch alone does not prevent a concurrent update. Bind QA evidence to the tested revision/content and retain candidate-to-integrated-commit mappings, including externally rebased, merged or squashed results. A changed revision cannot inherit PASS by implication: perform the required revalidation, or record supported content-equivalence evidence where the quality policy permits reuse.

# Appendix C — Detailed requirements

## FR-01 — Create an independent Project

The system MUST accept a new application/game PRD or design brief and create a unique Project without selecting a sample application. Greenfield creation is required (Q34): it is in this SIP's completion scope (E.4.6), delivered after the existing-product proof.

On `create`, the system MUST:

1. Validate caller authorization and requested project fields.
2. Assign or validate a unique immutable `project_id`.
3. Register the Project, including initial lifecycle status.
4. Provision source at a product-approved external destination, or bind an approved pre-provisioned repository; create an isolated managed development copy.
5. Produce the initial Project Record, Project Development Configuration and intent records in SquadOps Project metadata storage, without requiring files in product source.
6. Validate basic tool/environment capability declarations.
7. Set the Project to `READY`, or record a diagnosable registration failure. Registration readiness is distinct from evidence that the product currently passes its build/tests; execution eligibility must also account for the inherited baseline and acceptance policy in FR-20.

No hidden reference-app lookup or prescribed source layout is permitted as a prerequisite. For a greenfield product, choose its structure from the approved product requirements and selected stack, then retain the same external repository/ownership model used for an existing product. Registration itself does not authorize remote repository creation or publication beyond the caller's configured permissions.

## FR-02 — Import or attach an existing repository

Support an existing project by:

Two levels, one required and one optional:

- **Register and develop through managed clones (required; E.4.1, E.4.2):** register the external authoritative repository, or an approved existing location of it, and clone/fetch it into a SquadOps-managed development cache/workspace, retaining upstream, history and provenance. This is development onboarding; it does not relocate source ownership or replace the authoritative repository. A snapshot/export is a separate explicitly selected mode and must not masquerade as an upstream-linked clone.
- **Write in place in an existing checkout (optional; E.4.7, *direct attachment*):** develop in an approved existing checkout without a managed copy, under its explicit configured write permissions and branch/isolation controls. Until E.4.7 ships, a registration that names an existing checkout develops through a managed clone of it.

Operations MUST validate Git status (where applicable), path safety, permissions, reachability and repository-native tooling. Before feature-source changes, perform read-only discovery and capture the inherited verification baseline at the pinned unmodified source revision; builds may write their normal disposable workspace outputs, but must not alter the baseline source to manufacture a passing result. Discover the existing layout and commands without changing them; record development configuration outside product source by default. Changes to attached/external source MUST respect explicit write permission, contribution policy and branch controls.

Importing MUST NOT silently overwrite a destination or publish to a remote.

## FR-03 — Extend the implemented registry and migrate its authority

Preserve `ProjectRegistryPort.list_projects()` and `get_project()`, the current Project fields (`project_id`, `name`, `description`, `created_at`, `tags`, `prd_path`), and existing API identities. Add lifecycle writes through a typed service/port integrated with those readers.

**Proposed persistence decision:** introduce a transactional writable Project registry adapter in the runtime persistence layer, using the existing migration runner and dependency-injection/factory conventions. A `projects` table is a new migration, not an already deployed table. Extend the Project model and response mapping with:

- project lifecycle status and ownership/access scope;
- external authoritative repository type/locator and product-defined base/integration refs;
- development-baseline and integrated-upstream commit identities, plus contribution mode and pending integration state;
- managed clone/workspace configuration and readiness, kept distinct from authoritative source location;
- the Project Record version and the current Development Configuration revision;
- technical target and quality contract references;
- external owner/maintainer, delegated authority, versioned acceptance policy and owner decisions, registration provenance and timestamps;
- the repository instruction sources the Development Configuration lists, and inherited verification-baseline evidence references (instruction records stay in SIP-0110's store);
- references linking source promotions to relevant Campaign accepted trees, sandbox revisions and verification artifacts.

Migration MUST import the current YAML Projects without changing IDs, names, tags or PRD associations, reconcile all persisted `cycle_registry.project_id` and Campaign project references, and report unknown or conflicting IDs before enforcing foreign keys. Preserve an explicit mapping for SIP-0047's `is_internal` and `updated_at` fields if adopted; neither exists in the inspected Project model. `is_internal` MUST NOT imply benchmark membership; preserve current classification tags.

At cutover, select exactly one authoritative registry provider for every Project reader and writer. The config adapter remains a compatibility/read-only provider or explicit seed/import source. Do not merge cached YAML and writable records at lookup time, silently edit client-local YAML, or let newly created Projects be invisible to running API/Campaign workers. A deployment retaining the config-only provider must explicitly reject unsupported lifecycle writes. Configuration, dependency wiring, cache invalidation/reload behavior and rollback must be specified and tested.

Existing artifact pointers and Campaign acceptance records remain in their owning stores. The new Project registry stores source identity and evidence references rather than duplicating those stores.

## FR-04 — Resolve canonical Project context

Extend the existing Project lookup and shared Cycle preparation path to resolve a typed **Project Context** for Project-aware agents/tools, containing:

- project ID, Project Record version and Development Configuration revision;
- authoritative external repository/ref, pinned development baseline, last confirmed integrated-upstream revision and any pending contribution;
- workspace locator and workspace permission mode;
- the technical target and its capability gaps, from the Development Configuration;
- owner-approved quality/acceptance contract and applicable inherited-baseline policy;
- the unit's SIP-0110 snapshot reference (the project instructions it pinned, with their repository references bound at the pinned commit) and inherited verification evidence;
- relevant Campaign ID (if one exists);
- implemented `cycle_id` and `run_id` once allocated (SIP-0047's execution cycle ID never reached the current tree, so there is no alias to map);
- available prior accepted releases and Cycle evidence indexes.

The Project Context must be derived from authoritative records rather than untrusted free-text hints. It never carries a held-out scenario's steps or checks (§8.3), and it carries no scenario result until Outcome Evaluation's phase 2 is ruled, and after it only into the proposal run (§8.2 contract 5).

## FR-05 — Workspace provision and isolation

The Project Workspace Manager MUST integrate with the existing sandbox `WorkspaceStore` and its revision/lease boundaries. It adds managed development clones, external upstream bindings and Git-backed checkout/contribution management; product ownership stays external. Existing sandbox provision, path safety and stale-base protections must be reused or extended. It MUST:

- operate from configured roots, never hardcoded framework/sample paths;
- allocate separate workspaces for concurrent tasks/Cycles per policy;
- create/checkout the exact pinned source revision requested, preserving repository-relative paths and configured subdirectory roots;
- use repository-native build/test commands from the Development Configuration, with caches and runtime configuration outside committed product source by default;
- prevent path traversal, symlink escapes, and unsafe write targets;
- control read-only vs read-write access;
- provide lock/lease semantics for same-project conflicting writes;
- record workspace ownership, creation, lease, and cleanup;
- allow safe cleanup of disposable workspaces only after outputs are persisted/promoted;
- support project-specific caches without sharing mutable project source across tenants.

A task must never silently modify another project's directory or the framework repo.

## FR-06 — Git change workflow and promotion

A new development Cycle MUST begin from an identified external-repository development baseline (commit SHA or equivalent content revision) and work on an isolated branch/worktree or equivalent. Preserve the product's tree and contribution rules; record both the pinned development revision and the last confirmed integrated-upstream revision.

Reuse the existing `VersionControlPort`, Git adapter and `PathValidatedVCS`/path policy for supported operations. Extend the repository adapter with provisioning/import, checkout/worktree and guarded promotion capabilities; do not implement a second ungoverned Git command path in the CLI.

At Cycle completion:

- source changes MUST be auditable (commit/diff/revision);
- QA evidence and acceptance outcome MUST be linked;
- the Cycle's delivered revision MUST be distinguished from the **Project accepted revision**;
- promotion to the accepted Project baseline MUST follow configurable governance rules;
- if a branch conflicts with an updated baseline, the conflict MUST be surfaced; no silent force push, reset, or destructive overwrite;
- prior accepted revisions and evidence MUST remain retrievable;
- internal candidate approval, external contribution delivery and confirmed upstream integration MUST be recorded distinctly, including the target ref and resulting commit;
- changes made by external contributors MUST be detected and reconciled through an explicit policy before integration; the external ref must never be overwritten merely to match internal Project metadata.

Normal Project iteration MUST NOT publish changes into SquadOps framework `main` unless the Project is itself an authorized framework project.

Keep the existing per-type artifact baseline, existing Campaign accepted tree and proposed Git revision identities explicit. A Project may hold an approved development commit before it is integrated upstream; the confirmed integrated revision is recorded separately. A source promotion records their mapping and evidence where applicable. `baseline set` keeps its artifact-pointer semantics. Campaign promotion does not silently publish Git changes; Git promotion does not rewrite a Campaign control log or bypass its acceptance gate. Concurrent Campaigns promoting to the same Project source must use expected-base checks and an explicit conflict policy.

## FR-07 — Extend existing Cycle association

Each new Cycle MUST continue to reference one existing `project_id`. Preserve the `/api/v1/projects/{project_id}/cycles` resource and registry lookup in `prepare_cycle()`. Add validation of Project state, source/workspace availability and capability profile before executable work is enqueued. Both standalone and Campaign launches use this shared validation; do not validate only the CLI route. Resolve/revalidate development instructions and inherited-baseline evidence before feature-source writes; a baseline setup/verification task may be part of a governed Cycle, but implementation cannot proceed under stale or unknown readiness by implication.

The implemented `cycle_id` and `run_id` remain canonical API/persistence identifiers. The Project ID stays in the URL path for Cycle creation. Preserve existing `ArtifactRef` associations and vault retrieval, including current Project/Cycle/Run-scoped APIs. SIP-0047's `cycle_data/<project_id>/<execution cycle ID>/` layout and its `CycleDataStore` are retired (Q30) and are not restored.

Project source repositories remain separate from artifact storage. Any future path migration must preserve artifact IDs, Run provenance and historical readers.

## FR-08 — Campaign relationship without fixed Cycle counts

Integrate with the implemented SIP-0109 Campaign capability:

- a Campaign MUST reference a single Project;
- a Project MAY have multiple Campaigns over time;
- a Cycle MAY reference a Campaign of its own Project;
- the Campaign MUST express an outcome and evaluation criteria;
- the Campaign MUST be able to create further Cycles as needed until a conclusion is reached;
- the Campaign MUST NOT require a predetermined schedule/count of Cycles; preserve its implemented required policy budgets and maximum-Cycle safety limits.

The Project persists independently when a Campaign completes, pauses, changes objective, or is cancelled.

The existing Campaign launcher assigns `campaign_id`/Cycle kind through the shared preparation path. Preserve its launch intents, idempotency and accepted-tree seeding. This SIP MUST NOT add a generic `cycles create --campaign` shortcut that bypasses that authority.

This SIP adds Project eligibility/source-context integration and a mapping between Campaign accepted trees and Project source revisions. Campaign FSM, budget, launch and promotion governance remain owned by SIP-0109. Archiving must coordinate with active Campaigns and refuse new launches; it must not implicitly abort or erase an active Cycle.

## FR-09 — Cross-Cycle project continuity

A subsequent Cycle MUST be able to resolve, without relying solely on model memory:

1. the authoritative external repository/ref, approved development baseline, confirmed integrated-upstream revision and any pending contribution;
2. the Project Record version and the Development Configuration revision;
3. relevant PRD/design baseline and change requests;
4. owner-approved quality contract, inherited baseline findings and latest candidate/integration verification. Project history keeps references to Outcome Evaluation's evaluation records (§8.2 contract 5); no scenario result reaches a squad role's inputs through the handoff until Outcome Evaluation's phase 2 is ruled, and after it only the proposal run's;
5. the SIP-0110 snapshot each earlier unit pinned, the drift findings since, and owner-approved exceptions;
6. prior release/build artifact indexes;
7. unresolved known defects and decisions;
8. previous Cycle IDs and artifact references.

Carry this forward through durable, versioned **Project Handoff** metadata. Reuse artifact baseline references, existing Campaign accepted-tree/increment seeding and sandbox revision evidence; add the missing Project-level mapping from source revisions to Development Configuration revisions across standalone Cycles and Campaigns. SIP-0110's lessons may enrich context but MUST NOT be the only continuity source; its project instructions are binding by its own rules.

Every new Cycle record MUST explicitly pin its base source revision and target Project before dispatch. The server may resolve the current accepted revision for an existing caller that omits a new source-precondition option; explicit stale preconditions must be rejected. A failed or rewound Cycle MUST NOT change the accepted Project baseline by implication.

## FR-10 — Quality contracts for arbitrary applications

A Project MUST have a product-owner-approved quality contract independent of reference app fixtures. SquadOps may propose checks and acceptance thresholds; final product acceptance stays with the owner or an explicitly delegated authority. Extend the existing contract ingestion/binding, typed checks and verification evidence path; do not introduce a separate QA executor merely because the Project is independent.

Minimum contract shape:

- intended output/capability;
- executable verification (build, smoke, integration, acceptance or game-play tests);
- criteria for quality gate `PASS`, `FAIL`, or `UNVERIFIED`;
- test environment and evidence requirements;
- project-specific acceptance criteria and performance constraints.

For a new web app, this may be the product's own API and end-to-end checks; for a game, the gameplay checks its adapter's SIP defines. Absence of a benchmark-specific fixture MUST NOT prevent valid Project QA or execution.

Capture an inherited baseline before feature-source changes and compare the candidate against it using FR-20. Keep the check result (`PASS`, `FAIL`, `UNVERIFIED`) separate from attribution (`inherited`, `introduced/regressed`, `resolved`, `unverified attribution`). An inherited failure remains a failure; it does not become PASS because the squad did not cause it. Existing defects do not automatically require repair outside the approved feature scope, and unknown checks are never silently waived.

**Scenario evidence is Outcome Evaluation's** (Q35, §8.3). Independent held-out scenarios, quality baselines (Lighthouse, axe, lint) and contribution are measured there, on any registered Project. A Project's quality contract is its owner's acceptance criteria for the product's own checks. This SIP records references to Outcome Evaluation's results and never recomputes them.

Squad execution measurements (duration, interventions, repair rate, cost) stay apart from application quality. SIP-0108's assessment and Outcome Evaluation's intervention ledger hold them.

## FR-11 — Reference applications are Projects

`hello_squad`, `group_run`, and other benchmarks MUST be launchable via the same Project-aware Cycle entry point as newly created Projects.

The reference/benchmark profile MAY add deterministic fixtures, expected outputs, scoring, replay datasets, or synthetic users. It MUST NOT require a distinct orchestrator state machine or a different project-storage model.

Any legacy sample-path or CLI aliases MAY be retained during migration, but MUST resolve to a Project ID before Cycle execution.

## FR-12 — Registry discovery and operator visibility

Extend existing `projects list/show` and Project API responses with status, type/profile, source/workspace metadata (subject to permissions), last accepted source revision, last Cycle, associated Campaigns, known issues and current readiness. Preserve existing fields, the default list response shape, hidden `ls/cat` aliases and machine-readable output compatibility.

Project search/filter SHOULD support active/archived, internal/external, reference/non-reference, target stack and recent activity.

## FR-13 — Project policy and authorization

Project creation, source modification, import/attach, archive/restore, baseline promotion, release and publishing MUST be authorized actions. External owner policy defines product decision rights and any delegation to SquadOps; candidate acceptance and external integration remain distinct. Permissions MUST be checked at API/tool boundaries, not delegated to agent self-reporting.

At minimum, distinguish:
- read/inspect;
- create/import/attach;
- modify/workspace execution;
- accept/promote;
- release/publish;
- archive/restore.

Credential material MUST reside in appropriate secret storage, never in the Project Record, the Development Configuration or Cycle source evidence. Repository access/contribution rights do not transfer product ownership or authorize restructuring. Upstream writes, branch pushes, review requests and direct integration follow the product's configured permissions and governance.

## FR-14 — Eventing and auditability

Every meaningful Project transition MUST emit structured audit/event data with actor, Project ID, operation, relevant source revisions, timestamp, correlation/cycle ID when present, and result.

Events include logical registration/import, validation failure, workspace provision, Cycle linkage, source-promotion request/decision, archive and restore events. Source-promotion events must be distinguishable from existing artifact-baseline and Campaign promotion events.

Naming is illustrative pending alignment with existing SquadOps event conventions. No second message bus or event store is required.

## FR-15 — Failure and recovery semantics

Provisioning failures MUST leave the Project in an explicit recoverable state and avoid leaking orphan workspaces or partial credentials.

Workspace or repository outages MUST distinguish infrastructure unavailability from functional application failure. Failed/replayed Cycles MUST preserve historical artifacts and may create new source branches/workspaces; they MUST NOT erase previous Cycle history.

Promotion and remote-push operations MUST be idempotent or guarded by revision preconditions. Recoveries MUST follow the executor's existing paths: the repair loop at a pulse boundary (SIP-0070) and the correction loop's decisions, its rewind included (SIP-0086). Project Lifecycle never closes a pulse or changes cadence.

## FR-16 — Lifecycle disposal without data loss

Archiving prevents future ordinary Cycle starts but retains external source references, Project Record and Development Configuration revisions, releases, QA artifacts, Cycle history and all unresolved/unintegrated work. Archiving or deleting a managed clone does not delete or archive the external product repository. Restoring runs validation before returning the Project to `READY`. Final deletion, including retention policies and destructive cleanup approvals, is left to a separate explicit policy.

## FR-17 — Capabilities for future target adapters, games among them

Game-specific adapters belong to their own SIPs (Q33, Q34); the Godot/Roblox game development SIP is filed separately (`sips/proposed/SIP-Game-Development-Platform.md`, PR #2405). This SIP provides what any such adapter builds on:

- creation and import of the product through this lifecycle (FR-01, FR-02), as an ordinary Project with no registry or orchestration of its own;
- a technical target recorded in the Development Configuration, with its native commands, toolchain and asset handling, and an explicit capability gap when a target is unsupported;
- the product's files in Project source and its workspaces, never in shared sample-application directories (FR-05);
- a resolved Project Context and an isolated workspace before any adapter runs (FR-04, FR-05);
- the Project's quality contract, so that a target's own checks (gameplay tests, for a game) run through the existing verification path and link to the Project, Cycle and Run (FR-10);
- one Project across later Campaigns and Cycles (FR-08, FR-09);
- execution resources, such as a remote engine worker, treated as resources and never as a Project or an agent.

## FR-18 — Extend the existing CLI and API client

Implement new commands in the existing `squadops.cli.commands.projects` group. Preserve `projects list/show` and hidden `ls/cat` aliases; use `show`, not a new canonical `inspect` spelling. Preserve `cycles create <project_id>` and `cycles list/show`, existing `campaigns` control commands, `artifacts` operations and artifact `baseline` commands.

New commands MUST reuse the shared `get_client`/`APIClient`, existing configuration and token resolution, login flow, `CLIError` exit-code mapping, standard output helpers, global `--format`/`--json`/`--quiet` behavior and paging helpers where relevant. Do not claim unsupported global flags or add a second CLI executable/config/auth stack. All source and lifecycle writes are authorized by the server or designated worker; the CLI must not register a Project by editing its own `config/projects.yaml`.

Mutation commands expose a caller-reusable `--idempotency-key`. Follow the existing Campaign CLI pattern for generated keys and retry disclosure, and include the key/operation correlation in JSON responses. Version-sensitive updates and source promotions require explicit expected-version/base preconditions. Readiness results distinguish completed registration from pending or failed provisioning.

Creating/registering a Project does not start a Cycle or incur execution work by implication. Existing `cycles create` and Campaign `start` retain their execution behavior. Local brief and profile files are read by the CLI and transferred through defined upload/request contracts; a local file path is never treated as readable on the runtime server merely because it appears in JSON.

## FR-19 — Preserve external product independence

Registration MUST support an external repository with no SquadOps metadata files and no onboarding edits to its source tree. The Project Record, the Development Configuration with its build/test bindings, and governance metadata must all be storable under the SquadOps Project. Optional repository-side integration files are an authorized product change, never a prerequisite.

Managed cloning/importing MUST preserve repository history and layout. Use configurable product-defined roots, native commands and toolchains. Persist external-repository/ref bindings and development/integrated revisions, detect contributions made outside SquadOps, and deliver changes under the product's branch/review/integration policy. Support must be declared honestly for the target; a capability limitation must not silently trigger source relocation or restructuring.

The product's native build/test commands MUST remain usable with their documented toolchain without a running SquadOps installation. This is a portability requirement, not a claim that inherited defects have been repaired: recorded baseline failures and gaps remain visible under the owner's acceptance policy. Cleanup and archival retain unintegrated commits/patches/evidence and leave upstream intact. Definition-of-Done checks must demonstrate these properties on an existing external repository with a non-sample layout.

## FR-20 — Capture inherited quality before modifying source

Before feature implementation on an unfamiliar repository or a materially changed baseline, capture the agreed build/test verification against the pinned unmodified source in the managed execution environment. Preserve:

- repository/ref, exact commit and relevant dependency/lockfile state;
- the effective Development Configuration revision, instruction sources and command/working-directory definitions;
- runtime/toolchain/environment identity needed to interpret or reproduce results;
- attempted checks, results, evidence and relevant execution limits;
- pre-existing failures, missing prerequisites and checks that remain UNVERIFIED.

The baseline must represent what was actually observed; do not patch source, suppress checks or relabel failures to make onboarding appear green. Product-owner-approved policy decides whether feature work may proceed with identified inherited failures or environment gaps. Record the allowed scope, remaining obligations and evidence; do not impose a blanket obligation to repair every inherited defect. A Project can be registered while baseline work is pending, but registration alone is not permission to claim successful verification or to ignore readiness constraints.

Evaluate candidate changes against relevant baseline evidence. Persist check results independently of regression attribution and retain ambiguity when evidence cannot distinguish an inherited defect from a new regression. A candidate must meet the approved acceptance policy; unrelated inherited failures remain visible. Changes to source, toolchain, dependencies, commands or relevant instructions require appropriate refresh/revalidation, including after rebase/merge. The quality contract determines the affected verification scope; a prior PASS cannot silently migrate to a different source/environment.

## FR-21 — Respect instruction precedence and revalidate drift

The external owner/maintainer retains product intent and final acceptance authority; SquadOps roles act within explicit delegation. Effective instructions obey Appendix B.5.1: the product's authorities in this SIP's order, recorded and pinned as SIP-0110's project instructions (Q31). Version the Development Configuration and bind it to the source, instruction sources and build definitions it describes. Native repository tooling and maintainer policy cannot be silently replaced by stale external metadata.

Before feature-source changes, inspect/reconcile relevant upstream instruction, build/test, dependency and toolchain changes at the unit's pinned commit (drift detection, B.5.1). Pin the Development Configuration revision in the unit's source context beside its SIP-0110 snapshot, and record both in handoff metadata. Revalidate affected commands and inherited-baseline evidence before relying on them; repeat relevant checks at integration when source/configuration drift requires it. A change found after a unit was admitted is a drift finding on that unit and never modifies what it bound; only SIP-0110's re-binding does. If an owner-policy decision is needed, stop the affected operation and report the conflict through existing governance. Routine profile refresh within delegated authority does not require an extra approval ceremony. Repository content cannot elevate runtime permissions.

## C.1 Non-functional requirements

**Compatibility.** Existing WarmBoot/reference application invocation and recorded history MUST remain accessible through a documented migration/alias mapping. Do not delete, rename, or move legacy data without a validated migration and rollback plan.

**Data integrity.** IDs immutable; preserve existing registry-based Project validation and add Project–Cycle foreign keys only after registry migration/backfill; Development Configuration and source revision pinning explicit; promotion uses compare-and-swap/expected-base checks or equivalent controls.

**Isolation.** Workspaces and artifact paths derive from validated IDs/configuration, with directory/permissions boundaries enforced across projects.

**Idempotency.** Duplicate create/import/provision requests with the same idempotency key MUST not create duplicate Projects or silently overwrite source.

**Recoverability and portability.** SquadOps can reconstruct a development copy from external repository revision, out-of-repository Project metadata, toolchain and dependency configuration; evidence remains independently retrievable. The product remains usable outside SquadOps, with native source layout/build instructions and preserved upstream history.

**Performance.** Registry lookups and workspace provisioning MUST be measured. Configurable operational thresholds SHOULD be defined after baseline measurement instead of inventing universal timings.

**Extensibility.** Project types/targets (web, API, Godot, Roblox, other) are Development Configuration targets and adapters, not core lifecycle special cases.

**Least privilege.** Agents use scoped Project capabilities; creation, promotion, publication and archive/restore policies enforced centrally.

**Observability.** Expose source baseline, last accepted verification, active Cycle status, and provenance of delivered revisions. Project-status UI MUST NOT mask divergent Cycle states.

**Cost awareness.** Attribute model/tool/remote-worker costs and blocked-time metrics to Project/Campaign/Cycle without conflating them.

# Appendix D — Existing CLI/API contracts and proposed extensions

The command names and request shapes below distinguish **implemented behavior at the pinned revision** from **new behavior required by this SIP**. The existing CLI, runtime resource API and service boundaries MUST be extended. The logical names `project.create`/`project.workspace.provision` describe capabilities, not a new RPC API or executable.

## D.1 Preserve the implemented API surface

| Implemented API | Existing caller/meaning | Reconciliation requirement |
|---|---|---|
| `GET /api/v1/projects` | `squadops projects list` | Preserve collection shape; add lifecycle information compatibly. |
| `GET /api/v1/projects/{project_id}` | `squadops projects show <project_id>` | Preserve identity and existing response fields. |
| `GET /api/v1/projects/{project_id}/prd-content` | Project PRD read | Preserve existing PRD resolution or provide explicit artifact-backed compatibility. |
| `POST /api/v1/projects/{project_id}/cycles` | `squadops cycles create <project_id>` | Preserve create-and-start behavior, profiles and request builder; extend shared preflight/context resolution. |
| `GET /api/v1/projects/{project_id}/cycles` and `.../{cycle_id}` | `cycles list/show` | Preserve Project scoping, filters and paging. |
| `POST /api/v1/projects/{project_id}/artifacts/ingest` | `artifacts ingest`; `cycles create --prd <local-file>` auto-ingestion | Reuse brief/contract/evidence ingestion; preserve artifact IDs. |
| `GET/POST /api/v1/projects/{project_id}/baseline/{artifact_type}` and collection GET | `baseline get/set/list` | Keep per-type artifact-pointer semantics and existing promotion/build-strategy eligibility checks. |
| `/api/v1/campaigns` and its control resources | `campaigns create/list/show/start/...` | Preserve Campaign launch authority, budgets, control log and acceptance behavior. |

New lifecycle routes MUST follow `docs/architecture/api-route-lanes.md`: authenticated `/api/v1` resources, existing error helpers/envelope, declared response models/classes, and appropriate 201/202 success statuses. New authorization scopes and audit records must integrate with existing auth/audit infrastructure. Existing Project GETs currently require `CYCLES_READ`; adding lifecycle writes must not weaken that boundary.

## D.2 Proposed lifecycle API additions

These routes are **new**, not claims of current support. The implementation may refine subresource names within the existing API conventions, but must keep the existing read and Cycle contracts.

| Proposed API | Purpose / related CLI extension |
|---|---|
| `POST /api/v1/projects` | Register/provision with `origin.mode: new`, `import` or `attach`; used by `projects create/import/attach`. |
| `PUT /api/v1/projects/{project_id}` | Version-preconditioned Project Record and Development Configuration update; `projects update`. |
| `POST /api/v1/projects/{project_id}/validate` | Validate readiness; `projects validate`. |
| `POST /api/v1/projects/{project_id}/archive` and `/restore` | Govern reversible lifecycle transitions. |
| `GET /api/v1/projects/{project_id}/history` | Project lifecycle/source/evidence history; `projects history`. |
| `/api/v1/projects/{project_id}/workspaces` | Provision/read/release through the authorized repository/workspace service, integrating sandbox revisions. |
| `/api/v1/projects/{project_id}/source-baseline` and its proposal/promotion resources | Read/propose/promote accepted Git source with expected-base and evidence bindings. Distinct from existing artifact `/baseline`. |

Every mutation carries an idempotency key and actor/correlation data. Responses return `project_id`, the Project Record version and Development Configuration revision, operation correlation and explicit readiness/status; secrets are excluded. Long provisioning uses the existing 202 convention with a queryable operation reference; Project `show` exposes readiness.

Illustrative **new** registration request (the source destination/locator must be resolved and authorized before readiness):

```json
{
  "idempotency_key": "create-space-adventure-001",
  "name": "Space Adventure",
  "description": "A 3D exploration game built in Godot",
  "origin": {"mode": "new"},
  "technical": {"project_type": "game", "target": "godot"},
  "source": {"mode": "external_product", "development_copy": "managed_clone"},
  "governance": {"promotion": "approval_required"}
}
```

For `--brief <local-file>`, the command must transfer the file content. A compatible flow reserves a `REGISTERING` Project via this request, uploads the brief through the existing project artifact-ingestion endpoint, then finalizes/validates registration with the immutable artifact reference. Specify these new completion semantics, retry keys, pending-state reconciliation and failure recovery as one logical registration operation. The Project is not `READY` until required intent and provisioning are durable. Do not substitute a client-local path for an uploaded artifact reference. Import/attach repository locators likewise need an explicit server/worker access contract; a CLI-local path does not authorize host access on another machine.

The proposed source schema must distinguish the authoritative external locator/ref from the managed clone/cache location. `origin.mode: import` uses the supplied repository as authoritative and creates a development clone; `origin.mode: attach` leaves source in place. For `origin.mode: new`, resolve a product-approved external source destination before `READY`; never substitute the internal clone cache as the implicit product owner. Record repository-native roots/commands in Project metadata rather than generating a required repository scaffold.

## D.3 Preserve the Cycle request contract and extend source context explicitly

Current standalone Cycle creation is:

```text
POST /api/v1/projects/{project_id}/cycles
```

The current `CycleCreateRequest` requires `squad_profile_id` and accepts `prd_ref`, task-flow/build strategy, applied defaults, execution overrides, expected artifact types, experiment context, request profile and notes. It forbids unknown fields. An illustrative body using **existing** fields is:

```json
{
  "squad_profile_id": "full",
  "prd_ref": "artifact-id-returned-by-existing-ingestion",
  "notes": "Implement collectible keys and exit unlock"
}
```

The CLI builds the complete request from `cycle_request_body()` and request-profile defaults, compares local and server configuration hashes and warns on mismatch. The create request starts execution; hash comparison does not gate dispatch. Keep that builder, PRD auto-ingestion and profile/preflight behavior. Project ID belongs in the URL, not a new duplicate body field.

The current public body does **not** accept top-level `campaign_id`, `objective`, `base_revision` or `quality_contract_ref`. Do not document them as working options or hide source-governance fields in unvalidated `--set` values. This SIP requires an explicit typed extension for source-context version/base preconditions, persisted before dispatch and checked against the selected registry. Resolve the quality contract through the effective Project context and existing contract-binding machinery. Persist the server-resolved base even if a caller requests the current accepted revision implicitly; reject stale explicit preconditions. Update the DTO, request builder, CLI mapping, persistence, config-hash boundary and both standalone/Campaign preparation tests together.

Campaign Cycles retain `campaign_id`/kind assignment through the existing Campaign launcher, not an arbitrary public Cycle-create field. Integrate the Project context in that shared preparation path and map Campaign accepted-tree identity to the pinned source revision.

## D.4 CLI: existing commands to preserve

These spellings are present in the inspected implementation. They are contract examples, not instructions to execute work during SIP review.

```text
squadops projects list
squadops projects show group_run
squadops --json projects show group_run

squadops cycles create group_run --squad-profile full --request-profile default --prd docs/change-request.md
squadops cycles list group_run
squadops cycles show group_run <cycle-id>

squadops artifacts ingest --project group_run --type prd --file docs/change-request.md
squadops baseline list group_run
squadops baseline get group_run prd
squadops baseline set group_run prd <artifact-id>

squadops campaigns create --file campaign.yaml --reason "Develop playable prototype" --idempotency-key campaign-create-001
squadops campaigns start <campaign-id> --reason "Begin approved work" --idempotency-key campaign-start-001
squadops campaigns list --project group_run
squadops campaigns show <campaign-id>
```

`cycles create` requires `--squad-profile`; `--request-profile` defaults to `default`. `--prd` accepts a file or artifact reference; a local file is auto-ingested. Existing `--set key=value` and `--notes` remain supported. Creation starts the first Run immediately. `campaigns create` reads a definition containing `project_id`, objective and required policy; `campaigns start` uses the Campaign-controlled launcher. Existing Project `ls/cat` aliases remain.

`baseline set` retains the existing requirement that the referenced artifact is promoted, and the rejection of artifacts associated with fresh-strategy Cycles. These examples do not grant source-promotion authority or imply that any arbitrary artifact is eligible.

## D.5 CLI: proposed additions to the existing group

The commands below are **new requirements**. Implement them inside the existing plural `projects` group using the shared client and server-side lifecycle service.

```text
squadops projects create --brief docs/space-adventure.md --type game --target godot --idempotency-key project-create-001
squadops projects import --repo <approved-repository-locator> --idempotency-key project-import-001
squadops projects attach --repo <approved-repository-locator> --idempotency-key project-attach-001
squadops projects validate <project-id> --idempotency-key project-validate-001
squadops projects update <project-id> --file project.yaml --expected-version <version> --idempotency-key project-update-001
squadops projects archive <project-id> --idempotency-key project-archive-001
squadops projects restore <project-id> --idempotency-key project-restore-001
squadops projects history <project-id>
```

The existing `projects show` reports the Project Record, its Development Configuration revision, source baseline, operation state and readiness. Final schemas/options for workspace and source-promotion subcommands must be specified before implementation, using the source-baseline distinction above. Any optional convenience aliases are additive; `project`, `inspect`, `cycle start`, `--objective` and `--campaign` do not become replacement spellings for existing contracts.

After registration is `READY`, independent work uses the same existing entry point:

```text
squadops cycles create <project-id> --squad-profile full --request-profile default --prd docs/feature-request.md
```

Source-context options, when added, are explicitly new and must be documented with their typed API/persistence mapping. Project registration itself never launches this command implicitly.

## D.6 CLI/API acceptance checks

- Existing `projects list/show`, `ls/cat`, JSON/quiet modes, Cycle/profile/PRD handling and artifact baseline commands remain compatible.
- New mutation commands call the existing API client and `/api/v1/projects` resources; authorization and source writes occur server-side.
- A create/import/attach retry with the same key returns the same Project/operation; a conflicting payload is refused. JSON output retains the key and readiness needed for a safe retry.
- Independent registration becomes visible to `projects show`, standalone Cycle creation and Campaign workers through one selected registry without process-local YAML shadowing.
- A stale Project Record version or source precondition, archived Project or unsafe repository location fails before work is dispatched; denial does not allocate a running Cycle.
- Both standalone and Campaign-launched Cycles receive the same pinned Project source/quality context while retaining their existing launch authority.
- Tests enter at the CLI/API wiring seams and assert observable Project/source state, request/response compatibility and error behavior; command names alone are not sufficient proof.

# Appendix E — Implementation and acceptance detail

## E.1 Reconciled implementation plan

Appendix A.1 and Appendix F.5 record completed source inspection at the pinned revision. Before coding, compare the implementation branch with that pin and report relevant changes; do not repeat the original assumption that all foundations are unimplemented.

| Workstream | Reuse | Add or change |
|---|---|---|
| Project CLI/API | Existing `projects.py`, shared client/auth/output, current GET routes/mapping | New lifecycle commands, typed requests/responses, scopes, idempotent operations and version preconditions. |
| Registry | `ProjectRegistryPort`, existing Project identity/fields, provider factory/runtime wiring | Writable adapter/service, migration, YAML seed/cutover, all-reader consistency and lifecycle metadata. |
| Cycle integration | Existing plural `cycles create`, the cycle request profile builder, PRD upload, `prepare_cycle()` and current Cycle/Run persistence | Pinned Project source/quality context, eligibility checks and explicit schema/persistence additions. |
| Source/workspaces | Sandbox `WorkspaceStore`, stale-base checks, revisions, leases, path containment and artifact capture; existing `VersionControlPort`/Git adapter | External source locator, managed clone/import/attach/checkout, product-defined contribution policy and guarded candidate/integration tracking. |
| Continuity | Artifact baselines, Campaign accepted trees and increment seeding, existing memory as enrichment | Durable Project handoff and mapping among Git commit, sandbox revision, Campaign tree and artifact evidence. |
| Campaigns | Existing CLI/API, policies, control log, launch intents and promotion gates | Project readiness/archive/source integration at shared launch/preparation seams; no new Campaign FSM. |
| Evidence/QA | `ArtifactVaultPort`, current artifact APIs, contract binding and typed verification | Project lifecycle/handoff evidence types and Development Configuration integration for arbitrary targets. |

Source inspection does not verify the user's running deployment, migrations, credentials or remote workers. The implementation plan must validate those separately when rollout requires them, and resolve remaining adapter/schema choices from Appendix F.4 before adding their surfaces.

## E.2 SIP-0047, retired as a runtime contract (Q30)

SIP-0047 (implemented 2025-11-29) is retired as an active runtime contract by the owner's ruling of 2026-10-17. Its implemented status stays as history, and SIP-0047 §12a records the retirement. Its principles carry forward here: a durable Project identity (FR-03), traceability from Project to Cycle, Run and evidence (FR-07, FR-09, F.2), and evidence kept apart from product source and scratch space (B.3). Its names and layout do not overwrite the implementation facts:

- Current Project lookup is YAML-backed through `ProjectRegistryPort`; writable persistent Projects are new work.
- Current Cycle persistence is `cycle_registry` with `project_id`; preserve its `cycle_id`/Run records, not an assumed `execution_cycle` table.
- Current artifact access is `ArtifactVaultPort` plus its filesystem adapter and Project/Cycle/Run references. Preserve IDs, baseline pointers and historical content retrieval.
- Current sandbox `WorkspaceStore` already supplies live workspaces, revisions and leases. Extend/integrate its boundaries for Git-backed Project source.
- SIP-0047's `CycleDataStore` and its `cycle_data/<project_id>/<execution cycle ID>/` layout are not restored. Evidence stays with `ArtifactVaultPort`, with no second system of record. A later design that needs either is a new SIP, specified against the current stores.

Project repository management remains separate from evidence storage: the external Git repository tracks authoritative product source; the vault and telemetry services retain verification and execution evidence. Source-promotion records connect them.

## E.3 Lifecycle use cases

### UC-A — Existing application (primary acceptance path)

```text
User supplies external product repo, retaining its layout and ownership
  -> register Project ID + out-of-repository development metadata
  -> clone/import for development or attach under approved isolation policy
  -> resolve owner delegation + native instructions; pin the upstream and Development Configuration revisions
  -> run agreed build/tests on unmodified source and record inherited defects/UNVERIFIED checks
  -> Cycle adds a feature in isolated workspace without onboarding restructuring
  -> QA + approved candidate; preserve pending work for subsequent Cycles
  -> authorized branch/review request/patch delivery under product policy
  -> confirm upstream integration and record the actual resulting commit
  -> external developer advances the product before the next Cycle
  -> reconcile source/instruction drift, refresh affected baseline and Development Configuration evidence
  -> deliver a second scoped feature against the same Project and external repository
```

### UC-B — New independent application (greenfield: required, the second proof)

```text
PRD received
  -> Project created/registered
  -> product-approved external Git source initialized with a product-appropriate layout
  -> Project Record, Project Development Configuration and managed development workspace established
  -> existing cycles create / shared preparation pins project_id and accepted source baseline
  -> squad builds and tests
  -> QA evidence stored through the existing artifact/verification contracts
  -> approved source revision promoted
  -> Project remains available for later Cycles
```

### UC-C — Reference benchmark

```text
Existing group_run fixture
  -> resolve reference profile to registered Project
  -> run same Project-targeted Cycle interface
  -> attach benchmark fixture/scorecard
  -> retain historical sample access/behavior
```

### UC-D — Independent game (the game SIP's, built on FR-17)

```text
New Godot or Roblox game intent
  -> create ordinary Project
  -> game-specific technical target resolved from the Development Configuration
  -> engine adapter (the game SIP's) works against isolated Project workspace
  -> (Roblox) remote Studio worker validates as required
  -> game quality evidence linked to Project/Cycle
  -> later Campaigns evolve same Project
```

## E.4 Suggested delivery increments

These are implementation slices, not fixed Campaign stages or Cycle counts.

1. **Existing-product registration and authority:** add the writable registry cutover, its validated provider rollback and the existing-reference regression proof (IR-1), and the minimum existing-CLI enrollment flow; record external repository/ref, owner delegation and out-of-repository metadata while preserving list/show and historical IDs.
2. **Repository-native discovery and inherited baseline:** managed clone/pinned checkout, existing workspace/lease integration, native instruction and Development Configuration resolution, the declaration of how the product is started for evaluation (§8.2 contract 7), agreed baseline build/tests and honest readiness/defect reporting.
3. **First scoped feature through the shared Cycle path:** typed Project context and source preconditions, the standalone and Campaign launch regression proof (IR-2), implementation/verification against inherited evidence, approved candidate and the product's normal contribution/integration process.
4. **Second feature after an outside contribution:** detect source and instruction drift, reconcile with policy, refresh affected baseline checks, and continue through the same Project/Cycle or existing Campaign authority. Demonstrate durable handoff and independent product usability.
5. **Lifecycle completeness (required before the SIP closes; not required in 2.4, the owner's ruling of 2026-10-17):** update history, archive/restore, and concurrency/conflict recovery. Any mutation enabled earlier must already meet its authorization/idempotency requirements.
6. **Greenfield Project creation (required, Q34):** a new product's external repository created at an owner-approved destination with a product-appropriate structure, then developed through the same lifecycle as an existing product. It builds on the proven external-product path, follows the first proof, and is part of what closes this SIP.
7. **Direct checkout attachment (optional):** writing in place in an approved existing checkout under explicit permissions and isolation (FR-02).

**Dependencies:** E.4.1 → E.4.2 → E.4.3 → E.4.4. E.4.6 follows E.4.3, and E.4.5 follows E.4.3. E.4.7 follows E.4.2. Across the lanes: a product with binary files waits on X-2 (§8.2.2); Outcome Evaluation's reading of an external Project waits on E.4.2's start declaration (contract 7) and on X-3. The shared fixture (§8.2.3) comes before all of them.

**2.4 carries E.4.1–E.4.4 and E.4.6:** the brownfield demonstration, with its outside contribution between the two features, and greenfield, shipped (G6). Campaigns keep no predetermined Cycle counts.

Game-specific adapters and other technical targets belong to their own SIPs and build on FR-17. Readiness must explicitly report any operation or target not yet supported.

## E.5 Migration and rollback

- Use the existing migration runner and additive schema changes. Import current YAML entries and reconcile persisted Cycle/Campaign project IDs before enforcing foreign keys; retain unknown IDs for explicit reconciliation rather than deleting history.
- Preserve existing benchmark IDs/tags/PRD resolution. They are already Projects; add lifecycle defaults and source mapping without re-registration under new IDs or forced repository relocation.
- Switch all API, Campaign and worker reads/writes to one selected Project provider. Preserve the config provider as an explicit compatibility/read-only mode or seed source, not a concurrent authority.
- Preserve `projects list/show`, `cycles create`, global output behavior, auth/config, existing artifact-baseline commands and current resource paths; add fields/options compatibly.
- Keep existing vault and sandbox layouts in place. New external source bindings and development clones do not relocate old artifacts, alter artifact IDs or drop Run lineage.
- Add Project eligibility/source context to both standalone and Campaign launch paths; verify existing reference execution and Campaign acceptance behavior for parity.
- Feature-gate lifecycle writes and provider selection where rollout requires it. On rollback, retain new Project Records, source repositories, Development Configuration revisions and evidence. Do not switch to YAML-only reads if that would make post-cutover Projects disappear; provide an explicit read-compatible rollback path.
- Refuse writes when the selected provider cannot support them, and expose provisioning failures/readiness through the existing Project read surface.
- Remove any legacy sample-specific dispatch only after compatibility criteria are satisfied; do not assume such dispatch is the existing canonical Cycle path.

## E.6 Role responsibilities

- **External Product Owner/Maintainer:** owns product intent, roadmap/priorities, scope, constraints, quality expectations and final product acceptance; defines contribution/integration policy and any delegated SquadOps decision rights.
- **Strategy:** interprets owner intent, proposes goals, scoped work and measurable criteria, and recommends subsequent improvements within that mandate.
- **Lead:** validates Project context/delegation, governs execution and coordinates repair; accepts/rejects engineering candidates only within delegated policy. Candidate acceptance does not itself establish external integration or final product acceptance.
- **Dev:** implements authorized changes in the product's native structure, maintains reproducible development bindings, and prepares source contributions under product policy.
- **QA:** records the inherited baseline, verifies candidate changes and reports regressions, inherited defects and UNVERIFIED checks separately; evaluates the owner's acceptance contract without inventing waivers.
- **Data:** preserves source/profile/evidence provenance, drift/defect attribution, cross-Cycle measurements and Project-level continuity/quality trends.

No role is granted authority to bypass the orchestrator's Cycle/Pulse invariants.

## E.7 Detailed Definition of Done

### Registry and identity

- [ ] Implementation deltas are recorded against the pinned source: YAML registry, `cycle_registry`, `ArtifactVaultPort`, sandbox `WorkspaceStore`, Campaign accepted trees and existing CLI contracts.
- [ ] There is exactly one selected authoritative Project registry/identity model; YAML seed/cutover preserves existing IDs and new Projects are visible to all runtime readers.
- [ ] Project ID remains stable across Campaigns/Cycles/workspaces.
- [ ] Independent Projects can be registered without an entry in any sample-app catalog.
- [ ] The Project Record schema and Development Configuration resolution are versioned and validated.

### External product independence

- [ ] An existing external repository registers with a SquadOps Project ID and complete metadata while producing no onboarding source-tree changes or required SquadOps files.
- [ ] Managed clones/worktrees preserve history, relative paths, repository/subdirectory roots and native build/test commands for at least one supported non-sample layout.
- [ ] External source authority is recorded separately from internal clone/cache locations; registration/import does not transfer ownership or redirect upstream authority.
- [ ] Approved development candidates, delivered contributions and confirmed integrated-upstream revisions are distinct and traceable across Cycles/Campaigns.
- [ ] A change made by an external contributor between Cycles is detected and reconciled without resetting upstream to SquadOps metadata.
- [ ] Native build/test capability remains independent of SquadOps, with recorded inherited failures/gaps governed by owner policy; archive/cleanup leaves upstream intact and retains unintegrated work/evidence.
- [ ] Unsupported layout/toolchain requirements surface a capability gap rather than causing automatic source restructuring.
- [ ] External owner product authority and any delegation to Strategy/Lead are explicit; internal candidate acceptance is separate from final product acceptance and external integration.

### Workspaces and source

- [ ] `create` establishes a product-approved external authoritative source destination and a separately managed development copy; it does not mandate the product tree structure.
- [ ] Registration of an existing repository with managed clones preserves repository provenance and safety policies (FR-02). Direct attachment (E.4.7), if shipped, meets the same policies.
- [ ] Separate concurrent Project workspaces cannot modify each other's source.
- [ ] Project source is separate from the artifact vault; existing vault/sandbox paths and historical readers remain compatible.
- [ ] Workspace path-escape, permission and conflicting-write tests pass.
- [ ] Accepted Project Git revision is tracked distinctly from artifact baseline pointers, sandbox revisions, Campaign accepted trees and latest Cycle output; the relevant identities are explicitly mapped.
- [ ] Failed and replayed Cycles cannot silently replace accepted Project source.
- [ ] Project promotion records approved revision and verification evidence.

### Execution and continuity

- [ ] Every new Cycle retains one valid registered Project; both standalone and Campaign launch paths enforce eligibility and pinned source context before dispatch.
- [ ] Project Context resolves from authoritative records for agents/tools.
- [ ] A second Cycle can evolve a first Cycle's accepted application without recreating it.
- [ ] Project handoff includes source baseline, intent, QA status, prior relevant artifacts and unresolved issues.
- [ ] Campaign is optional for a Project or Cycle.
- [ ] Existing Campaign adaptive launch and required budget/maximum-Cycle safeguards remain intact; this SIP introduces no predetermined Cycle schedule.
- [ ] SIP-0070's Cycle and Pulse behavior (cadence-bounded pulses, boundary checks and their repair loop) and the correction loop's decisions, rewind included (SIP-0086), are unchanged; the counted regression pair holds its verdict on a deploy carrying this SIP (IR-10).

### Generalized quality and instruction continuity

- [ ] The agreed build/test baseline is recorded at the pinned unmodified source revision before feature-source changes, including effective commands and Development Configuration, environment, inherited failures and UNVERIFIED checks.
- [ ] Candidate check results are separate from regression attribution; inherited FAIL remains FAIL, unknown attribution remains explicit, and proceeding with inherited defects follows owner-approved policy.
- [ ] Applicable owner/maintainer policy and repository-native tooling constrain the Development Configuration; conflicting or stale metadata cannot silently win.
- [ ] Source, relevant instruction, build/test, dependency or toolchain drift invalidates affected Development Configuration and baseline evidence until reconciled and revalidated.
- [ ] Both standalone and Campaign-launched work receive pinned source, Development Configuration, SIP-0110 snapshot and baseline references through the shared preparation path.
- [ ] Project instructions live only in SIP-0110's store; a repository instruction source reaches a task only as a required reference, bound at admission to the unit's pinned commit.
- [ ] An upstream instruction change after admission leaves the admitted snapshot unchanged and is recorded as a drift finding; only SIP-0110's re-binding changes what the unit bound (IR-3).
- [ ] A non-sample Project can define and execute its owner-approved quality contract.
- [ ] Unknown/unexecuted checks are recorded as UNVERIFIED, not PASS.
- [ ] Scenario evidence (Outcome Evaluation's), inherited/regression quality and squad execution measurements stay distinct; this SIP builds no outcome evaluation, stores Outcome Evaluation's references without recomputing them, and no held-out scenario step reaches its records, workspaces or the product repository (IR-4).

### CLI/API compatibility

- [ ] Existing `projects list/show` and hidden `ls/cat` aliases, JSON/quiet modes and Project response fields remain compatible.
- [ ] Existing `cycles create <project_id> --squad-profile ...` retains request-profile resolution, PRD auto-ingestion, config hashing and immediate first-Run execution.
- [ ] New `projects` commands reuse shared client/config/auth/error/output/paging helpers; source and registry writes execute in the authorized runtime service/worker.
- [ ] New writes enforce scopes, idempotency and version/base preconditions; retry keys and readiness are available in machine-readable output.
- [ ] Existing artifact `baseline set/get/list` semantics and Campaign launcher/control/promotion authority are unchanged; neither implies integration into the external target ref.
- [ ] Source-context additions have explicit DTO/builder/persistence/CLI mappings and tests through both standalone and Campaign preparation.
- [ ] No replacement singular `project`/`cycle start` CLI, second auth/config stack, parallel registry or mandatory artifact-layout rewrite is introduced.

### Compatibility and proof

- [ ] `group_run` can run through the Project-aware Cycle path with prior benchmark semantics preserved.
- [ ] `hello_squad` and WarmBoot continue working or have validated compatibility mappings.
- [ ] Prior Project/Cycle/Run artifacts remain readable through their existing IDs.
- [ ] Primary proof: an unfamiliar existing external repository with a supported non-sample layout registers without onboarding source edits and receives a pinned inherited build/test baseline.
- [ ] A first scoped feature completes through the existing Cycle path and the product's normal contribution/integration policy, with QA and candidate/integrated revision evidence.
- [ ] An outside developer advances the repository between Cycles; the squad detects and reconciles relevant source/instruction drift before delivering a second feature through the same Project.
- [ ] The primary proof records any inherited failures and UNVERIFIED checks truthfully; it does not rely on an artificially pristine fixture or claim inherited defects were introduced by the squad.
- [ ] The external repository remains usable with its native tooling after the SquadOps engagement is archived; pending work/handoff evidence is preserved.
- [ ] Greenfield proof (required, after the primary proof, shipped in 2.4; Q34, G6): a new product is created at an owner-approved external destination and evolved through the same lifecycle. Game targets are proved by their own SIP.
- [ ] Archive/restore is reversible without data loss.
- [ ] API/CLI authorizations, idempotency, failure and recovery tests pass.

### Integration with Outcome Evaluation (2.4)

- [x] The Spark lane's compatibility review of §8.2 is recorded in §8.6 (G3).
- [ ] Every PR that changed a shared contract named it, carried the other lane's review and added its wiring test (G4).
- [ ] IR-1 to IR-10 pass on a deploy carrying both lanes, or report *not run* with the missing prerequisite named (G5, G6).
- [ ] Starting an external product for evaluation goes through the Development Configuration's commands (§8.2 contract 7).
- [ ] The shared fixture's contract tests pass on both lanes' seams (§8.2.3), and X-1 to X-3 are shipped or their capability gaps reported (§8.2.2).

**Primary end-to-end success demonstration:** A product maintainer supplies an unfamiliar existing external repository and a scoped feature request. SquadOps registers it without source-tree changes, resolves the owner's delegation and repository-native instructions, pins an unmodified build/test baseline, and delivers a verified feature through the product's normal contribution process. Another developer then advances the source or development instructions. A later Cycle detects/reconciles that drift, refreshes affected Development Configuration and baseline evidence and delivers a second feature through the same SquadOps Project. Candidate acceptance, inherited defects, regression findings and confirmed upstream integration remain distinct. Product source/builds remain independently usable and `group_run` compatibility is preserved. Greenfield product creation is the second required proof, after this one.

# Appendix F — Supporting models and pinned source evidence

## F.1 Concept boundaries

```text
Project: Space Adventure                     [persistent product]
  SquadOps metadata + external repo/ref + development/integrated revisions
  |
  +-- Campaign: Playable prototype           [outcome]
  |      +-- Cycle cyc_001                   [governed configuration + Runs]
  |      +-- Cycle cyc_002                   [optional; adaptive]
  |
  +-- Campaign: Enemy AI                     [new outcome]
         +-- Cycle cyc_005                   [governed configuration + Runs]

Reference Project: group_run                  [same Project model]
  +-- Benchmark profile / fixture version
  +-- Cycle cyc_010
```

A Project may be developed through a stand-alone Cycle without a Campaign. A benchmark is an evaluation overlay rather than a distinct application lifecycle.

## F.2 Traceability example

```text
Project ID: prj-space-adventure
  Project Record: version 4
  Development Configuration: revision 7
  External Repository: <product-owned-repository-locator>
  Target Ref: <product-defined-integration-ref>
  Owner Delegation/Acceptance Policy: <versioned-policy-ref>
  Instruction Sources: <paths-and-digests-at-the-pinned-commit>
  Inherited Verification: <baseline-evidence-artifact-id>
  Development Baseline: abc123
  Confirmed Integrated Revision: abc123
  Campaign: campaign-enemy-ai [optional]
    Cycle: cyc_example0042
      Base Revision: abc123
      SIP-0110 Snapshot: <snapshot-id> [project instructions, references bound at abc123]
      Delivered Revision: def456
      Run: run_example0001
      QA: <candidate-verification-artifact-id>
      Regression Attribution: <baseline-comparison-evidence-ref>
      Tested Configuration: <pinned-source-configuration-environment-binding>
      Workspace Revision: <sandbox-content-hash>
      Campaign Accepted Tree: <accepted-tree-hash> [if applicable]
      Outcome Evaluation: <result-reference> [goals and results only]
      Logs: <existing-telemetry-correlation>
      Decision: accept candidate def456
      Contribution: <external-branch/review-request/patch-reference>
      Integration: confirmed <external-integration-commit> [or explicitly pending]
  Current Development Baseline: def456
  Confirmed Integrated Revision: <verified-upstream-commit> [unchanged while pending]
```

## F.3 Cross-SIP dependencies

| Existing or related design | Relationship |
|---|---|
| SIP-0064 / SIP-0065 / SIP-0074 | **Implemented foundation**: Project registry/CLI/API, project-targeted Cycle execution, PRD ingestion and artifact baselines; extend existing contracts. |
| SIP-0102 | **Accepted, shipped in parts** (steps 1, 2 and 4 in v1.4.0): Cycle workspace revision, path and lease boundaries; integrate external product source through managed Git clones. A shared contract with the Spark lane (§8.2). |
| SIP-0109 | **Accepted, shipped in parts** (from v2.0.0): control log, launch authority, accepted-tree continuity and promotion; preserve and map to Project source. |
| SIP-0047 (`sips/implemented/SIP-0047-Cycle-Data-Layout-Project.md`, originally `SIP_CYCLE_DATA_STORE.md`) | **Implemented 2025-11-29; retired as a runtime contract** (Q30, its §12a). Its principles of identity, traceability and durable evidence carry forward (E.2); its store and layout are not restored. |
| SIP-0070 | **Implemented**: the Cycle and the cadence-bounded Pulse this SIP keeps (A.2). |
| SIP-0072 | **Implemented**: its §10a *development profile*, a stack's settings bundle, keeps that one meaning (Q36, B.5). |
| SIP-0103 | **Implemented**: owns the word *manifest*; this SIP's records are the Project Record and the Project Development Configuration (Q32, Q36). |
| SIP-0105 / SIP-0108 | Stack blueprints and the benchmark registry; boundaries in B.4.1. |
| SIP-0110 | **Accepted**: owns project-instruction records, their versioning, applicability and snapshot binding (Q31; its §5k). |
| Outcome Evaluation (proposed, PR #1963) | The Spark lane's 2.4 feature: independent held-out scenarios, quality baselines and contribution (its revision 2, PR #2406); seven shared contracts (§8), reviewed by the Spark lane (§8.6). |
| `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md` | **Non-normative history** (Q33), headed as such. Where its Pulse differs from SIP-0070's cadence-based Pulse, SIP-0070 governs. The `CYCLE_PROTOCOL.md` it cites is not in the repository. |
| `docs/ideas/IDEA_Cycle_and_Pulse_Execution_Model.md` | **Non-normative history** (Q33), headed as such. It reads as the earlier of the two: its Pulse groups work, the reading the IDEA above corrects. Its task flow policies were built as `FlowMode`. |
| `docs/ideas/Git workflow.txt` | Git traceability and stable `main`; extend for Project-owned repositories without assuming framework-specific WarmBoot branch conventions apply to all products. |
| `docs/ideas/Doc traceability.txt` (its Process ID proposal) | Reuse traceability for product features and tests; a Project ID is not a Process ID. |
| Game Development Platform (proposed, `sips/proposed/SIP-Game-Development-Platform.md`, PR #2405) | **Downstream consumer**: builds on FR-17; engine adapters operate on independent Project workspaces, not sample-app locations. |
| Existing Campaign implementation | Optional for standalone Project work; reuse current policy, launcher, accepted-tree records and shared Cycle preparation. |

## F.4 Remaining design decisions and validation

Classes: **A** resolved before parallel development (its minimum decision stated here); **B** the
MacBook lane's implementation; **C** the Spark lane's; **D** settled at joint integration; **E** deferred.

| item | class | where it is settled |
|---|---|---|
| The transactional Project schema, write service, provider configuration and YAML seed/cutover/rollback; read consistency after cutover | B | E.4.1. Fixed now: before cutover YAML is the only authority, after it the writable registry is, and every reader sees a newly registered Project at once (contract 1, IR-8) |
| How a Git checkout and verified source capture meet the sandbox live tree, revisions, leases and binary files | **A** | §8.2.2: seeding and capture through `WorkspaceStore`; X-1, X-2 and X-3 named as cross-lane tasks |
| Starting a product for evaluation | **A** | §8.2 contract 7 and its schema (§8.2.1) |
| Typed source-context and precondition fields, their persistence and config-hash scope, in `cycle_request_body()` and Campaign launch requests | B | E.4.3, under contract 2's rule: each lane adds its own typed fields, and Outcome Evaluation adds none at `prepare_cycle()` (§8.6) |
| Development Configuration revision binding | B | E.4.2–E.4.3. Fixed now: the revision is pinned in the unit's source context before dispatch, and a newer revision never applies to a unit already pinned (B.5.1, contract 7) |
| Source-baseline read/propose/promote DTOs and subcommands; the Git mappings to artifact baselines, accepted trees and sandbox revisions | B | E.4.3, with contracts 3 and 4's no-substitution rule (§8.2.1) |
| Campaign promotion against Project source promotion, and overlapping Campaigns | B | E.4.4, reviewed against SIP-0109. Fixed now (FR-06): Campaign promotion never publishes Git changes by itself, Git promotion never rewrites a Campaign's control log or bypasses its acceptance gate, and concurrent Campaigns promote with expected-base checks |
| Safe default permissions and runtime path resolution for a registration locator | B | E.4.1; for writing in place, with E.4.7 |
| Registration reservation, brief upload, finalization and recovery | B | E.4.1 |
| Archive handling, restoration evidence and project-level quality history | B | E.4.5, before the SIP closes |
| Inherited-baseline and candidate-comparison records | B | E.4.2, in §8.3.1's vocabulary |
| Relevant-drift detection and affected-operation conflict handling | B | E.4.4, through the existing governance and event paths |
| The repository reference with SIP-0110 (contract 6) | D | after #2179, as a numbered amendment to SIP-0110 in the PR that builds it |
| Confirming repository-derived project instructions under the owner's delegation | E | until SIP-0110 has a project membership model, admins confirm them (its Q27) |
| The Project Record's owner-decision entries | B | E.4.1 |
| A unit's in-scope change to build or test definitions reaching later Cycles | B | E.4.4, within B.5.1's admission rule |
| Binary files and a product's declared commands inside the sandbox | C | X-2 and X-3 (§8.2.2), with the MacBook lane's review |
| Outcome Evaluation's record, store and runner placement | C | its own design review (the 2.4 plan's D2); this SIP fixes only the reference (contract 5) |
| New target-specific tooling and asset requirements | E | the target SIPs (FR-17; the game SIP, #2405) |

**Scope note:** SIP-0047 (originally `SIP_CYCLE_DATA_STORE.md`, 2025-11-26) was implemented in the v0 tree and is retired as a runtime contract (Q30). Revision 2 reconciled the draft with freshly pulled source; Revision 3 clarified external product ownership. Revision 4 retains that evidence and adds owner authority, inherited quality baselines, instruction precedence/drift and an existing-product-first acceptance path. Revision 5 reconciles the owner's design review of 2026-10-17 (Q30–Q36); revision 6 the Spark lane's review; revision 7 the tightening review. Proposed lifecycle writes and new development contracts are not claimed as implemented. The pinned source inspection is not a fresh deployment verification.

## F.5 Pinned implementation evidence

All paths below are relative to `backspring-labs/squad-ops` at commit `7aecfa0b3ff6576f115eba10c2ee3465774e997d`. Line references are for that revision. They identify source contracts, not results from exercising a running service.

| Evidence | Source at the inspected revision |
|---|---|
| Existing command groups/global output flags | `src/squadops/cli/main.py:61-108` |
| Existing Project commands and aliases | `src/squadops/cli/commands/projects.py:13-66` |
| Shared CLI client/config/error handling | `src/squadops/cli/client.py:28-223`; `src/squadops/cli/config.py` |
| Cycle command/request builder/PRD handling | `src/squadops/cli/commands/cycles.py:33-155`; `src/squadops/contracts/cycle_request_profiles/__init__.py:96-130` |
| Public Cycle DTO forbids extra fields | `src/squadops/api/cycle_schemas.py:41-57` |
| Project routes and auth scopes | `src/squadops/api/routes/cycles/projects.py:18-65` |
| Current Project model | `src/squadops/cycles/models.py:292-301` |
| Cycle/Run distinction and identities | `src/squadops/cycles/models.py:370-455` |
| Registry lookup port and cached YAML provider | `src/squadops/ports/cycles/project_registry.py:10-23`; `adapters/cycles/config_project_registry.py:1-65` |
| Provider factory/runtime selection and artifact-vault wiring | `adapters/cycles/factory.py:32-39`; `src/squadops/api/runtime/main.py:338-374` |
| Existing registered Project IDs/tags/PRDs | `config/projects.yaml` |
| Existing Cycle schema | `infra/migrations/001_cycle_registry.sql:6-30` |
| Shared Cycle preparation/registry lookup | `src/squadops/api/routes/cycles/cycles.py:389-461` |
| Artifact storage and per-type baseline contract | `src/squadops/ports/cycles/artifact_vault.py:10-72`; `adapters/cycles/filesystem_artifact_vault.py:1-38,99-105,212-243` |
| Existing artifact-baseline CLI | `src/squadops/cli/commands/artifacts.py:205-286` |
| Existing sandbox workspace/revision/lease behavior | `src/squadops/sandbox/workspace.py:1-18,99-277`; `src/squadops/config/schema.py:373` |
| Existing version-control port and path-validation wrapper | `src/squadops/ports/tools/vcs.py:13-76`; `adapters/tools/git.py:148-185` |
| Campaign CLI/control API and launch request construction | `src/squadops/cli/commands/campaigns.py`; `src/squadops/api/routes/campaigns/campaigns.py`; `src/squadops/campaigns/launch_requests.py:21-90` |
| Campaign accepted-tree continuity and promotion | `infra/migrations/1630_campaign_accepted_tree.sql`; `src/squadops/campaigns/increment_tree.py:42-88`; `src/squadops/campaigns/progress.py:597-634` |
| API lanes, responses, errors and paging standard | `docs/architecture/api-route-lanes.md` |
| SIP-0047's store, removed with the v0 tree, and its unread configuration remnant (revision 5, at `c294ec79`) | `dd105d1a` (2026-02-01); `src/squadops/config/schema.py:723-726` |
| SIP-0070's Pulse as built (revision 5) | `sips/implemented/SIP-0070-Pulse-Checks-and-Verification.md` §4, §4.1; `src/squadops/execution/pulse_boundary_runner.py` |
| SIP-0072's *development profile* and its preparation check (revision 5) | `sips/implemented/SIP-0072-Stack-Aware-Development-Capabilities.md` §10a; `src/squadops/stacks/development_profiles.py`; `src/squadops/api/routes/cycles/cycles.py:182-186` |
| SIP-0110's instruction records, snapshot and re-binding (revision 5) | `sips/accepted/SIP-0110-Cross-Cycle-Memory.md` §0.7, §A.3.2, §A.3.6–§A.3.8; #2179 |
| Outcome Evaluation's scenarios, independence and results (revision 5) | `sips/proposed/SIP-Outcome-Evaluation.md` §4.1–§4.4, §4.7, §7 |

# Appendix G — Revision history

| Document revision | Date | Change |
|---|---|---|
| Original draft | 2026-10-16 | Independent Project identity, workspaces, governance and cross-Cycle lifecycle proposal based on supplied design sources. |
| 2 | 2026-10-17 | Reconciles against freshly pulled `main`: requires existing CLI/API reuse; separates existing vs new operations; specifies YAML-to-writable registry cutover; preserves ArtifactVault, sandbox and Campaign authority; distinguishes source/artifact/tree baselines; updates delivery and acceptance criteria. |
| 3 | 2026-10-17 | Clarifies SquadOps as a development team for independently owned products: external authoritative source, out-of-repository Project metadata, managed clones/worktrees, preserved repository-native layout/tooling, external-contribution reconciliation and separate candidate/integrated revision tracking. |
| 4 | 2026-10-17 | Keeps external owner authority explicit; adds inherited build/test baselines and separate regression attribution; defines instruction precedence/profile drift; makes enhancement of an existing external product across outside contributions the primary proof; separates the directional core from detailed implementation appendices. |
| 5 | 2026-10-17 | Reconciles the owner's design review (PR #2401). Q30: SIP-0047 retired as a runtime contract, its principles kept (A.1, E.2). Q31: instruction records, versioning, applicability and snapshot binding are SIP-0110's; this SIP discovers repository instructions, holds development configuration and detects drift, and an admitted snapshot changes only by re-binding (B.5.1, FR-21). Q32: the Project Record and Project Development Configuration replace the Project Manifest (B.5). Q33: the Pulse IDEAs non-normative, SIP-0070's Pulse kept (A.2), FR-17 restated as capabilities for future adapters. Q34: greenfield creation required (E.4.6). Q35: the 2.4 parallel development agreement (§8). Adds the boundaries with SIP-0105 and SIP-0108 (B.4.1) and with Outcome Evaluation (§8.3); renames *check outcome* to *check result*. Q36, ruled the same day: the second record named the *Project Development Configuration*, and its keys renamed to match (B.5). The Pulse IDEAs committed under `docs/ideas/` with non-normative headers; the game SIP filed (PR #2405). |
| 6 | 2026-10-17 | Applies the Spark lane's compatibility review of §8 (§8.6, PR #2401's comment `issuecomment-6242996612`, read at `b4bbeb56`): outcome results kept out of squad roles' inputs before Outcome Evaluation's phase 2 (contract 5, FR-04, FR-09); no scenario against a live tree (contract 3); squad task inputs and containers in the independence list and IR-4; each lane done on its own evidence (G5, G6) and the window's frozen deploy (G7); contracts 1, 2 and 3 and IR-7 corrected; contract 7 added, how a product is started for evaluation, approved by the owner as written, 2026-10-17. The owner ruled the same day that the 2.4 cut requires greenfield (E.4.6) shipped (G6), approved G4–G7 as written, and kept the author as Framework Committee. |
| 7 | 2026-10-17 | The tightening review: each contract's availability, absent or stale behavior, versioning and minimum test, with schemas for contracts 1, 5 and 7 (§8.2.1); the sandbox boundary and the cross-lane tasks X-1 to X-3 (§8.1, §8.2.2); the shared fixture (§8.2.3); status vocabularies (§8.3.1); evidence tiers and the *not run* record (§8.5, the owner's clarification); the 2.4 plan cross-reference; FR-02's required and optional levels; E.4's dependencies, rollback moved into E.4.1, and E.4.5 required before close but not in 2.4 (the owner's ruling); F.4 classified. Then the Spark lane's review of revision 7: X-3 runs in a disposable copy, `campaign_id` nullable, and Q40 opened for the owner (how secrets reach an evaluation). |
| 8 | 2026-10-17 | Aligned with Outcome Evaluation's revision 2 (PR #2406) and the adopted 2.4 plan: its renamed terms (*scenario evidence*, *scenario result*, *contribution*, the *scenario measure*); contract 2's phase-1 and phase-2 fields as its §4.7 states them; contract 5 renamed *evaluation references*; Q40 named as its A4; the plan's D12 rulings on X-1 to X-3 and the shared fixture. No boundary changes. Q40 ruled the same day: evaluation-scoped, owner-approved test credentials only (§8.2.1). |
| — | 2026-10-17 | **Accepted by the owner as SIP-0112** (PR #2401), titled *Project Lifecycle Management*. The shared fixture (#2407) and E.4.1–E.4.4 and E.4.6 (#2408–#2412) placed in 2.4.0, labelled `sip:0112`; E.4.5 and E.4.7 unplaced, deliberately. |

# Appendix H — Post-acceptance amendments

## H.1 A greenfield Project is registered against an empty repository its owner made, and initialized from an approved manifest (2026-10-20; E.4.6, #2412)

**What changed.** FR-01 step 4 allowed either provisioning source at an approved destination or binding a pre-provisioned repository. §D.2 and §D.5 proposed `projects create --brief` with `origin.mode: new`. The built path is narrower:
1. **The owner makes the repository and leaves it empty.** SquadOps binds it and never creates a repository.
2. **It's registered as any external product is,** with `projects import` (`POST /api/v1/projects`), against that repository and branch.
3. **`projects initialize <project> --manifest <file> [--token-from-gh]`** (`POST /api/v1/projects/{id}/initializations`) makes the branch's first commit:
   - the SIP-0105 blueprint's layout, rendered from the approved interface manifest exactly as the scaffold renders it for a sample application's run (`scaffold.expand`), and nothing else;
   - pushed with the owner's token for that one act, never forced, and refused when the branch already has a commit;
   - recorded once per Project (`project_initializations`, migration 1807), with the manifest as submitted.

   The commit has no parent and is dated at the registration, so a retry after a push that landed makes the same commit and is recorded, not refused.
4. **From there, the lifecycle is an existing product's:** `validate`, `configure`, `baseline --capture`, then Cycles and contributions by review request. The Development Configuration names the blueprint it was initialized on (§B.4.1); `configure` refuses any other, and refuses a `stack` that isn't a blueprint.

**Not built in 2.4:** `projects create --brief` and `origin.mode: new`. A brief's role is taken by the approved interface manifest, which is the input the blueprint's layout is rendered from. Authoring that manifest from a brief is framing's work (SIP-0103), and a framing Cycle is prepared only for a READY Project (contract 1). A greenfield Project isn't READY until it's initialized and validated.

**The evidence:**
- FR-01 says registration "does not authorize remote repository creation or publication beyond the caller's configured permissions".
- The scaffold renders from a manifest, not from a brief (`src/squadops/stacks/scaffold.py`, `expand`).
- `tests/unit/projects/test_initialization.py` runs the path through the real managed clone into an empty repository, then on through validation and configuration.

**Who ruled:**
- The owner chose the destination on 2026-10-20: an empty private repository in backspring-labs, made with the owner's GitHub access (`backspring-labs/shelfnote`, recorded on #2412).
- The owner chose the product the same day: a small FastAPI and React application on `fullstack_fastapi_react`.
- The API and CLI shape is the MacBook lane's, under the owner's delegation of 2026-10-18.

## H.2 A sync names what SquadOps's own contributions account for apart from outside change, and its drift holds new Cycles until reconciled (2026-10-21; E.4.4, #2606, #2608)

**What changed.** FR-21 says drift "invalidates affected Development Configuration and baseline evidence until reconciled and revalidated". The brownfield demonstration's stages 4 and 5 showed two ways the built sync fell short of that:
1. **Who changed what.** A sync compared the baseline's tree with upstream's before reading contributions, so a merged contribution's own files read as outside source drift (#2606). The drift document is now `source-drift/v2`:
   - `changed` holds what changed outside SquadOps;
   - `integrated` lists each integrated contribution with the paths it accounts for. A path counts as the contribution's when it changed the path and upstream's content is still what it wrote. A path an outside developer changed again since is outside drift.
   - `relevant` reads both, since a contribution that changed an instruction source invalidates the configuration as an outside edit does.
2. **What holds a Cycle.** Nothing on the Cycle path read a recorded sync, so a Cycle at a baseline a sync had already found upstream past was accepted (#2608), though the drift module's own docstring said `prepare_cycle` refuses. Now, while the Project's latest sync read upstream past its current baseline with `relevant` drift, `prepare_cycle` refuses (409 `STALE_SOURCE_PRECONDITION`, naming the upstream commit and the categories), on the standalone and the Campaign path alike (IR-2's shared path).
   - Once `validate` advances the baseline, that sync describes a replaced baseline and holds nothing. The configuration and the inherited baseline are then each required at the new commit on their own, as before.

**Where it narrows FR-21:** **source drift alone holds nothing.** A Cycle pinned at the older commit develops the tree its evidence describes, and its contribution is offered on that commit, through the product's own process. Only the categories that invalidate evidence (`relevant`) hold Cycles.

**The evidence:**
- The Spark lane's stage 4 sync of `prj-z-continuum` (`demo-a-sync-1`, #2410) listed z_continuum#1's two files under `source`, beside the outside commit's.
- Its stage 5 probe created `cyc_001b267cac63` at `43369054` after that sync, and it was accepted.
- **The wiring tests:**
  - `tests/unit/projects/test_sync.py` replays stage 4 through the real managed clone, for a merge commit and a squash merge, plus a path changed again outside;
  - `tests/unit/shared_contract/test_contract1_source_context.py` enters at the create route and at the Campaign launcher's `prepare_cycle`.

**Who ruled:** the MacBook lane, under the owner's delegation of 2026-10-18. The gate is the stated design of #2565's drift module. The narrowing to `relevant` drift follows that module's own definition of what invalidates evidence.

## H.3 IR-3 restated under SIP-0110 §5ad and H.2 (2026-10-21; E.4.4, #2411)

**What changed.** IR-3 was written before two later decisions:
- **§5ad (the owner, 2026-10-20):** a Campaign's snapshot fixes which instruction revisions are in force, and each of
  its Cycles binds their `@current` repository references at its own pinned commit when the Campaign launches it.
- **H.2:** a sync's relevant drift holds new Cycles until the Project is reconciled.

So "the Campaign's later Cycles keep the admission binding" reads, after both, as follows. A Campaign is admitted with
a project instruction citing a repository instruction source at `@current`, and an outside commit then changes the
source:
1. **The Campaign's snapshot is unchanged.** It pins the same instruction revision. A Cycle already launched keeps the
   content it bound at its own commit.
2. **The drift is found and holds new work.** A sync records it (`relevant: instructions`). Until the Project is
   reconciled, the Campaign's next launch is refused, so the Campaign escalates (§B.5.1's "held and escalated"), and a
   standalone Cycle is refused too.
3. **After reconciliation** (validate, configure, baseline at the new commit):
   - **the Campaign:** its refused launch left it escalated, with the launch intent pending. Once the owner resumes it,
     its next Cycle binds the reference at its own pinned commit, the new content;
   - **a standalone Cycle** created afterwards binds the new content at its admission.
4. **A re-binding** changes the Campaign's instruction revision only as a recorded intervention, unchanged from the
   IR as written.

**What became of "carry a drift finding":** after §5ad, no drift finding is recorded per Cycle. The finding is two
records:
- the later Cycle's own binding, whose reference revision and digest differ from the first Cycle's;
- the sync's drift document, which names the changed source as `instructions`.

**The evidence:**
- `tests/unit/projects/test_ir3_campaign_instruction_drift.py` enters at the Campaign launcher's `_build_cycle`, at
  `prepare_cycle` and `pin_standalone_cycle` for the standalone Cycle, and at `sync_project`. It enters below the
  drain, so it shows what each launch binds, not the escalation and the owner's resume between them. It runs over the shared
  fixture's Tally through the real managed clone, with the repository family's own resolver. A mutant without H.2's
  gate fails it.
- Point 4 is the re-binding route's: `tests/unit/api/test_rebinding.py` and
  `tests/unit/memory/test_campaign_cycle_bindings.py`.
- Live: H.2's hold was shown on the Spark's brownfield re-run and on the Mac (#2611).
- **Not run live yet:** a Campaign's later Cycle binding a reference after reconciliation. It needs a Campaign past its
  calibration on an external Project, which is the Spark's full squad. The Spark lane runs it before 2.4's cut, on
  `z_continuum`, tracked on #2179 (the binding side's issue).

**Who ruled:** the MacBook lane, under the owner's delegation of 2026-10-18. The restatement follows the owner's
ruling of §5ad and H.2; it decides nothing new.

## H.4 A repository-backed Project's development profile is derived, its gaps are named, and Campaigns run on it (2026-10-21; #2619; placed in 2.5)

**What was found.** A Campaign on a repository-backed Project can run its calibration cycle but can never launch an
increment (#2619, the Spark lane, 2026-10-21). That holds for an external product and for a greenfield one alike: once
created, a greenfield product is a repository registered like any other, and its cycles are source-backed. There are
three causes:
1. **The template stack.** The Campaign's increment request profiles (`campaign-increment`, `campaign-increment-asks`)
   pin the `fullstack_fastapi_react` template stack, and a source-backed cycle refuses a stack (E.4.3's
   `source_backed_stack_decision`).
2. **The proposal's input.** A proposal reads the accepted cycle's interface manifest from the artifact vault. A
   source-backed cycle carries none forward, not even for a greenfield product whose approved manifest made its first
   commit.
3. **The calibration's input.** The calibration launch carries no PRD or plan, so its cycle fails at provisioning
   ("implementation plan required but absent", IR-2's live run).

A Campaign on a sample application, which lives only in SquadOps's vault, is unaffected: the 2.4 window ran four.

**The owner's direction, 2026-10-21:** "it seems we need a way to derive the stack and recipe and call out any gaps
preventing squad ops from working on it", and then "go with 2.5, write up the amendment".

**The design:**
1. **A derived development profile.** E.4.2's discovery is extended. When a Development Configuration revision is
   recorded, SquadOps reads the pinned tree and the configuration, and records with the revision what its roles
   depend on:
   - the languages and their package managers;
   - the test runners and the test command;
   - the lint and type tools, and the findings reader each takes (#2609);
   - the start declaration;
   - the blueprint the tree follows, if any. A greenfield product names its blueprint in its configuration, and the
     tree and the approved manifest are checked against it;
   - the toolchains the declared commands need. These are read from the baseline capture's own evidence, never from a
     stack's environment contract, which fits no arbitrary product. A check UNVERIFIED as `command_not_found` or
     `command_not_executable` names a missing toolchain, recorded with the image it ran on.
2. **Capability gaps, named.** Each fact the squad can't serve is a gap, with what it blocks and what would close it.
   Examples:
   - a frontend whose test framework QA doesn't author: the squad's changes there go unverified by its own tests;
   - a toolchain the sandbox image lacks: those checks are UNVERIFIED;
   - a lint without a findings reader: it is compared only whole;
   - no start declaration: Outcome Evaluation is blocked.

   The gaps are recorded with the revision, and `projects configure` and `projects show` report them. Each gap is one
   of two kinds:
   - **blocking:** the gap leaves no check that the work's footprint touches able to run. A Cycle or a Campaign whose
     work would meet one is refused before dispatch, naming it.
   - **disclosed:** reported, and recorded with each run it applies to, but not refused. For one, a missing start
     declaration blocks only Outcome Evaluation, which reports, and never the Cycle.

   This is the existing rule that an unsupported layout or toolchain surfaces a capability gap, never an automatic
   restructuring (E.7), given a record.
3. **The recipe is derived, not pinned.** Request profiles carry no stack.
   - A sample application's stack comes from its Project and the Campaign's policy, as today (#2443).
   - A repository-backed Project's cycles take the derived profile:
     - nothing is seeded, and the squad starts from the product's own tree;
     - the checks are the configuration's;
     - QA writes tests for the product's own runner;
     - a greenfield product that follows a blueprint gets that blueprint's QA and check conventions, without its
       template laid down.
   - E.4.3's guard narrows from "a stack is named" to "a skeleton would be seeded", which is what it protects against.
   - Removing the stack from the profiles comes with a resolution-parity test. Every sample application's Campaign
     definition (`examples/03_group_run/campaigns/*.yaml`, the window's four included) must resolve to the same cycle
     requests as before, with `policy.stack` set and with it unset.
4. **Campaigns on a repository-backed Project.** SIP-0109's calibration and proposal, as they read such a Project:
   - **Calibration is the inherited baseline.** The first accepted tree is the pinned commit, already checked by the
     product's own checks (FR-20). Nothing is built, so the calibration needs no PRD or plan.
   - **A proposal reads the product's tree** (the bounded view) and its derived profile, where a sample application's
     proposal reads its interface manifest. A greenfield product's approved manifest, recorded at its
     initialization (H.1), is read beside them.
   - **Increments stack on a campaign branch** in the managed clone. A standalone source-backed cycle seeds from the
     Project's development baseline and captures one commit on it. A Campaign's increments would then each restart
     from upstream, without the one before, unless that one had been merged and reconciled first. So:
     - each accepted increment's captured commit is the next increment's pinned commit;
     - its regression baseline is the previous increment's verification, at that commit;
     - the per-cycle binding (H.3, SIP-0110 §5ad) reads instruction sources as the previous increment left them;
     - contract 4's mapping holds per increment.
   - **One review request per Campaign** is the contribution: its branch, holding the accepted increments in order,
     updated as each is accepted. The owner can merge it at any time. A later process per increment can be added
     beside it, but this is the default.
   - **When upstream moves** (H.2), the campaign branch is rebased onto it before the next increment launches. A
     rebase that conflicts escalates the Campaign, never resolving by itself. Merged increments then read as
     integrated (H.2's attribution).
   - **Serial contribution was rejected:** each increment merged upstream before the next could start. It would stall
     an unattended Campaign on the product owner's review.
   - **Each increment is a source-backed cycle,** verified by the product's checks and contributed through the
     campaign branch, as above.
   - **Contract 1's pin, for an increment.** `prepare_cycle` pins a repository-backed Campaign increment's source
     context at the campaign branch's head (SIP-0109 §24bv point 3), never the Project's
     `development_baseline_commit`. Its inherited-baseline check reads the previous accepted increment's verification
     there, or the calibration record's baseline for the first. H.2's gate keeps reading the Project's baseline,
     since a sync's drift is upstream's against the Project, and §24bv point 4 reconciles it before the branch
     rebases.

**What stays:**
- A sample application's Campaigns are unchanged, and the counted pair holds (IR-10).
- Standalone cycles on repository-backed Projects are unchanged: both 2.4 demonstrations ran on them.
- A drift's hold (H.2) and the per-cycle binding (H.3) apply to every increment as to any cycle.

**Boundaries:**
- **SIP-0109** owns the calibration and proposal mechanics. This amendment states what they read for a
  repository-backed Project, and SIP-0109 records the counterpart (the Spark lane's). There, the calibration is a
  calibration record, not a cycle, and counts toward no cycle limit. The proposal reads the tree view, the derived
  profile and the previous increment's verification, and its criteria freeze as typed checks on the product's runner.
- **SIP-0113** records its own counterpart (the Spark lane's): Outcome Evaluation's Campaign baseline is an evaluation
  of the pinned commit, read against the calibration record.
- **SIP-0105** owns the blueprints. The derived profile recognises one, and never generates one.

**In 2.4:** the shared demonstration (the 2.4 plan's D13: one Campaign on an external Project across two features)
can't run its feature cycles. It reports *not run*, naming #2619 as its prerequisite, as the plan provides (G5).
- IR-3's live half ran through calibration launches instead (#2179).
- IR-2 and both demonstrations are unaffected.

**The evidence:**
- #2619's three refusals, at the lines it cites.
- IR-2's calibration cycle failing at provisioning for lack of a plan (`cyc_95c8659ae6c5`, #2611).
- The Spark lane's IR-3 run on `z_continuum`, which reached a Campaign's calibration and no further.

**Who ruled:** the owner, 2026-10-21: the direction, and placement in 2.5. The MacBook lane wrote this. The Spark
lane's G4 (on #2624) added:
- the campaign branch (the stacking gap);
- blocking against disclosed gaps;
- toolchain gaps read from the baseline's evidence;
- the resolution-parity test.

## H.5 A check failing on both sides is compared finding by finding when it declares a reader (2026-10-21; #2609)

**What was found.** In the brownfield demonstration's stage 6 (#2611), the candidate added three ruff findings to
`lint`, which already failed at the baseline: 59 findings before, 62 after. The acceptance policy reads a check only
by its result, so the change read FAIL on both sides, `inherited`, and was accepted (#2609). On an unfamiliar product,
an already-failing lint or type check is the common case. A contribution could make one worse, change by change, with
every record saying `inherited`.

**What changed:**
1. **A check may declare a findings reader** in the Development Configuration (`findings: <reader>`), from a closed
   set (`squadops.sandbox.findings.READERS`), each reader versioned. `configure` refuses an unknown reader, naming the
   field.

   | reader | a finding's key | readable when |
   |---|---|---|
   | `ruff` | `"<code> <path>"`, never the line, in either output format, with syntax errors keyed `invalid-syntax` | exit 0 (none), or exit 1 with its rows adding up to its own "Found N errors." |
   | `pytest` | `"FAILED <node>"` or `"ERROR <node>"` | exit 0 or 1, with its rows adding up to its summary, which also gives the tests it ran |
   | `lines` | each non-empty output line, digits replaced | exit 0 (none), or any other exit with a line to read |

   Anything else is unreadable, with its reason: a tool error, a collection error, rows short of a summary, or more
   than 10,000 distinct keys. An unreadable run is never read as clean, since a run that broke would otherwise erase
   the baseline's failures as an improvement.
2. **The sandbox applies the reader** to the check's whole stdout and stderr, before their tails are cut (X-3a, #2623;
   the tail was 4,000 characters, and continuum's ruff output alone was 35,921). A named reader always answers: a
   command that never ran to an exit (a setup step stopped it, a timeout, not found, no daemon) reads as unreadable,
   with why. Each tail now says whether it was cut (#2622).
3. **The inherited baseline stores each check's reading,** additive in `inherited-baseline/v1`'s check rows. Baseline
   and candidate are read by one reader at one version, through the same `run_checks`.
4. **The acceptance policy is `no-introduced-regression/v2`.** For a FAIL on both sides, when the check declares a
   reader and both runs were read:
   - **a finding key whose count grew** makes the check `introduced/regressed`. It blocks, and the verification names
     the keys;
   - **readings that can't be compared** (another reader or version, an unreadable side, or a pytest run that ran fewer
     tests than its baseline) make it `unverified attribution`, which blocks;
   - **otherwise** it is `inherited`.

   A check with no reader, or a baseline captured before v2 (`baseline has no findings`), is read whole, as v1 read
   it. Its row says so (`read: whole`, with the reason). A v1 verification stays readable as it was.
5. **§8.3.1's rule** "an inherited `FAIL` is never an introduced regression" now reads: "…unless its check declares a
   findings reader and a finding key's count grew".

**IR-9, restated for both cases:**
- **A check with no reader:** as written. The shared fixture's inherited failure stays reader-less, and stays `FAIL`,
  `inherited`.
- **A check with a reader:**
  - a key grew: `introduced/regressed`;
  - none grew: `inherited`;
  - a run that broke: `unverified attribution`.

**Blind spots, named:**
- a file renamed or moved makes its findings new keys, so the check blocks (conservative);
- a finding swapped for another of the same key, in the same file, is masked;
- a failure newly skipped or xfailed reads as removed: "no longer failing", not an improvement;
- deleted tests leave pytest's readings incomparable (fewer ran), so the check blocks.

**The evidence:**
- **The readers, on real output** (`tests/unit/sandbox/test_findings_readers.py`, #2620):
  - continuum's 59 findings at `ba8fa68b` read the same in both ruff formats;
  - stage 6's candidate `0c814a7c` grows exactly `I001 src/continuum/cli.py`, `E501` and `F401` in the new test;
  - stage 3's `2f6b3baa` grows none;
  - a collection error and a ruff tool error read unreadable.
- **The sandbox** (#2623) reads the whole output past the tail, on the same continuum output.
- **The attribution table** (`tests/unit/projects/test_baseline.py`) runs on those readings, and stage 6's
  verification is `regressed: lint gained findings…`.
- **The wiring test** (`tests/unit/projects/test_workspaces.py`) enters at `capture_inherited_baseline`, then
  `run_checks` and `attributed`. The shared fixture's `parse` is read by `lines`, and a candidate that adds a second
  failure inside it is `introduced/regressed`, while the reader-less checks are untouched.

**Who ruled:** the MacBook lane, under the owner's delegation of 2026-10-18. The Spark lane's G4 is on #2609 (the
design, issuecomment-6326651632), on X-3a's shape (a), on #2620 and on #2623.

