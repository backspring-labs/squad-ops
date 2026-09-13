"""Which assembly notes reach the test author, and which never do (#1312, H2).

H2 is a correctness invariant rather than something counted rolls assure: **the notes the
qa prompt carries are the current builder's, or there are none.** A stale notes file from
an earlier attempt is the one shape worse than no notes at all — the test author cannot
tell it is stale, and would write a suite against a fact that is no longer true.

Entered at `_resolve_assembly_notes` for the selection rules and at `_enrich_envelope` for
the wiring, because a resolver that picks correctly and an envelope that never carries the
result are the same bug from the prompt's side (CLAUDE.md: name the entry point).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import ArtifactRef

pytestmark = [pytest.mark.domain_cycles]

_NOTES = "assembly_notes.md"


def _ref(art_id: str, *, filename: str = _NOTES, **metadata) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=art_id,
        project_id="group_run",
        artifact_type="assembly_notes",
        filename=filename,
        content_hash="h",
        size_bytes=10,
        media_type="text/markdown",
        created_at=datetime.now(UTC),
        metadata=metadata,
    )


@pytest.fixture
def mock_vault():
    return AsyncMock()


@pytest.fixture
def executor(mock_vault):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    return DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=mock_vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
    )


def _vault_returning(mock_vault, bodies: dict[str, str]):
    async def _retrieve(art_id):
        return _ref(art_id), bodies[art_id].encode()

    mock_vault.retrieve = AsyncMock(side_effect=_retrieve)


class TestWhichNotesAreChosen:
    async def test_the_latest_accepted_emission_wins(self, executor, mock_vault):
        """A re-take supersedes what it replaced. Picking the first would hand the suite
        author the emission the builder itself corrected."""
        _vault_returning(mock_vault, {"art_old": "first pass", "art_new": "corrected"})
        notes = await executor._resolve_assembly_notes(
            [("art_old", _ref("art_old")), ("art_new", _ref("art_new"))]
        )
        assert notes == {"content": "corrected", "artifact_id": "art_new"}

    async def test_a_failed_emission_is_never_notes(self, executor, mock_vault):
        """#971's rule, applied here: an attempt that failed its checks may still have
        written a notes file, and rendering it hands the test author a fact from an
        emission the framework rejected."""
        _vault_returning(mock_vault, {"art_ok": "good"})
        notes = await executor._resolve_assembly_notes(
            [
                ("art_ok", _ref("art_ok")),
                ("art_bad", _ref("art_bad", emission_status="failed")),
            ]
        )
        assert notes == {"content": "good", "artifact_id": "art_ok"}

    async def test_a_repair_candidate_is_not_notes(self, executor, mock_vault):
        """A candidate is unaccepted by construction — the same exclusion a fresh
        dispatch's workspace applies (pf-31 Fix E)."""
        _vault_returning(mock_vault, {"art_ok": "good"})
        notes = await executor._resolve_assembly_notes(
            [
                ("art_ok", _ref("art_ok")),
                (
                    "art_cand",
                    _ref("art_cand", producing_task_type="builder.assemble_repair"),
                ),
            ]
        )
        assert notes == {"content": "good", "artifact_id": "art_ok"}

    async def test_no_notes_at_all_is_the_expected_answer(self, executor):
        assert await executor._resolve_assembly_notes([]) is None

    async def test_an_empty_body_is_not_notes(self, executor, mock_vault):
        """A heading over nothing tells the test author a fact exists and shows none."""
        _vault_returning(mock_vault, {"art_blank": "   \n  "})
        assert await executor._resolve_assembly_notes([("art_blank", _ref("art_blank"))]) is None

    async def test_another_document_is_not_notes(self, executor, mock_vault):
        """Keyed on the filename, so a README or a report in the same set is not mistaken
        for the builder's notes."""
        _vault_returning(mock_vault, {"art_readme": "# README"})
        assert (
            await executor._resolve_assembly_notes(
                [("art_readme", _ref("art_readme", filename="README.md"))]
            )
            is None
        )

    async def test_a_retrieval_failure_degrades_to_no_notes(self, executor, mock_vault):
        """The notes are optional context; an unreachable vault must not fail the task
        that was going to be given them."""
        mock_vault.retrieve = AsyncMock(side_effect=RuntimeError("vault down"))
        assert await executor._resolve_assembly_notes([("art_x", _ref("art_x"))]) is None


class TestTheNotesReachTheEnvelopeTheQaAuthorIsDispatchedWith:
    """The wiring, entered at `_enrich_envelope` — the single composition point every
    live dispatch goes through (#663).

    A resolver that picks the right notes and an envelope that never carries them are the
    same bug from the prompt's side, and it is the half that has twice been latent from
    its own PR on this line (#1250, #1256, #1261 were each found by a live cycle, never by
    a test that handed the seam its input).
    """

    def _envelope(self, task_type: str):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id=f"task-run_1-m006-{task_type}",
            agent_id="eve",
            cycle_id="cyc_1",
            pulse_id="p",
            project_id="group_run",
            task_type=task_type,
            correlation_id="c",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={"resolved_config": {}},
            metadata={"role": "qa"},
        )

    async def _enrich(self, executor, task_type, stored):
        return await executor._enrich_envelope(
            self._envelope(task_type), {}, [], stored, None, None
        )

    async def test_the_qa_author_is_given_the_notes_and_the_artifact_id(self, executor, mock_vault):
        _vault_returning(mock_vault, {"art_notes": "UID 1000 owns /data"})
        enriched = await self._enrich(executor, "qa.test", [("art_notes", _ref("art_notes"))])
        assert enriched.inputs["assembly_notes"] == {
            "content": "UID 1000 owns /data",
            "artifact_id": "art_notes",
        }

    async def test_a_dispatch_with_no_notes_carries_no_key(self, executor, mock_vault):
        """Presence-keyed all the way down: an empty value would flip the appendix's own
        gate and render a heading over nothing."""
        enriched = await self._enrich(executor, "qa.test", [])
        assert "assembly_notes" not in enriched.inputs

    async def test_a_role_that_renders_no_appendix_is_not_given_them(self, executor, mock_vault):
        """Threading an input no handler reads is how the retired handoff got its shape:
        produced, required, consumed by nothing. The reader set is the guard."""
        _vault_returning(mock_vault, {"art_notes": "UID 1000 owns /data"})
        enriched = await self._enrich(
            executor, "development.develop", [("art_notes", _ref("art_notes"))]
        )
        assert "assembly_notes" not in enriched.inputs
