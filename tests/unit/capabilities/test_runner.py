"""
Unit tests for the WorkloadRunner.

Tests:
- DAG validation (unique task_id, refs exist, no cycles)
- Fail-fast behavior (independent task B not submitted if A fails)
- Input templating ({cycle_id}, {vars.x} resolve; unknown -> fail)
- Report paths are relative to run_root
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from squadops.capabilities.runner import WorkloadRunner, DAGValidationError
from squadops.capabilities.models import (
    AcceptanceCheck,
    CapabilityContract,
    CheckType,
    InputSpec,
    LifecycleScope,
    OutputSpec,
    TaskStatus,
    Trigger,
    Workload,
    WorkloadStatus,
    WorkloadTask,
)
from squadops.capabilities.exceptions import (
    ContractNotFoundError,
    TemplateResolutionError,
)
from squadops.ports.capabilities.repository import CapabilityRepository
from squadops.ports.capabilities.executor import CapabilityExecutor
from agents.tasks.models import TaskEnvelope, TaskResult


@pytest.fixture
def mock_repository():
    """Create a mock CapabilityRepository."""
    repo = MagicMock(spec=CapabilityRepository)
    return repo


@pytest.fixture
def mock_executor():
    """Create a mock CapabilityExecutor."""
    executor = MagicMock(spec=CapabilityExecutor)
    executor.executor_id = "test-executor"
    executor.execute = AsyncMock()
    return executor


@pytest.fixture
def run_root(tmp_path):
    """Create a temporary run root directory."""
    root = tmp_path / "run_root"
    root.mkdir()
    return root


@pytest.fixture
def sample_contract():
    """Create a sample capability contract."""
    return CapabilityContract(
        capability_id="data.test_capability",
        version="1.0.0",
        description="Test capability",
        owner_roles=("data",),
        lifecycle_scope=LifecycleScope.CYCLE,
        trigger=Trigger.ON_DEMAND,
        inputs=(
            InputSpec(name="cycle_id", type="string"),
        ),
        outputs=(
            OutputSpec(name="result_path", type="string"),
        ),
        timeout_seconds=60,
    )


@pytest.fixture
def simple_workload():
    """Create a simple workload with one task."""
    return Workload(
        workload_id="simple_workload",
        version="1.0.0",
        description="Simple test workload",
        tasks=(
            WorkloadTask(
                task_id="task1",
                capability_id="data.test_capability",
                inputs=(("cycle_id", "{cycle_id}"),),
            ),
        ),
    )


@pytest.fixture
def dag_workload():
    """Create a workload with DAG dependencies."""
    return Workload(
        workload_id="dag_workload",
        version="1.0.0",
        description="DAG test workload",
        tasks=(
            WorkloadTask(
                task_id="task_a",
                capability_id="data.test_capability",
                inputs=(("cycle_id", "{cycle_id}"),),
            ),
            WorkloadTask(
                task_id="task_b",
                capability_id="data.test_capability",
                inputs=(("cycle_id", "{cycle_id}"),),
                depends_on=("task_a",),
            ),
            WorkloadTask(
                task_id="task_c",
                capability_id="data.test_capability",
                inputs=(("cycle_id", "{cycle_id}"),),
                depends_on=("task_a",),
            ),
        ),
    )


class TestDAGValidation:
    """Tests for DAG validation in WorkloadRunner."""

    def test_valid_dag(self, mock_repository, mock_executor, run_root, dag_workload, sample_contract):
        """Valid DAG passes validation."""
        mock_repository.get_workload.return_value = dag_workload
        mock_repository.get_contract.return_value = sample_contract

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        # Should not raise
        runner._validate_dag(dag_workload)

    def test_duplicate_task_id_fails(self, mock_repository, mock_executor, run_root):
        """Duplicate task_id raises DAGValidationError."""
        workload = Workload(
            workload_id="bad_workload",
            version="1.0.0",
            description="Bad workload",
            tasks=(
                WorkloadTask(task_id="task1", capability_id="d.c"),
                WorkloadTask(task_id="task1", capability_id="d.c"),  # duplicate
            ),
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        with pytest.raises(DAGValidationError, match="Duplicate task_id"):
            runner._validate_dag(workload)

    def test_missing_dependency_fails(self, mock_repository, mock_executor, run_root):
        """Reference to non-existent task raises DAGValidationError."""
        workload = Workload(
            workload_id="bad_workload",
            version="1.0.0",
            description="Bad workload",
            tasks=(
                WorkloadTask(
                    task_id="task1",
                    capability_id="d.c",
                    depends_on=("missing_task",),  # doesn't exist
                ),
            ),
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        with pytest.raises(DAGValidationError, match="non-existent task"):
            runner._validate_dag(workload)

    def test_cycle_detection_simple(self, mock_repository, mock_executor, run_root):
        """Simple cycle (A -> B -> A) raises DAGValidationError."""
        workload = Workload(
            workload_id="cyclic_workload",
            version="1.0.0",
            description="Cyclic workload",
            tasks=(
                WorkloadTask(
                    task_id="task_a",
                    capability_id="d.c",
                    depends_on=("task_b",),
                ),
                WorkloadTask(
                    task_id="task_b",
                    capability_id="d.c",
                    depends_on=("task_a",),
                ),
            ),
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        with pytest.raises(DAGValidationError, match="[Cc]ycle"):
            runner._validate_dag(workload)

    def test_cycle_detection_complex(self, mock_repository, mock_executor, run_root):
        """Complex cycle (A -> B -> C -> A) raises DAGValidationError."""
        workload = Workload(
            workload_id="cyclic_workload",
            version="1.0.0",
            description="Cyclic workload",
            tasks=(
                WorkloadTask(
                    task_id="task_a",
                    capability_id="d.c",
                    depends_on=("task_c",),
                ),
                WorkloadTask(
                    task_id="task_b",
                    capability_id="d.c",
                    depends_on=("task_a",),
                ),
                WorkloadTask(
                    task_id="task_c",
                    capability_id="d.c",
                    depends_on=("task_b",),
                ),
            ),
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        with pytest.raises(DAGValidationError, match="[Cc]ycle"):
            runner._validate_dag(workload)


class TestTopologicalSort:
    """Tests for topological sorting of tasks."""

    def test_topological_order(self, mock_repository, mock_executor, run_root, dag_workload):
        """Tasks are returned in valid topological order."""
        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        sorted_tasks = runner._topological_sort(dag_workload)

        # task_a must come before task_b and task_c
        task_ids = [t.task_id for t in sorted_tasks]
        assert task_ids.index("task_a") < task_ids.index("task_b")
        assert task_ids.index("task_a") < task_ids.index("task_c")


class TestFailFastBehavior:
    """Tests for fail-fast execution semantics."""

    @pytest.mark.asyncio
    async def test_fail_fast_skips_remaining_tasks(
        self, mock_repository, mock_executor, run_root, dag_workload, sample_contract
    ):
        """When task_a fails, task_b and task_c are SKIPPED (not submitted)."""
        mock_repository.get_workload.return_value = dag_workload
        mock_repository.get_contract.return_value = sample_contract

        # task_a fails
        mock_executor.execute.return_value = TaskResult(
            task_id="task_a-xxx",
            status="FAILED",
            error="Simulated failure",
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        report = await runner.run(
            workload_id="dag_workload",
            cycle_id="test-cycle",
        )

        # Check that only task_a was executed (execute called once)
        assert mock_executor.execute.call_count == 1

        # Check task statuses
        task_statuses = {tr.task_id: tr.status for tr in report.task_records}
        assert task_statuses["task_a"] == TaskStatus.FAILED
        assert task_statuses["task_b"] == TaskStatus.SKIPPED
        assert task_statuses["task_c"] == TaskStatus.SKIPPED

        # Workload status should be FAILED
        assert report.status == WorkloadStatus.FAILED

    @pytest.mark.asyncio
    async def test_independent_tasks_skip_on_failure(
        self, mock_repository, mock_executor, run_root, sample_contract
    ):
        """Independent tasks are skipped when a prior task fails."""
        # Create workload with independent tasks (no dependencies)
        workload = Workload(
            workload_id="independent_workload",
            version="1.0.0",
            description="Independent tasks",
            tasks=(
                WorkloadTask(task_id="task_a", capability_id="data.test_capability"),
                WorkloadTask(task_id="task_b", capability_id="data.test_capability"),
            ),
        )

        mock_repository.get_workload.return_value = workload
        mock_repository.get_contract.return_value = sample_contract

        # task_a fails
        mock_executor.execute.return_value = TaskResult(
            task_id="task_a-xxx",
            status="FAILED",
            error="Simulated failure",
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        report = await runner.run(
            workload_id="independent_workload",
            cycle_id="test-cycle",
        )

        # Even though task_b has no dependency on task_a,
        # fail-fast means it's skipped
        task_statuses = {tr.task_id: tr.status for tr in report.task_records}
        assert task_statuses["task_a"] == TaskStatus.FAILED
        assert task_statuses["task_b"] == TaskStatus.SKIPPED


class TestInputTemplating:
    """Tests for task input template resolution."""

    @pytest.mark.asyncio
    async def test_cycle_id_resolution(
        self, mock_repository, mock_executor, run_root, simple_workload, sample_contract
    ):
        """Task inputs resolve {cycle_id}."""
        mock_repository.get_workload.return_value = simple_workload
        mock_repository.get_contract.return_value = sample_contract
        mock_executor.execute.return_value = TaskResult(
            task_id="task1-xxx",
            status="SUCCEEDED",
            outputs={"result_path": "path/to/result"},
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        await runner.run(
            workload_id="simple_workload",
            cycle_id="my-cycle-123",
        )

        # Check the envelope passed to execute
        call_args = mock_executor.execute.call_args
        envelope = call_args[0][0]
        assert envelope.inputs["cycle_id"] == "my-cycle-123"

    @pytest.mark.asyncio
    async def test_vars_resolution(
        self, mock_repository, mock_executor, run_root, sample_contract
    ):
        """Task inputs resolve {vars.name}."""
        workload = Workload(
            workload_id="vars_workload",
            version="1.0.0",
            description="Vars test",
            tasks=(
                WorkloadTask(
                    task_id="task1",
                    capability_id="data.test_capability",
                    inputs=(("env", "{vars.environment}"),),
                ),
            ),
            vars=(("environment", "production"),),
        )

        mock_repository.get_workload.return_value = workload
        mock_repository.get_contract.return_value = sample_contract
        mock_executor.execute.return_value = TaskResult(
            task_id="task1-xxx",
            status="SUCCEEDED",
            outputs={},
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        await runner.run(
            workload_id="vars_workload",
            cycle_id="test-cycle",
        )

        call_args = mock_executor.execute.call_args
        envelope = call_args[0][0]
        assert envelope.inputs["env"] == "production"

    @pytest.mark.asyncio
    async def test_task_output_resolution(
        self, mock_repository, mock_executor, run_root, sample_contract
    ):
        """Task inputs resolve {task_id.output_name}."""
        workload = Workload(
            workload_id="output_workload",
            version="1.0.0",
            description="Output resolution test",
            tasks=(
                WorkloadTask(
                    task_id="producer",
                    capability_id="data.test_capability",
                ),
                WorkloadTask(
                    task_id="consumer",
                    capability_id="data.test_capability",
                    inputs=(("input_path", "{producer.result_path}"),),
                    depends_on=("producer",),
                ),
            ),
        )

        mock_repository.get_workload.return_value = workload
        mock_repository.get_contract.return_value = sample_contract

        # First call (producer) returns result_path
        # Second call (consumer) succeeds
        mock_executor.execute.side_effect = [
            TaskResult(
                task_id="producer-xxx",
                status="SUCCEEDED",
                outputs={"result_path": "/output/data.json"},
            ),
            TaskResult(
                task_id="consumer-xxx",
                status="SUCCEEDED",
                outputs={},
            ),
        ]

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        await runner.run(
            workload_id="output_workload",
            cycle_id="test-cycle",
        )

        # Check consumer received resolved input
        assert mock_executor.execute.call_count == 2
        consumer_envelope = mock_executor.execute.call_args_list[1][0][0]
        assert consumer_envelope.inputs["input_path"] == "/output/data.json"

    @pytest.mark.asyncio
    async def test_unknown_variable_fails(
        self, mock_repository, mock_executor, run_root, sample_contract
    ):
        """Unknown template variable causes task failure."""
        workload = Workload(
            workload_id="bad_template",
            version="1.0.0",
            description="Bad template test",
            tasks=(
                WorkloadTask(
                    task_id="task1",
                    capability_id="data.test_capability",
                    inputs=(("value", "{unknown_var}"),),
                ),
            ),
        )

        mock_repository.get_workload.return_value = workload
        mock_repository.get_contract.return_value = sample_contract

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        report = await runner.run(
            workload_id="bad_template",
            cycle_id="test-cycle",
        )

        # Task should fail due to template resolution error
        assert report.task_records[0].status == TaskStatus.FAILED
        assert "template" in report.task_records[0].failure.error_type.lower()


class TestReportGeneration:
    """Tests for workload run report generation."""

    @pytest.mark.asyncio
    async def test_report_written_to_correct_location(
        self, mock_repository, mock_executor, run_root, simple_workload, sample_contract
    ):
        """Report is written to {run_root}/runs/<cycle_id>/workloads/<workload_id>/."""
        mock_repository.get_workload.return_value = simple_workload
        mock_repository.get_contract.return_value = sample_contract
        mock_executor.execute.return_value = TaskResult(
            task_id="task1-xxx",
            status="SUCCEEDED",
            outputs={},
        )

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        await runner.run(
            workload_id="simple_workload",
            cycle_id="test-cycle-456",
        )

        expected_path = (
            run_root
            / "runs"
            / "test-cycle-456"
            / "workloads"
            / "simple_workload"
            / "workload_run_report.json"
        )
        assert expected_path.exists()

        # Verify report content
        with open(expected_path) as f:
            report_data = json.load(f)
        assert report_data["workload_id"] == "simple_workload"
        assert report_data["cycle_id"] == "test-cycle-456"

    @pytest.mark.asyncio
    async def test_report_emitted_on_early_failure(
        self, mock_repository, mock_executor, run_root
    ):
        """Report is emitted even when workload fails to load."""
        mock_repository.get_workload.side_effect = Exception("Load failed")

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        report = await runner.run(
            workload_id="nonexistent",
            cycle_id="test-cycle",
        )

        assert report.status == WorkloadStatus.FAILED
        assert report.failure is not None
        assert "Load failed" in report.failure.message

        # Report file should exist
        report_path = (
            run_root
            / "runs"
            / "test-cycle"
            / "workloads"
            / "nonexistent"
            / "workload_run_report.json"
        )
        assert report_path.exists()

    @pytest.mark.asyncio
    async def test_report_contains_metrics(
        self, mock_repository, mock_executor, run_root, dag_workload, sample_contract
    ):
        """Report includes headline metrics."""
        mock_repository.get_workload.return_value = dag_workload
        mock_repository.get_contract.return_value = sample_contract

        # First task succeeds, then execution fails (causing skip)
        mock_executor.execute.side_effect = [
            TaskResult(task_id="task_a-xxx", status="SUCCEEDED", outputs={}),
            TaskResult(task_id="task_b-xxx", status="FAILED", error="Error"),
        ]

        runner = WorkloadRunner(
            repository=mock_repository,
            executors={"test": mock_executor},
            run_root=run_root,
        )

        report = await runner.run(
            workload_id="dag_workload",
            cycle_id="test-cycle",
        )

        assert report.metrics is not None
        assert report.metrics.total_tasks == 3
        assert report.metrics.succeeded == 1
        assert report.metrics.failed == 1
        assert report.metrics.skipped == 1
