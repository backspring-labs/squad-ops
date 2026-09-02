"""#1255: the handoff document's required sections are a typed criterion every seam reads.

Replayed from the 1.7.1 React shakeout on the main-built deploy (``cyc_c6db3ffc1f4e``,
2026-09-02): the builder's first handoff stopped after ``## How to Run`` and the handler's
validation named the two missing sections; the round-0 repair carried every section, and
runtime-api discarded it as ``unverifiable / no_typed_criteria`` because the builder task
carried no typed criterion at all once #1252 stripped the plan's handoff regexes.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from squadops.capabilities.handlers.build_profiles import QA_HANDOFF_REQUIRED_SECTIONS
from squadops.cycles.acceptance_check_spec import CHECK_SECTIONS_PRESENT

pytestmark = [pytest.mark.domain_capabilities]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
ROUND_0 = "1-7-1-react-shakeout-3-qa_handoff-round-0.md"
REPAIR_00 = "1-7-1-react-shakeout-3-qa_handoff-repair-00.md"
SECTIONS = list(QA_HANDOFF_REQUIRED_SECTIONS)
MISSING_IN_ROUND_0 = ["## How to Test", "## Expected Behavior"]


def _stored(name: str) -> str:
    return (_REPLAYS / name).read_text(encoding="utf-8")


class TestOneRuleForTheSections:
    """The leaf is the rule the builder handler has always applied; the handler now reads
    it from there. Bug caught: the two seams drifting apart — a document the handler
    accepts that the criterion rejects, or the reverse."""

    def test_the_round_0_handoff_is_missing_the_two_sections_the_builder_named(self):
        from squadops.capabilities.handoff_sections import missing_sections

        assert missing_sections(_stored(ROUND_0), SECTIONS) == MISSING_IN_ROUND_0

    def test_the_repaired_handoff_carries_every_section_in_its_own_phrasing(self):
        from squadops.capabilities.handoff_sections import missing_sections

        assert "## How to Run the Backend" in _stored(REPAIR_00)
        assert missing_sections(_stored(REPAIR_00), SECTIONS) == []

    @pytest.mark.parametrize(
        "content,section",
        [
            ("## Running the service\n", "## How to Run"),
            ("### Testing\n", "## How to Test"),
            ("Expected output: 200 with the run id\n", "## Expected Behavior"),
            ("## HOW TO RUN\n", "## How to Run"),
        ],
    )
    def test_a_phrasing_from_the_keyword_table_counts_in_any_case(self, content, section):
        from squadops.capabilities.handoff_sections import section_present

        assert section_present(content, section)

    def test_a_section_outside_the_table_is_matched_by_its_own_text_only(self):
        from squadops.capabilities.handoff_sections import missing_sections

        assert missing_sections(
            "## Known Limitations\n", ["## Known Limitations", "## Build Results"]
        ) == ["## Build Results"]

    def test_the_builder_validation_names_the_same_sections(self):
        from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler

        profile = SimpleNamespace(required_files=("Dockerfile", "qa_handoff.md"))
        extracted = [
            {"filename": "Dockerfile", "content": "FROM python:3.12\n"},
            {"filename": "qa_handoff.md", "content": _stored(ROUND_0)},
        ]
        error = BuilderAssembleHandler._validate_builder_output(
            extracted, profile, QA_HANDOFF_REQUIRED_SECTIONS, task_required_files=None
        )
        assert error == f"qa_handoff.md missing required sections: {MISSING_IN_ROUND_0}"
        extracted[1]["content"] = _stored(REPAIR_00)
        assert (
            BuilderAssembleHandler._validate_builder_output(
                extracted, profile, QA_HANDOFF_REQUIRED_SECTIONS, task_required_files=None
            )
            is None
        )


class TestSectionsPresentEvaluator:
    """The criterion at the typed-acceptance seam, replayed on both stored documents."""

    async def _run(self, tmp_path, fixture: str | None, sections: list[str]):
        from squadops.cycles.acceptance_checks import SectionsPresentCheck

        rel = "qa_handoff.md"
        if fixture is not None:
            (tmp_path / rel).write_text(_stored(fixture), encoding="utf-8")
        return await SectionsPresentCheck().evaluate({"file": rel, "sections": sections}, tmp_path)

    async def test_the_round_0_handoff_fails_naming_the_missing_sections(self, tmp_path):
        outcome = await self._run(tmp_path, ROUND_0, SECTIONS)
        assert outcome.status == "failed"
        assert outcome.reason == "missing section(s): ## How to Test, ## Expected Behavior"
        assert outcome.actual["missing"] == MISSING_IN_ROUND_0

    async def test_the_repaired_handoff_passes(self, tmp_path):
        outcome = await self._run(tmp_path, REPAIR_00, SECTIONS)
        assert outcome.status == "passed"
        assert outcome.actual["missing"] == []

    async def test_a_missing_document_fails_and_no_sections_skips(self, tmp_path):
        absent = await self._run(tmp_path, None, SECTIONS)
        assert (absent.status, absent.reason) == ("failed", "file_not_found")
        vacuous = await self._run(tmp_path, REPAIR_00, [])
        assert (vacuous.status, vacuous.reason) == ("skipped", "no_sections_declared")

    def test_the_check_applies_to_markdown_only(self):
        from squadops.cycles.acceptance_check_spec import is_check_applicable

        assert is_check_applicable(CHECK_SECTIONS_PRESENT, "qa_handoff.md")
        assert not is_check_applicable(CHECK_SECTIONS_PRESENT, "backend/tests/test_runs.py")


class TestHandoffSectionInjection:
    """The framework binds the criterion onto the builder task that owns the handoff, with
    the profile's sections as params — and onto nothing else. Bug caught: a builder task
    dispatched with no typed criterion over its own document (the shakeout's shape), or
    the rule leaking onto dev/qa tasks that never write it."""

    def test_the_builder_task_owning_the_handoff_gets_the_profile_sections(self):
        from squadops.cycles.task_plan import _handoff_section_criteria

        task = SimpleNamespace(expected_artifacts=["Dockerfile", "qa_handoff.md"])
        checks = _handoff_section_criteria("builder.assemble", task)
        assert [c.id for c in checks] == ["handoff-sections:qa_handoff.md"]
        assert checks[0].check == CHECK_SECTIONS_PRESENT
        assert checks[0].params == {"file": "qa_handoff.md", "sections": SECTIONS}
        assert checks[0].severity == "error"

    def test_a_nested_handoff_path_is_bound_by_its_own_path(self):
        from squadops.cycles.task_plan import _handoff_section_criteria

        task = SimpleNamespace(expected_artifacts=["docs/qa_handoff.md"])
        checks = _handoff_section_criteria("builder.assemble", task)
        assert [c.params["file"] for c in checks] == ["docs/qa_handoff.md"]

    @pytest.mark.parametrize(
        "task_type,artifacts",
        [
            ("builder.assemble", ["Dockerfile"]),
            ("development.develop", ["qa_handoff.md"]),
            ("qa.test", ["qa_handoff.md", "backend/tests/test_runs.py"]),
        ],
    )
    def test_nothing_binds_elsewhere(self, task_type, artifacts):
        from squadops.cycles.task_plan import _handoff_section_criteria

        assert (
            _handoff_section_criteria(task_type, SimpleNamespace(expected_artifacts=artifacts))
            == []
        )


class TestTheVerifierCanDecideTheBuilderRepair:
    """runtime-api holds the same row the builder evaluated, so the round-0 repair is
    decided instead of discarded. Bug caught: the shakeout's verdict — ``unverifiable /
    no_typed_criteria`` on a repair that fixed exactly what the handler named."""

    def _criterion(self):
        from squadops.cycles.task_plan import _handoff_section_criteria

        task = SimpleNamespace(expected_artifacts=["Dockerfile", "qa_handoff.md"])
        return list(_handoff_section_criteria("builder.assemble", task))

    async def test_the_repaired_handoff_is_accepted_and_the_short_one_rejected(self):
        from squadops.cycles.patch_verification import (
            PATCH_FAILED,
            PATCH_PASSED,
            verify_patched_artifacts,
        )

        accepted = await verify_patched_artifacts(
            self._criterion(), [{"name": "qa_handoff.md", "content": _stored(REPAIR_00)}]
        )
        assert accepted.status == PATCH_PASSED
        assert [r.check for r in accepted.checks] == [CHECK_SECTIONS_PRESENT]
        rejected = await verify_patched_artifacts(
            self._criterion(), [{"name": "qa_handoff.md", "content": _stored(ROUND_0)}]
        )
        assert rejected.status == PATCH_FAILED
        assert (
            rejected.checks[0].reason == "missing section(s): ## How to Test, ## Expected Behavior"
        )

    async def test_a_task_with_no_criteria_still_reports_the_rows_the_agent_executed(self):
        from squadops.cycles.patch_verification import (
            PATCH_UNVERIFIABLE,
            REASON_NO_TYPED_CRITERIA,
            verify_patched_artifacts,
        )

        verdict = await verify_patched_artifacts(
            [],
            [{"name": "Dockerfile", "content": "FROM node:20-alpine\nRUN npm ci\n"}],
            agent_checks={
                "environment": "agent:builder",
                "checks": [
                    {
                        "check": "acceptance:container_packaging",
                        "status": "failed",
                        "severity": "warning",
                        "reason": "1 packaging finding(s): npm_ci_without_lockfile",
                    }
                ],
            },
        )
        assert (verdict.status, verdict.reason) == (PATCH_UNVERIFIABLE, REASON_NO_TYPED_CRITERIA)
        assert [(r.check, r.status, r.executed_in) for r in verdict.checks] == [
            ("container_packaging", "failed", "agent:builder")
        ]
