"""Tests for ``PlanGuidance`` (SIP-0093 §5.4.2)."""

from __future__ import annotations

import pytest

from squadops.cycles.plan_guidance import PlanGuidance

pytestmark = [pytest.mark.domain_orchestration]


_VALID_GUIDANCE = """\
version: 1
guidance_id: guidance-strategy-001
source_brief_id: brief-test-001
proposing_role: strategy
priority_guidance:
  - area: backend_api
    priority: high
    rationale: "API surface is the integration anchor."
ordering_guidance:
  - before: dev.repository
    after: dev.api.routes
    rationale: "Routes pin the contract before persistence shape lands."
risk_guidance:
  - target: dev.api.routes
    risk: "Auth middleware not specified — assume Keycloak."
time_budget_guidance:
  - area: backend_api
    budget_pct: 30
scope_cut_guidance:
  - "Defer admin dashboards to a follow-up cycle."
must_not_skip:
  - "Auth integration smoke test"
defer_if_time_constrained:
  - "Cosmetic frontend polish"
confidence: medium
"""


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestFromYAMLHappy:
    def test_parses_valid_guidance(self):
        g = PlanGuidance.from_yaml(_VALID_GUIDANCE)
        assert g.version == 1
        assert g.guidance_id == "guidance-strategy-001"
        assert g.source_brief_id == "brief-test-001"
        assert g.proposing_role == "strategy"

        assert len(g.priority_guidance) == 1
        assert g.priority_guidance[0]["area"] == "backend_api"
        assert g.priority_guidance[0]["priority"] == "high"

        assert g.ordering_guidance[0]["before"] == "dev.repository"
        assert g.risk_guidance[0]["target"] == "dev.api.routes"
        assert g.time_budget_guidance[0]["budget_pct"] == 30

        assert g.scope_cut_guidance == ["Defer admin dashboards to a follow-up cycle."]
        assert g.must_not_skip == ["Auth integration smoke test"]
        assert g.defer_if_time_constrained == ["Cosmetic frontend polish"]
        assert g.confidence == "medium"

    def test_minimal_guidance_with_only_required_fields(self):
        """An LLM that returns only the required fields parses cleanly; the
        merger applies an empty overlay. Forcing optional fields to be
        populated would push too much format burden on strategy LLMs that
        legitimately have nothing to say in a given dimension."""
        minimal = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: strategy\n"
        )
        g = PlanGuidance.from_yaml(minimal)
        assert g.priority_guidance == []
        assert g.ordering_guidance == []
        assert g.must_not_skip == []
        assert g.confidence == ""


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestFromYAMLErrors:
    @pytest.mark.parametrize(
        "missing_field",
        ["version", "guidance_id", "source_brief_id", "proposing_role"],
    )
    def test_required_field_missing_rejected(self, missing_field):
        """Each required field must produce an error message that names it,
        so a malformed strategy emission is diagnosable without re-running
        the LLM call."""
        full = {
            "version": "1",
            "guidance_id": "g-1",
            "source_brief_id": "b-1",
            "proposing_role": "strategy",
        }
        full.pop(missing_field)
        yaml_doc = "\n".join(f"{k}: {v}" for k, v in full.items()) + "\n"
        with pytest.raises(ValueError, match=missing_field):
            PlanGuidance.from_yaml(yaml_doc)

    @pytest.mark.parametrize(
        "bad_role",
        ["development", "qa", "lead", "STRATEGY"[1:], ""],
    )
    def test_non_strategy_proposing_role_rejected(self, bad_role):
        """Strategy is the only Rev 1 contributor of guidance — a proposal
        coming through with another role indicates pipeline corruption,
        not a recoverable malformation."""
        yaml_doc = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            f'proposing_role: "{bad_role}"\n'
        )
        with pytest.raises(ValueError, match="proposing_role"):
            PlanGuidance.from_yaml(yaml_doc)

    def test_strategy_role_case_normalized(self):
        """``Strategy`` and ``strategy`` must both parse — LLM casing varies."""
        yaml_doc = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: Strategy\n"
        )
        g = PlanGuidance.from_yaml(yaml_doc)
        assert g.proposing_role == "strategy"

    def test_non_int_version_rejected(self):
        yaml_doc = (
            'version: "1"\n'
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: strategy\n"
        )
        with pytest.raises(ValueError, match="version"):
            PlanGuidance.from_yaml(yaml_doc)

    def test_priority_guidance_non_list_rejected(self):
        """A scalar where a list is expected is a structural mismatch the
        merger can't usefully recover from; surface at parse time."""
        yaml_doc = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: strategy\n"
            'priority_guidance: "high"\n'
        )
        with pytest.raises(ValueError, match="priority_guidance"):
            PlanGuidance.from_yaml(yaml_doc)

    def test_priority_guidance_list_with_non_mapping_rejected(self):
        """A list of scalars would be silently coerced to ``dict(entry)``
        and explode at attribute access in the merger; reject at parse."""
        yaml_doc = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: strategy\n"
            "priority_guidance:\n"
            '  - "backend_api: high"\n'
        )
        with pytest.raises(ValueError, match="priority_guidance"):
            PlanGuidance.from_yaml(yaml_doc)

    def test_must_not_skip_must_be_list(self):
        yaml_doc = (
            "version: 1\n"
            "guidance_id: g-1\n"
            "source_brief_id: b-1\n"
            "proposing_role: strategy\n"
            'must_not_skip: "auth tests"\n'
        )
        with pytest.raises(ValueError, match="must_not_skip"):
            PlanGuidance.from_yaml(yaml_doc)

    def test_malformed_yaml_rejected(self):
        with pytest.raises(ValueError, match="Malformed"):
            PlanGuidance.from_yaml("version: 1\nguidance_id: g-1\nsource_brief_id: [unclosed")
