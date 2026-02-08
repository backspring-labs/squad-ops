# SIP-0064: Cycle Execution API Foundation — Implementation Plan

## Context

SIP-0064 (accepted) establishes the domain-driven API foundation for submitting and executing work in SquadOps. It introduces Projects, Cycles (as experiment records), Runs, Squad Profiles, Task Flow Policy, and Artifact Vault integration. It deprecates WarmBoot and demotes PCR from a standalone entity to experiment configuration fields on Cycle.

SIP spec: `sips/accepted/SIP-0064-Project-Cycle-Request-API.md`

---

## Tightening Amendments (17 items)

**T1) Persistence alignment:** In-memory registry only for v0.9.3. DB schema (`init.sql` changes) is deferred to the release where `PostgresCycleRegistryPort` lands. No "tables exist but aren't used" confusion.

**T2) Table naming:** `run` table renamed to `cycle_run` (avoids collision with generic naming and legacy concepts).

**T3) Projects source of truth:** YAML (`config/projects.yaml`) is the canonical runtime source. No DB bootstrap inserts in v0.9.3. Future Postgres adapter will idempotent-upsert from YAML on startup.

**T4) Decision vocabulary:** Normalized to `approved`/`rejected` everywhere (API request payload, `GateDecisionValue` enum, storage). No `approve`/`reject` verb forms — single vocabulary, zero mapping code.

**T5) Defaults vs overrides immutability:** Both `applied_defaults` and `execution_overrides` are set once at Cycle creation and never mutated. `resolved_config_hash` is `SHA-256(canonical_json(merge(applied_defaults, execution_overrides)))`. Changing defaults → new Cycle, not mutation.

**T6) Baseline enforcement location:** Domain/service layer (route handler or use-case function). Vault adapters are dumb storage — enforce integrity (content_hash, vault_uri) but not business policy.

**T7) Factory naming:** `create_squad_profile_provider` → `create_squad_profile_port`. Other factory names already match port names (`create_project_registry`, `create_cycle_registry`, `create_artifact_vault`, `create_flow_executor`).

**T8) FlowExecutionPort v0.9.3 scope:** `sequential` is the primary MVP mode. `fan_out_fan_in` = best-effort concurrency (submit all, await all). `fan_out_soft_gates` = sequential dispatch with pause points: `RunStatus.PAUSED` → block further task dispatch → resume only on gate decision via API. No over-engineering: simple dispatch loop, not a workflow engine.

**T9) Error contract `details`:** Always present as nullable field in the error response shape. `{"error": {"code": "...", "message": "...", "details": null}}`. Consistent across all error responses for client stability.

**T10) Frozen dataclass mutation pattern:** Registry adapters store mutable internal records and return frozen snapshots. Mutating operations (`cancel_cycle`, `update_run_status`, `record_gate_decision`, `set_active_profile`) modify internal state and return a new frozen dataclass via `dataclasses.replace(...)`. Callers never mutate domain objects directly.

**T11) Gate decision validation responsibility:** The `CycleRegistryPort.record_gate_decision()` method is the single enforcement point:
- `gate_name` must exist in the Cycle's `TaskFlowPolicy.gates` (raise `ValidationError` if not)
- Run must not be in a terminal state (raise `RunTerminalError`)
- Conflicting decision (different value for same gate) raises `GateAlreadyDecidedError`
- Same decision for same gate is idempotent (no-op, return current Run)
- Route handlers delegate to the registry; no duplicate validation.

**T12) FlowExecutionPort resume invariant:** `PAUSED → RUNNING` transition is only valid when **all required gate decisions up to the current pause point** are present. The flow executor checks gate completeness before resuming dispatch. This prevents premature resume on a partial gate decision.

**T13) DTO enum typing:** Request DTOs use `Literal` unions or Pydantic-validated enums (not bare `str`) for `decision`, `build_strategy`, and `flow_mode` fields. This gives clean 422 rejections for unknown values without custom validation code.

**T14) DI getters must not return None at call sites:** `deps.py` getters raise `RuntimeError("port not configured")` if the port singleton is `None`. Routes never handle `None` — missing ports fail loudly at first use, not buried in `NoneType has no attribute` errors.

**T15) Project YAML upsert contract:** For future Postgres adapter:
- `project_id` is the stable key (never changes)
- Non-breaking updates (name, description, tags) are allowed and applied idempotently
- Deletions from YAML are **ignored** — projects persist in DB even if removed from YAML (prevents accidental data loss)

**T16) Artifact ingest transport:** For v0.9.3, `POST /api/v1/projects/{project_id}/artifacts/ingest` uses `multipart/form-data` with fields:
- `file`: uploaded bytes (required)
- `artifact_type`: string (required)
- `filename`: string (required)
- `media_type`: string (required)
- Max upload size: **50 MB** (configurable via env/config; reject with 413 Payload Too Large)
- Content-Type: `multipart/form-data` (not JSON). FastAPI `UploadFile` + `Form(...)` fields.
- Two-step/presigned upload is deferred to a future release.

**T17) Cycle creation atomicity:** `POST /projects/{project_id}/cycles` is atomic: either the Cycle and first Run are both created, or the request fails with no persisted partial state. Trivial with the in-memory registry (single-threaded dict writes); Postgres adapter must use a transaction.

---

## Phase 1: Domain Models + Enums + Exceptions

All domain models are frozen dataclasses following the pattern in `src/squadops/tasks/models.py` and `src/squadops/auth/models.py`. Exceptions and constants are co-located in the models module.

### 1.1 Domain Module — `src/squadops/cycles/` (NEW)

Create package with three files:

**`src/squadops/cycles/__init__.py`** — Public API re-exports.

**`src/squadops/cycles/models.py`** — All domain models:

```python
# Enums (str, Enum) — following config/schema.py SSLMode pattern
class CycleStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FlowMode(str, Enum):
    SEQUENTIAL = "sequential"
    FAN_OUT_FAN_IN = "fan_out_fan_in"
    FAN_OUT_SOFT_GATES = "fan_out_soft_gates"

class BuildStrategy(str, Enum):
    FRESH = "fresh"
    INCREMENTAL = "incremental"

class GateDecisionValue(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"

# Constants classes — following auth/models.py Role pattern
class ArtifactType:
    PRD = "prd"
    CODE = "code"
    TEST_REPORT = "test_report"
    BUILD_PLAN = "build_plan"
    CONFIG_SNAPSHOT = "config_snapshot"

class RunInitiator:
    API = "api"
    CLI = "cli"
    RETRY = "retry"
    SYSTEM = "system"

# Exceptions — following auth/models.py pattern
class CycleError(Exception): ...
class CycleNotFoundError(CycleError): ...
class RunNotFoundError(CycleError): ...
class IllegalStateTransitionError(CycleError): ...
class GateAlreadyDecidedError(CycleError): ...
class RunTerminalError(CycleError): ...
class ProjectNotFoundError(CycleError): ...
class ArtifactNotFoundError(CycleError): ...
class BaselineNotAllowedError(CycleError): ...
class ValidationError(CycleError): ...

# Frozen dataclasses — following tasks/models.py pattern
@dataclass(frozen=True)
class Project: ...           # §8.1 of SIP
@dataclass(frozen=True)
class Gate: ...              # §8.3 — name, description, after_task_types
@dataclass(frozen=True)
class TaskFlowPolicy: ...    # §8.3 — mode (FlowMode), gates
@dataclass(frozen=True)
class GateDecision: ...      # §8.4 — gate_name, decision, decided_by, decided_at, notes
@dataclass(frozen=True)
class Cycle: ...             # §8.2 — experiment record with 3 core dimensions + context
@dataclass(frozen=True)
class Run: ...               # §8.4 — execution attempt
@dataclass(frozen=True)
class ArtifactRef: ...       # §8.5 — immutable artifact metadata
@dataclass(frozen=True)
class AgentProfileEntry: ... # §8.6
@dataclass(frozen=True)
class SquadProfile: ...      # §8.6
```

**`src/squadops/cycles/lifecycle.py`** — State machine logic:

```python
# Declarative transition tuples: (trigger_name, source, destination)
# Readable, zero dependencies, fits frozen dataclass immutability pattern.
_RUN_TRANSITIONS: list[tuple[str, RunStatus, RunStatus]] = [
    ("start",    RunStatus.QUEUED,   RunStatus.RUNNING),
    ("complete", RunStatus.RUNNING,  RunStatus.COMPLETED),
    ("fail",     RunStatus.RUNNING,  RunStatus.FAILED),
    ("pause",    RunStatus.RUNNING,  RunStatus.PAUSED),
    ("resume",   RunStatus.PAUSED,   RunStatus.RUNNING),
    ("cancel",   RunStatus.QUEUED,   RunStatus.CANCELLED),
    ("cancel",   RunStatus.RUNNING,  RunStatus.CANCELLED),
    ("cancel",   RunStatus.PAUSED,   RunStatus.CANCELLED),
]

# Derived lookup: source → set of valid destinations (built from tuples at import time)
_VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {}
for _trigger, _src, _dst in _RUN_TRANSITIONS:
    _VALID_TRANSITIONS.setdefault(_src, set()).add(_dst)

def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
    """Raise IllegalStateTransitionError if transition is illegal."""

def derive_cycle_status(runs: Sequence[Run], cycle_cancelled: bool) -> CycleStatus:
    """Derive CycleStatus from latest non-cancelled Run. SIP §6.3."""

def compute_config_hash(applied_defaults: dict, execution_overrides: dict) -> str:
    """SHA-256 of canonical JSON merge of defaults + overrides."""

def compute_profile_snapshot_hash(profile: SquadProfile) -> str:
    """Deterministic SHA-256 hash of a SquadProfile for immutable snapshotting."""
```

### 1.2 Unit Tests — `tests/unit/cycles/` (NEW)

**`tests/unit/cycles/conftest.py`** — Shared fixtures (`_make_project()`, `_make_cycle()`, `_make_run()`, `_make_profile()` helpers).

**`tests/unit/cycles/test_models.py`** (~30 tests):
- Construction of each frozen dataclass with all fields
- Default values (dict, tuple, None) applied correctly
- Immutability (cannot assign to field after creation)
- Enum membership for CycleStatus, RunStatus, FlowMode, BuildStrategy, GateDecisionValue
- TaskFlowPolicy with gates tuple
- Cycle with all experiment dimensions populated
- Cycle with `prd_ref=None` (example project)
- Cycle `experiment_context` accepts arbitrary keys
- Run with gate_decisions tuple
- ArtifactRef with `vault_uri=None` (ingestion window)
- SquadProfile with AgentProfileEntry tuple
- Constants classes (ArtifactType, RunInitiator) have expected values

**`tests/unit/cycles/test_lifecycle.py`** (~35 tests):
- All legal RunStatus transitions accepted
- All illegal transitions raise `IllegalStateTransitionError`
- Terminal states (completed, failed, cancelled) reject all outgoing transitions
- `derive_cycle_status` with no runs → `CREATED`
- `derive_cycle_status` with queued/running/paused → `ACTIVE`
- `derive_cycle_status` with completed → `COMPLETED`
- `derive_cycle_status` with failed → `FAILED`
- `derive_cycle_status` with all runs cancelled + cycle not cancelled → `CREATED`
- `derive_cycle_status` with cancelled run + cycle cancelled → `CANCELLED`
- `derive_cycle_status` skips cancelled runs (latest non-cancelled)
- `compute_config_hash` is deterministic (same input → same hash)
- `compute_config_hash` changes with any input change
- `compute_profile_snapshot_hash` is deterministic
- `compute_profile_snapshot_hash` changes with agent config change

**`tests/unit/cycles/test_exceptions.py`** (~10 tests):
- Each exception inherits from `CycleError`
- Each exception can be instantiated with message

Markers: `@pytest.mark.domain_orchestration` (already registered in pyproject.toml)

### 1.3 Phase 1 Exit Criteria

- [ ] All domain models importable from `squadops.cycles.models`
- [ ] All enums, constants, exceptions defined
- [ ] Lifecycle state machine validates all legal/illegal transitions
- [ ] CycleStatus derivation handles all edge cases including cancelled runs
- [ ] Config hash and profile snapshot hash are deterministic
- [ ] ~75 unit tests passing
- [ ] `run_new_arch_tests.sh` passes (no regressions)

---

## Phase 2: Ports + Adapters + Config

### 2.1 Port Definitions — `src/squadops/ports/cycles/` (NEW)

Following the `ports/auth/` nested pattern (multiple related ports under one subdomain):

**`src/squadops/ports/cycles/__init__.py`** — Re-exports all ports.

**`src/squadops/ports/cycles/project_registry.py`**:
```python
class ProjectRegistryPort(ABC):
    @abstractmethod
    async def list_projects(self) -> list[Project]: ...
    @abstractmethod
    async def get_project(self, project_id: str) -> Project: ...
```

**`src/squadops/ports/cycles/cycle_registry.py`**:
```python
class CycleRegistryPort(ABC):
    # Cycle CRUD
    @abstractmethod
    async def create_cycle(self, cycle: Cycle) -> Cycle: ...
    @abstractmethod
    async def get_cycle(self, cycle_id: str) -> Cycle: ...
    @abstractmethod
    async def list_cycles(self, project_id: str, *, status: CycleStatus | None = None) -> list[Cycle]: ...
    @abstractmethod
    async def cancel_cycle(self, cycle_id: str) -> None: ...

    # Run CRUD
    @abstractmethod
    async def create_run(self, run: Run) -> Run: ...
    @abstractmethod
    async def get_run(self, run_id: str) -> Run: ...
    @abstractmethod
    async def list_runs(self, cycle_id: str) -> list[Run]: ...
    @abstractmethod
    async def update_run_status(self, run_id: str, status: RunStatus) -> Run: ...
    @abstractmethod
    async def cancel_run(self, run_id: str) -> None: ...
    @abstractmethod
    async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run: ...
```

**`src/squadops/ports/cycles/squad_profile.py`**:
```python
class SquadProfilePort(ABC):
    @abstractmethod
    async def list_profiles(self) -> list[SquadProfile]: ...
    @abstractmethod
    async def get_profile(self, profile_id: str) -> SquadProfile: ...
    @abstractmethod
    async def get_active_profile(self) -> SquadProfile: ...
    @abstractmethod
    async def set_active_profile(self, profile_id: str) -> None: ...
    @abstractmethod
    async def resolve_snapshot(self, profile_id: str) -> tuple[SquadProfile, str]: ...
    # Returns (profile, snapshot_hash)
```

**`src/squadops/ports/cycles/artifact_vault.py`**:
```python
class ArtifactVaultPort(ABC):
    @abstractmethod
    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef: ...
    # Returns artifact with vault_uri populated
    @abstractmethod
    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]: ...
    @abstractmethod
    async def get_metadata(self, artifact_id: str) -> ArtifactRef: ...
    @abstractmethod
    async def list_artifacts(self, *, project_id: str | None = None, cycle_id: str | None = None, run_id: str | None = None, artifact_type: str | None = None) -> list[ArtifactRef]: ...
    @abstractmethod
    async def set_baseline(self, project_id: str, artifact_type: str, artifact_id: str) -> None: ...
    @abstractmethod
    async def get_baseline(self, project_id: str, artifact_type: str) -> ArtifactRef | None: ...
    @abstractmethod
    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]: ...
```

**`src/squadops/ports/cycles/flow_execution.py`**:
```python
class FlowExecutionPort(ABC):
    @abstractmethod
    async def execute_run(self, cycle: Cycle, run: Run, profile: SquadProfile) -> None: ...
    # Interprets TaskFlowPolicy, dispatches tasks, updates Run status via CycleRegistryPort
    @abstractmethod
    async def cancel_run(self, run_id: str) -> None: ...
```

### 2.2 Adapters — `adapters/cycles/` (NEW)

Following the `adapters/auth/` pattern: one factory + multiple provider subdirs.

**`adapters/cycles/__init__.py`**
**`adapters/cycles/factory.py`**:
```python
def create_project_registry(provider: str = "config", **kwargs) -> ProjectRegistryPort: ...
def create_cycle_registry(provider: str = "memory", **kwargs) -> CycleRegistryPort: ...
def create_squad_profile_port(provider: str = "config", **kwargs) -> SquadProfilePort: ...  # T7
def create_artifact_vault(provider: str = "filesystem", **kwargs) -> ArtifactVaultPort: ...
def create_flow_executor(provider: str = "in_process", **kwargs) -> FlowExecutionPort: ...
```

**`adapters/cycles/config_project_registry.py`** — Loads projects from `config/projects.yaml` (YAML file listing built-in projects). Returns `Project` frozen dataclasses. YAML is the canonical runtime source of truth (T3); no DB bootstrap inserts. Future Postgres upsert contract (T15): `project_id` is the stable key, non-breaking updates (name/description/tags) applied idempotently, deletions from YAML are ignored (projects persist in DB).

**`adapters/cycles/memory_cycle_registry.py`** — In-memory `CycleRegistryPort` for v0.9.3 (dict-based storage). Stores mutable internal records, returns frozen snapshots via `dataclasses.replace(...)` (T10). Validates state transitions via `lifecycle.validate_run_transition()`. Gate decision validation (T11): checks gate_name exists in Cycle's TaskFlowPolicy, enforces terminal/conflict/idempotency rules. Sufficient for initial development/testing; PostgreSQL adapter deferred (T1).

**`adapters/cycles/config_squad_profile.py`** — Loads profiles from `config/squad-profiles.yaml`. Computes snapshot hash via `lifecycle.compute_profile_snapshot_hash()`. Tracks active profile in memory.

**`adapters/cycles/filesystem_artifact_vault.py`** — Stores artifact bytes to local filesystem (`data/artifacts/{artifact_id}`). Stores metadata in a companion JSON sidecar. Computes `content_hash` on store. Baseline tracking via `data/artifacts/.baselines.json`. Vault enforces integrity (content_hash, vault_uri) but NOT business policy (T6) — baseline build_strategy enforcement lives in the route handler / service layer.

**`adapters/cycles/in_process_flow_executor.py`** — Wraps `AgentOrchestrator`. For v0.9.3 (T8): `sequential` (primary MVP mode) = calls `orchestrator.submit_task()` one at a time; `fan_out_fan_in` = best-effort concurrency (submit all, await all); `fan_out_soft_gates` = sequential dispatch with pause points — sets `RunStatus.PAUSED`, blocks further task dispatch. Resume invariant (T12): `PAUSED → RUNNING` only when all required gate decisions up to the current pause point are present. Simple dispatch loop, not a workflow engine. Updates Run status via injected `CycleRegistryPort`.

### 2.3 Config Files (NEW)

**`config/projects.yaml`** — Built-in project definitions:
```yaml
projects:
  - project_id: hello_squad
    name: "Hello Squad"
    description: "Simple single-agent greeting (replaces warmboot_selftest)"
    tags: [example, selftest]
  - project_id: run_crysis
    name: "Run Crysis"
    description: "Multi-agent coordinated build"
    tags: [benchmark]
  - project_id: group_run
    name: "Group Run"
    description: "Full squad parallel execution"
    tags: [benchmark]
```

**`config/squad-profiles.yaml`** — Default squad profile(s):
```yaml
profiles:
  - profile_id: full-squad
    name: "Full Squad"
    description: "All 5 agents with default models"
    version: 1
    agents:
      - agent_id: max
        role: lead
        model: gpt-4
        enabled: true
      # ... (neo, nat, eve, data)
active_profile: full-squad
```

### 2.4 DB Schema — DEFERRED (T1)

DB schema changes (`infra/init.sql`) are deferred to the release where `PostgresCycleRegistryPort` lands. In v0.9.3, all persistence is handled by the in-memory cycle registry and filesystem artifact vault. No "tables exist but aren't used" confusion.

**Future tables** (for reference when Postgres adapter ships):
- `cycle_v2` — Cycle experiment records
- `cycle_run` — Run execution attempts (T2: renamed from `run` to avoid collision)
- `gate_decision` — Gate decisions per run
- `artifact_ref` — Artifact metadata
- `artifact_baseline` — Baseline artifact pointers

**No project INSERT statements** (T3): Projects are loaded from `config/projects.yaml` at runtime. Future Postgres adapter will idempotent-upsert from YAML on startup.

### 2.5 Unit Tests — `tests/unit/cycles/test_ports.py` (~15 tests)

- Each port is an ABC; cannot be instantiated directly
- Each port method is abstract
- Port method signatures match SIP spec (parameter names and types)

### 2.6 Unit Tests — `tests/unit/cycles/test_adapters.py` (~40 tests)

**Config project registry:**
- Loads projects from YAML file
- `list_projects` returns all projects
- `get_project` returns by ID
- `get_project` with unknown ID raises `ProjectNotFoundError`

**Memory cycle registry:**
- `create_cycle` stores and returns cycle
- `get_cycle` retrieves by ID
- `get_cycle` unknown ID → `CycleNotFoundError`
- `list_cycles` by project_id
- `list_cycles` filtered by status
- `cancel_cycle` marks cancelled
- `cancel_cycle` already cancelled → idempotent
- `create_run` stores and returns run
- `get_run` retrieves by ID
- `list_runs` by cycle_id
- `update_run_status` legal transition succeeds
- `update_run_status` illegal transition → `IllegalStateTransitionError`
- `cancel_run` from queued/running/paused
- `record_gate_decision` stores decision
- `record_gate_decision` duplicate same decision → idempotent
- `record_gate_decision` conflicting → `GateAlreadyDecidedError`
- `record_gate_decision` on terminal run → `RunTerminalError`

**Config squad profile:**
- `list_profiles` returns all profiles
- `get_profile` returns by ID
- `get_active_profile` returns active
- `set_active_profile` changes active
- `resolve_snapshot` returns profile + deterministic hash

**Filesystem artifact vault:**
- `store` writes bytes and returns artifact with vault_uri
- `retrieve` reads bytes back
- `get_metadata` returns ArtifactRef without bytes
- `list_artifacts` filters by project/cycle/run/type
- `set_baseline` stores baseline
- `get_baseline` returns baseline ref
- `list_baselines` returns all baselines for project
- Note: `BaselineNotAllowedError` (fresh build strategy) is tested in Phase 3 API tests, not here — vault is dumb storage (T6)

### 2.7 Phase 2 Exit Criteria

- [ ] 5 ports defined as ABCs in `src/squadops/ports/cycles/`
- [ ] 5 adapter implementations in `adapters/cycles/`
- [ ] Factory module creates all adapters
- [ ] Config files (projects.yaml, squad-profiles.yaml) define built-in data
- [ ] DB schema deferred (T1) — no init.sql changes in this phase
- [ ] ~55 unit tests passing
- [ ] `run_new_arch_tests.sh` passes (no regressions)

---

## Phase 3: API Routes + DTOs + DI Wiring

### 3.1 API DTOs — `src/squadops/api/routes/cycles/dtos.py` (NEW)

Pydantic BaseModel DTOs for request/response serialization (separate from frozen domain models):

```python
# Request DTOs
class CycleCreateRequest(BaseModel):
    prd_ref: str | None = None
    squad_profile_id: str
    task_flow_policy: TaskFlowPolicyDTO
    build_strategy: Literal["fresh", "incremental"] = "fresh"  # T13: typed, not bare str
    execution_overrides: dict = Field(default_factory=dict)
    expected_artifact_types: list[str] = Field(default_factory=list)
    experiment_context: dict = Field(default_factory=dict)
    notes: str | None = None

    class Config:
        extra = "forbid"

class GateDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]  # T4+T13: normalized vocab, typed
    notes: str | None = None

    class Config:
        extra = "forbid"

class SetActiveProfileRequest(BaseModel):
    profile_id: str

# ArtifactIngestRequest is NOT a Pydantic model — uses multipart/form-data (T16):
# file: UploadFile (required)
# artifact_type: Form(str) (required)
# filename: Form(str) (required)
# media_type: Form(str) (required)
# Max size: 50 MB (reject with 413)

class BaselinePromoteRequest(BaseModel):
    artifact_id: str

# Response DTOs
class ProjectResponse(BaseModel): ...
class CycleResponse(BaseModel): ...
class CycleCreateResponse(BaseModel): ...  # includes first run_id
class RunResponse(BaseModel): ...
class SquadProfileResponse(BaseModel): ...
class ArtifactRefResponse(BaseModel): ...
class ErrorResponse(BaseModel): ...  # §11 standard shape
```

### 3.2 DTO Mapping — `src/squadops/api/routes/cycles/mapping.py` (NEW)

Functions to convert between domain models and DTOs:

```python
def cycle_to_response(cycle: Cycle, runs: list[Run]) -> CycleResponse: ...
def run_to_response(run: Run) -> RunResponse: ...
def project_to_response(project: Project) -> ProjectResponse: ...
def profile_to_response(profile: SquadProfile) -> SquadProfileResponse: ...
def artifact_to_response(artifact: ArtifactRef) -> ArtifactRefResponse: ...
```

### 3.3 Route Modules — `src/squadops/api/routes/cycles/` (NEW)

Following the `routes/auth.py` pattern but grouped under a `cycles/` package:

**`src/squadops/api/routes/cycles/__init__.py`** — Re-exports all routers.

**`src/squadops/api/routes/cycles/projects.py`**:
```python
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.get("")           # GET /api/v1/projects
@router.get("/{project_id}")  # GET /api/v1/projects/{project_id}
```

**`src/squadops/api/routes/cycles/cycles.py`**:
```python
router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles", tags=["cycles"])

@router.post("")              # POST — create cycle + first run (atomic, T17)
@router.get("")               # GET — list cycles
@router.get("/{cycle_id}")    # GET — get cycle detail
@router.post("/{cycle_id}/cancel")  # POST — cancel cycle
```

**`src/squadops/api/routes/cycles/runs.py`**:
```python
router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", tags=["runs"])

@router.post("")              # POST — create new run (retry)
@router.get("")               # GET — list runs
@router.get("/{run_id}")      # GET — get run detail
@router.post("/{run_id}/cancel")  # POST — cancel run
@router.post("/{run_id}/gates/{gate_name}")  # POST — gate decision
```

**`src/squadops/api/routes/cycles/profiles.py`**:
```python
router = APIRouter(prefix="/api/v1/squad-profiles", tags=["squad-profiles"])

@router.get("")           # GET — list profiles
@router.get("/active")    # GET — get active profile
@router.post("/active")   # POST — set active profile
@router.get("/{profile_id}")  # GET — get profile
```

**`src/squadops/api/routes/cycles/artifacts.py`**:
```python
router = APIRouter(prefix="/api/v1", tags=["artifacts"])

@router.post("/projects/{project_id}/artifacts/ingest")  # POST — ingest artifact (multipart/form-data, T16)
@router.get("/artifacts/{artifact_id}")   # GET — metadata
@router.get("/artifacts/{artifact_id}/download")  # GET — bytes/URL
@router.get("/projects/{project_id}/artifacts")   # GET — list by project
@router.get("/projects/{project_id}/cycles/{cycle_id}/artifacts")  # GET — list by cycle
@router.post("/projects/{project_id}/baseline/{artifact_type}")  # POST — promote baseline
@router.get("/projects/{project_id}/baseline/{artifact_type}")   # GET — get baseline
@router.get("/projects/{project_id}/baseline")  # GET — list baselines
```

### 3.4 Error Handling

Each route module uses a consistent error handler that maps domain exceptions to HTTP responses per SIP §11:

```python
# T9: `details` is always present (nullable) for client stability.
# Shape: {"error": {"code": "...", "message": "...", "details": null}}

_ERROR_MAP: list[tuple[type, int, str]] = [
    (ProjectNotFoundError,        404, "PROJECT_NOT_FOUND"),
    (CycleNotFoundError,          404, "CYCLE_NOT_FOUND"),
    (RunNotFoundError,            404, "RUN_NOT_FOUND"),
    (ArtifactNotFoundError,       404, "ARTIFACT_NOT_FOUND"),
    (IllegalStateTransitionError, 409, "ILLEGAL_STATE_TRANSITION"),
    (GateAlreadyDecidedError,     409, "GATE_ALREADY_DECIDED"),
    (RunTerminalError,            409, "RUN_TERMINAL"),
    (BaselineNotAllowedError,     409, "BASELINE_NOT_ALLOWED"),
    (ValidationError,             422, "VALIDATION_ERROR"),
]

def handle_cycle_error(e: CycleError) -> HTTPException:
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(e, exc_type):
            return HTTPException(status, detail={"error": {"code": code, "message": str(e), "details": None}})
    return HTTPException(500, detail={"error": {"code": "INTERNAL_ERROR", "message": str(e), "details": None}})
```

### 3.5 DI Wiring — `src/squadops/api/runtime/deps.py` (MODIFY)

Add port singletons and setters/getters following existing pattern:

```python
# New singletons
_project_registry: ProjectRegistryPort | None = None
_cycle_registry: CycleRegistryPort | None = None
_squad_profile: SquadProfilePort | None = None
_artifact_vault: ArtifactVaultPort | None = None
_flow_executor: FlowExecutionPort | None = None

# Setters
def set_cycle_ports(
    project_registry: ProjectRegistryPort | None = None,
    cycle_registry: CycleRegistryPort | None = None,
    squad_profile: SquadProfilePort | None = None,
    artifact_vault: ArtifactVaultPort | None = None,
    flow_executor: FlowExecutionPort | None = None,
) -> None: ...

# Getters — raise RuntimeError if not configured (T14: never return None)
def get_project_registry() -> ProjectRegistryPort: ...
def get_cycle_registry() -> CycleRegistryPort: ...
def get_squad_profile_port() -> SquadProfilePort: ...
def get_artifact_vault() -> ArtifactVaultPort: ...
def get_flow_executor() -> FlowExecutionPort: ...
```

### 3.6 Startup Wiring — `src/squadops/api/runtime/main.py` (MODIFY)

Add to `startup_event()`:

```python
# Initialize SIP-0064 cycle ports
try:
    from adapters.cycles.factory import (
        create_project_registry,
        create_cycle_registry,
        create_squad_profile_port,  # T7: consistent naming
        create_artifact_vault,
        create_flow_executor,
    )
    set_cycle_ports(
        project_registry=create_project_registry("config"),
        cycle_registry=create_cycle_registry("memory"),
        squad_profile=create_squad_profile_port("config"),  # T7
        artifact_vault=create_artifact_vault("filesystem"),
        flow_executor=create_flow_executor("in_process"),
    )
    logger.info("SIP-0064 cycle ports initialized")
except Exception as e:
    logger.error(f"Failed to initialize cycle ports: {e}")
```

Include all cycle routers:
```python
from squadops.api.routes.cycles import projects_router, cycles_router, runs_router, profiles_router, artifacts_router
app.include_router(projects_router)
app.include_router(cycles_router)
app.include_router(runs_router)
app.include_router(profiles_router)
app.include_router(artifacts_router)
```

### 3.7 Unit Tests — `tests/unit/cycles/test_api_*.py` (~50 tests)

Follow the `tests/unit/auth/test_middleware.py` pattern: TestClient with inline minimal FastAPI apps using mock ports.

**`tests/unit/cycles/test_api_projects.py`** (~8 tests):
- `GET /api/v1/projects` returns list
- `GET /api/v1/projects/{id}` returns project
- `GET /api/v1/projects/unknown` → 404 with standard error shape

**`tests/unit/cycles/test_api_cycles.py`** (~15 tests):
- `POST /api/v1/projects/{id}/cycles` creates cycle + first run atomically (T17)
- Create cycle with `prd_ref=None` (example project) → 200
- Create cycle with unknown project → 404
- Create cycle with extra fields → 422 (extra="forbid")
- `GET /api/v1/projects/{id}/cycles` returns list
- `GET /api/v1/projects/{id}/cycles?status=completed` filters
- `GET /api/v1/projects/{id}/cycles/{cycle_id}` returns cycle detail with derived status
- `POST .../cancel` → cancels cycle

**`tests/unit/cycles/test_api_runs.py`** (~12 tests):
- `POST .../runs` creates new run (retry)
- `GET .../runs` lists runs
- `GET .../runs/{run_id}` returns run detail
- `POST .../runs/{run_id}/cancel` cancels run
- Gate decision: approve → 200
- Gate decision: double-approve → 200 (idempotent)
- Gate decision: approve then reject → 409
- Gate decision on terminal run → 409

**`tests/unit/cycles/test_api_profiles.py`** (~6 tests):
- `GET /api/v1/squad-profiles` returns list
- `GET /api/v1/squad-profiles/active` returns active
- `POST /api/v1/squad-profiles/active` sets active
- `GET /api/v1/squad-profiles/{id}` returns profile

**`tests/unit/cycles/test_api_artifacts.py`** (~10 tests):
- `POST /api/v1/projects/{id}/artifacts/ingest` ingests multipart file and returns ref (T16)
- `POST .../ingest` with oversized file → 413 (T16)
- `GET /api/v1/artifacts/{id}` returns metadata
- `GET /api/v1/projects/{id}/artifacts` lists
- `GET /api/v1/projects/{id}/artifacts?artifact_type=prd` filters
- Baseline promotion on incremental → 200
- Baseline promotion on fresh → 409 `BaselineNotAllowedError` (enforcement moved here from vault tests — T6)
- `GET .../baseline` returns baselines

**`tests/unit/cycles/test_error_contract.py`** (~5 tests):
- Error responses match §11 JSON shape (`{error: {code, message, details}}`) — T9: `details` always present (nullable)
- Each error code maps to correct HTTP status
- `details` field is `null` (not absent) on all error responses

### 3.8 Phase 3 Exit Criteria

- [ ] All 5 route modules registered on app
- [ ] DI wiring follows existing pattern (set/get singletons)
- [ ] Startup initializes all 5 adapters via factory
- [ ] Request/response DTOs enforce `extra="forbid"`
- [ ] Error responses match SIP §11 contract
- [ ] ~50 API unit tests passing
- [ ] `run_new_arch_tests.sh` passes (no regressions)

---

## Phase 4: Integration Tests + Regression

### 4.1 Integration Tests — `tests/unit/cycles/test_integration.py` (~15 tests)

End-to-end flows using real (in-memory/filesystem) adapters, no mocks:

- Create project → create cycle → start run → complete run → verify CycleStatus = completed
- Create cycle → start run → fail run → verify CycleStatus = failed
- Create cycle → start run → pause at gate → approve → complete → verify
- Create cycle → start run → pause at gate → reject → verify RunStatus = cancelled
- Create cycle → cancel cycle → attempt new run → rejected
- Create cycle → start run → cancel run → start another run → complete → verify
- Ingest PRD artifact → create cycle with prd_ref → verify linkage
- Ingest artifact → promote baseline → retrieve baseline
- Cycle with experiment_context → retrieve → context preserved
- Cycle applied_defaults vs execution_overrides stored separately
- Multiple cycles for same project → list cycles → filter by status

### 4.2 pyproject.toml (MODIFY)

Register new test marker if needed. `domain_orchestration` is already registered. Verify no new markers are needed.

### 4.3 Phase 4 Exit Criteria

- [ ] Integration tests pass with real in-memory/filesystem adapters
- [ ] `run_new_arch_tests.sh` passes (full regression, 629+ tests + new tests)
- [ ] Total new tests: ~195

---

## Files Modified/Created Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/cycles/__init__.py` | NEW — package init | 1 |
| `src/squadops/cycles/models.py` | NEW — all domain models, enums, exceptions, constants | 1 |
| `src/squadops/cycles/lifecycle.py` | NEW — state machine, hash computation | 1 |
| `src/squadops/ports/cycles/__init__.py` | NEW — port package init | 2 |
| `src/squadops/ports/cycles/project_registry.py` | NEW — ProjectRegistryPort | 2 |
| `src/squadops/ports/cycles/cycle_registry.py` | NEW — CycleRegistryPort | 2 |
| `src/squadops/ports/cycles/squad_profile.py` | NEW — SquadProfilePort | 2 |
| `src/squadops/ports/cycles/artifact_vault.py` | NEW — ArtifactVaultPort | 2 |
| `src/squadops/ports/cycles/flow_execution.py` | NEW — FlowExecutionPort | 2 |
| `adapters/cycles/__init__.py` | NEW — adapter package init | 2 |
| `adapters/cycles/factory.py` | NEW — adapter factory | 2 |
| `adapters/cycles/config_project_registry.py` | NEW — YAML project loader | 2 |
| `adapters/cycles/memory_cycle_registry.py` | NEW — in-memory cycle/run store | 2 |
| `adapters/cycles/config_squad_profile.py` | NEW — YAML profile loader | 2 |
| `adapters/cycles/filesystem_artifact_vault.py` | NEW — filesystem vault | 2 |
| `adapters/cycles/in_process_flow_executor.py` | NEW — wraps AgentOrchestrator | 2 |
| `config/projects.yaml` | NEW — built-in project definitions | 2 |
| `config/squad-profiles.yaml` | NEW — default squad profiles | 2 |
| `infra/init.sql` | DEFERRED (T1) — no changes in v0.9.3 | — |
| `src/squadops/api/routes/cycles/__init__.py` | NEW — route package init | 3 |
| `src/squadops/api/routes/cycles/dtos.py` | NEW — Pydantic request/response DTOs | 3 |
| `src/squadops/api/routes/cycles/mapping.py` | NEW — domain↔DTO mapping | 3 |
| `src/squadops/api/routes/cycles/projects.py` | NEW — project routes | 3 |
| `src/squadops/api/routes/cycles/cycles.py` | NEW — cycle routes | 3 |
| `src/squadops/api/routes/cycles/runs.py` | NEW — run routes | 3 |
| `src/squadops/api/routes/cycles/profiles.py` | NEW — profile routes | 3 |
| `src/squadops/api/routes/cycles/artifacts.py` | NEW — artifact routes | 3 |
| `src/squadops/api/routes/cycles/errors.py` | NEW — error handler (§11) | 3 |
| `src/squadops/api/runtime/deps.py` | MODIFY — add cycle port singletons | 3 |
| `src/squadops/api/runtime/main.py` | MODIFY — startup wiring + router includes | 3 |
| `tests/unit/cycles/__init__.py` | NEW | 1 |
| `tests/unit/cycles/conftest.py` | NEW — shared fixtures | 1 |
| `tests/unit/cycles/test_models.py` | NEW — ~30 tests | 1 |
| `tests/unit/cycles/test_lifecycle.py` | NEW — ~35 tests | 1 |
| `tests/unit/cycles/test_exceptions.py` | NEW — ~10 tests | 1 |
| `tests/unit/cycles/test_ports.py` | NEW — ~15 tests | 2 |
| `tests/unit/cycles/test_adapters.py` | NEW — ~40 tests | 2 |
| `tests/unit/cycles/test_api_projects.py` | NEW — ~8 tests | 3 |
| `tests/unit/cycles/test_api_cycles.py` | NEW — ~15 tests | 3 |
| `tests/unit/cycles/test_api_runs.py` | NEW — ~12 tests | 3 |
| `tests/unit/cycles/test_api_profiles.py` | NEW — ~6 tests | 3 |
| `tests/unit/cycles/test_api_artifacts.py` | NEW — ~10 tests | 3 |
| `tests/unit/cycles/test_error_contract.py` | NEW — ~5 tests | 3 |
| `tests/unit/cycles/test_integration.py` | NEW — ~15 tests | 4 |

**Total: ~35 new files, 2 modified files, ~195 new tests**

---

## Verification

### Phase 1
```bash
pytest tests/unit/cycles/test_models.py tests/unit/cycles/test_lifecycle.py tests/unit/cycles/test_exceptions.py -v
./scripts/dev/run_new_arch_tests.sh -v
```

### Phase 2
```bash
pytest tests/unit/cycles/test_ports.py tests/unit/cycles/test_adapters.py -v
./scripts/dev/run_new_arch_tests.sh -v
```

### Phase 3
```bash
pytest tests/unit/cycles/test_api_*.py tests/unit/cycles/test_error_contract.py -v
./scripts/dev/run_new_arch_tests.sh -v
```

### Phase 4
```bash
pytest tests/unit/cycles/ -v  # All cycle tests
./scripts/dev/run_new_arch_tests.sh -v  # Full regression (629+ existing + ~195 new)
```
