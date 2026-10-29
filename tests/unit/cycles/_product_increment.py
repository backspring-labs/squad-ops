"""A repository-backed product's increment cycle, composed as the executor composes it (#2810).

The shared contract fixture's Tally (its source context, development configuration, derived profile
and inherited baseline, as recorded), grown into an invented product larger than a 65,536-token
window: a package of many modules, its own checks and its instruction file. The task the plan names
writes one small file of it, ``tally/report.py``.

Every envelope here is the one the live path composes:
- the run's tree is seeded by ``seed_checkout_artifacts``, as provisioning seeds it;
- each run's plan is ``generate_task_plan``'s, the proposal's input ``with_product_proposal``'s;
- each task is enriched by the executor's ``_enrich_envelope``;
- a correction round is the executor's own ``_dispatch_correction_protocol``, through the
  correction runner and repair the executor composed, under its ``BindingHolds``.

Memory is the snapshot recall over a pinned project instruction of 1,330 tokens, its framing
included, as the live hold measured it, that applies to every task type.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import yaml

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from adapters.noop.ports import NoOpProposalEvidence
from squadops.capabilities import lesson_supply
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    DerivedProfileNotFoundError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.execution.binding_holds import BindingHolds
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.records import InstructionApplicability, Revision, Source, new_record
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import CheckoutTree
from squadops.projects.source_context import parse_source_context
from squadops.tasks.models import TaskResult
from tests.fixtures.shared_contract.repository import recorded

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
#: The 2.5 main demonstration's model: a 65,536-token window.
MODEL = "qwen3.8-27b-tf-nvfp4"
#: The binding project instruction's section as the live hold measured it, framing included.
INSTRUCTION_TOKENS = 1_330
INSTRUCTION_ID = "mrec_tally_totals"
#: The one product file the develop task writes, and the qa task's suite, both small.
NAMED = "tally/report.py"
SUITE = "checks/check_criterion_R1.py"
CONTEXT = parse_source_context(recorded("project_source_context", "valid"))
CONFIGURATION = parse_configuration(recorded("development_configuration", "valid"))
PROFILE = parse_profile(recorded("derived_profile", "valid"))
BASELINE = parse_baseline(recorded("inherited_baseline", "valid"))


def module(name: str, chars: int) -> str:
    """An invented Python module exactly ``chars`` long: a ledger helper repeated."""
    line = f"def {name}(ledger):\n    return sum(entry.amount for entry in ledger.entries)\n\n"
    return (line * (chars // len(line) + 1))[:chars]


def product_tree(
    *, named: tuple[str, ...] = (NAMED,), named_chars: int = 8_000, modules: int = 78
) -> dict:
    """The invented product: ``modules`` package modules of 4,400 characters each (78 make about
    98,000 tokens of source and config, near the checkout's 384 KB limit), its own checks, its
    instruction file and requirements, and the files a task names, ``named_chars`` each."""
    files = {f"tally/ledger_{i:02d}.py": module(f"ledger_{i:02d}", 4_400) for i in range(modules)}
    files |= {f"checks/check_area_{i}.py": module(f"check_area_{i}", 1_800) for i in range(4)}
    files |= {path: module(path.rsplit("/", 1)[-1][:-3], named_chars) for path in named}
    files |= {
        "CONTRIBUTING.md": "Keep each ledger function pure; run the checks before a change.\n" * 20,
        "docs/requirements.md": "# Tally\n\nTally totals a ledger's entries per account.\n" * 30,
        "tools/build.py": "print('built')\n",
        "pyproject.toml": '[project]\nname = "tally"\nversion = "0.4.0"\n',
    }
    return {path: content.encode() for path, content in files.items()}


class Vault:
    """The run's artifact store, in memory."""

    def __init__(self) -> None:
        self.stored: dict[str, tuple[ArtifactRef, bytes]] = {}

    async def store(self, ref: ArtifactRef, content: bytes) -> ArtifactRef:
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]:
        return self.stored[artifact_id]

    def refs(self) -> list[tuple[str, ArtifactRef]]:
        return [(art_id, ref) for art_id, (ref, _content) in self.stored.items()]

    def produced(self, name: str, content: str, task_type: str, artifact_type: str) -> None:
        """A file the run's own task produced, stored as the executor stores an emission."""
        art_id = f"art_{len(self.stored):04d}"
        self.stored[art_id] = (
            ArtifactRef(
                artifact_id=art_id, project_id=CONTEXT.project_id, artifact_type=artifact_type,
                filename=name, content_hash="h", size_bytes=len(content), media_type="text/plain",
                created_at=NOW, cycle_id="cyc_tally_inc", metadata={"producing_task_type": task_type},
            ),
            content.encode(),
        )  # fmt: skip


def repository(tree: dict[str, bytes]) -> AsyncMock:
    """The managed clone at the pinned commit."""
    repo = AsyncMock()
    repo.tree_at.return_value = CheckoutTree(
        commit=CONTEXT.pinned_commit, files=dict(tree), executable=frozenset(),
        symlinks=frozenset(), submodules=frozenset(),
    )  # fmt: skip

    async def file_at(_project, _commit, path):
        return tree[path]

    repo.file_at.side_effect = file_at
    return repo


def projects() -> AsyncMock:
    """The Project registry as the recorded contracts answer it."""
    registry = AsyncMock()
    registry.get_project.return_value = SimpleNamespace(
        source=SimpleNamespace(base_ref="refs/heads/main")
    )
    registry.get_development_configuration.return_value = CONFIGURATION
    registry.get_derived_profile.side_effect = DerivedProfileNotFoundError("no profile")
    registry.get_inherited_baseline.return_value = BASELINE
    registry.get_initialization.return_value = None
    return registry


def squad() -> SquadProfile:
    """Every role, the builder among them, on the demonstration's model."""
    return SquadProfile(
        profile_id="full", name="full", description="", version=1, created_at=NOW,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model=MODEL, enabled=True, serves_roles=(r,))
            for a, r in (("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data"),
                         ("max", "lead"), ("bob", "builder"))
        ),
    )  # fmt: skip


def increment_cycle() -> Cycle:
    """A Campaign's increment on Tally's campaign branch, on ``campaign-increment-source``'s
    defaults, pinned at the recorded source context."""
    from squadops.contracts.cycle_request_profiles import load_profile

    block = {
        "proposal_id": "prop_tally0001",
        "version": 1,
        "basis": "campaign_branch",
        "baseline_tree": "f" * 64,
        "objective": {
            "statement": "The report totals each account",
            "allowed_scope": ["tally/**", "checks/**"],
            "measurement": "every report ends in its total",
            "requirements": "repo:file:docs/requirements.md@current",
        },
        "prior_criteria": [],
        "frozen_criteria": [],
        "max_revisions": 2,
    }
    return Cycle(
        cycle_id="cyc_tally_inc",
        project_id=CONTEXT.project_id,
        created_at=NOW,
        created_by="campaign-launcher",
        prd_ref="Tally totals a ledger's entries per account.",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=dict(load_profile("campaign-increment-source").defaults),
        execution_overrides={"campaign_proposal": block},
        campaign_id="cmp_tally00001",
        kind="increment",
        request_profile="campaign-increment-source",
        source_context=CONTEXT,
    )


def run(workload: str) -> Run:
    return Run(
        f"run_{workload[:4]}0000001", "cyc_tally_inc", 1, "running", "system", "cfg",
        workload_type=workload,
    )  # fmt: skip


def plan(*named: str) -> ImplementationPlan:
    """The increment's implementation plan: a develop task writing ``named`` and the criterion's
    suite."""
    return ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1, "project_id": CONTEXT.project_id, "cycle_id": "cyc_tally_inc",
                "prd_hash": "abc",
                "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
                "tasks": [
                    {"task_index": 0, "task_type": "development.develop", "role": "dev",
                     "focus": "the report's total line", "description": "End with the total.",
                     "expected_artifacts": list(named), "acceptance_criteria": []},
                    {"task_index": 1, "task_type": "qa.test", "role": "qa",
                     "focus": "the criterion's check", "description": "Check R1.",
                     "expected_artifacts": [SUITE], "acceptance_criteria": [], "depends_on": [0]},
                ],
            }
        )
    )  # fmt: skip


async def pinned_recall(cycle: Cycle) -> tuple[SnapshotRecall, InMemoryCrossCycleMemoryStore]:
    """The snapshot recall, the campaign's snapshot pinning one project instruction for every task
    type, its section 1,330 tokens with its framing."""
    framing = lesson_supply._framing("request.project_instructions_section")
    text = ("Every report ends in its account's total. " * INSTRUCTION_TOKENS)[
        : (INSTRUCTION_TOKENS - framing) * 4
    ]
    records = InMemoryMemoryRecords()
    await records.create(
        new_record(
            record_id=INSTRUCTION_ID, kind="instruction", scope="project",
            project_id=cycle.project_id, owner_id="ada",
            revision=Revision(
                number=1, body=text, author="ada", created_at=NOW, source=Source("api_call"),
                confirmed_by="ada", applicability=InstructionApplicability(("*",), ("*",), ("*",)),
            ),
        )
    )  # fmt: skip
    store = InMemoryCrossCycleMemoryStore()
    unit_kind, unit_id = lesson_supply.unit_of(cycle)
    await pin_unit(store, unit_kind=unit_kind, unit_id=unit_id, project_id=cycle.project_id,
                   pinned_at=NOW, disabled=False, records=records)  # fmt: skip
    assert unit_kind is UnitKind.CAMPAIGN
    return SnapshotRecall(store, records=records), store


class Dispatcher:
    """The task dispatcher, answering each correction step as an agent would: the analysis, the
    lead's patch decision, and a repair that succeeds. Every envelope it is sent is kept as it was
    sent (the round goes on to write into dicts the envelope shares, as ``prior_outputs``)."""

    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def dispatch_task(self, envelope, run_id, **_kwargs) -> TaskResult:
        self.sent.append(copy.deepcopy(envelope))
        outputs = {
            "data.analyze_failure": {
                "summary": "[data] the total line is missing",
                "analysis_summary": "render ends without the total line",
                "contributing_factors": ["no total is computed"],
            },
            "governance.correction_decision": {
                "correction_path": "patch",
                "decision_rationale": "the report is patchable",
                "affected_task_types": [envelope.inputs.get("failed_task_type", "")],
            },
        }.get(str(envelope.task_type), {"summary": "done"})
        return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs=outputs)

    async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
        return None


def executor(vault: Vault, recall: SnapshotRecall, dispatcher: Dispatcher):
    """The executor over ``vault`` and ``recall``. Its binding holds are its own class, polling at
    once and cancelled at the first poll, so a held task ends the test rather than waiting."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

    registry = AsyncMock()
    registry.get_run.return_value = run("implementation")
    registry.get_latest_checkpoint.return_value = None
    built = DispatchedFlowExecutor(
        cycle_registry=registry, artifact_vault=vault, queue=AsyncMock(),
        squad_profile=AsyncMock(), project_registry=projects(), campaign_registry=None,
        campaign_progress=None, box_verdict=None, failure_recall=recall,
        proposal_evidence=NoOpProposalEvidence(), task_timeout=5.0, event_bus=MagicMock(),
        task_dispatcher=dispatcher,
    )  # fmt: skip
    built.__dict__["_binding_holds"] = BindingHolds(
        cycle_registry=registry, campaign_registry=None, event_bus=MagicMock(),
        is_cancelled=AsyncMock(return_value=True), await_box=AsyncMock(), fill=None, poll_s=0,
    )  # fmt: skip
    return built, registry


def failed(envelope, artifacts: dict[str, str], checks: list[dict]) -> TaskResult:
    """``envelope``'s task failed its acceptance, having written ``artifacts``."""
    return TaskResult(
        task_id=envelope.task_id,
        status="FAILED",
        error="acceptance failed",
        outputs={
            "summary": "[dev] wrote the report",
            "artifacts": [
                {"name": name, "content": content, "type": "source", "media_type": "text/x-python"}
                for name, content in artifacts.items()
            ],
            "outcome_class": "semantic_failure",
            "validation_result": {
                "passed": False,
                "summary": "acceptance failed",
                "checks": checks,
            },
        },
    )


async def correction_round(built, envelope, enriched, result, cycle: Cycle, stored=None) -> Any:
    """One correction round for ``result``, entered where the live run enters it, over the run's
    ``stored`` artifacts (the vault's, by default)."""
    return await built._dispatch_correction_protocol(
        result, envelope, cycle, run("implementation").run_id,
        correction_counter={"n": 0}, correction_signature_state={},
        scaffold_enforcement_carry=[], prior_outputs={}, all_artifact_refs=[],
        stored_artifacts=built._artifact_vault.refs() if stored is None else stored,
        completed_task_ids=[], plan_delta_refs=[],
        profile=squad(), flow_run_id=None, enriched_envelope=enriched, interface_manifest=None,
        budget_guard=None, repair_rejection_carry=None, accepted_repair_task_ids=None,
    )  # fmt: skip


def replace_inputs(envelope, **inputs):
    return dataclasses.replace(envelope, inputs={**envelope.inputs, **inputs})
