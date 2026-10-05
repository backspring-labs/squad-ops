"""#1884's proposal outlet: the block's contract, and where its entries go and never go.

Entered at each real reader: ``QATestHandler.handle()`` (the only author given the outlet),
``QATestRepairHandler.handle()`` (which is not), ``failed_task_artifacts`` (what a repair and the
verifier overlay), ``ProgressDriver._propose_launch`` (the next proposal's launch) and
``StrategyProposeIncrementHandler.handle()``. The correction runner's retest filter is held in
``test_correction_runner.py`` (``test_retest_inputs_carry_suite_and_original_workspace``).
"""

from __future__ import annotations

import pytest

from squadops.campaigns.proposed_behaviours import (
    QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE,
    ProposedBehavioursError,
    merged_entries,
    parse_proposed_behaviours,
    stored_form,
)

_ENTRY = {
    "behaviour": "Two runs with the same date keep the order they were created in",
    "why": "The list reorders between refreshes when dates tie",
    "surface_kind": "endpoint",
    "surface": "GET /runs",
}


def _block(entries=None, **doc) -> str:
    import yaml

    return yaml.safe_dump(doc or {"proposed_behaviours": entries or [_ENTRY]})


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("proposed_behaviours: [", "not valid YAML"),
        (_block(extra=1, proposed_behaviours=[_ENTRY]), "one top-level key"),
        (_block(proposed_behaviours=[]), "1 to 10 entries"),
        (_block([_ENTRY] * 11), "1 to 10 entries"),
        (_block([{**_ENTRY, "note": "x"}]), "exactly the fields"),
        (_block([{k: v for k, v in _ENTRY.items() if k != "why"}]), "exactly the fields"),
        (_block([{**_ENTRY, "behaviour": "  "}]), "leaves behaviour blank"),
        (_block([{**_ENTRY, "surface_kind": "page"}]), "surface_kind is one of"),
    ],
)
def test_a_malformed_block_is_refused_with_its_reason(text, why):
    """Bugs caught: a block two implementations would read differently accepted, or refused
    with no reason the author can act on inside its attempt budget."""
    with pytest.raises(ProposedBehavioursError, match=why):
        parse_proposed_behaviours(text)


def test_entries_merge_oldest_first_without_repeats_and_at_most_ten():
    first = stored_form(parse_proposed_behaviours(_block([_ENTRY])))
    others = [{**_ENTRY, "behaviour": f"b{i}"} for i in range(12)]
    later = stored_form(parse_proposed_behaviours(_block([_ENTRY, *others[:9]])))
    more = stored_form(parse_proposed_behaviours(_block(others[9:])))

    merged = merged_entries([first, later, more])

    assert [e["behaviour"] for e in merged] == [_ENTRY["behaviour"]] + [f"b{i}" for i in range(9)]


def test_a_failed_tasks_proposal_never_reaches_the_tree_its_repair_overlays():
    """#1884, a third reader the plan's seam table did not list: ``failed_task_artifacts``
    forwards every file a failed task emitted to its repair and the verifier's overlay."""
    from squadops.capabilities.context_assembly import failed_task_artifacts

    outputs = {
        "artifacts": [
            {"name": "tests/test_runs.py", "content": "def test_x(): pass", "type": "test"},
            {
                "name": "proposed_behaviours.yaml",
                "content": _block(),
                "type": QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE,
            },
        ]
    }

    assert [a["name"] for a in failed_task_artifacts(outputs)] == ["tests/test_runs.py"]


# --------------------------------------------------------------------------- #
# Through the real handlers
# --------------------------------------------------------------------------- #

_SUITE = (
    "```python:backend/tests/criteria/test_C1.py\n"
    "def test_c1(client):\n"
    "    assert client.post('/runs', json={'capacity': 2}).json()['capacity'] == 2\n"
    "```\n"
)
_MALFORMED = _block([{**_ENTRY, "surface_kind": "page"}])


def _emission(block: str | None) -> str:
    return _SUITE + (f"\n```yaml:proposed_behaviours.yaml\n{block}```\n" if block else "")


async def _qa_run(monkeypatch, *replies: str):
    """``QATestHandler.handle()`` on the ``qa.test`` envelope ``generate_task_plan`` builds for an
    increment from the ``campaign-increment`` profile's defaults (output validation on, three
    self-evaluation passes): the model answers ``replies`` in turn."""
    from unittest.mock import AsyncMock

    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
    from squadops.capabilities.handlers.test_runner import RunTestsResult
    from squadops.llm.models import ChatMessage
    from tests.unit.campaigns.test_increment_test_scope import (
        STORED,
        _implementation,
        _increment_cycle,
        _qa_context,
    )

    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    [qa] = [e for e in _implementation(_increment_cycle(), STORED) if e.task_type == "qa.test"]
    sent: list = []
    ctx = _qa_context(sent)
    answers = iter(replies)

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=next(answers), completion_tokens=40)

    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    result = await QATestHandler().handle(
        ctx, {**qa.inputs, "prd": "Runs API", "artifact_contents": {}}
    )
    return result, [m[-1].content for m in sent]


def _outlet(result) -> list[dict]:
    return [
        a
        for a in result.outputs.get("artifacts", [])
        if a["name"].endswith("proposed_behaviours.yaml")
    ]


async def test_a_valid_block_is_stored_once_as_a_proposal_never_as_a_test(monkeypatch):
    """Bugs caught: the block typed as a test (run by the suite, overlaid on the tree), or stored
    twice; and the author never told the outlet exists."""
    result, prompts = await _qa_run(monkeypatch, _emission(_block()))

    [stored] = _outlet(result)
    assert stored["type"] == QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE
    assert parse_proposed_behaviours(stored["content"])[0].behaviour == _ENTRY["behaviour"]
    assert "## Behaviour you would test but nothing accepted requires: propose it" in prompts[0]
    assert result.evidence.metadata["proposed_behaviours"] == 1


async def test_a_malformed_block_is_returned_on_a_pass_and_the_correction_stored(monkeypatch):
    """Bug caught: a malformed block dropped silently, where the self-evaluation budget could
    have had it corrected."""
    result, prompts = await _qa_run(monkeypatch, _emission(_MALFORMED), _emission(_block()))

    assert len(prompts) == 2
    assert "entry 1's surface_kind is one of endpoint, client_route" in prompts[1]
    [stored] = _outlet(result)
    assert parse_proposed_behaviours(stored["content"])[0].surface_kind == "endpoint"


async def test_a_block_malformed_on_every_pass_is_dropped_and_never_decides_the_task(
    monkeypatch,
):
    """Bug caught: an optional proposal failing the task that wrote it. The verdict with a block
    malformed to the end equals the same emission's verdict with no block at all."""
    dropped, _ = await _qa_run(monkeypatch, *[_emission(_MALFORMED)] * 4)
    clean, _ = await _qa_run(monkeypatch, _emission(None))

    assert _outlet(dropped) == []
    assert "surface_kind is one of" in dropped.evidence.metadata["proposed_behaviours_dropped"]
    assert dropped.success == clean.success is True


async def test_a_qa_repair_is_not_given_the_outlet_and_its_block_reaches_no_tree():
    """The repair re-authors a broken suite; proposing belongs to the authoring task. Bug caught:
    a repair's block overlaid on the verifier's tree as a file."""
    from unittest.mock import AsyncMock, MagicMock

    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.capabilities.handlers.impl.repair_handlers import QATestRepairHandler
    from squadops.prompts.renderer import RequestTemplateRenderer
    from tests.unit.campaigns.test_increment_test_scope import _PROMPTS

    ctx = MagicMock()
    ctx.role_id = "qa"
    ctx.task_id = "repair-run_i-00-qa.test_repair"
    ctx.correlation_context = None
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=MagicMock(
            content=_emission(_block()), prompt_tokens=1, completion_tokens=1, reasoning_tokens=None
        )
    )
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    scope = {"criteria": [], "frozen": [{"criterion_id": "T1", "statement": "by date"}]}

    result = await QATestRepairHandler().handle(
        ctx,
        {
            "prd": "Runs",
            "failed_task_type": "qa.test",
            "expected_artifacts": ["backend/tests/criteria/test_C1.py"],
            "increment_test_scope": scope,
        },
    )

    prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][-1].content
    assert "propose it" not in prompt  # the outlet's appendix is the suite author's alone
    assert _outlet(result) == []
    assert result.outputs["proposed_behaviours_ignored"] == ["proposed_behaviours.yaml"]
