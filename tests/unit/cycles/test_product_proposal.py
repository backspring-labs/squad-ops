"""What a repository-backed Project's proposal is given (SIP-0109 §24bv point 5), composed at its run.

The wiring enters at ``RunProvisioning.prepare``, the step ``execute_run`` takes before dispatch,
for a proposal run of an increment on the campaign branch: the shared fixture's Tally, its real
managed clone (``GitSourceRepository``) and its recorded derived profile and inherited baseline.
The increment is the first after the calibration record, so its head is the record's commit and
its previous verification the record's inherited baseline.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.change_request import PRODUCT_PROPOSAL_INPUT
from squadops.cycles.models import (
    Cycle,
    DerivedProfileNotFoundError,
    Run,
    TaskFlowPolicy,
)
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.registration import LocatorPolicy
from squadops.projects.source_context import parse_source_context
from tests.fixtures.shared_contract.repository import build_repository, recorded

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
_TREE = "f" * 64


class _Projects:
    """The registry's reads the proposal's input makes: the profile at the pin and the baseline."""

    def __init__(self, *, profile=True) -> None:
        self.profile = parse_profile(recorded("derived_profile", "valid")) if profile else None
        self.baseline = parse_baseline(recorded("inherited_baseline", "valid"))

    async def get_derived_profile(self, project_id, *, at=None):
        if self.profile is None:
            raise DerivedProfileNotFoundError("none")
        return self.profile

    async def get_inherited_baseline(self, project_id):
        return self.baseline


class _EmptyVault:
    """A vault holding nothing: a stored requirements artifact this run never stored."""

    async def retrieve(self, artifact_id):
        raise LookupError(f"no artifact {artifact_id}")

    async def list_artifacts(self, **_):
        return []


async def _clone(tmp_path):
    repo = build_repository(tmp_path / "sources" / "tally")
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    project_id = recorded("project_source_context", "valid")["project_id"]
    await clones.sync(project_id, str(repo.path), "refs/heads/main")
    return repo, clones


def _cycle(repo, requirements: str = "repo:file:README.md@current") -> Cycle:
    context = parse_source_context(recorded("project_source_context", "valid"))
    return Cycle(
        cycle_id="cyc_inc",
        project_id=context.project_id,
        created_at=NOW,
        created_by="campaign-launcher",
        prd_ref=None,
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"workload_sequence": [{"type": "proposal"}]},
        execution_overrides={
            "campaign_proposal": {
                "proposal_id": "prop_tally0001",
                "version": 1,
                "basis": "campaign_branch",
                "baseline_tree": _TREE,
                "objective": {
                    "statement": "s",
                    "allowed_scope": ["tally/**"],
                    "measurement": "m",
                    "requirements": requirements,
                },
                "max_revisions": 2,
            }
        },
        source_context=dataclasses.replace(
            context,
            repo_uri=str(repo.path),
            pinned_commit=repo.second_commit,
            pinned_from="campaign_branch",
        ),
        campaign_id="cmp_tally00001",
        kind="increment",
    )


async def _prepared(cycle: Cycle, clones, projects: _Projects):
    """``RunProvisioning.prepare`` for the cycle's proposal run, as ``execute_run`` calls it."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.execution.run_provisioning import RunInProgress
    from tests.unit.cycles.test_increment_evaluation_wiring import PROFILE

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(), artifact_vault=_EmptyVault(), queue=AsyncMock(),
        squad_profile=AsyncMock(), task_timeout=5.0, project_registry=projects,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(), proposal_evidence=NoOpProposalEvidence(),
        source_repository=clones,
    )  # fmt: skip
    executor._cycle_event_bus = MagicMock()
    run = Run("run_prop", cycle.cycle_id, 1, "queued", "system", "cfg", workload_type="proposal")
    executor._prepare_cycle_for_run = AsyncMock(return_value=(cycle, None))
    executor._cycle_registry.get_run.return_value = run
    executor._cycle_registry.get_latest_checkpoint.return_value = None
    executor._squad_profile.resolve_snapshot.return_value = (PROFILE, "sha")
    executor._load_plan_for_run = AsyncMock(return_value=None)
    executor._load_contract_for_run = AsyncMock(return_value=None)
    state = RunInProgress()
    await executor._run_provisioning.prepare(
        state, cycle.cycle_id, run.run_id, "full", forwarding_overrides=None
    )
    return state.plan


async def test_the_proposal_task_is_given_the_head_profile_verification_and_requirements(tmp_path):
    """Wiring (anti-pattern 6a). Bugs caught: the composition applied nowhere on the live path, so
    the proposal has no profile to place its criteria under and refuses every one; the head read at
    the Project's baseline rather than the pin; the previous verification not the one the change
    is compared with; the requirements read anywhere but the head; or another task given them."""
    repo, clones = await _clone(tmp_path)

    plan = await _prepared(_cycle(repo), clones, _Projects())

    [proposal] = [e for e in plan if PRODUCT_PROPOSAL_INPUT in e.inputs]
    assert proposal.task_type == "strategy.propose_increment"
    given = proposal.inputs[PRODUCT_PROPOSAL_INPUT]
    assert given["head"] == {"commit": repo.second_commit, "tree": _TREE}
    assert given["profile"]["placements"] == [
        {
            "runner": "unittest",
            "checks": ["parse", "ledger", "server", "report", "notify"],
            "covers": ["tally/**"],
            "template": "checks/check_criterion_{criterion}.py",
            "refused": None,
            "taken": [],
        }
    ]
    assert [g["id"] for g in given["profile"]["gaps"]] == [
        "missing_environment",
        "no_test_id_reader",
    ]
    assert given["previous_verification"]["source"] == (
        "the calibration record's inherited baseline"
    )
    assert [(c["id"], c["result"]) for c in given["previous_verification"]["checks"]] == [
        (c["id"], c["result"]) for c in recorded("inherited_baseline", "valid")["checks"]
    ]
    readme = (tmp_path / "sources" / "tally" / "README.md").read_text()
    assert given["requirements"] == {
        "ref": f"repo:file:README.md@{repo.second_commit}",
        "content": readme,
    }


@pytest.mark.parametrize(
    ("requirements", "profile", "why"),
    [
        ("repo:file:docs/missing.md@current", True, "can't be read at the head"),
        ("art_000000000000", True, "no artifact the vault holds"),
        ("repo:file:README.md@current", False, "has no derived profile at its pin"),
    ],
    ids=["a requirements file the head lacks", "an artifact not stored", "no profile at the pin"],
)
async def test_a_proposal_whose_input_cant_be_read_fails_its_run_naming_why(
    tmp_path, requirements, profile, why
):
    """§10t ruling 6's rule for every proposal input: a failed read raises, and the campaign
    proposes again under §24bn's bound. Bug caught: a proposal launched without its requirements
    or its runners, which then proposes against nothing."""
    from squadops.execution.execution_errors import _ExecutionError

    repo, clones = await _clone(tmp_path)

    with pytest.raises(_ExecutionError, match=why):
        await _prepared(_cycle(repo, requirements), clones, _Projects(profile=profile))
