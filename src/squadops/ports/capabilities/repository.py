"""
Driven port for task contract and workload storage abstraction.

This interface defines the contract for loading task contracts
and workload definitions, allowing the domain logic to remain isolated
from physical storage implementation details.
"""

from abc import ABC, abstractmethod

from squadops.capabilities.models import TaskContract, Workload


class CapabilityRepository(ABC):
    """
    Abstract contract for fetching task contracts and workloads.

    Implementations handle the actual storage medium (filesystem, S3, etc.)
    while the domain layer works against this abstraction.
    """

    @abstractmethod
    def get_contract(self, task_type: str) -> TaskContract:
        """
        Get a task contract by ID.

        Args:
            task_type: Unique identifier for the contract
                          (e.g., "data.collect_cycle_snapshot")

        Returns:
            The resolved TaskContract

        Raises:
            ContractNotFoundError: If contract cannot be found
            ContractValidationError: If contract fails validation
        """
        pass

    @abstractmethod
    def get_workload(self, workload_id: str) -> Workload:
        """
        Get a workload definition by ID.

        Args:
            workload_id: Unique identifier for the workload
                        (e.g., "data_cycle_wrapup_smoke")

        Returns:
            The resolved Workload

        Raises:
            WorkloadNotFoundError: If workload cannot be found
            ContractValidationError: If workload fails validation
        """
        pass

    @abstractmethod
    def list_contracts(self, domain: str | None = None) -> list[TaskContract]:
        """
        List available task contracts, optionally filtered by domain.

        Args:
            domain: Optional domain filter (e.g., "data", "dev", "qa")

        Returns:
            List of matching TaskContract objects
        """
        pass

    @abstractmethod
    def list_workloads(self) -> list[Workload]:
        """
        List all available workload definitions.

        Returns:
            List of Workload objects
        """
        pass

    @abstractmethod
    def contract_exists(self, task_type: str) -> bool:
        """
        Check if a task contract exists without loading it.

        Args:
            task_type: Unique identifier for the contract

        Returns:
            True if the contract exists
        """
        pass

    @abstractmethod
    def workload_exists(self, workload_id: str) -> bool:
        """
        Check if a workload definition exists without loading it.

        Args:
            workload_id: Unique identifier for the workload

        Returns:
            True if the workload exists
        """
        pass
