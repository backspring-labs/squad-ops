"""DeployRegistryPort — the record of what each deploy put in service (#1720)."""

from abc import ABC, abstractmethod

from squadops.cycles.deploy_record import DeployRecord


class DeployRegistryPort(ABC):
    """Port for deploy records. Written by the deploy step, read when a cycle is created."""

    @abstractmethod
    async def record(self, record: DeployRecord) -> None:
        """Store a deploy's record. Records are write-once: a deploy_id is never rewritten."""

    @abstractmethod
    async def latest(self) -> DeployRecord | None:
        """The most recently recorded deploy, or ``None`` when no deploy has been recorded."""

    @abstractmethod
    async def get(self, deploy_id: str) -> DeployRecord | None:
        """A deploy's record by id, or ``None`` when there is none."""
