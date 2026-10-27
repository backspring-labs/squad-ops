"""The slot-subject gate — SIP-0104 §13f (#2664).

A repair of a failing slot assertion keeps an assertion on the same field and surface, unless
the declarations show the field absent there; otherwise it is refused as
``slot_subject_dropped``. Before this, ``measure_assertion_strength`` recorded how much the
fills asserted and refused nothing, and a qa repair in ``cyc_bb493eb4725b`` dropped the failing
store assertion from three slots and passed every shell.

Every value below is invented, on the reference manifest's own entities (``RunEvent``,
``Participant``). Each test names the defect it catches.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.context_assembly import PRIOR_SLOT_FAILURES_KEY, prior_slot_failures
from squadops.capabilities.handlers.impl.repair_handlers import (
    QATestRepairHandler,
    _merge_repair_fills,
)
from squadops.capabilities.verification_scaffold_fill import (
    SLOT_SUBJECT_DROPPED_KEY,
    merge_fills,
    parse_fill_emission,
    slot_subject_guard,
)
from squadops.cycles.scaffold_evidence import classify_shell_failures
from squadops.cycles.task_plan import inject_contract_inputs
from squadops.cycles.verification_contract import VerificationContract
from squadops.stacks.scaffold_contract import emit_contract_dict
from squadops.stacks.slot_subject import AssertionSubject, MatcherClass, SubjectSurface
from squadops.stacks.stack_nextjs_ts_subjects import read_slot_assertions
from squadops.stacks.verification_scaffold import VerificationScaffoldManifest
from squadops.stacks.verification_scaffold_emission import slot_subject_surfaces
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_JOIN = "__tests__/scaffold/vc-probe-api-runs-join.scaffold.test.ts"
_JOIN_SLOT = "slot-vc-probe-api-runs-join"
_DUP = "__tests__/scaffold/vc-probe-api-runs-join-duplicate.scaffold.test.ts"
_DUP_SLOT = "slot-vc-probe-api-runs-join-duplicate"

_RESPONSE = SubjectSurface.RESPONSE
_ENVELOPE = SubjectSurface.ERROR_ENVELOPE
_STORE = SubjectSurface.STORE


def _subject(target: str) -> AssertionSubject | None:
    [assertion] = read_slot_assertions(f"    expect({target}).toBe(1)")
    return assertion.subject


# --------------------------------------------------------------------------------- the reader


class TestTheReaderPlacesEachTarget:
    @pytest.mark.parametrize(
        ("target", "subject"),
        [
            ("body.location", AssertionSubject(_RESPONSE, "location")),
            ("body?.location", AssertionSubject(_RESPONSE, "location")),
            ("body['location']", AssertionSubject(_RESPONSE, "location")),
            ("body.participants[0].name", AssertionSubject(_RESPONSE, "participants")),
            ("body", AssertionSubject(_RESPONSE)),
            ("body.error.code", AssertionSubject(_ENVELOPE, "code")),
            ("body.error?.message", AssertionSubject(_ENVELOPE, "message")),
            ("body.error", AssertionSubject(_ENVELOPE)),
            ("all(TABLES.RunEvent)[0].location", AssertionSubject(_STORE, "location", "RunEvent")),
            ("all(TABLES.RunEvent)[0]?.location", AssertionSubject(_STORE, "location", "RunEvent")),
            ("all(TABLES.RunEvent)", AssertionSubject(_STORE, table="RunEvent")),
            ("all(TABLES.RunEvent).length", AssertionSubject(_STORE, table="RunEvent")),
            ("all(TABLES.RunEvent)[0]", AssertionSubject(_STORE, table="RunEvent")),
            ("TABLES.RunEvent", AssertionSubject(_STORE, table="RunEvent")),
            ("typeof body.title", AssertionSubject(_RESPONSE, "title")),
            ("Array.isArray(body.participants)", AssertionSubject(_RESPONSE, "participants")),
        ],
    )
    def test_each_subject_form_maps_to_its_surface_and_field(self, target, subject):
        """Bug caught: a target form read on the wrong surface or field, so the gate refuses a
        correct rewrite of it or misses a drop of it."""
        assert _subject(target) == subject

    @pytest.mark.parametrize(
        "target",
        [
            "created.id",  # the prerequisite's response, not the shell's surfaces
            "body[0].title",  # an element of a collection body: not a declared form
            "all(TABLES.RunEvent).find((r) => r.id === created.id)?.title",
            "1",
            "helper(body)",
        ],
    )
    def test_a_target_outside_the_forms_has_no_subject(self, target):
        """Bug caught: an unplaceable target read as a subject, so the gate refuses on what it
        cannot show (G4 point 1: such a target is recorded, never refused)."""
        assert _subject(target) is None

    def test_the_bodys_own_aliases_resolve_to_their_subject(self):
        """Bug caught: a rewrite through an alias (`const rows = all(TABLES.X)`, the form the
        cyc_bb493eb4725b repair used) reads as a drop, and a correct repair is refused."""
        body = "\n".join(
            [
                "    const rows = all(TABLES.RunEvent)",
                "    expect(rows[0].title).toBe('Dawn loop')",
                "    const row: any = all(TABLES.RunEvent)[0]",
                "    expect(row!.location).toBe('Pier 4')",
                "    const { participants } = body",
                "    expect(participants).toHaveLength(2)",
                "    for (const p of body.participants) expect(p.name).toBeDefined()",
            ]
        )
        assert [a.subject for a in read_slot_assertions(body)] == [
            AssertionSubject(_STORE, "title", "RunEvent"),
            AssertionSubject(_STORE, "location", "RunEvent"),
            AssertionSubject(_RESPONSE, "participants"),
            AssertionSubject(_RESPONSE, "participants"),
        ]

    @pytest.mark.parametrize(
        ("statement", "klass"),
        [
            ("expect(body.title).toBe('Dawn loop')", MatcherClass.VALUE),
            ("expect(body.participants).toHaveLength(2)", MatcherClass.VALUE),
            ("expect(body.title).toBeDefined()", MatcherClass.EXISTENCE),
            ("expect(body.title).not.toBeUndefined()", MatcherClass.EXISTENCE),
            ("expect(body).toHaveProperty('title')", MatcherClass.SHAPE),
            ("expect(typeof body.title).toBe('string')", MatcherClass.SHAPE),
            ("expect(body.title).not.toBe('')", MatcherClass.OTHER),
        ],
    )
    def test_each_matcher_is_classed_for_the_softer_signal(self, statement, klass):
        """Bug caught: a loosening from an exact value to existence or shape (G4 point 3) read
        as no loosening, or a value check read as one."""
        [assertion] = read_slot_assertions(f"    {statement}")
        assert assertion.matcher_class == klass

    def test_a_multi_line_assertion_covers_its_matcher_line_and_a_comment_asserts_nothing(self):
        """Bug caught: the runner reports the matcher's line, which a reader keyed on the
        `expect(` line cannot place; and a commented-out assertion counted as one kept."""
        body = "\n".join(
            [
                "    // expect(all(TABLES.RunEvent)[0].title).toBe('Dawn loop')",
                "    expect(",
                "      all(TABLES.RunEvent)[0].title,",
                "    ).toBe('Dusk loop')",
            ]
        )
        [assertion] = read_slot_assertions(body)
        assert (assertion.first_line, assertion.last_line) == (2, 4)
        assert assertion.covers(4) and not assertion.covers(1)
        assert assertion.subject == AssertionSubject(_STORE, "title", "RunEvent")


# ------------------------------------------------------------------------ the declarations


class TestTheDeclarations:
    def test_each_surface_is_read_from_the_manifest(self):
        """Bug caught: "absent there" read off the wrong surface — the entity's fields on an
        error shell, whose body is the frozen envelope (the cyc_b6a4ba977d5e reduction) — so a
        correct reduction is refused or a real drop passes."""
        surfaces = slot_subject_surfaces(manifest_for_stack("nextjs_ts"))
        entity = [
            "id",
            "title",
            "datetime",
            "location",
            "distance",
            "pace_target",
            "route_notes",
            "participants",
        ]
        assert surfaces["slots"][_DUP_SLOT] == {
            "response": ["error"],
            "error_envelope": ["code", "message"],
        }
        assert surfaces["slots"][_JOIN_SLOT] == {"response": entity, "error_envelope": []}
        # a collection body is an array, which declares no named field
        assert surfaces["slots"]["slot-vs-get-api-runs"]["response"] == []
        assert surfaces["tables"] == {"RunEvent": entity}

    def test_a_stack_with_no_scaffold_declares_nothing(self):
        """Bug caught: declarations derived for a product with no slots (G4 point 5)."""
        assert slot_subject_surfaces(manifest_for_stack("fullstack_fastapi_react")) == {}

    def test_every_stack_that_emits_shells_has_a_reader_and_declarations(self):
        """Bug caught: a stack added to the shell emitters without a fill reader or its
        declarations. `slot_subject_guard` builds no guard for a stack with no reader, so its
        slots would be revised ungated, and nothing would say so."""
        from squadops.stacks import verification_scaffold_emission as emission

        emitting = set(emission._EMITTERS)
        assert emitting  # the check is vacuous with no shell-emitting stack
        assert set(emission._SLOT_ASSERTION_READERS) == emitting
        assert set(emission._SLOT_SUBJECT_SURFACES) == emitting


# ---------------------------------------------------------------- the gate, at the merge seams


_ACCEPTED_JOIN = (
    "    expect(body.participants).toHaveLength(1)\n"
    "    expect(all(TABLES.RunEvent)[0].participants[0].name).toBe('Ada')"
)
_ACCEPTED_DUP = (
    "    expect(body.error.code).toBe('duplicate_participant')\n"
    "    expect(body.participants).toHaveLength(1)"
)


@pytest.fixture(scope="module")
def manifest():
    return manifest_for_stack("nextjs_ts")


@pytest.fixture(scope="module")
def scaffold(manifest):
    """The scaffold input exactly as the plan composer threads it onto a qa task."""
    inputs: dict = {}
    contract = VerificationContract.from_dict(emit_contract_dict(manifest))
    inject_contract_inputs(inputs, contract, "qa.test", manifest)
    return inputs["verification_scaffold"]


def _accepted_shells(scaffold, overrides: dict[str, str]):
    """Every slot filled; the ones named carry the given bodies, the rest a trivial check."""
    record = VerificationScaffoldManifest.from_dict(scaffold["manifest"])
    fills = "".join(
        f"```fill:{slot}\n{overrides.get(slot, '    expect(body).toBeTruthy()')}\n```\n"
        for slot in record.slot_ids()
    )
    merged = merge_fills(
        scaffold["files"],
        record,
        parse_fill_emission(fills),
        store_tables=scaffold["store_tables"],
        slot_element_kinds=scaffold["slot_element_kinds"],
    )
    return [{"name": f.path, "content": f.content} for f in merged.files]


def _failure(scaffold, shells, path: str, needle: str) -> dict:
    """The fill observation the scaffold evidence records for an assertion failing at the
    line holding ``needle`` — classified by the real classifier, as the live cycle does."""
    content = next(s["content"] for s in shells if s["name"] == path)
    line = next(i for i, text in enumerate(content.split("\n"), start=1) if needle in text)
    record = VerificationScaffoldManifest.from_dict(scaffold["manifest"])
    [observation] = classify_shell_failures(
        [{"file": path, "line": line, "messages": ["AssertionError: expected undefined to be 1"]}],
        {s["name"]: s["content"] for s in shells},
        record,
        {slot.slot_id: "filled" for f in record.files for slot in f.slots},
    )
    return observation.to_dict()


def _repair(scaffold, accepted, failures, emission: str):
    artifacts = QATestRepairHandler()._build_artifacts_from_content(emission)
    return _merge_repair_fills(
        {**scaffold, "current_files": accepted}, artifacts, repair_slots=failures
    )


def _fill(slot: str, body: str) -> str:
    return f"```fill:{slot}\n{body}\n```\n"


class TestTheRepairMerge:
    @pytest.fixture
    def join_failing(self, scaffold):
        shells = _accepted_shells(scaffold, {_JOIN_SLOT: _ACCEPTED_JOIN})
        return shells, [_failure(scaffold, shells, _JOIN, "participants[0].name).toBe('Ada')")]

    def test_a_repair_dropping_the_failing_store_subject_is_refused_whole(
        self, scaffold, join_failing
    ):
        """Bug caught: the cyc_bb493eb4725b weakening — the failing store assertion deleted,
        a response assertion left beside it — accepted because the suite then passed."""
        shells, failures = join_failing
        emission = _fill(_JOIN_SLOT, "    expect(body.participants).toHaveLength(1)") + (
            "```typescript:__tests__/extra.test.ts\nit('x', () => {})\n```\n"
        )
        out, evidence = _repair(scaffold, shells, failures, emission)

        assert out == []  # nothing of the repair is applied, its additive file included
        [refused] = evidence["refused"]
        assert refused["verdict"] == "slot_subject_dropped"
        assert (refused["slot_id"], refused["file"]) == (_JOIN_SLOT, _JOIN)
        assert refused["subject"] == {
            "surface": "store",
            "table": "RunEvent",
            "field": "participants",
        }
        assert refused["described"] == "`participants` on store table `RunEvent`"
        assert "declarations show present there" in refused["detail"]

    def test_a_not_applicable_disposition_on_the_failing_slot_is_refused(
        self, scaffold, join_failing
    ):
        """Bug caught: a repair escaping the gate by declaring the failing slot not applicable,
        which asserts nothing at all."""
        shells, failures = join_failing
        out, evidence = _repair(
            scaffold, shells, failures, _fill(_JOIN_SLOT, "not_applicable: nothing to check")
        )
        assert out == []
        assert [r["verdict"] for r in evidence["refused"]] == ["slot_subject_dropped"]

    def test_a_correct_rewrite_on_the_same_subject_passes(self, scaffold, join_failing):
        """Bug caught: a repair that corrects the failing assertion's value, through an alias
        and another matcher, refused as a drop."""
        shells, failures = join_failing
        rewrite = (
            "    const rows = all(TABLES.RunEvent)\n"
            "    expect(rows[0].participants).toEqual([{ id: expect.any(String), name: 'Bo' }])"
        )
        out, evidence = _repair(scaffold, shells, failures, _fill(_JOIN_SLOT, rewrite))

        assert [a["name"] for a in out] == [_JOIN]
        assert "name: 'Bo'" in out[0]["content"]
        assert "refused" not in evidence
        [verdict] = evidence["subject_gate"]
        assert (verdict["verdict"], verdict["matcher_loosened"]) == ("kept", False)
        # the response check beside it was dropped: the softer signal, recorded
        assert verdict["lost_subjects"] == ["`participants` on the response"]

    def test_a_matcher_loosened_on_the_same_subject_passes_and_is_recorded(
        self, scaffold, join_failing
    ):
        """Bug caught: the loosening G4 point 3 names (an exact value to existence) either
        refused, against the design, or passed with no record a window can read."""
        shells, failures = join_failing
        loosened = (
            "    expect(body.participants).toHaveLength(1)\n"
            "    expect(all(TABLES.RunEvent)[0].participants).toBeDefined()"
        )
        out, evidence = _repair(scaffold, shells, failures, _fill(_JOIN_SLOT, loosened))

        assert [a["name"] for a in out] == [_JOIN]
        [verdict] = evidence["subject_gate"]
        assert verdict["verdict"] == "kept"
        assert verdict["matcher_loosened"] is True

    @pytest.mark.parametrize(
        ("slot", "path", "accepted", "needle", "revision"),
        [
            # the frozen error envelope carries no `participants` (cyc_b6a4ba977d5e's shape)
            (
                _DUP_SLOT,
                _DUP,
                _ACCEPTED_DUP,
                "expect(body.participants)",
                "    expect(body.error.code).toBe('duplicate_participant')\n"
                "    expect(all(TABLES.RunEvent)[0].participants).toHaveLength(1)",
            ),
            # `RunEvent` declares no `participant_count` (cyc_311e2117c21d's shape)
            (
                _JOIN_SLOT,
                _JOIN,
                "    expect(all(TABLES.RunEvent)[0].participant_count).toBe(1)",
                "participant_count",
                "    expect(all(TABLES.RunEvent)).toHaveLength(1)",
            ),
        ],
        ids=["error-envelope", "undeclared-entity-field"],
    )
    def test_a_drop_the_declarations_show_absent_there_passes(
        self, scaffold, slot, path, accepted, needle, revision
    ):
        """Bug caught: a correct reduction — an assertion on a field the surface never
        declares — refused, so qa cannot correct its own wrong assertion."""
        shells = _accepted_shells(scaffold, {slot: accepted})
        out, evidence = _repair(
            scaffold, shells, [_failure(scaffold, shells, path, needle)], _fill(slot, revision)
        )

        assert [a["name"] for a in out] == [path]
        [verdict] = evidence["subject_gate"]
        assert verdict["verdict"] == "absent_there"
        assert "refused" not in evidence

    def test_an_unreadable_failing_subject_is_recorded_and_never_refused(self, scaffold):
        """Bug caught: the gate refusing a revision whose failing subject it cannot read."""
        accepted = "    expect(created.id).toBe(body.id)"
        shells = _accepted_shells(scaffold, {_JOIN_SLOT: accepted})
        failures = [_failure(scaffold, shells, _JOIN, "created.id")]
        out, evidence = _repair(
            scaffold, shells, failures, _fill(_JOIN_SLOT, "    expect(body.id).toBeTruthy()")
        )

        assert [a["name"] for a in out] == [_JOIN]
        [verdict] = evidence["subject_gate"]
        assert verdict["verdict"] == "subject_unreadable"
        assert verdict["subject"] is None

    def test_a_slot_with_no_open_failure_is_not_gated(self, scaffold, join_failing):
        """Bug caught: the gate judging slots that never failed, refusing a repair of another
        slot or file. The failing slot, re-rendered from its accepted body, reads unchanged."""
        shells, failures = join_failing
        out, evidence = _repair(
            scaffold,
            shells,
            failures,
            _fill(_DUP_SLOT, "    expect(body.error.code).toBe('duplicate_participant')"),
        )
        assert [a["name"] for a in out] == [_DUP]
        assert [(v["slot_id"], v["verdict"]) for v in evidence["subject_gate"]] == [
            (_JOIN_SLOT, "unchanged")
        ]


class TestTheHandlerStampsTheRefusal:
    async def test_the_repair_handler_hands_back_nothing_and_names_the_refusal(
        self, scaffold, monkeypatch
    ):
        """Entry point: `QATestRepairHandler._after_emission`, on the inputs the runner builds.
        Bug caught: the merge refuses, but the handler returns the artifacts it was given, or
        no stamp the correction loop reads, so the refusal never reaches the round."""
        from unittest.mock import AsyncMock

        from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult

        shells = _accepted_shells(scaffold, {_JOIN_SLOT: _ACCEPTED_JOIN})
        failures = [_failure(scaffold, shells, _JOIN, "participants[0].name).toBe('Ada')")]
        handler = QATestRepairHandler()
        monkeypatch.setattr(QATestRepairHandler, "_attach_typed_checks", AsyncMock())
        result = HandlerResult(
            success=True,
            outputs={
                "artifacts": handler._build_artifacts_from_content(
                    _fill(_JOIN_SLOT, "    expect(body.participants).toHaveLength(1)")
                )
            },
            _evidence=HandlerEvidence.create("qa_test_repair_handler", "qa.test_repair", 1.0),
        )
        inputs = {
            "verification_scaffold": {**scaffold, "current_files": shells},
            "repair_slots": failures,
        }
        await handler._after_emission(inputs, result)

        assert result.outputs["artifacts"] == []
        [stamp] = result.outputs[SLOT_SUBJECT_DROPPED_KEY]
        assert (stamp["slot_id"], stamp["verdict"]) == (_JOIN_SLOT, "slot_subject_dropped")


# ------------------------------------------------------------- the re-dispatched qa.test path


class TestTheRedispatchedQaTest:
    def _failed_result(self, scaffold):
        shells = _accepted_shells(scaffold, {_JOIN_SLOT: _ACCEPTED_JOIN})
        observation = _failure(scaffold, shells, _JOIN, "participants[0].name).toBe('Ada')")
        return shells, {
            "artifacts": [{**s, "type": "test"} for s in shells],
            "scaffold_evidence": {"observations": [observation]},
        }

    def _envelope(self, scaffold):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-run_001-m004-qa.test",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="prj_invented",
            task_type="qa.test",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={"verification_scaffold": scaffold},
            metadata={"role": "qa"},
        )

    def test_the_re_dispatch_is_gated_and_keeps_the_accepted_assertion(self, scaffold):
        """Entry point: the executor's carry (`_carry_prior_slot_failures`, which block 1 runs
        on every failed attempt), then the qa handler's fill shape on the envelope it re-
        dispatches. Bug caught: a re-dispatched qa.test, a fresh emission with no memory,
        re-fills the failing slot without its assertion and nothing refuses it."""
        from squadops.capabilities.handlers.cycle.qa_test import QATestHandler, _ScaffoldFill
        from squadops.execution.dispatched_flow_executor import _carry_prior_slot_failures
        from squadops.tasks.models import TaskResult

        _shells, outputs = self._failed_result(scaffold)
        envelope = self._envelope(scaffold)
        _carry_prior_slot_failures(
            TaskResult(task_id=envelope.task_id, status="FAILED", outputs=outputs), envelope, None
        )
        carried = envelope.inputs[PRIOR_SLOT_FAILURES_KEY]
        assert [f["slot_id"] for f in carried["failures"]] == [_JOIN_SLOT]
        # only the shell the failure was observed on rides the re-dispatch, not every shell
        assert [f["name"] for f in carried["current_files"]] == [_JOIN]

        shape = _ScaffoldFill(QATestHandler(), envelope.inputs)
        shape.split(_fill(_JOIN_SLOT, "    expect(body.participants).toHaveLength(1)"))
        evidence_extra: dict = {}
        artifacts = shape.merge([], evidence_extra)

        join = next(a for a in artifacts if a["name"] == _JOIN)
        assert "participants[0].name).toBe('Ada')" in join["content"]  # the accepted body kept
        [refused] = evidence_extra["fill_merge"]["refused"]
        assert refused["verdict"] == "slot_subject_dropped"

    def test_a_result_that_ran_no_suite_keeps_the_carry_and_a_clean_one_clears_it(self, scaffold):
        """Bug caught: an attempt that never ran its suite wiping the failure it was re-
        dispatched for (the gate goes off), or a passing attempt leaving a stale one."""
        from squadops.execution.dispatched_flow_executor import _carry_prior_slot_failures
        from squadops.tasks.models import TaskResult

        _shells, outputs = self._failed_result(scaffold)
        envelope = self._envelope(scaffold)
        _carry_prior_slot_failures(
            TaskResult(task_id="t", status="FAILED", outputs=outputs), envelope, None
        )
        before = envelope.inputs[PRIOR_SLOT_FAILURES_KEY]

        _carry_prior_slot_failures(
            TaskResult(task_id="t", status="FAILED", outputs={}), envelope, None
        )
        assert envelope.inputs[PRIOR_SLOT_FAILURES_KEY] == before

        clean = {"scaffold_evidence": {"observations": []}, "artifacts": outputs["artifacts"]}
        _carry_prior_slot_failures(
            TaskResult(task_id="t", status="FAILED", outputs=clean), envelope, None
        )
        assert PRIOR_SLOT_FAILURES_KEY not in envelope.inputs


# ------------------------------------------------------------------- off the scaffold stacks


class TestAProductWithNoScaffoldIsUnchanged:
    def test_no_scaffold_builds_no_guard_and_carries_nothing(self, scaffold):
        """Bug caught: the gate's machinery reaching a product with no slots — a repository-
        backed product or a stack that emits no shells (G4 point 5)."""
        failure = [{"file": _JOIN, "slot_id": _JOIN_SLOT, "line": 40}]
        assert slot_subject_guard(None, failure, []) is None
        no_reader = {
            **scaffold,
            "manifest": {**scaffold["manifest"], "stack": "fullstack_fastapi_react"},
        }
        assert slot_subject_guard(no_reader, failure, []) is None
        observations = {
            "scaffold_evidence": {"observations": [{**failure[0], "failure_class": "fill"}]}
        }
        assert prior_slot_failures(observations, None) is None

    async def test_a_repair_with_no_scaffold_input_is_untouched(self, monkeypatch):
        """Entry point: `QATestRepairHandler._after_emission` with no `verification_scaffold`.
        Bug caught: a non-scaffold qa repair's files stripped or stamped as refused."""
        from unittest.mock import AsyncMock

        from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult

        monkeypatch.setattr(QATestRepairHandler, "_attach_typed_checks", AsyncMock())
        suite = {"name": "tests/test_runs.py", "content": "def test_x(): ...", "type": "test"}
        result = HandlerResult(
            success=True,
            outputs={"artifacts": [dict(suite)]},
            _evidence=HandlerEvidence.create("qa_test_repair_handler", "qa.test_repair", 1.0),
        )
        await QATestRepairHandler()._after_emission({"repair_slots": []}, result)
        assert result.outputs == {"artifacts": [suite]}
