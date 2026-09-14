"""SIP-0108 §4.3 (c): the benchmark registry's membership, preflight, lineage and capture.

Entry point for the wiring: ``regrade`` over a real ``MemoryCycleRegistry`` and a real
``FilesystemArtifactVault``, the ports the live stores implement. The capture guards read the
committed membership (``docs/benchmark/rolls.yaml``) and capture (``docs/benchmark/regrade.json``)
against each other and against the 1.7.5 record's headline table: that agreement is the SIP's
acceptance criterion 5.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from adapters.cycles.benchmark_regrade import regrade
from adapters.cycles.cycle_evidence import assess_cycle
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.benchmark_registry import (
    BenchmarkManifestError,
    BenchmarkRoll,
    LineageSource,
    PinnedDeploy,
    PreflightRefusal,
    RollRole,
    benchmark_rolls,
    lineage_for,
    pins_configs,
    preflight,
)
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import aggregate_verification

pytestmark = [pytest.mark.domain_orchestration]

REPO = Path(__file__).resolve().parents[3]
MEMBERSHIP = REPO / "docs" / "benchmark" / "rolls.yaml"
CAPTURE = REPO / "docs" / "benchmark" / "regrade.json"
T0 = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
ASSESSOR = AssessorIdentity(framework_version="1.8.0", git_sha="abc1234")
PINS = PinnedDeploy("8fd30eb8", {"runtime-api": "93c7dd5fd6f5"}, "set.yaml")


def _cycle(cycle_id="cyc_1", *, notes="1.7.5 set — COUNTED roll 2 of 6.", stack="nextjs_ts", **kw):
    return Cycle(
        cycle_id=cycle_id,
        project_id="group_run",
        created_at=T0,
        created_by="admin",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react"},
        execution_overrides={"build_profile": stack},
        request_profile="validated-fullstack",
        notes=notes,
        **kw,
    )


def _roll(cycle_id="cyc_1", *, roll=2, role=RollRole.COUNTED, stack="nextjs_ts", pins=PINS):
    return BenchmarkRoll(cycle_id, "1.7.5 Next.js", "record.md", stack, roll, role, pins)


def _evidence(runs=("run_1",), summaries=("run_1",)) -> CycleEvidence:
    return CycleEvidence(
        cycle_id="cyc_1",
        runs=tuple(
            RunRecord(r, i, "implementation", "completed", T0, T0) for i, r in enumerate(runs)
        ),
        verification_summary_runs=tuple(summaries),
    )


class TestMembership:
    def test_a_set_declares_its_voids_and_counted_rolls_with_lineage_from_its_own_pins(self):
        """Bug caught: a roll number off by the void launch before it, a void carrying the pins of
        the rebuilt deploy its set restarted on, or pins copied rather than read from the config."""
        manifest = {
            "sets": [
                {
                    "name": "1.7.3 FastAPI+React",
                    "record": "r.md",
                    "stack": "fullstack_fastapi_react",
                    "pins_config": "set.yaml",
                    "void": [{"cycle": "cyc_v", "roll": 1, "reason": "#1364"}],
                    "counted": ["cyc_a", "cyc_b"],
                }
            ]
        }
        config = {"frozen_deploy_commit": "933aed95", "frozen_image_ids": {"max": "e640fbb2876b"}}

        rolls = benchmark_rolls(manifest, {"set.yaml": config})

        assert pins_configs(manifest) == ("set.yaml",)
        assert [(r.cycle_id, r.role, r.roll) for r in rolls] == [
            ("cyc_v", RollRole.VOID, 1),
            ("cyc_a", RollRole.COUNTED, 1),
            ("cyc_b", RollRole.COUNTED, 2),
        ]
        assert rolls[0].pins is None and rolls[0].void_reason == "#1364"
        assert rolls[1].pins == PinnedDeploy("933aed95", {"max": "e640fbb2876b"}, "set.yaml")

    @pytest.mark.parametrize(
        ("sets", "configs", "message"),
        [
            (
                [{"counted": ["cyc_a"], "pins_config": "s.yaml"}] * 2,
                {"s.yaml": {"frozen_deploy_commit": "c", "frozen_image_ids": {"max": "i"}}},
                "declared more than once",
            ),
            (
                [{"pins_config": "s.yaml", "void": [{"cycle": "cyc_v", "roll": 1}]}],
                {"s.yaml": {"frozen_deploy_commit": "c", "frozen_image_ids": {"max": "i"}}},
                "has no reason",
            ),
            ([{"pins_config": "s.yaml", "counted": ["cyc_a"]}], {}, "was not loaded"),
            (
                [{"pins_config": "s.yaml", "counted": ["cyc_a"]}],
                {"s.yaml": {"frozen_deploy_commit": "c"}},
                "pins no frozen deploy",
            ),
            ([{"counted": ["cyc_a"]}], {}, "neither pins_config nor pins"),
        ],
        ids=[
            "a cycle twice",
            "a void without reason",
            "config not loaded",
            "config unpinned",
            "no pins",
        ],
    )
    def test_a_membership_the_record_cannot_stand_behind_is_refused(self, sets, configs, message):
        """Bug caught: a row counted twice, a void with no account of why, or a row with lineage
        nobody pinned — each a registry row saying what its record does not."""
        manifest = {"sets": [{"name": "s", "record": "r", "stack": "x", **s} for s in sets]}

        with pytest.raises(BenchmarkManifestError, match=message):
            benchmark_rolls(manifest, configs)


class TestPreflight:
    @pytest.mark.parametrize(
        ("cycle", "roll", "evidence", "refusals"),
        [
            (_cycle(), _roll(), _evidence(), ()),
            (
                _cycle(notes="1.7.3 set — COUNTED roll 1 of 6."),
                _roll(roll=1, role=RollRole.VOID, pins=None),
                _evidence(),
                (),
            ),
            (None, _roll(), None, (PreflightRefusal.NOT_IN_REGISTRY,)),
            (
                _cycle(notes="COUNTED roll 3 of 6"),
                _roll(),
                _evidence(),
                (PreflightRefusal.NOT_LAUNCHED_AS_DECLARED,),
            ),
            (
                _cycle(notes="1.7.5 SHAKEOUT — NON-COUNTING by declaration before launch."),
                _roll(),
                _evidence(),
                (PreflightRefusal.NOT_LAUNCHED_AS_DECLARED,),
            ),
            (_cycle(stack=""), _roll(), _evidence(), (PreflightRefusal.STACK_DISAGREES,)),
            (_cycle(), _roll(), _evidence(runs=(), summaries=()), (PreflightRefusal.NO_RUNS,)),
            (
                _cycle(),
                _roll(),
                _evidence(summaries=()),
                (PreflightRefusal.NO_VERIFICATION_SUMMARY,),
            ),
        ],
        ids=[
            "gradeable",
            "a void launched as roll 1",
            "absent",
            "launched as another roll",
            "a shakeout declared counted",
            "the other stack",
            "no runs",
            "no summary",
        ],
    )
    def test_the_preflight_names_every_reason_a_declared_roll_cannot_be_graded(
        self, cycle, roll, evidence, refusals
    ):
        """§4.3's preflight. Bug caught: a mis-transcribed cycle id graded as a count (a shakeout,
        another roll, the other arm's stack — here an empty override falls back to the profile
        default, React), or a roll with nothing to roll up assessed as if it had."""
        assert preflight(roll, cycle, evidence).refusals == refusals


@pytest.mark.parametrize(
    ("cycle", "roll", "expected"),
    [
        (
            _cycle(framework_version="1.8.0", framework_git_sha="b92f3cf3"),
            _roll(),
            (LineageSource.CYCLE_RECORD, "1.8.0", "b92f3cf3", PINS),
        ),
        (
            _cycle(framework_version="1.8.0"),
            _roll(),
            (LineageSource.SET_PINS, "1.8.0", None, PINS),
        ),
        (_cycle(), _roll(role=RollRole.VOID, pins=None), None),
    ],
    ids=["#80's commit", "a version without a commit", "a void with neither"],
)
def test_lineage_is_the_cycles_commit_else_the_sets_pins_and_never_a_guess(cycle, roll, expected):
    """Bug caught: a version string standing in for a commit, or a void row credited with the
    rebuilt deploy's pins."""
    lineage = lineage_for(roll, cycle)

    if expected is None:
        assert lineage is None
    else:
        assert (
            lineage.source,
            lineage.framework_version,
            lineage.framework_git_sha,
            lineage.pins,
        ) == expected


async def test_the_regrade_keeps_every_declared_roll_and_grades_only_what_its_preflight_admits(
    tmp_path,
):
    """Wiring: ``regrade`` over the ports the live stores implement. Bug caught: a refused roll
    dropped from the registry instead of named, a refused roll assessed anyway, or a re-grade that
    reads different evidence than the live assessment of the same cycle."""
    registry = MemoryCycleRegistry()
    vault = FilesystemArtifactVault(tmp_path / "vault")
    await registry.create_cycle(_cycle())
    await registry.create_cycle(_cycle("cyc_shakeout", notes="SHAKEOUT — NON-COUNTING"))
    for cycle_id in ("cyc_1", "cyc_shakeout"):
        run_id = f"run_{cycle_id}"
        await registry.create_run(
            Run(
                run_id=run_id,
                cycle_id=cycle_id,
                run_number=1,
                status="completed",
                initiated_by="api",
                resolved_config_hash="h",
                started_at=T0,
                finished_at=T0 + timedelta(minutes=46),
                workload_type="implementation",
            )
        )
        await registry.record_run_verification_summary(run_id, aggregate_verification([]))

    rows = await regrade(
        registry,
        vault,
        [_roll(), _roll("cyc_shakeout"), _roll("cyc_gone")],
        assessor=ASSESSOR,
    )

    assert [(r.roll.cycle_id, r.preflight.refusals) for r in rows] == [
        ("cyc_1", ()),
        ("cyc_shakeout", (PreflightRefusal.NOT_LAUNCHED_AS_DECLARED,)),
        ("cyc_gone", (PreflightRefusal.NOT_IN_REGISTRY,)),
    ]
    live = await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)
    assert rows[0].assessment.evidence_identity == live.evidence_identity
    assert rows[0].series.squad_profile_id == "full-38" and rows[0].unresolved_refs == ()
    assert rows[1].assessment is None and rows[2].assessment is None


# --- The committed membership and capture ----------------------------------------------------


@pytest.fixture(scope="module")
def committed():
    manifest = yaml.safe_load(MEMBERSHIP.read_text())
    configs = {p: yaml.safe_load((REPO / p).read_text()) for p in pins_configs(manifest)}
    return benchmark_rolls(manifest, configs), json.loads(CAPTURE.read_text())


def test_the_capture_is_a_grading_of_the_committed_membership(committed):
    """Bug caught: the membership edited (a roll added, a pin moved) without a re-grade, so the
    committed rows describe a registry that is no longer declared — or a capture written while
    a row was refused or cited a record the stores did not hold."""
    rolls, capture = committed

    assert [
        (r["cycle_id"], r["set"], r["roll"], r["role"], (r["lineage"] or {}).get("deploy_commit"))
        for r in capture["rows"]
    ] == [
        (r.cycle_id, r.set_name, r.roll, str(r.role), r.pins.deploy_commit if r.pins else None)
        for r in rolls
    ]
    assert sum(r.role == RollRole.COUNTED for r in rolls) == 79
    assert [
        r["cycle_id"] for r in capture["rows"] if not r["gradeable"] or r["unresolved_refs"]
    ] == []


def _headline_rows(record: Path) -> dict[str, tuple[str, str, int]]:
    """``cycle -> (verdict, criteria, rounds)`` from a set record's headline table."""
    rows = {}
    for line in record.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        match = re.fullmatch(r"`(cyc_[0-9a-f]{12})`", cells[1]) if len(cells) > 5 else None
        if match:
            rows[match.group(1)] = (cells[2].strip("*"), cells[3], int(cells[5]))
    return rows


def test_the_regraded_1_7_5_rows_agree_with_that_records_headline_table(committed):
    """SIP-0108 §5 criterion 5. Bug caught: a re-grade that disagrees with the record on a
    verdict, a criteria count or a correction-round count — the benchmark would then re-write
    history rather than read it."""
    _, capture = committed
    table = _headline_rows(REPO / "docs" / "plans" / "1-7-5-verification-set-record.md")
    regraded = {}
    for row in capture["rows"]:
        if row["set"].startswith("1.7.5"):
            ind = row["assessment"]["indicators"]
            criteria = ind["criteria_coverage"][1]
            regraded[row["cycle_id"]] = (
                ind["verdict"][1],
                f"{criteria['verified']}/{criteria['total']}",
                ind["correction_rounds"][1],
            )

    assert len(table) == 9
    assert regraded == table


def test_the_role_vocabulary_is_the_release_packages():
    """Bug caught: a role added to one vocabulary and not the other — a row the release page
    labels one way and the registry another."""
    path = REPO / "scripts" / "maintainer" / "build_release_package.py"
    spec = importlib.util.spec_from_file_location("build_release_package", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_release_package"] = module
    spec.loader.exec_module(module)

    assert tuple(RollRole) == module.CYCLE_ROLES
