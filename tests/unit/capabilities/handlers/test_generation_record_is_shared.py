"""Every cycle handler records generations through one implementation.

``GovernanceReviewHandler`` carried a private copy of ``_record_generation`` that
silently shadowed the shared one. The base's docstring even documented the variant, so
it read as deliberate — but its stated justification ("has no ChatMessage") had stopped
being true, and the copy quietly cost governance everything the shared version had
gained since: token counts, throughput, prompt name and version, and the configurable
prompt-layer kind.

Nothing failed. Governance generations simply arrived in LangFuse thinner than every
other handler's, for as long as nobody diffed two files that were never meant to be
compared. Same class as #918 — a private, drifted duplicate of a shared surface.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import GovernanceReviewHandler

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[4]
_CYCLE = _REPO / "src/squadops/capabilities/handlers/cycle"


def _context_recording_generations() -> tuple[MagicMock, list]:
    """A context whose observability port captures what it is handed."""
    recorded: list = []
    ctx = MagicMock()
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.request_renderer = None
    ctx.ports.llm.default_model = "fallback-model"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock()
    ctx.correlation_context = MagicMock()
    ctx.ports.llm_observability.record_generation = lambda corr, record, layers: recorded.append(
        (record, layers)
    )
    ctx.project_id = "group_run"
    ctx.cycle_id = "cyc_test"
    return ctx, recorded


def _response() -> MagicMock:
    resp = MagicMock()
    resp.content = "review body"
    resp.tokens_per_second = 11.5
    resp.prompt_tokens = 1200
    resp.completion_tokens = 800
    resp.total_tokens = 2000
    return resp


async def test_governance_records_the_token_accounting_it_used_to_drop():
    """Bug caught: the private copy omitted every usage field.

    These four are the whole point of recording a generation — without them a trace
    says an LLM call happened and nothing about what it cost. They were present for
    dev, qa and builder and absent for governance.

    ``implementation_plan: True`` is load-bearing. The other setting delegates to the
    base handler, whose own inline observability block already records everything —
    so the first version of this test passed against the defect it was written for.
    """
    ctx, recorded = _context_recording_generations()
    ctx.ports.llm.chat_stream_with_usage.return_value = _response()

    await GovernanceReviewHandler().handle(
        ctx, {"prd": "build a thing", "resolved_config": {"implementation_plan": True}}
    )

    assert recorded, "governance recorded no generation at all"
    record, _ = recorded[-1]
    assert record.prompt_tokens == 1200
    assert record.completion_tokens == 800
    assert record.total_tokens == 2000
    assert record.tokens_per_second == 11.5


async def test_governance_keeps_its_existing_prompt_layer_identity():
    """Bug caught: inheriting the shared version silently re-groups the traces.

    The private copy hardcoded ``f"{role}-cycle"``; the shared one derives the string
    from ``_prompt_layer_kind``, whose base default is ``"build"``. Deleting the copy
    without pinning the field would have moved every governance generation into a
    different layer set — a data change disguised as a refactor.
    """
    ctx, recorded = _context_recording_generations()
    ctx.ports.llm.chat_stream_with_usage.return_value = _response()

    await GovernanceReviewHandler().handle(
        ctx, {"prd": "build a thing", "resolved_config": {"implementation_plan": True}}
    )

    _, layers = recorded[-1]
    assert layers.prompt_layer_set_id == "lead-cycle"


def test_no_cycle_handler_defines_its_own_generation_record():
    """Bug caught: a second copy reappears.

    Structural, because the failure mode is silence — a shadowing override changes no
    behavior the functional tests observe, it only makes one handler's telemetry worse
    than the rest. The base class is the single legitimate definition.
    """
    definitions = []
    for path in sorted(_CYCLE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_record_generation":
                definitions.append(f"{path.name}:{node.lineno}")

    assert len(definitions) == 1 and definitions[0].startswith("base.py:"), (
        f"_record_generation is defined in {definitions} — it belongs to the cycle "
        f"handler base alone; a per-handler copy drifts silently and costs that "
        f"handler its telemetry"
    )
