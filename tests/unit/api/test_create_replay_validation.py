"""SIP-0101 Slice 3.1/3.5 — create-time replay validation + interim gate.

A replay admitted against a missing run, a pruned boundary, or a divergent
contract/prd/profile would restore a prefix that never matches what the target
executes — the gate must refuse at create, naming the failing element.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.api.routes.cycles.cycles import _validate_replay_declaration
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import PreflightRejectedError, RunNotFoundError

pytestmark = [pytest.mark.domain_api]

_APPLIED = {"build_profile": "fullstack_fastapi_react"}


def _body(overrides: dict, prd_ref: str = "prd_1") -> SimpleNamespace:
    return SimpleNamespace(execution_overrides=overrides, prd_ref=prd_ref)


def _decl(source: str = "run_src", boundary: int = 2) -> dict:
    return {
        "execution_mode": "replay",
        "replay": {"source_run_id": source, "boundary_index": boundary},
    }


def _registry(
    *,
    source_prd: str = "prd_1",
    source_config: dict | None = None,
    checkpoint_indexes: tuple[int, ...] = (1, 2),
) -> AsyncMock:
    registry = AsyncMock()
    registry.get_run.return_value = SimpleNamespace(run_id="run_src", cycle_id="cyc_src")
    source_cycle = MagicMock()
    source_cycle.prd_ref = source_prd
    source_cycle.resolved_config.return_value = source_config or dict(_APPLIED)
    registry.get_cycle.return_value = source_cycle
    registry.list_checkpoints.return_value = [
        RunCheckpoint(
            run_id="run_src",
            checkpoint_index=i,
            completed_task_ids=(),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=datetime.now(UTC),
        )
        for i in checkpoint_indexes
    ]
    return registry


async def test_normal_cycle_touches_nothing():
    registry = AsyncMock()
    await _validate_replay_declaration(registry, _body({}), _APPLIED)
    registry.get_run.assert_not_awaited()


async def test_malformed_declaration_rejected():
    with pytest.raises(PreflightRejectedError, match="replay_declaration_invalid"):
        await _validate_replay_declaration(
            AsyncMock(), _body({"execution_mode": "replay"}), _APPLIED
        )


async def test_missing_source_run_rejected():
    registry = AsyncMock()
    registry.get_run.side_effect = RunNotFoundError("nope")
    with pytest.raises(PreflightRejectedError, match="replay_source_missing"):
        await _validate_replay_declaration(registry, _body(_decl()), _APPLIED)


async def test_missing_boundary_rejected_by_index():
    registry = _registry(checkpoint_indexes=(1,))  # boundary 2 pruned/never written
    with pytest.raises(PreflightRejectedError, match="replay_boundary_missing"):
        await _validate_replay_declaration(registry, _body(_decl(boundary=2)), _APPLIED)


async def test_contract_mismatch_rejected_naming_the_element():
    registry = _registry(source_config={**_APPLIED, "contract_ref": "art_c9"})
    # target declares no contract_ref → author-mode target vs bind-mode source
    with pytest.raises(PreflightRejectedError, match="contract_ref"):
        await _validate_replay_declaration(registry, _body(_decl()), _APPLIED)


async def test_prd_mismatch_rejected_naming_the_element():
    registry = _registry(source_prd="prd_other")
    with pytest.raises(PreflightRejectedError, match="prd_ref"):
        await _validate_replay_declaration(registry, _body(_decl()), _APPLIED)


async def test_compatible_replay_admitted():
    registry = _registry(source_config={**_APPLIED, "contract_ref": "art_c9"})
    overrides = {**_decl(), "contract_ref": "art_c9"}
    await _validate_replay_declaration(registry, _body(overrides), _APPLIED)  # no raise
