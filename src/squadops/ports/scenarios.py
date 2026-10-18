"""The held-out scenario store's port (SIP-0113 §4.1; #2413).

A store of its own, in the runtime API's Postgres: never the artifact vault, which is where squad
tasks' inputs come from. It persists; the rules that decide what it may hold are
``squadops.scenarios.suites``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.scenarios.models import CampaignSuitePin, SuiteRecord


class ScenarioStorePort(ABC):
    @abstractmethod
    async def save_suite(self, record: SuiteRecord) -> None:
        """Insert or replace the record under its digest."""

    @abstractmethod
    async def get_suite(self, digest: str) -> SuiteRecord | None: ...

    @abstractmethod
    async def list_suites(self) -> list[SuiteRecord]:
        """Every stored suite, the newest draft first."""

    @abstractmethod
    async def save_pin(self, pin: CampaignSuitePin) -> None:
        """Write a campaign's pin. A campaign is pinned once."""

    @abstractmethod
    async def get_pin(self, campaign_id: str) -> CampaignSuitePin | None: ...
