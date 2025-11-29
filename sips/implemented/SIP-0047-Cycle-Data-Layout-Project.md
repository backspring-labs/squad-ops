---
sip_uid: 01KB4B74MN5BHXZH42ZRPEYVAG
sip_number: 47
title: Cycle Data Layout, Project Registry, and CycleDataStore Contract for Execution
  Cycles
status: implemented
author: Jason Ladd
approver: Jason Ladd
created_at: '2025-11-28T04:23:35Z'
updated_at: '2025-11-29T10:14:54.117935Z'
original_filename: SIP_CYCLE_DATA_STORE.md
---
# Cycle Data Layout, Project Registry, and `CycleDataStore` Contract

- **Title:** Cycle Data Layout, Project Registry, and `CycleDataStore` Contract for Execution Cycles  
- **Status:** Accepted  
- **Owner:** Jason (product/architecture), Max (orchestrator), Neo (implementation), EVE (validation)  
- **Target Release:** Point release (0.x → 0.(x+1)) – first major refactor of run artifacts  
- **Created:** 2025-11-26  

---

## 1. Summary

This SIP defines:

1. A **canonical `cycle_data/` filesystem layout** for artifacts and telemetry produced during an Execution Cycle (ECID).  
2. A **root `projects` database table** to register long-lived projects and bind them to cycle data.  
3. A **`CycleDataStore` contract** (behavioral interface) for reading and writing cycle artifacts, without prescribing a specific implementation.

The goal is to:

- Move away from ad-hoc, WarmBoot-specific output paths.  
- Establish a reusable substrate for *any* project (WarmBoot, example apps, future user projects).  
- Support future orchestration features (phases, pulses, rollback, SOC views, Prefect, Langfuse) without locking in premature details.

This is intentionally **requirements-driven**, not code-driven. Concrete class definitions and wiring will be handled in Cursor and implementation PRs.

---

## 2. Motivation & Background

### 2.1 Current Gaps

- WarmBoot and other experiments persist artifacts into ad-hoc locations.  
- There is no single, documented relationship between:
  - **Project** → **Execution Cycle (ECID)** → **Artifacts / Telemetry**.  
- Execution Cycle data is not clearly separated from:
  - Repo source code.  
  - Ephemeral container scratch space.  
- There is no formal **Project registry**:
  - "What projects exist?"  
  - "Which ECIDs belong to which project?"  
  - "Where is the canonical place to look for that?"

### 2.2 Why Now

- The system is evolving from a WarmBoot-only self-test into:
  - A framework that can run *multiple* projects (example apps + future user apps).  
- Larger Execution Cycles (multi-hour) require:
  - Durable, inspectable cycle substrates.  
  - Clear mapping between project, EC, and artifacts.  
- Introducing Prefect, Langfuse, and workspace-style abstractions will be much easier if **cycle_data** and **project registry** are first-class concepts.

---

## 3. Concepts & Definitions

- **Project**  
  A long-lived unit of work (e.g., `warmboot_selftest`, `personal_fitness`, `financial_fitness`). Projects may correspond to:
  - Framework self-tests  
  - Example applications  
  - User-defined applications (later)

- **Execution Cycle (ECID)**  
  A single, end-to-end attempt to move a project forward.  
  The ECID already exists in the system (e.g., `EC-2025-11-27-0001`).

- **Cycle Data**  
  All persistent artifacts, metadata, and telemetry produced during a specific `(project_id, ECID)` pair.

- **Artifact**  
  Any meaningful file produced during a cycle (plans, PRDs, designs, code diffs, test reports, retros, etc.).

- **Telemetry**  
  Structured event streams (e.g., JSON lines) representing agent and orchestrator actions, decisions, and measurements.

- **`CycleDataStore`**  
  A logical interface/contract for interacting with cycle data. It owns:
  - Path resolution into `cycle_data/`.  
  - Simple read/write/append behaviors.  
  - A consistent abstraction that can later be backed by different storage implementations (local FS, S3, etc.).

---

## 4. Project Registry (Database)

### 4.1 Goals

Introduce a **root `projects` table** to:

- Register all known projects.  
- Provide a stable, queryable mapping from `project_id` to:
  - Human-readable name and description.  
  - Flags relevant to orchestration and analytics (e.g., internal vs user).  
- Provide a **foreign-key anchor** for ECIDs and cycle data.

### 4.2 `projects` Table – Required Fields

The `projects` table must minimally support:

- `project_id` (string, primary key)  
  - Compact identifier, used in `cycle_data/` paths.  
  - Examples: `warmboot_selftest`, `personal_fitness`, `financial_fitness`.

- `name` (string)  
  - Human-facing name.  
  - Example: "WarmBoot Self-Test", "Personal Fitness Tracker".

- `description` (string or text)  
  - Short description of the project's purpose.

- `is_internal` (boolean)  
  - `true` for framework-owned projects (WarmBoot, official examples).  
  - `false` for user-defined projects (future capability).

- `created_at` (timestamp)  
- `updated_at` (timestamp)

### 4.3 Relationships to Existing Tables

- **Execution Cycles**  
  - The existing `execution_cycle` table must be extended (if not already) to include a `project_id` column.  
  - Each ECID row must belong to exactly one project.  
  - The `(project_id, ecid)` pair is the canonical identity for a given cycle's data.

- **Tasks / Task Logs**  
  - No immediate schema changes required for this SIP, but downstream tasks can be filtered by `project_id` via join on `execution_cycle`.

### 4.4 Requirements

1. A project **must exist** in the `projects` table before it can be used to start an Execution Cycle.  
2. WarmBoot must be registered as a project (e.g., `project_id = "warmboot_selftest"`).  
3. Example applications (e.g., personal and financial fitness apps) must register their own `project_id` values when they are introduced.  
4. The orchestrator must resolve the `project_id` for each ECID and provide it to the `CycleDataStore`.

---

## 5. Canonical `cycle_data` Layout

### 5.1 Root Structure

At the repo (or ops base) root, a `cycle_data` directory is reserved for cycle outputs:

```text
cycle_data/
  <project_id>/
    <ECID>/
      meta/
      shared/
      agents/
      artifacts/
      tests/
      telemetry/
```

Where:

- `<project_id>` comes from the `projects` table.  
- `<ECID>` comes from the execution_cycle entry.

### 5.2 Area Semantics

- `meta/`  
  - Orchestrator-owned metadata for the cycle.  
  - Examples:
    - `cycle_manifest.json`  
    - `summary.md` (optional human-friendly summary)

- `shared/`  
  - Artifacts not tied to a specific agent.  
  - Examples: shared plan, consolidated PRD, shared architecture notes.

- `agents/`  
  - Agent-specific "persistent whiteboard" space.  
  - Each agent can have its own subdirectory if needed.

- `artifacts/`  
  - Deliverables produced in the cycle.  
  - PRDs, designs, code patches, release notes, etc.

- `tests/`  
  - Test plans and test results.  
  - QA-focused outputs: strategies, reports, coverage.

- `telemetry/`  
  - Structured logs and event streams for the cycle.  
  - JSONL event files, potentially agent-specific streams.

### 5.3 Requirements

1. For any `(project_id, ECID)` pair, the orchestrator must treat `cycle_data/<project_id>/<ECID>/` as the **single canonical root** for artifacts and telemetry for that cycle.  
2. Orchestrator is responsible for creating the directory tree when a new EC starts.  
3. The path mapping must **not** depend on container-local paths; it must be resolvable from:
   - `cycle_data_root`  
   - `project_id`  
   - `ECID`.

4. Existing WarmBoot output paths should be migrated or deprecated in favor of this structure.

---

## 6. `CycleDataStore` Contract (Behavioral)

> Note: This section defines **behavior**, not a concrete class declaration. Exact method signatures and types will be defined during implementation.

### 6.1 Responsibilities

`CycleDataStore` must:

- Resolve and create the directory structure for `cycle_data/<project_id>/<ECID>/...`.  
- Provide simple operations for:
  - Writing text artifacts.  
  - Writing binary artifacts.  
  - Reading existing artifacts.  
  - Appending telemetry events as JSON lines.  
- Be testable in isolation (e.g., by pointing to a temporary directory).  
- Avoid hard-coding Repo root; it must rely on configuration.

### 6.2 Core Behaviors (Required)

`CycleDataStore` must support at least:

1. **Initialization / Context**

   - Inputs:
     - `cycle_data_root` (base path from configuration)  
     - `project_id` (validated against `projects` table)  
     - `ecid` (existing execution_cycle row)
   - Behavior:
     - Prepares an internal reference to `cycle_data/<project_id>/<ECID>/`.  
     - Ensures the directory tree is created on first write.

2. **Write Text Artifact**

   - Inputs:
     - Logical area (one of: shared, agents, artifacts, tests, telemetry)  
     - Relative path within that area (e.g. `plan.md`, `prd/v1_prd.md`)  
     - Optional agent name (for agent-specific areas)  
     - Content string
   - Behavior:
     - Writes UTF-8 text to the appropriate location.  
     - Creates intermediate directories as needed.  
     - Overwrites existing files by default (idempotent behavior is acceptable for v1).

3. **Write Binary Artifact**

   - Inputs similar to text, but with binary data.  
   - Behavior:
     - Writes raw bytes to disk.  
     - Used for non-text outputs (e.g., compressed bundles, images, etc.).

4. **Read Text / Binary Artifact**

   - Inputs mirror the write operations.  
   - Behavior:
     - Returns content if the file exists.  
     - Returns a clear "missing" signal (e.g., `None` or equivalent) if it does not.

5. **Append Telemetry Event**

   - Inputs:
     - Event as a dictionary / structured object.  
     - Optional agent name.  
   - Behavior:
     - Renders the event as a single JSON line.  
     - Appends it to:
       - A shared telemetry stream for the cycle, and/or  
       - An agent-specific stream, depending on configuration.  
     - Does not require callers to manage file handles.

### 6.3 Non-Goals (for v1)

- No requirement for concurrency-safe file locking beyond typical single-node usage.  
- No requirement for remote storage or object store support (but design must not make this harder later).  
- No requirement for phases/pulses in filenames or folders; those will be layered on later.

---

## 7. Integration: Orchestrator & WarmBoot

### 7.1 Orchestrator

The orchestrator must:

1. Resolve:
   - `project_id` (from `projects` table or configuration)  
   - `ECID` (existing execution_cycle entry)

2. Instantiate `CycleDataStore` (or equivalent) using:
   - `cycle_data_root` from unified config  
   - `project_id`  
   - `ECID`

3. During the cycle:
   - Persist:
     - Cycle manifest (metadata) into `meta/`.  
     - Shared artifacts (plans, PRDs, designs) into `shared/` or `artifacts/`.  
     - Test artifacts into `tests/`.  
   - Append key lifecycle telemetry events (e.g. EC start, EC end, failure conditions).

### 7.2 WarmBoot Migration

WarmBoot must be updated so that:

- It is registered in the `projects` table with a stable `project_id` (e.g., `warmboot_selftest`).  
- Each WarmBoot Execution Cycle writes all new outputs into:

  ```text
  cycle_data/warmboot_selftest/<ECID>/
  ```

- Any existing WarmBoot-specific output paths are declared **legacy** and may be:
  - Left as historical data, or  
  - Migrated once, then ignored going forward.

---

## 8. Configuration Requirements

- There must be a unified configuration entry for **cycle data root**, with:
  - A default value such as `<repo_root>/cycle_data`.  
  - Optional override via environment variable (e.g., `SQUADOPS_CYCLE_DATA_ROOT`) to support:
    - External volumes  
    - Ops base directories  
    - Cloud hosts

- Orchestrator and any other `CycleDataStore` consumers must resolve `cycle_data_root` via this configuration, not by hardcoding paths.

---

## 9. Testing Requirements

### 9.1 Unit-Level

- `CycleDataStore` behavior must be validated by unit tests that:
  - Use a temporary directory as `cycle_data_root`.  
  - Verify that writing and then reading text/binary artifacts works as expected.  
  - Verify that telemetry events are appended as valid JSON lines.  
  - Verify correct path derivation from `project_id` and `ECID`.

### 9.2 Integration-Level

- An integration test (or scenario) must simulate:
  - Creating a project entry.  
  - Creating an execution_cycle linked to that project.  
  - Running a minimal orchestrated cycle that:
    - Writes a manifest.  
    - Writes at least one shared artifact.  
    - Writes at least one test artifact.  
    - Appends telemetry.  

- The test must assert the presence and structure of:

  ```text
  cycle_data/<project_id>/<ECID>/
  ```

### 9.3 WarmBoot

- A WarmBoot self-test path must be updated so that:
  - It uses a registered `project_id`.  
  - It writes to the new `cycle_data` layout.  
  - The test can verify the existence of `cycle_data/warmboot_selftest/<ECID>/...` after a run.

---

## 10. Migration & Backward Compatibility

- New runs after this SIP is implemented must use the `cycle_data` layout and `projects` table.  
- Existing legacy WarmBoot outputs:
  - Are not required to be migrated automatically.  
  - May remain as historical artifacts.  
  - Should be documented as legacy in any relevant developer docs.

- No changes are required to:
  - Agent container scratch patterns (they remain ephemeral).  
  - External API shapes (e.g., task API) for this SIP.

---

## 11. Acceptance Criteria

This SIP is considered complete when:

1. The `projects` table exists and is used to register at least:
   - WarmBoot  
   - One example application (even if stubbed).

2. The `execution_cycle` table can associate each ECID with a `project_id`.

3. A `cycle_data/<project_id>/<ECID>/...` structure is created for new runs.

4. A `CycleDataStore`-like abstraction is in place and used by the orchestrator to:
   - Write a cycle manifest.  
   - Write at least one shared artifact.  
   - Append at least one telemetry event.

5. WarmBoot's happy-path run writes its artifacts into:
   - `cycle_data/warmboot_selftest/<ECID>/...`.

6. Unit and integration tests validate the structure and basic behaviors described above.

At that point, Execution Cycles will have a **durable, inspectable, and project-anchored cycle_data substrate**, and WarmBoot will be fully migrated to this model, unblocking future work on phases, pulses, rollback, and observability.

