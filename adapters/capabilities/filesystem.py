"""
Filesystem-based capability repository for local development.

Implements the CapabilityRepository port using the POSIX filesystem.
Loads contracts and workloads from YAML files, validating against JSON schemas.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore

from squadops.ports.capabilities.repository import CapabilityRepository
from squadops.capabilities.models import (
    AcceptanceCheck,
    ArtifactSpec,
    CapabilityContract,
    CheckType,
    InputSpec,
    LifecycleScope,
    OutputSpec,
    Trigger,
    Workload,
    WorkloadTask,
)
from squadops.capabilities.exceptions import (
    ContractNotFoundError,
    ContractValidationError,
    WorkloadNotFoundError,
)

logger = logging.getLogger(__name__)


class FileSystemCapabilityRepository(CapabilityRepository):
    """
    Filesystem-based storage for capability contracts and workloads.

    Directory structure:
    {base_path}/
    ├── schemas/
    │   ├── capability_contract.schema.json
    │   ├── workload.schema.json
    │   └── workload_run_report.schema.json
    ├── contracts/
    │   └── {domain}/
    │       └── {capability_name}.yaml
    └── workloads/
        └── {workload_id}.yaml
    """

    def __init__(
        self,
        base_path: Path,
        validate_schemas: bool = True,
    ):
        """
        Initialize filesystem repository.

        Args:
            base_path: Root directory containing contracts and workloads
            validate_schemas: Whether to validate against JSON schemas (default True)
        """
        self.base_path = Path(base_path)
        self.validate_schemas = validate_schemas
        self._contract_cache: dict[str, CapabilityContract] = {}
        self._workload_cache: dict[str, Workload] = {}
        self._contract_schema: dict | None = None
        self._workload_schema: dict | None = None

    def _load_schema(self, schema_name: str) -> dict:
        """Load a JSON schema file."""
        schema_path = self.base_path / "schemas" / schema_name
        if not schema_path.exists():
            raise ContractValidationError(
                f"Schema not found: {schema_path}",
                {"path": str(schema_path)},
            )
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_against_schema(self, data: dict, schema_name: str) -> None:
        """Validate data against a JSON schema."""
        if not self.validate_schemas or jsonschema is None:
            return

        if schema_name == "capability_contract.schema.json":
            if self._contract_schema is None:
                self._contract_schema = self._load_schema(schema_name)
            schema = self._contract_schema
        elif schema_name == "workload.schema.json":
            if self._workload_schema is None:
                self._workload_schema = self._load_schema(schema_name)
            schema = self._workload_schema
        else:
            schema = self._load_schema(schema_name)

        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            raise ContractValidationError(
                f"Schema validation failed: {e.message}",
                {"path": list(e.absolute_path), "schema_path": list(e.absolute_schema_path)},
            )

    def _parse_acceptance_check(self, data: dict) -> AcceptanceCheck:
        """Parse an acceptance check from YAML data."""
        return AcceptanceCheck(
            check_type=CheckType(data["check_type"]),
            target=data["target"],
            field_path=data.get("field_path"),
            expected_value=data.get("expected_value"),
            description=data.get("description", ""),
        )

    def _parse_contract(self, data: dict) -> CapabilityContract:
        """Parse a capability contract from YAML data."""
        inputs = tuple(
            InputSpec(
                name=i["name"],
                type=i["type"],
                required=i.get("required", True),
                description=i.get("description", ""),
            )
            for i in data.get("inputs", [])
        )

        outputs = tuple(
            OutputSpec(
                name=o["name"],
                type=o["type"],
                description=o.get("description", ""),
            )
            for o in data.get("outputs", [])
        )

        artifacts = tuple(
            ArtifactSpec(
                name=a["name"],
                path_template=a["path_template"],
                description=a.get("description", ""),
            )
            for a in data.get("artifacts", [])
        )

        acceptance_checks = tuple(
            self._parse_acceptance_check(c)
            for c in data.get("acceptance_checks", [])
        )

        return CapabilityContract(
            capability_id=data["capability_id"],
            version=data["version"],
            description=data["description"],
            owner_roles=tuple(data["owner_roles"]),
            lifecycle_scope=LifecycleScope(data["lifecycle_scope"]),
            trigger=Trigger(data["trigger"]),
            inputs=inputs,
            outputs=outputs,
            artifacts=artifacts,
            acceptance_checks=acceptance_checks,
            timeout_seconds=data.get("timeout_seconds", 300),
        )

    def _parse_workload(self, data: dict) -> Workload:
        """Parse a workload from YAML data."""
        # Parse vars as tuple of key-value pairs
        vars_data = data.get("vars", {})
        vars_tuple = tuple((k, v) for k, v in vars_data.items())

        tasks = []
        for t in data.get("tasks", []):
            # Parse inputs as tuple of key-value pairs
            inputs_data = t.get("inputs", {})
            inputs_tuple = tuple((k, v) for k, v in inputs_data.items())

            tasks.append(
                WorkloadTask(
                    task_id=t["task_id"],
                    capability_id=t["capability_id"],
                    inputs=inputs_tuple,
                    depends_on=tuple(t.get("depends_on", [])),
                    executor_override=t.get("executor_override"),
                )
            )

        acceptance_checks = tuple(
            self._parse_acceptance_check(c)
            for c in data.get("acceptance_checks", [])
        )

        return Workload(
            workload_id=data["workload_id"],
            version=data["version"],
            description=data["description"],
            tasks=tuple(tasks),
            vars=vars_tuple,
            acceptance_checks=acceptance_checks,
        )

    def _resolve_contract_path(self, capability_id: str) -> Path | None:
        """
        Resolve filesystem path for a capability contract.

        Capability ID format: domain.capability_name
        Path: contracts/{domain}/{capability_name}.yaml
        """
        parts = capability_id.split(".", 1)
        if len(parts) != 2:
            return None

        domain, name = parts
        path = self.base_path / "contracts" / domain / f"{name}.yaml"
        return path if path.exists() else None

    def _resolve_workload_path(self, workload_id: str) -> Path | None:
        """
        Resolve filesystem path for a workload.

        Path: workloads/{workload_id}.yaml
        """
        path = self.base_path / "workloads" / f"{workload_id}.yaml"
        return path if path.exists() else None

    def get_contract(self, capability_id: str) -> CapabilityContract:
        """Get a capability contract by ID."""
        # Check cache
        if capability_id in self._contract_cache:
            return self._contract_cache[capability_id]

        # Resolve path
        path = self._resolve_contract_path(capability_id)
        if path is None:
            raise ContractNotFoundError(capability_id)

        # Load and parse
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ContractValidationError(f"Invalid YAML: {e}")

        if not data:
            raise ContractValidationError(f"Empty contract file: {path}")

        # Validate schema
        self._validate_against_schema(data, "capability_contract.schema.json")

        # Parse and cache
        contract = self._parse_contract(data)
        self._contract_cache[capability_id] = contract

        return contract

    def get_workload(self, workload_id: str) -> Workload:
        """Get a workload definition by ID."""
        # Check cache
        if workload_id in self._workload_cache:
            return self._workload_cache[workload_id]

        # Resolve path
        path = self._resolve_workload_path(workload_id)
        if path is None:
            raise WorkloadNotFoundError(workload_id)

        # Load and parse
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ContractValidationError(f"Invalid YAML: {e}")

        if not data:
            raise ContractValidationError(f"Empty workload file: {path}")

        # Validate schema
        self._validate_against_schema(data, "workload.schema.json")

        # Parse and cache
        workload = self._parse_workload(data)
        self._workload_cache[workload_id] = workload

        return workload

    def list_contracts(self, domain: str | None = None) -> list[CapabilityContract]:
        """List available capability contracts, optionally filtered by domain."""
        contracts = []
        contracts_dir = self.base_path / "contracts"

        if not contracts_dir.exists():
            return contracts

        # Iterate over domain directories
        for domain_dir in contracts_dir.iterdir():
            if not domain_dir.is_dir():
                continue

            # Filter by domain if specified
            if domain and domain_dir.name != domain:
                continue

            # Load contracts in this domain
            for contract_file in domain_dir.glob("*.yaml"):
                capability_id = f"{domain_dir.name}.{contract_file.stem}"
                try:
                    contract = self.get_contract(capability_id)
                    contracts.append(contract)
                except (ContractNotFoundError, ContractValidationError) as e:
                    logger.warning(f"Failed to load contract {capability_id}: {e}")

        return contracts

    def list_workloads(self) -> list[Workload]:
        """List all available workload definitions."""
        workloads = []
        workloads_dir = self.base_path / "workloads"

        if not workloads_dir.exists():
            return workloads

        for workload_file in workloads_dir.glob("*.yaml"):
            workload_id = workload_file.stem
            try:
                workload = self.get_workload(workload_id)
                workloads.append(workload)
            except (WorkloadNotFoundError, ContractValidationError) as e:
                logger.warning(f"Failed to load workload {workload_id}: {e}")

        return workloads

    def contract_exists(self, capability_id: str) -> bool:
        """Check if a capability contract exists without loading it."""
        return self._resolve_contract_path(capability_id) is not None

    def workload_exists(self, workload_id: str) -> bool:
        """Check if a workload definition exists without loading it."""
        return self._resolve_workload_path(workload_id) is not None
