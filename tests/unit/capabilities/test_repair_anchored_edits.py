"""SIP-0107 step 4, second half (#1213) — a repair revises an existing file by anchored edit.

Entry point: ``DevelopmentCorrectionRepairHandler.handle`` with the real request templates
rendered by the real renderer, and a model scripted to answer. Each test names what it catches:
the edit form never reaching the model, an edit applied against a tree other than the one the
verifier builds, a refused edit silently dropped or silently rewritten, a second retry economy.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.anchored_edits import EMISSION_FAILURE_ANCHORED_EDIT_REFUSED
from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
)
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"

_ROUTES = (
    "from fastapi import APIRouter\n"
    "router = APIRouter()\n"
    "\n"
    '@router.post("/runs")\n'
    "def create(payload):\n"
    "    return Run(**payload.dict())\n"
    "\n"
    '@router.get("/runs")\n'
    "def list_runs():\n"
    "    return Run(**payload.dict())\n"
)

_GOOD_EDIT = (
    "```edit:backend/routes.py\n"
    "<<<<<<< SEARCH\n"
    "def create(payload):\n"
    "    return Run(**payload.dict())\n"
    "=======\n"
    "def create(payload):\n"
    "    return Run(**payload.dict(exclude_none=True))\n"
    ">>>>>>> REPLACE\n"
    "```\n"
)
_AMBIGUOUS_EDIT = (
    "```edit:backend/routes.py\n"
    "<<<<<<< SEARCH\n"
    "    return Run(**payload.dict())\n"
    "=======\n"
    "    return Run(**payload.dict(exclude_none=True))\n"
    ">>>>>>> REPLACE\n"
    "```\n"
)


def _context(*responses: str):
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
    ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    return ctx


def _inputs(**extra):
    return {
        "prd": "Runs API",
        "failed_task_type": "development.develop",
        "failure_evidence": {},
        "correction_decision": {"correction_path": "patch"},
        "expected_artifacts": ["backend/routes.py", "backend/new_helper.py"],
        "acceptance_workspace_files": {
            "backend/routes.py": _ROUTES,
            "backend/main.py": "app = 1\n",
        },
        **extra,
    }


def _user_prompt(ctx, call: int) -> str:
    messages = ctx.ports.llm.chat_stream_with_usage.await_args_list[call].args[0]
    return messages[-1].content


async def test_an_anchored_repair_becomes_the_whole_file_with_only_the_anchor_changed():
    """Bug caught: the edit form never reaching the model, or an edit applied to a tree other
    than the workspace the verifier materialises — the stored file would not be the file the
    edit was resolved against."""
    ctx = _context(_GOOD_EDIT)

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    prompt = _user_prompt(ctx, 0)
    assert "Editing a File That Already Exists" in prompt
    assert "- `backend/routes.py`" in prompt
    assert (
        "`backend/new_helper.py`"
        not in prompt.split("Editing a File That Already Exists")[1].split("Rules")[0]
    )
    (artifact,) = result.outputs["artifacts"]
    assert artifact["name"] == "backend/routes.py"
    assert artifact["content"] == _ROUTES.replace(
        "def create(payload):\n    return Run(**payload.dict())\n",
        "def create(payload):\n    return Run(**payload.dict(exclude_none=True))\n",
    )
    assert result.outputs["anchored_edits"]["accepted"] is True
    assert "emission_failure" not in result.outputs
    assert ctx.ports.llm.chat_stream_with_usage.await_count == 1


async def test_a_refused_edit_is_retried_once_with_its_typed_reason():
    """§22. Bug caught: the model re-rolled blind on the same wrong anchor, or the first of two
    matches applied instead of the refusal being said."""
    ctx = _context(_AMBIGUOUS_EDIT, _GOOD_EDIT)

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    retry_prompt = _user_prompt(ctx, 1)
    assert "Your Previous Edits Were Not Applied" in retry_prompt
    assert "`backend/routes.py`: anchor_ambiguous — the anchor occurs 2 times" in retry_prompt
    assert "Your Previous Edits Were Not Applied" not in _user_prompt(ctx, 0)
    assert result.outputs["anchored_edits"]["accepted"] is True
    assert result.outputs["anchored_edit_retry"]["first_refusals"][0].startswith(
        "`backend/routes.py`: anchor_ambiguous"
    )


async def test_a_retry_refused_too_returns_the_refusal_and_nothing_else():
    """§22: one retry, then the refusal stands. Bug caught: a third call (a second retry economy
    inside the round), or a partially applied or guessed file handed to verification."""
    ctx = _context(_AMBIGUOUS_EDIT, _AMBIGUOUS_EDIT, _GOOD_EDIT)

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    assert ctx.ports.llm.chat_stream_with_usage.await_count == 2
    assert result.outputs["artifacts"] == []
    assert result.outputs["emission_failure"]["reason"] == EMISSION_FAILURE_ANCHORED_EDIT_REFUSED
    assert "repair_typed_checks" not in result.outputs


async def test_a_whole_file_repair_reads_exactly_as_before():
    """§46a: before the flip a whole-file response is accepted. Bug caught: the anchored reading
    changing a response that carries no edit fence."""
    whole = "```python:backend/routes.py\nrouter = 1\n```\n"
    ctx = _context(whole)

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    assert [a["name"] for a in result.outputs["artifacts"]] == ["backend/routes.py"]
    assert result.outputs["artifacts"][0]["content"] == "router = 1"
    assert "anchored_edits" not in result.outputs


async def test_a_repair_with_no_existing_named_file_is_not_offered_the_edit_form():
    ctx = _context("```python:backend/new_helper.py\nX = 1\n```\n")

    await DevelopmentCorrectionRepairHandler().handle(
        ctx, _inputs(expected_artifacts=["backend/new_helper.py"])
    )

    assert "Editing a File That Already Exists" not in _user_prompt(ctx, 0)


async def test_the_edit_resolves_against_the_failed_attempts_file_over_the_workspace():
    """#1264's overlay, on the anchored path. Bug caught: the edit resolved against the stale
    workspace copy when the failed attempt had already changed the file — the anchor the model
    copied from the failing file would be reported missing, or apply to text the verifier
    never sees."""
    from squadops.capabilities.handlers.impl.repair_handlers import REPAIR_FAILED_ARTIFACTS_KEY

    failed_routes = _ROUTES.replace("def list_runs():\n", "def list_all_runs():\n")
    edit = (
        "```edit:backend/routes.py\n<<<<<<< SEARCH\ndef list_all_runs():\n=======\n"
        "def list_runs():\n>>>>>>> REPLACE\n```\n"
    )
    ctx = _context(edit)

    result = await DevelopmentCorrectionRepairHandler().handle(
        ctx,
        _inputs(
            **{
                REPAIR_FAILED_ARTIFACTS_KEY: [
                    {"name": "backend/routes.py", "content": failed_routes}
                ]
            }
        ),
    )

    (artifact,) = result.outputs["artifacts"]
    assert artifact["content"] == _ROUTES


async def test_an_edit_to_a_file_the_repair_was_not_named_for_is_refused():
    """The grant is the named files that exist. Bug caught: any workspace file anchorable — a
    repair of routes.py quietly editing the frozen main.py by anchor."""
    edit = (
        "```edit:backend/main.py\n<<<<<<< SEARCH\napp = 1\n=======\napp = 2\n>>>>>>> REPLACE\n```\n"
    )
    ctx = _context(edit, edit)

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    assert result.outputs["artifacts"] == []
    assert any(
        line.startswith("`backend/main.py`: out_of_grant")
        for line in result.outputs["emission_failure"]["refusals"]
    )


async def test_a_structural_repair_targets_an_entity_the_prompt_listed():
    """SIP-0107 step 5, entered at the handler. Bug caught: the entity listing and the
    transaction's resolver disagreeing — a selector shown to the model that the edit cannot
    find — or a body replacement disturbing the decorator and signature around it."""
    routes = (
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "\n"
        '@router.post("/runs", status_code=201)\n'
        "def post_runs(payload):\n"
        '    raise NotImplementedError("scaffold")\n'
    )
    body = "    return {'id': 'r1', **payload}\n"
    ctx = _context(
        f"```edit:backend/routes.py\n<<<<<<< REPLACE function:post_runs#body\n{body}>>>>>>> END\n```\n"
    )

    result = await DevelopmentCorrectionRepairHandler().handle(
        ctx, _inputs(acceptance_workspace_files={"backend/routes.py": routes})
    )

    prompt = _user_prompt(ctx, 0)
    assert (
        "- `backend/routes.py` — entities: `imports`, `import:fastapi`, `function:post_runs`, `function:post_runs#body`"
        in prompt
    )
    (artifact,) = result.outputs["artifacts"]
    assert artifact["content"] == routes.replace(
        '    raise NotImplementedError("scaffold")\n', body
    )


async def test_an_entity_that_does_not_exist_is_retried_with_its_reason():
    ctx = _context(
        "```edit:backend/routes.py\n<<<<<<< REPLACE function:delete_run#body\n    return 1\n>>>>>>> END\n```\n",
        _GOOD_EDIT,
    )

    result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    retry_prompt = _user_prompt(ctx, 1)
    assert (
        "`backend/routes.py`: unresolved_entity — function:delete_run#body is not in backend/routes.py"
        in retry_prompt
    )
    assert result.outputs["anchored_edits"]["accepted"] is True
