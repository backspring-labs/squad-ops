---
sip_uid: '17922606138197288'
sip_number: null
title: "Independent Project Lifecycle Management"
status: "proposed"
author: "Framework Committee"
approver: null
created_at: "2026-10-16T00:00:00Z"
updated_at: "2026-10-16T00:00:00Z"
original_filename: "SIP-Project-Lifecycle-Management.md"
---
# SIP-XXX — Independent Project Lifecycle Management
## External Product Development, Managed Clones, and Governed Continuity

**Status:** Draft  
**Target Version:** TBD (intentionally unassigned)  
**Author:** Framework Committee  
**Roles Impacted:** External Product Owner/Maintainer; Lead, Strategy, Dev, QA, Data  
**Date:** 2026-10-16  
**Revised:** 2026-10-17  
**Document Revision:** 4 — external owner authority, inherited quality baselines, instruction precedence and existing-product-first proof  
**Source Baseline:** `backspring-labs/squad-ops`, `main`, commit `7aecfa0b3ff6576f115eba10c2ee3465774e997d` (freshly pulled and inspected 2026-10-17)  
**Related SIPs:** SIP-0064 (Project Cycle Request API); SIP-0065 (CLI for Cycle Execution); SIP-0074 (Console Cycle Operations UX); SIP-0102 (sandbox workspaces); SIP-0109 (Campaign Orchestration); `SIP_CYCLE_DATA_STORE.md` (earlier design reference); `SIP-XXX-Game-Development-Godot-Roblox-Remote-Execution.md` (downstream consumer)  
**SIP Number:** Provisional—allocate the next available identifier only after checking the current registry.

## Intake check

Checked against `sips/PORTFOLIO.md` on 2026-10-17, before this draft was recorded (CLAUDE.md, "SIP
System"). The body below is the owner's revision 4 as written. The findings are reconciled by a revision
in the same PR, and the open ones are Q30–Q33 in the portfolio's §4.

- **Overlaps:**
  - **SIP-0047** (Cycle Data Layout, Project Registry and `CycleDataStore`, implemented 2025-11-29) is
    the document this draft cites as `SIP_CYCLE_DATA_STORE.md`, its original filename. Its
    `CycleDataStore` was built in the v0 tree and removed with `_v0_legacy/` (`dd105d1a`), so its status
    no longer describes main. This draft takes over its project-registry concern (Q30).
  - **SIP-0109** (Campaign): the launcher, accepted trees, increment seeding and the brownfield reference
    scenario (§11a). The boundary is stated here (FR-08): Campaign keeps its state machine, budgets,
    launch and promotion; this SIP supplies the project's eligibility and source context, and maps
    accepted trees to Git revisions.
  - **SIP-0102** (sandbox): `WorkspaceStore`'s live trees, revisions and leases. The boundary is stated
    here (FR-05, §B.3): a managed clone reaches the sandbox through its existing boundaries, never as a
    second live tree, and a sandbox content hash is never a Git commit.
  - **SIP-0110** (Cross-Cycle Memory): its *project instructions* record kind, pinned in the unit
    snapshot (Appendix A §A.3.6, placed in 2.4.0 as #2179), and this draft's development instructions,
    pinned per cycle with precedence and drift rules (§B.5.1, FR-21), cover the same ground. The boundary
    waits for the owner's ruling (Q31).
  - **SIP-0103's manifest** and this draft's *Project Manifest*: one word, two meanings (Q32).
  - **SIP-0105** (stack blueprint) and the draft's technical profile; **SIP-0108**'s benchmark registry
    and the draft's reference/benchmark profile: where a stack and a benchmark are declared. The
    boundary is stated in the reconciling revision.
  - **SIP-0064, SIP-0065, SIP-0074:** the project API, CLI and console this draft extends. The boundary
    is stated here (Appendix D): existing routes, commands and aliases are kept, and lifecycle writes
    are added beside them.
- **Conflicts:** SIP-0047 prescribes the `cycle_data/<project_id>/<ECID>/` layout and a `CycleDataStore`,
  and this draft rules that neither is imposed (§A.1, §E.2), while SIP-0047 reads as implemented. It
  waits for the owner's ruling (Q30).
- **Cited sources the repository does not hold:** `IDEA_Cycle_Orchestrator_Pulses_and_Surges.md` (§A.2
  calls it canonical), `IDEA_Cycle_and_Pulse_Execution_Model.md`, and the Godot/Roblox game development
  SIP (§A.3, FR-17). Each is committed, or its reference rewritten (Q33).

## Delivery ledger (current as of 2026-10-17)

One row per part that ships separately, from Appendix E.4. Statuses: *shipped* (the release, the PR,
and the issue it closed), *placed* (the release and the open issue tracking it, labelled `sip:NNNN` once
numbered), *unplaced* (said deliberately), *dropped* (by the numbered amendment that dropped it), or
*deferred to N.x (ruled <date>)*. Updated in the PR that ships or re-places a part
(`tests/unit/architecture/test_sip_ledgers.py` holds it). The owner's direction of 2026-10-17 is a 2.4
feature on the MacBook lane, beside Outcome Evaluation's feature half on the Spark; each row is placed at
acceptance, when it has its issue.

| part | status | where |
|---|---|---|
| E.4.1 existing-product registration and authority: the writable registry cutover and minimum enrollment | **unplaced** | — |
| E.4.2 repository-native discovery and the inherited baseline | **unplaced** | — |
| E.4.3 the first scoped feature through the shared cycle path | **unplaced** | — |
| E.4.4 the second feature after an outside contribution | **unplaced** | — |
| E.4.5 the complete lifecycle and rollout | **unplaced** | — |
| E.4.6 additional onboarding modes and targets (greenfield, direct attachment, game profiles) | **unplaced** | — |

**What closes this SIP:** E.4.1–E.4.5 shipped, and E.4.6 shipped or dropped.

---

**Decision:** SquadOps will act as a governed development team for independently owned products. The product repository remains authoritative and independently usable. SquadOps maintains a durable Project identity, development configuration, Cycles/Campaigns and evidence, and uses managed clones/worktrees to perform authorized work.

**Revision 4:** Clarifies external owner decision rights, establishes inherited quality before source changes, defines precedence and drift handling for development instructions, and makes an existing external product the first end-to-end proof. The detailed CLI reconciliation and implementation contracts are retained in the appendices.

# 1. Direction and intended outcome

A product owner can bring an existing repository to SquadOps, request an improvement, review the resulting contribution and return later for further development. The product keeps its source structure, native tools, history and contribution process. Other developers remain able to work on the same repository.

The first success case is an unfamiliar, supported external repository enhanced through two governed iterations, with an outside contribution between them. New-product creation remains supported, using an owner-approved external source destination and a product-appropriate structure.

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
2. **Discover:** clone/fetch approved source and inspect native structure, toolchain, build/test commands and applicable maintainer instructions without onboarding source edits.
3. **Establish the inherited baseline:** pin the unmodified source and effective development configuration; run agreed build/test checks and retain failures, environment gaps and UNVERIFIED checks.
4. **Implement:** start through the existing Project-targeted Cycle path, optionally under an existing Campaign, using isolated branches/worktrees and the agreed scope.
5. **Verify and accept a candidate:** compare relevant results with inherited evidence and evaluate the owner's acceptance policy. Retain exact tested source/configuration and any remaining defects.
6. **Contribute and confirm integration:** deliver through the product's permitted branch/review-request/patch/direct-integration process. Record the actual resulting upstream revision; a push or internal PASS alone is not integration.
7. **Continue:** fetch external changes, reconcile relevant source/instruction drift, refresh affected evidence and perform the next iteration against the same Project.

Approved but unintegrated development commits may seed later work under explicit continuation policy. Keep the development baseline separate from the last confirmed integrated-upstream revision; retain pending changes before workspace cleanup.

# 4. Quality baseline and development instructions

**Observe the product before changing it.** Baseline evidence binds the repository commit, applicable commands/working directories, technical profile/instruction versions, dependency/toolchain/environment identity and actual results. An inherited FAIL stays FAIL. A check that could not execute stays UNVERIFIED. Neither is silently converted to a successful result because the squad did not cause it.

Check outcome and regression attribution are separate: a candidate may retain an inherited defect, introduce a regression, resolve a defect or have insufficient evidence for attribution. Owner-approved policy determines whether scoped development can proceed with identified inherited issues. The squad is not automatically tasked with fixing every pre-existing defect, and missing evidence does not grant a waiver.

**Bind SquadOps configuration to the product's instructions.** Applicable runtime access restrictions and authorized owner/maintainer decisions govern the work; applicable contribution rules and repository-native build/test definitions govern product execution; SquadOps technical profiles encode those bindings. Explicit, authorized exceptions are versioned and auditable. A stale profile cannot silently override current product instructions, and repository content cannot grant runtime privileges.

Before feature-source changes, inspect relevant upstream changes to instructions, build/test scripts, dependencies and toolchains. Reconcile/revalidate the affected profile and baseline checks before relying on them. Unresolved policy conflicts stop the affected operation and are reported through existing governance. Verification is scoped to relevant changes and the agreed contract rather than requiring an indiscriminate rerun of every check.

Registration readiness, development eligibility, engineering-candidate acceptance and external integration remain separately visible. A registered Project can have pending baseline work; that state is not a claim that the product passes its checks.

# 5. Mandatory integration boundaries

- Extend the existing plural `squadops projects` CLI and `/api/v1/projects` resources. Preserve `projects list/show`, existing aliases and shared client/config/auth/output behavior.
- Preserve `squadops cycles create <project_id> --squad-profile ...`, request-profile/PRD behavior and immediate first-Run execution. Standalone and Campaign launches share Project context/eligibility checks; preserve the Campaign launcher and control authority.
- Keep one selected authoritative Project registry. The current inspected provider is YAML-backed; lifecycle writes require an explicit writable-provider migration/cutover, with existing IDs and history preserved.
- Keep external Git commits, sandbox revision hashes, artifact baseline pointers and Campaign accepted-tree identities distinct and linked by evidence. Preserve existing artifact/sandbox contracts and historical readers.
- Store required SquadOps metadata outside product source by default. No sample conversion, mandatory `.squadops` files, prescribed source directories or replacement build system is required. Unsupported tooling/layout produces an explicit capability gap.
- Honor product integration policy and expected-target-head checks at the actual write boundary. Bind verification to tested content/configuration and revalidate affected results after changes, including rebase/merge/squash.
- Archive the SquadOps engagement without changing external repository ownership/lifecycle or losing unintegrated contributions. Product builds remain usable with native tooling independently of SquadOps.

# 6. Scope and delivery priority

The lifecycle includes create, import/clone, attach, list/show, validate, update, history, archive/restore, source/workspace management and durable handoff. Technical targets use adapters; repository layout remains product-defined. Production hosting, a new source-control system and replacement Campaign/orchestration semantics are excluded.

Prioritize existing-product registration, managed cloning, native discovery/baseline verification, a first feature contribution, and a second feature after an outside update. Complete lifecycle/rollout hardening and additional onboarding modes as subsequent slices. Greenfield repository creation, direct attachment and game targets remain supported goals; they do not substitute for the existing-product proof. Operations enabled in any slice already need their applicable authorization, idempotency and integrity checks.

The implementation details, proposed schemas/routes and migration choices live in the appendices. They are explicitly distinguished from verified contracts at the pinned source revision.

# 7. Primary acceptance demonstration

An external product maintainer supplies an unfamiliar supported repository with a non-sample layout and a scoped feature request. Demonstrate all of the following:

- Registration assigns a stable Project ID and complete out-of-repository metadata with no onboarding changes to product source or required SquadOps files.
- The squad records owner delegation, effective instructions and the agreed build/test results at the pinned unmodified source, including inherited defects or UNVERIFIED checks where present.
- A first Cycle delivers a scoped feature, relevant QA and a traceable contribution through the product's normal acceptance/integration process.
- An outside developer advances the repository or relevant development instructions. A later Cycle detects/reconciles the change, refreshes affected profile/baseline evidence and delivers another feature through the same Project.
- Internal candidate approval, check outcomes/regression attribution, pending contributions and confirmed integrated revisions remain distinguishable throughout.
- Handoff/archival retains pending work and evidence while the product remains usable with its native toolchain. Existing registered references such as `group_run` retain compatibility.

Greenfield creation and additional target adapters are secondary acceptance demonstrations. The detailed Definition of Done is in Appendix E.7.

# 8. Detailed contracts and implementation appendices

The directional requirements above and the functional requirements below are normative. Tables/examples explicitly labeled illustrative or proposed describe unimplemented additions; Appendix A records inspected implementation facts. Appendix F preserves the pinned source evidence.

| Appendix | Contents |
|---|---|
| A | Verified implementation baseline, execution semantics and problem statements |
| B | Detailed source/workspace/manifest design and external repository contract |
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
| Project model | `project_id`, `name`, `description`, `created_at`, `tags`, `prd_path`. Existing entries include `hello_squad`, `run_crysis`, `group_run`, `play_game`, and `agent_chess`. | Add lifecycle, ownership, source, technical profile, manifest, quality and accepted-source metadata while preserving existing fields/IDs. |
| Cycle creation | `squadops cycles create <project_id> --squad-profile <id>` uses request profiles, optional `--prd`, `--set`, and `--notes`; posts to `/api/v1/projects/{project_id}/cycles`. Creation starts the first run immediately. Server-side `prepare_cycle()` resolves the Project through the existing registry. | Enrich that shared preparation path with Project eligibility and pinned source/workspace context. No alternate launch command or execution path. |
| Cycle persistence | The implemented table is `cycle_registry`, with `project_id TEXT NOT NULL`; Runs have their own records. The inspected migrations do not define the earlier draft's `projects` table or `execution_cycle` table. | Add the Project persistence migration and backfill before enforcing database referential integrity. Preserve `cycle_id` and `run_id`. |
| Artifacts | `ArtifactVaultPort`, runtime-selected filesystem adapter, project/cycle/run-scoped artifact APIs and PRD ingestion already exist. Default artifact root is `data/artifacts`. | Store new lifecycle evidence through existing artifact contracts, adding metadata only where needed. |
| Workspaces | Sandbox `WorkspaceStore` already provisions per-Cycle live trees, hash-pinned revision manifests, HEAD pointers, stale-base protection and leases. The configured default root is `cycle_data/sandbox`. | Add external repository bindings and managed clone/branch management integrated with these sandbox boundaries. |
| Version control | `VersionControlPort` and the Git adapter already provide status, commit and push; `PathValidatedVCS` applies the existing path policy. | Reuse those boundaries and add the missing repository provisioning/import, exact-revision checkout/worktree and expected-base promotion capabilities. |
| Baselines and continuity | `baseline set/get/list` manage per-type artifact pointers. Campaigns already retain accepted tree identities, accepted Cycle IDs, promotion decisions and increment seeding. | Add a Project-level accepted Git revision and explicit mapping to artifact/Campaign/sandbox identities. Preserve existing promotion authority. |
| Campaigns | SIP-0109 CLI/API, policy, control log and launcher already exist. Campaign launches use the shared cycle request builder and preparation path. | Carry Project eligibility/source context through that launcher; preserve Campaign control semantics. |

No Python `CycleDataStore` implementation was found in the inspected `src/` and `adapters/` trees. The older `SIP_CYCLE_DATA_STORE.md` describes a proposed `projects`/`execution_cycle` schema and `cycle_data/<project_id>/<ECID>/` layout. Those are **design references**, not the runtime contracts to impose over current code. This SIP does not require a storage-layout replacement or a second artifact service. Any later adoption of that layout requires a separately specified mapping, migration and rollback that preserve existing artifact IDs, Run associations and readers.

**Reuse is mandatory:** existing CLI commands call the existing API client; existing API readers continue through `ProjectRegistryPort`; standalone and Campaign-launched Cycles use the same Project-aware preparation path. Implementation planning identifies missing capabilities and integration changes, rather than reconsidering whether to reuse the existing CLI.

## A.2 Canonical execution semantics

The implemented Cycle/Run orchestration remains the execution authority. The supplied **“Cycle Orchestrator, Pulses, and Surges”** IDEA describes the following additional design semantics; referencing it does not assert that every concept is implemented at the inspected revision:

- **Cycle:** authoritative governed execution container, including rewind/recovery.
- **Pulse:** coordination-topology change; only the Cycle Orchestrator may emit it; it is the legal rewind boundary.
- **Surge:** non-authoritative logical grouping of tasks originating at one Pulse, without gating execution.
- **Task:** atomic execution/throughput unit that may outlive its originating Pulse.

Projects, Campaigns, repositories, workspaces, and reference benchmarks MUST NOT introduce alternative Cycle lifecycle authority.

## A.3 Why this matters now

Godot and Roblox support is useful only if SquadOps can build genuine applications independently of its test fixtures. The companion **Game Development Platform Capability** SIP therefore depends on this Project Lifecycle SIP. Game engines are technical target profiles of Projects; they are not a parallel project registry or special orchestration system.

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
| **Project Manifest** | Versioned development configuration and intent metadata | Stored with SquadOps Project metadata by default; no required file in product source |
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
        Single selected registry provider + versioned manifest
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

**Cycle evidence:** immutable or versioned artifacts and references associated with Project, Cycle and Run through existing artifact and telemetry services. New Project manifests, handoffs and source-promotion evidence reuse `ArtifactVaultPort` where appropriate.

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

The authoritative product source may reside on any approved external Git host or filesystem root. A managed clone is the normal development option for existing products; attachment to an approved existing checkout is also supported within explicit permissions and isolation policy. Never presume the framework repository or sample tree is the product destination.

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

## B.5 Project Manifest

A versioned manifest MUST define, or reference in the authoritative SquadOps registry, at minimum the development configuration below, including the external product owner/maintainer, delegated engineering authority and versioned acceptance policy. This is **SquadOps Project metadata**, stored in its registry/artifact storage by default. An in-repository export is optional and explicitly opt-in; enrollment does not create `.squadops/`, rewrite existing metadata or require this manifest to live in the product tree.

The fields below are proposed schema additions, not a claim that the current CLI accepts them:

```yaml
api_version: squadops.project/v1
project:
  id: prj-space-adventure
  name: Space Adventure
  description: Godot exploration game
  lifecycle_status: READY
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
  technical:
    project_type: game
    target: godot
    profile_ref: project-metadata/technical-profile-v1
  workspace:
    mode: managed_clone
    preserve_repository_layout: true
  governance:
    promotion: approval_required
    publishing: approval_required
  quality:
    contract_ref: project-metadata/quality-contract-v1
  classification:
    reference_app: false
```

**Manifest/registry authority:** After the provider cutover in FR-03, the selected writable registry is authoritative for SquadOps identity, engagement status, access/engagement ownership, and configured external source locator; the product repository remains authoritative for source history and integrated refs; a manifest is a versioned, exportable declaration. Before cutover, YAML remains the implemented lookup authority; a manifest must not shadow it. Conflicts MUST be rejected or reconciled by an explicit, auditable operation. A manifest is not an alternate project registry.

`profile_ref` and `contract_ref` in this example resolve through SquadOps Project metadata, not mandatory product files. The actual default branch is discovered/configured per product; `main` is illustrative. Repository commands, working directories and toolchain/environment bindings are recorded in the versioned technical profile and reference existing product tooling. Record the repository revision and relevant instruction/build-definition hashes that informed the profile; stale metadata must be revalidated under FR-21. Record inherited build/test evidence separately under FR-20. Engine-specific keys belong under a versioned technical/target profile, not in core Project Lifecycle logic.

### B.5.1 Product authority and development-instruction precedence

The external product owner/maintainer owns product intent, priorities, scope, constraints, quality expectations and final product acceptance. The owner may delegate engineering decisions, candidate acceptance and contribution/integration actions through explicit Project policy. Strategy interprets intent and proposes work; Lead acts within that delegation. A SquadOps role has no implicit authority to replace the owner's roadmap or acceptance criteria. Existing valid delegation remains effective across Cycles; this is not a requirement to request a new approval for every routine authorized action.

Apply development instructions in this order: applicable runtime access restrictions and authorized owner/maintainer decisions; then the product's applicable contribution/development rules and native build/test definitions; then the SquadOps technical profile that records how to execute them. The profile is an execution binding, not an independent source of product policy. Owner-approved exceptions must be explicit, versioned and auditable. If an unresolved conflict affects execution or contribution, block the affected operation and surface the conflict; do not silently choose a stale profile or infer permission from repository text. Repository instructions cannot grant credentials, widen runtime permissions or override access restrictions.

Pin the effective instruction sources, source revision and profile version for each Cycle. Before dispatch, inspect relevant upstream changes to build/test scripts, dependency/toolchain definitions, contribution policy and instructions. Changed relevant inputs invalidate the previous profile/baseline evidence until reconciled and revalidated. Unrelated changes need not trigger a blanket rerun; the technical/quality contract identifies the affected checks. Refresh the profile within existing authority where the change is routine; surface a policy conflict when a new owner decision is actually required.

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

The system MUST accept a new application/game PRD or design brief and create a unique Project without selecting a sample application.

On `create`, the system MUST:

1. Validate caller authorization and requested project fields.
2. Assign or validate a unique immutable `project_id`.
3. Register the Project, including initial lifecycle status.
4. Provision source at a product-approved external destination, or bind an approved pre-provisioned repository; create an isolated managed development copy.
5. Produce the initial Project Manifest and intent records in SquadOps Project metadata storage, without requiring files in product source.
6. Validate basic tool/environment capability declarations.
7. Set the Project to `READY`, or record a diagnosable registration failure. Registration readiness is distinct from evidence that the product currently passes its build/tests; execution eligibility must also account for the inherited baseline and acceptance policy in FR-20.

No hidden reference-app lookup or prescribed source layout is permitted as a prerequisite. For a greenfield product, choose its structure from the approved product requirements and selected stack, then retain the same external repository/ownership model used for an existing product. Registration itself does not authorize remote repository creation or publication beyond the caller's configured permissions.

## FR-02 — Import or attach an existing repository

Support an existing project by:

- **Import:** register the external authoritative repository and clone/fetch it into a SquadOps-managed development cache/workspace, retaining upstream, history and provenance. Here import means development onboarding; it does not relocate source ownership or replace the authoritative repository. A snapshot/export is a separate explicitly selected mode and must not masquerade as an upstream-linked clone.
- **Attach:** register an approved external repository/location and prepare development against it without moving its authoritative source. Prefer isolated worktrees/managed copies for writes; modifying an existing checkout requires its explicit configured permissions and branch/isolation controls.

Operations MUST validate Git status (where applicable), path safety, permissions, reachability and repository-native tooling. Before feature-source changes, perform read-only discovery and capture the inherited verification baseline at the pinned unmodified source revision; builds may write their normal disposable workspace outputs, but must not alter the baseline source to manufacture a passing result. Discover the existing layout and commands without changing them; record development configuration outside product source by default. Changes to attached/external source MUST respect explicit write permission, contribution policy and branch controls.

Importing MUST NOT silently overwrite a destination or publish to a remote.

## FR-03 — Extend the implemented registry and migrate its authority

Preserve `ProjectRegistryPort.list_projects()` and `get_project()`, the current Project fields (`project_id`, `name`, `description`, `created_at`, `tags`, `prd_path`), and existing API identities. Add lifecycle writes through a typed service/port integrated with those readers.

**Proposed persistence decision:** introduce a transactional writable Project registry adapter in the runtime persistence layer, using the existing migration runner and dependency-injection/factory conventions. A `projects` table is a new migration, not an already deployed table. Extend the Project model and response mapping with:

- project lifecycle status and ownership/access scope;
- external authoritative repository type/locator and product-defined base/integration refs;
- development-baseline and integrated-upstream commit identities, plus contribution mode and pending integration state;
- managed clone/workspace configuration and readiness, kept distinct from authoritative source location;
- current manifest version/hash/artifact reference;
- technology/target profile and quality contract references;
- external owner/maintainer, delegated authority, versioned acceptance policy, registration provenance and timestamps;
- effective instruction/profile versions and inherited verification-baseline evidence references;
- references linking source promotions to relevant Campaign accepted trees, sandbox revisions and verification artifacts.

Migration MUST import the current YAML Projects without changing IDs, names, tags or PRD associations, reconcile all persisted `cycle_registry.project_id` and Campaign project references, and report unknown or conflicting IDs before enforcing foreign keys. Preserve an explicit mapping for the older draft's `is_internal` and `updated_at` fields if adopted; neither exists in the inspected Project model. `is_internal` MUST NOT imply benchmark membership; preserve current classification tags.

At cutover, select exactly one authoritative registry provider for every Project reader and writer. The config adapter remains a compatibility/read-only provider or explicit seed/import source. Do not merge cached YAML and writable records at lookup time, silently edit client-local YAML, or let newly created Projects be invisible to running API/Campaign workers. A deployment retaining the config-only provider must explicitly reject unsupported lifecycle writes. Configuration, dependency wiring, cache invalidation/reload behavior and rollback must be specified and tested.

Existing artifact pointers and Campaign acceptance records remain in their owning stores. The new Project registry stores source identity and evidence references rather than duplicating those stores.

## FR-04 — Resolve canonical Project context

Extend the existing Project lookup and shared Cycle preparation path to resolve a typed **Project Context** for Project-aware agents/tools, containing:

- project ID and effective manifest version;
- authoritative external repository/ref, pinned development baseline, last confirmed integrated-upstream revision and any pending contribution;
- workspace locator and workspace permission mode;
- target capability profile;
- owner-approved quality/acceptance contract and applicable inherited-baseline policy;
- pinned development-instruction sources, technical profile version and inherited verification evidence;
- relevant Campaign ID (if one exists);
- implemented `cycle_id` and `run_id` once allocated, with legacy ECID aliases only where an explicit mapping exists;
- available prior accepted releases and Cycle evidence indexes.

The Project Context must be derived from authoritative records rather than untrusted free-text hints.

## FR-05 — Workspace provision and isolation

The Project Workspace Manager MUST integrate with the existing sandbox `WorkspaceStore` and its revision/lease boundaries. It adds managed development clones, external upstream bindings and Git-backed checkout/contribution management; product ownership stays external. Existing sandbox provision, path safety and stale-base protections must be reused or extended. It MUST:

- operate from configured roots, never hardcoded framework/sample paths;
- allocate separate workspaces for concurrent tasks/Cycles per policy;
- create/checkout the exact pinned source revision requested, preserving repository-relative paths and configured subdirectory roots;
- use repository-native build/test commands from the technical profile, with caches and runtime configuration outside committed product source by default;
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

The implemented `cycle_id` and `run_id` remain canonical API/persistence identifiers. The Project ID stays in the URL path for Cycle creation. Preserve existing `ArtifactRef` associations and vault retrieval, including current Project/Cycle/Run-scoped APIs. This SIP does not require moving evidence to `cycle_data/<project_id>/<ECID>/` or implementing a parallel `CycleDataStore`.

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
2. effective Project Manifest and technical profile;
3. relevant PRD/design baseline and change requests;
4. owner-approved quality contract, inherited baseline findings and latest candidate/integration verification;
5. pinned instruction sources/profile versions and any drift or owner-approved exceptions;
6. prior release/build artifact indexes;
7. unresolved known defects and decisions;
8. previous Cycle IDs and artifact references.

Carry this forward through durable, versioned **Project Snapshot / Handoff** metadata. Reuse artifact baseline references, existing Campaign accepted-tree/increment seeding and sandbox revision evidence; add the missing Project-level source/manifest mapping across standalone Cycles and Campaigns. Existing cross-Cycle memory may enrich context but MUST NOT be the only continuity source.

Every new Cycle record MUST explicitly pin its base source revision and target Project before dispatch. The server may resolve the current accepted revision for an existing caller that omits a new source-precondition option; explicit stale preconditions must be rejected. A failed or rewound Cycle MUST NOT change the accepted Project baseline by implication.

## FR-10 — Quality and outcome contracts for arbitrary applications

A Project MUST have a product-owner-approved quality contract independent of reference app fixtures. SquadOps may propose checks and acceptance thresholds; final product acceptance stays with the owner or an explicitly delegated authority. Extend the existing contract ingestion/binding, typed checks and verification evidence path; do not introduce a separate QA executor merely because the Project is independent.

Minimum contract shape:

- intended output/capability;
- executable verification (build, smoke, integration, acceptance or game-play tests);
- criteria for quality gate `PASS`, `FAIL`, or `UNVERIFIED`;
- test environment and evidence requirements;
- project-specific outcomes and performance constraints.

For a new web app, this may be API/E2E/lighthouse-style checks; for Godot/Roblox, gameplay checks from the game SIP. Absence of a benchmark-specific fixture MUST NOT prevent valid Project QA or execution.

Capture an inherited baseline before feature-source changes and compare the candidate against it using FR-20. Keep check outcome (`PASS`, `FAIL`, `UNVERIFIED`) separate from attribution (`inherited`, `introduced/regressed`, `resolved`, `unverified attribution`). An inherited failure remains a failure; it does not become PASS because the squad did not cause it. Existing defects do not automatically require repair outside the approved feature scope, and unknown checks are never silently waived.

Framework/team performance (duration, intervention, repair rate, cost) MUST be separately evaluated from application quality.

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

Credential material MUST reside in appropriate secret storage, never in Project Manifest or Cycle source evidence. Repository access/contribution rights do not transfer product ownership or authorize restructuring. Upstream writes, branch pushes, review requests and direct integration follow the product's configured permissions and governance.

## FR-14 — Eventing and auditability

Every meaningful Project transition MUST emit structured audit/event data with actor, Project ID, operation, relevant source revisions, timestamp, correlation/cycle ID when present, and result.

Events include logical registration/import, validation failure, workspace provision, Cycle linkage, source-promotion request/decision, archive and restore events. Source-promotion events must be distinguishable from existing artifact-baseline and Campaign promotion events.

Naming is illustrative pending alignment with existing SquadOps event conventions. No second message bus or event store is required.

## FR-15 — Failure and recovery semantics

Provisioning failures MUST leave the Project in an explicit recoverable state and avoid leaking orphan workspaces or partial credentials.

Workspace or repository outages MUST distinguish infrastructure unavailability from functional application failure. Failed/replayed Cycles MUST preserve historical artifacts and may create new source branches/workspaces; they MUST NOT erase previous Cycle history.

Promotion and remote-push operations MUST be idempotent or guarded by revision preconditions. Recoveries MUST follow existing Cycle rewind authority; Project Lifecycle cannot independently emit Pulses.

## FR-16 — Lifecycle disposal without data loss

Archiving prevents future ordinary Cycle starts but retains external source references, manifests, releases, QA artifacts, Cycle history and all unresolved/unintegrated work. Archiving or deleting a managed clone does not delete or archive the external product repository. Restoring runs validation before returning the Project to `READY`. Final deletion, including retention policies and destructive cleanup approvals, is left to a separate explicit policy.

## FR-17 — Game-development dependency integration

The Godot/Roblox Game Development SIP MUST:

- create/import games through Project Lifecycle;
- store engine files in Project source/workspaces, **not** in shared sample-app directories;
- associate game QA outputs with the Project/Cycle context;
- use the engine adapter only after Project context/workspace resolution;
- preserve the same Project across subsequent gameplay feature Campaigns/Cycles.

Its remote MacBook/Roblox Studio worker is an execution resource, not a Project or new agent.

## FR-18 — Extend the existing CLI and API client

Implement new commands in the existing `squadops.cli.commands.projects` group. Preserve `projects list/show` and hidden `ls/cat` aliases; use `show`, not a new canonical `inspect` spelling. Preserve `cycles create <project_id>` and `cycles list/show`, existing `campaigns` control commands, `artifacts` operations and artifact `baseline` commands.

New commands MUST reuse the shared `get_client`/`APIClient`, existing configuration and token resolution, login flow, `CLIError` exit-code mapping, standard output helpers, global `--format`/`--json`/`--quiet` behavior and paging helpers where relevant. Do not claim unsupported global flags or add a second CLI executable/config/auth stack. All source and lifecycle writes are authorized by the server or designated worker; the CLI must not register a Project by editing its own `config/projects.yaml`.

Mutation commands expose a caller-reusable `--idempotency-key`. Follow the existing Campaign CLI pattern for generated keys and retry disclosure, and include the key/operation correlation in JSON responses. Version-sensitive updates and source promotions require explicit expected-version/base preconditions. Readiness results distinguish completed registration from pending or failed provisioning.

Creating/registering a Project does not start a Cycle or incur execution work by implication. Existing `cycles create` and Campaign `start` retain their execution behavior. Local brief/manifest files are read by the CLI and transferred through defined upload/request contracts; a local file path is never treated as readable on the runtime server merely because it appears in JSON.

## FR-19 — Preserve external product independence

Registration MUST support an external repository with no SquadOps metadata files and no onboarding edits to its source tree. All required Project ID, manifest, build/test bindings and governance metadata must be storable under the SquadOps Project. Optional repository-side integration files are an authorized product change, never a prerequisite.

Managed cloning/importing MUST preserve repository history and layout. Use configurable product-defined roots, native commands and toolchains. Persist external-repository/ref bindings and development/integrated revisions, detect contributions made outside SquadOps, and deliver changes under the product's branch/review/integration policy. Support must be declared honestly for the target; a capability limitation must not silently trigger source relocation or restructuring.

The product's native build/test commands MUST remain usable with their documented toolchain without a running SquadOps installation. This is a portability requirement, not a claim that inherited defects have been repaired: recorded baseline failures and gaps remain visible under the owner's acceptance policy. Cleanup and archival retain unintegrated commits/patches/evidence and leave upstream intact. Definition-of-Done checks must demonstrate these properties on an existing external repository with a non-sample layout.

## FR-20 — Capture inherited quality before modifying source

Before feature implementation on an unfamiliar repository or a materially changed baseline, capture the agreed build/test verification against the pinned unmodified source in the managed execution environment. Preserve:

- repository/ref, exact commit and relevant dependency/lockfile state;
- effective technical profile, instruction sources and command/working-directory definitions;
- runtime/toolchain/environment identity needed to interpret or reproduce results;
- attempted checks, results, evidence and relevant execution limits;
- pre-existing failures, missing prerequisites and checks that remain UNVERIFIED.

The baseline must represent what was actually observed; do not patch source, suppress checks or relabel failures to make onboarding appear green. Product-owner-approved policy decides whether feature work may proceed with identified inherited failures or environment gaps. Record the allowed scope, remaining obligations and evidence; do not impose a blanket obligation to repair every inherited defect. A Project can be registered while baseline work is pending, but registration alone is not permission to claim successful verification or to ignore readiness constraints.

Evaluate candidate changes against relevant baseline evidence. Persist check outcomes independently of regression attribution and retain ambiguity when evidence cannot distinguish an inherited defect from a new regression. A candidate must meet the approved acceptance policy; unrelated inherited failures remain visible. Changes to source, toolchain, dependencies, commands or relevant instructions require appropriate refresh/revalidation, including after rebase/merge. The quality contract determines the affected verification scope; a prior PASS cannot silently migrate to a different source/environment.

## FR-21 — Respect instruction precedence and revalidate drift

The external owner/maintainer retains product intent and final acceptance authority; SquadOps roles act within explicit delegation. Effective instructions obey the precedence and conflict rules in Appendix B.5.1. Version the SquadOps technical profile and bind it to the source/instruction/build definitions it describes. Native repository tooling and maintainer policy cannot be silently replaced by stale external metadata.

Before feature-source changes, inspect/reconcile relevant upstream instruction, build/test, dependency and toolchain changes. Pin the resulting effective configuration in Cycle context and handoff metadata. Revalidate affected commands and inherited-baseline evidence before relying on them; repeat relevant checks at integration when source/configuration drift requires it. If an owner-policy decision is needed, stop the affected operation and report the conflict through existing governance. Routine profile refresh within delegated authority does not require an extra approval ceremony. Repository content cannot elevate runtime permissions.

## C.1 Non-functional requirements

**Compatibility.** Existing WarmBoot/reference application invocation and recorded history MUST remain accessible through a documented migration/alias mapping. Do not delete, rename, or move legacy data without a validated migration and rollback plan.

**Data integrity.** IDs immutable; preserve existing registry-based Project validation and add Project–Cycle foreign keys only after registry migration/backfill; manifest and source revision pinning explicit; promotion uses compare-and-swap/expected-base checks or equivalent controls.

**Isolation.** Workspaces and artifact paths derive from validated IDs/configuration, with directory/permissions boundaries enforced across projects.

**Idempotency.** Duplicate create/import/provision requests with the same idempotency key MUST not create duplicate Projects or silently overwrite source.

**Recoverability and portability.** SquadOps can reconstruct a development copy from external repository revision, out-of-repository Project metadata, tool profile and dependency configuration; evidence remains independently retrievable. The product remains usable outside SquadOps, with native source layout/build instructions and preserved upstream history.

**Performance.** Registry lookups and workspace provisioning MUST be measured. Configurable operational thresholds SHOULD be defined after baseline measurement instead of inventing universal timings.

**Extensibility.** Project types/targets (web, API, Godot, Roblox, other) are profile/adapters, not core lifecycle special cases.

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
| `PUT /api/v1/projects/{project_id}` | Version-preconditioned metadata/manifest update; `projects update`. |
| `POST /api/v1/projects/{project_id}/validate` | Validate readiness; `projects validate`. |
| `POST /api/v1/projects/{project_id}/archive` and `/restore` | Govern reversible lifecycle transitions. |
| `GET /api/v1/projects/{project_id}/history` | Project lifecycle/source/evidence history; `projects history`. |
| `/api/v1/projects/{project_id}/workspaces` | Provision/read/release through the authorized repository/workspace service, integrating sandbox revisions. |
| `/api/v1/projects/{project_id}/source-baseline` and its proposal/promotion resources | Read/propose/promote accepted Git source with expected-base and evidence bindings. Distinct from existing artifact `/baseline`. |

Every mutation carries an idempotency key and actor/correlation data. Responses return `project_id`, effective manifest/version, operation correlation and explicit readiness/status; secrets are excluded. Long provisioning uses the existing 202 convention with a queryable operation reference; Project `show` exposes readiness.

Illustrative **new** registration request (the source destination/locator must be resolved and authorized before readiness):

```json
{
  "idempotency_key": "create-space-adventure-001",
  "name": "Space Adventure",
  "description": "A 3D exploration game built in Godot",
  "origin": {"mode": "new"},
  "technical_profile": {"type": "game", "target": "godot"},
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

The existing `projects show` reports effective manifest, source baseline, operation state and readiness. Final schemas/options for workspace and source-promotion subcommands must be specified before implementation, using the source-baseline distinction above. Any optional convenience aliases are additive; `project`, `inspect`, `cycle start`, `--objective` and `--campaign` do not become replacement spellings for existing contracts.

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
- A stale manifest/source precondition, archived Project or unsafe repository location fails before work is dispatched; denial does not allocate a running Cycle.
- Both standalone and Campaign-launched Cycles receive the same pinned Project source/quality context while retaining their existing launch authority.
- Tests enter at the CLI/API wiring seams and assert observable Project/source state, request/response compatibility and error behavior; command names alone are not sufficient proof.

# Appendix E — Implementation and acceptance detail

## E.1 Reconciled implementation plan

Appendix A.1 and Appendix F.5 record completed source inspection at the pinned revision. Before coding, compare the implementation branch with that pin and report relevant changes; do not repeat the original assumption that all foundations are unimplemented.

| Workstream | Reuse | Add or change |
|---|---|---|
| Project CLI/API | Existing `projects.py`, shared client/auth/output, current GET routes/mapping | New lifecycle commands, typed requests/responses, scopes, idempotent operations and version preconditions. |
| Registry | `ProjectRegistryPort`, existing Project identity/fields, provider factory/runtime wiring | Writable adapter/service, migration, YAML seed/cutover, all-reader consistency and lifecycle metadata. |
| Cycle integration | Existing plural `cycles create`, CRP builder, PRD upload, `prepare_cycle()` and current Cycle/Run persistence | Pinned Project source/quality context, eligibility checks and explicit schema/persistence additions. |
| Source/workspaces | Sandbox `WorkspaceStore`, stale-base checks, revisions, leases, path containment and artifact capture; existing `VersionControlPort`/Git adapter | External source locator, managed clone/import/attach/checkout, product-defined contribution policy and guarded candidate/integration tracking. |
| Continuity | Artifact baselines, Campaign accepted trees and increment seeding, existing memory as enrichment | Durable Project handoff and mapping among Git commit, sandbox revision, Campaign tree and artifact evidence. |
| Campaigns | Existing CLI/API, policies, control log, launch intents and promotion gates | Project readiness/archive/source integration at shared launch/preparation seams; no new Campaign FSM. |
| Evidence/QA | `ArtifactVaultPort`, current artifact APIs, contract binding and typed verification | Project lifecycle/handoff evidence types and profile integration for arbitrary targets. |

Source inspection does not verify the user's running deployment, migrations, credentials or remote workers. The implementation plan must validate those separately when rollout requires them, and resolve remaining adapter/schema choices from Appendix F.4 before adding their surfaces.

## E.2 Reconcile the earlier Cycle Data SIP with current storage

The earlier draft's persistent identity and separation-of-source-from-evidence goals remain useful. Its names/layout must not overwrite the implementation facts:

- Current Project lookup is YAML-backed through `ProjectRegistryPort`; writable persistent Projects are new work.
- Current Cycle persistence is `cycle_registry` with `project_id`; preserve its `cycle_id`/Run records, not an assumed `execution_cycle` table.
- Current artifact access is `ArtifactVaultPort` plus its filesystem adapter and Project/Cycle/Run references. Preserve IDs, baseline pointers and historical content retrieval.
- Current sandbox `WorkspaceStore` already supplies live workspaces, revisions and leases. Extend/integrate its boundaries for Git-backed Project source.
- `CycleDataStore` and the old per-ECID layout are not prerequisites for this lifecycle increment. If later implemented, specify an adapter/migration preserving current contracts rather than adding another system of record.

Project repository management remains separate from evidence storage: the external Git repository tracks authoritative product source; the vault and telemetry services retain verification and execution evidence. Source-promotion records connect them.

## E.3 Lifecycle use cases

### UC-A — Existing application (primary acceptance path)

```text
User supplies external product repo, retaining its layout and ownership
  -> register Project ID + out-of-repository development metadata
  -> clone/import for development or attach under approved isolation policy
  -> resolve owner delegation + native instructions; pin upstream/development/profile revisions
  -> run agreed build/tests on unmodified source and record inherited defects/UNVERIFIED checks
  -> Cycle adds a feature in isolated workspace without onboarding restructuring
  -> QA + approved candidate; preserve pending work for subsequent Cycles
  -> authorized branch/review request/patch delivery under product policy
  -> confirm upstream integration and record the actual resulting commit
  -> external developer advances the product before the next Cycle
  -> reconcile source/instruction drift, refresh affected baseline/profile evidence
  -> deliver a second scoped feature against the same Project and external repository
```

### UC-B — New independent application (secondary proof)

```text
PRD received
  -> Project created/registered
  -> product-approved external Git source initialized with a product-appropriate layout
  -> SquadOps Project metadata/manifest and managed development workspace established
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

### UC-D — Independent game

```text
New Godot or Roblox game intent
  -> create ordinary Project
  -> game-specific target profile resolved
  -> engine adapter works against isolated Project workspace
  -> (Roblox) remote Studio worker validates as required
  -> game quality evidence linked to Project/Cycle
  -> later Campaigns evolve same Project
```

## E.4 Suggested delivery increments

These are implementation slices, not fixed Campaign stages or Cycle counts.

1. **Existing-product registration and authority:** add the writable registry cutover and the minimum existing-CLI enrollment flow; record external repository/ref, owner delegation and out-of-repository metadata while preserving list/show and historical IDs.
2. **Repository-native discovery and inherited baseline:** managed clone/pinned checkout, existing workspace/lease integration, native instruction/profile resolution, agreed baseline build/tests and honest readiness/defect reporting.
3. **First scoped feature through the shared Cycle path:** typed Project context and source preconditions, implementation/verification against inherited evidence, approved candidate and the product's normal contribution/integration process.
4. **Second feature after an outside contribution:** detect source and instruction drift, reconcile with policy, refresh affected baseline checks, and continue through the same Project/Cycle or existing Campaign authority. Demonstrate durable handoff and independent product usability.
5. **Complete lifecycle and rollout:** richer update/history/archive/restore, concurrency/conflict recovery, validated provider rollback and existing-reference/Campaign regression proof. Any mutation enabled earlier must already meet its authorization/idempotency requirements.
6. **Additional onboarding modes and targets:** greenfield external repository creation, direct checkout attachment and game/other technical profiles build on the proven external-product path. These remain in scope, but are not prerequisites for the first proof. Readiness must explicitly report any operation/profile not yet supported.

## E.5 Migration and rollback

- Use the existing migration runner and additive schema changes. Import current YAML entries and reconcile persisted Cycle/Campaign project IDs before enforcing foreign keys; retain unknown IDs for explicit reconciliation rather than deleting history.
- Preserve existing benchmark IDs/tags/PRD resolution. They are already Projects; add lifecycle defaults and source mapping without re-registration under new IDs or forced repository relocation.
- Switch all API, Campaign and worker reads/writes to one selected Project provider. Preserve the config provider as an explicit compatibility/read-only mode or seed source, not a concurrent authority.
- Preserve `projects list/show`, `cycles create`, global output behavior, auth/config, existing artifact-baseline commands and current resource paths; add fields/options compatibly.
- Keep existing vault and sandbox layouts in place. New external source bindings and development clones do not relocate old artifacts, alter artifact IDs or drop Run lineage.
- Add Project eligibility/source context to both standalone and Campaign launch paths; verify existing reference execution and Campaign acceptance behavior for parity.
- Feature-gate lifecycle writes and provider selection where rollout requires it. On rollback, retain new Project rows, source repositories, manifests and evidence. Do not switch to YAML-only reads if that would make post-cutover Projects disappear; provide an explicit read-compatible rollback path.
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
- [ ] Project schema/manifest resolution is versioned and validated.

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
- [ ] `import` and `attach` preserve repository provenance and safety policies.
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
- [ ] Existing Cycle/Pulse/Surge authority and rewind semantics remain unchanged.

### Generalized quality and instruction continuity

- [ ] The agreed build/test baseline is recorded at the pinned unmodified source revision before feature-source changes, including effective commands/profile, environment, inherited failures and UNVERIFIED checks.
- [ ] Candidate check outcomes are separate from regression attribution; inherited FAIL remains FAIL, unknown attribution remains explicit, and proceeding with inherited defects follows owner-approved policy.
- [ ] Applicable owner/maintainer policy and repository-native tooling constrain SquadOps profiles; conflicting or stale metadata cannot silently win.
- [ ] Source, relevant instruction, build/test, dependency or toolchain drift invalidates affected profile/baseline evidence until reconciled and revalidated.
- [ ] Both standalone and Campaign-launched work receive pinned source/profile/instruction and baseline references through the shared preparation path.
- [ ] A non-sample Project can define and execute its owner-approved quality contract.
- [ ] Unknown/unexecuted checks are recorded as UNVERIFIED, not PASS.
- [ ] Product outcomes and inherited/regression quality are distinct from squad execution measurements.

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
- [ ] Prior Project/Cycle/Run artifacts and any legacy ECID aliases remain readable through existing IDs and documented mappings.
- [ ] Primary proof: an unfamiliar existing external repository with a supported non-sample layout registers without onboarding source edits and receives a pinned inherited build/test baseline.
- [ ] A first scoped feature completes through the existing Cycle path and the product's normal contribution/integration policy, with QA and candidate/integrated revision evidence.
- [ ] An outside developer advances the repository between Cycles; the squad detects and reconciles relevant source/instruction drift before delivering a second feature through the same Project.
- [ ] The primary proof records any inherited failures and UNVERIFIED checks truthfully; it does not rely on an artificially pristine fixture or claim inherited defects were introduced by the squad.
- [ ] The external repository remains usable with its native tooling after the SquadOps engagement is archived; pending work/handoff evidence is preserved.
- [ ] Secondary proof: a new product, including a game target when its adapter is supported, can be created at an external destination and evolved through the same lifecycle.
- [ ] Archive/restore is reversible without data loss.
- [ ] API/CLI authorizations, idempotency, failure and recovery tests pass.

**Primary end-to-end success demonstration:** A product maintainer supplies an unfamiliar existing external repository and a scoped feature request. SquadOps registers it without source-tree changes, resolves the owner's delegation and repository-native instructions, pins an unmodified build/test baseline, and delivers a verified feature through the product's normal contribution process. Another developer then advances the source or development instructions. A later Cycle detects/reconciles that drift, refreshes affected profile/baseline evidence and delivers a second feature through the same SquadOps Project. Candidate acceptance, inherited defects, regression findings and confirmed upstream integration remain distinct. Product source/builds remain independently usable and `group_run` compatibility is preserved. Greenfield product creation is an additional proof, not a substitute for this one.

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
  Manifest: manifest-v3
  External Repository: <product-owned-repository-locator>
  Target Ref: <product-defined-integration-ref>
  Owner Delegation/Acceptance Policy: <versioned-policy-ref>
  Technical Profile / Instructions: <profile-version-and-instruction-digests>
  Inherited Verification: <baseline-evidence-artifact-id>
  Development Baseline: abc123
  Confirmed Integrated Revision: abc123
  Campaign: campaign-enemy-ai [optional]
    Cycle: cyc_example0042
      Base Revision: abc123
      Delivered Revision: def456
      Run: run_example0001
      QA: <candidate-verification-artifact-id>
      Regression Attribution: <baseline-comparison-evidence-ref>
      Tested Configuration: <pinned-source-profile-environment-binding>
      Workspace Revision: <sandbox-content-hash>
      Campaign Accepted Tree: <accepted-tree-hash> [if applicable]
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
| SIP-0102 | **Implemented sandbox foundation**: Cycle workspace revision, path and lease boundaries; integrate external product source through managed Git clones. |
| SIP-0109 | **Implemented Campaign foundation**: control log, launch authority, accepted-tree continuity and promotion; preserve and map to Project source. |
| `SIP_CYCLE_DATA_STORE.md` | Earlier design reference for persistent identity and evidence separation. Reconcile with current YAML registry, `cycle_registry` and `ArtifactVaultPort`; its proposed table/ECID layout is not treated as deployed. |
| `IDEA_Cycle_Orchestrator_Pulses_and_Surges.md` | Canonical coordination semantics; Project Lifecycle must not alter authority or rewind rules. |
| `IDEA_Cycle_and_Pulse_Execution_Model.md` | Earlier non-normative conceptual exploration. Where terminology differs, use the later aligned Orchestrator/Pulse/Surge design. |
| `Git workflow.txt` | Git traceability and stable `main`; extend for Project-owned repositories without assuming framework-specific WarmBoot branch conventions apply to all products. |
| `Doc traceability.txt` / PID proposal | Reuse traceability for product features and tests; Project identity is not a PID. |
| `SIP-XXX-Game-Development-Godot-Roblox-Remote-Execution.md` | **Downstream consumer**: engine adapters operate on independent Project workspaces, not sample-app locations. |
| Existing Campaign implementation | Optional for standalone Project work; reuse current policy, launcher, accepted-tree records and shared Cycle preparation. |

## F.4 Remaining design decisions and validation

- Define the new transactional Project schema/write-service contract, provider configuration and YAML seed/cutover/rollback procedure. Current registry authority and lookup operations are already established in Appendix A.1.
- Define exactly how Project-owned Git checkout and verified source capture integrate with the existing sandbox live tree, revisions, leases and binary/asset handling; do not duplicate an independent workspace authority.
- Specify typed Cycle source-context/precondition fields, their persistence and config-hash scope, and their use by both `cycle_request_body()` and Campaign launch requests. The public API currently forbids unknown top-level fields.
- Define source-baseline read/propose/promote DTOs/subcommands and map Git commits to existing artifact baselines, Campaign accepted trees and sandbox revision identities.
- Define how Campaign promotion, Project source promotion and overlapping Campaigns reconcile without changing accepted state by implication or bypassing existing approval/control logs.
- Choose safe default permissions for external repository attachment and define server/remote-worker path resolution; a client-local directory is not automatically an authorized runtime path.
- Specify registration reservation, brief upload, finalization and recovery as an idempotent operation, including queryable pending/failure results.
- Define archive handling for active Campaigns/Cycles, required source/manifest evidence for restoration, and project-level quality history as acceptance expectations evolve.
- Define inherited-baseline evidence and candidate-comparison records, preserving check status independently of attribution, environment gaps and owner-authorized continuation policy.
- Define instruction/profile version bindings, relevant-drift detection and affected-operation conflict handling through the existing governance/event paths; do not create a parallel approval or orchestration system.
- Confirm new target-specific tooling and asset requirements independently; current source inspection does not prove game-engine support or running-deployment readiness.

**Scope note:** `SIP_CYCLE_DATA_STORE.md` is a proposal dating from 2025-11-26. Revision 2 reconciled it with freshly pulled source; Revision 3 clarified external product ownership. Revision 4 retains that evidence and adds owner authority, inherited quality baselines, instruction precedence/drift and an existing-product-first acceptance path. Proposed lifecycle writes and new development contracts are not claimed as implemented. The pinned source inspection is not a fresh deployment verification.

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

# Appendix G — Revision history

| Document revision | Date | Change |
|---|---|---|
| Original draft | 2026-10-16 | Independent Project identity, workspaces, governance and cross-Cycle lifecycle proposal based on supplied design sources. |
| 2 | 2026-10-17 | Reconciles against freshly pulled `main`: requires existing CLI/API reuse; separates existing vs new operations; specifies YAML-to-writable registry cutover; preserves ArtifactVault, sandbox and Campaign authority; distinguishes source/artifact/tree baselines; updates delivery and acceptance criteria. |
| 3 | 2026-10-17 | Clarifies SquadOps as a development team for independently owned products: external authoritative source, out-of-repository Project metadata, managed clones/worktrees, preserved repository-native layout/tooling, external-contribution reconciliation and separate candidate/integrated revision tracking. |
| 4 | 2026-10-17 | Keeps external owner authority explicit; adds inherited build/test baselines and separate regression attribution; defines instruction precedence/profile drift; makes enhancement of an existing external product across outside contributions the primary proof; separates the directional core from detailed implementation appendices. |
