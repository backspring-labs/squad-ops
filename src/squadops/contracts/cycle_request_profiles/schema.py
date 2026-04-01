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
    "build_manifest",
    "max_build_subtasks",
    "min_build_subtasks",
    "output_validation",
    "max_self_eval_passes",
    "min_artifact_count",
    "stub_threshold_bytes",
}

_ALL_ALLOWED_KEYS = _ALLOWED_DEFAULT_KEYS | _APPLIED_DEFAULTS_EXTRA_KEYS

# SIP-0076 D11/D18: valid gate name prefixes for workload_sequence entries.
_VALID_GATE_PREFIXES = ("progress_", "promote_")


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
        return v
