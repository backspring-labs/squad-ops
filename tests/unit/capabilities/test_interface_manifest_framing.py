"""Interface-manifest-in-framing deterministic core (SIP-0099 phase 99.2).

Covers the two seams that carry a framing-authored interface manifest without a live
LLM: the proposer-output extraction helper (``extract_interface_manifest_yaml``) and
the executor's plan-gate validation net (``_reject_invalid_plan_before_workload_gate``
+ ``_validate_interface_manifest``), which is the ONLY net that validates the manifest
and feeds the existing ``system:plan_validation`` REJECTED recording. Merger emission is
covered in ``test_merge_plan_handler.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.handlers._plan_authoring import extract_interface_manifest_yaml
from squadops.capabilities.handlers.planning_tasks import (
    DevelopmentProposePlanTasksHandler,
    QaProposePlanTasksHandler,
)
from squadops.capabilities.scaffold import InterfaceManifest, is_scaffoldable_stack

pytestmark = [pytest.mark.domain_capabilities]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"
_APPENDIX_PATH = (
    _REPO_ROOT
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
    / "request.development_interface_manifest_appendix.md"
)


def _clean_manifest_yaml() -> str:
    return _MANIFEST_PATH.read_text(encoding="utf-8")


def _malformed_manifest_yaml() -> str:
    raw = yaml.safe_load(_clean_manifest_yaml())
    raw["api"]["endpoints"] = []  # parses, but nothing to scaffold — a lint defect
    return yaml.safe_dump(raw)


# --------------------------------------------------------------------------- #
# extract_interface_manifest_yaml — capture the block from proposer output
# --------------------------------------------------------------------------- #


def test_extract_returns_the_interface_block_by_filename_regardless_of_order():
    # interface_manifest.yaml is emitted SECOND here, after the plan block; the helper
    # selects by filename, so ordering can't hide it (unlike first-yaml-block extraction)
    content = (
        "Plan first:\n"
        "```yaml:proposed_plan_tasks.yaml\nversion: 1\ntasks: []\n```\n"
        "Then the interface:\n"
        "```yaml:interface_manifest.yaml\nversion: 1\nkind: interface_manifest\n```\n"
    )
    extracted = extract_interface_manifest_yaml(content)
    assert extracted is not None
    assert "kind: interface_manifest" in extracted


def test_extract_returns_none_when_no_interface_block():
    # data-driven: no interface_manifest.yaml block => None => today's behavior downstream
    content = "```yaml:proposed_plan_tasks.yaml\nversion: 1\ntasks: []\n```\n"
    assert extract_interface_manifest_yaml(content) is None
    assert extract_interface_manifest_yaml("") is None


# --------------------------------------------------------------------------- #
# _validate_interface_manifest — parse + lint + prefix (the rejection payload)
# --------------------------------------------------------------------------- #


def test_validate_clean_manifest_yields_no_errors():
    assert DispatchedFlowExecutor._validate_interface_manifest(_clean_manifest_yaml()) == []


def test_validate_malformed_manifest_yields_prefixed_lint_errors():
    errors = DispatchedFlowExecutor._validate_interface_manifest(_malformed_manifest_yaml())
    assert errors
    assert all(e.startswith("interface_manifest:") for e in errors)
    assert any("endpoint" in e for e in errors)


def test_validate_unparseable_manifest_is_a_single_error():
    errors = DispatchedFlowExecutor._validate_interface_manifest("::: not valid yaml :::")
    assert len(errors) == 1
    assert "interface_manifest: unparseable" in errors[0]


# --------------------------------------------------------------------------- #
# net-b: _reject_invalid_plan_before_workload_gate surfaces interface errors
# --------------------------------------------------------------------------- #


def _executor_for(manifest_yaml: str | None) -> tuple[DispatchedFlowExecutor, Any, Any]:
    stored: dict[str, tuple[Any, bytes]] = {}
    refs: list[str] = []
    if manifest_yaml is not None:
        ref = MagicMock()
        ref.filename = "interface_manifest.yaml"
        ref.artifact_type = "interface_manifest"
        stored["ref-iface"] = (ref, manifest_yaml.encode("utf-8"))
        refs.append("ref-iface")

    vault = AsyncMock()

    async def _retrieve(ref_id: str):
        return stored[ref_id]

    vault.retrieve.side_effect = _retrieve

    executor = DispatchedFlowExecutor(artifact_vault=vault)
    run = MagicMock()
    run.artifact_refs = refs
    cycle = MagicMock()
    cycle.applied_defaults = {"implementation_plan": True}
    # a real Cycle always has a dict here; without it MagicMock's .get() returns a
    # truthy mock and the SIP-0098 98.3 bind-mode branch would misfire (author mode
    # is keyed on contract_ref being absent).
    cycle.execution_overrides = {}
    return executor, run, cycle


async def test_net_b_rejects_a_malformed_interface_manifest():
    executor, run, cycle = _executor_for(_malformed_manifest_yaml())
    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )
    # these errors are what the caller records as the system:plan_validation REJECTED note
    assert any(e.startswith("interface_manifest:") and "endpoint" in e for e in errors)


async def test_net_b_passes_a_clean_interface_manifest():
    executor, run, cycle = _executor_for(_clean_manifest_yaml())
    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )
    assert errors == []


async def test_net_b_no_manifest_is_todays_behavior():
    # absent interface manifest => no new rejection (byte-identical for plan-only cycles)
    executor, run, cycle = _executor_for(None)
    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, cycle, "progress_plan_review"
    )
    assert errors == []


# --------------------------------------------------------------------------- #
# Slice B: the conditional scaffold_section injection (dev-only, scaffoldable-only)
# --------------------------------------------------------------------------- #


async def test_scaffold_section_rendered_for_dev_on_scaffoldable_stack():
    handler = DevelopmentProposePlanTasksHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="INTERFACE MANIFEST INSTRUCTION")

    out = await handler._scaffold_section(
        renderer, {"resolved_config": {"build_profile": "fullstack_fastapi_react"}}
    )

    assert out == "INTERFACE MANIFEST INSTRUCTION"
    renderer.render.assert_awaited_once_with(
        "request.development_interface_manifest_appendix", {"stack": "fullstack_fastapi_react"}
    )


async def test_scaffold_section_empty_and_unrendered_for_non_scaffoldable_stack():
    handler = DevelopmentProposePlanTasksHandler()
    renderer = AsyncMock()
    out = await handler._scaffold_section(
        renderer, {"resolved_config": {"build_profile": "django_htmx"}}
    )
    assert out == ""
    renderer.render.assert_not_awaited()  # never told to author a manifest it can't scaffold


async def test_scaffold_section_empty_for_non_dev_proposer():
    # qa proposes tests, not the interface — only dev owns the interface section
    handler = QaProposePlanTasksHandler()
    renderer = AsyncMock()
    out = await handler._scaffold_section(
        renderer, {"resolved_config": {"build_profile": "fullstack_fastapi_react"}}
    )
    assert out == ""
    renderer.render.assert_not_awaited()


def test_appendix_example_manifest_is_itself_valid_and_scaffoldable():
    # the schema example we teach the LLM must itself parse, lint clean, and be
    # scaffoldable — otherwise a squad copying it faithfully still gets rejected
    example = extract_interface_manifest_yaml(_APPENDIX_PATH.read_text(encoding="utf-8"))
    assert example is not None
    manifest = InterfaceManifest.from_yaml(example)
    assert manifest.lint() == []
    assert is_scaffoldable_stack(manifest.stack)
