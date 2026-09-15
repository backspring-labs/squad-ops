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
    assert "How to Write an Edit Fence" in prompt
    assert "- `backend/routes.py`" in prompt
    assert (
        "`backend/new_helper.py`"
        not in prompt.split("How to Write an Edit Fence")[1].split("Rules")[0]
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

    assert "How to Write an Edit Fence" not in _user_prompt(ctx, 0)
    assert "Revise the Existing Files in Place" not in _user_prompt(ctx, 0)


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


# --- The revision form, as evidence (SIP-0107 §46a) -----------------------------------------


@pytest.mark.parametrize(
    ("responses", "extra", "expected"),
    [
        (
            ("```python:backend/routes.py\nrouter = 1\n```\n",),
            {},
            {
                "form": "whole_file",
                "whole_file_offered": ["backend/routes.py"],
                "accepted": None,
                "modes": [],
            },
        ),
        (
            (_GOOD_EDIT,),
            {},
            {
                "form": "edits",
                "edited": ["backend/routes.py"],
                "accepted": True,
                "refusals": 0,
                "modes": ["anchored"],
            },
        ),
        (
            (_AMBIGUOUS_EDIT, _AMBIGUOUS_EDIT),
            {},
            {
                "form": "edits",
                "edited": [],
                "accepted": False,
                "refusals": 1,
                "retried": True,
                "modes": ["anchored"],
                "failure_reason": "anchored_edit_refused",
            },
        ),
        (
            (
                "```edit:backend/routes.py\n<<<<<<< REPLACE function:create#body\n"
                "    return None\n>>>>>>> END\n```\n",
            ),
            {},
            {"form": "edits", "edited": ["backend/routes.py"], "modes": ["structural"]},
        ),
        (
            ("```python:backend/new_helper.py\nX = 1\n```\n",),
            {"expected_artifacts": ["backend/new_helper.py"]},
            {"form": "new_files_only", "offered": {}, "new_files": ["backend/new_helper.py"]},
        ),
    ],
    ids=[
        "offered file re-emitted whole",
        "anchored edit",
        "refused twice",
        "structural edit",
        "never offered",
    ],
)
async def test_every_repair_logs_the_form_it_was_offered_and_the_form_it_took(
    caplog, responses, extra, expected
):
    """Wiring, entered at the dev repair's ``handle``. Bug caught: a whole-file answer to a file
    the prompt offered for in-place revision leaving no trace, so the record cannot tell it from a
    repair never offered the form — deploy B's Next.js repair of `app/runs/[run_id]/page.tsx`,
    unreadable because the stored prompt is cut before the form and the transaction line is
    written only when a response carries edits."""
    import json
    import logging

    ctx = _context(*responses)
    with caplog.at_level(
        logging.INFO, logger="squadops.capabilities.handlers.impl.repair_handlers"
    ):
        result = await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs(**extra))

    (line,) = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("repair_revision_form ")
    ]
    logged = json.loads(line.removeprefix("repair_revision_form "))
    assert logged == {
        "handler": "development_correction_repair_handler",
        "task_type": "development.correction_repair",
        **result.outputs["revision_form"],
    }
    if extra.get("expected_artifacts") is None:
        # The offer names the file with the entities the prompt listed for it, from the same
        # base the edits resolve on: imports, import:fastapi, and two functions with a body each.
        assert logged["offered"] == {"backend/routes.py": 6}
    assert {k: logged[k] for k in expected} == expected


async def test_a_repair_offered_the_edit_form_is_never_also_told_to_emit_the_file_whole():
    """SIP-0107 §46a: a repair of an existing file requests a scoped revision. Bug caught (deploy
    B, `cyc_e62d74598211`): the edit form said edits were "preferred" while the output section
    and the prompt's last line required every named file whole in ` ```language:<path> ` fences,
    and the dev repair of a one-line fix came back as a whole file. The existing file is asked
    for as edits, the new file as a whole file, and the last instruction agrees."""
    ctx = _context(_GOOD_EDIT)

    await DevelopmentCorrectionRepairHandler().handle(ctx, _inputs())

    prompt = _user_prompt(ctx, 0)
    scoped = prompt.split("Revise the Existing Files in Place")[1].split(
        "How to Write an Edit Fence"
    )[0]
    assert "- `backend/routes.py`" in scoped.split("does not exist yet")[0]
    assert "- `backend/new_helper.py`" in scoped.split("does not exist yet")[1]
    assert "MUST produce the following file(s) by name" not in prompt
    assert "re-emitted byte-identical" not in prompt
    closing = prompt.rstrip().rsplit("\n\n", 1)[-1]
    assert closing.startswith("Emit the repair now.") and "never for an existing one" in closing


async def test_a_repair_not_offered_the_edit_form_is_asked_exactly_as_before():
    """Bug caught: the restructure changing what a whole-file repair is asked — the output
    section and closing line of v7, byte for byte, for a repair with no existing named file."""
    ctx = _context("```python:backend/new_helper.py\nX = 1\n```\n")

    await DevelopmentCorrectionRepairHandler().handle(
        ctx, _inputs(expected_artifacts=["backend/new_helper.py"])
    )

    prompt = _user_prompt(ctx, 0)
    assert "The repair MUST produce the following file(s) by name" in prompt
    assert "- `backend/new_helper.py`" in prompt.split("Required Output Artifacts")[1]
    assert prompt.rstrip().endswith(
        "for. Do not include explanatory prose between code blocks unless it is essential."
    )
