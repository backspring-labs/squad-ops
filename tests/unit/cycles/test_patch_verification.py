"""Unit tests for executor-side patch verification (#389).

Each test names the bug it catches: the correction loop re-dispatching a
generative task after a good repair (re-roll clobbers the patch), or the
verifier accepting a patch without positive executed evidence.
"""

from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.patch_verification import (
    PATCH_FAILED,
    PATCH_PASSED,
    PATCH_UNVERIFIABLE,
    overlay_artifacts,
    verify_patched_artifacts,
)

# The field-evidence contract from cyc_6841d75f167c: qa_handoff.md must
# contain five headings; the broken generation misses two, the repair
# restores them.
BROKEN_DOC = "# QA Handoff\n## How to Run\n## Expected Behavior\n"
REPAIRED_DOC = (
    "# QA Handoff\n## How to Run\n## How to Test\n## Expected Behavior\n"
    "## Implemented Scope\n## Known Limitations\n"
)


def _heading_criteria() -> list[TypedCheck]:
    return [
        TypedCheck(
            check="regex_match",
            params={"file": "qa_handoff.md", "pattern": f"## {section}"},
            severity="error",
            description=f"Contains {section} section",
        )
        for section in ("How to Run", "How to Test", "Implemented Scope")
    ]


class TestVerifyPatchedArtifacts:
    async def test_passed_when_repair_satisfies_blocking_criteria(self):
        """Bug caught: a good repair re-dispatched into a re-roll (the #389
        oscillation) because no path existed to verify it behaviorally."""
        artifacts = overlay_artifacts(
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        result = await verify_patched_artifacts(_heading_criteria(), artifacts)
        assert result.status == PATCH_PASSED
        assert all(r.status == "passed" for r in result.checks)

    async def test_failed_when_repair_still_misses_required_section(self):
        """Bug caught: false-accepting an incomplete repair (broken doc kept)."""
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
        )
        assert result.status == PATCH_FAILED
        failed = [r for r in result.checks if r.status == "failed"]
        assert {r.description for r in failed} == {
            "Contains How to Test section",
            "Contains Implemented Scope section",
        }

    async def test_overlay_patch_supersedes_base_artifact(self):
        """Bug caught: overlay precedence inverted — verification would run
        against the broken original and every good repair would read FAILED."""
        merged = overlay_artifacts(
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}, {"name": "a.txt", "content": "x"}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}, {"name": "b.txt", "content": "y"}],
        )
        by_name = {a["name"]: a["content"] for a in merged}
        assert by_name["qa_handoff.md"] == REPAIRED_DOC
        assert set(by_name) == {"qa_handoff.md", "a.txt", "b.txt"}

    async def test_unverifiable_when_no_typed_criteria(self):
        """Bug caught: a prose-only contract silently 'passing' with zero
        behavioral evidence — patch acceptance requires executed checks."""
        result = await verify_patched_artifacts(
            ["backend responds correctly"],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_typed_criteria"

    async def test_unverifiable_when_all_blocking_checks_skipped(self):
        """Bug caught: typed acceptance disabled → every row skipped → the
        old logic would have accepted the patch with nothing executed."""
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
            typed_acceptance_enabled=False,
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_executed_blocking_checks"

    async def test_unverifiable_on_unparseable_dict_criterion(self):
        """Bug caught: verifying against only the intelligible subset of a
        contract — an unknown check name must force fallback, not be skipped."""
        result = await verify_patched_artifacts(
            [{"check": "not_a_real_check", "file": "qa_handoff.md"}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "unparseable_criteria"

    async def test_dict_form_criteria_are_parsed_and_evaluated(self):
        """Bug caught: criteria arriving as dicts (deserialized envelope)
        being ignored — the fix would silently never engage."""
        result = await verify_patched_artifacts(
            [
                {
                    "check": "regex_match",
                    "file": "qa_handoff.md",
                    "pattern": "## Known Limitations",
                    "description": "Contains Known Limitations section",
                }
            ],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_PASSED

    async def test_warning_severity_failure_does_not_block(self):
        """Bug caught: RC-9 regression — a warning-severity miss blocking
        patch acceptance that error-severity evidence already justified."""
        criteria = [
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                severity="error",
                description="required section",
            ),
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## Nonexistent Nicety"},
                severity="warning",
                description="optional section",
            ),
        ]
        result = await verify_patched_artifacts(
            criteria, [{"name": "qa_handoff.md", "content": REPAIRED_DOC}]
        )
        assert result.status == PATCH_PASSED
        warning_row = next(r for r in result.checks if r.severity == "warning")
        assert warning_row.status == "failed"

    async def test_check_rows_render_for_ledger_normalization(self):
        """Bug caught: patch-verified evidence emitted in a shape
        normalize_task_checks can't read → the ledger would show the task
        as never re-verified (§6.1 keys on 'check' + 'status')."""
        result = await verify_patched_artifacts(
            _heading_criteria()[:1],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        row = result.checks[0].to_check_row()
        assert row["check"] == "acceptance:regex_match"
        assert row["status"] == "passed"
        assert row["passed"] is True
        assert row["patch_verified"] is True


# --------------------------------------------------------------------------- #
# repair path rebase (#507) — bug caught: every roll-4 repair emitted
# app/routes.py while checks target backend/routes.py; the overlay appended it
# as net-new, typed verification ran on the un-patched original, and three
# QA-validated repairs were discarded by re-dispatch until the time budget.
# --------------------------------------------------------------------------- #

from squadops.cycles.patch_verification import rebase_artifact_paths  # noqa: E402


def test_wrong_directory_repair_is_rehomed_to_expected_path():
    arts = [{"name": "app/routes.py", "content": "fixed"}]
    out = rebase_artifact_paths(arts, ["backend/routes.py", "backend/models.py"])
    assert out == [{"name": "backend/routes.py", "content": "fixed"}]


def test_rehomed_repair_supersedes_in_overlay():
    base = [{"name": "backend/routes.py", "content": "broken"}]
    patches = rebase_artifact_paths(
        [{"name": "app/routes.py", "content": "fixed"}], ["backend/routes.py"]
    )
    merged = {a["name"]: a["content"] for a in overlay_artifacts(base, patches)}
    assert merged == {"backend/routes.py": "fixed"}


def test_exact_expected_path_passes_through():
    arts = [{"name": "backend/routes.py", "content": "x"}]
    assert rebase_artifact_paths(arts, ["backend/routes.py"]) == arts


def test_ambiguous_basename_is_never_rehomed():
    arts = [{"name": "app/routes.py", "content": "x"}]
    out = rebase_artifact_paths(arts, ["backend/routes.py", "frontend/routes.py"])
    assert out[0]["name"] == "app/routes.py"


def test_unmatched_and_net_new_files_pass_through():
    arts = [{"name": "README.md", "content": "x"}, {"name": "", "content": "y"}, {"other": 1}]
    assert rebase_artifact_paths(arts, ["backend/routes.py"]) == arts
