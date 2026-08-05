"""Replay evidence rails — rendering surface (SIP-0101 Slice 1).

The ``ReplayProvenance`` record itself lives in ``verification_integrity``
beside its evidence-disclosure siblings (``UnverifiedCheck``, ``WaivedCheck``)
so the aggregation module stays import-pure; it is re-exported here as the
SIP-0101-named import path. This module owns the human-facing wording.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.verification_integrity import ReplayProvenance

__all__ = [
    "EXECUTION_MODE_REPLAY",
    "REPLAY_COMPATIBILITY_ELEMENTS",
    "ReplayProvenance",
    "ReplayRequest",
    "check_replay_compatibility",
    "parse_replay_declaration",
    "replay_marker_lines",
    "translate_checkpoint_for_replay",
]


def replay_marker_lines(replay: ReplayProvenance) -> list[str]:
    """The human-facing replay disclosure, shared by every rendering surface.

    One source for the wording so the report, CLI, and any future surface
    cannot drift into softer language: evidence at or before the boundary is
    inherited, not earned.
    """
    return [
        f"⚠ REPLAYED — prefix restored from {replay.source_run_id} "
        f"at boundary {replay.boundary_index}",
        "Evidence at or before the boundary is inherited from the source run, "
        "not earned by this execution.",
    ]


# --------------------------------------------------------------------------- #
# Slice 3 — the mechanism (SIP-0101 §3): declaration, compatibility, translation
# --------------------------------------------------------------------------- #

EXECUTION_MODE_REPLAY = "replay"

# Interim create-time compatibility gate (Slice 3.5): strict equality over these
# elements between source cycle and target request. Deliberately MORE conservative
# than §3.5's eventual per-boundary sets — Slice 4 relaxes an existing guard.
# ``plan_artifact_refs`` equality is guaranteed by construction: the replayed
# prefix restores the source checkpoint's own artifact refs.
REPLAY_COMPATIBILITY_ELEMENTS = ("prd_ref", "build_profile", "contract_ref")


@dataclass(frozen=True)
class ReplayRequest:
    """A parsed, well-formed replay declaration off ``execution_overrides``."""

    source_run_id: str
    boundary_index: int

    def __post_init__(self) -> None:
        if not self.source_run_id:
            raise ValueError("replay.source_run_id must be non-empty")
        if self.boundary_index < 0:
            raise ValueError("replay.boundary_index must be >= 0")


def parse_replay_declaration(execution_overrides: Mapping[str, Any]) -> ReplayRequest | None:
    """Parse the maintainer-only replay declaration; ``None`` for normal cycles.

    The declaration is two keys in ``execution_overrides`` (no new API surface —
    the SIP-0101 harness entry point, classified maintainer-only):

        execution_mode: replay
        replay: {source_run_id: run_..., boundary_index: N}

    Raises ``ValueError`` on any malformed shape — a half-declared replay must
    never execute as a normal run (or vice versa).
    """
    mode = execution_overrides.get("execution_mode")
    block = execution_overrides.get("replay")
    if mode is None and block is None:
        return None
    if mode != EXECUTION_MODE_REPLAY:
        raise ValueError(f"replay block requires execution_mode: {EXECUTION_MODE_REPLAY!r}")
    if not isinstance(block, Mapping):
        raise ValueError("execution_mode: replay requires a replay: {...} block")
    try:
        return ReplayRequest(
            source_run_id=str(block["source_run_id"]),
            boundary_index=int(block["boundary_index"]),
        )
    except (KeyError, TypeError) as e:
        raise ValueError(f"malformed replay block: {e!r}") from e


def check_replay_compatibility(source: Mapping[str, Any], target: Mapping[str, Any]) -> list[str]:
    """Strict-equality interim gate (Slice 3.5): mismatches name the failing element."""
    errors = []
    for element in REPLAY_COMPATIBILITY_ELEMENTS:
        if source.get(element) != target.get(element):
            errors.append(
                f"replay_incompatible: {element} differs "
                f"(source={source.get(element)!r}, target={target.get(element)!r})"
            )
    return errors


def translate_checkpoint_for_replay(checkpoint: RunCheckpoint, target_run_id: str) -> RunCheckpoint:
    """Rebind a source run's boundary checkpoint into the target run's namespace.

    Task ids embed the producing run (``task-{run_id[:12]}-m{index}-{type}``,
    SIP-0086 RC-2), so the source's ``completed_task_ids`` can never match the
    target plan's ids for dispatch suppression — the premise correction to the
    SIP plan's 3.3. Only the run prefix rebinds; the deterministic suffix
    (task index + type) is untouched, so suppression matches exactly the same
    plan positions the source completed. Everything else — prior_outputs
    (role-keyed), artifact refs (globally addressed), plan-delta refs — is
    carried verbatim; a source id that does not carry the expected prefix
    fails closed (the determinism contract, never a guess).
    """
    source_prefix = f"task-{checkpoint.run_id[:12]}-"
    target_prefix = f"task-{target_run_id[:12]}-"
    translated = []
    for task_id in checkpoint.completed_task_ids:
        if not task_id.startswith(source_prefix):
            raise ValueError(
                f"replay checkpoint task id {task_id!r} is not in the source run's "
                f"deterministic namespace ({source_prefix!r}*) — cannot translate"
            )
        translated.append(target_prefix + task_id[len(source_prefix) :])
    return RunCheckpoint(
        run_id=target_run_id,
        checkpoint_index=checkpoint.checkpoint_index,
        completed_task_ids=tuple(translated),
        prior_outputs=checkpoint.prior_outputs,
        artifact_refs=checkpoint.artifact_refs,
        plan_delta_refs=checkpoint.plan_delta_refs,
        created_at=checkpoint.created_at,
    )
