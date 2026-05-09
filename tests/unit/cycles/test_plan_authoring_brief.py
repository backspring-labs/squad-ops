"""Schema tests for ``PlanAuthoringBrief`` (SIP-0093 PR 93.0)."""

from __future__ import annotations

import pytest

from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

VALID_BRIEF_YAML = """\
version: 1
brief_id: br_abc123
objective_summary: |
  Build a small FastAPI service exposing user CRUD with persistence
  via in-memory repository and a basic React frontend.
accepted_stack:
  language: python
  framework: fastapi
  persistence: in_memory_repository
must_cover_requirements:
  - "5 user CRUD endpoints"
  - "Duplicate-create returns 409"
scope_cuts:
  - "No real auth"
  - "No external persistence"
risk_areas:
  - "Concurrent create/delete races"
"""


def test_valid_brief_parses_round_trip():
    brief = PlanAuthoringBrief.from_yaml(VALID_BRIEF_YAML)

    assert brief.version == 1
    assert brief.brief_id == "br_abc123"
    assert brief.accepted_stack == {
        "language": "python",
        "framework": "fastapi",
        "persistence": "in_memory_repository",
    }
    assert brief.must_cover_requirements == [
        "5 user CRUD endpoints",
        "Duplicate-create returns 409",
    ]
    assert brief.scope_cuts == ["No real auth", "No external persistence"]
    assert brief.risk_areas == ["Concurrent create/delete races"]
    # Optional fields default to empty when absent.
    assert brief.source_artifact_refs == []
    assert brief.major_components == []
    assert brief.dependency_assumptions == []
    assert brief.time_budget_guidance == {}
    assert brief.task_granularity_guidance == ""
    assert brief.artifact_naming_conventions == []
    assert brief.open_questions == []


def test_optional_fields_round_trip_when_present():
    yaml_text = (
        VALID_BRIEF_YAML
        + """\
source_artifact_refs:
  - "context_research.md"
  - "test_strategy.md"
major_components:
  - "backend.api"
  - "frontend.shell"
dependency_assumptions:
  - "Frontend depends on backend API contract"
time_budget_guidance:
  framing_minutes: 15
  build_minutes: 120
task_granularity_guidance: "One file per task; prefer narrow focus."
artifact_naming_conventions:
  - "backend/*.py"
  - "frontend/src/*.tsx"
open_questions:
  - "Persistence layer for follow-on cycle?"
"""
    )

    brief = PlanAuthoringBrief.from_yaml(yaml_text)
    assert brief.source_artifact_refs == ["context_research.md", "test_strategy.md"]
    assert brief.major_components == ["backend.api", "frontend.shell"]
    assert brief.dependency_assumptions == ["Frontend depends on backend API contract"]
    assert brief.time_budget_guidance == {"framing_minutes": 15, "build_minutes": 120}
    assert brief.task_granularity_guidance == "One file per task; prefer narrow focus."
    assert brief.artifact_naming_conventions == ["backend/*.py", "frontend/src/*.tsx"]
    assert brief.open_questions == ["Persistence layer for follow-on cycle?"]


@pytest.mark.parametrize(
    "missing",
    [
        "version",
        "brief_id",
        "objective_summary",
        "accepted_stack",
        "must_cover_requirements",
        "scope_cuts",
        "risk_areas",
    ],
)
def test_missing_required_field_raises_with_field_name(missing):
    """Each required field, named in the error message when missing."""
    lines = VALID_BRIEF_YAML.splitlines()
    # Drop both the key line and any continuation lines (block scalars / lists).
    filtered: list[str] = []
    skipping = False
    for line in lines:
        if not skipping and line.startswith(f"{missing}:"):
            skipping = True
            continue
        if skipping:
            if not line or line.startswith(" ") or line.startswith("-"):
                continue
            skipping = False
        filtered.append(line)
    yaml_text = "\n".join(filtered) + "\n"

    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(yaml_text)
    assert missing in str(exc.value)


def test_malformed_yaml_raises():
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml("not: valid: yaml: : :")
    assert "Malformed brief YAML" in str(exc.value)


def test_top_level_non_mapping_rejected():
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml("- a\n- b\n")
    assert "must be a YAML mapping" in str(exc.value)


def test_version_must_be_int():
    bad = VALID_BRIEF_YAML.replace("version: 1", 'version: "1"')
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(bad)
    assert "version must be int" in str(exc.value)


def test_empty_brief_id_rejected():
    bad = VALID_BRIEF_YAML.replace("brief_id: br_abc123", 'brief_id: ""')
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(bad)
    assert "brief_id" in str(exc.value)


def test_empty_objective_summary_rejected():
    bad = VALID_BRIEF_YAML.replace(
        "objective_summary: |\n  Build a small FastAPI service exposing user CRUD with persistence\n  via in-memory repository and a basic React frontend.",
        'objective_summary: ""',
    )
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(bad)
    assert "objective_summary" in str(exc.value)


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("accepted_stack", "accepted_stack: not-a-mapping"),
        ("must_cover_requirements", "must_cover_requirements: not-a-list"),
        ("scope_cuts", "scope_cuts: not-a-list"),
        ("risk_areas", "risk_areas: not-a-list"),
    ],
)
def test_required_field_wrong_shape_rejected(field, replacement):
    """A required container field with the wrong YAML shape names the field
    in the error so authors can find what's broken."""
    # Replace the multi-line block with a single scalar line.
    lines = VALID_BRIEF_YAML.splitlines()
    out: list[str] = []
    skipping = False
    for line in lines:
        if not skipping and line.startswith(f"{field}:"):
            skipping = True
            out.append(replacement)
            continue
        if skipping:
            if not line or line.startswith(" ") or line.startswith("-"):
                continue
            skipping = False
        out.append(line)
    yaml_text = "\n".join(out) + "\n"

    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(yaml_text)
    assert field in str(exc.value)


def test_optional_list_with_wrong_shape_rejected():
    """Optional fields are lenient on absence but strict on type when present."""
    bad = VALID_BRIEF_YAML + "open_questions: not-a-list\n"
    with pytest.raises(ValueError) as exc:
        PlanAuthoringBrief.from_yaml(bad)
    assert "open_questions" in str(exc.value)


def test_must_cover_requirements_can_be_empty():
    """Edge case named in the plan doc: empty must_cover_requirements
    parses but the merger surfaces a warning. Parser stays permissive;
    the warning is the merger's job."""
    bad = VALID_BRIEF_YAML.replace(
        'must_cover_requirements:\n  - "5 user CRUD endpoints"\n  - "Duplicate-create returns 409"',
        "must_cover_requirements: []",
    )
    brief = PlanAuthoringBrief.from_yaml(bad)
    assert brief.must_cover_requirements == []
