"""
Pydantic schema for CycleRequestProfile validation (SIP-0065 §5).

CRP is a value-object contract pack — not a domain entity, not an API resource.
Profiles are validated at load time to ensure defaults stay in sync with the
server DTO (CycleCreateRequest).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from squadops.api.routes.cycles.dtos import CycleCreateRequest

# Ground truth for allowed default keys — derived from the server DTO (D9).
_ALLOWED_DEFAULT_KEYS = set(CycleCreateRequest.model_fields.keys())

# Keys that are valid in CRP defaults but flow into applied_defaults (not top-level DTO).
# These control task plan generation and are consumed by the executor, not the API.
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks",
    "plan_tasks",
    "pulse_checks",
    "cadence_policy",
    "build_profile",
    "dev_capability",
    "generation_timeout",
    "workload_sequence",
    "max_task_retries",
    "max_task_seconds",
    "max_consecutive_failures",
    "max_correction_attempts",
    "time_budget_seconds",
    "implementation_pulse_checks",
    "implementation_plan",
    "max_build_subtasks",
    "min_build_subtasks",
    "output_validation",
    "max_self_eval_passes",
    "min_artifact_count",
    "stub_threshold_bytes",
    # SIP-0092 M1.3 typed acceptance
    "typed_acceptance",  # master flag (default true)
    "command_acceptance_checks",  # gate command_exit_zero independently
    "command_check_safelist",  # operator-controlled extension to argv safelist
    "stack",  # resolved stack identity for typed-check evaluators
    # SIP-0093: multi-role plan authoring activation. Selects which roles emit
    # ``*.propose_plan_tasks`` before ``governance.merge_plan``; empty/absent
    # → the merger runs sole-author. Consumed by task_plan.build_planning_steps
    # via resolved_config. Valid roles: development, qa, strategy (build reserved
    # for Rev 2). Without this entry no request profile can turn the path on.
    "plan_authoring_contributors",
    # SIP-0096 §6.3: explicit list of stable check-ids this profile REQUIRES.
    # A required check classified not-executed at run end blocks acceptance as
    # blocked_unverified. Requiredness is declared here, never inferred from
    # names/types/history (AC#5). Absent/empty → nothing required (Phase 1 ships
    # no required lists; the per-profile list is the Phase 2 throttle).
    "required_checks",
}

_ALL_ALLOWED_KEYS = _ALLOWED_DEFAULT_KEYS | _APPLIED_DEFAULTS_EXTRA_KEYS

# SIP-0076 D11/D18: valid gate name prefixes for workload_sequence entries.
_VALID_GATE_PREFIXES = ("progress_", "promote_")


def _validate_required_checks(defaults: dict) -> None:
    """Validate the SIP-0096 ``required_checks`` declaration shape at load time.

    Must be a list of non-empty, non-duplicate check-id strings. Fail loud on a
    malformed declaration rather than let a mis-shaped required list silently
    mis-aggregate at run end (the "no fallback that masks" rule).
    """
    checks = defaults.get("required_checks")
    if checks is None:
        return
    if not isinstance(checks, list):
        raise ValueError(
            f"required_checks must be a list of check-id strings, got {type(checks).__name__}"
        )
    seen: set[str] = set()
    for entry in checks:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"required_checks entries must be non-empty strings, got {entry!r}")
        if entry in seen:
            raise ValueError(f"required_checks contains duplicate check-id {entry!r}")
        seen.add(entry)


def _validate_workload_sequence_gates(defaults: dict) -> None:
    """Validate that gate names in workload_sequence use allowed prefixes (case-sensitive)."""
    sequence = defaults.get("workload_sequence")
    if not sequence or not isinstance(sequence, list):
        return
    for entry in sequence:
        if not isinstance(entry, dict):
            continue
        gate = entry.get("gate")
        if gate is None or gate == "auto":
            continue  # null = no gate, auto = auto-progress
        if not any(gate.startswith(prefix) for prefix in _VALID_GATE_PREFIXES):
            raise ValueError(
                f"Gate name {gate!r} in workload_sequence must start with "
                f"'progress_' or 'promote_'. Got: {gate!r}"
            )


class PromptMeta(BaseModel):
    """CLI/console prompt metadata for interactive mode (SIP-0074 §5.8)."""

    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)
    type: str | None = None  # "choice" | "text" | "bool" — inferred by consumers if None
    required: bool = False


class CycleRequestProfile(BaseModel):
    """A named YAML profile that guides Cycle creation.

    Contains defaults (suggested values for defaultable Cycle fields) and
    optional prompt metadata for interactive CLI mode.
    """

    name: str
    description: str = ""
    defaults: dict = Field(default_factory=dict)
    prompts: dict[str, PromptMeta] = Field(default_factory=dict)

    @field_validator("defaults")
    @classmethod
    def validate_known_keys(cls, v: dict) -> dict:
        """Fail fast if defaults contain keys not in CycleCreateRequest or applied_defaults."""
        unknown = set(v.keys()) - _ALL_ALLOWED_KEYS
        if unknown:
            raise ValueError(f"Unknown default keys: {unknown}")
        # SIP-0076 D11/D18: validate gate names in workload_sequence
        _validate_workload_sequence_gates(v)
        # SIP-0096 §6.3: validate the required_checks declaration shape
        _validate_required_checks(v)
        return v
