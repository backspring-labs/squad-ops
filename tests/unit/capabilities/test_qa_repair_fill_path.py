"""A qa repair can reach a fill — 1.6.5 D (#970, with #969's brief).

Under fill mode the shells are merge products. Before this the own-artifact repair emitted
whole files (0 fills, 1 path fence — #969's observation), the shell guard discarded them,
and the retest ran the unrepaired suite. Now the repair authors under the SAME fill-mode
brief as ``qa.test``, emits fill blocks, and the handler merges them into the task's
current shells through the same gate; the merged shell is emitted at the shell path so the
patch overlay supersedes the failed one by name.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import (
    QATestRepairHandler,
    _merge_repair_fills,
)
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.capabilities.verification_scaffold_fill import merge_fills, parse_fill_emission
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)
_JOIN = "__tests__/scaffold/vc-probe-api-runs-join.scaffold.test.ts"
_CREATE = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
_SLOTS = [
    "vc-probe-api-runs",
    "vc-probe-api-runs-rejects-blank",
    "vs-get-api-runs",
    "vs-get-api-runs-run-id",
    "vs-get-api-runs-run-id-not-found",
    "vc-probe-api-runs-join",
    "vc-probe-api-runs-join-duplicate",
    "vc-probe-api-runs-leave",
]


@pytest.fixture(scope="module")
def scaffold_input():
    """The scaffold as the repair receives it: pristine files + the task's CURRENT
    shells, which carry eight fills (the join one is the wrong one)."""
    emission = emit_verification_scaffold(manifest_for_stack("nextjs_ts"))
    files = [dict(f) for f in emission.files]
    primary = parse_fill_emission(
        "".join(f"```fill:slot-{s}\n    expect(body).toBeTruthy() // {s}\n```\n" for s in _SLOTS)
    )
    merged = merge_fills(files, emission.manifest, primary)
    return {
        "manifest": emission.manifest.to_dict(),
        "files": files,
        "store_tables": ["Run"],
        "current_files": [{"name": f.path, "content": f.content} for f in merged.files],
    }


def _art(name, content, type_="test"):
    return {"name": name, "content": content, "media_type": "x", "type": type_}


class TestMergeRepairFills:
    def test_one_slot_is_replaced_and_every_other_byte_is_kept(self, scaffold_input):
        artifacts = QATestRepairHandler()._build_artifacts_from_content(
            "```fill:slot-vc-probe-api-runs-join\n    expect(body.participants).toHaveLength(1)\n```\n"
        )
        out, evidence = _merge_repair_fills(scaffold_input, artifacts)

        assert [a["name"] for a in out] == [_JOIN]  # only the touched shell is emitted
        assert out[0]["type"] == "test"
        assert "expect(body.participants).toHaveLength(1)" in out[0]["content"]
        assert "// vc-probe-api-runs-join" not in out[0]["content"]
        assert evidence["applied"] == ["slot-vc-probe-api-runs-join"]
        assert evidence["counts"] == {"filled": 8}
        # the untouched shells would be reproduced byte for byte (round-trip property)
        current = {f["name"]: f["content"] for f in scaffold_input["current_files"]}
        assert (
            "// vc-probe-api-runs-leave"
            in current["__tests__/scaffold/vc-probe-api-runs-leave.scaffold.test.ts"]
        )

    def test_a_whole_shell_rewrite_is_dropped_and_recorded(self, scaffold_input):
        artifacts = [
            _art(_CREATE, "// REWRITTEN"),
            *QATestRepairHandler()._build_artifacts_from_content(
                "```fill:slot-vc-probe-api-runs\n    expect(1).toBe(1)\n```\n"
            ),
        ]
        out, evidence = _merge_repair_fills(scaffold_input, artifacts)
        assert evidence["dropped_shell_rewrites"] == [_CREATE]
        create = next(a for a in out if a["name"] == _CREATE)
        assert "REWRITTEN" not in create["content"]
        assert "expect(1).toBe(1)" in create["content"]

    def test_a_repair_fill_passes_the_same_gate_as_the_primary(self, scaffold_input):
        """#1087 on the repair path: a phantom-table fill is rejected with the real
        tables named, exactly as qa.test would reject it."""
        artifacts = QATestRepairHandler()._build_artifacts_from_content(
            "```fill:slot-vc-probe-api-runs\n    expect(all(TABLES.Participant)).toHaveLength(1)\n```\n"
        )
        out, evidence = _merge_repair_fills(scaffold_input, artifacts)
        assert evidence["counts"]["rejected"] == 1
        assert evidence["dispositions"][0]["disposition"] == "rejected"
        assert "`TABLES.Run`" in out[0]["content"]

    def test_no_fill_emitted_keeps_the_additive_files_and_says_so(self, scaffold_input):
        artifacts = [_art("__tests__/extra.test.ts", "// extra")]
        out, evidence = _merge_repair_fills(scaffold_input, artifacts)
        assert out == artifacts
        assert evidence["detail"] == "the repair emitted no fill block"

    def test_without_current_shells_nothing_is_merged_and_the_fills_do_not_leak(
        self, scaffold_input
    ):
        artifacts = QATestRepairHandler()._build_artifacts_from_content(
            "```fill:slot-vc-probe-api-runs\n    expect(1).toBe(1)\n```\n"
        )
        out, evidence = _merge_repair_fills(
            {k: v for k, v in scaffold_input.items() if k != "current_files"}, artifacts
        )
        assert out == []
        assert "no current shells" in evidence["detail"]


class TestArtifactTyping:
    def test_fill_blocks_become_fill_artifacts_and_files_stay_files(self):
        arts = QATestRepairHandler()._build_artifacts_from_content(
            "```fill:slot-a\n    x()\n```\n```fill:slot-b\nnot_applicable: covered\n```\n"
            "```typescript:__tests__/extra.test.ts\n// extra\n```\n"
        )
        assert [(a["name"], a["type"]) for a in arts[:2]] == [
            ("slot-a", "fill"),
            ("slot-b", "fill"),
        ]
        assert arts[2]["name"] == "__tests__/extra.test.ts" and arts[2]["type"] != "fill"
        assert arts[1]["content"] == "not_applicable: covered"

    def test_no_fences_at_all_still_falls_back_to_the_document(self):
        arts = QATestRepairHandler()._build_artifacts_from_content("just prose")
        assert [a["name"] for a in arts] == ["repair_output.md"]


async def test_handle_authors_under_the_qa_brief_and_merges_into_the_current_shell(
    scaffold_input,
):
    handler = QATestRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(
        content="PROMPT", template_version="5", render_hash="h"
    )
    context = MagicMock()
    context.ports.request_renderer = renderer
    context.ports.llm.default_model = "m"
    context.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=MagicMock(
            content="```fill:slot-vc-probe-api-runs-join\n    expect(body.participants).toHaveLength(1)\n```\n"
        )
    )
    assembled = MagicMock()
    assembled.content = "system"
    context.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    context.correlation_context = None

    result = await handler.handle(
        context,
        {
            "prd": "group_run",
            "failed_task_type": "qa.test",
            "expected_artifacts": [_JOIN],
            "verification_scaffold": scaffold_input,
            "repair_slots": [
                {
                    "file": _JOIN,
                    "slot_id": "slot-vc-probe-api-runs-join",
                    "detail": "expected [] to have a length of 1",
                }
            ],
        },
    )

    rendered = [c.args[0] for c in renderer.render.await_args_list]
    assert rendered[:2] == [
        "request.qa_test_fill_mode_appendix",
        "request.qa_test_repair_fill_appendix",
    ]
    assert rendered[-1] == "request.cycle_repair_task"
    variables = renderer.render.await_args_list[1].args[1]
    assert "slot-vc-probe-api-runs-join" in variables["failed_slot_lines"]
    assert "expected [] to have a length of 1" in variables["failed_slot_lines"]
    main_vars = renderer.render.await_args_list[-1].args[1]
    assert main_vars["qa_fill_mode_section"] == "PROMPT\n\nPROMPT"

    names = [a["name"] for a in result.outputs["artifacts"]]
    assert names == [_JOIN]
    assert "expect(body.participants).toHaveLength(1)" in result.outputs["artifacts"][0]["content"]
    assert result.outputs["fill_merge"]["applied"] == ["slot-vc-probe-api-runs-join"]


async def test_the_repair_addendum_renders_from_the_real_asset():
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.capabilities.handlers.cycle.fill_mode_brief import render_repair_fill_section
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=_TEMPLATES.parent / "fragments", templates_path=_TEMPLATES
        )
    )
    out = await render_repair_fill_section(
        renderer, [{"file": _JOIN, "slot_id": "slot-vc-probe-api-runs-join", "detail": "why"}]
    )
    assert "`slot-vc-probe-api-runs-join` in `" + _JOIN + "` — why" in out
    assert "fill block is the only way to change a slot" in out
    assert await render_repair_fill_section(renderer, []) == ""


# --- #1583: a free-authored suite beside the shells is edited in place, never re-emitted -----

_SUITE = "__tests__/runs-ui.test.ts"
_SUITE_TEXT = (
    "import { describe, it, expect } from 'vitest'\n"
    "\n"
    "describe('RunDetailView data contract', () => {\n"
    "  it('returns a Run', async () => {\n"
    "    const body = { participants: [] }\n"
    "    expect(typeof body.participants_count).toBe('number')\n"
    "  })\n"
    "})\n"
)


def _real_context(*responses):
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.prompts.renderer import RequestTemplateRenderer

    llm = AsyncMock()
    llm.chat_stream_with_usage.side_effect = [
        MagicMock(content=r, prompt_tokens=10, completion_tokens=10, reasoning_tokens=None)
        for r in responses
    ]
    llm.default_model = "m"
    context = MagicMock()
    context.ports.llm = llm
    context.ports.prompt_service.get_system_prompt = MagicMock(
        return_value=MagicMock(content="system", assembly_hash="h")
    )
    context.ports.llm_observability = None
    context.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=_TEMPLATES.parent / "fragments", templates_path=_TEMPLATES
        )
    )
    context.correlation_context = None
    return context


def _fill_mode_inputs(scaffold_input):
    return {
        "prd": "group_run",
        "failed_task_type": "qa.test",
        "expected_artifacts": [_JOIN, _SUITE],
        "verification_scaffold": scaffold_input,
        "repair_slots": [
            {"file": _JOIN, "slot_id": "slot-vc-probe-api-runs-join", "detail": "expected 1"}
        ],
        "acceptance_workspace_files": {_SUITE: _SUITE_TEXT, "lib/store.ts": "export {}\n"},
        "resolved_config": {"development_profile": "nextjs_ts"},
    }


async def test_a_free_authored_suite_beside_the_shells_is_offered_the_edit_form_and_edited(
    scaffold_input,
):
    """#1583 (deploy D, `cyc_95c0e2dbb25c`): the shells' fill rule was applied to every file, so
    the qa repair had no scoped path to the one assertion in its free-authored suite, re-emitted
    the whole suite (11,245 → 7,564 chars), and — with nothing offered — that read as a new file.
    Bug caught: the suite not offered, not shown, or a shell listed as a file to emit whole."""
    response = (
        "```fill:slot-vc-probe-api-runs-join\n    expect(body.participants).toHaveLength(1)\n```\n"
        f"```edit:{_SUITE}\n<<<<<<< SEARCH\n"
        "    expect(typeof body.participants_count).toBe('number')\n=======\n"
        "    expect(Array.isArray(body.participants)).toBe(true)\n>>>>>>> REPLACE\n```\n"
    )
    ctx = _real_context(response)
    handler = QATestRepairHandler()
    inputs = _fill_mode_inputs(scaffold_input)

    assert handler._anchorable_files(inputs) == [_SUITE]  # the shell is filled, never anchored
    result = await handler.handle(ctx, inputs)

    prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][-1].content
    shown = prompt.split("The Files as They Are Now")[1].split("How to Write an Edit Fence")[0]
    assert f"`{_SUITE}`:\n```\n{_SUITE_TEXT}```" in shown
    assert _JOIN not in shown
    output_form = prompt.split("Revise the Existing Files in Place")[1].split(
        "The Files as They Are Now"
    )[0]
    assert f"- `{_SUITE}`" in output_form.split("does not exist yet")[0]
    assert _JOIN not in output_form  # a shell is not "a file that does not exist yet"
    assert "slot-vc-probe-api-runs-join" in prompt  # the fill brief still names the slot

    by_name = {a["name"]: a["content"] for a in result.outputs["artifacts"]}
    assert set(by_name) == {_JOIN, _SUITE}
    assert "expect(body.participants).toHaveLength(1)" in by_name[_JOIN]
    assert by_name[_SUITE] == _SUITE_TEXT.replace(
        "expect(typeof body.participants_count).toBe('number')",
        "expect(Array.isArray(body.participants)).toBe(true)",
    )
    form = result.outputs["revision_form"]
    assert (form["form"], form["edited"], form["fills"], form["whole_file_unoffered"]) == (
        "edits",
        [_SUITE],
        1,
        [],
    )


async def test_a_pure_fill_repair_still_offers_nothing_and_reads_as_fill(scaffold_input):
    """Control: with no free-authored file named, fill mode is exactly what it was — no edit
    form, no shown files, the fill brief alone."""
    ctx = _real_context(
        "```fill:slot-vc-probe-api-runs-join\n    expect(body.participants).toHaveLength(1)\n```\n"
    )
    inputs = {**_fill_mode_inputs(scaffold_input), "expected_artifacts": [_JOIN]}

    result = await QATestRepairHandler().handle(ctx, inputs)

    prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][-1].content
    assert "The Files as They Are Now" not in prompt
    assert "How to Write an Edit Fence" not in prompt
    assert result.outputs["revision_form"]["form"] == "fill"
    assert [a["name"] for a in result.outputs["artifacts"]] == [_JOIN]
