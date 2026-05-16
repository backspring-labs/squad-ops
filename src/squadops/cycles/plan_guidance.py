"""PlanGuidance — strategy's plan-authoring contribution (SIP-0093 §5.4.2).

Strategy is the only Rev 1 role that contributes guidance rather than
proposed tasks. The guidance is overlay metadata the merger applies during
``governance.merge_plan``: priority hints, ordering edges, risk callouts,
time-budget allocations, and the small set of items that must not be
skipped under budget pressure.

Required fields are kept tight (`version`, `guidance_id`, `source_brief_id`,
`proposing_role`) so a strategy LLM that produces only partial overlays
still parses. The merger records gaps in ``merge_decisions.yaml`` rather
than relying on strategy to self-report missing dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

_REQUIRED_PROPOSING_ROLE = "strategy"


@dataclass(frozen=True)
class PlanGuidance:
    """Strategy's overlay guidance for ``governance.merge_plan``.

    The merger reads each list as advisory: priorities and ordering bias the
    canonical-task sequencing; ``must_not_skip`` survives merge regardless of
    time pressure; ``defer_if_time_constrained`` is the merger's preferred
    cut surface. None of these fields are typed beyond YAML list/mapping
    shape — over-typing pushes too much format burden onto the LLM for
    inconsistent return.
    """

    version: int
    guidance_id: str
    source_brief_id: str
    proposing_role: str
    priority_guidance: list[dict[str, Any]] = field(default_factory=list)
    ordering_guidance: list[dict[str, Any]] = field(default_factory=list)
    risk_guidance: list[dict[str, Any]] = field(default_factory=list)
    time_budget_guidance: list[dict[str, Any]] = field(default_factory=list)
    scope_cut_guidance: list[str] = field(default_factory=list)
    must_not_skip: list[str] = field(default_factory=list)
    defer_if_time_constrained: list[str] = field(default_factory=list)
    confidence: str = ""

    @classmethod
    def from_yaml(cls, content: str) -> PlanGuidance:
        """Parse a ``plan_guidance.yaml`` document.

        Raises:
            ValueError: malformed YAML, missing required fields, or a
                non-strategy ``proposing_role``. The merger drops a
                malformed guidance file and proceeds without overlay.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed plan_guidance YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("plan_guidance must be a YAML mapping at the top level")

        for key in ("version", "guidance_id", "source_brief_id", "proposing_role"):
            if key not in data:
                raise ValueError(f"plan_guidance missing required field: {key}")

        version = data["version"]
        if not isinstance(version, int):
            raise ValueError(
                f"plan_guidance version must be int, got {type(version).__name__}"
            )

        guidance_id = str(data["guidance_id"]).strip()
        if not guidance_id:
            raise ValueError("plan_guidance guidance_id must be non-empty")

        source_brief_id = str(data["source_brief_id"]).strip()
        if not source_brief_id:
            raise ValueError("plan_guidance source_brief_id must be non-empty")

        proposing_role = str(data["proposing_role"]).strip().lower()
        if proposing_role != _REQUIRED_PROPOSING_ROLE:
            raise ValueError(
                f"plan_guidance proposing_role must be {_REQUIRED_PROPOSING_ROLE!r}, "
                f"got {data['proposing_role']!r}"
            )

        return cls(
            version=version,
            guidance_id=guidance_id,
            source_brief_id=source_brief_id,
            proposing_role=proposing_role,
            priority_guidance=_parse_mapping_list(
                data.get("priority_guidance", []), "priority_guidance"
            ),
            ordering_guidance=_parse_mapping_list(
                data.get("ordering_guidance", []), "ordering_guidance"
            ),
            risk_guidance=_parse_mapping_list(data.get("risk_guidance", []), "risk_guidance"),
            time_budget_guidance=_parse_mapping_list(
                data.get("time_budget_guidance", []), "time_budget_guidance"
            ),
            scope_cut_guidance=_parse_str_list(
                data.get("scope_cut_guidance", []), "scope_cut_guidance"
            ),
            must_not_skip=_parse_str_list(data.get("must_not_skip", []), "must_not_skip"),
            defer_if_time_constrained=_parse_str_list(
                data.get("defer_if_time_constrained", []), "defer_if_time_constrained"
            ),
            confidence=str(data.get("confidence", "")).strip(),
        )


def _parse_mapping_list(raw: object, field_name: str) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError(f"plan_guidance {field_name} must be a YAML list")
    parsed: list[dict[str, Any]] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"plan_guidance {field_name}[{i}] must be a mapping")
        parsed.append(dict(entry))
    return parsed


def _parse_str_list(raw: object, field_name: str) -> list[str]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError(f"plan_guidance {field_name} must be a YAML list")
    return [str(x).strip() for x in raw if str(x).strip()]
