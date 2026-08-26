"""Content pins for the qa.test task_type fragment (#877).

Roll 14 (cyc_25b4a9b0b637) died on a qa suite that fetched a live server, because
every guidance surface the author saw was stack-1-shaped: the fragment stated the
pytest discovery rule as universal and confined its no-live-server warning to jsdom
component tests. These tests pin the two properties the fix introduced — an
execution-environment rule that holds on every stack, and a discovery rule scoped
to the workspaces it is true of. A later edit that drops either re-opens the loss.
"""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_capabilities]

_FRAGMENT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "squadops"
    / "prompts"
    / "fragments"
    / "shared"
    / "task_type"
    / "task_type.qa.test.md"
).read_text(encoding="utf-8")


def test_the_execution_environment_rule_exists_and_covers_both_stacks():
    """The one sentence that would have prevented roll 14: no application server is
    running during test execution, on any stack — with the in-process alternative
    named for each stack, so the prohibition comes with a replacement strategy."""
    assert "## Execution Environment (hard rule)" in _FRAGMENT
    assert "No application server is\nrunning during test execution" in _FRAGMENT.replace("**", "")
    # stack #1's in-process client and stack #2's handler-import pattern
    assert "TestClient" in _FRAGMENT
    assert "from '@/app/api/runs/route'" in _FRAGMENT


def test_the_execution_rule_precedes_the_discovery_contract():
    """Strategy before naming: the author must learn how the suite executes before
    the file-naming rules — a suite named perfectly but fetching localhost still
    fails every test."""
    assert _FRAGMENT.index("## Execution Environment") < _FRAGMENT.index("## Discovery Contract")


def test_the_pytest_discovery_rule_is_scoped_to_python_workspaces():
    """The old fragment stated 'Backend tests MUST be Python pytest files' as a
    universal hard rule — nonsense on a single-tree TypeScript workspace, and
    contradicting the stack-2 supplement in the same prompt. The rule must be
    conditioned on the workspace shape, and the TypeScript branch must exist."""
    conditioned = _FRAGMENT.index("When the workspace declares Python dependency manifests")
    pytest_rule = _FRAGMENT.index("MUST be Python pytest files")
    assert conditioned < pytest_rule

    assert "single TypeScript application" in _FRAGMENT


class TestFillModeBriefInstructions:
    """#910 — the brief told the author two opposite things about the same slots."""

    @staticmethod
    def _brief() -> str:
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[3]
            / "src/squadops/prompts/request_templates/request.qa_test_fill_mode_appendix.md"
        ).read_text(encoding="utf-8")

    def test_the_slot_list_reads_as_an_instruction_not_a_prohibition(self):
        """Bug caught: the heading over the fill list says not to test these behaviors.

        It read "Already covered deterministically (do not re-test these behaviors
        mechanically)" over the exact eight slots the brief then demands be filled.
        Window roll 3 left all eight unfilled, rolls 1 and 2 left some — a correction
        round lost per roll to an instruction the author was following.
        """
        brief = self._brief()
        heading = brief.split("{{slot_lines}}")[0].rsplit("\n\n", 1)[-1]

        assert "do not re-test" not in heading.lower(), (
            "the heading immediately above the slot list must not tell the author to "
            "skip them — that is the instruction roll 3 obeyed"
        )
        assert "fill" in heading.lower()

    def test_the_error_envelope_is_carried_and_shown_in_a_worked_example(self):
        """Bug caught: the brief's only body example is a success field.

        Four of eight slots are error behaviors. With no error-path example and no
        envelope statement, the author invents the field name — `body.error_code` on two
        consecutive window rolls.
        """
        brief = self._brief()

        assert "{{error_envelope}}" in brief
        assert "body.error.code" in brief

    def test_every_declared_variable_is_actually_substituted(self):
        """Bug caught: a variable declared in the frontmatter but never rendered, or
        rendered but undeclared — either leaves a literal `{{...}}` in the prompt or an
        unfilled fact, and both reach the agent silently."""
        import re

        import yaml

        brief = self._brief()
        header = brief.split("---")[1]
        meta = yaml.safe_load(header)
        declared = set(meta.get("required_variables") or []) | set(
            meta.get("optional_variables") or []
        )
        used = set(re.findall(r"\{\{(\w+)\}\}", brief))

        assert used == declared, f"declared={sorted(declared)} used={sorted(used)}"


class TestFillsAreEmittedFirst:
    """1.6.5 A (#998 ask 2, ordering half). Bug caught: the brief says fills come first
    in *priority* but nothing about emission ORDER, so the author wrote the additive file
    first, hit the completion cap, and lost every fill (1.6.4 set, roll 6)."""

    _APPENDIX = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates/request.qa_test_fill_mode_appendix.md"
    )

    def test_the_order_rule_is_stated_and_precedes_the_additive_files_paragraph(self):
        text = self._APPENDIX.read_text()
        rule = text.index("**Order of emission: every fill block first, then any additive file.**")
        additive = text.index("The plan also asked for the file(s) below.")
        assert rule < additive
        assert "lands on an additive file" in text
