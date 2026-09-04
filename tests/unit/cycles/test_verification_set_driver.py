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
        [
            ("1-6-5-nextjs.yaml", "nextjs_ts"),
            ("1-6-5-fastapi-react.yaml", "fullstack_fastapi_react"),
            ("1-6-6-nextjs.yaml", "nextjs_ts"),
            ("1-6-6-fastapi-react.yaml", "fullstack_fastapi_react"),
        ],
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

    def test_stack1_seeded_tree_holds_and_records_the_phantom_store(self, driver):
        """Asserted: models.py carries `list[Participant]` (the _py_type pass-through).
        Recorded, not asserted: the per-entity store beyond the roots — #1087's open half."""
        m = manifest_for_stack("fullstack_fastapi_react")
        out = driver.p0_checks(
            "fullstack_fastapi_react", m, _seeded_reader("fullstack_fastapi_react", m)
        )
        assert out["passed"] is True
        assert "participants: list[Participant]" in out["models_expected_collection_lines"]
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
        ("filename", "n"),
        [
            ("1-6-5-nextjs.yaml", 6),
            ("1-6-5-fastapi-react.yaml", 6),
            ("1-6-6-nextjs.yaml", 2),
            ("1-6-6-fastapi-react.yaml", 6),
        ],
    )
    def test_the_counting_sets_are_fully_pinned(self, driver, filename, n):
        """Bug caught: a counting set whose config still carries the shakeout-time blanks —
        the driver would then record instead of assert, and a rebuild mid-set would pass."""
        import re

        cfg = driver.load_set_config(_SETS / filename)
        assert cfg.n_rolls == n
        assert re.fullmatch(r"[0-9a-f]{12,16}", cfg.expected_squad_snapshot_prefix)
        assert re.fullmatch(r"[0-9a-f]{12}", cfg.expected_config_hash_prefix)
        assert re.fullmatch(r"[0-9a-f]{8}", cfg.frozen_deploy_commit)
        assert set(cfg.frozen_image_ids) == set(driver.DEPLOY_SERVICES)
        assert all(re.fullmatch(r"[0-9a-f]{12}", v) for v in cfg.frozen_image_ids.values())

    @pytest.mark.parametrize("line", ["1-6-5", "1-6-6"])
    def test_both_sets_share_the_deploy_and_snapshot_but_not_the_config_hash(self, driver, line):
        a = driver.load_set_config(_SETS / f"{line}-nextjs.yaml")
        b = driver.load_set_config(_SETS / f"{line}-fastapi-react.yaml")
        assert a.frozen_image_ids == b.frozen_image_ids
        assert a.frozen_deploy_commit == b.frozen_deploy_commit
        assert a.expected_squad_snapshot_prefix == b.expected_squad_snapshot_prefix
        assert a.expected_config_hash_prefix != b.expected_config_hash_prefix


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
