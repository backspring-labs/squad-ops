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
_APPLIED_DEFAULTS_EXTRA_KEYS = {"build_tasks", "plan_tasks"}

_ALL_ALLOWED_KEYS = _ALLOWED_DEFAULT_KEYS | _APPLIED_DEFAULTS_EXTRA_KEYS


class PromptMeta(BaseModel):
    """CLI prompt metadata for interactive mode."""

    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)


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
        return v
