"""The manifest-authoring handler: revise against the gates, emit either way (#791, M1).

Bug classes guarded:

- an accepted manifest emitted under the wrong artifact identity — everything downstream
  finds the manifest by filename/type, so a mismatch silently produces an unscaffolded run;
- **a revision loop that re-rolls instead of revising**: corrective feedback that does not
  name the specific defects is a fresh set of dice with extra steps, which is the fay-6
  new-dice lesson §5c.6 rules against;
- one-defect-per-attempt feedback, which spends the whole budget on a manifest that had three;
- a budget-exhausted manifest being *dropped*, which trades a free framing re-roll and a
  readable rejection for a run failure nobody can attribute;
- the reverse: a genuinely empty response being reported as success, which would hand the
  gate nothing and call it a design;
- an unresolved decision being treated as a rejection, punishing an author for correctly
  declaring what the PRD does not determine;
- **inputs beyond the §5c.1 contract reaching the author** — the contamination class that
  would make every authored-mode measurement unattributable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from squadops.capabilities.handlers.planning import DevelopmentAuthorManifestHandler
from squadops.cycles.manifest_authoring import (
    AUTHORING_INPUT_CONTRACT,
    MANIFEST_ARTIFACT_TYPE,
)

pytestmark = [pytest.mark.domain_capabilities]

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _clean_manifest() -> str:
    return _REFERENCE.read_text(encoding="utf-8")


def _manifest_without(mutate) -> str:
    data = yaml.safe_load(_clean_manifest())
    mutate(data)
    return yaml.dump(data, sort_keys=False)


def _fenced(manifest_yaml: str) -> str:
    return f"Here it is:\n\n```yaml:interface_manifest.yaml\n{manifest_yaml}\n```\n"


def _context(*responses: str) -> Any:
    """A context whose LLM returns ``responses`` in order (last one repeats)."""
    llm = AsyncMock()
    queue = list(responses)

    async def _chat(_messages, **_kwargs):
        return MagicMock(content=queue.pop(0) if len(queue) > 1 else queue[0])

    llm.chat_stream_with_usage.side_effect = _chat
    llm.default_model = "test-model"

    assembled = MagicMock()
    assembled.content = "system prompt"
    assembled.assembly_hash = "deadbeef"
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = assembled

    renderer = AsyncMock()

    async def _render(template_id: str, variables: dict[str, Any]):
        rendered = MagicMock()
        rendered.content = f"[{template_id}] {variables}"
        rendered.template_id = template_id
        rendered.template_version = "1"
        rendered.render_hash = "cafe"
        return rendered

    renderer.render.side_effect = _render

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.request_renderer = renderer
    ports.llm_observability = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    # Real ids: the provenance stamp records them, and a MagicMock here would only ever
    # surface as an unserialisable object rather than as the wrong id.
    ctx.cycle_id = "cyc_test"
    ctx.task_id = "task-authoring-1"
    return ctx


def _inputs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "prd": "Build a group run scheduler.",
        "prior_outputs": {"artifact_contents": {"technical_design.md": "## Design"}},
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
    }
    base.update(overrides)
    return base


def _feedback_renders(ctx) -> list[dict[str, Any]]:
    return [
        call.args[1]
        for call in ctx.ports.request_renderer.render.call_args_list
        if call.args[0] == "request.manifest_revision_feedback"
    ]


# --------------------------------------------------------------------------- #
# The accepted path
# --------------------------------------------------------------------------- #


async def test_a_clean_manifest_is_emitted_under_the_identity_downstream_looks_for():
    ctx = _context(_fenced(_clean_manifest()))

    result = await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert result.success is True
    (artifact,) = result.outputs["artifacts"]
    assert artifact["name"] == "interface_manifest.yaml"
    assert artifact["type"] == MANIFEST_ARTIFACT_TYPE
    assert "kind: interface_manifest" in artifact["content"]
    assert result.outputs["authoring_outcome"]["gates_passed"] is True
    assert ctx.ports.llm.chat_stream_with_usage.await_count == 1


async def test_a_clean_manifest_costs_one_attempt_and_no_revision_feedback():
    """A revision rendered for a passing manifest means the gates rejected something the
    assessment says is fine — the two disagreeing is worth catching directly."""
    ctx = _context(_fenced(_clean_manifest()))

    await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert _feedback_renders(ctx) == []


async def test_declared_open_questions_are_reported_without_rejecting():
    """§5c.10: declining to resolve what the PRD does not determine is correct behavior.
    Rejecting it would teach the author to guess instead — the opposite of the intent."""
    manifest = _manifest_without(
        lambda d: d["decisions"].append(
            {"id": "pagination", "unresolved": True, "question": "page size for GET /runs?"}
        )
    )
    ctx = _context(_fenced(manifest))

    result = await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert result.success is True
    assert result.outputs["authoring_outcome"]["gates_passed"] is True
    assert result.outputs["authoring_outcome"]["open_questions"] == ["page size for GET /runs?"]


# --------------------------------------------------------------------------- #
# The revision loop
# --------------------------------------------------------------------------- #


async def test_a_rejected_manifest_is_revised_with_the_specific_defect_named():
    """Revise, don't re-dice (§5c.6). Feedback that does not name the defect makes the
    second attempt a fresh roll — and fay-6 measured what fresh rolls cost."""
    missing_prd = _manifest_without(lambda d: d.pop("source_prd"))
    ctx = _context(_fenced(missing_prd), _fenced(_clean_manifest()))

    result = await DevelopmentAuthorManifestHandler().handle(
        ctx,
        _inputs(
            resolved_config={"build_profile": "fullstack_fastapi_react", "manifest_max_attempts": 3}
        ),
    )

    assert result.success is True
    assert result.outputs["authoring_outcome"]["gates_passed"] is True
    (feedback,) = _feedback_renders(ctx)
    assert "source_prd" in feedback["findings"]
    assert "source_prd" in feedback["findings"]


async def test_every_defect_is_reported_in_one_revision_not_one_per_attempt():
    """Two defects, one attempt's feedback. One-per-attempt would exhaust the budget on a
    manifest that could have been fixed once — the same reason the gate accumulates."""

    def _break_two(data):
        data.pop("source_prd")
        data["decisions"].append({"id": "no-warrant", "choice": "something"})

    ctx = _context(_fenced(_manifest_without(_break_two)))

    await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    findings = _feedback_renders(ctx)[0]["findings"]
    assert "source_prd" in findings
    assert "decision_record" in findings
    assert len(findings.strip().splitlines()) >= 2


async def test_an_exhausted_budget_still_emits_the_manifest_for_the_gate_to_reject():
    """The layering the two budgets encode: in-stage revisions are cheap, and a manifest
    that survives them still failing is the framing gate's rejection to make — a free
    re-roll (#522) plus a rejection an operator and the taxonomy can both read. Dropping
    it would spend the framing workload and leave nothing behind."""
    broken = _manifest_without(lambda d: d.pop("source_prd"))
    ctx = _context(_fenced(broken))

    result = await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert result.success is True
    assert result.outputs["artifacts"][0]["content"].strip()
    assert result.outputs["authoring_outcome"]["gates_passed"] is False
    assert result.outputs["authoring_outcome"]["class_counts"] == {"authoring_defect": 1}


async def test_the_revision_budget_is_the_configured_one():
    """``manifest_max_attempts`` is an existing profile knob (§5b Q4). A handler that
    ignored it would spend a validated profile's four attempts as two."""
    broken = _manifest_without(lambda d: d.pop("source_prd"))
    ctx = _context(_fenced(broken))

    await DevelopmentAuthorManifestHandler().handle(
        ctx,
        _inputs(
            resolved_config={
                "build_profile": "fullstack_fastapi_react",
                "manifest_max_attempts": 4,
            }
        ),
    )

    assert ctx.ports.llm.chat_stream_with_usage.await_count == 4


# --------------------------------------------------------------------------- #
# Failure surfaces
# --------------------------------------------------------------------------- #


async def test_a_response_with_no_manifest_block_fails_rather_than_emitting_nothing():
    """Distinct from an unwinnable manifest: there is no document for the gate to reject
    or for M6 to classify, so reporting success would hand an empty artifact forward."""
    ctx = _context("I have some thoughts about the design but no file.")

    result = await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert result.success is False
    assert result.outputs == {}
    assert "interface_manifest.yaml" in (result.error or "")


async def test_a_missing_renderer_fails_closed():
    """The prose is a managed asset; without the renderer there is no prompt to send, and
    inventing an inline fallback is what CLAUDE.md #448 forbids."""
    ctx = _context(_fenced(_clean_manifest()))
    ctx.ports.request_renderer = None

    result = await DevelopmentAuthorManifestHandler().handle(ctx, _inputs())

    assert result.success is False
    assert "request_renderer" in (result.error or "")


# --------------------------------------------------------------------------- #
# The input contract (§5c.1)
# --------------------------------------------------------------------------- #


class _RecordingInputs(dict):
    """Records which keys were read for their meaning (not merely serialized)."""

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__(data)
        self.read: set[str] = set()

    def get(self, key, default=None):  # type: ignore[override]
        self.read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)


async def test_the_author_reads_nothing_outside_its_declared_input_contract():
    """§5c.1 made mechanical. An undeclared input is contamination by definition — and the
    failure mode is silent: authored-mode numbers stay plausible while measuring a stage
    that saw something the contract says it did not."""
    inputs = _RecordingInputs(
        _inputs(
            # the shapes contamination would arrive in
            reference_manifest=_clean_manifest(),
            cross_cycle_recall=["last cycle used cursor pagination"],
            contract_criteria_index="vc-routes-endpoints",
        )
    )

    await DevelopmentAuthorManifestHandler().handle(_context(_fenced(_clean_manifest())), inputs)

    assert inputs.read, "the recorder saw no reads at all — the assertion below is vacuous"
    undeclared = inputs.read - AUTHORING_INPUT_CONTRACT
    assert not undeclared, (
        f"the authoring stage read undeclared input(s) {sorted(undeclared)} — add them to "
        f"AUTHORING_INPUT_CONTRACT with a reason, or stop reading them"
    )


async def test_rejection_context_is_inside_the_contract_and_actually_reaches_the_prompt():
    """#669's rail is explicitly IN the contract: it is the cycle's own prior rejection.
    Declared but unread would leave a framing re-roll with fresh dice and no teaching —
    the fay-10 class this stage inherits rather than re-learns."""
    ctx = _context(_fenced(_clean_manifest()))

    await DevelopmentAuthorManifestHandler().handle(
        ctx, _inputs(rejection_reasons=["interface_manifest [provenance]: source_prd is empty"])
    )

    rendered = [c.args[0] for c in ctx.ports.request_renderer.render.call_args_list]
    assert "request.plan_reroll_rejection_appendix" in rendered
