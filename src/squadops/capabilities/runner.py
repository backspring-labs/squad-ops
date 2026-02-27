"""
Workload Runner for executing capability DAGs.

Implements SIP-0.8.6 workload execution semantics:
- Load and validate workloads against schema
- DAG validation (unique task_id, refs exist, no cycles)
- Fail-fast behavior (no further submissions after failure)
- Report generation (always emitted, even on early failure)
"""

import json
import logging
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from squadops.capabilities.acceptance import AcceptanceCheckEngine
from squadops.capabilities.exceptions import (
    ContractNotFoundError,
    ContractValidationError,
    TemplateResolutionError,
)
from squadops.capabilities.models import (
    AcceptanceContext,
    AcceptanceResult,
    CapabilityContract,
    FailureRecord,
    HeadlineMetrics,
    TaskRecord,
    TaskStatus,
    Workload,
    WorkloadRunReport,
    WorkloadStatus,
    WorkloadTask,
)
from squadops.ports.capabilities.executor import CapabilityExecutor
from squadops.ports.capabilities.repository import CapabilityRepository

# Import ACI models from core domain (SIP-0.8.8 migration)
from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


class DAGValidationError(ContractValidationError):
    """Raised when workload DAG validation fails."""

    pass


class WorkloadRunner:
    """
    Runner for executing workloads as capability DAGs.

    Execution algorithm:
    1. Load workload, validate schema -> emit report on failure, halt
    2. DAG validation (unique task_id, refs exist, no cycles)
    3. Load/validate contracts
    4. Executor resolution (workload override -> contract roles -> availability)
    5. For each task in topological order:
       - Build AcceptanceContext
       - Resolve task inputs via template resolution
       - Construct TaskEnvelope, submit, await result
       - On failure: halt all further submissions, mark remaining as SKIPPED
    6. Evaluate acceptance checks for produced artifacts (no short-circuit)
    7. Evaluate workload-level acceptance_checks (if present)
    8. Generate WorkloadRunReport (always emitted)
    """

    def __init__(
        self,
        repository: CapabilityRepository,
        executors: dict[str, CapabilityExecutor],
        run_root: Path | str,
        default_executor: str | None = None,
    ):
        """
        Initialize the workload runner.

        Args:
            repository: CapabilityRepository for loading contracts/workloads
            executors: Mapping of executor_id -> CapabilityExecutor
            run_root: Root directory for run artifacts and reports
            default_executor: Default executor ID to use when not specified
        """
        self.repository = repository
        self.executors = executors
        self.run_root = Path(run_root)
        self.default_executor = default_executor or next(iter(executors.keys()), None)

    def _validate_dag(self, workload: Workload) -> None:
        """
        Validate the workload DAG structure.

        Checks:
        1. Unique task_ids
        2. All depends_on references exist
        3. No cycles

        Raises:
            DAGValidationError: If validation fails
        """
        task_ids = set()
        task_map: dict[str, WorkloadTask] = {}

        # Check unique task_ids
        for task in workload.tasks:
            if task.task_id in task_ids:
                raise DAGValidationError(
                    f"Duplicate task_id: {task.task_id}",
                    {"workload_id": workload.workload_id, "task_id": task.task_id},
                )
            task_ids.add(task.task_id)
            task_map[task.task_id] = task

        # Check depends_on references exist
        for task in workload.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise DAGValidationError(
                        f"Task '{task.task_id}' depends on non-existent task '{dep}'",
                        {"task_id": task.task_id, "missing_dependency": dep},
                    )

        # Check for cycles using Kahn's algorithm
        in_degree: dict[str, int] = {tid: 0 for tid in task_ids}
        for task in workload.tasks:
            for _dep in task.depends_on:
                in_degree[task.task_id] = in_degree.get(task.task_id, 0) + 1

        # Start with tasks that have no dependencies
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        visited = 0

        while queue:
            current = queue.popleft()
            visited += 1

            # Find tasks that depend on current
            for task in workload.tasks:
                if current in task.depends_on:
                    in_degree[task.task_id] -= 1
                    if in_degree[task.task_id] == 0:
                        queue.append(task.task_id)

        if visited != len(task_ids):
            raise DAGValidationError(
                "Cycle detected in workload DAG",
                {"workload_id": workload.workload_id},
            )

    def _topological_sort(self, workload: Workload) -> list[WorkloadTask]:
        """
        Return tasks in topological order (dependencies first).

        Assumes DAG has already been validated (no cycles).
        """
        task_map = {t.task_id: t for t in workload.tasks}
        in_degree: dict[str, int] = {t.task_id: len(t.depends_on) for t in workload.tasks}

        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(task_map[current])

            for task in workload.tasks:
                if current in task.depends_on:
                    in_degree[task.task_id] -= 1
                    if in_degree[task.task_id] == 0:
                        queue.append(task.task_id)

        return result

    def _resolve_executor(
        self, task: WorkloadTask, contract: CapabilityContract
    ) -> CapabilityExecutor:
        """
        Resolve the executor to use for a task.

        Resolution order:
        1. Task-level executor_override
        2. Default executor
        3. First available executor

        Raises:
            ContractValidationError: If no executor available
        """
        # Task-level override
        if task.executor_override and task.executor_override in self.executors:
            return self.executors[task.executor_override]

        # Default executor
        if self.default_executor and self.default_executor in self.executors:
            return self.executors[self.default_executor]

        # First available
        if self.executors:
            return next(iter(self.executors.values()))

        raise ContractValidationError(
            f"No executor available for task '{task.task_id}'",
            {"task_id": task.task_id, "capability_id": task.capability_id},
        )

    def _resolve_task_inputs(
        self,
        task: WorkloadTask,
        context: AcceptanceContext,
        engine: AcceptanceCheckEngine,
    ) -> dict[str, Any]:
        """
        Resolve template variables in task inputs.

        Supports:
        - {cycle_id}, {workload_id}, {run_root}
        - {vars.name}
        - {task_id.output_name}

        Raises:
            TemplateResolutionError: If variable cannot be resolved
        """
        resolved = {}
        for name, value in task.inputs:
            if isinstance(value, str) and "{" in value:
                resolved[name] = engine.resolve_template(value, context)
            else:
                resolved[name] = value
        return resolved

    def _build_envelope(
        self,
        task: WorkloadTask,
        contract: CapabilityContract,
        inputs: dict[str, Any],
        cycle_id: str,
        project_id: str,
        pulse_id: str,
    ) -> TaskEnvelope:
        """Build a TaskEnvelope for task execution."""
        # Select first owner role as agent
        agent_id = contract.owner_roles[0] if contract.owner_roles else "unknown"

        return TaskEnvelope(
            task_id=f"{task.task_id}-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            cycle_id=cycle_id,
            pulse_id=pulse_id,
            project_id=project_id,
            task_type=contract.capability_id,
            inputs=inputs,
            correlation_id=cycle_id,
            causation_id=task.task_id,
            trace_id=str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            timeout=float(contract.timeout_seconds),
            metadata={"workload_task_id": task.task_id},
        )

    def _create_failure_record(self, error_type: str, message: str) -> FailureRecord:
        """Create a failure record with current timestamp."""
        return FailureRecord(
            error_type=error_type,
            message=message,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def _acceptance_result_to_dict(self, result: AcceptanceResult) -> dict:
        """Convert AcceptanceResult to dictionary for JSON serialization."""
        return {
            "check_type": result.check.check_type.value,
            "target": result.check.target,
            "passed": result.passed,
            "resolved_path": result.resolved_path,
            "actual_value": result.actual_value,
            "error": result.error,
        }

    def _make_path_relative(self, path: str) -> str:
        """
        Make an absolute path relative to run_root.

        Per SIP-0.8.6, all paths in reports are relative to run_root.
        """
        try:
            abs_path = Path(path)
            if abs_path.is_absolute():
                return str(abs_path.relative_to(self.run_root))
        except (ValueError, TypeError):
            pass
        return path

    def _write_report(self, report: WorkloadRunReport, cycle_id: str, workload_id: str) -> Path:
        """
        Write the workload run report to disk.

        Location: {run_root}/runs/<cycle_id>/workloads/<workload_id>/workload_run_report.json
        """
        report_dir = self.run_root / "runs" / cycle_id / "workloads" / workload_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "workload_run_report.json"

        # Convert to dict for JSON serialization
        report_dict = {
            "workload_id": report.workload_id,
            "cycle_id": report.cycle_id,
            "status": report.status.value,
            "started_at": report.started_at,
            "completed_at": report.completed_at,
            "task_records": [
                {
                    "task_id": tr.task_id,
                    "capability_id": tr.capability_id,
                    "status": tr.status.value,
                    "started_at": tr.started_at,
                    "completed_at": tr.completed_at,
                    "task_result_ref": tr.task_result_ref,
                    "artifact_refs": list(tr.artifact_refs),
                    "acceptance_results": [
                        self._acceptance_result_to_dict(ar) for ar in tr.acceptance_results
                    ],
                    "failure": (
                        {
                            "error_type": tr.failure.error_type,
                            "message": tr.failure.message,
                            "timestamp": tr.failure.timestamp,
                        }
                        if tr.failure
                        else None
                    ),
                }
                for tr in report.task_records
            ],
            "workload_acceptance_results": [
                self._acceptance_result_to_dict(ar) for ar in report.workload_acceptance_results
            ],
            "metrics": (
                {
                    "total_tasks": report.metrics.total_tasks,
                    "succeeded": report.metrics.succeeded,
                    "failed": report.metrics.failed,
                    "skipped": report.metrics.skipped,
                    "duration_seconds": report.metrics.duration_seconds,
                }
                if report.metrics
                else None
            ),
            "failure": (
                {
                    "error_type": report.failure.error_type,
                    "message": report.failure.message,
                    "timestamp": report.failure.timestamp,
                }
                if report.failure
                else None
            ),
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)

        logger.info(f"Wrote workload run report to {report_path}")
        return report_path

    async def run(
        self,
        workload_id: str,
        cycle_id: str,
        project_id: str = "default",
        pulse_id: str | None = None,
        extra_vars: dict[str, Any] | None = None,
    ) -> WorkloadRunReport:
        """
        Execute a workload and return the run report.

        The report is always written to disk, even on early failure.

        Args:
            workload_id: ID of the workload to execute
            cycle_id: Cycle identifier for this run
            project_id: Project identifier
            pulse_id: Pulse identifier (defaults to cycle_id)
            extra_vars: Additional variables to merge with workload vars

        Returns:
            WorkloadRunReport with execution results
        """
        started_at = datetime.now(UTC).isoformat()
        pulse_id = pulse_id or cycle_id
        task_records: list[TaskRecord] = []
        task_outputs: dict[str, dict[str, Any]] = {}
        workload_failure: FailureRecord | None = None
        halt_execution = False

        # Load workload
        try:
            workload = self.repository.get_workload(workload_id)
        except Exception as e:
            logger.error(f"Failed to load workload {workload_id}: {e}")
            workload_failure = self._create_failure_record("workload_load_error", str(e))
            return self._emit_early_failure_report(
                workload_id, cycle_id, started_at, workload_failure
            )

        # Validate DAG
        try:
            self._validate_dag(workload)
        except DAGValidationError as e:
            logger.error(f"DAG validation failed: {e}")
            workload_failure = self._create_failure_record("dag_validation_error", str(e))
            return self._emit_early_failure_report(
                workload_id, cycle_id, started_at, workload_failure
            )

        # Load contracts
        contracts: dict[str, CapabilityContract] = {}
        for task in workload.tasks:
            try:
                contracts[task.capability_id] = self.repository.get_contract(task.capability_id)
            except ContractNotFoundError as e:
                logger.error(f"Contract not found: {e}")
                workload_failure = self._create_failure_record("contract_not_found", str(e))
                return self._emit_early_failure_report(
                    workload_id, cycle_id, started_at, workload_failure
                )

        # Build acceptance engine and context
        engine = AcceptanceCheckEngine(self.run_root)

        # Merge workload vars with extra vars
        merged_vars = dict(workload.vars)
        if extra_vars:
            merged_vars.update(extra_vars)
        vars_tuple = tuple(merged_vars.items())

        # Get topological order
        sorted_tasks = self._topological_sort(workload)

        # Execute tasks
        for task in sorted_tasks:
            if halt_execution:
                # Mark remaining tasks as SKIPPED
                task_records.append(
                    TaskRecord(
                        task_id=task.task_id,
                        capability_id=task.capability_id,
                        status=TaskStatus.SKIPPED,
                    )
                )
                continue

            contract = contracts[task.capability_id]
            executor = self._resolve_executor(task, contract)

            # Build context with current outputs
            context = AcceptanceContext(
                run_root=str(self.run_root),
                cycle_id=cycle_id,
                workload_id=workload_id,
                task_outputs=tuple(task_outputs.items()),
                vars=vars_tuple,
            )

            # Resolve task inputs
            try:
                resolved_inputs = self._resolve_task_inputs(task, context, engine)
            except TemplateResolutionError as e:
                logger.error(f"Failed to resolve inputs for task {task.task_id}: {e}")
                task_records.append(
                    TaskRecord(
                        task_id=task.task_id,
                        capability_id=task.capability_id,
                        status=TaskStatus.FAILED,
                        failure=self._create_failure_record("template_resolution_error", str(e)),
                    )
                )
                halt_execution = True
                continue

            # Build envelope and execute
            envelope = self._build_envelope(
                task, contract, resolved_inputs, cycle_id, project_id, pulse_id
            )

            task_started_at = datetime.now(UTC).isoformat()

            try:
                result = await executor.execute(envelope, timeout_seconds=contract.timeout_seconds)
                task_completed_at = datetime.now(UTC).isoformat()

                if result.status == "SUCCEEDED":
                    # Store outputs for downstream tasks
                    task_outputs[task.task_id] = result.outputs or {}

                    # Evaluate acceptance checks
                    context = AcceptanceContext(
                        run_root=str(self.run_root),
                        cycle_id=cycle_id,
                        workload_id=workload_id,
                        task_outputs=tuple(task_outputs.items()),
                        vars=vars_tuple,
                    )
                    validation = engine.evaluate_all(contract.acceptance_checks, context)

                    task_records.append(
                        TaskRecord(
                            task_id=task.task_id,
                            capability_id=task.capability_id,
                            status=TaskStatus.SUCCEEDED,
                            started_at=task_started_at,
                            completed_at=task_completed_at,
                            acceptance_results=validation.results,
                        )
                    )

                    # If acceptance checks failed, halt
                    if not validation.all_passed:
                        logger.warning(f"Task {task.task_id} acceptance checks failed")
                        halt_execution = True

                else:
                    # Task failed
                    task_records.append(
                        TaskRecord(
                            task_id=task.task_id,
                            capability_id=task.capability_id,
                            status=TaskStatus.FAILED,
                            started_at=task_started_at,
                            completed_at=task_completed_at,
                            failure=self._create_failure_record(
                                "execution_error", result.error or "Unknown error"
                            ),
                        )
                    )
                    halt_execution = True

            except TimeoutError as e:
                task_completed_at = datetime.now(UTC).isoformat()
                task_records.append(
                    TaskRecord(
                        task_id=task.task_id,
                        capability_id=task.capability_id,
                        status=TaskStatus.TIMED_OUT,
                        started_at=task_started_at,
                        completed_at=task_completed_at,
                        failure=self._create_failure_record("timeout", str(e)),
                    )
                )
                halt_execution = True

            except Exception as e:
                task_completed_at = datetime.now(UTC).isoformat()
                task_records.append(
                    TaskRecord(
                        task_id=task.task_id,
                        capability_id=task.capability_id,
                        status=TaskStatus.FAILED,
                        started_at=task_started_at,
                        completed_at=task_completed_at,
                        failure=self._create_failure_record("execution_error", str(e)),
                    )
                )
                halt_execution = True

        # Evaluate workload-level acceptance checks
        workload_acceptance_results: tuple[AcceptanceResult, ...] = ()
        if workload.acceptance_checks and not halt_execution:
            context = AcceptanceContext(
                run_root=str(self.run_root),
                cycle_id=cycle_id,
                workload_id=workload_id,
                task_outputs=tuple(task_outputs.items()),
                vars=vars_tuple,
            )
            validation = engine.evaluate_all(workload.acceptance_checks, context)
            workload_acceptance_results = validation.results

        # Compute metrics
        completed_at = datetime.now(UTC).isoformat()
        succeeded = sum(1 for tr in task_records if tr.status == TaskStatus.SUCCEEDED)
        failed = sum(
            1
            for tr in task_records
            if tr.status in (TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.REJECTED)
        )
        skipped = sum(1 for tr in task_records if tr.status == TaskStatus.SKIPPED)

        # Parse timestamps for duration
        try:
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            duration = (end_dt - start_dt).total_seconds()
        except (ValueError, TypeError):
            duration = 0.0

        metrics = HeadlineMetrics(
            total_tasks=len(task_records),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration,
        )

        # Determine overall status
        if workload_failure:
            status = WorkloadStatus.FAILED
        elif failed > 0 or (
            workload_acceptance_results and not all(r.passed for r in workload_acceptance_results)
        ):
            status = WorkloadStatus.FAILED
        elif skipped > 0:
            status = WorkloadStatus.FAILED  # Fail-fast means failure
        else:
            status = WorkloadStatus.SUCCEEDED

        # Build report
        report = WorkloadRunReport(
            workload_id=workload_id,
            cycle_id=cycle_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            task_records=tuple(task_records),
            workload_acceptance_results=workload_acceptance_results,
            metrics=metrics,
            failure=workload_failure,
        )

        # Write report
        self._write_report(report, cycle_id, workload_id)

        return report

    def _emit_early_failure_report(
        self,
        workload_id: str,
        cycle_id: str,
        started_at: str,
        failure: FailureRecord,
    ) -> WorkloadRunReport:
        """Emit a failure report when execution cannot proceed."""
        completed_at = datetime.now(UTC).isoformat()

        report = WorkloadRunReport(
            workload_id=workload_id,
            cycle_id=cycle_id,
            status=WorkloadStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            task_records=(),
            failure=failure,
        )

        self._write_report(report, cycle_id, workload_id)
        return report
