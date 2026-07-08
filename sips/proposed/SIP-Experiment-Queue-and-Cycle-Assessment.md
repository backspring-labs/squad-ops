---
title: Experiment Queue and Cycle Assessment Framework
status: proposed
authors: SquadOps Architecture
created_at: '2026-03-29'
---
# SIP: Experiment Queue and Cycle Assessment Framework

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-03-29

## 1. Abstract

Introduce a governed experiment queue and cycle assessment framework for SquadOps. This SIP adds the ability to define hypotheses with measurable targets, queue experiments containing one or more cycle configurations, execute them sequentially through the existing cycle pipeline, score each cycle with a structured assessment, and evaluate results against the hypothesis.

The framework extends the existing multi-workload orchestration (SIP-0083) by one level: an experiment is a governed sequence of cycles, the same way a cycle is a governed sequence of workloads. No new agent roles are introduced. The existing squad produces assessment artifacts through new handlers in the wrap-up workload.

This is the foundation for Plutarch — the master experimenter capability for SquadOps. v1.1 establishes the harness; v1.2 can plug in an autonomous experimenter that designs and queues experiments via the same API.

## 2. Problem Statement

SquadOps can execute cycles and produce artifacts, but it has no structured way to:

1. **Measure cycle effectiveness** — there is no standardized scorecard that captures outcome quality, efficiency, retry burden, or artifact completeness in a comparable format across cycles.
2. **Test hypotheses** — there is no mechanism to define what "better" means for a given change (new memory rules, different model, changed routing) and measure whether the change actually improved outcomes.
3. **Run multiple experiments unattended** — operators must manually create cycles one at a time and visually inspect results. There is no queue, no batch execution, and no automated comparison.
4. **Accumulate operational knowledge** — without structured assessment, lessons from each cycle remain trapped in raw telemetry and human memory rather than feeding into a measurable improvement loop.

Without this, SquadOps cannot answer its central question: **can coordinated squads outperform a single strong model on sustained software-building work, and what changes improve that performance?**

## 3. Goals

1. Define a `CycleAssessment` artifact produced after every cycle, scoring outcome, quality, efficiency, and stability in a structured, comparable format.
2. Define an `ExperimentDefinition` model that captures a hypothesis, target metrics with thresholds, a list of cycle configurations to run, and budget/stop controls.
3. Implement an experiment queue (Postgres-backed) with CLI and API operations: queue, list, show, cancel.
4. Implement an experiment runner that processes queued experiments: execute each cycle, collect assessments, evaluate against hypothesis thresholds, produce an `ExperimentAssessment`.
5. Add a `CycleAssessmentHandler` to the wrap-up workload (Data role) that consumes run telemetry and produces the scorecard artifact.
6. Expose experiment results as structured artifacts in the vault for downstream consumption (future diagnosis, MemoryRule extraction, trend analysis).

## 4. Non-Goals

1. Autonomous experiment design — v1.1 is human-queued, system-executed.
2. External benchmark integration (SWE-bench, BFCL, etc.) — deferred to v1.2.
3. MemoryRule extraction or registry — separate SIP, consumes this framework's output.
4. Failure diagnosis automation — v1.1 produces scorecards; structured diagnosis is a follow-on.
5. Squad health or agent impact assessments — deferred to v1.2.
6. Model lane policies or automatic model swapping.
7. New agent roles — experiments use the existing squad.

## 5. SIP Relationships

- **Extends SIP-0083** (Multi-Run Cycle Orchestration): Adds `execute_experiment` as a higher-order loop over `execute_cycle`.
- **Extends SIP-0080** (Wrap-Up Workload Protocol): Adds a `CycleAssessmentHandler` to the wrap-up task steps.
- **Uses SIP-0077** (Cycle Event System): Emits experiment lifecycle events.
- **Uses SIP-0076** (Workload-Gate Canon): Experiments use auto-gates for unattended execution.
- **Prepares for** Collaborative Memory Distillation: Assessment artifacts are the input for future MemoryRule extraction.
- **Prepares for** Plutarch v1.2: The experiment API becomes the surface an autonomous experimenter calls.

## 6. Design

### 6.1 CycleAssessment Artifact

Produced by the Data role during wrap-up. Consumes telemetry from the completed cycle.

```yaml
kind: CycleAssessment
uid: assessment-cyc_a6161205cf1e
cycle_id: cyc_a6161205cf1e
run_id: run_43022c7d61c6
project_id: play_game
squad_profile_id: full-squad
request_profile: selftest
model: qwen2.5:7b

scores:
  outcome: 1.0          # 1.0 = completed, 0.5 = partial, 0.0 = failed
  quality: 0.85         # test pass ratio, artifact completeness
  efficiency: 0.72      # inverse of retry/rewind/escalation burden
  stability: 0.90       # no downstream regressions, correction loops bounded

telemetry:
  total_tasks: 5
  completed_tasks: 5
  failed_tasks: 0
  retries: 1
  corrections: 0
  rewinds: 0
  wall_clock_seconds: 127
  token_cost_usd: 0.42

artifact_summary:
  total_artifacts: 5
  artifact_types:
    document: 3
    source: 1
    test: 1

tags: {}
```

#### Scoring Rules

| Dimension | Inputs | Formula (v1) |
|-----------|--------|-------------|
| outcome | terminal status | COMPLETED=1.0, FAILED=0.0, CANCELLED=0.0 |
| quality | test_pass_ratio, artifact_count vs expected | weighted average |
| efficiency | retries, corrections, rewinds, wall_clock vs budget | 1.0 - (penalty_sum / max_penalty) clamped to [0,1] |
| stability | correction_attempts, downstream failures | 1.0 - (instability_signals / max_signals) |

Exact weights are configurable via `applied_defaults` on the cycle request profile. v1 uses simple defaults; refinement is expected through experimentation.

### 6.2 ExperimentDefinition Model

```python
@dataclass(frozen=True)
class ExperimentDefinition:
    experiment_id: str
    hypothesis: str
    target_metrics: tuple[TargetMetric, ...]
    cycle_configs: tuple[ExperimentCycleConfig, ...]
    budget_cap_usd: float | None = None
    time_cap_seconds: int | None = None
    stop_on_first_failure: bool = False
    status: str = "queued"  # queued | running | completed | failed | cancelled
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetMetric:
    metric: str          # e.g. "retries", "quality", "outcome", "wall_clock_seconds"
    operator: str        # lte, gte, eq, lt, gt
    threshold: float


@dataclass(frozen=True)
class ExperimentCycleConfig:
    project_id: str
    request_profile: str
    squad_profile: str
    execution_overrides: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)  # e.g. {"role": "baseline"}
```

### 6.3 ExperimentAssessment Artifact

Produced after all cycles in an experiment complete.

```yaml
kind: ExperimentAssessment
uid: exp-assessment-exp_001
experiment_id: exp_001
hypothesis: "MemoryRules reduce retry count below 2"
verdict: passed  # passed | failed | inconclusive
target_metrics:
  - metric: retries
    operator: lte
    threshold: 2.0
    observed_values: [1, 3]
    passed: false
  - metric: quality
    operator: gte
    threshold: 0.8
    observed_values: [0.85, 0.78]
    passed: false
cycle_assessments:
  - assessment_id: assessment-cyc_001
    tags: { role: baseline }
  - assessment_id: assessment-cyc_002
    tags: { role: challenger }
summary: "1 of 2 target metrics met. Retry count exceeded threshold in challenger cycle."
```

### 6.4 Experiment Queue (DDL)

```sql
CREATE TABLE experiments (
    experiment_id   TEXT PRIMARY KEY,
    hypothesis      TEXT NOT NULL,
    target_metrics  JSONB NOT NULL DEFAULT '[]',
    cycle_configs   JSONB NOT NULL DEFAULT '[]',
    budget_cap_usd  NUMERIC,
    time_cap_seconds INT,
    stop_on_first_failure BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    queue_position  SERIAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    cycle_ids       JSONB DEFAULT '[]',
    assessment_refs JSONB DEFAULT '[]',
    tags            JSONB DEFAULT '{}',
    error           TEXT
);

CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_queue ON experiments(queue_position) WHERE status = 'queued';
```

### 6.5 ExperimentRegistryPort

```python
class ExperimentRegistryPort(ABC):
    """Registry for experiment definitions and queue management."""

    @abstractmethod
    async def enqueue(self, definition: ExperimentDefinition) -> None:
        """Add an experiment to the queue. Idempotent by experiment_id."""

    @abstractmethod
    async def dequeue_next(self) -> ExperimentDefinition | None:
        """Return the next queued experiment (by queue_position), or None."""

    @abstractmethod
    async def update_status(
        self, experiment_id: str, status: str, **kwargs
    ) -> None:
        """Update experiment status and optional fields (started_at, finished_at, error)."""

    @abstractmethod
    async def append_cycle_id(self, experiment_id: str, cycle_id: str) -> None:
        """Record a cycle_id created as part of this experiment."""

    @abstractmethod
    async def append_assessment_ref(
        self, experiment_id: str, assessment_id: str
    ) -> None:
        """Record an assessment artifact produced for this experiment."""

    @abstractmethod
    async def get(self, experiment_id: str) -> ExperimentDefinition | None:
        """Retrieve an experiment by ID."""

    @abstractmethod
    async def list_experiments(
        self, status: str | None = None
    ) -> list[ExperimentDefinition]:
        """List experiments, optionally filtered by status."""
```

### 6.6 Experiment Execution Flow

```
execute_experiment(experiment_id)
  │
  ├─ for each cycle_config in experiment.cycle_configs:
  │    ├─ create_cycle(project, profile, squad_profile, overrides)
  │    ├─ execute_cycle(cycle_id)  # existing SIP-0083 flow
  │    │    └─ includes wrap-up workload with CycleAssessmentHandler
  │    ├─ collect CycleAssessment artifact from vault
  │    ├─ check budget/time caps → break if exceeded
  │    └─ check stop_on_first_failure → break if cycle failed
  │
  ├─ build ExperimentAssessment
  │    ├─ compare each cycle's scorecard against target_metrics
  │    ├─ determine verdict (passed/failed/inconclusive)
  │    └─ store as artifact
  │
  └─ update experiment status → completed/failed
```

The experiment runner is a simple loop — no new orchestration paradigm. It calls `execute_cycle` (SIP-0083) for each cycle config and collects the results.

### 6.7 CycleAssessmentHandler

A new handler registered for the `data.assess_cycle` task type, added to the wrap-up workload task steps.

```python
class CycleAssessmentHandler(_CycleTaskHandler):
    _handler_name = "cycle_assessment_handler"
    _capability_id = "data.assess_cycle"
    _role = "data"
    _artifact_name = "cycle_assessment"
```

The handler:
1. Receives run telemetry via `inputs` (task counts, retry counts, timing, artifact refs)
2. Computes scores using the scoring rules
3. Produces a `CycleAssessment` YAML artifact
4. Stores it in the vault as artifact type `assessment`

This does NOT require an LLM call. It's a deterministic computation from telemetry — the Data agent produces it as a structured artifact, not a generated document.

### 6.8 CLI Commands

```bash
# Queue an experiment
squadops experiments queue <project_id> \
  --profile <profile>[,<profile2>] \
  --squad-profile <squad_profile> \
  --hypothesis "description" \
  --metric "retries:lte:3" \
  [--metric "quality:gte:0.8"] \
  [--budget-cap-usd 25] \
  [--tag role=baseline,role=challenger]

# List experiments
squadops experiments list [--status queued|running|completed]

# Show experiment details + assessment
squadops experiments show <experiment_id>

# Cancel a queued experiment
squadops experiments cancel <experiment_id>

# Run the queue (processes experiments sequentially)
squadops experiments run-queue [--max-experiments N] [--budget-cap-usd N]
```

### 6.9 API Routes

```
POST   /api/v1/experiments                    # enqueue
GET    /api/v1/experiments                    # list (filter by status)
GET    /api/v1/experiments/{experiment_id}    # show
DELETE /api/v1/experiments/{experiment_id}    # cancel
POST   /api/v1/experiments/run-queue          # start queue runner
```

### 6.10 Event Types

New event types added to the existing taxonomy:

```python
EXPERIMENT_QUEUED = "experiment.queued"
EXPERIMENT_STARTED = "experiment.started"
EXPERIMENT_CYCLE_STARTED = "experiment.cycle_started"
EXPERIMENT_CYCLE_COMPLETED = "experiment.cycle_completed"
EXPERIMENT_ASSESSED = "experiment.assessed"
EXPERIMENT_COMPLETED = "experiment.completed"
EXPERIMENT_FAILED = "experiment.failed"
EXPERIMENT_CANCELLED = "experiment.cancelled"
```

## 7. Key Design Decisions

### D1: Experiments are N cycles, not forced pairs
An experiment contains a list of cycle configs. Could be 1 (smoke test), 2 (A/B comparison), or 10 (repeatability study). The hypothesis + target metrics define success, not the structure.

### D2: CycleAssessment is independent of experiments
Every cycle can produce an assessment during wrap-up, regardless of whether it's part of an experiment. This makes assessments useful for standalone cycle monitoring too.

### D3: Assessment scoring is deterministic, not LLM-generated
The CycleAssessmentHandler computes scores from telemetry, not from LLM judgment. This ensures assessments are comparable and reproducible. LLM-assisted analysis belongs in a future diagnosis layer.

### D4: No new agent roles
Experiments use the existing squad. The Data agent produces assessments. Max leads cycles. No Plutarch agent.

### D5: Experiment runner is framework-level
The runner sits on `FlowExecutionPort`, same as `execute_cycle`. It is not an agent, not a workload — it's an outer loop that calls `execute_cycle` for each config.

### D6: Auto-gates for unattended execution
Experiment cycles should use `"auto"` gates (SIP-0083) so they can run without human intervention. The experiment definition inherits this from the cycle request profiles used.

### D7: Queue runner is human-initiated in v1.1
`run-queue` is a CLI/API command that processes experiments. It is not a persistent daemon. v1.2 can add scheduled or autonomous queue population.

### D8: Budget enforcement at experiment level
Budget caps and time caps are checked after each cycle completes. If exceeded, remaining cycles are skipped and the experiment status is set to `completed` with a note.

### D9: Tags for flexible grouping
Cycle configs have a `tags` dict (e.g., `{"role": "baseline"}`) that flows into the assessment. This allows flexible grouping without baking in baseline/challenger semantics.

## 8. Implementation Phases

### Phase 1: CycleAssessment Foundation
- Define `CycleAssessment` frozen dataclass and YAML artifact schema
- Implement `CycleAssessmentHandler` (deterministic scoring from telemetry)
- Add `data.assess_cycle` to `WRAPUP_TASK_STEPS`
- Register handler in capability dispatch
- Tests: handler unit tests, scoring rule tests, artifact format tests

### Phase 2: Experiment Models and Registry
- Define `ExperimentDefinition`, `TargetMetric`, `ExperimentCycleConfig` frozen dataclasses
- Define `ExperimentAssessment` artifact schema
- Implement `ExperimentRegistryPort` and Postgres adapter
- DDL migration for `experiments` table
- Add `experiment_id` keys to `_APPLIED_DEFAULTS_EXTRA_KEYS` if needed
- Tests: model tests, registry adapter CRUD, queue ordering

### Phase 3: Experiment Execution
- Implement `execute_experiment` on `FlowExecutionPort`
- Implement experiment runner loop (cycle execution, assessment collection, budget checks)
- Implement `ExperimentAssessment` generation (compare scorecards vs target metrics)
- Wire experiment lifecycle events
- Tests: executor unit tests, budget/stop condition tests, assessment comparison tests

### Phase 4: CLI and API
- Implement `experiments` CLI commands (queue, list, show, cancel, run-queue)
- Implement experiment API routes
- Wire DTOs and mapping
- Tests: CLI tests, route tests

### Phase 5: Integration and Validation
- End-to-end: queue experiment via CLI, run queue, verify scorecards and assessment produced
- Version bump
- SIP promotion

## 9. Acceptance Criteria

1. Every cycle with a wrap-up workload produces a `CycleAssessment` artifact with outcome, quality, efficiency, and stability scores.
2. `squadops experiments queue` creates an experiment with hypothesis, target metrics, and cycle configs.
3. `squadops experiments run-queue` processes queued experiments, executing each cycle and collecting assessments.
4. Each completed experiment produces an `ExperimentAssessment` with per-metric pass/fail against thresholds.
5. Budget caps halt experiment execution when exceeded.
6. Experiment status transitions are tracked (queued → running → completed/failed/cancelled).
7. All experiment and assessment artifacts are stored in the vault and queryable.
8. Experiments work with auto-gates for unattended execution.

## 10. Risks

### A1: Scoring formula produces misleading results early
Mitigation: Start with simple formulas, make weights configurable, iterate based on experiment evidence. v1 scoring does not need to be perfect — it needs to be consistent and comparable.

### A2: Queue runner hangs on a stuck cycle
Mitigation: Time cap per experiment. The existing cycle-level time budget (SIP-0079) handles per-cycle timeouts. The experiment-level cap handles the aggregate.

### A3: Assessment handler adds overhead to every cycle
Mitigation: Assessment is a deterministic computation from telemetry — no LLM call, negligible latency. It's a structured artifact write, not a generation task.

### A4: Experiment queue grows without bound
Mitigation: Queue position ordering ensures FIFO. `--max-experiments` flag on `run-queue` bounds each invocation. Stale experiments can be cancelled.

## 11. Future Extensions (v1.2+)

- **Autonomous experiment design**: An external system (OpenClaw, scheduled job) reads prior assessments and queues new experiments via the API.
- **MemoryRule extraction**: A diagnosis step consumes experiment assessments and proposes candidate MemoryRules from recurring failure patterns.
- **External benchmarks**: Benchmark registry entries that reference SWE-bench, BFCL, etc., with experiment configs that run them.
- **Trend analysis**: Historical assessment queries that detect regression or improvement over time.
- **Squad health assessments**: Aggregate assessments across cycles to evaluate squad-level bottlenecks and handoff quality.
- **Experiment scheduling**: Cron-based experiment queue population for continuous regression detection.
