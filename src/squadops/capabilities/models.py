"""
Domain models for the capability contracts system.

All models are immutable (frozen dataclasses) to ensure deterministic
behavior and prevent accidental mutation during execution.

Per SIP-0.8.6 v1 semantics:
- Inputs/outputs are limited to primitives: string, number, boolean
- Template field addressing uses dot-path notation
- Type comparison is strict
"""

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class CheckType(StrEnum):
    """Acceptance check types supported in v1."""

    FILE_EXISTS = "file_exists"
    NON_EMPTY = "non_empty"
    JSON_FIELD_EQUALS = "json_field_equals"
    HTTP_STATUS = "http_status"
    PROCESS_RUNNING = "process_running"
    JSON_SCHEMA = "json_schema"
    COMMAND_EXIT_CODE = "command_exit_code"


class LifecycleScope(StrEnum):
    """Capability lifecycle scope."""

    CYCLE = "cycle"
    PULSE = "pulse"
    PROJECT = "project"


class Trigger(StrEnum):
    """When the capability is expected to be invoked."""

    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"


class TaskStatus(StrEnum):
    """Status of a task within a workload run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class WorkloadStatus(StrEnum):
    """Overall status of a workload run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# =============================================================================
# Primitive Type Validation
# =============================================================================

# v1 primitives: string, number, boolean
PRIMITIVE_TYPES = {"string", "number", "boolean"}


def _validate_primitive_type(type_name: str, context: str) -> None:
    """Validate that a type name is a v1 primitive."""
    if type_name not in PRIMITIVE_TYPES:
        raise ValueError(f"{context}: type must be one of {PRIMITIVE_TYPES}, got '{type_name}'")


def _validate_primitive_value(value: Any, expected_type: str) -> bool:
    """
    Strictly validate a value against an expected primitive type.

    Returns True if value matches type, False otherwise.
    Type checking is strict: int is not a valid number (only float is).
    """
    if expected_type == "string":
        return isinstance(value, str)
    elif expected_type == "number":
        # In JSON/Python, numbers can be int or float
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected_type == "boolean":
        return isinstance(value, bool)
    return False


# =============================================================================
# Contract Models
# =============================================================================


@dataclass(frozen=True)
class InputSpec:
    """
    Specification for a capability input parameter.

    Attributes:
        name: Parameter name (must be unique within contract)
        type: Primitive type (string, number, boolean)
        required: Whether this input is mandatory
        description: Human-readable description
    """

    name: str
    type: str
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """Validate input spec on creation."""
        _validate_primitive_type(self.type, f"InputSpec '{self.name}'")


@dataclass(frozen=True)
class OutputSpec:
    """
    Specification for a capability output value.

    Attributes:
        name: Output name (must be unique within contract)
        type: Primitive type (string, number, boolean)
        description: Human-readable description
    """

    name: str
    type: str
    description: str = ""

    def __post_init__(self) -> None:
        """Validate output spec on creation."""
        _validate_primitive_type(self.type, f"OutputSpec '{self.name}'")


@dataclass(frozen=True)
class ArtifactSpec:
    """
    Specification for a capability artifact (file output).

    Attributes:
        name: Artifact name (used in acceptance checks and references)
        path_template: Template for artifact path, supports {variable} syntax
        description: Human-readable description
    """

    name: str
    path_template: str
    description: str = ""


@dataclass(frozen=True)
class AcceptanceCheck:
    """
    Acceptance check definition for validating artifacts.

    Attributes:
        check_type: Type of check (file_exists, non_empty, json_field_equals,
            http_status, process_running, json_schema, command_exit_code)
        target: Path template for the artifact to check
        field_path: Dot-path for json_field_equals (e.g., "metadata.status")
        expected_value: Expected value for json_field_equals (primitives only)
        description: Human-readable description of what this check validates
        url: URL template for http_status checks
        expected_status: Expected HTTP status code for http_status checks
        container_name: Docker container name for process_running checks
        command: Command argv tuple for command_exit_code checks
        expected_exit_code: Expected exit code (default 0)
        cwd: Working directory for command_exit_code (relative path only)
        env: Allowlist-only env vars for command_exit_code (no host env inheritance)
        schema: Relative path to JSON schema file for json_schema checks
    """

    check_type: CheckType
    target: str
    field_path: str | None = None
    expected_value: Any = None
    description: str = ""
    url: str | None = None
    expected_status: int | None = None
    container_name: str | None = None
    command: tuple[str, ...] | None = None
    expected_exit_code: int = 0
    cwd: str | None = None
    env: tuple[tuple[str, str], ...] = ()
    schema: str | None = None

    def __post_init__(self) -> None:
        """Validate acceptance check on creation."""
        if self.check_type == CheckType.JSON_FIELD_EQUALS:
            if not self.field_path:
                raise ValueError("json_field_equals check requires field_path")
            if self.expected_value is None:
                raise ValueError("json_field_equals check requires expected_value")
            # Validate expected_value is a primitive
            if not isinstance(self.expected_value, (str, int, float, bool)):
                raise ValueError(
                    f"expected_value must be a primitive, got {type(self.expected_value).__name__}"
                )
        elif self.check_type == CheckType.HTTP_STATUS:
            if not self.url:
                raise ValueError("http_status check requires url")
            if self.expected_status is None:
                raise ValueError("http_status check requires expected_status")
        elif self.check_type == CheckType.PROCESS_RUNNING:
            if not self.container_name:
                raise ValueError("process_running check requires container_name")
        elif self.check_type == CheckType.JSON_SCHEMA:
            if not self.target:
                raise ValueError("json_schema check requires target (document path)")
            if not self.schema:
                raise ValueError("json_schema check requires schema (schema path)")
            if os.path.isabs(self.schema):
                raise ValueError(
                    f"json_schema schema path must be relative, got absolute: {self.schema}"
                )
        elif self.check_type == CheckType.COMMAND_EXIT_CODE:
            if not self.command or len(self.command) == 0:
                raise ValueError("command_exit_code check requires non-empty command tuple")
            if self.cwd is not None:
                if os.path.isabs(self.cwd):
                    raise ValueError(
                        f"command_exit_code cwd must be relative, got absolute: {self.cwd}"
                    )
                if ".." in PurePosixPath(self.cwd).parts:
                    raise ValueError(
                        f"command_exit_code cwd must not contain '..' segments: {self.cwd}"
                    )


@dataclass(frozen=True)
class CapabilityContract:
    """
    Capability contract defining delivery expectations.

    The contract specifies what a capability accepts as input, what it
    produces as output and artifacts, and how to validate successful
    delivery through acceptance checks.

    Attributes:
        capability_id: Unique identifier (e.g., "data.collect_cycle_snapshot")
        version: Semantic version of the contract
        description: Human-readable description
        owner_roles: Agent roles that can fulfill this capability
        lifecycle_scope: Scope of the capability (cycle, pulse, project)
        trigger: When the capability is invoked
        inputs: Input parameter specifications
        outputs: Output value specifications
        artifacts: Artifact (file) specifications
        acceptance_checks: Validation checks for artifacts
        timeout_seconds: Maximum execution time
    """

    capability_id: str
    version: str
    description: str
    owner_roles: tuple[str, ...]
    lifecycle_scope: LifecycleScope
    trigger: Trigger
    inputs: tuple[InputSpec, ...] = field(default_factory=tuple)
    outputs: tuple[OutputSpec, ...] = field(default_factory=tuple)
    artifacts: tuple[ArtifactSpec, ...] = field(default_factory=tuple)
    acceptance_checks: tuple[AcceptanceCheck, ...] = field(default_factory=tuple)
    timeout_seconds: int = 300

    def get_input_spec(self, name: str) -> InputSpec | None:
        """Get input spec by name."""
        for spec in self.inputs:
            if spec.name == name:
                return spec
        return None

    def get_output_spec(self, name: str) -> OutputSpec | None:
        """Get output spec by name."""
        for spec in self.outputs:
            if spec.name == name:
                return spec
        return None

    def get_artifact_spec(self, name: str) -> ArtifactSpec | None:
        """Get artifact spec by name."""
        for spec in self.artifacts:
            if spec.name == name:
                return spec
        return None


# =============================================================================
# Workload Models
# =============================================================================


@dataclass(frozen=True)
class WorkloadTask:
    """
    A task within a workload, referencing a capability contract.

    Attributes:
        task_id: Unique identifier within the workload
        capability_id: Reference to a capability contract
        inputs: Input values (may contain {variable} templates)
        depends_on: Task IDs this task depends on (for DAG ordering)
        executor_override: Optional executor to use instead of default
    """

    task_id: str
    capability_id: str
    inputs: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    executor_override: str | None = None

    def get_input(self, name: str) -> Any:
        """Get input value by name."""
        for key, value in self.inputs:
            if key == name:
                return value
        return None


@dataclass(frozen=True)
class Workload:
    """
    A workload composing multiple capabilities into a DAG.

    Attributes:
        workload_id: Unique identifier
        version: Semantic version
        description: Human-readable description
        tasks: Ordered sequence of tasks
        vars: Global variables available for template resolution
        acceptance_checks: Workload-level acceptance checks (run after all tasks)
    """

    workload_id: str
    version: str
    description: str
    tasks: tuple[WorkloadTask, ...]
    vars: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    acceptance_checks: tuple[AcceptanceCheck, ...] = field(default_factory=tuple)

    def get_task(self, task_id: str) -> WorkloadTask | None:
        """Get task by ID."""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_var(self, name: str) -> Any:
        """Get variable value by name."""
        for key, value in self.vars:
            if key == name:
                return value
        return None


# =============================================================================
# Report Models
# =============================================================================


@dataclass(frozen=True)
class AcceptanceContext:
    """
    Context for resolving acceptance check templates.

    Attributes:
        run_root: Root directory for the run
        cycle_id: Current cycle identifier
        workload_id: Workload being executed
        task_outputs: Mapping of task_id -> outputs dict
        vars: Workload-level variables
    """

    run_root: str
    cycle_id: str
    workload_id: str
    task_outputs: tuple[tuple[str, dict[str, Any]], ...] = field(default_factory=tuple)
    vars: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    run_id: str = ""

    def get_task_output(self, task_id: str, output_name: str) -> Any:
        """Get a specific output from a task."""
        for tid, outputs in self.task_outputs:
            if tid == task_id:
                return outputs.get(output_name)
        return None

    def get_var(self, name: str) -> Any:
        """Get variable value by name."""
        for key, value in self.vars:
            if key == name:
                return value
        return None


@dataclass(frozen=True)
class AcceptanceResult:
    """
    Result of evaluating a single acceptance check.

    Attributes:
        check: The acceptance check that was evaluated
        passed: Whether the check passed
        resolved_path: The resolved path after template substitution
        actual_value: Actual value found (for json_field_equals)
        error: Error message if check failed
    """

    check: AcceptanceCheck
    passed: bool
    resolved_path: str
    actual_value: Any = None
    error: str | None = None
    reason_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    """
    Report of all acceptance check results for a task or workload.

    Attributes:
        results: All acceptance check results
        all_passed: Whether all checks passed
    """

    results: tuple[AcceptanceResult, ...]

    @property
    def all_passed(self) -> bool:
        """Check if all results passed."""
        return all(r.passed for r in self.results)


@dataclass(frozen=True)
class FailureRecord:
    """
    Record of a task or workload failure.

    Attributes:
        error_type: Type of error (e.g., "timeout", "execution_error")
        message: Error message
        timestamp: When the failure occurred
    """

    error_type: str
    message: str
    timestamp: str


@dataclass(frozen=True)
class TaskRecord:
    """
    Record of a task execution within a workload run.

    Attributes:
        task_id: Task identifier
        capability_id: Capability contract that was invoked
        status: Final task status
        started_at: When execution started (ISO timestamp)
        completed_at: When execution completed (ISO timestamp)
        task_result_ref: Relative path to task result file
        artifact_refs: Relative paths to produced artifacts
        acceptance_results: Results of acceptance checks
        failure: Failure details if task failed
    """

    task_id: str
    capability_id: str
    status: TaskStatus
    started_at: str | None = None
    completed_at: str | None = None
    task_result_ref: str | None = None
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    acceptance_results: tuple[AcceptanceResult, ...] = field(default_factory=tuple)
    failure: FailureRecord | None = None


@dataclass(frozen=True)
class HeadlineMetrics:
    """
    High-level metrics for a workload run.

    Attributes:
        total_tasks: Total number of tasks in workload
        succeeded: Number of succeeded tasks
        failed: Number of failed tasks
        skipped: Number of skipped tasks
        duration_seconds: Total execution duration
    """

    total_tasks: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float


@dataclass(frozen=True)
class WorkloadRunReport:
    """
    Complete report for a workload run.

    Per SIP-0.8.6, the report is always emitted at:
    {run_root}/runs/<cycle_id>/workloads/<workload_id>/workload_run_report.json

    All paths in task_result_ref and artifact_refs are RELATIVE to run_root.

    Attributes:
        workload_id: Workload that was executed
        cycle_id: Cycle identifier
        status: Overall workload status
        started_at: When execution started (ISO timestamp)
        completed_at: When execution completed (ISO timestamp)
        task_records: Records of all task executions
        workload_acceptance_results: Results of workload-level acceptance checks
        metrics: Headline metrics
        failure: Workload-level failure if applicable
    """

    workload_id: str
    cycle_id: str
    status: WorkloadStatus
    started_at: str
    completed_at: str
    task_records: tuple[TaskRecord, ...]
    workload_acceptance_results: tuple[AcceptanceResult, ...] = field(default_factory=tuple)
    metrics: HeadlineMetrics | None = None
    failure: FailureRecord | None = None
