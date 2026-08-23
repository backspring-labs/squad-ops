"""#1055: insert-as-update findings on emitted route handlers.

Filed on a wrong diagnosis and corrected against the source — the lead reported a
"local shadow store" and every route file in that roll imports the frozen store. The
real defect is `find` then `insert` against an append-only store. Each test names the
bug it catches; the over-rejection cases matter as much, because a create legitimately
inserts and flagging it would make the finding noise.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.source_containment import assess_source_containment, is_route_module

_ROUTE = "app/api/runs/[run_id]/join/route.ts"


def _f(name: str, content: str) -> dict:
    return {"name": name, "content": content}


def test_find_then_insert_on_the_same_table_is_flagged():
    """The banked defect, both failing rolls. `insert` is `push`, so persisting an
    update this way stores a SECOND row — which is the `length of 1 but got 2` that
    killed arm A and the "does not add a second participant" red in arm B."""
    content = (
        "import { TABLES, find, insert } from '@/lib/store'\n"
        "export async function POST(r: Request) {\n"
        "  const run = find(TABLES.Run, '1')\n"
        "  insert(TABLES.Run, { ...run, participants: [] })\n}"
    )
    findings = assess_source_containment([_f(_ROUTE, content)])
    assert len(findings) == 1
    assert "insert is append-only" in findings[0]
    assert "TABLES.Run" in findings[0]


def test_a_create_handler_that_only_inserts_is_clean():
    """The control that decides whether this finding is usable. A collection POST
    inserts a genuinely new row and is correct — it is the preceding `find` that turns
    a later insert into a duplicate."""
    content = (
        "import { TABLES, insert, nextId } from '@/lib/store'\n"
        "export async function POST(r: Request) { insert(TABLES.Run, { id: nextId() }) }"
    )
    assert assess_source_containment([_f("app/api/runs/route.ts", content)]) == []


def test_a_read_handler_that_only_finds_is_clean():
    content = (
        "import { TABLES, find } from '@/lib/store'\n"
        "export async function GET() { return Response.json(find(TABLES.Run, '1')) }"
    )
    assert assess_source_containment([_f("app/api/runs/[run_id]/route.ts", content)]) == []


def test_the_correct_update_form_is_clean():
    """Mutating the object `find` returned is the working answer today — the finding
    must not fire on the very form it is telling the author to use."""
    content = (
        "import { TABLES, find } from '@/lib/store'\n"
        "export async function POST() {\n"
        "  const run = find(TABLES.Run, '1')\n"
        "  run.participants = [...run.participants, 'ada']\n}"
    )
    assert assess_source_containment([_f(_ROUTE, content)]) == []


def test_find_and_insert_on_DIFFERENT_tables_is_clean():
    """Reading a Run to validate, then creating a Participant, is ordinary and correct.
    Matching on `insert` near any `find` would flag it."""
    content = (
        "import { TABLES, find, insert } from '@/lib/store'\n"
        "export async function POST() {\n"
        "  const run = find(TABLES.Run, '1')\n"
        "  insert(TABLES.Participant, { id: 'p1', runId: run.id })\n}"
    )
    assert assess_source_containment([_f(_ROUTE, content)]) == []


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("app/api/runs/route.ts", True),
        ("app/api/runs/[run_id]/join/route.ts", True),
        ("app/page.tsx", False),
        ("lib/store.ts", False),
        ("__tests__/runs.test.ts", False),
    ],
)
def test_only_route_modules_are_judged(path, expected):
    """A page or a lib file holding state is a different question. The store itself
    obviously contains both verbs and must never flag."""
    assert is_route_module(path) is expected


def test_findings_are_ordered_so_two_rolls_are_comparable():
    files = [
        _f("app/api/runs/z/route.ts", "find(TABLES.Run, '1'); insert(TABLES.Run, {})"),
        _f("app/api/runs/a/route.ts", "find(TABLES.Run, '1'); insert(TABLES.Run, {})"),
    ]
    assert [f.split(":")[0] for f in assess_source_containment(files)] == [
        "app/api/runs/a/route.ts",
        "app/api/runs/z/route.ts",
    ]


class TestTheFindingsReachTheRecord:
    """The landing, asserted end to end — the lesson #1057 cost.

    #1052 computed findings, placed them in `execution_evidence` which nothing
    persists, and described them as banked. Every layer had a passing test. So this
    asserts on `outputs` and then on the evidence dict the analyzer actually reads.
    """

    @staticmethod
    def _make_envelope():
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="t1",
            agent_id="neo",
            cycle_id="cyc_1",
            pulse_id="p1",
            project_id="group_run",
            task_type="development.develop",
            correlation_id="c1",
            causation_id="c0",
            trace_id="tr1",
            span_id="sp1",
            inputs={},
        )

    _BAD = (
        "import { TABLES, find, insert } from '@/lib/store'\n"
        "export async function POST() {\n"
        "  const run = find(TABLES.Run, '1')\n"
        "  insert(TABLES.Run, { ...run })\n}"
    )

    def test_the_evidence_builder_carries_the_findings_to_the_analyzer(self):
        """Bug caught: the finding computed, banked in outputs, and then dropped before
        the diagnosis. Arm A's lead invented a mechanism because nothing told it what
        the handlers actually did wrong."""
        from squadops.cycles.failure_evidence import build_failure_evidence
        from squadops.tasks.models import TaskResult

        envelope = self._make_envelope()
        result = TaskResult(
            task_id="t1",
            status="FAILED",
            outputs={"source_containment": ["app/api/runs/x/route.ts: ... insert is append-only"]},
        )
        evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=0)
        assert evidence["source_containment"] == [
            "app/api/runs/x/route.ts: ... insert is append-only"
        ]

    def test_a_clean_emission_adds_no_key_rather_than_an_empty_one(self):
        """Presence-keyed, like every other manifest surface: an empty list in the
        analyzer's prompt is a section that says nothing, and the prompt is not free."""
        from squadops.cycles.failure_evidence import build_failure_evidence
        from squadops.tasks.models import TaskResult

        envelope = self._make_envelope()
        result = TaskResult(task_id="t1", status="FAILED", outputs={"source_containment": []})
        assert "source_containment" not in build_failure_evidence(
            envelope, result, prior_plan_deltas_count=0
        )

    def test_a_non_route_file_with_the_pattern_is_not_judged(self):
        """The predicate is tested above; this proves the ASSESSOR uses it. `lib/store.ts`
        itself contains both verbs by definition, and a seeded fixture may too — judging
        them would make the finding fire on the scaffold's own bytes."""
        bad = "find(TABLES.Run, '1'); insert(TABLES.Run, {})"
        assert assess_source_containment([_f("lib/store.ts", bad)]) == []
        assert assess_source_containment([_f("app/page.tsx", bad)]) == []

    def test_the_handler_assigns_the_findings_into_outputs(self):
        """The transport step, and the reason it gets its own test.

        Bug caught: the assessment computed and the result never placed in `outputs` —
        which has now happened six times in this codebase in one working session
        (#1040, #1048, #1052, #1057 twice, here). Every other test in this file passes
        while the fact reaches nobody.

        Asserted structurally because driving the full develop handler needs an LLM, a
        validator and a workspace — a cost that has, in practice, meant this step gets
        no test at all. A structural assertion that the call's result lands in `outputs`
        is worth more than the end-to-end test nobody writes.
        """
        import ast
        import pathlib

        import squadops.capabilities.handlers.cycle.develop as develop_mod

        tree = ast.parse(pathlib.Path(develop_mod.__file__).read_text())
        assigned = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "assess_source_containment"
            and any(
                isinstance(t, ast.Subscript)
                and getattr(t.value, "id", "") == "outputs"
                and getattr(t.slice, "value", None) == "source_containment"
                for t in node.targets
            )
        ]
        assert assigned, (
            "assess_source_containment's result is not assigned into "
            'outputs["source_containment"] — computed and dropped'
        )
