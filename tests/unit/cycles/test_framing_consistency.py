"""#1013: manifest↔plan consistency + completeness.

Every test here is keyed to a banked failure: V38 roll 1 (contradiction), V38
slot 6 (omission), pf-39 (derived-default enforcement), and the false-positive
shapes a rejection gate must never produce.
"""

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.framing_consistency import validate_manifest_plan_consistency
from squadops.cycles.implementation_plan import ImplementationPlan


def _manifest(endpoints_yaml: str, stack: str = "nextjs_ts") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(
        f"""
version: 1
kind: interface_manifest
project_id: group_run
stack: {stack}
api:
  endpoints:
{endpoints_yaml}
frontend:
  routes:
    - path: /
      view: RunsListView
      testids: [runs-list]
"""
    )


def _plan(task_lines: list[str]) -> ImplementationPlan:
    criteria = "\n".join(f"  - '{ln}'" for ln in task_lines) or "  []"
    return ImplementationPlan.from_yaml(
        f"""
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
summary:
  approach: test
tasks:
- task_index: 0
  task_type: development.develop
  role: dev
  focus: API routes
  description: Implement the API routes.
  expected_artifacts: [app/api/runs/route.ts]
  acceptance_criteria:
{criteria}
"""
    )


JOIN_201 = """
    - method: POST
      path: /api/runs
      success_status: 201
    - method: POST
      path: "/api/runs/{run_id}/join"
      success_status: 201
"""


class TestContradiction:
    def test_roll1_class_plan_states_wrong_status(self):
        """V38 roll 1: manifest declares 201, a plan line says the endpoint
        returns 200 — the dev builds the plan, the contract judges the
        manifest, the roll dies. This gate refuses the framing instead."""
        manifest = _manifest(JOIN_201)
        plan = _plan(["POST /api/runs returns 200 with the created run."])
        errors = validate_manifest_plan_consistency(manifest, plan)
        assert any("contradiction on POST /api/runs:" in e for e in errors)
        assert any("enforce success 201" in e for e in errors)

    def test_pf39_class_derived_default_is_enforced(self):
        """pf-39 / #772: a collection POST with NO declared status is still
        enforced at 201 by the deriver — a plan saying 200 contradicts the
        contract even though the manifest never wrote a number."""
        manifest = _manifest(
            """
    - method: POST
      path: /api/runs
"""
        )
        plan = _plan(["POST /api/runs returns 200."])
        errors = validate_manifest_plan_consistency(manifest, plan)
        assert any("contradiction on POST /api/runs:" in e for e in errors)
        assert any("derived default" in e for e in errors)

    def test_multi_status_line_with_enforced_present_is_consistent(self):
        """A summary line carrying its own 201 plus a neighbor's 200 must not
        flag — flagging multi-endpoint prose would reject good framings."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201 with the created run; list returns 200.",
                "POST /api/runs/{run_id}/join returns 201 on success.",
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []

    def test_error_status_vocabulary_never_participates(self):
        """Error teaching (400/404/409) is out of scope — a line rejecting
        blanks with 400 is not a success-status claim."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201.",
                "POST /api/runs rejects blank title with 400 validation_error.",
                "POST /api/runs/{run_id}/join returns 201; duplicate rejected with 409.",
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []


class TestOmission:
    def test_slot6_class_fires_where_no_channel_carries_the_status(self):
        """V38 slot 6: join 201 lived only in the manifest; the plan was silent; the dev
        defaulted to 200 and the roll died on a fact the implementer never received.

        Exercised on a stack with NEITHER channel — no skeleton pinning and no dev-brief
        appendix — because that is now the only condition under which prose is still the
        sole carrier, and it is the condition the gate exists for.
        """
        manifest = _manifest(JOIN_201, stack="no_such_stack")
        plan = _plan(
            [
                "POST /api/runs returns 201 with the created run.",
                "POST /api/runs/{run_id}/join adds the participant and updates the count.",
            ]
        )
        errors = validate_manifest_plan_consistency(manifest, plan)
        assert len(errors) == 1
        assert "omission on POST /api/runs/{run_id}/join:" in errors[0]
        assert "default to 200" in errors[0]

    def test_the_omission_is_silent_once_the_dev_brief_carries_the_status(self):
        """#1049: the same framing, on nextjs_ts, must now PASS.

        Bug caught: the check kept rejecting after #1042 threaded the declared status
        onto the dev brief — enforcing a prose restatement of a fact the implementer is
        now told directly, and warning that "the implementer will default to 200" when
        it will not. Five identical rejections across three cycles, two of them
        consuming both re-rolls of one cycle and dead-ending a correct framing.
        """
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201 with the created run.",
                "POST /api/runs/{run_id}/join adds the participant and updates the count.",
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []

    def test_a_contradiction_still_fires_on_a_stack_with_the_brief_channel(self):
        """The half that must NOT be softened. Derivation fixes silence; it does not fix
        a plan that says the wrong thing — a dev reading "returns 200" builds 200 no
        matter what any appendix also says, and the two channels then disagree."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201 with the created run.",
                "POST /api/runs/{run_id}/join returns 200 once the participant is added.",
            ]
        )
        errors = validate_manifest_plan_consistency(manifest, plan)
        assert len(errors) == 1
        assert "contradiction on POST /api/runs/{run_id}/join:" in errors[0]

    def test_child_post_default_200_needs_no_statement(self):
        """A child-action POST with no declared status is enforced at 200 —
        the dev's own default — so silence is fine (slot 5's green shape)."""
        manifest = _manifest(
            """
    - method: POST
      path: /api/runs
      success_status: 201
    - method: POST
      path: "/api/runs/{run_id}/join"
"""
        )
        plan = _plan(
            [
                "POST /api/runs returns 201 with the created run.",
                "POST /api/runs/{run_id}/join adds the participant.",
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []

    def test_contradiction_suppresses_duplicate_omission_report(self):
        """A contradicted endpoint is already rejected once — reporting the
        omission too would double-charge one defect."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201.",
                "POST /api/runs/{run_id}/join returns 200 on success.",
            ]
        )
        errors = validate_manifest_plan_consistency(manifest, plan)
        join_errors = [e for e in errors if "/join" in e]
        assert len(join_errors) == 1
        assert "contradiction" in join_errors[0]


class TestPathBinding:
    def test_pathless_prose_never_binds(self):
        """Conservative by design: 'create returns 200' with no path form
        binds to nothing — a false positive rejects a good framing, which is
        worse than missing pathless prose."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201.",
                "POST /api/runs/{run_id}/join returns 201.",
                "The create operation returns 200 quickly.",  # pathless — ignored
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []

    def test_param_segment_prose_forms_bind(self):
        """Both `{run_id}` and `[run_id]` prose forms of a parameterized path
        bind to the endpoint (the plan corpus writes both)."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201.",
                "POST /api/runs/[run_id]/join returns 200 on success.",
            ]
        )
        errors = validate_manifest_plan_consistency(manifest, plan)
        assert any("contradiction on POST /api/runs/{run_id}/join:" in e for e in errors)

    def test_prefix_path_does_not_bind_longer_endpoint(self):
        """A line about `/api/runs` must not bind `/api/runs/{run_id}/join` —
        segment-exact matching, no prefix bleed in either direction."""
        manifest = _manifest(JOIN_201)
        plan = _plan(
            [
                "POST /api/runs returns 201.",
                "POST /api/runs/{run_id}/join returns 201.",
                "GET /api/runs returns 200 with the list.",  # GET unchecked; also not join
            ]
        )
        assert validate_manifest_plan_consistency(manifest, plan) == []
