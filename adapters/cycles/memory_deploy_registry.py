"""Deploy records in memory (#1720): the test and no-database twin of the Postgres adapter."""

from __future__ import annotations

from squadops.cycles.deploy_record import DeployRecord
from squadops.ports.cycles.deploy_registry import DeployRegistryPort


class MemoryDeployRegistry(DeployRegistryPort):
    def __init__(self) -> None:
        self._records: dict[str, DeployRecord] = {}

    async def record(self, record: DeployRecord) -> None:
        if record.deploy_id in self._records:
            raise ValueError(f"deploy record {record.deploy_id} already exists")
        self._records[record.deploy_id] = record

    async def latest(self) -> DeployRecord | None:
        return max(self._records.values(), key=lambda r: r.recorded_at, default=None)

    async def get(self, deploy_id: str) -> DeployRecord | None:
        return self._records.get(deploy_id)
