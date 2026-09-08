"""The verification-set driver — the instrument, pinned like any other surface.

Promoted from a session scratchpad after the 1.6.3 and 1.6.4 sets recorded two instrument
defects against it (a stack assumed in code; a log window read without a zone). Each test
here names the launch-time bug it would catch: a driver that misreads the stack opens the
wrong seeded file and reports a P0 that was never checked; a wrong `--since` reads an empty
window and reports "0 empty emissions" for a roll that had one.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack, manifest_for_stack

pytestmark = [pytest.mark.domain_cycles]

_REPO = Path(__file__).resolve().parents[3]
_SETS = _REPO / "docs" / "plans" / "verification-sets"

#: Every committed counting set, by release line and arm, with the arm's roll count.
#: One table drives all four guards below, so covering a new line is one edit instead of
#: three — and `test_the_guard_covers_every_committed_set` goes red when a set config is
#: added to the directory and not to this table. That is the gap this table closes: the
#: pin guard named the 1.7.2 defect exactly and never ran against it, because the lists
#: it was parametrised on stopped at 1.6.6 and nothing noticed for three release lines.
_COUNTING_SETS: dict[str, dict[str, int]] = {
    "1-6-5": {"nextjs": 6, "fastapi-react": 6},
    "1-6-6": {"nextjs": 2, "fastapi-react": 6},
    "1-7-1": {"nextjs": 2, "fastapi-react": 6},
    "1-7-2": {"nextjs": 3, "fastapi-react": 6},
    "1-7-3": {"nextjs": 3, "fastapi-react": 6},
    "1-7-4": {"nextjs": 3, "fastapi-react": 6},
}
_ARM_STACK = {"nextjs": "nextjs_ts", "fastapi-react": "fullstack_fastapi_react"}
_COUNTING_SET_FILES = [
    (f"{line}-{arm}.yaml", arm, rolls)
    for line, arms in _COUNTING_SETS.items()
    for arm, rolls in arms.items()
]


def _committed_counting_sets() -> set[str]:
    """The set configs on disk that are counting arms of a line.

    Excluded by naming convention rather than by a second list, so a new line's pair is
    picked up automatically: `*-diagnostic-*` injects a fault and can never count, and
    `*-ab-*` is an A/B arm, which carries no pin fields at all.
    """
    return {
        path.name
        for path in _SETS.glob("*.yaml")
        if "-diagnostic-" not in path.name and "-ab-" not in path.name
    }


@pytest.fixture(scope="module")
def driver():
    """Import scripts/dev/verification_set_driver.py by path (scripts/ is not a package)."""
    path = _REPO / "scripts" / "dev" / "verification_set_driver.py"
    spec = importlib.util.spec_from_file_location("verification_set_driver", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verification_set_driver"] = module  # dataclasses resolve annotations via it
    spec.loader.exec_module(module)
    return module


class TestLogWindow:
    def test_a_naive_utc_moment_gets_an_explicit_zone(self, driver):
        assert driver.log_since(datetime(2026, 8, 26, 4, 19, 13)) == "2026-08-26T04:19:13Z"

    def test_an_aware_local_moment_is_converted_to_utc(self, driver):
        et = timezone(timedelta(hours=-4))
        assert (
            driver.log_since(datetime(2026, 8, 26, 0, 19, 13, tzinfo=et)) == "2026-08-26T04:19:13Z"
        )

    def test_the_window_is_rfc3339_with_z(self, driver):
        assert driver.log_since(datetime.now(UTC)).endswith("Z")


class TestStackIsTheCyclesFact:
    def test_the_override_wins_over_the_profile_default(self, driver):
        assert (
            driver.derive_stack(
                {"build_profile": "fullstack_fastapi_react"}, {"build_profile": "nextjs_ts"}
            )
            == "nextjs_ts"
        )

    def test_the_profile_default_is_used_when_no_override(self, driver):
        assert (
            driver.derive_stack({"build_profile": "fullstack_fastapi_react"}, {})
            == "fullstack_fastapi_react"
        )

    def test_neither_is_a_refusal_not_a_guess(self, driver):
        with pytest.raises(SystemExit, match="cannot derive the stack"):
            driver.derive_stack({}, {})


class TestNotesAreNotFormatted:
    def test_only_roll_and_n_are_substituted(self, driver):
        out = driver.render_launch_notes("roll {roll} of {n}; per {section} rules {x}", 3, 8)
        assert out == "roll 3 of 8; per {section} rules {x}"


class TestSetConfig:
    def _write(self, tmp_path, **overrides):
        base = {
            "name": "t",
            "project": "group_run",
            "squad_profile": "full-38",
            "request_profile": "validated-fullstack",
            "gate_name": "g",
            "gate_notes": "verbatim {not formatted}",
            "launch_notes": "r {roll}/{n}",
            "shakeout_notes": "s",
            "n_rolls": 2,
        }
        base.update(overrides)
        import yaml

        p = tmp_path / "set.yaml"
        p.write_text(yaml.safe_dump(base))
        return p

    def test_a_missing_key_is_named(self, driver, tmp_path):
        p = self._write(tmp_path)
        text = p.read_text().replace("gate_notes:", "gate_notez:")
        p.write_text(text)
        with pytest.raises(SystemExit, match="missing gate_notes"):
            driver.load_set_config(p)

    def test_an_unknown_service_in_the_image_pins_is_refused(self, driver, tmp_path):
        p = self._write(tmp_path, frozen_image_ids={"runtime-api": "abc", "gateway": "def"})
        with pytest.raises(SystemExit, match="unknown services \\['gateway'\\]"):
            driver.load_set_config(p)

    def test_gate_notes_survive_verbatim_including_braces(self, driver, tmp_path):
        cfg = driver.load_set_config(self._write(tmp_path))
        assert cfg.gate_notes == "verbatim {not formatted}"
        assert cfg.overrides == {} and cfg.frozen_image_ids == {}

    @pytest.mark.parametrize(
        "filename, stack",
        [(name, _ARM_STACK[arm]) for name, arm, _ in _COUNTING_SET_FILES],
    )
    def test_the_committed_set_configs_load_and_derive_their_stack(self, driver, filename, stack):
        """Bug caught: a typo in the file the shakeout will actually run with."""
        cfg = driver.load_set_config(_SETS / filename)
        assert driver.stack_for(cfg) == stack
        assert "{roll}" in cfg.launch_notes and "{n}" in cfg.launch_notes


def _seeded_reader(stack: str, manifest, tamper=None):
    import squadops.capabilities.scaffold as sc

    files = {f["name"]: f["content"] for f in sc.expand(manifest)}
    if tamper:
        files.update(tamper(files))
    return lambda name: files.get(name)


class TestP0PerStack:
    def test_an_unregistered_stack_is_refused_not_passed(self, driver):
        out = driver.p0_checks("fastapi_vue", object(), lambda _n: None)
        assert out["passed"] is False and out["asserted"] is False
        assert "no P0 check registered" in out["refused"]

    def test_no_manifest_is_refused(self, driver):
        out = driver.p0_checks("nextjs_ts", None, lambda _n: None)
        assert out["passed"] is False and "interface_manifest.yaml" in out["refused"]

    def test_nextjs_seeded_tree_holds_against_its_manifest(self, driver):
        m = manifest_for_stack("nextjs_ts")
        out = driver.p0_checks("nextjs_ts", m, _seeded_reader("nextjs_ts", m))
        assert out["passed"] is True and out["asserted"] is True
        assert out["models_mismatches"] == []
        assert out["p0_store_root_only"] and out["p0_harness_root"]

    def test_nextjs_p0_is_falsified_by_the_1096_shape(self, driver):
        """The exact defect the 1.6.4 set was built to see: `participants: string[]` under
        a manifest that declares list[Participant]."""
        m = manifest_for_stack("nextjs_ts")

        def tamper(files):
            return {"lib/models.ts": files["lib/models.ts"].replace("Participant[]", "string[]")}

        out = driver.p0_checks("nextjs_ts", m, _seeded_reader("nextjs_ts", m, tamper))
        assert out["passed"] is False
        assert any("Participant[]" in line for line in out["models_mismatches"])

    def test_stack1_seeded_tree_holds_and_records_no_store_beyond_the_roots(self, driver):
        """Asserted: models.py carries `list[Participant]` (the _py_type pass-through).
        Recorded, not asserted: the stores beyond the roots — the React store used to hand
        `Participant` (an embedded shape) a dict of its own; since #1087's stack #1 half it
        exports the root only, and the readout is empty on the expander's own tree."""
        m = manifest_for_stack("fullstack_fastapi_react")
        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m)
        )
        assert out["passed"] is True
        assert "participants: list[Participant]" in out["models_expected_collection_lines"]
        assert out["store_names"] == ["run_event"]
        assert out["stores_beyond_roots"] == []

    def test_stack1_p0_still_records_a_phantom_store_a_stale_deploy_would_seed(self, driver):
        """A deploy built before the root-table store seeds `participant_store`; the readout
        must still name it (texture the roll record reads), and must not fail the roll —
        the store is recorded, not asserted."""
        m = manifest_for_stack("fullstack_fastapi_react")

        def tamper(files):
            return {
                "backend/store.py": files["backend/store.py"].replace(
                    "run_event_store: dict[str, RunEvent] = {}",
                    "participant_store: dict[str, Participant] = {}\n"
                    "run_event_store: dict[str, RunEvent] = {}",
                )
            }

        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m, tamper)
        )
        assert out["passed"] is True
        assert out["stores_beyond_roots"] == ["participant"]

    def test_stack1_p0_is_falsified_by_a_string_typed_collection(self, driver):
        m = manifest_for_stack("fullstack_fastapi_react")

        def tamper(files):
            return {
                "backend/models.py": files["backend/models.py"].replace(
                    "list[Participant]", "list[str]"
                )
            }

        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m, tamper)
        )
        assert out["passed"] is False and out["models_mismatches"] == [
            "participants: list[Participant]"
        ]

    def test_stack1_p0_asserts_optional_fields_freeze_nullable(self, driver):
        """1.6.6 R1 (#1125): a field the manifest declares ``required: false, default: null``
        must freeze ``X | None = None``. Five of six 1.6.5 rolls opened on the ``str = None``
        form; the driver read them as P0 held because nothing asserted this."""
        import squadops.capabilities.scaffold as sc

        raw = manifest_dict_for_stack("fullstack_fastapi_react")
        for ent in raw["entities"]:
            for f in ent["fields"]:
                if f["name"] == "distance":
                    f["required"], f["default"] = False, None
        m = sc.InterfaceManifest.from_dict(raw)
        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m)
        )
        assert out["passed"] is True
        assert "distance: str | None = None" in out["models_nullable_expected_lines"]

        def tamper(files):
            return {
                "backend/models.py": files["backend/models.py"].replace(
                    "distance: str | None = None", "distance: str = None"
                )
            }

        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m, tamper)
        )
        assert out["passed"] is False
        assert out["models_nullable_mismatches"] == ["distance: str | None = None"]
        assert out["p0_optional_fields_nullable"] is False


class TestTextureFromLogs:
    """1.6.6 R4 (#1129): the record must say whether a plan_defect termination followed
    ANY applied patch — rolls 5 and 6 read as "the loop failed to converge" from the roll-up
    and as "the loop never applied a patch" from the executor log."""

    _REFUSED = "patch_verification task=t status=failed reason=unresolved_imports checks=4"
    _PASSED = "patch_verification task=t status=passed reason= checks=4"
    _RETEST = "patch_retest task=t status=FAILED passed=False reason=x"
    _TERM = "correction_terminated_plan_defect task=t rounds=0..1 candidate=tighten_acceptance"

    def test_roll_five_shape_is_a_termination_after_zero_applied(self, driver):
        out = driver.texture_from_logs([self._REFUSED, self._TERM])
        assert out["applied_patches"] == 0
        assert len(out["refused_patches"]) == 1
        assert out["plan_defect_after_zero_applied"] is True

    def test_a_retest_counts_as_an_applied_patch(self, driver):
        out = driver.texture_from_logs([self._PASSED, self._RETEST, self._TERM])
        assert out["applied_patches"] == 2
        assert out["plan_defect_after_zero_applied"] is False

    def test_unverifiable_then_redispatch_is_a_refusal_but_unverifiable_then_retest_is_applied(
        self, driver
    ):
        """The 1.6.6 Next.js shakeout (cyc_38f95b29cf79): both dev-task patches came back
        unverifiable (no executable typed checks on a .tsx file) and the executor re-dispatched
        the task — never applied — and the first reading counted refused=0."""
        unver = (
            "patch_verification task=task-a status=unverifiable reason=no_executed_blocking_checks"
        )
        redispatch = "Dispatched task task-a (development.develop) to neo_comms"
        retest = "patch_retest task=task-b status=SUCCEEDED passed=True reason=ok"
        unver_b = "patch_verification task=task-b status=unverifiable reason=no_typed_criteria"
        out = driver.texture_from_logs([unver, redispatch, unver_b, retest])
        assert len(out["refused_patches"]) == 1 and "task-a" in out["refused_patches"][0]
        assert out["applied_patches"] == 1

    def test_no_termination_is_never_the_falsifier(self, driver):
        out = driver.texture_from_logs([self._REFUSED, self._REFUSED])
        assert out["plan_defect_terminations"] == []
        assert out["plan_defect_after_zero_applied"] is False

    def test_d_and_f_lines_are_banked(self, driver):
        out = driver.texture_from_logs(
            [
                "plan_defect terminal: round 0's repair … not counted as a repeat (#1129)",
                "patch_retest task=t evidence superseded by the passing retest: replaced=a dropped=b (#1111)",
            ]
        )
        assert len(out["refused_rounds_not_counted"]) == 1
        assert len(out["evidence_superseded"]) == 1


class TestEmptyBodyProbes:
    """1.6.6 R5 (#1128): a POST probe on an endpoint that declares a request body must not
    ship ``json: {}`` — roll 3's contract did, and was unsatisfiable by construction."""

    def test_the_roll_three_shape_is_named_and_a_filled_body_is_not(self, driver):
        m = manifest_for_stack("fullstack_fastapi_react")
        contract = (
            "behavioral:\n  probes:\n"
            "    - id: vc-probe-runs\n      request: {method: POST, path: /runs, json: {title: x}}\n"
            "    - id: vc-probe-runs-join\n      request: {method: POST, path: '/runs/{run_id}/join', json: {}}\n"
            "    - id: vc-probe-runs-blank\n      request: {method: POST, path: /nowhere, json: {}}\n"
        )
        assert driver.empty_body_probes(m, contract) == ["vc-probe-runs-join"]

    def test_an_unparseable_contract_is_visible_not_silent(self, driver):
        m = manifest_for_stack("fullstack_fastapi_react")
        assert driver.empty_body_probes(m, "behavioral: [unclosed") == ["<contract unparseable>"]


class TestRunRows:
    def test_rows_parse_and_blank_lines_are_skipped(self, driver):
        text = (
            "1|framing|completed||run_a|1800\n\n2|implementation|failed|plan_defect: x|run_b|2400\n"
        )
        rows = driver.parse_run_rows(text)
        assert [r["run_number"] for r in rows] == [1, 2]
        assert rows[1] == {
            "run_number": 2,
            "workload": "implementation",
            "status": "failed",
            "failure_reason": "plan_defect: x",
            "run_id": "run_b",
            "seconds": 2400,
        }


class TestSquadSnapshotIsAnIdentity:
    """1.6.5 E moved the squad-profile snapshot (eve's completion budget) and left
    `resolved_config_hash` — the request-profile side — untouched: the first 1.6.5 shakeout
    launched on the 1.6.4 config hash `d4d4f66217d8` while its snapshot was new. Bug caught:
    a set that pins only the config hash accepts a roll on a different squad configuration."""

    @pytest.mark.parametrize(
        "expected, actual, mismatch",
        [
            ("575707c5", "575707c58536cf3b", False),
            ("575707c5", "ab2965c78ccf2497", True),
            ("", "ab2965c78ccf2497", False),  # unpinned = record, do not assert
            ("575707c5", "", True),
        ],
    )
    def test_identity_mismatch(self, driver, expected, actual, mismatch):
        assert driver.identity_mismatch(expected, actual) is mismatch

    @pytest.mark.parametrize(
        ("filename", "n"), [(name, rolls) for name, _, rolls in _COUNTING_SET_FILES]
    )
    def test_the_counting_sets_are_fully_pinned(self, driver, filename, n):
        """Bug caught: a set that has been pinned drifts — a pin hand-edited mid-set, or a
        half-filled block where the driver records instead of asserting and a rebuild
        mid-set passes. A set still in pre-registration has no pins yet, so the assertion
        there is that the block is wholly blank rather than partly filled; catching a
        wholly blank block at launch is `preflight --counting`'s job, and it does refuse."""
        import re

        cfg = driver.load_set_config(_SETS / filename)
        assert cfg.n_rolls == n
        pins = (
            cfg.expected_squad_snapshot_prefix,
            cfg.expected_config_hash_prefix,
            cfg.frozen_deploy_commit,
        )
        if not any(pins) and not cfg.frozen_image_ids:
            return  # pre-registration: pinned at the end of the shakeout loop, not before
        assert re.fullmatch(r"[0-9a-f]{12,16}", cfg.expected_squad_snapshot_prefix)
        assert re.fullmatch(r"[0-9a-f]{12}", cfg.expected_config_hash_prefix)
        assert re.fullmatch(r"[0-9a-f]{8}", cfg.frozen_deploy_commit)
        assert set(cfg.frozen_image_ids) == set(driver.DEPLOY_SERVICES)
        assert all(re.fullmatch(r"[0-9a-f]{12}", v) for v in cfg.frozen_image_ids.values())

    def test_the_guard_covers_every_committed_set(self):
        """Bug caught: a release line's set configs are committed and never added to the
        table, so the guards keep passing on old lines while the line about to launch is
        unchecked. 1.7.0, 1.7.1 and 1.7.2 were each uncovered this way, and 1.7.2 shipped
        two configs with empty pins that no counting roll could have launched from."""
        enumerated = {name for name, _, _ in _COUNTING_SET_FILES}
        assert _committed_counting_sets() == enumerated

    @pytest.mark.parametrize("line", list(_COUNTING_SETS))
    def test_both_sets_share_the_deploy_and_snapshot_but_not_the_config_hash(self, driver, line):
        a = driver.load_set_config(_SETS / f"{line}-nextjs.yaml")
        b = driver.load_set_config(_SETS / f"{line}-fastapi-react.yaml")
        if not (a.frozen_image_ids or b.frozen_image_ids or a.frozen_deploy_commit):
            return  # pre-registration: neither arm is pinned yet (same rule as the pin guard)
        assert a.frozen_image_ids == b.frozen_image_ids
        assert a.frozen_deploy_commit == b.frozen_deploy_commit
        assert a.expected_squad_snapshot_prefix == b.expected_squad_snapshot_prefix
        assert a.expected_config_hash_prefix != b.expected_config_hash_prefix


class TestP0NullableHonoursDeclaredDefaults:
    """A field declared ``required: false`` WITH a non-null default is not nullable.

    The 1.7.2 shakeout on `e2dff444` (`cyc_9a1acc7623b4`) declared
    ``participant_count: {type: int, required: false, default: 0}``. The scaffold rendered
    ``participant_count: int = 0`` — what the manifest asked for — and P0 demanded
    ``int | None = None``, which would discard the default. P0 is a carried prediction, so
    on a counted roll that false positive stops the set.
    """

    @staticmethod
    def _manifest(fields):
        from types import SimpleNamespace

        return SimpleNamespace(
            entities=[SimpleNamespace(name="Run", fields=[SimpleNamespace(**f) for f in fields])]
        )

    @staticmethod
    def _reader(models: str):
        return lambda name: models if name == "backend/models.py" else ""

    def _p0(self, driver, fields, models):
        return driver.p0_checks(
            "fullstack_fastapi_react", self._manifest(fields), self._reader(models)
        )

    def test_an_optional_field_with_a_declared_default_is_not_demanded_nullable(self, driver):
        out = self._p0(
            driver,
            [
                {
                    "name": "participant_count",
                    "type": "int",
                    "required": False,
                    "has_default": True,
                    "default": 0,
                    "generated": False,
                }
            ],
            "class Run(BaseModel):\n    participant_count: int = 0\n",
        )
        assert out["models_nullable_mismatches"] == []
        assert out["p0_optional_fields_nullable"] is True

    def test_an_optional_field_with_no_default_is_still_demanded_nullable(self, driver):
        """The #1125 rule the fix must not weaken: `str = None` is what pydantic rejects."""
        out = self._p0(
            driver,
            [
                {
                    "name": "distance",
                    "type": "string",
                    "required": False,
                    "has_default": False,
                    "default": None,
                    "generated": False,
                }
            ],
            "class Run(BaseModel):\n    distance: str = None\n",
        )
        assert out["models_nullable_mismatches"] == ["distance: str | None = None"]
        assert out["p0_optional_fields_nullable"] is False

    def test_an_explicit_null_default_is_still_demanded_nullable(self, driver):
        out = self._p0(
            driver,
            [
                {
                    "name": "route_notes",
                    "type": "string",
                    "required": True,
                    "has_default": True,
                    "default": None,
                    "generated": False,
                }
            ],
            "class Run(BaseModel):\n    route_notes: str\n",
        )
        assert out["models_nullable_mismatches"] == ["route_notes: str | None = None"]


class TestStaleEvaluationsAreNamed:
    """#1318: a later STORE carrying an earlier EVALUATION is a run judged on a tree that
    no longer exists — and L3's declared read ("the last stored evaluation") cannot see it.
    """

    @staticmethod
    def _tree(tmp_path, versions):
        """versions: [(art_id, stored_at, evaluated_at, ws, [failed checks])]"""
        import json as _json

        for art_id, stored, evaluated, ws, failed in versions:
            art = tmp_path / art_id
            art.mkdir(parents=True)
            (art / "metadata.json").write_text(_json.dumps({"created_at": stored}))
            (art / "typed_check_evaluation_task_4.json").write_text(
                _json.dumps(
                    {
                        "evaluated_at": evaluated,
                        "workspace_revision_id": ws,
                        "evaluations": [
                            {"check": c, "status": "failed", "reason": "file_not_found"}
                            for c in failed
                        ],
                    }
                )
            )
        return tmp_path

    def _run(self, driver, monkeypatch, tmp_path, versions):
        tree = self._tree(tmp_path, versions)
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: sorted(tree.glob("art_*")))
        return driver._stale_evaluations(object(), "cyc", "run")

    def test_a_re_store_with_an_unchanged_evaluation_is_named(self, driver, monkeypatch, tmp_path):
        """The roll-1 shape: stored twice, same evaluated_at, same workspace revision."""
        rows = self._run(
            driver,
            monkeypatch,
            tmp_path,
            [
                ("art_aaa", "2026-09-05 17:08:19", "17:08:18.97", "6b15b9aab690", ["acceptance:x"]),
                ("art_bbb", "2026-09-05 17:10:15", "17:08:18.97", "6b15b9aab690", ["acceptance:x"]),
            ],
        )
        assert len(rows) == 1
        assert rows[0]["stored_versions"] == 2
        assert rows[0]["failed_rows_carried"] == ["acceptance:x"]
        assert rows[0]["last_stored"].endswith("17:10:15")

    def test_a_genuine_re_evaluation_is_not_named(self, driver, monkeypatch, tmp_path):
        """The fix's shape: stored twice because it was RE-RUN — a new workspace revision
        and a new evaluated_at. Reporting this would make the readout cry wolf on exactly
        the behaviour #1318 asks for."""
        rows = self._run(
            driver,
            monkeypatch,
            tmp_path,
            [
                ("art_aaa", "2026-09-05 17:08:19", "17:08:18.97", "6b15b9aab690", ["acceptance:x"]),
                ("art_bbb", "2026-09-05 17:10:15", "17:10:15.40", "d4a09957dfc7", []),
            ],
        )
        assert rows == []

    def test_a_single_stored_evaluation_is_not_named(self, driver, monkeypatch, tmp_path):
        rows = self._run(
            driver,
            monkeypatch,
            tmp_path,
            [("art_aaa", "2026-09-05 17:08:19", "17:08:18.97", "6b15b9aab690", ["acceptance:x"])],
        )
        assert rows == []


def _fake_psql(*, impl_runs: int, active: int, terminal_row: str = ""):
    """Script the three queries `ended_without_implementation` asks, by their subject.

    Dispatching on a substring rather than the whole SQL keeps the tests about the
    decision the function makes, not about its formatting.
    """

    def psql(query: str) -> str:
        if "workload_type='implementation'" in query:
            return str(impl_runs)
        if "status in ('running','queued')" in query:
            return str(active)
        if "status in ('failed','cancelled')" in query:
            return terminal_row
        raise AssertionError(f"unexpected query: {query}")

    return psql


class TestEndedWithoutImplementation:
    """#1168: a cycle that never builds anything must end the drive loop, not outlast it.

    `terminal_impl` only reads implementation runs, so a failed framing left `drive`
    polling for the full four-hour MAX_WAIT_S — no record, no watcher, and the next
    set's preflight stuck behind a process that would not exit (cyc_6e068cdd7de0).
    """

    def test_a_failed_framing_with_nothing_left_running_reports_its_reason(
        self, driver, monkeypatch
    ):
        monkeypatch.setattr(
            driver,
            "psql",
            _fake_psql(
                impl_runs=0,
                active=0,
                terminal_row="failed: Rewinding to checkpoint after "
                "governance.prepare_plan_authoring_brief failure",
            ),
        )
        assert driver.ended_without_implementation("cyc_x") == (
            "failed: Rewinding to checkpoint after governance.prepare_plan_authoring_brief failure"
        )

    def test_an_open_gate_is_not_an_ending(self, driver, monkeypatch):
        """The regression that would matter most: a framing sitting `completed` at an
        unapproved gate has no implementation run and nothing running. Ending here would
        abandon every cycle at its gate — the ordinary path of every shakeout."""
        monkeypatch.setattr(driver, "psql", _fake_psql(impl_runs=0, active=0, terminal_row=""))
        assert driver.ended_without_implementation("cyc_x") is None

    def test_an_existing_implementation_run_defers_to_terminal_impl(self, driver, monkeypatch):
        """Two probes answering the same question would race; `terminal_impl` owns it
        the moment an implementation run exists, whatever that run's status."""
        monkeypatch.setattr(
            driver, "psql", _fake_psql(impl_runs=1, active=0, terminal_row="failed: whatever")
        )
        assert driver.ended_without_implementation("cyc_x") is None

    @pytest.mark.parametrize("active", [1, 3], ids=["one-running", "several-running"])
    def test_work_still_in_flight_is_never_an_ending(self, driver, monkeypatch, active):
        """A queued or running task means the cycle may still create an implementation
        run. Ending here would cut a live cycle short and bank a red record for it."""
        monkeypatch.setattr(
            driver,
            "psql",
            _fake_psql(impl_runs=0, active=active, terminal_row="failed: not yet"),
        )
        assert driver.ended_without_implementation("cyc_x") is None

    def test_a_cancelled_framing_is_reported_as_cancelled_not_failed(self, driver, monkeypatch):
        """#1168 sketched a `framing_failed: true` flag. 32 framing runs in the real table
        ended `cancelled`, and calling those a failure puts a wrong word in a banked
        record — so the status travels with the reason."""
        monkeypatch.setattr(
            driver,
            "psql",
            _fake_psql(impl_runs=0, active=0, terminal_row="cancelled: operator cancelled"),
        )
        assert driver.ended_without_implementation("cyc_x").startswith("cancelled: ")

    def test_a_missing_failure_reason_says_so_rather_than_trailing_a_colon(
        self, driver, monkeypatch
    ):
        """`failure_reason` is nullable. A bare `failed: ` in the record reads as a
        truncated message rather than as an absent one."""
        monkeypatch.setattr(
            driver,
            "psql",
            _fake_psql(impl_runs=0, active=0, terminal_row="failed: no failure_reason recorded"),
        )
        assert driver.ended_without_implementation("cyc_x") == "failed: no failure_reason recorded"


class TestDriveLoopExitsOnAFailedFraming:
    """The #1168 hang itself: the probe is only half the fix — `drive` has to consult it."""

    def test_drive_returns_the_reason_instead_of_polling_to_the_timeout(self, driver, monkeypatch):
        monkeypatch.setattr(driver, "gate_pending", lambda _c: None)
        monkeypatch.setattr(driver, "terminal_impl", lambda _c: None)
        monkeypatch.setattr(
            driver, "ended_without_implementation", lambda _c: "failed: framing died"
        )

        def no_sleep(_s):
            raise AssertionError("drive slept — it did not notice the cycle had ended")

        monkeypatch.setattr(driver.time, "sleep", no_sleep)

        assert driver.drive(object(), "cyc_x") == "failed: framing died"

    def test_the_ordinary_path_still_returns_none_when_implementation_is_terminal(
        self, driver, monkeypatch
    ):
        """`drive` gained a return value; the ordinary path must keep meaning 'nothing
        to report' or every green shakeout would be recorded as ended-early."""
        monkeypatch.setattr(driver, "gate_pending", lambda _c: None)
        monkeypatch.setattr(driver, "terminal_impl", lambda _c: "completed")
        monkeypatch.setattr(
            driver,
            "ended_without_implementation",
            lambda _c: (_ for _ in ()).throw(AssertionError("consulted before terminal_impl")),
        )
        assert driver.drive(object(), "cyc_x") is None


class TestReadoutsByReason:
    """#1276: a readout says on WHAT it fired, not only that it did.

    Each test names the 1.7.1 misreading it would have caught (record §4.6). The oracle in
    every case is the roll's own stored evidence, quoted from `var/verification_sets/`.
    """

    def test_a_kind_gate_row_that_failed_on_an_absent_file_is_not_a_gate_rejection(
        self, driver, tmp_path, monkeypatch
    ):
        """React roll 5 reported `kind_gate_rejections: 1`. The row was
        `assertion_kinds_match` failing with `file_not_found` — the gate rejected nothing;
        a repair was evaluated against a tree that did not carry the suite (#1259)."""
        art = tmp_path / "art_a"
        art.mkdir()
        (art / "typed_check_evaluation_task_6.json").write_text(
            json.dumps(
                {
                    "task_type": "qa.test",
                    "evaluations": [
                        {
                            "check": "acceptance:assertion_kinds_match",
                            "status": "failed",
                            "reason": "file_not_found",
                        },
                        {
                            "check": "acceptance:assertion_kinds_match",
                            "status": "passed",
                            "reason": "ok",
                        },
                    ],
                }
            )
        )
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: [art])
        out = driver.typed_checks_by_check(object(), "cyc", "run")
        assert out["assertion_kinds_match_rows"] == {
            "failed": {"file_not_found": 1},
            "skipped": {},
        }
        assert "kind_gate_rejections" not in out

    def test_skipped_rows_are_reported_beside_failed_ones(self, driver, tmp_path, monkeypatch):
        """#1261 arrived as skipped rows on an ACCEPTED emission — invisible to a count of
        failed ones, and the R6 readout said `0`."""
        art = tmp_path / "art_b"
        art.mkdir()
        (art / "typed_check_evaluation_task_0.json").write_text(
            json.dumps(
                {
                    "task_type": "development.develop",
                    "evaluations": [
                        {
                            "check": "acceptance:undefined_names",
                            "status": "skipped",
                            "reason": "unsupported_stack_or_syntax",
                        }
                    ]
                    * 5,
                }
            )
        )
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: [art])
        out = driver.typed_checks_by_check(object(), "cyc", "run")
        assert out["undefined_names_rows"]["skipped"] == {"unsupported_stack_or_syntax": 5}
        assert out["undefined_names_rows"]["failed"] == {}

    def test_a_row_with_no_reason_is_named_unstated_not_dropped(
        self, driver, tmp_path, monkeypatch
    ):
        art = tmp_path / "art_c"
        art.mkdir()
        (art / "typed_check_evaluation_task_1.json").write_text(
            json.dumps(
                {
                    "task_type": "qa.test",
                    "evaluations": [
                        {"check": "acceptance:additive_containment", "status": "failed"}
                    ],
                }
            )
        )
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: [art])
        out = driver.typed_checks_by_check(object(), "cyc", "run")
        assert out["additive_containment_rows"]["failed"] == {"unstated": 1}

    def test_an_unverifiable_verdict_is_counted_by_its_own_reason(self, driver):
        """Next.js roll 1's `unverifiable_toolchain_absent: 1` came from an absent FILE (a
        prose-only repair), not an absent toolchain — the readout could not tell them apart."""
        absent_file = (
            "patch_verification task=task-a task_type=qa.test status=unverifiable "
            "reason=no_executed_blocking_checks checks=4 failed=- decided_by_agent=0 "
            "agent_rows=2 agent_executed=0 skips=file_not_found:2"
        )
        absent_tooling = (
            "patch_verification task=task-b task_type=development.develop status=unverifiable "
            "reason=no_executed_blocking_checks checks=3 failed=- decided_by_agent=0 "
            "agent_rows=0 agent_executed=0 skips=missing_tooling:3"
        )
        no_criteria = (
            "patch_verification task=task-c task_type=qa.test status=unverifiable "
            "reason=no_typed_criteria checks=0 failed=- skips=-"
        )
        out = driver.texture_from_logs([absent_file, absent_tooling, no_criteria])
        assert out["unverifiable_by_reason"] == {
            "no_executed_blocking_checks": 2,
            "no_typed_criteria": 1,
        }
        assert out["no_execution_by_skip_reason"] == {"missing_tooling": 3, "file_not_found": 2}

    def test_a_repair_brief_records_where_its_evidence_came_from(self, driver):
        """R4's falsifier — a 0-case brief while the failed row carried cases — is only
        readable when the record says which result the brief was built from (#1273)."""
        refunded = (
            "correction_repair_brief: qa.test_repair carries 0 failing case(s) for "
            "__tests__/runs.test.ts from=repair-run_d515-00-qa.test_repair tests_pass_rows=0"
        )
        original = (
            "correction_repair_brief: qa.test_repair carries 3 failing case(s) for "
            "__tests__/runs.test.ts from=task-run_d515-m006-qa.test tests_pass_rows=1"
        )
        out = driver.texture_from_logs([refunded, original])
        assert out["repair_brief_case_counts"] == [
            {"cases": 0, "from": "repair-run_d515-00-qa.test_repair", "tests_pass_rows": 0},
            {"cases": 3, "from": "task-run_d515-m006-qa.test", "tests_pass_rows": 1},
        ]

    def test_a_pre_1276_brief_line_still_parses_with_its_source_unknown(self, driver):
        """The 1.7.1 records were written from a line with no `from=`; reading an old
        window must not crash, and must not invent a source."""
        out = driver.texture_from_logs(
            ["correction_repair_brief: qa.test_repair carries 2 failing case(s) for a.ts"]
        )
        assert out["repair_brief_case_counts"] == [
            {"cases": 2, "from": "?", "tests_pass_rows": None}
        ]


class TestEmissionShapes:
    """#1276/#1268: the emission fact is read from the emission, in the agent's own window.

    `empty_repair_emissions` used to key on the runtime-api's "repair emitted no content"
    token, which both 1.7.1 prose-only repairs failed to produce, and the contentless first
    attempts that shaped five of seven counted rolls appeared in no readout at all.
    """

    _CONTENTLESS = (
        "2026-09-03 08:14:39,401 - squadops.capabilities.handlers.emission_log - INFO - "
        "qa_test_handler emission shape: chars=148 completion_tokens=114 "
        "fences={'fill': 0, 'path': 0, 'plain': 0} head=\"I'll examine the workspace\""
    )
    _REPAIR_PROSE = (
        "2026-09-03 06:10:18,578 - squadops.capabilities.handlers.emission_log - INFO - "
        "qa_test_repair_handler emission shape: chars=225 completion_tokens=154 "
        "fences={'fill': 0, 'path': 0, 'plain': 0} head=\"I'll verify the workspace state\""
    )
    _HEALTHY = (
        "2026-09-03 03:54:49,217 - squadops.capabilities.handlers.emission_log - INFO - "
        "qa_define_test_strategy_handler emission shape: chars=21509 completion_tokens=5943 "
        "reasoning_chars=2181 fences={'fill': 0, 'path': 3, 'plain': 0} head='# QA Test Strategy'"
    )

    def test_a_preamble_with_no_fence_is_contentless_and_carries_its_own_numbers(self, driver):
        out = driver.texture_from_emission_shapes([self._CONTENTLESS, self._HEALTHY])
        assert out["emissions_logged"] == 2
        assert [
            (s["handler"], s["chars"], s["completion_tokens"]) for s in out["contentless_emissions"]
        ] == [("qa_test_handler", 148, "114")]
        assert out["contentless_by_handler"] == {"qa_test_handler": 1}

    def test_a_long_emission_that_addresses_no_file_is_not_contentless(self, driver):
        """A 21k-char strategy document with fences is a healthy emission; the readout must
        not report every fence-less emission as a failure — that is the #932 shape."""
        long_plain = self._HEALTHY.replace("'path': 3", "'path': 0")
        out = driver.texture_from_emission_shapes([long_plain])
        assert out["contentless_emissions"] == []

    def test_a_prose_only_repair_is_an_empty_repair_emission(self, driver):
        """Next.js roll 1: the repair emitted 225 chars of intent, was VERIFIED rather than
        refunded (#1273), and `empty_repair_emissions` reported nothing."""
        out = driver.texture_from_emission_shapes([self._REPAIR_PROSE, self._CONTENTLESS])
        assert [s["handler"] for s in out["empty_repair_emissions"]] == ["qa_test_repair_handler"]

    def test_the_reasoning_split_is_kept_when_the_line_carries_it(self, driver):
        shapes = driver.emission_shapes([self._HEALTHY])
        assert shapes[0]["reasoning_chars"] == "2181"
        assert shapes[0]["fences"] == {"fill": 0, "path": 3, "plain": 0}

    def test_a_line_that_is_not_an_emission_shape_is_ignored(self, driver):
        assert driver.emission_shapes(["INFO - something else entirely"]) == []


class TestTheRecordNamesTheDeployItObserved:
    """#1296: `render`'s fallback to the observed identity was dead code.

    Nothing ever wrote a `deploy` key into the record — `deploy_identity()` was called only
    in `cmd_shakeout` and persisted to a side file — so the header always fell through to
    `cfg.frozen_deploy_commit`, a string an operator types and nothing checks. A shakeout,
    the one cycle whose deploy is unpinned by definition, therefore printed `deploy ?`.
    """

    def _cfg(self, driver, tmp_path, **overrides):
        import yaml

        base = {
            "name": "t",
            "project": "group_run",
            "squad_profile": "full-38",
            "request_profile": "validated-fullstack",
            "gate_name": "g",
            "gate_notes": "g",
            "launch_notes": "r {roll}/{n}",
            "shakeout_notes": "s",
            "n_rolls": 2,
        }
        base.update(overrides)
        p = tmp_path / "set.yaml"
        p.write_text(yaml.safe_dump(base))
        return driver.load_set_config(p)

    def _rec(self, **extra):
        """Every key `render` reads, taken from a real stored record's key set — `render`
        indexes most of them directly, so a partial dict fails for the wrong reason."""
        rec = {
            "cycle_id": "cyc_abc",
            "stack": "fullstack_fastapi_react",
            "verdict": "accepted",
            "config_hash": "c4d6a2165acf",
            "squad_profile_snapshot_ref": "575707c58536",
            "wall_clock_seconds": 60,
            "launched_at": "2026-09-04T15:33:18Z",
            "impl_run_id": "run_abc",
            "boot_audit": {},
            "static_checks": {},
            "ledger_checks": {},
            "loop_texture": {},
            "typed_checks": {},
            "gate_decisions": [],
            "runs": [],
            "failed_checks": [],
            "criteria_verified": 0,
            "criteria_total": 0,
            "criteria_unevidenced": [],
            "correction_rounds": 0,
            "framing_runs": 1,
            "framing_rerolls": 0,
            "failed_emissions_banked": 0,
            "ended_without_implementation": False,
        }
        rec.update(extra)
        return rec

    def test_an_unpinned_shakeout_names_the_head_it_observed_instead_of_a_question_mark(
        self, driver, tmp_path
    ):
        cfg = self._cfg(driver, tmp_path)
        rec = self._rec(deploy={"head": "d6165d2a", "eve": "25de15429a96"})
        header = driver.render(cfg, "shakeout (non-counting)", rec).splitlines()[2]
        assert "deploy `d6165d2a`" in header
        assert "`?`" not in header

    def test_without_an_observed_identity_it_still_says_unknown_rather_than_inventing_one(
        self, driver, tmp_path
    ):
        """The degraded reading stays degraded: a record with no identity must not borrow
        the config's typed pin as though it had been measured."""
        cfg = self._cfg(driver, tmp_path)
        out = driver.render(cfg, "shakeout (non-counting)", self._rec())
        assert "deploy `?`" in out.splitlines()[2]
        assert "## Deploy" not in out

    def test_the_observed_image_ids_and_loaded_checks_reach_the_record(self, driver, tmp_path):
        """They were only ever in the launch log, which no record carries — so a record
        could not show what the deploy actually answered."""
        cfg = self._cfg(driver, tmp_path)
        rec = self._rec(
            deploy={
                "head": "d6165d2a",
                "eve": "25de15429a96",
                "runtime-api": "e6a9898ee18b",
                "eve:loaded": "1 0 ('backend/tests/',)",
            }
        )
        out = driver.render(cfg, "shakeout (non-counting)", rec)
        assert "| eve | `25de15429a96` |" in out
        assert "| runtime-api | `e6a9898ee18b` |" in out
        assert "`eve` → `1 0 ('backend/tests/',)`" in out
        # the loaded check is not also listed as an image
        assert "| eve:loaded |" not in out

    def test_the_typed_pin_is_labelled_as_typed_so_it_is_never_read_as_measured(
        self, driver, tmp_path
    ):
        cfg = self._cfg(driver, tmp_path, frozen_deploy_commit="f85de47a")
        out = driver.render(cfg, "roll 1 of 2", self._rec(deploy={"head": "d6165d2a"}))
        assert "`frozen_deploy_commit`: `f85de47a`" in out
        assert "driver HEAD `d6165d2a`" in out, "the observed head is stated beside the pin"

    def test_an_unset_pin_is_named_as_unset_rather_than_rendered_blank(self, driver, tmp_path):
        cfg = self._cfg(driver, tmp_path)
        out = driver.render(cfg, "shakeout (non-counting)", self._rec(deploy={"head": "d6165d2a"}))
        assert "**unset** (typed, not measured)" in out


class TestAFaultDeclarationSurvivesTheSetConfig:
    """#1298: the carriage from a set config to the agent's emission seam.

    The hook (#1251) and the readouts (#1276) were both built and tested against the shape
    the *handler* sees. Nothing exercised the shape the *driver* produces, and the driver
    could not express a declaration at all: `str(["qa_suite_absent"])` is `"['qa_suite_absent']"`,
    which the framework's guard correctly refuses at cycle create.
    """

    def _cfg(self, driver, tmp_path, faults):
        import yaml

        p = tmp_path / "set.yaml"
        p.write_text(
            yaml.safe_dump(
                {
                    "name": "d",
                    "project": "group_run",
                    "squad_profile": "full-38",
                    "request_profile": "validated-fullstack",
                    "gate_name": "g",
                    "gate_notes": "g",
                    "launch_notes": "r {roll}/{n}",
                    "shakeout_notes": "s",
                    "n_rolls": 1,
                    "overrides": {"fault_injection": faults},
                }
            )
        )
        return driver.load_set_config(p)

    def test_a_yaml_list_is_carried_as_the_comma_form_the_cli_can_express(self, driver, tmp_path):
        """`--set k=v` takes strings, so the list has to become one. Before this it became
        `"['qa_suite_absent']"` and the cycle create was refused."""
        cfg = self._cfg(driver, tmp_path, ["qa_suite_absent", "repair_prose_only"])
        assert cfg.overrides["fault_injection"] == "qa_suite_absent,repair_prose_only"
        assert "[" not in cfg.overrides["fault_injection"]

    def test_the_launch_command_carries_the_declaration_verbatim(self, driver, tmp_path):
        cfg = self._cfg(driver, tmp_path, ["qa_suite_absent", "repair_prose_only"])
        sets = " ".join(f"--set {k}={v}" for k, v in cfg.overrides.items())
        assert sets == "--set fault_injection=qa_suite_absent,repair_prose_only"

    def test_a_single_fault_is_named_not_spelled_out_letter_by_letter(self, driver, tmp_path):
        """The bug the readouts had: a single fault arrives as a string, and both `preflight`
        and the record renderer iterated it directly — so a diagnostic's own record named the
        fault as `_, a, b, e, …` and could not say what it had injected."""
        cfg = self._cfg(driver, tmp_path, "qa_suite_absent")
        assert driver.declared_fault_names(cfg.overrides) == ("qa_suite_absent",)

    def test_a_counting_roll_declaring_a_fault_is_refused_and_the_fault_is_readable(
        self, driver, tmp_path, monkeypatch
    ):
        """The refusal fired before this fix too — a non-empty string is truthy — but named
        the fault by its letters. The outcome was right and the message was unusable."""
        cfg = self._cfg(driver, tmp_path, ["qa_suite_absent"])
        monkeypatch.setattr(driver, "psql", lambda *a, **k: "0")
        monkeypatch.setattr(driver, "sh", lambda *a, **k: "")
        problems = driver.preflight(cfg, counting=True, identity={})
        refusals = [p for p in problems if "fault injection" in p]
        assert refusals, "a counting roll declaring a fault must be refused"
        assert "(qa_suite_absent)" in refusals[0]

    def test_no_declaration_leaves_the_overrides_untouched(self, driver, tmp_path):
        import yaml

        p = tmp_path / "set.yaml"
        p.write_text(
            yaml.safe_dump(
                {
                    "name": "d",
                    "project": "group_run",
                    "squad_profile": "full-38",
                    "request_profile": "validated-fullstack",
                    "gate_name": "g",
                    "gate_notes": "g",
                    "launch_notes": "r {roll}/{n}",
                    "shakeout_notes": "s",
                    "n_rolls": 1,
                    "overrides": {"build_profile": "nextjs_ts"},
                }
            )
        )
        cfg = driver.load_set_config(p)
        assert cfg.overrides == {"build_profile": "nextjs_ts"}
        assert driver.declared_fault_names(cfg.overrides) == ()


class TestRefusalLinesAreTheFactNotAWindow:
    """#1330: ``refused_patches`` banked ``line[-200:]``, and the 1.7.2 Next.js roll 2
    record holds its two refusals as ``'tion task=…'`` and ``'pe=qa.test …'`` — the second
    with its task id gone. The one texture field that says WHY a repair was refused,
    cut mid-word by a width that a qa refusal's fact exceeds."""

    # The stored shape, with the runtime-api's prefix restored in front of it.
    _PREFIX = "2026-09-06 14:01:02,118 INFO squadops.adapters.cycles.dispatched_flow_executor: "
    _FACT = (
        "patch_verification task=task-run_0ed7b128-m007-qa.test task_type=qa.test "
        "status=failed reason= checks=40 failed=assertion_kinds_match,assertion_kinds_match "
        "decided_by_agent=0 agent_rows=38 agent_executed=38 skips=-"
    )

    def test_a_refusal_longer_than_the_old_window_keeps_its_head_and_its_task_id(self, driver):
        assert len(self._FACT) > 200, "the fixture must exceed the old window to mean anything"
        out = driver.texture_from_logs([self._PREFIX + self._FACT])
        assert out["refused_patches"] == [self._FACT]

    def test_an_unverifiable_then_redispatched_refusal_is_whole_too(self, driver):
        unver = self._FACT.replace(
            "status=failed reason=", "status=unverifiable reason=nothing_ran"
        )
        out = driver.texture_from_logs(
            [
                self._PREFIX + unver,
                "Dispatched task task-run_0ed7b128-m007-qa.test (qa.test) to eve",
            ]
        )
        assert out["refused_patches"] == [unver]

    @pytest.mark.parametrize(
        ("field", "line", "starts"),
        [
            (
                "plan_defect_terminations",
                "PFX correction_terminated_plan_defect task=t rounds=0..1 candidate=x " + "y" * 220,
                "correction_terminated_plan_defect task=t",
            ),
            (
                "evidence_superseded",
                "PFX patch_retest task=t evidence superseded by the passing retest: " + "z" * 220,
                "patch_retest task=t evidence superseded",
            ),
            (
                "refused_rounds_not_counted",
                "PFX plan_defect terminal: round 0's repair not counted as a repeat (#1129) "
                + "w" * 220,
                "plan_defect terminal: round 0",
            ),
            (
                "refunded_rounds",
                "PFX correction attempt 0 refunded: the repair emitted no content (signature "
                "unreported), so the round is re-taken rather than spent (refund 1 of 3, "
                "#1053/#998) " + "q" * 220,
                "correction attempt 0 refunded",
            ),
            (
                "self_eval_fill_merges",
                "PFX self_eval fills merged: " + "v" * 220,
                "self_eval fills merged:",
            ),
        ],
    )
    def test_every_banked_line_starts_at_its_marker_and_is_not_capped(
        self, driver, field, line, starts
    ):
        out = driver.texture_from_logs([line])
        assert len(out[field]) == 1
        assert out[field][0].startswith(starts)
        assert out[field][0] == line[len("PFX ") :].rstrip()

    def test_a_line_without_the_marker_is_kept_whole_rather_than_dropped(self, driver):
        assert driver._fact("  no marker here  ", "patch_verification task=") == "no marker here"


class TestL8ReadsTheExtractorNotTheStoredName:
    """#1311: L8 ("no emission lands under a literal ``path/`` prefix") was read from stored
    artifact names — which are what the extractor LEFT after stripping the prefix (#1272).
    The round-4 path-prefix diagnostic injected the condition on both qa emissions and
    both stored names came back correct: the readout could not see its own miss. L8 is
    two claims — the model's (L8a, the strip count) and the extractor's (L8b, the names)."""

    _LINE = (
        "2026-09-05 03:42:07,401 WARNING squadops.capabilities.handlers.fenced_parser: "
        "fence path placeholder: 'path/backend/tests/test_runs.py' emitted under the "
        "example's literal 'path/' segment; stripped to 'backend/tests/test_runs.py', "
        "which the task expects (#1272)"
    )

    def test_the_diagnostics_shape_reads_as_a_model_emission_under_the_placeholder(self, driver):
        """The round-4 roll: stored names clean, and the model emitted under ``path/``
        on both qa tasks. The old readout said HELD; this one says two strips."""
        strips = driver.placeholder_strips(
            [self._LINE, self._LINE.replace("backend/tests/test_runs.py", "frontend/x.test.jsx")]
        )
        assert strips == [
            {
                "emitted": "path/backend/tests/test_runs.py",
                "stripped_to": "backend/tests/test_runs.py",
            },
            {"emitted": "path/frontend/x.test.jsx", "stripped_to": "frontend/x.test.jsx"},
        ]
        assert (
            driver.stored_under_placeholder(["backend/tests/test_runs.py", "frontend/x.test.jsx"])
            == []
        )

    def test_a_stored_name_still_under_the_placeholder_is_the_extractor_half(self, driver):
        assert driver.stored_under_placeholder(
            ["path/backend/tests/test_runs.py", "backend/app.py", "path/z.py"]
        ) == ["path/backend/tests/test_runs.py", "path/z.py"]

    def test_the_agent_window_keeps_the_extractor_line_beside_emission_shapes(
        self, driver, monkeypatch
    ):
        """Wiring: ``loop_texture`` reads the agent containers through ``agent_log_window``.
        A filter that kept only ``emission shape:`` — the pre-#1311 driver — would drop
        the line and the readout would be blind again, with every unit test above green."""
        seen: list[str] = []

        def fake_docker_logs(container: str, since: str, until: str | None = None) -> list[str]:
            seen.append(container)
            return [
                "noise line",
                "… emission shape: handler=qa.test chars=100 fences={'python': 1}",
                self._LINE,
            ]

        monkeypatch.setattr(driver, "docker_logs", fake_docker_logs)
        lines = driver.agent_log_window("2026-09-05T03:00:00Z")
        assert seen == [f"squadops-{s}" for s in driver.AGENT_SERVICES]
        per_container = [line for line in lines if "fence path placeholder" in line]
        assert len(per_container) == len(driver.AGENT_SERVICES)
        assert not any("noise" in line for line in lines)
        assert len(driver.placeholder_strips(lines)) == len(driver.AGENT_SERVICES)

    def test_the_driver_and_the_extractor_agree_on_the_placeholder(self, driver):
        """The driver reads a deployed container's log, so it holds the literal rather
        than importing it; this is what stops the two drifting apart."""
        from squadops.capabilities.handlers import fenced_parser

        assert driver._PLACEHOLDER_PREFIX == fenced_parser._PLACEHOLDER_PREFIX
        # And the log line the driver parses is the one the extractor writes.
        assert "fence path placeholder: %r emitted under the example's literal %r segment; " in (
            Path(fenced_parser.__file__).read_text(encoding="utf-8")
        )


class TestADiagnosticIsReadByTheSeamItReached:
    """#1310: "the fault fired" is not "the prediction was exercised". The round-4
    absent-suite diagnostic bit, the emission retry recovered, correction was never
    entered, and a record reading L2 off the fault's application would have said
    exercised-and-held. Each fault's readout is what the record must show for the seam
    the prediction names to have been reached."""

    @staticmethod
    def _rec(**texture):
        base = {"correction_rounds": 0, "loop_texture": {}}
        base["loop_texture"].update(texture)
        if "correction_rounds" in texture:
            base["correction_rounds"] = texture.pop("correction_rounds")
            base["loop_texture"].pop("correction_rounds", None)
        return base

    def test_the_round_4_absent_suite_shape_reads_as_not_reached(self, driver):
        """Correction rounds 0, no retest: the fault fired and L2's seam was never touched."""
        out = driver.seam_readouts(("qa_suite_absent",), self._rec(retests=[]))
        assert out["qa_suite_absent"]["reached"] is False
        assert out["qa_suite_absent"]["evidence"]["correction_rounds"] == 0

    def test_a_qa_repair_retested_after_correction_reads_as_reached(self, driver):
        rec = {
            "correction_rounds": 1,
            "loop_texture": {
                "retests": [
                    "patch_retest task=task-run_x-m006-qa.test status=SUCCEEDED passed=True"
                ]
            },
        }
        assert driver.seam_readouts(("qa_suite_absent",), rec)["qa_suite_absent"]["reached"] is True

    def test_a_dev_retest_is_not_l2s_seam(self, driver):
        """A retest of a dev task after the qa task recovered on its own is a different
        seam — L2 is the qa repair that supplied the suite."""
        rec = {
            "correction_rounds": 1,
            "loop_texture": {
                "retests": ["patch_retest task=task-run_x-m004-development.develop status=x"]
            },
        }
        assert (
            driver.seam_readouts(("qa_suite_absent",), rec)["qa_suite_absent"]["reached"] is False
        )

    @pytest.mark.parametrize(
        ("fault", "field", "value"),
        [
            (
                "qa_suite_at_path_prefix",
                "placeholder_strips",
                [{"emitted": "path/x", "stripped_to": "x"}],
            ),
            ("qa_suite_own_frame_failure", "qa_owned_routed", ["qa_owned_routed task=t"]),
            (
                "repair_prose_only",
                "refunded_rounds",
                ["correction attempt 0 refunded: the repair emitted no content"],
            ),
        ],
    )
    def test_each_other_fault_is_read_from_the_field_its_seam_writes(
        self, driver, fault, field, value
    ):
        assert driver.seam_readouts((fault,), self._rec(**{field: value}))[fault]["reached"] is True
        assert driver.seam_readouts((fault,), self._rec(**{field: []}))[fault]["reached"] is False

    def test_l4_is_the_refund_not_the_1129_exclusion(self, driver):
        """Bug caught: the 1.7.3 chain diagnostic on the pinned deploy (`cyc_6258b632e198`)
        — the prose-only fault applied, the executor refunded round 0 ("the repair emitted
        no content … re-taken rather than spent"), and the readout, wired to
        ``refused_rounds_not_counted`` (#1129: a REFUSED patch's signature not counted as a
        repeat — a different mechanism), read L4 as not reached."""
        refund = (
            "correction attempt 0 refunded: the repair emitted no content (signature "
            "unreported), so the round is re-taken rather than spent (refund 1 of 3, #1053/#998)"
        )
        rec = self._rec(refunded_rounds=[refund], refused_rounds_not_counted=[])
        out = driver.seam_readouts(("repair_prose_only",), rec)["repair_prose_only"]
        assert out["reached"] is True
        assert out["evidence"] == [refund]
        # The #1129 exclusion alone is not the refund.
        rec = self._rec(refunded_rounds=[], refused_rounds_not_counted=["plan_defect terminal: x"])
        assert (
            driver.seam_readouts(("repair_prose_only",), rec)["repair_prose_only"]["reached"]
            is False
        )

    def test_a_fault_with_no_readout_is_named_not_skipped(self, driver):
        out = driver.seam_readouts(("some_new_fault",), self._rec())
        assert out["some_new_fault"] == {
            "seam": None,
            "reached": None,
            "evidence": "no readout for this fault",
        }

    def test_every_framework_fault_has_a_seam_readout(self, driver):
        """The list that would drift: a fault added to the framework without a readout here
        runs as a diagnostic nothing can read (#1300, #1310)."""
        from squadops.capabilities.handlers.fault_injection import FAULTS

        assert set(driver.SEAM_READOUTS) == set(FAULTS)

    def test_the_texture_carries_the_retests_as_facts(self, driver):
        line = (
            "PFX patch_retest task=task-run_x-m006-qa.test status=SUCCEEDED passed=True reason=ok"
        )
        out = driver.texture_from_logs([line])
        assert out["retests"] == [line[len("PFX ") :]]
        assert out["applied_patches"] == 1


class TestEmissionTokensAreProducedNotOnlyDeclared:
    """#1285 / 1.7.2 record §8: the pre-registration listed "qa primary tokens" as texture
    and no roll record carried it — the driver parsed every emission's tokens and kept
    only the contentless ones. A declared field with no producer reads as measured and is
    not (the #1312 shape). These are the lines the agents actually log."""

    _QA = (
        "2026-09-06 19:52:35,205 - squadops.capabilities.handlers.emission_log - INFO - "
        "qa_define_test_strategy_handler emission shape: chars=15964 completion_tokens=4677 "
        "reasoning_chars=2018 fences={'fill': 0, 'path': 0, 'plain': 1} head='# QA Test"
    )
    _QA_SUITE = (
        "x qa_test_handler emission shape: chars=9117 completion_tokens=5793 "
        "reasoning_tokens=1200 reasoning_chars=4000 fences={'python': 1}"
    )
    _DEV_UNREPORTED = (
        "x development_develop_handler emission shape: chars=100 completion_tokens=None "
        "reasoning_tokens=None fences={'python': 1}"
    )

    def test_every_emission_contributes_its_tokens_by_handler(self, driver):
        out = driver.texture_from_emission_shapes([self._QA, self._QA_SUITE, self._QA_SUITE])
        by = out["emission_tokens_by_handler"]
        assert by["qa_define_test_strategy_handler"] == {
            "emissions": 1,
            "completion_tokens": 4677,
            "reasoning_tokens": 0,
            "reasoning_chars": 2018,
            "unreported_completion": 0,
            "unreported_reasoning": 1,
        }
        assert by["qa_test_handler"]["completion_tokens"] == 5793 * 2
        assert by["qa_test_handler"]["reasoning_tokens"] == 2400
        assert by["qa_test_handler"]["emissions"] == 2

    def test_an_unreported_token_field_is_counted_as_absent_not_zero(self, driver):
        """Bug caught: ``None`` summed as 0 — a record would read "no reasoning spend"
        for an adapter that never reported it."""
        by = driver.emission_tokens_by_handler(driver.emission_shapes([self._DEV_UNREPORTED]))
        row = by["development_develop_handler"]
        assert row["completion_tokens"] == 0 and row["unreported_completion"] == 1
        assert row["reasoning_tokens"] == 0 and row["unreported_reasoning"] == 1

    def test_the_record_row_reads_the_qa_handlers_only(self, driver):
        by = driver.texture_from_emission_shapes([self._QA, self._DEV_UNREPORTED])[
            "emission_tokens_by_handler"
        ]
        text = driver._qa_tokens(by)
        assert "qa_define_test_strategy_handler: 4677 / 0 (1 em)" == text
        assert driver._qa_tokens({}) == "—"


class TestFillMergeEvidenceIsReadFromTheTree:
    """#999: the qa task's fill-merge evidence (#982's assertion strength, the dispositions,
    the additive-containment findings) is a stored artifact beside test_report.md, and
    the record reads it from there — never recomputed from the shells, never from a log."""

    @staticmethod
    def _tree(tmp_path, payloads):
        import json as _json

        for i, (task_id, payload) in enumerate(payloads):
            art = tmp_path / f"art_{i}"
            art.mkdir()
            (art / "fill_merge_evidence.json").write_text(_json.dumps(payload))
            (art / "metadata.json").write_text(
                _json.dumps(
                    {
                        "filename": "fill_merge_evidence.json",
                        "vault_uri": str((art / "fill_merge_evidence.json").relative_to(tmp_path)),
                        "metadata": {"task_id": task_id, "role": "qa"},
                    }
                )
            )
        noise = tmp_path / "art_noise"
        noise.mkdir()
        (noise / "metadata.json").write_text(
            _json.dumps({"filename": "test_report.md", "vault_uri": "x", "metadata": {}})
        )
        return tmp_path

    def test_each_qa_tasks_evidence_is_read_by_task(self, driver, monkeypatch, tmp_path):
        tree = self._tree(
            tmp_path,
            [
                (
                    "task-m006-qa.test",
                    {
                        "fill_merge": {
                            "counts": {"merged": 5},
                            "assertion_strength": {"store_touching": 2, "expect_lines": 16},
                            "additive_containment": ["x.test.ts: names an undeclared table"],
                        },
                        "self_eval_fills": [{"a": 1}, {"b": 2}],
                    },
                ),
                ("task-m007-qa.test", {"fill_merge": {"counts": {"merged": 1}}}),
            ],
        )
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: sorted(tree.glob("art_*")))
        monkeypatch.setattr(driver, "REPO", tree)
        out = driver.fill_merge_evidence(None, "cyc", "run")
        assert [e["task_id"] for e in out] == ["task-m006-qa.test", "task-m007-qa.test"]
        assert out[0]["assertion_strength"] == {"store_touching": 2, "expect_lines": 16}
        assert out[0]["additive_containment"] == ["x.test.ts: names an undeclared table"]
        assert out[0]["self_eval_fills"] == 2
        assert out[1]["assertion_strength"] is None and out[1]["self_eval_fills"] == 0

    def test_a_run_without_the_artifact_reads_as_absent_not_as_zero(
        self, driver, monkeypatch, tmp_path
    ):
        """Bug caught: the #999 shape itself — a field that reads as measured when nothing
        produced it. No artifact → an empty list, so the record shows the gap."""
        tree = self._tree(tmp_path, [])
        monkeypatch.setattr(driver, "artifact_dirs", lambda *a, **k: sorted(tree.glob("art_*")))
        monkeypatch.setattr(driver, "REPO", tree)
        assert driver.fill_merge_evidence(None, "cyc", "run") == []


class TestRetryFeedbackIsReadFromBothWindows:
    """1.7.4 plan §3.1 (#1372, R1): the field exists before the fix, so the pre-registration
    has a producer to check. The executor aims a retry in the runtime-api window; whether
    the handler rendered the fact into the prompt is logged only in the agent's window —
    the #1276 shape again, where a readout keyed on the wrong container read nothing."""

    _AIMED = (
        "2026-09-08 01:02:03,004 - adapters.cycles.dispatched_flow_executor - INFO - "
        "Retryable failure for task-run_x-m004-qa.test (attempt 1), retrying — "
        "signature=unextractable response_chars=148 completion_tokens=114 completion_cap=6000"
    )
    _APPENDED = (
        "2026-09-08 01:02:05,006 - squadops.capabilities.handlers.cycle.base - INFO - "
        "emission retry feedback appended for development_develop_handler: "
        "signature=unextractable appendix_chars=412 expected_files=2"
    )
    _BLIND = (
        "2026-09-08 01:02:05,006 - squadops.capabilities.handlers.cycle.base - WARNING - "
        "emission retry feedback NOT appended for qa_test_handler (no request_renderer) — "
        "this retry re-rolls blind on the same prior; signature=empty"
    )
    _SHAPE = (
        "2026-09-08 01:02:04,000 - squadops.capabilities.handlers.emission_log - INFO - "
        "qa_test_handler emission shape: chars=148 completion_tokens=114 "
        "fences={'fill': 0, 'path': 0, 'plain': 0} head=\"I'll examine\""
    )

    def test_the_aimed_retry_is_banked_from_the_executor_window_as_the_whole_fact(self, driver):
        out = driver.texture_from_logs([self._AIMED, "INFO - Dispatched task task-a (x) to y"])
        assert out["emission_retries"] == [self._AIMED[self._AIMED.find("Retryable failure") :]]

    def test_appended_and_blind_are_told_apart_and_a_shape_line_is_neither(self, driver):
        out = driver.texture_from_retry_feedback([self._APPENDED, self._BLIND, self._SHAPE])
        assert out["retried_with_fact"] == [
            "emission retry feedback appended for development_develop_handler: "
            "signature=unextractable appendix_chars=412 expected_files=2"
        ]
        assert out["retried_blind"] == [
            "emission retry feedback NOT appended for qa_test_handler (no request_renderer) — "
            "this retry re-rolls blind on the same prior; signature=empty"
        ]

    def test_both_windows_keep_the_lines_the_field_reads(self, driver, monkeypatch):
        """Bug caught: a producer whose lines the window filter drops reads as zero forever
        — `empty_repair_emissions` did exactly that for two 1.7.1 rolls (#1276)."""
        assert driver._agent_lines_of_interest([self._APPENDED, self._BLIND, "noise"]) == [
            self._APPENDED,
            self._BLIND,
        ]
        monkeypatch.setattr(
            driver, "docker_logs", lambda container, since, until=None: [self._AIMED, "noise"]
        )
        assert driver.runtime_log_window("2026-09-08T00:00:00Z") == [self._AIMED]

    def test_no_lines_is_neither_with_fact_nor_blind(self, driver):
        assert driver.texture_from_retry_feedback([]) == {
            "retried_with_fact": [],
            "retried_blind": [],
        }


class TestB1IsAFieldNotAGrep:
    """1.7.3 record §2: B1 ("no stored qa suite names a fixture table for a non-root entity")
    was read by a grep over 43 stored suites because the driver produced no field for it —
    the #1285 shape, a declared readout with no producer. The reference manifest declares
    `RunEvent` (root — returned as a single object) and `Participant` (a shape)."""

    @staticmethod
    def _manifest(stack: str) -> str:
        import yaml

        return yaml.safe_dump(manifest_dict_for_stack(stack))

    def test_a_suite_on_the_root_table_holds_and_one_on_a_shape_is_named(self, driver):
        react = self._manifest("fullstack_fastapi_react")
        held = driver.non_root_fixture_tables(
            react, [("backend/tests/test_runs.py", "from backend.store import run_event_store\n")]
        )
        assert held["root_entities"] == ["RunEvent"]
        assert held["non_root_entities"] == ["Participant"]
        assert held["mentions"] == [] and held["suites_read"] == 1
        broken = driver.non_root_fixture_tables(
            react, [("backend/tests/test_runs.py", "participant_store.clear()\n")]
        )
        assert broken["mentions"] == [
            {
                "suite": "backend/tests/test_runs.py",
                "entity": "Participant",
                "form": "participant_store",
            }
        ]

    @pytest.mark.parametrize(
        "text",
        [
            "expect(all(TABLES.Participant)).toHaveLength(1)",
            "insert(TABLES['Participant'], { id: 'p' })",
            'reset(); all(TABLES["Participant"])',
        ],
    )
    def test_every_nextjs_form_of_a_shape_table_is_a_mention(self, driver, text):
        out = driver.non_root_fixture_tables(self._manifest("nextjs_ts"), [("t.test.ts", text)])
        assert [(m["entity"], m["form"]) for m in out["mentions"]] == [
            ("Participant", "TABLES.Participant")
        ]

    def test_a_longer_identifier_that_starts_with_the_shapes_name_is_not_a_mention(self, driver):
        """`TABLES.Participants` and `participant_stores` are other identifiers; a substring
        read would name a suite that never touched the shape's table."""
        out = driver.non_root_fixture_tables(
            self._manifest("nextjs_ts"),
            [("t.test.ts", "all(TABLES.Participants); all(TABLES.RunEvent); participant_stores")],
        )
        assert out["mentions"] == []

    def test_no_manifest_is_a_refusal_not_a_hold(self, driver):
        out = driver.non_root_fixture_tables(None, [("t.test.ts", "all(TABLES.Participant)")])
        assert out["mentions"] is None and out["suites_read"] == 1
        assert "refused" in out
        assert driver._b1_words(out).startswith("REFUSED")
        assert driver._b1_words({"suites_read": 4, "mentions": []}) == "4 / none"
        assert driver._b1_words(None) == "—"

    def test_the_vault_reader_takes_every_stored_version_of_the_qa_authored_suites_only(
        self, driver, tmp_path, monkeypatch
    ):
        """The denominator is the qa author's suites (first emission and repairs, every
        stored version); a scaffold-owned conftest or a qa-authored non-suite file is not."""
        import json
        import types

        root = tmp_path / "data" / "artifacts" / "p" / "cyc_1" / "run_1"
        rows = [
            ("art_1", "backend/tests/test_runs.py", "qa.test", "v1"),
            ("art_2", "backend/tests/test_runs.py", "qa.test_repair", "v2"),
            ("art_3", "conftest.py", "scaffold.expand", "scaffold"),
            ("art_4", "qa_handoff_notes.md", "qa.test", "notes"),
            ("art_5", "tests/runs.test.ts", "qa.test", "ts"),
            # The React frontend suites are .jsx — the first rule missed them and read 39
            # of the 1.7.3 record's 43 suites.
            ("art_6", "frontend/src/__tests__/runs.test.jsx", "qa.test", "jsx"),
            # A qa repair that patched a dev file (#1350's shape) is not a suite.
            ("art_7", "backend/routes.py", "qa.test_repair", "routes"),
        ]
        for art, filename, producer, body in rows:
            d = root / art
            d.mkdir(parents=True)
            (d / "body").write_text(body)
            (d / "metadata.json").write_text(
                json.dumps(
                    {
                        "filename": filename,
                        "metadata": {"producing_task_type": producer},
                        "vault_uri": str((d / "body").relative_to(tmp_path)),
                    }
                )
            )
        monkeypatch.setattr(driver, "REPO", tmp_path)
        cfg = types.SimpleNamespace(project="p")
        assert driver._stored_qa_suites(cfg, "cyc_1", "run_1") == [
            ("backend/tests/test_runs.py", "v1"),
            ("backend/tests/test_runs.py", "v2"),
            ("tests/runs.test.ts", "ts"),
            ("frontend/src/__tests__/runs.test.jsx", "jsx"),
        ]


class TestTheNewFaultsAreReadBySeams:
    """1.7.4 plan §3.1: the contentless-builder and analyzer faults, each read by the seam
    its claim names, never by "the fault fired" (#1310)."""

    @staticmethod
    def _rec(*, correction_rounds=0, typed_checks=None, **texture):
        return {
            "correction_rounds": correction_rounds,
            "loop_texture": texture,
            "typed_checks": typed_checks or {},
        }

    _BUILDER_PASSED = (
        "patch_verification task=task-run_x-m005-builder.assemble status=passed reason= checks=3"
    )
    _BUILDER_REFUSED = "patch_verification task=task-run_x-m005-builder.assemble status=failed reason=required_files checks=3"

    def test_the_builder_seam_is_the_builders_own_verified_repair(self, driver):
        """A correction round on some OTHER task, or a refused builder repair, is not the
        loop recovering the contentless attempt."""
        out = driver.seam_readouts(
            ("builder_emission_contentless",),
            self._rec(correction_rounds=1, patch_verifications=[self._BUILDER_PASSED]),
        )["builder_emission_contentless"]
        assert out["reached"] is True
        assert out["evidence"]["builder_patch_verifications"] == [self._BUILDER_PASSED]
        qa_only = "patch_verification task=task-run_x-m006-qa.test status=passed reason= checks=2"
        for texture in (
            dict(correction_rounds=1, patch_verifications=[qa_only]),
            dict(correction_rounds=1, patch_verifications=[self._BUILDER_REFUSED]),
            dict(correction_rounds=0, patch_verifications=[self._BUILDER_PASSED]),
        ):
            rec = self._rec(**texture)
            assert (
                driver.seam_readouts(("builder_emission_contentless",), rec)[
                    "builder_emission_contentless"
                ]["reached"]
                is False
            )

    def test_the_builder_evidence_carries_the_rows_and_the_retry_facts(self, driver):
        rec = self._rec(
            correction_rounds=1,
            patch_verifications=[self._BUILDER_PASSED],
            emission_retries=["Retryable failure for task-run_x-m005-builder.assemble (attempt 1)"],
            retried_with_fact=[],
            typed_checks={"by_check": {"required_files": {"passed": {"executed": 1}}}},
        )
        ev = driver.seam_readouts(("builder_emission_contentless",), rec)[
            "builder_emission_contentless"
        ]["evidence"]
        assert ev["required_files_rows"] == {"passed": {"executed": 1}}
        assert len(ev["emission_retries"]) == 1 and ev["retried_with_fact"] == []

    def test_the_analyzer_seam_is_the_decision_and_an_inherited_claim_is_named(self, driver):
        held = self._rec(
            decision_inherited_claims=[{"artifact": "art_9", "inherited": False}],
            analyzer_claims_dropped=["correction_repair_target: analyzer implicated x — dropped"],
        )
        out = driver.seam_readouts(("analyzer_false_source_claim",), held)[
            "analyzer_false_source_claim"
        ]
        assert out["reached"] is True
        assert out["evidence"]["refuted_by_workspace_check"] == [
            "correction_repair_target: analyzer implicated x — dropped"
        ]
        inherited = self._rec(
            decision_inherited_claims=[
                {"artifact": "art_9", "inherited": True},
                {"artifact": "art_12", "inherited": False},
            ]
        )
        out = driver.seam_readouts(("analyzer_false_source_claim",), inherited)[
            "analyzer_false_source_claim"
        ]
        assert out["reached"] is False
        assert [d["artifact"] for d in out["evidence"]["decisions"] if d["inherited"]] == ["art_9"]
        # No decision stored at all: the seam was never reached, whatever the fault did.
        assert (
            driver.seam_readouts(("analyzer_false_source_claim",), self._rec())[
                "analyzer_false_source_claim"
            ]["reached"]
            is False
        )

    def test_the_runtime_window_banks_verifications_and_dropped_claims_as_facts(self, driver):
        dropped = (
            "PFX correction_repair_target: analyzer implicated backend/__squadops_injected_fault__.py "
            "but the workspace has no such file — dropped, not aimed at (#968)"
        )
        out = driver.texture_from_logs([f"PFX {self._BUILDER_PASSED}", dropped])
        assert out["patch_verifications"] == [self._BUILDER_PASSED]
        assert out["analyzer_claims_dropped"] == [dropped[len("PFX ") :]]

    def test_decisions_are_read_from_the_vault_by_the_marker(self, driver, tmp_path, monkeypatch):
        import json
        import types

        root = tmp_path / "data" / "artifacts" / "p" / "cyc_1" / "run_1"
        for art, filename, body in (
            (
                "art_1",
                "correction_decision.md",
                '{"decision_rationale": "repair __squadops_injected_fault__.py"}',
            ),
            ("art_2", "correction_decision.md", '{"decision_rationale": "repair routes.py"}'),
            ("art_3", "failure_analysis.md", '{"analysis_summary": "__squadops_injected_fault__"}'),
        ):
            d = root / art
            d.mkdir(parents=True)
            (d / "body").write_text(body)
            (d / "metadata.json").write_text(
                json.dumps(
                    {"filename": filename, "vault_uri": str((d / "body").relative_to(tmp_path))}
                )
            )
        monkeypatch.setattr(driver, "REPO", tmp_path)
        out = driver._decision_inherited_claims(
            types.SimpleNamespace(project="p"), "cyc_1", "run_1"
        )
        assert out == [
            {
                "artifact": "art_1",
                "inherited": True,
                "echoes": [],
                "foreign_affected_task_types": [],
            },
            {
                "artifact": "art_2",
                "inherited": False,
                "echoes": [],
                "foreign_affected_task_types": [],
            },
        ]

    def test_the_marker_the_driver_reads_is_the_one_the_framework_writes(self, driver):
        from squadops.capabilities.handlers.fault_injection import INJECTED_CLAIM_MARKER

        assert driver._INJECTED_CLAIM_MARKER == INJECTED_CLAIM_MARKER


class TestPrefectLoopOverrunsAreRead:
    """#330: the loop-starvation failure mode is read per cycle rather than known about."""

    _LINE = (
        "07:05:11.718 | WARNING | prefect.server.services.scheduler - Scheduler took "
        "4021.211806 seconds to run, which is longer than its loop interval of 60.0 seconds."
    )

    def test_overruns_are_counted_per_service_with_the_worst(self, driver):
        late = self._LINE.replace("scheduler - Scheduler", "late_runs - MarkLateRuns").replace(
            "4021.211806", "12613.0"
        )
        out = driver.prefect_loop_overruns([self._LINE, self._LINE, late, "INFO other"])
        assert out["overruns"] == 3
        assert out["by_service"] == {
            "late_runs": {"count": 1, "worst_seconds": 12613.0},
            "scheduler": {"count": 2, "worst_seconds": 4021.211806},
        }

    def test_a_quiet_window_reads_as_zero_not_absent(self, driver):
        assert driver.prefect_loop_overruns([]) == {"overruns": 0, "by_service": {}}

    def test_the_window_keeps_only_overrun_lines(self, driver, monkeypatch):
        monkeypatch.setattr(
            driver, "docker_logs", lambda c, s, until=None: [self._LINE, "INFO healthy"]
        )
        assert driver.prefect_log_window("2026-09-08T00:00:00Z") == [self._LINE]


class TestF1HasAProducerBeforeRollOne:
    """1.7.4 plan preamble: every registered readout maps to a typed field before the set
    opens. The contentless-builder diagnostic on deploy A showed `typed_checks.by_check`
    carries no `required_files` row for the re-derived patch row — the executor composes
    it into the corrected result and stores no evaluation artifact — so F1's field is the
    executor's own line, kept by the runtime window and banked as a fact."""

    _LINE = (
        "2026-09-08 06:16:33,216 INFO adapters.cycles.dispatched_flow_executor: patch "
        "task=task-run_fed2c9cc-m004-builder.assemble re-derived required_files on the "
        "patched set: passed=True missing=- (no rows; #1318, #1364)"
    )

    def test_the_rederived_row_is_banked_as_a_fact(self, driver):
        out = driver.texture_from_logs([self._LINE, "INFO noise"])
        assert out["framework_rows_rederived"] == [self._LINE[self._LINE.index("patch task=") :]]

    def test_the_runtime_window_keeps_the_line(self, driver, monkeypatch):
        monkeypatch.setattr(
            driver, "docker_logs", lambda c, s, until=None: [self._LINE, "INFO noise"]
        )
        assert driver.runtime_log_window("2026-09-08T00:00:00Z") == [self._LINE]

    def test_the_builder_readout_carries_it(self, driver):
        rec = {
            "correction_rounds": 1,
            "typed_checks": {},
            "loop_texture": {
                "patch_verifications": [
                    "patch_verification task=task-run_x-m005-builder.assemble status=passed reason= checks=3"
                ],
                "framework_rows_rederived": [self._LINE[self._LINE.index("patch task=") :]],
            },
        }
        ev = driver.seam_readouts(("builder_emission_contentless",), rec)[
            "builder_emission_contentless"
        ]["evidence"]
        assert ev["framework_rows_rederived"] == [self._LINE[self._LINE.index("patch task=") :]]


class TestTheA1ReadoutSeesTheClaimsSubstance:
    """The analyzer diagnostic on deploy A (cyc_1063c4dca548, 2026-09-08 07:16Z): the
    round-0 decision carried the refuted claim in substance and no marker. A readout keyed
    on the marker read it as not inherited — its own miss, found by the diagnostic."""

    _REAL_DECISION = json.dumps(
        {
            "correction_path": "patch",
            "decision_rationale": (
                "The failure is a structural absence where the model entered deliberation "
                "mode instead of emitting the required test artifact, but the root cause is "
                "also an injected backend fault preventing endpoint verification. A `patch` "
                "path is necessary to inject specific repair tasks that force the emission of "
                "the missing `backend/tests/test_runs.py` file with the required content and "
                "address the missing router registration to allow the tests to function."
            ),
            "affected_task_types": ["qa.test", "backend"],
        }
    )

    def test_the_real_decision_reads_as_absorbed_without_the_marker(self, driver):
        r = driver._decision_reading(self._REAL_DECISION)
        assert r["inherited"] is False
        assert r["echoes"] == ["injected backend fault", "router registration"]
        assert r["foreign_affected_task_types"] == ["backend"]

    def test_a_clean_decision_reads_clean_and_the_marker_still_counts(self, driver):
        clean = json.dumps(
            {"decision_rationale": "re-emit the suite", "affected_task_types": ["qa.test"]}
        )
        assert driver._decision_reading(clean) == {
            "inherited": False,
            "echoes": [],
            "foreign_affected_task_types": [],
        }
        marked = json.dumps({"decision_rationale": "fix backend/__squadops_injected_fault__.py"})
        assert driver._decision_reading(marked)["inherited"] is True
        # The own-frame chain's decision (cyc_a26c6828482c) said "injected" of the fault call
        # it could see in the suite — not the analyzer's claim.
        own_frame = json.dumps({"decision_rationale": "the suite carries an injected fault call"})
        assert driver._decision_reading(own_frame)["echoes"] == []

    def test_foreign_task_types_alone_do_not_falsify_a1(self, driver):
        """The contentless-builder diagnostic's decision — no analyzer fault declared —
        carried `builder`, `assembler`, `data`, `qa_handoff` in affected_task_types: the
        lead's habit (D1's texture), not the injected claim's leak."""
        rec = {
            "correction_rounds": 1,
            "loop_texture": {
                "decision_inherited_claims": [
                    {
                        "artifact": "a",
                        "inherited": False,
                        "echoes": [],
                        "foreign_affected_task_types": ["builder", "assembler"],
                    }
                ]
            },
        }
        out = driver.seam_readouts(("analyzer_false_source_claim",), rec)[
            "analyzer_false_source_claim"
        ]
        assert out["reached"] is True

    def test_the_readout_is_false_on_substance_alone(self, driver):
        rec = {
            "correction_rounds": 1,
            "loop_texture": {
                "decision_inherited_claims": [
                    {
                        "artifact": "art_bd2bec36ef94",
                        "inherited": False,
                        "echoes": ["injected"],
                        "foreign_affected_task_types": ["backend"],
                    }
                ]
            },
        }
        out = driver.seam_readouts(("analyzer_false_source_claim",), rec)[
            "analyzer_false_source_claim"
        ]
        assert out["reached"] is False
        held = {
            "correction_rounds": 1,
            "loop_texture": {
                "decision_inherited_claims": [
                    {
                        "artifact": "a",
                        "inherited": False,
                        "echoes": [],
                        "foreign_affected_task_types": [],
                    }
                ]
            },
        }
        assert (
            driver.seam_readouts(("analyzer_false_source_claim",), held)[
                "analyzer_false_source_claim"
            ]["reached"]
            is True
        )


class TestTheLogWindowIsBoundedAtBothEnds:
    """The deploy A re-render of the contentless-builder record (cyc_ceef5581bfd1) carried
    the analyzer diagnostic's qa retries as its own: `docker logs --since` with no end
    reads every later cycle. The window ends at the cycle's last run plus a grace."""

    def test_docker_logs_passes_the_end_bound_only_when_given(self, driver, monkeypatch):
        calls = []

        class _P:
            stdout = "a\n"
            stderr = ""

        monkeypatch.setattr(driver.subprocess, "run", lambda args, **kw: calls.append(args) or _P())
        driver.docker_logs("c", "2026-09-08T05:30:00Z")
        driver.docker_logs("c", "2026-09-08T05:30:00Z", "2026-09-08T06:27:00Z")
        assert calls[0] == ["docker", "logs", "--since", "2026-09-08T05:30:00Z", "c"]
        assert calls[1] == [
            "docker",
            "logs",
            "--since",
            "2026-09-08T05:30:00Z",
            "--until",
            "2026-09-08T06:27:00Z",
            "c",
        ]

    def test_the_end_is_the_last_runs_finish_plus_grace_or_none_while_a_run_is_open(
        self, driver, monkeypatch
    ):
        monkeypatch.setattr(driver, "psql", lambda q: "2026-09-08T06:25:49Z|0")
        assert driver.cycle_log_until("cyc_x") == driver.log_since(
            driver.datetime(2026, 9, 8, 6, 26, 49, tzinfo=driver.UTC)
        )
        monkeypatch.setattr(driver, "psql", lambda q: "2026-09-08T06:25:49Z|1")
        assert driver.cycle_log_until("cyc_x") is None
        monkeypatch.setattr(driver, "psql", lambda q: "")
        assert driver.cycle_log_until("cyc_x") is None

    def test_the_texture_records_its_window(self, driver, monkeypatch):
        monkeypatch.setattr(driver, "docker_logs", lambda c, s, u=None: [])
        monkeypatch.setattr(driver, "_fill_rejections", lambda *a: [])
        monkeypatch.setattr(driver, "fill_merge_evidence", lambda *a: [])
        monkeypatch.setattr(driver, "_stored_artifact_names", lambda *a: [])
        monkeypatch.setattr(driver, "_decision_inherited_claims", lambda *a: [])
        out = driver.loop_texture(
            None, "cyc_x", None, "2026-09-08T05:30:00Z", until="2026-09-08T06:27:00Z"
        )
        assert out["log_window"] == {
            "since": "2026-09-08T05:30:00Z",
            "until": "2026-09-08T06:27:00Z",
        }


class TestNonExecutionIsCountedWhereverItHappens:
    """The React checkpoint on deploy B (`cyc_dd3068d22f2c`) is the launch-time bug.

    Its qa repair verification came back `status=passed` carrying
    `skips=missing_tooling:3` — three `frontend_compiles` rows that never ran, which
    demoted three already-passed `vc-view-compiles-*` criteria to unverified. The record
    read `non-execution by skip reason: 0`, because the readout only looked at
    verifications that came back `unverifiable`. A skip that rides a PASSING verification
    is the one a reader most needs, and it was the one the instrument could not see.
    """

    _PASSED_WITH_SKIPS = (
        "patch_verification task=task-run_737ff76b-m006-qa.test task_type=qa.test "
        "status=passed reason= checks=16 failed=- decided_by_agent=0 agent_rows=11 "
        "agent_executed=11 skips=missing_tooling:3"
    )
    _UNVERIFIABLE = (
        "patch_verification task=task-b task_type=development.develop status=unverifiable "
        "reason=no_executed_blocking_checks checks=3 failed=- decided_by_agent=0 "
        "agent_rows=0 agent_executed=0 skips=file_not_found:2"
    )

    def test_a_skip_on_a_passing_verification_is_counted(self, driver):
        out = driver.texture_from_logs([self._PASSED_WITH_SKIPS, self._UNVERIFIABLE])
        assert out["no_execution_by_skip_reason"] == {"missing_tooling": 3, "file_not_found": 2}
        assert out["no_execution_on_passed_verifications"] == {"missing_tooling": 3}

    def test_the_passing_half_is_reported_apart_so_the_unverifiable_reading_survives(self, driver):
        """#1261's reading is the unverifiable one; widening the first field must not
        erase the distinction, or a toolchain gap on a passing verification and a repair
        that earned no verdict become the same number."""
        out = driver.texture_from_logs([self._UNVERIFIABLE])
        assert out["no_execution_by_skip_reason"] == {"file_not_found": 2}
        assert out["no_execution_on_passed_verifications"] == {}

    def test_a_verification_with_no_skips_reads_as_zero_not_absent(self, driver):
        clean = (
            "patch_verification task=task-c task_type=qa.test status=passed reason= "
            "checks=4 failed=- decided_by_agent=0 agent_rows=4 agent_executed=4 skips=-"
        )
        out = driver.texture_from_logs([clean])
        assert out["no_execution_by_skip_reason"] == {}
        assert out["no_execution_on_passed_verifications"] == {}


class TestTheCriteriaShortfallIsNamed:
    """`21 / 24` beside an empty unevidenced list, and the record could not say which
    three criteria were lost or why (the React checkpoint on deploy B again: three
    `vc-view-compiles-*` criteria carried a row and were not credited). The framework
    derives `criteria_unverified`/`criteria_adverse` on its own summary (#945, #1021);
    the driver reads the stored JSON and has to derive the same subtraction.
    """

    _SUMMARY = {
        "criteria_total": ["vc-a", "vc-b", "vc-view-compiles-runs-list-view", "vc-d"],
        "criteria_verified": ["vc-a", "vc-b"],
        "criteria_unevidenced": ["vc-d"],
    }

    def test_the_shortfall_is_named_and_split_by_whether_a_row_was_produced(self, driver):
        assert driver._criteria_unverified(self._SUMMARY) == [
            "vc-view-compiles-runs-list-view",
            "vc-d",
        ]

    def test_an_empty_contract_yields_no_shortfall_rather_than_raising(self, driver):
        assert driver._criteria_unverified({}) == []

    def test_the_record_names_the_adverse_criteria_instead_of_leaving_a_subtraction(
        self, driver, tmp_path
    ):
        holder = TestTheRecordNamesTheDeployItObserved()
        cfg = holder._cfg(driver, tmp_path)
        rec = holder._rec(
            criteria_verified=21,
            criteria_total=24,
            criteria_unevidenced=[],
            criteria_adverse=["vc-view-compiles-runs-list-view"],
        )
        out = driver.render(cfg, "shakeout (non-counting)", rec)
        assert "vc-view-compiles-runs-list-view" in out
        assert "criteria NOT verified" in out


class TestH1ReadsEveryRequiredFileNotTheHandoffs:
    """H1 (1.7.4) is "no counted roll is rejected or blocked on the handoff", and its own
    blind spot is that a NEW required file the profile derives fails identically under a
    different name — a record listing only the handoff would read as the bar holding while
    a different deliverable rejected every roll. #1312 put `required=` on the row and on
    the executor's line so the readout can name the whole declared set.
    """

    _LINE = (
        "patch task=task-run_1-m004-builder.assemble re-derived required_files on the "
        "patched set: passed=True required=Dockerfile,start.sh missing=- (the failed "
        "attempt carried the row; #1318, #1364)"
    )

    def test_every_declared_file_is_named(self, driver):
        out = driver.texture_from_logs([self._LINE])
        assert out["required_files_declared"] == ["Dockerfile", "start.sh"]

    def test_a_roll_with_no_such_row_reads_empty_not_absent(self, driver):
        out = driver.texture_from_logs(["something else entirely"])
        assert out["required_files_declared"] == []

    def test_a_line_without_the_field_contributes_nothing(self, driver):
        """Pre-#1312 lines carry `missing=` and no `required=`; the readout must not
        invent a set from them."""
        old = (
            "patch task=t re-derived required_files on the patched set: passed=False "
            "missing=qa_handoff.md (the failed attempt carried the row; #1318, #1364)"
        )
        assert driver.texture_from_logs([old])["required_files_declared"] == []


class TestALoadedCheckIsAskedWhereItSaysAndAnsweredBeforeLaunch:
    """#1425: three 1.7.4 probes named containers that do not exist.

    `loaded_checks` keyed on the container, so a second probe for one service needed a
    distinct key; the suffix invented for that (`bob-1-7-4`) was then docker-exec'd as
    `squadops-bob-1-7-4`. Every launch recorded `ERROR: No such container` beside the
    probes that did run, and a whole checkpoint pair was read as clean with three of its
    surfaces never verified. Two halves: the probe names its service explicitly and an
    unknown one is refused at load, and preflight refuses to launch on a probe that could
    not run — an unasked question, which in the record is indistinguishable from an
    answered one.
    """

    def _cfg(self, driver, tmp_path, checks):
        import yaml

        p = tmp_path / "set.yaml"
        p.write_text(
            yaml.safe_dump(
                {
                    "name": "t",
                    "project": "group_run",
                    "squad_profile": "full-38",
                    "request_profile": "validated-fullstack",
                    "gate_name": "g",
                    "gate_notes": "g",
                    "launch_notes": "r {roll}/{n}",
                    "shakeout_notes": "s",
                    "n_rolls": 2,
                    "loaded_checks": checks,
                }
            )
        )
        return driver.load_set_config(p)

    def _execs(self, driver, monkeypatch, cfg):
        """Run deploy_identity against a stubbed docker, returning (argv seen, identity)."""
        seen = []

        class _Proc:
            returncode = 0
            stdout = "answered"
            stderr = ""

        def fake_run(argv, **kwargs):
            seen.append(argv)
            return _Proc()

        monkeypatch.setattr(driver.subprocess, "run", fake_run)
        monkeypatch.setattr(driver, "sh", lambda *a, **k: "")
        return seen, driver.deploy_identity(cfg)

    def test_a_probe_naming_a_container_that_does_not_exist_is_refused_at_load(
        self, driver, tmp_path
    ):
        with pytest.raises(SystemExit, match=r"unknown services \['bob-1-7-4'\]"):
            self._cfg(driver, tmp_path, {"bob-1-7-4": "print(1)"})

    def test_a_mapping_probe_naming_a_container_that_does_not_exist_is_refused_too(
        self, driver, tmp_path
    ):
        """The explicit shape must not become the way to smuggle a bad service back in."""
        with pytest.raises(SystemExit, match=r"unknown services \['nope'\]"):
            self._cfg(driver, tmp_path, {"faults": {"service": "nope", "source": "print(1)"}})

    def test_a_named_probe_is_asked_in_its_service_and_recorded_under_its_name(
        self, driver, tmp_path, monkeypatch
    ):
        """Two probes for one container: the record must distinguish them, and both must
        reach `bob` rather than a container named after the question."""
        cfg = self._cfg(
            driver,
            tmp_path,
            {
                "builder-fault-seam": {"service": "bob", "source": "print('a')"},
                "builder-pack": {"service": "bob", "source": "print('b')"},
            },
        )
        seen, ids = self._execs(driver, monkeypatch, cfg)
        assert [a[2] for a in seen] == ["squadops-bob", "squadops-bob"]
        assert [a[-1] for a in seen] == ["print('a')", "print('b')"]
        assert ids["builder-fault-seam:loaded"] == "answered"
        assert ids["builder-pack:loaded"] == "answered"

    def test_the_bare_shape_still_reads_its_key_as_the_service(self, driver, tmp_path, monkeypatch):
        """Every set through 1.7.3 is written this way; their records must stay reproducible."""
        cfg = self._cfg(driver, tmp_path, {"eve": "print('x')"})
        seen, ids = self._execs(driver, monkeypatch, cfg)
        assert [a[2] for a in seen] == ["squadops-eve"]
        assert ids["eve:loaded"] == "answered"

    def test_a_mapping_probe_missing_its_source_is_named(self, driver, tmp_path):
        with pytest.raises(SystemExit, match="loaded_checks\\[faults\\] is missing source"):
            self._cfg(driver, tmp_path, {"faults": {"service": "bob"}})

    def _clean_environment(self, driver, monkeypatch):
        monkeypatch.setattr(driver, "psql", lambda *a, **k: "0")
        monkeypatch.setattr(driver, "sh", lambda *a, **k: "")

    def test_a_probe_that_could_not_run_stops_the_launch(self, driver, tmp_path, monkeypatch):
        self._clean_environment(driver, monkeypatch)
        cfg = self._cfg(driver, tmp_path, {"eve": "print(1)"})
        problems = driver.preflight(
            cfg,
            counting=False,
            identity={
                "eve:loaded": "ERROR: Error response from daemon: No such container: squadops-eve",
                "bob:loaded": "True True",
            },
        )
        assert len(problems) == 1
        assert "LOADED CHECK DID NOT RUN (1)" in problems[0]
        assert "eve:loaded" in problems[0] and "No such container" in problems[0]
        assert "bob:loaded" not in problems[0]

    def test_a_deploy_whose_probes_all_answered_launches(self, driver, tmp_path, monkeypatch):
        """The control: the guard must key on the failure to run, not on probe output —
        a probe printing `False` is a reading, and a reading is not a blocker."""
        self._clean_environment(driver, monkeypatch)
        cfg = self._cfg(driver, tmp_path, {"eve": "print(1)"})
        problems = driver.preflight(
            cfg, counting=False, identity={"eve:loaded": "False False", "head": "abc1234"}
        )
        assert problems == []

    def test_the_shakeout_judges_the_identity_it_records(self, driver, tmp_path, monkeypatch):
        """Wiring, entered where the driver is actually launched (#1250/#1256): preflight
        ran BEFORE the identity was taken, so nothing could have refused on it. Asserts the
        launch is stopped and no cycle is created."""
        self._clean_environment(driver, monkeypatch)
        cfg = self._cfg(driver, tmp_path, {"eve": "print(1)"})
        judged = {"eve:loaded": "ERROR: exit 1", "head": "abc1234"}
        monkeypatch.setattr(driver, "deploy_identity", lambda c: judged)
        monkeypatch.setattr(
            driver, "_run_cycle", lambda *a, **k: pytest.fail("launched on an unverified deploy")
        )
        assert driver.cmd_shakeout(cfg, dry_run=False) == 2

    @pytest.mark.parametrize("filename", sorted(p.name for p in _SETS.glob("*.yaml")))
    def test_every_committed_probe_names_a_deployed_service(self, driver, filename):
        """Broader than the change that prompted it: every set on disk, counting arms,
        A/B arms and diagnostics alike — the defect reached two files because nothing
        looked at the rest."""
        cfg = driver.load_set_config(_SETS / filename)
        assert all(c.service in driver.DEPLOY_SERVICES for c in cfg.loaded_checks)


class TestAFailedEmissionIsCountedOnceNotOncePerArtifact:
    """#1431: the record's "failed emissions banked" counted artifacts.

    #971 banks every artifact of a failed emission — a `qa.test` failure banks its suite,
    its `test_report.md` and its `typed_check_evaluation_*.json` — so one failed emission
    reported as 3. Round 1's halves recorded 0 and round 2's React half recorded 3, which
    reads as "three emissions failed versus none" when one did, and the true figure was
    recoverable only by opening the vault and grouping on `task_id`.
    """

    def _cycle(self, driver, tmp_path, monkeypatch, artifacts):
        """Stub the two seams `collect` reads: the run rows and the artifact dirs."""
        dirs = []
        for i, (task_id, filename) in enumerate(artifacts):
            art = tmp_path / f"art_{i:012x}"
            art.mkdir()
            (art / "metadata.json").write_text(
                json.dumps(
                    {
                        "filename": filename,
                        "metadata": {"task_id": task_id, "emission_status": "failed"},
                    }
                )
            )
            dirs.append(art)

        def fake_psql(query: str) -> str:
            if "from cycle_runs where cycle_id" in query:
                return "1|implementation|completed||run_abc|1800"
            return ""

        monkeypatch.setattr(driver, "psql", fake_psql)
        monkeypatch.setattr(driver, "artifact_dirs", lambda cfg, c, r: dirs)
        import yaml

        p = tmp_path / "set.yaml"
        p.write_text(
            yaml.safe_dump(
                {
                    "name": "t",
                    "project": "group_run",
                    "squad_profile": "full-38",
                    "request_profile": "validated-fullstack",
                    "gate_name": "g",
                    "gate_notes": "g",
                    "launch_notes": "r {roll}/{n}",
                    "shakeout_notes": "s",
                    "n_rolls": 2,
                }
            )
        )
        return driver.collect(driver.load_set_config(p), "cyc_test")

    def test_one_failed_task_banking_three_artifacts_counts_as_one_emission(
        self, driver, tmp_path, monkeypatch
    ):
        """The exact shape of `cyc_69d34bc41c20`: one qa.test failure, three artifacts."""
        rec = self._cycle(
            driver,
            tmp_path,
            monkeypatch,
            [
                ("task-m005-qa.test", "backend/tests/test_runs.py"),
                ("task-m005-qa.test", "test_report.md"),
                ("task-m005-qa.test", "typed_check_evaluation_task_5.json"),
            ],
        )
        assert rec["failed_emissions_banked"] == 1
        assert rec["failed_emission_artifacts_banked"] == 3

    def test_two_failed_tasks_are_two_emissions(self, driver, tmp_path, monkeypatch):
        """The counting must still separate genuinely distinct failures — a fix that
        collapsed everything to 1 would pass the test above and lose the signal."""
        rec = self._cycle(
            driver,
            tmp_path,
            monkeypatch,
            [
                ("task-m005-qa.test", "backend/tests/test_runs.py"),
                ("task-m005-qa.test", "test_report.md"),
                ("task-m008-builder.assemble", "Dockerfile"),
            ],
        )
        assert rec["failed_emissions_banked"] == 2
        assert rec["failed_emission_artifacts_banked"] == 3

    def test_a_clean_roll_reports_zero_on_both_counts(self, driver, tmp_path, monkeypatch):
        rec = self._cycle(driver, tmp_path, monkeypatch, [])
        assert rec["failed_emissions_banked"] == 0
        assert rec["failed_emission_artifacts_banked"] == 0

    def test_an_artifact_with_no_task_id_is_not_folded_into_one_bucket(
        self, driver, tmp_path, monkeypatch
    ):
        """Older banked artifacts predate the `task_id` stamp. Grouping them all under a
        missing key would report N such failures as one; each falls back to its own id."""
        rec = self._cycle(driver, tmp_path, monkeypatch, [("", "a.py"), ("", "b.py")])
        assert rec["failed_emissions_banked"] == 2
        assert rec["failed_emission_artifacts_banked"] == 2
