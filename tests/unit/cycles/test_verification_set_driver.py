"""The verification-set driver — the instrument, pinned like any other surface.

Promoted from a session scratchpad after the 1.6.3 and 1.6.4 sets recorded two instrument
defects against it (a stack assumed in code; a log window read without a zone). Each test
here names the launch-time bug it would catch: a driver that misreads the stack opens the
wrong seeded file and reports a P0 that was never checked; a wrong `--since` reads an empty
window and reports "0 empty emissions" for a roll that had one.
"""

from __future__ import annotations

import importlib.util
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
