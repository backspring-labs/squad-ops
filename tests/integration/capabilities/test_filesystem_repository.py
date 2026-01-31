"""
Integration tests for FileSystemCapabilityRepository.

Tests loading contracts and workloads from the actual filesystem,
including schema validation.
"""

import json
import pytest
from pathlib import Path

from adapters.capabilities.filesystem import FileSystemCapabilityRepository
from squadops.capabilities.models import (
    CheckType,
    LifecycleScope,
    Trigger,
)
from squadops.capabilities.exceptions import (
    ContractNotFoundError,
    ContractValidationError,
    WorkloadNotFoundError,
)


@pytest.fixture
def manifests_path():
    """Path to the actual manifests directory."""
    # __file__ = tests/integration/capabilities/test_filesystem_repository.py
    # 4 parents: capabilities -> integration -> tests -> squad-ops (project root)
    return Path(__file__).parent.parent.parent.parent / "src" / "squadops" / "capabilities" / "manifests"


@pytest.fixture
def repository(manifests_path):
    """Create a FileSystemCapabilityRepository with real manifests."""
    return FileSystemCapabilityRepository(
        base_path=manifests_path,
        validate_schemas=True,
    )


@pytest.fixture
def temp_repository(tmp_path):
    """Create a repository with a temporary directory for testing edge cases."""
    # Create directory structure
    (tmp_path / "schemas").mkdir()
    (tmp_path / "contracts" / "test").mkdir(parents=True)
    (tmp_path / "workloads").mkdir()

    # Copy schemas from real location
    manifests_path = Path(__file__).parent.parent.parent.parent / "src" / "squadops" / "capabilities" / "manifests"
    for schema_file in manifests_path.glob("schemas/*.json"):
        (tmp_path / "schemas" / schema_file.name).write_text(schema_file.read_text())

    return FileSystemCapabilityRepository(base_path=tmp_path, validate_schemas=True)


class TestContractLoading:
    """Tests for loading capability contracts."""

    def test_load_real_contract(self, repository):
        """Load a real contract from the manifests directory."""
        contract = repository.get_contract("data.collect_cycle_snapshot")

        assert contract.capability_id == "data.collect_cycle_snapshot"
        assert contract.version == "1.0.0"
        assert "data" in contract.owner_roles
        assert contract.lifecycle_scope == LifecycleScope.CYCLE
        assert contract.trigger == Trigger.ON_DEMAND
        assert len(contract.inputs) > 0
        assert len(contract.artifacts) > 0
        assert len(contract.acceptance_checks) > 0

    def test_load_all_data_contracts(self, repository):
        """Load all data domain contracts."""
        contracts = repository.list_contracts(domain="data")

        assert len(contracts) >= 3  # We created 3 data contracts
        capability_ids = [c.capability_id for c in contracts]
        assert "data.collect_cycle_snapshot" in capability_ids
        assert "data.profile_cycle_metrics" in capability_ids
        assert "data.compose_cycle_summary" in capability_ids

    def test_contract_not_found(self, repository):
        """ContractNotFoundError for missing contract."""
        with pytest.raises(ContractNotFoundError) as exc:
            repository.get_contract("nonexistent.capability")
        assert "nonexistent.capability" in str(exc.value)

    def test_contract_caching(self, repository):
        """Contract is cached after first load."""
        contract1 = repository.get_contract("data.collect_cycle_snapshot")
        contract2 = repository.get_contract("data.collect_cycle_snapshot")

        # Same object due to caching
        assert contract1 is contract2

    def test_contract_exists_check(self, repository):
        """contract_exists returns correct values."""
        assert repository.contract_exists("data.collect_cycle_snapshot") is True
        assert repository.contract_exists("nonexistent.capability") is False

    def test_invalid_yaml_raises(self, temp_repository, tmp_path):
        """Invalid YAML raises ContractValidationError."""
        contract_path = tmp_path / "contracts" / "test" / "bad_yaml.yaml"
        contract_path.write_text("invalid: yaml: content: [")

        with pytest.raises(ContractValidationError, match="Invalid YAML"):
            temp_repository.get_contract("test.bad_yaml")

    def test_empty_file_raises(self, temp_repository, tmp_path):
        """Empty file raises ContractValidationError."""
        contract_path = tmp_path / "contracts" / "test" / "empty.yaml"
        contract_path.write_text("")

        with pytest.raises(ContractValidationError, match="Empty"):
            temp_repository.get_contract("test.empty")


class TestWorkloadLoading:
    """Tests for loading workload definitions."""

    def test_load_real_workload(self, repository):
        """Load a real workload from the manifests directory."""
        workload = repository.get_workload("data_cycle_wrapup_smoke")

        assert workload.workload_id == "data_cycle_wrapup_smoke"
        assert workload.version == "1.0.0"
        assert len(workload.tasks) == 3

        # Check DAG structure
        task_ids = [t.task_id for t in workload.tasks]
        assert "collect_snapshot" in task_ids
        assert "profile_metrics" in task_ids
        assert "compose_summary" in task_ids

        # Check dependencies
        profile_task = workload.get_task("profile_metrics")
        assert "collect_snapshot" in profile_task.depends_on

    def test_workload_not_found(self, repository):
        """WorkloadNotFoundError for missing workload."""
        with pytest.raises(WorkloadNotFoundError) as exc:
            repository.get_workload("nonexistent_workload")
        assert "nonexistent_workload" in str(exc.value)

    def test_workload_caching(self, repository):
        """Workload is cached after first load."""
        workload1 = repository.get_workload("data_cycle_wrapup_smoke")
        workload2 = repository.get_workload("data_cycle_wrapup_smoke")

        assert workload1 is workload2

    def test_workload_exists_check(self, repository):
        """workload_exists returns correct values."""
        assert repository.workload_exists("data_cycle_wrapup_smoke") is True
        assert repository.workload_exists("nonexistent") is False

    def test_list_workloads(self, repository):
        """list_workloads returns all workloads."""
        workloads = repository.list_workloads()

        assert len(workloads) >= 1
        workload_ids = [w.workload_id for w in workloads]
        assert "data_cycle_wrapup_smoke" in workload_ids


class TestSchemaValidation:
    """Tests for JSON schema validation."""

    def test_valid_contract_passes_schema(self, temp_repository, tmp_path):
        """Valid contract passes schema validation."""
        contract_yaml = """
capability_id: test.valid_contract
version: 1.0.0
description: A valid test contract
owner_roles:
  - data
lifecycle_scope: cycle
trigger: on_demand
inputs:
  - name: test_input
    type: string
    required: true
outputs:
  - name: test_output
    type: string
artifacts:
  - name: test_artifact
    path_template: "{cycle_id}/output.json"
acceptance_checks:
  - check_type: file_exists
    target: "{cycle_id}/output.json"
timeout_seconds: 60
"""
        contract_path = tmp_path / "contracts" / "test" / "valid_contract.yaml"
        contract_path.write_text(contract_yaml)

        contract = temp_repository.get_contract("test.valid_contract")
        assert contract.capability_id == "test.valid_contract"

    def test_invalid_contract_fails_schema(self, temp_repository, tmp_path):
        """Contract missing required fields fails schema validation."""
        contract_yaml = """
capability_id: test.invalid_contract
version: 1.0.0
# Missing: description, owner_roles, lifecycle_scope, trigger
"""
        contract_path = tmp_path / "contracts" / "test" / "invalid_contract.yaml"
        contract_path.write_text(contract_yaml)

        with pytest.raises(ContractValidationError, match="Schema validation failed"):
            temp_repository.get_contract("test.invalid_contract")

    def test_invalid_primitive_type_fails_schema(self, temp_repository, tmp_path):
        """Contract with invalid primitive type fails schema validation."""
        contract_yaml = """
capability_id: test.bad_type
version: 1.0.0
description: Contract with bad type
owner_roles:
  - data
lifecycle_scope: cycle
trigger: on_demand
inputs:
  - name: bad_input
    type: array  # Invalid - not a v1 primitive
"""
        contract_path = tmp_path / "contracts" / "test" / "bad_type.yaml"
        contract_path.write_text(contract_yaml)

        with pytest.raises(ContractValidationError):
            temp_repository.get_contract("test.bad_type")


class TestContractParsing:
    """Tests for correct parsing of contract fields."""

    def test_acceptance_check_parsing(self, repository):
        """Acceptance checks are parsed correctly."""
        contract = repository.get_contract("data.collect_cycle_snapshot")

        # Find the json_field_equals check
        json_check = None
        for check in contract.acceptance_checks:
            if check.check_type == CheckType.JSON_FIELD_EQUALS:
                json_check = check
                break

        assert json_check is not None
        assert json_check.field_path is not None
        assert json_check.expected_value is not None

    def test_input_spec_parsing(self, repository):
        """Input specs are parsed correctly."""
        contract = repository.get_contract("data.collect_cycle_snapshot")

        cycle_id_input = contract.get_input_spec("cycle_id")
        assert cycle_id_input is not None
        assert cycle_id_input.type == "string"
        assert cycle_id_input.required is True

    def test_artifact_spec_parsing(self, repository):
        """Artifact specs are parsed correctly."""
        contract = repository.get_contract("data.collect_cycle_snapshot")

        assert len(contract.artifacts) > 0
        artifact = contract.artifacts[0]
        assert "{cycle_id}" in artifact.path_template
