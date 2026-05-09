"""PlanAuthoringBrief — shared frame for SIP-0093 plan authoring.

The brief is authored once per cycle by ``governance.prepare_plan_authoring_brief``
and consumed (read-only) by every role proposer and the merger. It pins
stack, scope, and constraints before fan-out so proposers operate from the
same worldview.

Rev 1 fixes six required fields (objective, stack, requirements, scope, risk).
Optional fields earn promotion to required only after real cycles show they're
load-bearing — keeping the required surface tight prevents the brief from
sliding into "the brief *is* the plan and proposers are typing exercises."

Per RC-22 the brief is immutable after emission. Every downstream
proposal/guidance/merge_decisions artifact references it by ``brief_id``
(RC-23). The brief is always produced — even on sole-author cycles
(``plan_authoring_contributors: []``) the merger still consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass(frozen=True)
class PlanAuthoringBrief:
    """Shared scope-framing artifact consumed by every plan-authoring path.

    Required fields cover the dimensions proposers must agree on: objective,
    stack, requirements, scope cuts, risks. Optional fields are parsed if
    present but carry no validation beyond YAML well-formedness.
    """

    version: int
    brief_id: str
    objective_summary: str
    accepted_stack: dict[str, Any]
    must_cover_requirements: list[str]
    scope_cuts: list[str]
    risk_areas: list[str]
    # Optional Rev 1 fields — parsed if present, no validation beyond YAML shape.
    source_artifact_refs: list[str] = field(default_factory=list)
    major_components: list[str] = field(default_factory=list)
    dependency_assumptions: list[str] = field(default_factory=list)
    time_budget_guidance: dict[str, Any] = field(default_factory=dict)
    task_granularity_guidance: str = ""
    artifact_naming_conventions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, content: str) -> PlanAuthoringBrief:
        """Parse a ``plan_authoring_brief.yaml`` document.

        Strict on the seven required fields, permissive on optionals — a
        malformed brief is a hard failure for the framing phase, so the error
        message names the specific missing or invalid field rather than dumping
        the parsed dict.

        Raises:
            ValueError: malformed YAML, top-level non-mapping, or any required
                field missing or wrong-shaped.
        """
        data = _parse_top_level(content)
        required = _validate_required(data)
        optionals = _validate_optionals(data)

        return cls(
            version=required["version"],
            brief_id=required["brief_id"],
            objective_summary=required["objective_summary"],
            accepted_stack=required["accepted_stack"],
            must_cover_requirements=required["must_cover_requirements"],
            scope_cuts=required["scope_cuts"],
            risk_areas=required["risk_areas"],
            **optionals,
        )


_REQUIRED_FIELDS = (
    "version",
    "brief_id",
    "objective_summary",
    "accepted_stack",
    "must_cover_requirements",
    "scope_cuts",
    "risk_areas",
)


def _parse_top_level(content: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed brief YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Brief must be a YAML mapping at the top level")
    for key in _REQUIRED_FIELDS:
        if key not in data:
            raise ValueError(f"Brief missing required field: {key}")
    return data


def _require_str_list(data: dict[str, Any], key: str) -> list[str]:
    v = data[key]
    if not isinstance(v, list):
        raise ValueError(f"Brief {key} must be a list, got {type(v).__name__}")
    return [str(x) for x in v]


def _validate_required(data: dict[str, Any]) -> dict[str, Any]:
    version = data["version"]
    if not isinstance(version, int):
        raise ValueError(f"Brief version must be int, got {type(version).__name__}")

    brief_id = str(data["brief_id"]).strip()
    if not brief_id:
        raise ValueError("Brief brief_id must be non-empty")

    objective_summary = str(data["objective_summary"]).strip()
    if not objective_summary:
        raise ValueError("Brief objective_summary must be non-empty")

    accepted_stack = data["accepted_stack"]
    if not isinstance(accepted_stack, dict):
        raise ValueError(
            f"Brief accepted_stack must be a mapping, got {type(accepted_stack).__name__}"
        )

    return {
        "version": version,
        "brief_id": brief_id,
        "objective_summary": objective_summary,
        "accepted_stack": dict(accepted_stack),
        "must_cover_requirements": _require_str_list(data, "must_cover_requirements"),
        "scope_cuts": _require_str_list(data, "scope_cuts"),
        "risk_areas": _require_str_list(data, "risk_areas"),
    }


def _opt_list(data: dict[str, Any], key: str) -> list[str]:
    v = data.get(key, [])
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError(f"Brief {key} must be a list when present")
    return [str(x) for x in v]


def _opt_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    v = data.get(key, {})
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"Brief {key} must be a mapping when present")
    return dict(v)


def _opt_str(data: dict[str, Any], key: str) -> str:
    v = data.get(key, "")
    return "" if v is None else str(v)


def _validate_optionals(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_artifact_refs": _opt_list(data, "source_artifact_refs"),
        "major_components": _opt_list(data, "major_components"),
        "dependency_assumptions": _opt_list(data, "dependency_assumptions"),
        "time_budget_guidance": _opt_dict(data, "time_budget_guidance"),
        "task_granularity_guidance": _opt_str(data, "task_granularity_guidance"),
        "artifact_naming_conventions": _opt_list(data, "artifact_naming_conventions"),
        "open_questions": _opt_list(data, "open_questions"),
    }
