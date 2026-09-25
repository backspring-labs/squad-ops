"""The repair brief's Correction Decision section is optional (SIP-0108 §10i item 5).

The runner hands every repair `decision_outputs` — `{}` when the protocol declares no
`decide` step. Before this, the template's fixed heading rendered "The lead reviewed the
failure and chose to patch (not rewind). Their rationale: {}" on every Solo repair: a lead
that did not exist, quoted. Now the section is one of two templates, chosen by whether a
decision exists, and the Solo brief states the deterministic fact in its place.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
    _decision_present,
)
from squadops.prompts.renderer import RequestTemplateRenderer

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create(payload):\n    return Run(**payload.dict())\n"
_EDIT = (
    "```edit:backend/routes.py\n<<<<<<< SEARCH\ndef create(payload):\n"
    "    return Run(**payload.dict())\n=======\ndef create(payload):\n"
    "    return Run(**payload.dict(exclude_none=True))\n>>>>>>> REPLACE\n```\n"
)


def _context(*responses: str, renderer: bool = True):
    llm = AsyncMock()
    llm.chat_stream_with_usage.side_effect = [
        MagicMock(content=r, prompt_tokens=10, completion_tokens=10, reasoning_tokens=None)
        for r in responses
    ]
    llm.default_model = "test-model"
    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ports.llm_observability = None
    if renderer:
        ports.request_renderer = RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
        )
    else:
        ports.request_renderer = None
    ctx = MagicMock()
    ctx.ports = ports
    ctx.role_id = "dev"
    ctx.correlation_context = None
    return ctx


def _inputs(decision):
    return {
        "prd": "Runs API",
        "failed_task_type": "development.develop",
        "failure_evidence": {},
        "correction_decision": decision,
        "expected_artifacts": ["backend/routes.py"],
        "acceptance_workspace_files": {"backend/routes.py": _ROUTES},
    }


def _user_prompt(ctx) -> str:
    return ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][-1].content


async def test_a_solo_repair_states_the_rule_and_never_quotes_an_absent_lead():
    """Wiring at ``handle`` through the REAL renderer and templates. Bug this catches: the
    Solo brief rendering "The lead reviewed the failure … Their rationale: {}" — the exact
    text every repair on the Solo arm would have carried."""
    ctx = _context(_EDIT)
    await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs({}))
    prompt = _user_prompt(ctx)
    assert "### Correction Decision" in prompt
    assert "declares repair alone, so the path is patch by rule" in prompt
    assert "The lead reviewed" not in prompt
    assert "{}" not in prompt


async def test_a_squad_repair_still_carries_the_leads_rationale():
    """The squad's brief is byte-for-byte the section it always had. Bug this catches: the
    lead path lost while making the section optional — every squad repair silently briefed
    without its decision."""
    ctx = _context(_EDIT)
    decision = {"correction_path": "patch", "decision_rationale": "the join handler drops a field"}
    await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs(decision))
    prompt = _user_prompt(ctx)
    assert "The lead reviewed the failure and chose to patch (not rewind)" in prompt
    assert "Path: patch\n\nthe join handler drops a field" in prompt
    assert "patch by rule" not in prompt


async def test_the_inline_fallback_agrees_with_the_templates():
    """The no-renderer path (the SIP-0084 accommodation) states the same fact. Bug this
    catches: the fallback still printing the raw ``{}`` the lead template was fixed for."""
    ctx = _context(_EDIT, renderer=False)
    await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs({}))
    prompt = _user_prompt(ctx)
    assert "patch by rule" in prompt and "{}" not in prompt


def test_a_decision_is_present_only_when_it_says_something():
    """The predicate both paths key on. Bug this catches: ``{}`` or ``""`` read as a decision
    (the defect), or a path-only decision read as absent (the lead's choice dropped)."""
    assert _decision_present({}) is False
    assert _decision_present(None) is False
    assert _decision_present("") is False
    assert _decision_present({"correction_path": "patch"}) is True
    assert _decision_present({"decision_rationale": "because"}) is True
    assert _decision_present("patch — the analyzer named the handler") is True


async def test_the_repair_records_which_decision_section_its_brief_carried(caplog):
    """#1661, wiring at ``handle`` through the real renderer and templates, on both arms'
    shapes. The rendered prompt is stored only as LangFuse's first 10,000 characters and the
    decision section comes after them, so the 1.8.1 window's I2 and H3 rule reading could not
    be asked on any roll. Bug this catches: the fact recorded from something other than the
    section that rendered (a lead's rationale briefed while the record says "rule")."""
    import logging

    for decision, kind, phrase in (
        ({}, "rule", "patch by rule"),
        (
            {"correction_path": "patch", "decision_rationale": "drops a field"},
            "lead",
            "The lead reviewed",
        ),
    ):
        ctx = _context(_EDIT)
        caplog.clear()
        with caplog.at_level(logging.INFO):
            result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs(decision))
        assert phrase in _user_prompt(ctx)
        assert result.outputs["revision_form"]["decision_section"] == kind
        (line,) = [
            r.getMessage() for r in caplog.records if "repair_revision_form" in r.getMessage()
        ]
        assert f'"decision_section": "{kind}"' in line


def test_the_record_requires_the_decision_section():
    """Require, don't default (2026-09-14): a caller that forgets the fact must fail, not
    record a guess."""
    import pytest

    with pytest.raises(TypeError):
        DevelopmentCorrectionRepairHandler()._record_revision_form({}, MagicMock(outputs={}))
