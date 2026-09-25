"""SIP-0096 §17a change 3 — the analyzer is asked one question of each contested row.

The failure evidence carries contested rows in their own block (change 2). These tests name
what each would catch: the question asked where no row is contested, or not asked where one is;
the analyzer's answer lost between its JSON and its outputs; and a malformed ruling rejecting
the whole analysis, which would send the round to NEEDS_REPLAN for an optional answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.impl.analyze_failure import DataAnalyzeFailureHandler
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROW = {
    "check": "acceptance:declared_imports",
    "params": {"file": "frontend/src/views/RunList.jsx"},
    "status": "failed",
    "passed": False,
    "reason": "unresolved import '@/lib/api'",
    "criterion_id": "vc-list",
}
_DISPUTE = {"by": "dev", "reason": "tsconfig.json declares the @/lib alias"}
_ANALYSIS = {
    "classification": "work_product",
    "analysis_summary": "The declared_imports check refused the @/lib alias import.",
    "contributing_factors": ["the alias is declared in tsconfig.json paths"],
}
_RULING = {
    "check": "acceptance:declared_imports",
    "file": "frontend/src/views/RunList.jsx",
    "criterion_id": "vc-list",
    "dispute_confirmed": True,
    "reason": "tsconfig.json compilerOptions.paths maps @/lib, so the import resolves",
}


def _context(answer: dict, sent: list) -> MagicMock:
    ctx = MagicMock()

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=json.dumps(answer), completion_tokens=40)

    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.assemble_task_only.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    ctx.task_id = "corr-run_ab12-00-data.analyze_failure"
    return ctx


def _evidence(*, contested: bool) -> dict:
    row = {**_ROW, "contested": _DISPUTE} if contested else _ROW
    evidence = {"validation_result": {"checks": [row]}}
    if contested:
        evidence["contested_rows"] = [row]
    return evidence


async def test_a_contested_row_is_asked_about_and_the_ruling_reaches_the_outputs():
    """Entered at ``handle`` on the real template. Bug caught: the question never rendered (the
    section declared and not passed, #1289's shape), or the ruling parsed and dropped before
    the outputs change 4 routes on."""
    sent: list = []
    result = await DataAnalyzeFailureHandler().handle(
        _context({**_ANALYSIS, "dispute_rulings": [_RULING]}, sent),
        {"prd": "Runs API", "failure_evidence": _evidence(contested=True)},
    )

    prompt = sent[0][-1].content
    assert "## Disputed checks" in prompt
    assert (
        "- check: `acceptance:declared_imports`, file: `frontend/src/views/RunList.jsx`, "
        "criterion_id: `vc-list` — failed: unresolved import '@/lib/api' — disputed by dev: "
        "tsconfig.json declares the @/lib alias"
    ) in prompt
    assert result.success, result.error
    assert result.outputs["dispute_rulings"] == [_RULING]


async def test_an_analysis_with_no_contested_row_is_asked_nothing_new():
    """The control: no contest, no question, no key — the analyzer's prompt and outputs for
    every uncontested failure are what they were before this change."""
    sent: list = []
    result = await DataAnalyzeFailureHandler().handle(
        _context(_ANALYSIS, sent),
        {"prd": "Runs API", "failure_evidence": _evidence(contested=False)},
    )

    assert "Disputed checks" not in sent[0][-1].content
    assert result.success, result.error
    assert "dispute_rulings" not in result.outputs


@pytest.mark.parametrize(
    "malformed",
    [
        {**_RULING, "dispute_confirmed": "yes"},
        {k: v for k, v in _RULING.items() if k != "dispute_confirmed"},
        {**_RULING, "reason": "  "},
        {**_RULING, "check": None},
        "confirmed",
    ],
    ids=["confirmed not a bool", "no verdict", "blank reason", "no check", "not an object"],
)
async def test_a_malformed_ruling_is_dropped_and_the_analysis_stands(malformed):
    """Bug caught: a strict schema rejecting the whole analysis over one bad ruling — the round
    routes to NEEDS_REPLAN and the failure is never diagnosed — or a malformed ruling kept, so
    a string "yes" confirms a dispute."""
    result = await DataAnalyzeFailureHandler().handle(
        _context({**_ANALYSIS, "dispute_rulings": [malformed, _RULING]}, []),
        {"prd": "Runs API", "failure_evidence": _evidence(contested=True)},
    )

    assert result.success, result.error
    assert result.outputs["dispute_rulings"] == [_RULING]
