"""A qa first call is sent the cut-off re-ask's clause as a last user message (the 2.5 plan's D12).

#2253's two pre-registered checks sent "keep any reasoning short so that the output fits." after a
qa call's own messages: on 46 calls the cap had cut, 39 finished against 14, and on 80 it had not
cut, it cost no pass the sample could see and about a third of the tokens. The steps are declared by
``TaskType.first_call_keeps_reasoning_short``, and the words are the re-ask's own asset.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
    QATestRepairHandler,
)
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_NOTE = "keep any reasoning short so that the output fits."
#: The note's sha256 as #2253's second check recorded it in its instruction arm's manifest
#: (``first_call_note.text_sha256``, 2026-10-28). The arm's folder is named by its first 8.
_MEASURED_NOTE_SHA256 = "f18fdf3805b571beb778bfcf4d88e20024f233b9050f9d278658ba88e4dedead"
_SUITE = "tests/test_runs.py"
_SUITE_TEXT = "def test_runs():\n    assert False\n"
_ANSWER = f"```python:{_SUITE}\ndef test_runs():\n    assert True\n```\n"


def _renderer() -> RequestTemplateRenderer:
    return RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )


def _context(*replies, renderer: bool = True, role: str = "qa"):
    """``replies``: per call, ``(content, at_cap)``."""
    calls: list[list] = []

    async def llm(messages, **kwargs):
        calls.append(messages)
        content, at_cap = replies[len(calls) - 1]
        return MagicMock(
            content=content,
            prompt_tokens=10,
            completion_tokens=kwargs["max_tokens"] if at_cap else 10,
            reasoning_tokens=None,
            reasoning_text="",
            termination=None,
        )

    ctx = MagicMock()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=llm)
    ctx.ports.llm.default_model = "m"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = _renderer() if renderer else None
    ctx.role_id = role
    ctx.task_id = "repair-run_ab12cd34-00-qa.test_repair"
    ctx.correlation_context = None
    return ctx, calls


def _repair_inputs(failed_task_type: str, path: str, text: str) -> dict:
    return {
        "prd": "Runs API",
        "failed_task_type": failed_task_type,
        "failure_evidence": {},
        "correction_decision": {},
        "expected_artifacts": [path],
        "acceptance_workspace_files": {path: text},
        "agent_config_overrides": {"max_completion_tokens": 12288},
    }


@pytest.mark.parametrize(
    ("handler", "inputs", "role", "noted"),
    [
        (QATestRepairHandler(), _repair_inputs("qa.test", _SUITE, _SUITE_TEXT), "qa", True),
        (
            QATestHandler(),
            {"prd": "Build a CLI", "artifact_contents": {"src/main.py": "def main(): ...\n"}},
            "qa",
            True,
        ),
        (
            DevelopmentCorrectionRepairHandler(),
            _repair_inputs("development.develop", "backend/routes.py", "def create(): ...\n"),
            "dev",
            False,
        ),
    ],
    ids=["qa.test_repair", "qa.test", "development.correction_repair"],
)
async def test_a_qa_first_call_ends_with_the_note_and_no_other_step_is_sent_it(
    handler, inputs, role, noted
):
    """Wiring, entered at ``handle`` through the real renderer and templates. Bug caught: the note
    sent to neither qa step, so D12 changes nothing the cut's evidence reads; or sent to a step it
    was never measured on."""
    ctx, calls = _context((_ANSWER, False), (_ANSWER, False), role=role)
    await handler.handle(ctx, inputs)

    first = calls[0]
    assert [m.role for m in first[:2]] == ["system", "user"]
    if noted:
        assert len(first) == 3
        assert (first[-1].role, first[-1].content) == ("user", _NOTE)
    else:
        assert len(first) == 2
        assert all(_NOTE not in m.content for m in first)


async def test_a_cut_qa_call_is_asked_again_with_the_note_kept_and_records_its_own_prompt():
    """Bug caught: the re-ask built on the caller's messages, dropping the note the first call
    had; or the note recorded as the call's prompt, so LangFuse shows a sentence in place of the
    qa request."""
    cut = f"```python:{_SUITE}\ndef test_runs():\n    assert Tr"
    ctx, calls = _context((cut, True), *[(_ANSWER, False)] * 4)
    handler = QATestRepairHandler()
    recorded: list[str] = []
    handler._record_generation = lambda context, prompt, *a, **k: recorded.append(prompt)

    await handler.handle(ctx, _repair_inputs("qa.test", _SUITE, _SUITE_TEXT))

    assert calls[1][:-1] == calls[0], "the re-ask is the first call, note and all, plus its fact"
    assert calls[1][-1].content.rstrip().endswith(f"every block closed, and {_NOTE}")
    # The two calls of the first ask; a later pass records its own prompt.
    assert recorded[:2] == [calls[0][1].content, calls[1][-1].content]


async def test_the_note_is_the_text_the_check_measured():
    """Bug caught: the asset edited, so production sends an instruction #2253 never measured. A
    change to it is a new measurement, not an edit."""
    note = (await _renderer().render("request.keep_reasoning_short", {})).content.strip()

    assert note == _NOTE
    assert hashlib.sha256(note.encode()).hexdigest() == _MEASURED_NOTE_SHA256


async def test_a_qa_handler_with_no_renderer_sends_its_first_call_without_the_note(caplog):
    """Edge: no renderer can state the note, so the call goes as the caller built it, and the
    log says so, as the re-ask isn't sent without one."""
    ctx, calls = _context((_ANSWER, False), (_ANSWER, False), renderer=False)
    with caplog.at_level(logging.WARNING):
        await QATestRepairHandler().handle(ctx, _repair_inputs("qa.test", _SUITE, _SUITE_TEXT))

    assert [m.role for m in calls[0]] == ["system", "user"]
    assert "keep_reasoning_short: qa_test_repair_handler has no request renderer" in caplog.text
