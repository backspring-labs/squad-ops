"""
Driven port for capability contract and workload storage abstraction.

This interface defines the contract for loading capability contracts
and workload definitions, allowing the domain logic to remain isolated
from physical storage implementation details.
"""

from abc import ABC, abstractmethod

from squadops.capabilities.models import CapabilityContract, Workload


class CapabilityRepository(ABC):
    """
    Abstract contract for fetching capability contracts and workloads.

    Implementations handle the actual storage medium (filesystem, S3, etc.)
    while the domain layer works against this abstraction.
    """

    @abstractmethod
    def get_contract(self, capability_id: str) -> CapabilityContract:
        """
        Get a capability contract by ID.

        Args:
            capability_id: Unique identifier for the contract
                          (e.g., "data.collect_cycle_snapshot")

        Returns:
            The resolved CapabilityContract

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
    def list_contracts(self, domain: str | None = None) -> list[CapabilityContract]:
        """
        List available capability contracts, optionally filtered by domain.

        Args:
            domain: Optional domain filter (e.g., "data", "dev", "qa")

        Returns:
            List of matching CapabilityContract objects
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
    def contract_exists(self, capability_id: str) -> bool:
        """
        Check if a capability contract exists without loading it.

        Args:
            capability_id: Unique identifier for the contract

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
