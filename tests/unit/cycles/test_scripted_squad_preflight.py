"""The create-time check of a scripted squad's script (#2495), on the shipped `machinery` profile.

The profile is read from ``config/squad-profiles.yaml`` as the config provider reads it, so a
change to the shipped profile that breaks the rule fails here. The wiring test enters at the
cycle-create route's ``_run_create_preflight`` with the deploy's LLM port, ``with_scripted_model``,
which is also what makes the model-availability check admit ``scripted``.
"""

from __future__ import annotations

import dataclasses
import textwrap
from pathlib import Path

import pytest

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from adapters.llm.factory import create_llm_provider, with_scripted_model
from adapters.llm.script_positions import InProcessScriptPositions
from squadops.cycles.models import PreflightRejectedError
from squadops.cycles.preflight import scripted_squad_decision
from squadops.llm.script import ScriptLibrary, script_version

pytestmark = [pytest.mark.domain_orchestration]

REPO = Path(__file__).resolve().parents[3]
SCRIPT = textwrap.dedent(
    """\
    script: shelf-flag
    description: one analysis
    answers:
      - task_type: strategy.analyze_prd
        occurrence: 1
        call: 1
        content: "# Analysis"
    """
)
VERSION = script_version(SCRIPT.encode())


async def _profile(profile_id: str):
    return await ConfigSquadProfile(REPO / "config" / "squad-profiles.yaml").get_profile(profile_id)


@pytest.fixture
def library(tmp_path) -> ScriptLibrary:
    (tmp_path / "shelf-flag.yaml").write_text(SCRIPT)
    return ScriptLibrary(tmp_path)


async def test_the_shipped_machinery_profile_is_scripted_throughout_and_takes_a_pinned_script(
    library,
):
    """Bug caught: a machinery agent left on a real model, so part of a 'scripted' run's evidence
    was a model's; or a pinned script refused, so the profile could never run."""
    machinery = await _profile("machinery")
    assert {a.model for a in machinery.agents if a.enabled} == {"scripted"}

    decision = scripted_squad_decision(machinery, {"llm_script": f"shelf-flag@{VERSION}"}, library)

    assert decision.blocking == ()
    assert [(w.code, w.message) for w in decision.warnings] == [
        (
            "llm_script_declared",
            f"this cycle is SCRIPTED: every call is answered from shelf-flag@{VERSION} (1 "
            "answers), no model. It checks the machinery and is never evidence about a model or "
            "a prompt.",
        )
    ]


@pytest.mark.parametrize(
    ("profile_id", "config", "code", "says"),
    [
        ("machinery", {}, "llm_script_missing", "holds ['shelf-flag']"),
        (
            "machinery",
            {"llm_script": "shelf-flag"},
            "llm_script_unversioned",
            f"set llm_script=shelf-flag@{VERSION}",
        ),
        (
            "machinery",
            {"llm_script": "shelf-flag@0123456789ab"},
            "llm_script_unusable",
            f"holds shelf-flag@{VERSION}",
        ),
        (
            "machinery",
            {"llm_script": "shelf-flog@0123456789ab"},
            "llm_script_unusable",
            "no script 'shelf-flog'",
        ),
        (
            "lite",
            {"llm_script": f"shelf-flag@{VERSION}"},
            "llm_script_unread",
            "no agent on the `scripted` model",
        ),
    ],
)
async def test_a_scripted_cycle_that_would_fail_or_mislabel_is_refused_at_create(
    library, profile_id, config, code, says
):
    """Bugs caught: each one surfacing a task into the run instead of in seconds, and the last
    labelling a model run scripted, which takes it out of every model reading."""
    decision = scripted_squad_decision(await _profile(profile_id), config, library)

    assert [f.code for f in decision.blocking] == [code]
    assert says in decision.blocking[0].message


async def test_a_squad_mixing_scripted_and_model_agents_is_refused(library):
    """Bug caught: a half-scripted squad admitted, so its model half's plans read as a model's."""
    machinery = await _profile("machinery")
    mixed = dataclasses.replace(
        machinery,
        agents=(
            dataclasses.replace(machinery.agents[0], model="qwen2.5:7b"),
            *machinery.agents[1:],
        ),
    )

    decision = scripted_squad_decision(mixed, {"llm_script": f"shelf-flag@{VERSION}"}, library)

    assert [f.code for f in decision.blocking] == ["scripted_squad_mixed"]


async def test_a_model_profile_with_no_script_is_untouched(library):
    decision = scripted_squad_decision(await _profile("lite"), {}, library)
    assert (decision.blocking, decision.warnings) == ((), ())


async def test_the_create_route_admits_a_pinned_machinery_cycle_and_refuses_an_unpinned_one(
    tmp_path, monkeypatch
):
    """Wiring, at the create route's preflight with the deploy's port. Bugs caught: the decision
    not composed into the route, and `scripted` missing from the port's listing, so the
    availability check refused every machinery cycle as 'model not pulled'."""
    from squadops.api.routes.cycles import cycles as cycles_route
    from squadops.api.routes.cycles.cycles import _run_create_preflight
    from squadops.cycles.preflight import PreflightDecision

    async def _no_sandbox():  # the sandbox check reads the deploy's environment; not under test
        return PreflightDecision()

    monkeypatch.setattr(cycles_route, "_sandbox_preflight_decision", _no_sandbox)
    (tmp_path / "shelf-flag.yaml").write_text(SCRIPT)
    monkeypatch.setattr("squadops.llm.script.PACKAGED_SCRIPTS_DIR", tmp_path)
    engine = create_llm_provider(
        provider="ollama", base_url="http://x.invalid:1", default_model="m"
    )

    async def _pulled():
        return []

    monkeypatch.setattr(engine, "list_available_models", _pulled)
    port = with_scripted_model(engine, InProcessScriptPositions())
    machinery = await _profile("machinery")
    config = {"memory": "disabled", "llm_script": f"shelf-flag@{VERSION}"}

    warnings = await _run_create_preflight(port, machinery, config, campaign_cycle=False)

    assert "llm_script_declared" in [w.code for w in warnings]
    assert "model_unavailable" not in [w.code for w in warnings]
    with pytest.raises(PreflightRejectedError, match="the cycle must name its script"):
        await _run_create_preflight(port, machinery, {"memory": "disabled"}, campaign_cycle=False)
