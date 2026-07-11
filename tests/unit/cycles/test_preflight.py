"""
Unit tests for the cycle-create preflight — SIP-0095 capability check (#172) +
model-availability check (#224, Spark half).

Capability bug classes guarded: false-positive blocks on a satisfiable squad; the
wrong required-role set per workload; unhelpful error text; **incorrectly blocking
a builder-less build cycle** (option-A scope); disabled agents counting toward
roles; multi-workload non-aggregation; combine/decision semantics.

Model-availability bug classes guarded (SIP §6.2/§6.3/§137): blocking on
unverifiable evidence (backend unreachable MUST warn-and-allow, not block);
conflating a reachable-empty list with an unreachable backend; false blocks from
tag normalization (`llama3.2` vs `llama3.2:latest`); false *passes* from
family inference (`qwen3:7b` satisfying `qwen3:27b`); disabled agents' models
being checked; non-actionable error text.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.cycles.preflight import (
    Finding,
    PreflightDecision,
    combine,
    model_availability_decision,
    required_check_tooling_decision,
    required_roles_decision,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PLAN_ROLES = ("strat", "dev", "qa", "data", "lead")


def _profile(roles, *, profile_id="test-squad", disabled=()):
    agents = tuple(
        AgentProfileEntry(agent_id=f"agent-{r}", role=r, model="m", enabled=(r not in disabled))
        for r in roles
    )
    return SquadProfile(
        profile_id=profile_id, name="Test", description="", version=1, agents=agents, created_at=NOW
    )


def _ws(*types):
    return {"workload_sequence": [{"type": t} for t in types]}


def test_full_plan_squad_satisfies_framing_and_evaluation():
    profile = _profile(PLAN_ROLES)
    for wtype in ("framing", "evaluation"):
        decision = required_roles_decision(profile, _ws(wtype))
        assert decision.rejected is False
        assert decision.blocking == ()


@pytest.mark.parametrize(
    ("wtype", "missing_role", "squad_roles"),
    [
        ("wrapup", "data", ("qa", "lead")),  # wrapup needs {data, qa, lead}
        ("refinement", "qa", ("lead", "dev")),  # refinement needs {lead, qa}
        ("framing", "strat", ("dev", "qa", "data", "lead")),  # plan needs strat too
    ],
)
def test_missing_required_role_blocks_naming_workload_and_role(wtype, missing_role, squad_roles):
    profile = _profile(squad_roles, profile_id="lite")
    decision = required_roles_decision(profile, _ws(wtype))

    assert decision.rejected is True
    codes = {f.code for f in decision.blocking}
    assert codes == {"missing_role"}
    # the finding for the missing role names the workload, the role, and stays a block
    hit = next(f for f in decision.blocking if f"role `{missing_role}`" in f.message)
    assert hit.severity == "block"
    assert f"workload `{wtype}`" in hit.message
    assert "squad profile `lite`" in hit.message
    assert missing_role in hit.message


def test_missing_role_message_is_actionable():
    profile = _profile(("qa", "lead"), profile_id="lite")  # wrapup missing `data`
    decision = required_roles_decision(profile, _ws("wrapup"))

    (finding,) = decision.blocking
    assert finding.message == (
        "workload `wrapup` requires role `data`, but squad profile `lite` provides "
        "`lead`, `qa`. Choose a profile with a `data` agent or adjust the requested workloads."
    )


def test_build_and_implementation_on_builderless_squad_do_not_block():
    """Option A: `implementation` / `build_tasks` impose NO static builder requirement —
    a builder-less squad is a valid graceful fallback, not a create-time block."""
    builderless = _profile(PLAN_ROLES)  # no `builder` role

    # workload-sequence form
    assert required_roles_decision(builderless, _ws("implementation")).rejected is False
    # legacy form: build_tasks with no plan_tasks requirement
    legacy = {"plan_tasks": False, "build_tasks": True}
    assert required_roles_decision(builderless, legacy).rejected is False


def test_legacy_plan_tasks_default_true_requires_plan_roles():
    profile = _profile(("strat", "dev", "qa", "lead"))  # missing `data`
    # no workload_sequence → legacy path; plan_tasks defaults True
    decision = required_roles_decision(profile, {})

    assert decision.rejected is True
    assert any("plan_tasks" in f.message and "role `data`" in f.message for f in decision.blocking)


def test_legacy_plan_tasks_false_allows_regardless_of_roles():
    profile = _profile(("lead",))  # almost nothing
    decision = required_roles_decision(profile, {"plan_tasks": False, "build_tasks": True})
    assert decision.rejected is False


def test_disabled_agent_does_not_satisfy_a_required_role():
    """A `data` agent that is disabled must not count — wrapup still blocks on `data`."""
    profile = _profile(("data", "qa", "lead"), disabled=("data",))
    decision = required_roles_decision(profile, _ws("wrapup"))

    assert decision.rejected is True
    assert any("role `data`" in f.message for f in decision.blocking)


def test_multiple_workloads_aggregate_required_roles():
    """A sequence checks every workload's roles, not just the first."""
    # framing needs strat; wrapup needs data. Squad has neither.
    profile = _profile(("dev", "qa", "lead"))
    decision = required_roles_decision(profile, _ws("framing", "wrapup"))

    blocked_roles = {
        r for f in decision.blocking for r in ("strat", "data") if f"role `{r}`" in f.message
    }
    assert {"strat", "data"} <= blocked_roles


def test_combine_any_block_rejects_and_warnings_ride_alongside():
    block = PreflightDecision(blocking=(Finding("missing_role", "block", "boom"),))
    warn = PreflightDecision(warnings=(Finding("model_unverifiable", "warning", "heads up"),))

    merged = combine(block, warn)

    assert merged.rejected is True
    assert merged.summary() == "boom"  # only blocking messages
    assert [f.message for f in merged.warnings] == ["heads up"]  # warning preserved, not dropped


def test_empty_decision_is_not_rejected():
    d = PreflightDecision()
    assert d.rejected is False
    assert d.summary() == ""


# --- model_availability_decision (SIP §6.2/§6.3, #224 — Spark half) ------------


def _model_profile(models, *, profile_id="test-squad", disabled_idx=()):
    """Profile whose enabled agents carry the given model names."""
    agents = tuple(
        AgentProfileEntry(
            agent_id=f"agent-{i}", role=f"r{i}", model=m, enabled=(i not in disabled_idx)
        )
        for i, m in enumerate(models)
    )
    return SquadProfile(
        profile_id=profile_id, name="Test", description="", version=1, agents=agents, created_at=NOW
    )


def test_all_required_models_pulled_allows():
    profile = _model_profile(["qwen3:27b", "nomic-embed-text"])
    decision = model_availability_decision(profile, ["qwen3:27b", "nomic-embed-text", "extra:1b"])
    assert decision.rejected is False
    assert decision.blocking == ()
    assert decision.warnings == ()


def test_missing_model_blocks_with_actionable_message():
    profile = _model_profile(["qwen3:27b"], profile_id="full")
    decision = model_availability_decision(profile, ["qwen3:7b", "llama3.2:latest"])

    assert decision.rejected is True
    (finding,) = decision.blocking
    assert finding.code == "model_unavailable"
    assert finding.severity == "block"
    assert "`qwen3:27b`" in finding.message  # the required-but-missing model
    assert "squad profile `full`" in finding.message
    assert "qwen3:7b" in finding.message  # shows what the backend actually has


def test_unreachable_backend_warns_and_allows():
    """None pulled list = unverifiable → warn, never block (SIP §6.3, AC#5)."""
    profile = _model_profile(["qwen3:27b"])
    decision = model_availability_decision(profile, None)

    assert decision.rejected is False  # allowed, not blocked on missing evidence
    (warning,) = decision.warnings
    assert warning.code == "model_unverifiable"
    assert warning.severity == "warning"
    assert "`qwen3:27b`" in warning.message


def test_empty_pulled_list_is_verifiable_and_blocks():
    """Reachable-but-empty (a list, not None) is verifiable → blocks, unlike unreachable."""
    profile = _model_profile(["qwen3:27b"])
    decision = model_availability_decision(profile, [])
    assert decision.rejected is True
    assert decision.blocking[0].code == "model_unavailable"


def test_tagless_model_matches_latest_no_false_block():
    """`llama3.2` ⇔ `llama3.2:latest` (canonical tag) — no false block (SIP §137)."""
    profile = _model_profile(["llama3.2"])
    decision = model_availability_decision(profile, ["llama3.2:latest"])
    assert decision.rejected is False


def test_different_tag_blocks_no_family_inference():
    """`qwen3:7b` must NOT satisfy a required `qwen3:27b` — no family inference (§137)."""
    profile = _model_profile(["qwen3:27b"])
    decision = model_availability_decision(profile, ["qwen3:7b"])
    assert decision.rejected is True


def test_disabled_agent_model_not_checked():
    """A missing model belonging to a disabled agent must not block."""
    profile = _model_profile(["present:1b", "missing:27b"], disabled_idx={1})
    decision = model_availability_decision(profile, ["present:1b"])
    assert decision.rejected is False


def test_multiple_missing_models_each_block():
    profile = _model_profile(["a:1b", "b:2b", "c:3b"])
    decision = model_availability_decision(profile, ["a:1b"])

    assert len(decision.blocking) == 2
    missing = {m for f in decision.blocking for m in ("b:2b", "c:3b") if f"`{m}`" in f.message}
    assert missing == {"b:2b", "c:3b"}


def test_no_enabled_models_is_empty_decision():
    """No enabled agents with models → nothing to check, even with no backend."""
    profile = _model_profile(["x:1b"], disabled_idx={0})
    decision = model_availability_decision(profile, None)
    assert decision.rejected is False
    assert decision.blocking == () and decision.warnings == ()


# --- required-check tooling parity (SIP-0096 §6.5, slice-4a-2) -----------------
# frontend_build needs `node`; tests_pass/required_files need no external tooling.


def test_required_tooling_backed_check_blocks_when_tooling_absent():
    """The point of the guard: a profile requiring the frontend build on a
    deployment that provisions no Node is rejected at create-time — not left to
    surface mid-run as blocked_unverified."""
    decision = required_check_tooling_decision(["frontend_build"], available_tooling=frozenset())
    assert decision.rejected is True
    assert decision.blocking[0].code == "check_tooling_unavailable"
    assert "frontend_build" in decision.blocking[0].message


def test_required_tooling_backed_check_passes_when_provisioned():
    decision = required_check_tooling_decision(["frontend_build"], available_tooling={"node"})
    assert decision.rejected is False
    assert decision.warnings == ()


def test_unresolved_provisioning_warns_never_blocks():
    """None ⇒ provisioning unverifiable ⇒ warn-and-allow, mirroring the model
    check — never block on missing evidence."""
    decision = required_check_tooling_decision(["frontend_build"], available_tooling=None)
    assert decision.rejected is False
    assert decision.warnings[0].code == "check_tooling_unverifiable"


def test_tooling_free_required_checks_never_block():
    """tests_pass / required_files declare no external tooling, so requiring them
    is never a tooling-parity concern even when nothing is provisioned."""
    decision = required_check_tooling_decision(
        ["tests_pass", "required_files"], available_tooling=frozenset()
    )
    assert decision.rejected is False
    assert decision.warnings == ()


def test_empty_required_checks_is_empty_decision():
    decision = required_check_tooling_decision([], available_tooling=None)
    assert decision.blocking == () and decision.warnings == ()
