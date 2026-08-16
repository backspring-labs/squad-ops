"""Fill mode reaches the qa author and its output merges — SIP-0104 P3 transport.

Mirrors ``test_frozen_surface_proposer``'s end-to-end shape: the executor-side injection
that puts the scaffold on the qa.test envelope, the handler section that renders it, a
real render of the managed asset, and the handle-level proof that a fills-only emission
is a successful authorship — not a zero-extraction emission failure (#566's class would
otherwise eat every correct fill-mode output).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.capabilities.verification_scaffold_fill import parse_fill_emission
from squadops.cycles.task_plan import inject_contract_inputs
from squadops.cycles.verification_contract import VerificationContract
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)


@pytest.fixture(scope="module")
def nextjs_manifest():
    return manifest_for_stack("nextjs_ts")


@pytest.fixture(scope="module")
def emission(nextjs_manifest):
    return emit_verification_scaffold(nextjs_manifest)


@pytest.fixture(scope="module")
def scaffold_input(emission):
    return {
        "manifest": emission.manifest.to_dict(),
        "files": [dict(f) for f in emission.files],
    }


def _contract_for(manifest) -> VerificationContract:
    return VerificationContract.from_dict(emit_contract_dict(manifest))


# --- executor-side injection --------------------------------------------------- #


class TestInjection:
    def test_qa_test_receives_the_scaffold_on_an_opted_in_stack(self, nextjs_manifest):
        inputs: dict = {}
        inject_contract_inputs(inputs, _contract_for(nextjs_manifest), "qa.test", nextjs_manifest)
        scaffold = inputs["verification_scaffold"]
        assert len(scaffold["files"]) == 8
        assert scaffold["manifest"]["stack"] == "nextjs_ts"
        assert scaffold["manifest"]["generator_version"] == 2

    def test_an_unopted_stack_injects_nothing(self):
        manifest = manifest_for_stack("fullstack_fastapi_react")
        inputs: dict = {}
        inject_contract_inputs(inputs, _contract_for(manifest), "qa.test", manifest)
        assert "verification_scaffold" not in inputs

    def test_non_qa_tasks_do_not_carry_it(self, nextjs_manifest):
        inputs: dict = {}
        inject_contract_inputs(
            inputs, _contract_for(nextjs_manifest), "development.develop", nextjs_manifest
        )
        assert "verification_scaffold" not in inputs

    def test_a_manifest_less_call_injects_nothing(self, nextjs_manifest):
        inputs: dict = {}
        inject_contract_inputs(inputs, _contract_for(nextjs_manifest), "qa.test", None)
        assert "verification_scaffold" not in inputs


# --- handler section ------------------------------------------------------------ #


class TestFillModeSection:
    async def test_renders_slots_and_shells_through_the_asset(self, scaffold_input):
        context = MagicMock()
        renderer = AsyncMock()
        renderer.render.return_value = MagicMock(content="FILL MODE SECTION")
        context.ports.request_renderer = renderer

        out = await QATestHandler()._fill_mode_section(
            context, {"verification_scaffold": scaffold_input}
        )

        assert out == "FILL MODE SECTION"
        variables = renderer.render.await_args.args[1]
        assert "slot-vc-probe-api-runs — POST /api/runs -> 201" in variables["slot_lines"]
        assert "(mirrors probe vc-probe-api-runs)" in variables["slot_lines"]
        assert "vc-probe-api-runs.scaffold.test.ts" in variables["shell_files"]

    async def test_absent_scaffold_renders_nothing(self):
        context = MagicMock()
        context.ports.request_renderer = AsyncMock()
        out = await QATestHandler()._fill_mode_section(context, {})
        assert out == ""
        context.ports.request_renderer.render.assert_not_awaited()


async def test_real_asset_renders_slots_and_rules(scaffold_input):
    """A live render: the slot inventory and the fill grammar must survive the template."""
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=_TEMPLATES.parent / "fragments", templates_path=_TEMPLATES
        )
    )
    context = MagicMock()
    context.ports.request_renderer = renderer
    out = await QATestHandler()._fill_mode_section(
        context, {"verification_scaffold": scaffold_input}
    )
    assert "FILL MODE" in out
    assert "slot-vc-probe-api-runs" in out
    assert "not_applicable" in out
    assert "beforeEach(() => reset())" in out  # the shells themselves are visible


# --- merge into artifacts -------------------------------------------------------- #


class TestMergeFillArtifacts:
    def test_merged_shells_join_artifacts_and_shell_rewrites_are_dropped(self, scaffold_input):
        fills = parse_fill_emission(
            "```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
        )
        artifacts = [
            # an additive file — kept
            {
                "name": "__tests__/extra.test.ts",
                "content": "// extra",
                "media_type": "x",
                "type": "test",
            },
            # an attempted wholesale shell rewrite — dropped and recorded
            {
                "name": "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts",
                "content": "// REWRITTEN",
                "media_type": "x",
                "type": "test",
            },
        ]
        merged_artifacts, suite_files, evidence = QATestHandler()._merge_fill_artifacts(
            scaffold_input, fills, artifacts
        )
        names = [a["name"] for a in merged_artifacts]
        assert "__tests__/extra.test.ts" in names
        create_shell = next(
            a for a in merged_artifacts if a["name"].endswith("vc-probe-api-runs.scaffold.test.ts")
        )
        assert "expect(body.id).toBeTruthy()" in create_shell["content"]
        assert "REWRITTEN" not in create_shell["content"]
        assert evidence["dropped_shell_rewrites"] == [
            "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
        ]
        assert evidence["counts"]["filled"] == 1
        assert evidence["counts"]["missing"] == 7
        assert len(suite_files) == 8


# --- handle(): a fills-only emission is authorship, not emission failure --------- #


async def test_a_fills_only_emission_is_not_a_zero_extraction_failure(scaffold_input):
    fill_text = (
        "Fills below.\n\n```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
    )
    context = MagicMock()
    chat = AsyncMock(return_value=MagicMock(content=fill_text))
    context.ports.llm.chat_stream_with_usage = chat
    context.ports.llm.default_model = "m"
    assembled = MagicMock()
    assembled.content = "system"
    context.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    context.ports.request_renderer = None

    result = await QATestHandler().handle(
        context,
        {
            "prd": "group_run",
            "artifact_contents": {},
            "resolved_config": {"dev_capability": "nextjs_ts"},
            "subtask_focus": "fill the scaffold",
            "expected_artifacts": [],
            "verification_scaffold": scaffold_input,
        },
    )

    artifact_names = [a["name"] for a in result.outputs["artifacts"]]
    assert "emission_failure" not in result.outputs
    merged_shells = [n for n in artifact_names if n.startswith("__tests__/scaffold/")]
    assert len(merged_shells) == 8
    create_shell = next(
        a
        for a in result.outputs["artifacts"]
        if a["name"].endswith("vc-probe-api-runs.scaffold.test.ts")
    )
    assert "expect(body.id).toBeTruthy()" in create_shell["content"]


async def test_the_evidence_pipeline_lands_in_outputs(scaffold_input, monkeypatch):
    """P5 wiring: a spine failure among the runner's observation rows classifies as
    app_contract and lands in BOTH outputs['scaffold_evidence'] (the banked summary)
    and the validation_result classification row the locus classifier consults."""
    from squadops.capabilities.handlers.cycle import qa_test as qa_test_module
    from squadops.capabilities.handlers.test_runner import RunTestsResult

    fill_text = "```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
    shell_path = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"

    async def _canned_suite(capability, sources, extracted):
        merged_content = next(f["content"] for f in extracted if f["filename"] == shell_path)
        status_line = next(
            i
            for i, line in enumerate(merged_content.split("\n"), start=1)
            if "expect(res.status).toBe(201)" in line
        )
        result = RunTestsResult(
            executed=True,
            exit_code=1,
            runner="vitest",
            suite_broken=False,
            test_failures=(
                {
                    "file": shell_path,
                    "title": "POST /api/runs -> 201 [vc-probe-api-runs]",
                    "messages": ["expected 500 to be 201 // Object.is equality"],
                    "line": status_line,
                    "suite_level": False,
                },
            ),
        )
        return result, {
            "name": "test_report.md",
            "content": "r",
            "media_type": "text/markdown",
            "type": "document",
        }

    monkeypatch.setattr(
        qa_test_module.QATestHandler, "_run_test_suite", staticmethod(_canned_suite)
    )

    context = MagicMock()
    context.ports.llm.chat_stream_with_usage = AsyncMock(return_value=MagicMock(content=fill_text))
    context.ports.llm.default_model = "m"
    assembled = MagicMock()
    assembled.content = "system"
    context.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    context.ports.request_renderer = None

    result = await QATestHandler().handle(
        context,
        {
            "prd": "group_run",
            "artifact_contents": {},
            "resolved_config": {"dev_capability": "nextjs_ts"},
            "subtask_focus": "fill the scaffold",
            "expected_artifacts": [],
            "verification_scaffold": scaffold_input,
        },
    )

    evidence = result.outputs["scaffold_evidence"]
    assert evidence["failure_classes"] == {"app_contract": 1}
    assert evidence["observations"][0]["criterion_id"] == "vc-probe-api-runs"
    assert evidence["observations"][0]["owner"] == "dev"
    assert evidence["fill_dispositions"] == {"filled": 1, "missing": 7}
    # The summary is diagnostic, NOT a verification check: it must not appear among
    # validation_result.checks, or normalize_task_checks records it and the cycle
    # outcome reports it as an unverified check (roll 1, cyc_04d36309d793).
    rows = (result.outputs.get("validation_result") or {}).get("checks") or []
    assert not any("scaffold" in str(r.get("check", "")) for r in rows)

    # ...and it reaches the correction loop on the failure-evidence transport instead.
    from squadops.cycles.failure_evidence import FailureLocus, classify_failure_locus

    evidence = {"scaffold_evidence": evidence, "validation_result": {"checks": rows}}
    assert classify_failure_locus(evidence) == FailureLocus.SUBJECT
