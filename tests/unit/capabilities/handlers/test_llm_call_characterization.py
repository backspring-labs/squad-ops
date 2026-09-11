"""Every LLM call seam, characterized before #929 extracts the sequence.

#929 collapses the ~10-line sequence wrapped around each ``chat_stream_with_usage``
call — call, read ``.content``, inject a declared fault, log the emission shape,
measure the duration, record the generation — into one method on
``_CycleTaskHandler``. #1206 is the measured cost of not having done it: ten of the
seventeen sites record no generation at all, so LangFuse held 26 of the 35 calls the
2026-08-31 shakeout pair actually made and said nothing about being partial.

These tests exist to make that refactor's diff readable. They pin, per seam:

* the **messages** the handler hands the port — role and content, in order;
* the **kwargs** it hands the port alongside them;
* how many **generations** it records, and under which prompt-layer identity;
* what the handler **returns**, so a seam moved into the shared method is proved
  to still drive its own parsing and failure handling.

The first, second and fourth are invariants: the extraction must not change one
byte of what reaches the model or one field of what comes back — every assertion of
those three was written against the pre-extraction code and has not moved since. The
third is the thing #1206 changes, and the count assertions are the diff: they were
written as ten zeros against the old code, and this commit turns them into ones.
Read the two commits together; that pair is the evidence, not either alone.

Bug caught: an extraction that quietly re-prompts. Nothing downstream would notice
a system message dropped from a re-ask, a ``reasoning`` kwarg lost on the self-eval
pass, or a record grouped under a different layer set — the cycle would still
complete, and the damage would only be visible months later in a LangFuse query
nobody thought to re-run.
"""

from __future__ import annotations

import json
from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.capabilities.handlers._plan_authoring_service import produce_plan
from squadops.capabilities.handlers.cycle_tasks import (
    BuilderAssembleHandler,
    DevelopmentDevelopHandler,
    GovernanceReviewHandler,
    QATestHandler,
    StrategyAnalyzeHandler,
)
from squadops.capabilities.handlers.impl.analyze_failure import DataAnalyzeFailureHandler
from squadops.capabilities.handlers.impl.correction_decision import (
    GovernanceCorrectionDecisionHandler,
)
from squadops.capabilities.handlers.impl.define_done import GovernanceDefineDoneHandler
from squadops.capabilities.handlers.planning_tasks import (
    DataResearchContextHandler,
    GovernanceMergePlanHandler,
    GovernancePreparePlanAuthoringBriefHandler,
    GovernanceReviewPlanHandler,
)
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.cycles.task_outcome import FailureClassification, TaskOutcome
from squadops.llm.models import ChatMessage
from squadops.telemetry.models import CorrelationContext

pytestmark = [pytest.mark.domain_capabilities]

_RUN_TESTS = "squadops.capabilities.handlers.test_runner.run_generated_tests"
_TESTS_PASSED = RunTestsResult(
    executed=True, exit_code=0, stdout="1 passed", stderr="", test_file_count=1, source_file_count=1
)


# ---------------------------------------------------------------------------
# The recording harness
# ---------------------------------------------------------------------------


def _response(content: str) -> ChatMessage:
    """A response carrying the full usage surface, so a record that drops a field shows.

    Every figure is distinct and non-round: a record built from the wrong attribute
    reads as a wrong number here rather than as a plausible one.
    """
    return ChatMessage(
        role="assistant",
        content=content,
        prompt_tokens=1201,
        completion_tokens=803,
        total_tokens=2004,
        tokens_per_second=11.5,
        reasoning_tokens=97,
        reasoning_text="deliberating",
    )


class Seam:
    """What one handler run did at the LLM port and the observability port."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[ChatMessage], dict]] = []
        self.records: list[tuple] = []

    @property
    def transcripts(self) -> list[list[tuple[str, str]]]:
        """Each call's messages as (role, content) pairs."""
        return [[(m.role, m.content) for m in msgs] for msgs, _ in self.calls]

    @property
    def kwargs(self) -> list[dict]:
        return [kw for _, kw in self.calls]

    @property
    def layer_sets(self) -> list[str]:
        return [layers.prompt_layer_set_id for _, layers in self.records]


def _context(*responses: str, renderer=None) -> tuple[MagicMock, Seam]:
    """A context whose LLM port captures every call and whose observability port
    captures every generation recorded.

    ``correlation_context`` is set deliberately. Every other handler fixture in this
    suite leaves it ``None``, which gates recording off entirely — a record-count
    assertion written against one of those would read zero everywhere and prove
    nothing about the gap #1206 measured.
    """
    seam = Seam()
    queued = [_response(r) for r in responses]

    ctx = MagicMock()
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt.return_value = assembled
    ctx.ports.prompt_service.assemble.return_value = assembled
    ctx.ports.prompt_service.assemble_task_only.return_value = assembled
    ctx.ports.request_renderer = renderer
    ctx.ports.llm.default_model = "test-model"

    async def _capture(messages, **kwargs):
        seam.calls.append((list(messages), dict(kwargs)))
        if not queued:
            raise AssertionError(f"handler made {len(seam.calls)} LLM calls; fewer were seeded")
        return queued.pop(0)

    ctx.ports.llm.chat_stream_with_usage = _capture
    ctx.ports.llm.chat = _capture

    ctx.ports.llm_observability.record_generation = lambda corr, record, layers: (
        seam.records.append((record, layers))
    )
    ctx.correlation_context = CorrelationContext(
        cycle_id="cyc_test", task_id="task_1", trace_id="trace-1", agent_id="a", agent_role="r"
    )
    ctx.task_id = "task_1"
    ctx.project_id = "group_run"
    ctx.cycle_id = "cyc_test"
    return ctx, seam


def _renderer(content: str, template_id: str = "request.tmpl", version: str = "3"):
    r = AsyncMock()
    rendered = MagicMock()
    rendered.content = content
    rendered.template_id = template_id
    rendered.template_version = version
    rendered.render_hash = "rh"
    r.render.return_value = rendered
    return r


# ---------------------------------------------------------------------------
# A. The six primaries that already record
# ---------------------------------------------------------------------------


class TestPrimariesThatAlreadyRecord:
    """Six seams whose sequence is complete today. The extraction must leave every
    one of them byte-identical — these are the copies being collapsed, so a
    divergence introduced here would be invisible against the sites it was copied
    from."""

    async def test_the_generic_cycle_path_sends_two_messages_and_records_one_generation(self):
        """``_CycleTaskHandler.handle`` — the inline record block, used by every
        handler that does not override ``handle``. Its layer set is the one #929
        names as the data decision: ``{role}-cycle``, not ``{role}-{kind}``."""
        ctx, seam = _context("Strategy body")

        result = await StrategyAnalyzeHandler().handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        assert [r for r, _ in seam.transcripts[0]] == ["system", "user"]
        assert seam.transcripts[0][0][1] == "System prompt"
        assert "Build a widget" in seam.transcripts[0][1][1]
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["strat-cycle"]
        record, layers = seam.records[0]
        assert record.completion_tokens == 803
        assert record.total_tokens == 2004
        assert record.tokens_per_second == 11.5
        assert record.reasoning_text == "deliberating"
        assert record.response_text == "Strategy body"
        assert record.attempt is None
        assert [(x.layer_type, x.layer_id) for x in layers.layers] == [
            ("system", "strat-system"),
            ("user", "cycle-strategy.analyze_prd"),
        ]

    async def test_develop_records_under_its_prompt_layer_kind(self):
        """``develop`` routes through ``_record_generation``, whose layer set is
        derived from ``_prompt_layer_kind`` — ``dev-build``, not ``dev-cycle``.
        The two identities coexisting is #929's stated reason for the extraction."""
        ctx, seam = _context("```python:app.py\nprint('x')\n```\n")

        result = await DevelopmentDevelopHandler().handle(
            ctx, {"prd": "Build a CLI", "artifact_contents": {}}
        )

        assert result.success is True
        assert result.outputs["artifacts"][0]["name"] == "app.py"
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["dev-build"]
        record, _ = seam.records[0]
        assert record.model == "test-model"
        assert record.prompt_text == seam.transcripts[0][1][1]
        assert record.prompt_tokens == 1201

    @patch(_RUN_TESTS, return_value=_TESTS_PASSED)
    async def test_qa_test_records_under_its_prompt_layer_kind(self, _run):
        ctx, seam = _context("```python:tests/test_main.py\ndef test_x():\n    assert True\n```\n")

        result = await QATestHandler().handle(
            ctx, {"prd": "Build a CLI", "artifact_contents": {"src/main.py": "def main(): ..."}}
        )

        assert result.success is True
        assert len(seam.calls) == 1
        assert seam.layer_sets == ["qa-build"]
        assert seam.records[0][0].prompt_text == seam.transcripts[0][1][1]

    async def test_builder_records_under_the_assemble_kind_it_overrides(self):
        """``BuilderAssembleHandler`` is the one handler that overrides
        ``_prompt_layer_kind``. A shared method that derived the kind itself
        rather than reading the attribute would silently re-group these."""
        ctx, seam = _context("```dockerfile:Dockerfile\nFROM python:3.12\n```\n")

        result = await BuilderAssembleHandler().handle(
            ctx,
            {
                "prd": "Package it",
                "artifact_contents": {"src/main.py": "def main(): ..."},
                "resolved_config": {"build_profile": "python_cli_builder"},
            },
        )

        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["builder-assemble"]
        assert result.outputs["artifacts"][0]["name"] == "Dockerfile"

    async def test_governance_records_the_token_accounting_it_once_dropped(self):
        """The third copy, deleted in #938. ``implementation_plan: True`` is
        load-bearing — the other setting delegates to the base handler, whose own
        inline block records everything, so the assertion would pass against the
        defect."""
        ctx, seam = _context("Review body")

        await GovernanceReviewHandler().handle(
            ctx, {"prd": "build a thing", "resolved_config": {"implementation_plan": False}}
        )

        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.records[0][0].completion_tokens == 803

    async def test_the_planning_path_has_its_own_inline_record_block(self):
        """``planning/base.py`` carries a second inline copy of the record block,
        with a third layer identity (``{role}-planning``). It is the reason #929
        says planning "can take the same treatment or share a mixin"."""
        ctx, seam = _context("## Research context\n\nFindings.")

        result = await DataResearchContextHandler().handle(ctx, {"prd": "Build a widget"})

        assert result.success is True
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["data-planning"]
        _, layers = seam.records[0]
        assert [(x.layer_type, x.layer_id) for x in layers.layers] == [
            ("system", "data-planning-system"),
            ("user", "planning-data.research_context"),
        ]


# ---------------------------------------------------------------------------
# B. The three dark primaries — #1206's "record nothing at all"
# ---------------------------------------------------------------------------


class TestPrimariesThatWereDark:
    """Three impl handlers made an LLM call and recorded nothing. Two of the three
    are declared ``ReasoningLevel.HIGH`` — the most expensive thinking in the cycle,
    and none of it was visible in LangFuse.

    Their new records use the layer identity ``_record_generation`` derives from
    ``_prompt_layer_kind``, which is the base default ``"build"`` for all three. That
    is a *chosen* value, not a preserved one: these generations had no prompt-layer
    identity to preserve, because they had no records. Nothing existing re-groups."""

    async def test_define_done_calls_the_model_and_records_what_it_spent(self):
        contract = {
            "objective": "Build CLI tool",
            "acceptance_criteria": ["Passes tests"],
            "non_goals": ["UI"],
            "time_budget_seconds": 3600,
            "stop_conditions": ["3 consecutive failures"],
            "required_artifacts": ["main.py"],
        }
        ctx, seam = _context(json.dumps(contract))

        result = await GovernanceDefineDoneHandler().handle(ctx, {"prd": "Build a CLI tool"})

        assert result.success is True
        assert result.outputs["contract"]["objective"] == "Build CLI tool"
        assert len(seam.calls) == 1
        assert [r for r, _ in seam.transcripts[0]] == ["system", "user"]
        assert len(seam.records) == 1
        record, layers = seam.records[0]
        assert record.completion_tokens == 803
        assert record.reasoning_text == "deliberating"
        assert record.attempt is None, "a first attempt does not claim to be a retry"
        assert layers.prompt_layer_set_id == "lead-build"

    async def test_analyze_failure_calls_the_model_and_records_what_it_spent(self):
        analysis = {
            "classification": FailureClassification.WORK_PRODUCT,
            "analysis_summary": "Output quality below bar",
            "contributing_factors": ["insufficient context"],
        }
        ctx, seam = _context(json.dumps(analysis))

        result = await DataAnalyzeFailureHandler().handle(
            ctx, {"prd": "test", "failure_evidence": {"error": "bad output"}}
        )

        assert result.success is True
        assert result.outputs["classification"] == FailureClassification.WORK_PRODUCT
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["data-build"]
        assert seam.records[0][0].completion_tokens == 803

    async def test_correction_decision_calls_the_model_and_records_what_it_spent(self):
        decision = {
            "correction_path": "patch",
            "decision_rationale": "Local fix suffices",
            "affected_task_types": ["development.develop"],
        }
        ctx, seam = _context(json.dumps(decision))

        result = await GovernanceCorrectionDecisionHandler().handle(
            ctx, {"prd": "test", "failure_analysis": {"classification": "execution"}}
        )

        assert result.success is True
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        assert seam.layer_sets == ["lead-build"]


# ---------------------------------------------------------------------------
# C. The second calls — re-asks and retries
# ---------------------------------------------------------------------------


class TestSecondCallsAreDistinctPrompts:
    """A second call is not a copy of the first: it carries the first response as an
    assistant turn plus corrective feedback. #1206 asks for these to be recorded
    "with the attempt/outcome fields the record already carries so a retry is
    distinguishable from a first attempt", and they were recorded not at all.

    ``attempt=2`` is what makes the pair readable. Without it two generations arrive
    under the same layer set with no ordering, and the retry is indistinguishable from
    a handler that happened to run twice."""

    async def test_the_json_reask_replays_the_transcript_with_feedback(self):
        """#1008: the model stopped mid-object once and the whole correction chain
        ran decisionless. The re-ask is one re-ask, and it must carry the truncated
        emission back as the assistant turn — a re-ask that dropped it would be a
        blind re-roll of the same prompt."""
        truncated = '{"classification": "work_product", "analysis_summary": "The check'
        complete = json.dumps(
            {
                "classification": FailureClassification.WORK_PRODUCT,
                "analysis_summary": "Named import of a default export",
                "contributing_factors": ["TS2614"],
            }
        )
        ctx, seam = _context(truncated, complete)

        result = await DataAnalyzeFailureHandler().handle(
            ctx, {"prd": "test", "failure_evidence": {"e": "x"}}
        )

        assert result.success is True
        assert result.outputs["analysis_summary"] == "Named import of a default export"
        assert len(seam.calls) == 2
        first, second = seam.transcripts
        assert [r for r, _ in second] == ["system", "user", "assistant", "user"]
        assert second[:2] == first
        assert second[2][1] == truncated
        assert seam.kwargs[1] == seam.kwargs[0], "the re-ask must use the same model kwargs"
        assert len(seam.records) == 2
        assert [r.attempt for r, _ in seam.records] == [None, 2]
        assert seam.records[1][0].prompt_text == second[3][1], (
            "the retry records the feedback it was sent, not the original prompt"
        )
        assert seam.records[1][0].response_text == complete

    async def test_define_done_reask_replays_the_transcript_with_feedback(self):
        truncated = '{"objective": "Build CLI", "acceptance_criteria": ["Pas'
        complete = json.dumps(
            {
                "objective": "Build CLI tool",
                "acceptance_criteria": ["Passes tests"],
                "non_goals": [],
                "time_budget_seconds": 3600,
                "stop_conditions": [],
                "required_artifacts": ["main.py"],
            }
        )
        ctx, seam = _context(truncated, complete)

        result = await GovernanceDefineDoneHandler().handle(ctx, {"prd": "Build a CLI tool"})

        assert result.success is True
        assert len(seam.calls) == 2
        assert [r for r, _ in seam.transcripts[1]] == ["system", "user", "assistant", "user"]
        assert seam.transcripts[1][2][1] == truncated
        assert [r.attempt for r, _ in seam.records] == [None, 2]

    async def test_correction_decision_reask_replays_the_transcript_with_feedback(self):
        truncated = '{"correction_path": "pat'
        complete = json.dumps(
            {
                "correction_path": "patch",
                "decision_rationale": "Local fix suffices",
                "affected_task_types": ["development.develop"],
            }
        )
        ctx, seam = _context(truncated, complete)

        result = await GovernanceCorrectionDecisionHandler().handle(
            ctx, {"prd": "test", "failure_analysis": {"classification": "execution"}}
        )

        assert result.success is True
        assert len(seam.calls) == 2
        assert [r for r, _ in seam.transcripts[1]] == ["system", "user", "assistant", "user"]
        assert [r.attempt for r, _ in seam.records] == [None, 2]

    async def test_the_frontmatter_retry_is_a_second_call_no_test_had_driven(self):
        """#109: a plan review that omits frontmatter is re-prompted once rather
        than having a default ``readiness=revise`` synthesized for it. The retry
        makes a second LLM call and logs its emission under its own label — and no
        test drove it at all before this one.

        Its latency is measured from the retry's own clock rather than the primary's:
        the primary belongs to ``super().handle()`` and is already spent, so a retry
        billed against it would report a duration it did not take."""
        ctx, seam = _context(
            "no frontmatter here, just prose",
            "---\nreadiness: go\nsufficiency_score: 4\n---\n\nThe plan is sound.",
        )

        result = await GovernanceReviewPlanHandler().handle(
            ctx, {"prd": "Build a widget", "resolved_config": {"implementation_plan": False}}
        )

        assert result.success is True
        assert len(seam.calls) == 2
        assert [r for r, _ in seam.transcripts[1]] == ["system", "user", "assistant", "user"]
        assert seam.transcripts[1][2][1] == "no frontmatter here, just prose"
        assert "YAML frontmatter" in seam.transcripts[1][3][1]
        assert len(seam.records) == 2
        assert seam.layer_sets == ["lead-planning", "lead-planning"]
        assert [r.attempt for r, _ in seam.records] == [None, 2]


# ---------------------------------------------------------------------------
# D. The self-eval second calls
# ---------------------------------------------------------------------------


class TestSelfEvalSecondCalls:
    """``develop`` and ``qa_test`` each make a second call whose emission can
    overwrite the first's artifacts. #928's own docstring names them as the
    interesting pair; #1206 found both left out of generation recording, which is
    why ``gens_per_task`` read exactly 1.00 on every cycle measured — an invariant
    that was the second call being dropped every time. It reads 2.00 here now."""

    async def test_develop_self_eval_sends_a_four_message_transcript_and_records_it(self):
        ctx, seam = _context(
            "```python:wrong.py\nx = 1\n```",
            "```python:models.py\nclass RunEvent: pass\n```",
        )

        result = await DevelopmentDevelopHandler().handle(
            ctx,
            {
                "prd": "Build models",
                "subtask_focus": "Backend models",
                "expected_artifacts": ["models.py"],
                "acceptance_criteria": [],
                "artifact_contents": {},
                "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
            },
        )

        assert result.success is True
        names = [a["name"] for a in result.outputs["artifacts"]]
        assert "models.py" in names and "wrong.py" in names
        assert len(seam.calls) == 2
        first, second = seam.transcripts
        assert [r for r, _ in second] == ["system", "user", "assistant", "user"]
        assert second[:2] == first
        assert second[2][1] == "```python:wrong.py\nx = 1\n```"
        assert seam.kwargs[1] == seam.kwargs[0]
        assert len(seam.records) == 2
        assert [r.attempt for r, _ in seam.records] == [None, 2]
        assert seam.records[1][0].response_text == "```python:models.py\nclass RunEvent: pass\n```"

    @patch(_RUN_TESTS, return_value=_TESTS_PASSED)
    async def test_qa_self_eval_sends_a_four_message_transcript_and_records_it(self, _run):
        ctx, seam = _context(
            "```python:tests/test_wrong.py\ndef test_a():\n    assert True\n```",
            "```python:tests/test_main.py\ndef test_b():\n    assert True\n```",
        )

        result = await QATestHandler().handle(
            ctx,
            {
                "prd": "Build a CLI",
                "subtask_focus": "cover main",
                "expected_artifacts": ["tests/test_main.py"],
                "acceptance_criteria": [],
                "artifact_contents": {"src/main.py": "def main(): ..."},
                "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
            },
        )

        assert result.success is True
        assert len(seam.calls) == 2
        assert [r for r, _ in seam.transcripts[1]] == ["system", "user", "assistant", "user"]
        assert seam.kwargs[1] == seam.kwargs[0]
        assert [r.attempt for r, _ in seam.records] == [None, 2]


# ---------------------------------------------------------------------------
# E. The two function-owned loops
# ---------------------------------------------------------------------------


class TestFunctionOwnedLoops:
    """Two seams live in module-level functions rather than on a handler:
    ``retry_yaml_call`` (the brief and proposer loops) and ``produce_plan`` (the
    sole-author manifest loop). They are why the extraction cannot be a method call
    and nothing else — each takes the sequence in as a bound callable rather than
    reaching for the port, which is what left one of them recording nothing."""

    async def test_the_yaml_retry_loop_records_the_attempt_it_is_on(self):
        brief_yaml = (
            "version: 1\n"
            "brief_id: br_seeded_001\n"
            "objective_summary: |\n"
            "  Build a small FastAPI service.\n"
            "accepted_stack:\n"
            "  language: python\n"
            "  framework: fastapi\n"
            "must_cover_requirements:\n"
            '  - "5 user CRUD endpoints"\n'
            "scope_cuts:\n"
            '  - "No real auth"\n'
            "risk_areas:\n"
            '  - "Concurrent create/delete races"\n'
        )
        ctx, seam = _context(
            f"Here's the brief.\n\n```yaml:plan_authoring_brief.yaml\n{brief_yaml}```\n"
        )

        result = await GovernancePreparePlanAuthoringBriefHandler().handle(
            ctx,
            {
                "prd": "Build a simple user-CRUD API",
                "profile_roles": ["lead", "dev", "qa"],
                "prior_outputs": {"data": "context", "strat": "objective frame"},
            },
        )

        assert result.success is True
        assert len(seam.calls) == 1
        assert [r for r, _ in seam.transcripts[0]] == ["system", "user"]
        assert len(seam.records) == 1
        record, layers = seam.records[0]
        # This loop numbers from 1 rather than leaving the first attempt None: it *is*
        # a retry loop, which is what ``attempt`` was added for (#1172). A primary that
        # never retries stays None so it does not claim to be attempt 1 of something.
        assert record.attempt == 1
        assert record.completion_tokens == 803
        assert layers.prompt_layer_set_id == "lead-planning"

    async def test_produce_plan_records_per_attempt_with_the_outcome_the_validator_gave(self):
        """The one seam whose record cannot be written at call time: it fires *after*
        validation, so it carries what the validator said. That ordering is the whole
        reason ``_llm_call`` has a ``record=False`` — and it is one opt-out, held to
        one by ``test_every_llm_call_records_a_generation``.

        It records through the same ``_record_generation`` as everything else now.
        Until #929 it had a fourth copy of the record-building block, with its own
        field set — which is the drift the extraction exists to end."""
        manifest = (
            "version: 1\n"
            "project_id: test_proj\n"
            "cycle_id: cyc_test\n"
            "prd_hash: deadbeef\n"
            "tasks:\n"
            "  - task_index: 0\n"
            "    task_type: development.develop\n"
            "    role: dev\n"
            '    focus: "Backend models"\n'
            "    description: |\n"
            "      Define User dataclass.\n"
            "    expected_artifacts:\n"
            '      - "backend/models.py"\n'
            "    acceptance_criteria:\n"
            '      - "User class with id and email"\n'
            "    depends_on: []\n"
            "  - task_index: 1\n"
            "    task_type: development.develop\n"
            "    role: dev\n"
            '    focus: "Backend API"\n'
            "    description: |\n"
            "      Wire FastAPI routes.\n"
            "    expected_artifacts:\n"
            '      - "backend/main.py"\n'
            "    acceptance_criteria:\n"
            '      - "GET /users returns list"\n'
            "    depends_on: [0]\n"
            "  - task_index: 2\n"
            "    task_type: qa.test\n"
            "    role: qa\n"
            '    focus: "Backend tests"\n'
            "    description: |\n"
            "      Cover the routes.\n"
            "    expected_artifacts:\n"
            '      - "tests/test_backend.py"\n'
            "    acceptance_criteria:\n"
            '      - "Three test functions"\n'
            "    depends_on: [1]\n"
            "summary:\n"
            "  total_dev_tasks: 2\n"
            "  total_qa_tasks: 1\n"
            "  total_tasks: 3\n"
            "  estimated_layers: [backend, test]\n"
        )
        ctx, seam = _context(
            "Here's the manifest:\n\n```yaml:implementation_plan.yaml\n" + manifest + "```\n",
            renderer=_renderer(
                "rendered manifest prompt", "request.governance_review_plan_manifest"
            ),
        )

        handler = GovernanceMergePlanHandler()
        artifact = await produce_plan(
            ctx,
            {"prd": "Build a simple user-CRUD API", "profile_roles": ["lead", "dev", "qa"]},
            planning_content="## Plan\n\nLooks good.",
            resolved_config={"implementation_plan": True},
            role="lead",
            handler_name="test_harness",
            chat_kwargs={},
            call=partial(handler._llm_call, ctx, inputs={}),
            record=partial(handler._record_generation, ctx),
        )

        assert artifact is not None
        assert artifact["name"] == "implementation_plan.yaml"
        assert len(seam.calls) == 1
        assert len(seam.records) == 1
        record, layers = seam.records[0]
        assert record.attempt == 1
        assert record.outcome == "accepted"
        assert record.completion_tokens == 803
        # The identity the deleted fourth copy of the record block spelled out. This
        # generation belongs to the authoring loop, not to the handler driving it.
        assert layers.prompt_layer_set_id == "lead-plan-authoring"


# ---------------------------------------------------------------------------
# The gap, stated as one number
# ---------------------------------------------------------------------------


async def test_a_correction_chain_records_everything_it_spends():
    """Bug caught: LangFuse reports a spend figure that is low by an unstated margin.

    #1206 measured 26 recorded of 35 called across a shakeout pair; this is the same
    arithmetic on one correction chain, where it was worst — analyse the failure,
    decide the correction, define the contract, each with a re-ask. Six calls, and
    before the extraction, zero records.

    The margin is what made it dangerous rather than merely incomplete: a partial
    record that announces itself is a caveat, and one that does not is a wrong number.

    Asserted as one arithmetic statement rather than six per-handler counts because
    the arithmetic is the claim — "every call is accounted for" is what a spend figure
    read out of LangFuse depends on, and it is false the moment any one seam drops.
    """
    calls = 0
    records = 0

    analysis = json.dumps(
        {
            "classification": FailureClassification.WORK_PRODUCT,
            "analysis_summary": "Named import of a default export",
            "contributing_factors": ["TS2614"],
        }
    )
    ctx, seam = _context('{"classification": "work_product", "analysis_summary": "The', analysis)
    await DataAnalyzeFailureHandler().handle(ctx, {"prd": "p", "failure_evidence": {"e": "x"}})
    calls += len(seam.calls)
    records += len(seam.records)

    decision = json.dumps(
        {
            "correction_path": "patch",
            "decision_rationale": "Local fix suffices",
            "affected_task_types": ["development.develop"],
        }
    )
    ctx, seam = _context('{"correction_path": "pat', decision)
    await GovernanceCorrectionDecisionHandler().handle(
        ctx, {"prd": "p", "failure_analysis": {"classification": "work_product"}}
    )
    calls += len(seam.calls)
    records += len(seam.records)

    contract = json.dumps(
        {
            "objective": "Fix the import",
            "acceptance_criteria": ["build passes"],
            "non_goals": [],
            "time_budget_seconds": 900,
            "stop_conditions": [],
            "required_artifacts": ["app/page.tsx"],
        }
    )
    ctx, seam = _context('{"objective": "Fix the imp', contract)
    await GovernanceDefineDoneHandler().handle(ctx, {"prd": "p"})
    calls += len(seam.calls)
    records += len(seam.records)

    assert calls == 6
    assert records == calls, (
        f"only {records} of {calls} generations recorded — #1206's gap has reopened "
        f"somewhere in the correction chain, and any spend figure read from LangFuse "
        f"for a corrected cycle is low by an unstated margin"
    )


async def test_a_task_outcome_is_unchanged_when_the_model_fails_at_a_dark_seam():
    """The dark seams own failure handling the shared method must not absorb.

    ``define_done`` returns ``NEEDS_REPLAN`` outputs on an unparseable emission,
    ``analyze_failure`` returns a bare failure, and the review retry returns None
    so its caller fails the task. Three different results from one shape of
    failure — folding the error path into a shared method would have to pick one.
    """
    ctx, seam = _context("not valid json", "still not valid json")
    result = await GovernanceDefineDoneHandler().handle(ctx, {"prd": "test"})
    assert result.success is False
    assert result.outputs["outcome_class"] == TaskOutcome.NEEDS_REPLAN
    assert len(seam.calls) == 2

    ctx, seam = _context("unstructured analysis text", "still unstructured")
    result = await DataAnalyzeFailureHandler().handle(ctx, {"prd": "test"})
    assert result.success is False
    assert result.outputs.get("outcome_class") == TaskOutcome.NEEDS_REPLAN
