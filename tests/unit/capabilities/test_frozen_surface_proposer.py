"""The frozen surface reaches the plan author (pf-42).

Knowing what the frozen files declare is useless if the proposer never sees it. These
cover the transport end to end: the executor-side injection that puts the index on the
proposer's envelope, the handler section that renders it, and a real render of the
managed asset proving the field names and relative imports actually arrive in the prompt.

Same conditions as the bind-criteria section it sits beside — bind mode only, dev/qa
only — so an author-mode cycle keeps today's prompt byte-identical.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning_tasks import (
    DevelopmentProposePlanTasksHandler,
    QaProposePlanTasksHandler,
    StrategyProposePlanGuidanceHandler,
)
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.cycles.task_plan import inject_contract_inputs
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _contract() -> VerificationContract:
    return VerificationContract.from_dict(emit_contract_dict(_manifest()))


# --- executor-side injection --------------------------------------------------- #


def test_proposer_envelope_carries_the_frozen_surface():
    inputs: dict = {}
    inject_contract_inputs(inputs, _contract(), "development.propose_plan_tasks", _manifest())

    index = inputs["frozen_surface_index"]
    assert "RunEvent(id, title, datetime, location" in index
    assert "`.routes`" in index
    assert "meeting_location" not in index


def test_build_tasks_do_not_carry_it():
    """Only the proposers author checks; a develop task has no use for the index."""
    inputs: dict = {}
    inject_contract_inputs(inputs, _contract(), "development.develop", _manifest())

    assert "frozen_surface_index" not in inputs


def test_author_mode_injects_nothing():
    inputs: dict = {}
    inject_contract_inputs(inputs, None, "development.propose_plan_tasks", _manifest())

    assert inputs == {}


def test_bind_mode_without_a_manifest_still_injects_the_criteria_index():
    """The frozen surface is additive — losing it must not cost the bind index."""
    inputs: dict = {}
    inject_contract_inputs(inputs, _contract(), "development.propose_plan_tasks", None)

    assert "frozen_surface_index" not in inputs
    assert inputs["contract_criteria_index"]


# --- handler section ----------------------------------------------------------- #


@pytest.mark.parametrize(
    "handler_cls", [DevelopmentProposePlanTasksHandler, QaProposePlanTasksHandler]
)
async def test_dev_and_qa_proposers_render_the_section(handler_cls):
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="FROZEN SURFACE")

    out = await handler_cls()._frozen_surface_section(
        renderer, {"frozen_surface_index": "- `backend/models.py` — defines RunEvent(id)"}
    )

    assert out == "FROZEN SURFACE"
    renderer.render.assert_awaited_once_with(
        "request.plan_frozen_surface_appendix",
        {"frozen_surface_index": "- `backend/models.py` — defines RunEvent(id)"},
    )


async def test_strategy_proposer_does_not_render_it():
    """Strategy proposes guidance, not build tasks — it authors no checks."""
    renderer = AsyncMock()

    out = await StrategyProposePlanGuidanceHandler()._frozen_surface_section(
        renderer, {"frozen_surface_index": "- `backend/models.py`"}
    )

    assert out == ""
    renderer.render.assert_not_awaited()


async def test_absent_index_renders_nothing():
    renderer = AsyncMock()

    out = await DevelopmentProposePlanTasksHandler()._frozen_surface_section(renderer, {})

    assert out == ""
    renderer.render.assert_not_awaited()


# --- the real asset ------------------------------------------------------------ #


async def test_real_asset_renders_the_declarations_into_the_prompt():
    """A live render — the facts must survive the template, not just the function."""
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.prompts.renderer import RequestTemplateRenderer

    templates_dir = _MANIFEST_PATH.parents[2] / "src" / "squadops" / "prompts" / "request_templates"
    renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=templates_dir.parent / "fragments",
            templates_path=templates_dir,
        )
    )

    inputs: dict = {}
    inject_contract_inputs(inputs, _contract(), "development.propose_plan_tasks", _manifest())
    section = await DevelopmentProposePlanTasksHandler()._frozen_surface_section(renderer, inputs)

    # the two facts pf-42 invented
    assert "RunEvent(id, title, datetime, location" in section
    assert "`.routes`" in section
    # and the rule that makes them matter
    assert "frozen" in section.lower()
    assert "expected_artifacts" in section
