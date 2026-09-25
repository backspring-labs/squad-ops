"""A call that spends its whole completion budget and writes nothing is asked again once, with
that fact (1.8.2 plan §3.2 item 2).

The provider's completion limit counts reasoning tokens: 1.8.1's cap-exhausted emissions each
reported ``completion_tokens=12288`` — the squad profile's flat cap — with ``chars=0`` and
44–49k reasoning characters: a qa self-eval pass, a qa repair and a dev repair. Nothing asked
them again; the budget cannot be separated on this provider, so the R1 shape (#1372) applies at
the one seam every call passes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.impl.repair_handlers import DevelopmentCorrectionRepairHandler
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create(payload):\n    return Run(**payload.dict())\n"
_EDIT = (
    "```edit:backend/routes.py\n<<<<<<< SEARCH\ndef create(payload):\n"
    "    return Run(**payload.dict())\n=======\ndef create(payload):\n"
    "    return Run(**payload.dict(exclude_none=True))\n>>>>>>> REPLACE\n```\n"
)


def _context(*shapes, renderer: bool = True):
    """``shapes``: per call, ``"cap"`` (the whole budget, nothing written), ``"short"`` (empty
    under the budget) or the content to return."""
    calls: list[tuple[list, dict]] = []

    async def llm(messages, **kwargs):
        calls.append((messages, kwargs))
        shape = shapes[len(calls) - 1]
        cap = kwargs["max_tokens"]
        return MagicMock(
            content="" if shape in ("cap", "short") else shape,
            prompt_tokens=10,
            completion_tokens=cap if shape == "cap" else 10,
            reasoning_tokens=None,
            reasoning_text="thinking " * 500 if shape == "cap" else "",
        )

    ports = MagicMock()
    ports.llm.chat_stream_with_usage = AsyncMock(side_effect=llm)
    ports.llm.default_model = "m"
    ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ports.llm_observability = None
    ports.request_renderer = (
        RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
        )
        if renderer
        else None
    )
    ctx = MagicMock()
    ctx.ports = ports
    ctx.role_id = "dev"
    ctx.task_id = "repair-run_ab12cd34-00-development.correction_repair"
    ctx.correlation_context = None
    return ctx, calls


def _inputs():
    return {
        "prd": "Runs API",
        "failed_task_type": "development.develop",
        "failure_evidence": {},
        "correction_decision": {},
        "expected_artifacts": ["backend/routes.py"],
        "acceptance_workspace_files": {"backend/routes.py": _ROUTES},
        # The squad profile's flat cap, as full-38 and solo set it on every agent.
        "agent_config_overrides": {"max_completion_tokens": 12288},
    }


async def test_a_cap_exhausted_repair_is_asked_again_with_the_fact_and_its_answer_is_used(caplog):
    """Wiring, entered at ``handle`` through the real renderer and templates, on the dev repair
    shape 1.8.1 met. Bug this catches: the 12,288 tokens of reasoning discarded and the round
    refunded with nothing learned, when one more call told what happened lands the edit."""
    ctx, calls = _context("cap", _EDIT)
    with caplog.at_level(logging.INFO):
        result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    assert len(calls) == 2
    retry_prompt = calls[1][0][-1].content
    cap = calls[0][1]["max_tokens"]
    assert f"the whole {cap}-token output" in retry_prompt
    assert calls[1][0][:-1] == calls[0][0], "the retry is the same call with the fact appended"
    assert result.success, result.error
    shapes = [r.getMessage() for r in caplog.records if "emission shape:" in r.getMessage()]
    assert any(":cap_exhausted emission shape: chars=0" in s for s in shapes)
    assert "cap_exhausted_retry handler=" in caplog.text


@pytest.mark.parametrize(
    ("shapes", "calls_made"),
    [
        (("short",), 1),  # empty under the cap: not a cap exhaustion, the ordinary path owns it
        ((_EDIT,), 1),  # an answer: nothing to do
        (("cap", "cap"), 2),  # once: a second exhaustion is returned, not asked again
    ],
)
async def test_only_a_cap_exhaustion_is_asked_again_and_only_once(shapes, calls_made):
    ctx, calls = _context(*shapes)
    await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())
    assert len(calls) == calls_made


async def test_without_a_renderer_to_state_the_fact_it_is_not_asked_again(caplog):
    """The fact lives in its asset (CLAUDE.md #448); no inline copy is improvised."""
    ctx, calls = _context("cap", _EDIT, renderer=False)
    with caplog.at_level(logging.WARNING):
        await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())
    assert len(calls) == 1
    assert "not asked again" in caplog.text
