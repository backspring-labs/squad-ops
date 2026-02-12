# SIP Proposal — 0.9.4: Project-Scoped PRD/PCR Registry + CLI Workflow

**Status:** Proposed  
**Target Release:** 0.9.4  
**Evolves:** 0.9.3 Project/Cycle/Run API foundation (SIP-0064)  
**Intent:** Lock down where PRDs/PCRs live relative to Projects, make provenance queryable (“what ran?”), and ship a CLI workflow that can author/register/version PRDs and PCRs and submit Cycles/Runs end-to-end (no WarmBoot).

---

## Goals

- Define PRD and PCR as project-scoped, versioned entities with immutable content refs.
- Ensure Cycles and Runs can always resolve:
  - PCR version used
  - PRD version referenced (if any)
  - resolved overrides/config snapshot hash/ref
  - squad profile snapshot ref
- Provide a CLI that supports a simple, repeatable workflow:
  - register project artifacts (PRD/PCR)
  - set active PRD/PCR (optional)
  - submit cycles and trigger runs
  - inspect status, gates, artifacts
- Keep provider-agnostic boundaries intact:
  - artifact storage behind ArtifactVaultPort
  - persistence behind registry ports
  - orchestration behind FlowExecutionPort

---

## Non-goals

- Building a full “PRD authoring system” UI.
- Implementing managed identity provider packs (Cognito/Entra/GCP).
- Adding new orchestration semantics beyond what 0.9.3 already defines.

---

## Domain Model (Normative)

- **Project (Entity):** top-level namespace
- **PRD (Entity, versioned):**
  - `prd_id`, `project_id`, `version`, `status`, `artifact_ref`, `created_at`
- **PCR (Entity, versioned):**
  - `pcr_id`, `project_id`, `version`, `prd_ref` (nullable), `artifact_ref`, `created_at`
  - PCR defines execution defaults + allowed overrides + declared TaskFlowPolicy refs/shape + expected artifact types (as applicable)
- **Cycle (Entity):**
  - `cycle_id`, `project_id`, `pcr_id@version` (immutable ref), `status`, `created_at`
- **Run (Entity):**
  - `run_id`, `cycle_id`, `status`, `started_at`, `finished_at`, `initiated_by`/`trigger`
  - Run must reference:
    - `squad_profile_snapshot_ref`
    - `resolved_config_ref` (hash/ref)
    - `artifact_manifest_ref` (or produced artifact refs)
- **ArtifactRef (Value Object):** immutable (`id`/`hash`/metadata + locator/handle)

---

## Persistence Model (Normative)

- PRD and PCR records MUST be stored in the DB as project-scoped, versioned rows.
- The content bodies for PRDs and PCRs SHOULD be stored in the Artifact Vault and referenced by ArtifactRef in the DB.
- PCR MAY reference a PRD version (`prd_ref`), but MUST NOT embed PRD content inline.
- Cycle MUST reference an immutable PCR version (`pcr_id` + `version`).
- Runs MUST be able to resolve PCR and PRD lineage through Cycle→PCR (and PCR→PRD when present).

---

## Ports (Hex) (Normative)

- **ProjectRegistryPort:** list/get (create optional if stance is config-seeded)
- **PRDRegistryPort:**
  - register PRD (from ArtifactRef + metadata)
  - list/get versions
  - set active version (optional)
- **PCRRegistryPort:**
  - register PCR (from ArtifactRef + metadata)
  - list/get versions
  - set active version (optional)
  - validate PCR references (project ownership, referenced PRD version)
- **CycleRegistryPort:** create cycle (from PCR version), query, lifecycle updates
- **RunRegistryPort** (or part of CycleRegistryPort): start/stop runs, query runs, record status
- **ArtifactVaultPort:** ingest/retrieve/list
- **FlowExecutionPort:** interpret declared policy, execute run, report events

---

## API Additions (0.9.4)

(Keep SIP-0064 endpoints; add these minimal registry endpoints.)

### PRDs

- `POST /projects/{project_id}/prds`  
  registers a PRD version (body includes `artifact_ref` and metadata; content is already ingested)
- `GET /projects/{project_id}/prds`  
  list PRDs and versions (optionally filter by status)
- `GET /projects/{project_id}/prds/{prd_id}`  
  list versions; allow query param `?version=`
- `POST /projects/{project_id}/prds/{prd_id}/active`  
  set active version (optional but recommended for ergonomics)

### PCRs

- `POST /projects/{project_id}/pcrs`
- `GET /projects/{project_id}/pcrs`
- `GET /projects/{project_id}/pcrs/{pcr_id}?version=`
- `POST /projects/{project_id}/pcrs/{pcr_id}/active` (optional)

### Cycles and Runs

- `POST /projects/{project_id}/cycles`  
  requires `pcr_id` + (optional version; resolution rule: explicit version wins, else active version, else latest)
- `POST /projects/{project_id}/cycles/{cycle_id}/runs`  
  starts a run
- `GET /projects/{project_id}/cycles/{cycle_id}/runs`  
  list runs for a cycle

---

## Resolution rules (Normative)

- If caller supplies PCR version, use it.
- Else if an “active” PCR version is set, use it.
- Else use latest version.
- The resolved version MUST be persisted onto the Cycle record.
- A Run MUST store the `resolved_config_ref` and `squad_profile_snapshot_ref` used.

---

## CLI Requirements (Normative)

The CLI must support these workflows end-to-end.

### Project discovery

- `squadops project list`
- `squadops project show <project_id>`

### Artifact ingestion (vault)

- `squadops artifact ingest <path> --media-type ...` → returns `artifact_ref`
- `squadops artifact get <artifact_id>` (optional)
- `squadops artifact list --project <project_id>` (optional)

### PRD workflow

- `squadops prd register <project_id> --file prd.md --version 0.1.0 [--status draft|active]`  
  CLI ingests artifact, then calls PRD register endpoint with `artifact_ref`
- `squadops prd list <project_id>`
- `squadops prd show <project_id> <prd_id> [--version ...]`
- `squadops prd set-active <project_id> <prd_id> --version ...` (if active supported)

### PCR workflow

- `squadops pcr register <project_id> --file pcr.yaml --version 0.1.0 [--prd <prd_id> --prd-version ...]`
- `squadops pcr list <project_id>`
- `squadops pcr show <project_id> <pcr_id> [--version ...]`
- `squadops pcr set-active <project_id> <pcr_id> --version ...` (if active supported)
- `squadops pcr validate <project_id> <pcr_id> [--version ...]`  
  validates ownership + prd ref + override schema sanity

### Cycle + Run workflow (replaces WarmBoot)

- `squadops cycle create <project_id> --pcr <pcr_id> [--version ...] [--override key=value ...]`
- `squadops run start <project_id> <cycle_id>`
- `squadops run status <project_id> <cycle_id> [--follow]`
- `squadops cycle show <project_id> <cycle_id>`
- `squadops run list <project_id> <cycle_id>`
- `squadops gate approve <project_id> <cycle_id> <gate_name> --decision approve|reject [--note ...]`
- `squadops artifact list --cycle <cycle_id> [--run <run_id>]`

### Error handling / UX requirements

- CLI MUST surface `request_id` and a stable `error_code` on failures.
- CLI MUST provide non-interactive operation for automation (CI/selftest).

### Selftest workflow

- CLI MUST support a “selftest project” flow:
  - `squadops selftest run` which submits the built-in example project cycle and starts a run.

---

## Acceptance Criteria

- PRD and PCR are queryable per project with version history.
- A cycle creation can select PCR version by explicit version / active / latest resolution rule and persists the resolved selection.
- A run captures `resolved_config_ref` + `squad_profile_snapshot_ref` and can be inspected via API and CLI.
- The CLI can:
  - register a PRD and PCR from local files
  - create a cycle from a PCR
  - start a run
  - follow status to completion
- No WarmBoot endpoints are required for these workflows.

---

## Notes / Open questions (optional)

- Whether “active” version is needed in 0.9.4 or can be deferred (CLI can also require explicit versions).
- Whether PRD/PCR content is always vault-stored or allowed inline for small payloads (recommend vault-only for immutability).
