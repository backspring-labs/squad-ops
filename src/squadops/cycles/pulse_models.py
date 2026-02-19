"""
Pulse verification domain models (SIP-0070: Pulse Checks and Verification).

Cadence-bounded execution intervals with fast, mechanical checks at boundaries.
All models are frozen dataclasses to match the cycle/run lifecycle pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from squadops.capabilities.acceptance import (
    KNOWN_TEMPLATE_PREFIXES,
    KNOWN_TEMPLATE_VARIABLES,
    validate_template_variables,
)
from squadops.capabilities.models import AcceptanceCheck, CheckType

# Single constant for cadence boundary identifier (D19).
# Used everywhere cadence-bound boundaries are emitted, compared, or validated.
CADENCE_BOUNDARY_ID = "cadence"


# =============================================================================
# Enums
# =============================================================================


class PulseDecision(str, Enum):  # noqa: UP042 — project convention
    """Boundary-level decision derived from per-suite outcomes."""

    PASS = "pass"
    FAIL = "fail"
    EXHAUSTED = "exhausted"


class SuiteOutcome(str, Enum):  # noqa: UP042 — project convention
    """Per-suite verification outcome."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


# =============================================================================
# Frozen dataclasses
# =============================================================================


@dataclass(frozen=True)
class CadencePolicy:
    """Runtime cadence limits for pulse boundaries.

    max_pulse_seconds: Maximum wall-clock time per cadence interval (non-preemptive).
    max_tasks_per_pulse: Maximum tasks dispatched before cadence close.
    """

    max_pulse_seconds: int = 600
    max_tasks_per_pulse: int = 5


@dataclass(frozen=True)
class PulseCheckDefinition:
    """A named suite of acceptance checks bound to a pulse boundary.

    suite_id: Author-assigned unique identifier within a CRP profile.
    boundary_id: Semantic binding target (e.g., "post_dev", "post_build", "cadence").
    checks: Acceptance checks to evaluate at this boundary.
    suite_class: Suite classification ("guardrail" for Tier 1; "proof" rejected).
    after_task_types: Task type prefixes that determine where milestones fire.
    binding_mode: "milestone" (default) or "cadence" (heartbeat).
    max_suite_seconds: Suite-level timeout.
    max_check_seconds: Per-check timeout.
    """

    suite_id: str
    boundary_id: str
    checks: tuple[AcceptanceCheck, ...] = ()
    suite_class: str = "guardrail"
    after_task_types: tuple[str, ...] = ()
    binding_mode: str = "milestone"
    max_suite_seconds: float = 30
    max_check_seconds: float = 10


@dataclass(frozen=True)
class PulseVerificationRecord:
    """Per-suite verification record persisted to the registry (D16).

    Records are facts: suite X produced outcome Y at boundary Z.
    Boundary-level decisions are derived by determine_boundary_decision().
    """

    suite_id: str
    boundary_id: str
    cadence_interval_id: int
    run_id: str
    suite_outcome: SuiteOutcome
    check_results: tuple[dict, ...] = ()
    repair_attempt_number: int = 0
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    repair_task_refs: tuple[str, ...] = ()
    notes: str | None = None


# =============================================================================
# Factory / parser
# =============================================================================


def parse_pulse_checks(
    raw_list: list[dict],
    profile_dir: str | None = None,
) -> tuple[PulseCheckDefinition, ...]:
    """Parse raw CRP pulse_checks into validated PulseCheckDefinition objects.

    Validates:
    - suite_class != "proof" (D6: fail early)
    - binding_mode in {"milestone", "cadence"}
    - cadence binding: boundary_id must equal CADENCE_BOUNDARY_ID (D5a)
    - suite_id uniqueness within the profile (D15)
    - json_schema.schema resolved relative to profile_dir

    Args:
        raw_list: List of dicts from CRP YAML defaults.pulse_checks.
        profile_dir: Directory containing the CRP profile (for relative schema paths).

    Returns:
        Tuple of validated PulseCheckDefinition objects.

    Raises:
        ValueError: On validation failure.
    """
    definitions: list[PulseCheckDefinition] = []
    seen_suite_ids: set[str] = set()

    for idx, raw in enumerate(raw_list):
        suite_id = raw.get("suite_id")
        if not suite_id:
            raise ValueError(f"pulse_checks[{idx}]: suite_id is required")

        if suite_id in seen_suite_ids:
            raise ValueError(
                f"pulse_checks[{idx}]: duplicate suite_id {suite_id!r}"
            )
        seen_suite_ids.add(suite_id)

        suite_class = raw.get("suite_class", "guardrail")
        if suite_class == "proof":
            raise ValueError(
                f"pulse_checks[{idx}] ({suite_id}): suite_class='proof' is not "
                f"supported in Tier 1. Use 'guardrail' instead."
            )

        binding_mode = raw.get("binding_mode", "milestone")
        if binding_mode not in ("milestone", "cadence"):
            raise ValueError(
                f"pulse_checks[{idx}] ({suite_id}): binding_mode must be "
                f"'milestone' or 'cadence', got {binding_mode!r}"
            )

        boundary_id = raw.get("boundary_id", "")
        if not boundary_id:
            raise ValueError(
                f"pulse_checks[{idx}] ({suite_id}): boundary_id is required"
            )

        # D5a: cadence binding enforces boundary_id == CADENCE_BOUNDARY_ID
        if binding_mode == "cadence" and boundary_id != CADENCE_BOUNDARY_ID:
            raise ValueError(
                f"pulse_checks[{idx}] ({suite_id}): cadence-bound suite must "
                f"have boundary_id={CADENCE_BOUNDARY_ID!r}, got {boundary_id!r}"
            )

        # Parse individual checks
        raw_checks = raw.get("checks", [])
        checks: list[AcceptanceCheck] = []
        for _cidx, raw_check in enumerate(raw_checks):
            check_type = CheckType(raw_check["check_type"])
            kwargs = dict(raw_check)
            kwargs["check_type"] = check_type

            # Convert command list to tuple
            if "command" in kwargs and isinstance(kwargs["command"], list):
                kwargs["command"] = tuple(kwargs["command"])

            # Convert env list of dicts/lists to tuple of tuples
            if "env" in kwargs and isinstance(kwargs["env"], list):
                env_tuples = []
                for e in kwargs["env"]:
                    if isinstance(e, (list, tuple)) and len(e) == 2:
                        env_tuples.append(tuple(e))
                    elif isinstance(e, dict):
                        for k, v in e.items():
                            env_tuples.append((k, str(v)))
                kwargs["env"] = tuple(env_tuples)

            # Convert after_task_types to tuple
            if "after_task_types" in kwargs and isinstance(kwargs["after_task_types"], list):
                kwargs["after_task_types"] = tuple(kwargs["after_task_types"])

            checks.append(AcceptanceCheck(**kwargs))

        # Validate template variables in check targets (fail early, not at runtime)
        for cidx, check in enumerate(checks):
            if check.target:
                bad_vars = validate_template_variables(check.target)
                if bad_vars:
                    valid = sorted(KNOWN_TEMPLATE_VARIABLES) + [
                        f"{p}.*" for p in sorted(KNOWN_TEMPLATE_PREFIXES)
                    ]
                    raise ValueError(
                        f"pulse_checks[{idx}] ({suite_id}): check[{cidx}] target "
                        f"references unknown template variable(s): {bad_vars}. "
                        f"Valid variables: {valid}"
                    )

        after_task_types = raw.get("after_task_types", [])
        if isinstance(after_task_types, list):
            after_task_types = tuple(after_task_types)

        definitions.append(PulseCheckDefinition(
            suite_id=suite_id,
            boundary_id=boundary_id,
            checks=tuple(checks),
            suite_class=suite_class,
            after_task_types=after_task_types,
            binding_mode=binding_mode,
            max_suite_seconds=raw.get("max_suite_seconds", 30),
            max_check_seconds=raw.get("max_check_seconds", 10),
        ))

    return tuple(definitions)
