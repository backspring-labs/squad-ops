"""#933 — in fill mode the prompt must not state a competing deliverable.

The SIP-0104 window's blocker, and it was never a model failure. The focused qa prompt
rendered the plan's authored filename under "Expected Output Files" and closed with
*"Produce ONLY the files listed in Expected Output Files."* — then appended the fill
appendix **after** it. Two contradictory contracts in one prompt, the negating one more
emphatic and more specific.

Roll 6 (``cyc_5544c63d1f9c``) obeyed it exactly: one path-addressed file, zero fills,
8,192 completion tokens spent on the wrong deliverable, seven scaffold slots left
unfilled. Rolls 3 and 5 died the same way; every plan in the window authored a
whole-test-file deliverable, because the plan author cannot see that a scaffold will be
bound (the #866 context-completeness class).

Asserted on the rendered prompt rather than on the handler's internals: the defect was
only ever visible in the bytes the model received.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

pytestmark = [pytest.mark.domain_capabilities]

_SCAFFOLD = {
    "manifest": {"stack": "nextjs_ts", "slots": []},
    "files": [{"name": "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts", "content": "x"}],
}


def _inputs(*, fill_mode: bool) -> dict:
    """Roll 6's actual task, minus the parts the prompt does not read."""
    inputs = {
        "subtask_focus": "Write API integration tests for run management",
        "subtask_description": (
            "Create Vitest tests covering happy paths and error cases for create, list, "
            "join, leave, and duplicate prevention. Use direct fetch to /api/runs or the "
            "scaffold harness."
        ),
        "expected_artifacts": ["__tests__/runs.test.ts"],
        "acceptance_criteria": ["Tests run successfully with vitest."],
        "prd": "group run events",
    }
    if fill_mode:
        inputs["verification_scaffold"] = _SCAFFOLD
    return inputs


def test_fill_mode_does_not_order_the_author_to_produce_only_the_authored_file():
    """Bug caught: the prompt forbids the very thing the appendix asks for.

    "Produce ONLY the files listed in Expected Output Files" is the direct negation of
    fill mode. This is the exact string window roll 6 obeyed.
    """
    prompt = QATestHandler()._build_focused_prompt(_inputs(fill_mode=True))

    assert "Produce ONLY" not in prompt, (
        "fill mode still tells the author to produce only the authored file — this is "
        "the instruction that cost the window three rolls"
    )


def test_fill_mode_does_not_present_the_authored_file_as_an_expected_output():
    """Bug caught: a second deliverable is stated, even without the ONLY clause.

    A heading that says "Expected Output Files" competes with the slot table for what
    the job *is*. The appendix keeps the filename, framed as additive.
    """
    prompt = QATestHandler()._build_focused_prompt(_inputs(fill_mode=True))

    assert "Expected Output Files" not in prompt
    assert "__tests__/runs.test.ts" not in prompt, (
        "the authored filename still appears in the focused prompt; in fill mode it "
        "belongs only to the appendix, where it is marked additive"
    )


def test_the_non_fill_path_is_unchanged():
    """The tripwire. Both assertions above pass trivially against a prompt that stopped
    rendering deliverables at all, which would break every non-scaffolded stack."""
    prompt = QATestHandler()._build_focused_prompt(_inputs(fill_mode=False))

    assert "Expected Output Files" in prompt
    assert "__tests__/runs.test.ts" in prompt
    assert "Produce ONLY the files listed in Expected Output Files." in prompt


@pytest.mark.parametrize("fill_mode", [True, False])
def test_the_orthogonal_guards_survive_in_both_modes(fill_mode):
    """Bug caught: fixing the contradiction throws out the guards beside it.

    The fence-format instruction is how additive files are emitted, and the
    source-artifact guard has no equivalent in the appendix — dropping either while
    removing the ONLY clause trades one emission defect for another.
    """
    prompt = QATestHandler()._build_focused_prompt(_inputs(fill_mode=fill_mode))

    # #1272: the fence example names the task's OWN expected file now — the literal
    # `path/to/file` was copied verbatim by React roll 5 and cost a round. What this test
    # guards is that the instruction survives, not the placeholder it used to use.
    assert "fenced code blocks whose header carries the file's own path" in prompt
    assert "path/to/file" not in prompt
    assert "Do not reproduce source artifacts." in prompt
    # The concrete example is the non-fill path's alone: in fill mode the authored
    # filename belongs only to the appendix (the assertion two tests above).
    assert ("```typescript:__tests__/runs.test.ts```" in prompt) is (fill_mode is False)
