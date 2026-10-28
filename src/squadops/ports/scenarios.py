"""The held-out scenario store's port (SIP-0113 §4.1; #2413).

A store of its own, in the runtime API's Postgres: never the artifact vault, which is where squad
tasks' inputs come from. It persists; the rules that decide what it may hold are
``squadops.scenarios.suites``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.scenarios.evaluation import EvaluationRecord, QualityRemeasure
from squadops.scenarios.evidence import ScenarioEvidence
from squadops.scenarios.models import CampaignSuitePin, SuiteRecord
from squadops.scenarios.runner import DeclaredStart, RouteRequest, TreeEvaluation

if TYPE_CHECKING:  # the plan is the campaigns side's; the port only carries it
    from squadops.campaigns.seed_plan import SeedPlan


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

    @abstractmethod
    async def save_evaluation(self, record: EvaluationRecord) -> None:
        """Write an evaluation run's record (#2415). A record is written once."""

    @abstractmethod
    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None: ...

    @abstractmethod
    async def evaluations_for_cycle(self, cycle_id: str) -> list[EvaluationRecord]:
        """A cycle's evaluation runs, the earliest first: a cycle can be evaluated more than once."""

    @abstractmethod
    async def save_remeasure(self, remeasure: QualityRemeasure) -> None:
        """Write one re-measure (§10j, §10n ruling 1), apart from every evaluation record. The
        same evaluation, series and round again is refused: a series is written once."""

    @abstractmethod
    async def remeasures_for_cycle(self, cycle_id: str) -> list[QualityRemeasure]:
        """The cycle's re-measures, by series, then round."""

    @abstractmethod
    async def save_evidence(self, evaluation_id: str, evidence: Sequence[ScenarioEvidence]) -> None:
        """Keep each failed or blocked page scenario's evidence for its evaluation (SIP-0113 §10p
        ruling 8), once per scenario: held out, in the store's own table, never the vault."""

    @abstractmethod
    async def evidence_for(self, evaluation_id: str) -> list[ScenarioEvidence]:
        """The evaluation's evidence, by scenario. Read under ``scenarios:approve`` alone."""

    @abstractmethod
    async def purge_evidence(self, before: datetime) -> int:
        """Delete the evidence of every evaluation made before ``before``, and say how many
        scenarios' it was: the line's cut purges what the line kept (§10p ruling 8, cut step 8)."""


class ScenarioRunnerPort(ABC):
    """The scenario runner (SIP-0113 §4.1, A3): in the sandbox service, outside every squad
    agent's container. A scenario's steps reach it in the request, and it holds them in memory."""

    @abstractmethod
    async def evaluate_tree(
        self,
        *,
        tree: Mapping[str, bytes | str],
        tree_identity: str,
        executable: Collection[str],
        stack: str | None,
        declared: DeclaredStart | None,
        scenarios: Sequence[Mapping[str, Any]],
        environment: Mapping[str, str],
        pages: Sequence[str],
        seed: SeedPlan | None = None,
        routes: Sequence[RouteRequest] = (),
    ) -> TreeEvaluation:
        """Stand the tree up in a disposable copy and run the scenarios against it.
        ``declared`` is a non-blueprint Project's start (contract 7). Without one, the
        ``stack``'s environment contract starts it. ``environment`` is the owner-approved
        evaluation secrets, resolved (Q40), and is never written anywhere. ``pages`` are the
        declared pages Lighthouse and axe measure before any scenario runs (§4.2, #2416).
        ``seed``, when given, is §10j's: a second instance of the tree, seeded through its own API
        and measured on every page the plan names (``quality_seeded``). ``routes``, when given,
        are client routes read by the browser after the scenarios, at the declared UI base, each
        one's test ids returned (``TreeEvaluation.routes``, SIP-0109 §24co)."""
