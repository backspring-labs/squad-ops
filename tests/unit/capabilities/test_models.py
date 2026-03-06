"""
Unit tests for capability domain models.

Tests immutability (frozen dataclasses) and v1 primitive type validation.
"""

import pytest

from squadops.capabilities.models import (
    AcceptanceCheck,
    ArtifactSpec,
    CapabilityContract,
    CheckType,
    InputSpec,
    LifecycleScope,
    OutputSpec,
    TaskRecord,
    TaskStatus,
    Trigger,
    Workload,
    WorkloadRunReport,
    WorkloadStatus,
    WorkloadTask,
    _validate_primitive_value,
)


class TestInputSpec:
    """Tests for InputSpec model."""

    def test_valid_primitive_types(self):
        """InputSpec accepts valid v1 primitive types."""
        for ptype in ["string", "number", "boolean"]:
            spec = InputSpec(name="test", type=ptype)
            assert spec.type == ptype

    def test_invalid_primitive_type_raises(self):
        """InputSpec rejects non-primitive types."""
        with pytest.raises(ValueError, match="type must be one of"):
            InputSpec(name="test", type="array")

        with pytest.raises(ValueError, match="type must be one of"):
            InputSpec(name="test", type="object")

    def test_immutability(self):
        """InputSpec is immutable (frozen)."""
        spec = InputSpec(name="test", type="string")
        with pytest.raises(AttributeError):
            spec.name = "changed"  # type: ignore


class TestOutputSpec:
    """Tests for OutputSpec model."""

    def test_valid_primitive_types(self):
        """OutputSpec accepts valid v1 primitive types."""
        for ptype in ["string", "number", "boolean"]:
            spec = OutputSpec(name="test", type=ptype)
            assert spec.type == ptype

    def test_invalid_primitive_type_raises(self):
        """OutputSpec rejects non-primitive types."""
        with pytest.raises(ValueError, match="type must be one of"):
            OutputSpec(name="test", type="list")

    def test_immutability(self):
        """OutputSpec is immutable (frozen)."""
        spec = OutputSpec(name="test", type="number")
        with pytest.raises(AttributeError):
            spec.type = "string"  # type: ignore


class TestArtifactSpec:
    """Tests for ArtifactSpec model."""

    def test_creation(self):
        """ArtifactSpec can be created with required fields."""
        spec = ArtifactSpec(
            name="report",
            path_template="runs/{cycle_id}/report.json",
        )
        assert spec.name == "report"
        assert "{cycle_id}" in spec.path_template

    def test_immutability(self):
        """ArtifactSpec is immutable (frozen)."""
        spec = ArtifactSpec(name="test", path_template="path")
        with pytest.raises(AttributeError):
            spec.name = "changed"  # type: ignore


class TestAcceptanceCheck:
    """Tests for AcceptanceCheck model."""

    def test_file_exists_check(self):
        """file_exists check requires only target."""
        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="path/to/file",
        )
        assert check.check_type == CheckType.FILE_EXISTS
        assert check.field_path is None

    def test_non_empty_check(self):
        """non_empty check requires only target."""
        check = AcceptanceCheck(
            check_type=CheckType.NON_EMPTY,
            target="path/to/file",
        )
        assert check.check_type == CheckType.NON_EMPTY

    def test_json_field_equals_requires_field_path(self):
        """json_field_equals requires field_path."""
        with pytest.raises(ValueError, match="requires field_path"):
            AcceptanceCheck(
                check_type=CheckType.JSON_FIELD_EQUALS,
                target="path/to/file.json",
                expected_value="test",
            )

    def test_json_field_equals_requires_expected_value(self):
        """json_field_equals requires expected_value."""
        with pytest.raises(ValueError, match="requires expected_value"):
            AcceptanceCheck(
                check_type=CheckType.JSON_FIELD_EQUALS,
                target="path/to/file.json",
                field_path="status",
            )

    def test_json_field_equals_requires_primitive_expected_value(self):
        """json_field_equals expected_value must be primitive."""
        with pytest.raises(ValueError, match="must be a primitive"):
            AcceptanceCheck(
                check_type=CheckType.JSON_FIELD_EQUALS,
                target="path/to/file.json",
                field_path="data",
                expected_value=["list", "value"],
            )

    def test_immutability(self):
        """AcceptanceCheck is immutable (frozen)."""
        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="path",
        )
        with pytest.raises(AttributeError):
            check.target = "new_path"  # type: ignore


class TestCapabilityContract:
    """Tests for CapabilityContract model."""

    def test_get_input_spec(self):
        """Contract provides input spec lookup."""
        contract = CapabilityContract(
            capability_id="data.test",
            version="1.0.0",
            description="Test",
            owner_roles=("data",),
            lifecycle_scope=LifecycleScope.CYCLE,
            trigger=Trigger.ON_DEMAND,
            inputs=(
                InputSpec(name="cycle_id", type="string"),
                InputSpec(name="count", type="number"),
            ),
        )
        spec = contract.get_input_spec("cycle_id")
        assert spec is not None
        assert spec.type == "string"
        assert contract.get_input_spec("missing") is None

    def test_immutability(self):
        """Contract is immutable (frozen)."""
        contract = CapabilityContract(
            capability_id="data.test",
            version="1.0.0",
            description="Test",
            owner_roles=("data",),
            lifecycle_scope=LifecycleScope.CYCLE,
            trigger=Trigger.ON_DEMAND,
        )
        with pytest.raises(AttributeError):
            contract.version = "2.0.0"  # type: ignore


class TestWorkloadTask:
    """Tests for WorkloadTask model."""

    def test_creation(self):
        """WorkloadTask can be created."""
        task = WorkloadTask(
            task_id="collect",
            capability_id="data.collect",
            inputs=(("cycle_id", "{cycle_id}"),),
            depends_on=(),
        )
        assert task.task_id == "collect"
        assert task.get_input("cycle_id") == "{cycle_id}"

    def test_get_input_missing(self):
        """get_input returns None for missing inputs."""
        task = WorkloadTask(task_id="t", capability_id="c")
        assert task.get_input("missing") is None

    def test_immutability(self):
        """WorkloadTask is immutable (frozen)."""
        task = WorkloadTask(task_id="t", capability_id="c")
        with pytest.raises(AttributeError):
            task.task_id = "new"  # type: ignore


class TestWorkload:
    """Tests for Workload model."""

    def test_creation(self):
        """Workload can be created."""
        workload = Workload(
            workload_id="test_workload",
            version="1.0.0",
            description="Test workload",
            tasks=(
                WorkloadTask(task_id="t1", capability_id="d.c1"),
                WorkloadTask(task_id="t2", capability_id="d.c2", depends_on=("t1",)),
            ),
            vars=(("key", "value"),),
        )
        assert workload.workload_id == "test_workload"
        assert len(workload.tasks) == 2
        assert workload.get_var("key") == "value"

    def test_get_task(self):
        """Workload provides task lookup."""
        workload = Workload(
            workload_id="test",
            version="1.0.0",
            description="Test",
            tasks=(WorkloadTask(task_id="t1", capability_id="d.c"),),
        )
        assert workload.get_task("t1") is not None
        assert workload.get_task("missing") is None

    def test_immutability(self):
        """Workload is immutable (frozen)."""
        workload = Workload(
            workload_id="test",
            version="1.0.0",
            description="Test",
            tasks=(),
        )
        with pytest.raises(AttributeError):
            workload.version = "2.0.0"  # type: ignore


class TestPrimitiveValueValidation:
    """Tests for primitive value validation."""

    def test_string_validation(self):
        """String type validation."""
        assert _validate_primitive_value("hello", "string") is True
        assert _validate_primitive_value("", "string") is True
        assert _validate_primitive_value(123, "string") is False
        assert _validate_primitive_value(True, "string") is False

    def test_number_validation(self):
        """Number type validation (int and float)."""
        assert _validate_primitive_value(123, "number") is True
        assert _validate_primitive_value(1.5, "number") is True
        assert _validate_primitive_value(0, "number") is True
        assert _validate_primitive_value("123", "number") is False
        # Boolean is not a number
        assert _validate_primitive_value(True, "number") is False

    def test_boolean_validation(self):
        """Boolean type validation."""
        assert _validate_primitive_value(True, "boolean") is True
        assert _validate_primitive_value(False, "boolean") is True
        assert _validate_primitive_value(1, "boolean") is False
        assert _validate_primitive_value("true", "boolean") is False


class TestTaskRecord:
    """Tests for TaskRecord model."""

    def test_creation(self):
        """TaskRecord can be created."""
        record = TaskRecord(
            task_id="t1",
            capability_id="d.c",
            status=TaskStatus.SUCCEEDED,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:01:00Z",
        )
        assert record.task_id == "t1"
        assert record.status == TaskStatus.SUCCEEDED

    def test_immutability(self):
        """TaskRecord is immutable (frozen)."""
        record = TaskRecord(task_id="t", capability_id="c", status=TaskStatus.PENDING)
        with pytest.raises(AttributeError):
            record.status = TaskStatus.RUNNING  # type: ignore


class TestWorkloadRunReport:
    """Tests for WorkloadRunReport model."""

    def test_creation(self):
        """WorkloadRunReport can be created."""
        report = WorkloadRunReport(
            workload_id="test",
            cycle_id="cycle-123",
            status=WorkloadStatus.SUCCEEDED,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:05:00Z",
            task_records=(),
        )
        assert report.workload_id == "test"
        assert report.status == WorkloadStatus.SUCCEEDED

    def test_immutability(self):
        """WorkloadRunReport is immutable (frozen)."""
        report = WorkloadRunReport(
            workload_id="test",
            cycle_id="cycle-123",
            status=WorkloadStatus.PENDING,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:05:00Z",
            task_records=(),
        )
        with pytest.raises(AttributeError):
            report.status = WorkloadStatus.RUNNING  # type: ignore
