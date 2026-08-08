"""The framing-emitted manifest's two runtime seams: the gate that rejects it, and the
forwarding that carries it (#791, M1 — was SIP-0099 99.2/99.3).

Both seams are executor-side and neither needs an LLM. The authoring stage itself is
covered in ``test_manifest_authoring_stage.py``; the gates as pure predicates in
``tests/unit/cycles/test_manifest_gates.py``.

Bug classes guarded:

- **the taught schema failing the gates** — the authoring asset shows the author a worked
  instance, so a schema example that would itself be rejected manufactures authoring
  defects the prompt caused (#629's pattern: the system holds the answer and never shows it);
- a manifest rejected at the gate with no proof class in the note, leaving an operator to
  guess which subsystem to look at;
- **a promoted manifest that never reaches the implementation run** — the forwarding filter
  dropped ``interface_manifest`` for as long as 99.2 existed, so an authored manifest was
  stored, validated, promoted, and then silently not carried, and the implementation ran
  unscaffolded while framing believed it had designed a skeleton. Invisible because every
  cycle since ran bind mode, where the manifest rides ``plan_artifact_refs`` from creation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.capabilities.scaffold import InterfaceManifest, is_scaffoldable_stack
from squadops.cycles.manifest_authoring import MANIFEST_ARTIFACT_TYPE
from squadops.cycles.manifest_gates import assess_schema, assess_winnability

pytestmark = [pytest.mark.domain_capabilities]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"
_AUTHORING_ASSET = (
    _REPO_ROOT
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
    / "request.development_author_manifest.md"
)


def _clean_manifest_yaml() -> str:
    return _MANIFEST_PATH.read_text(encoding="utf-8")


def _malformed_manifest_yaml() -> str:
    raw = yaml.safe_load(_clean_manifest_yaml())
    raw["api"]["endpoints"] = []  # parses, but nothing to scaffold — a lint defect
    return yaml.safe_dump(raw)


# --------------------------------------------------------------------------- #
# The schema the author is taught must survive the gates it will be judged by
# --------------------------------------------------------------------------- #


def _taught_example() -> str:
    """The worked manifest in the authoring asset, with the stack variable resolved as the
    renderer would resolve it."""
    blocks = extract_fenced_files(_AUTHORING_ASSET.read_text(encoding="utf-8"))
    example = next(f["content"] for f in blocks if f["filename"] == "interface_manifest.yaml")
    return example.replace("{{stack}}", "fullstack_fastapi_react")


def test_the_taught_schema_example_passes_both_gates():
    """The load-bearing guard on the authoring asset. A squad that copies the worked
    example faithfully must not be rejected for doing so — and an example predating the
    gates is exactly how that happens (the pre-M1 asset showed no ``source_prd``, no
    ``decisions``, no ``success_status`` and no ``testids``, all four of which the gates
    now require, so every authored manifest would have been rejected for obeying it)."""
    example = _taught_example()

    assert assess_schema(example) == ()
    assert assess_winnability(example) == ()


def test_the_taught_schema_example_is_scaffoldable_as_written():
    """Separate from the gates: an example the expander cannot place teaches a shape that
    dies later, and the gates alone would not catch a stack the asset names wrongly."""
    manifest = InterfaceManifest.from_yaml(_taught_example())

    assert manifest.lint() == []
    assert is_scaffoldable_stack(manifest.stack)


# --------------------------------------------------------------------------- #
# _validate_interface_manifest — the gate's rejection payload
# --------------------------------------------------------------------------- #


def test_validate_clean_manifest_yields_no_errors():
    assert DispatchedFlowExecutor._validate_interface_manifest(_clean_manifest_yaml()) == []


def test_validate_rejection_names_the_proof_class_not_just_the_symptom():
    """The operator reading a REJECTED note needs to know which subsystem to look at.
    Bare prose sends them to read the manifest; the proof class sends them to the right
    place — and it is the same vocabulary M6 attributes ownership with."""
    errors = DispatchedFlowExecutor._validate_interface_manifest(_malformed_manifest_yaml())

    assert errors
    assert all(e.startswith("interface_manifest [") for e in errors)
    assert any("[lint]" in e and "endpoint" in e for e in errors)


def test_validate_widened_beyond_lint_to_the_full_gates():
    """#791: this seam ran ``lint()`` alone, which passes a manifest with no stated
    provenance and no warranted decisions — precisely the classes M2 exists to catch. A
    manifest the authoring stage could not fix must be rejectable here, or the revision
    budget's exhaustion has no consequence."""
    raw = yaml.safe_load(_clean_manifest_yaml())
    raw.pop("source_prd")
    no_provenance = yaml.safe_dump(raw)

    assert InterfaceManifest.from_yaml(no_provenance).lint() == []  # the old net saw nothing
    errors = DispatchedFlowExecutor._validate_interface_manifest(no_provenance)
    assert any("[provenance]" in e for e in errors)


def test_validate_unparseable_manifest_is_a_single_error():
    errors = DispatchedFlowExecutor._validate_interface_manifest("::: not valid yaml :::")

    assert len(errors) == 1
    assert "[parses]" in errors[0]


# --------------------------------------------------------------------------- #
# net-b: _reject_invalid_plan_before_workload_gate surfaces interface errors
# --------------------------------------------------------------------------- #


def _executor_for(manifest_yaml: str | None) -> tuple[DispatchedFlowExecutor, Any, Any]:
    stored: dict[str, tuple[Any, bytes]] = {}
    refs: list[str] = []
    # #424: the seam now rejects a plan-less framing outright
    # (plan_authoring_collapsed), so these interface-manifest-net tests carry a
    # minimal valid plan to keep exercising their own net in isolation.
    plan_ref = MagicMock()
    plan_ref.filename = "implementation_plan.yaml"
    plan_ref.artifact_type = "control_implementation_plan"
    minimal_plan = (
        "version: 1\n"
        "project_id: p\n"
        "cycle_id: c\n"
        "prd_hash: h\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: development.develop\n"
        "    role: dev\n"
        '    focus: "Backend"\n'
        '    description: "Build"\n'
        "    expected_artifacts:\n"
        '      - "backend/main.py"\n'
        "    depends_on: []\n"
        "summary:\n"
        "  total_tasks: 1\n"
    )
    stored["ref-plan"] = (plan_ref, minimal_plan.encode("utf-8"))
    refs.append("ref-plan")
    if manifest_yaml is not None:
        ref = MagicMock()
        ref.filename = "interface_manifest.yaml"
        ref.artifact_type = MANIFEST_ARTIFACT_TYPE
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
    assert any(e.startswith("interface_manifest [") and "endpoint" in e for e in errors)


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
# Forwarding: framing's manifest must reach the implementation run
# --------------------------------------------------------------------------- #


def _promoted(artifact_id: str, artifact_type: str) -> Any:
    art = MagicMock()
    art.artifact_id = artifact_id
    art.artifact_type = artifact_type
    art.created_at = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return art


async def _forwarded(*artifacts: Any) -> dict[str, Any]:
    vault = AsyncMock()
    vault.list_artifacts.return_value = list(artifacts)
    executor = DispatchedFlowExecutor(artifact_vault=vault)

    cycle = MagicMock()
    cycle.execution_overrides = {}
    completed = MagicMock()
    completed.run_id = "run_framing"
    completed.workload_type = "framing"

    return await executor._build_forwarding_overrides(cycle, completed)


async def test_a_framing_authored_manifest_is_forwarded_to_the_implementation_run():
    """The #791 finding, pinned. ``_load_interface_manifest_for_run`` reads exactly this
    list; an ``interface_manifest`` dropped here is a promoted, gate-approved design that
    silently never scaffolds anything."""
    overrides = await _forwarded(
        _promoted("art_plan", "control_implementation_plan"),
        _promoted("art_manifest", MANIFEST_ARTIFACT_TYPE),
    )

    assert overrides["plan_artifact_refs"] == ["art_plan", "art_manifest"]


async def test_forwarding_still_carries_the_plan_and_still_drops_run_local_output():
    """The filter is a filter, not a pass-through: source files a framing run happened to
    promote must not become plan inputs to the next workload."""
    overrides = await _forwarded(
        _promoted("art_plan", "control_implementation_plan"),
        _promoted("art_doc", "document"),
        _promoted("art_src", "source"),
    )

    assert overrides["plan_artifact_refs"] == ["art_plan", "art_doc"]
    assert "art_src" in overrides["prior_workload_artifact_refs"]
