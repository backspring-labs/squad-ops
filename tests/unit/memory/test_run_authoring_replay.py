"""The replay's host runner (SIP-0110 §0.11–§0.12; slice 2, #2106): what it decides before any case
runs.

What bugs would these catch? A lesson handed to a case whose cutoff its evidence postdates (the
two-units-at-once case, §0.15 temporal validity); a named experiment rerun with a lesson edited,
reported as if it were the frozen one (§0.12 experiment manifest); a rubric's version named while
another version's text reads the outputs (#2313).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadops.memory.replay import CitedEvidence, ReplayLesson

pytestmark = [pytest.mark.domain_memory]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "run_authoring_replay.py"
_spec = importlib.util.spec_from_file_location("run_authoring_replay", _SCRIPT)
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_authoring_replay"] = runner
_spec.loader.exec_module(runner)

T = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)


def _envelope(envelope_id: str, captured: datetime, cycle: str) -> dict:
    return {
        "envelope_id": envelope_id,
        "task_type": "strategy.propose_increment",
        "seam": "proposal_writing",
        "messages_sha256": envelope_id,
        "captured_at": captured.isoformat(),
        "cycle_id": cycle,
        "chat_kwargs": {"model": "qwen3.8:27b"},
    }


def _args(**change) -> Namespace:
    return Namespace(
        **{
            "experiment": "e1",
            "static_guidance": None,
            "generations": 2,
            "seed": 7,
            "rubric": "r@1",
            "framework_git_sha": "99d4a11e",
            **change,
        }
    )


def test_each_case_is_handed_only_lessons_its_cutoff_could_have_seen():
    """Two units at once: the lesson's source failed again between the two targets' captures. It
    reaches the later target only; the earlier one's exclusion is recorded with its reason."""
    lesson = ReplayLesson(
        "pat_a@1",
        "Name the element.",
        (
            CitedEvidence("o1", T - timedelta(hours=2), "cyc_source"),
            CitedEvidence("o2", T + timedelta(minutes=30), "cyc_source"),
        ),
    )
    early = _envelope("env_early", T + timedelta(minutes=10), "cyc_a")
    late = _envelope("env_late", T + timedelta(hours=1), "cyc_b")

    frozen, case_lessons = runner.plan(_args(), [early, late], [lesson])

    assert case_lessons == {
        "env_early": [],
        "env_late": [{"revision_id": "pat_a@1", "claim": "counterfactual"}],
    }
    [excluded] = frozen["excluded"]
    assert (
        excluded["envelope_id"] == "env_early" and "after the target's cutoff" in excluded["reason"]
    )
    assert frozen["arms"] == ["baseline", "scoped_memory"]


def test_a_frozen_experiment_refuses_a_changed_rerun_and_accepts_the_same_one(tmp_path):
    lesson = ReplayLesson("pat_a@1", "Name it.", (CitedEvidence("o1", T - timedelta(hours=1)),))
    envelopes = [_envelope("env_1", T, "cyc_a")]
    frozen, _ = runner.plan(_args(), envelopes, [lesson])
    runner._freeze(tmp_path, frozen)

    again, _ = runner.plan(_args(), envelopes, [lesson])
    runner._freeze(tmp_path, again)  # the same experiment, a later clock: accepted
    edited, _ = runner.plan(
        _args(), envelopes, [ReplayLesson("pat_a@1", "Name it, edited.", lesson.cited)]
    )

    with pytest.raises(SystemExit, match="frozen and differs"):
        runner._freeze(tmp_path, edited)
    assert json.loads((tmp_path / "manifest.json").read_text())["lessons"] == frozen["lessons"]


def _text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def test_a_held_rubric_is_pinned_by_the_text_its_version_names():
    """#2274 edited the rubric from @2 to @3 in place, so an experiment naming @2 was read by @3's
    text. Each version names its own file's text, and @2's is kept for the results scored with it."""
    envelopes = [_envelope("env_1", T, "cyc_a")]
    rubrics = _SCRIPT.parent / "replay_rubrics"

    pinned = {
        version: runner.plan(
            _args(rubric=f"lesson.criterion_already_satisfied@{version}"), envelopes, []
        )[0]["rubric_sha256"]
        for version in ("2", "3")
    }

    assert pinned == {
        "2": _text_sha(rubrics / "criterion_already_satisfied@2.md"),
        "3": _text_sha(rubrics / "criterion_already_satisfied.md"),
    }


@pytest.mark.parametrize("version", ["1", "4"])
def test_a_held_rubric_named_at_a_version_no_file_holds_is_refused(version):
    with pytest.raises(SystemExit, match="holds lesson.criterion_already_satisfied at @2, @3;"):
        runner.plan(
            _args(rubric=f"lesson.criterion_already_satisfied@{version}"),
            [_envelope("env_1", T, "cyc_a")],
            [],
        )


def test_a_rubric_edited_under_its_version_is_a_different_experiment(tmp_path, monkeypatch):
    """The label can't show an in-place edit and the text's hash can, so a frozen experiment refuses
    a rerun whose rubric changed under the same version. A label no file holds records no text."""
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    monkeypatch.setattr(runner, "_RUBRICS", rubrics)
    envelopes = [_envelope("env_1", T, "cyc_a")]
    unheld, _ = runner.plan(_args(rubric="validity@exploratory"), envelopes, [])
    (rubrics / "r.md").write_text("# Rubric `r@1`\n\nRead it.\n", encoding="utf-8")
    runner._freeze(tmp_path, runner.plan(_args(), envelopes, [])[0])
    (rubrics / "r.md").write_text("# Rubric `r@1`\n\nRead it differently.\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="frozen and differs"):
        runner._freeze(tmp_path, runner.plan(_args(), envelopes, [])[0])
    assert unheld["rubric_sha256"] is None


# --- the skills replay (SIP-0116 §17p) -------------------------------------------------------

_SKILL_CASES = """\
# Skill cases `fixture-skills@{version}`
cases:
  - id: strategy-unobservable
    task_type: strategy.propose_increment
    skillset: fixture-design
    swaps:
      - path: [resolved_config, campaign_proposal, objective, statement]
        value: A chime plays when gold is picked up.
    expect: {{stop: "no scenario:"}}
  - id: strategy-capture
    task_type: strategy.propose_increment
    skillset: fixture-design
    expect: {{scenario_criterion: true}}
  - id: qa-capture
    task_type: qa.test
    skillset: fixture-qa
    expect: {{accepted: true, specs_pass: true}}
"""


@pytest.fixture
def cases_dir(tmp_path, monkeypatch):
    held = tmp_path / "skill_replay_cases"
    held.mkdir()
    (held / "fixture-skills.yaml").write_text(_SKILL_CASES.format(version="2"))
    (held / "fixture-skills@1.yaml").write_text(_SKILL_CASES.format(version="1") + "# older\n")
    monkeypatch.setattr(runner, "_SKILL_CASES", held)
    return held


def _typed(envelope_id: str, task_type: str, role: str) -> dict:
    return {**_envelope(envelope_id, T, "cyc_capture"), "task_type": task_type, "role": role}


def test_a_skills_experiment_pins_its_cases_by_text_and_gives_each_case_its_own_envelope(cases_dir):
    """Bugs caught: two cases that start from one capture sharing an id, so one's records
    overwrite the other's; and a cases file edited under the same version reading an experiment
    frozen with the earlier text."""
    cases, text = runner.skill_cases_text("fixture-skills@2")
    envelopes = [
        _typed("env_s", "strategy.propose_increment", "strat"),
        _typed("env_q", "qa.test", "qa"),
    ]

    frozen, case_envelopes, notes = runner.skill_plan(_args(), envelopes, cases, text)

    assert [e["envelope_id"] for e in case_envelopes] == [
        "env_s#strategy-unobservable",
        "env_s#strategy-capture",
        "env_q#qa-capture",
    ]
    assert frozen["arms"] == ["baseline", "skills"]
    assert frozen["rubric"] == "skill-cases.fixture-skills@2"
    assert frozen["rubric_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert frozen["cases"][0]["swaps"] == [
        {
            "path": ["resolved_config", "campaign_proposal", "objective", "statement"],
            "value": "A chime plays when gold is picked up.",
        }
    ]
    assert notes["env_q#qa-capture"]["expect"] == {"accepted": True, "specs_pass": True}
    older, older_text = runner.skill_cases_text("fixture-skills@1")
    assert older.version == "1" and older_text != text


@pytest.mark.parametrize(
    ("cases_id", "says"),
    [
        ("fixture-skills@3", "holds fixture-skills at @1, @2"),
        ("absent@1", "holds absent at no version"),
    ],
)
def test_a_cases_version_no_file_holds_is_refused(cases_dir, cases_id, says):
    with pytest.raises(SystemExit, match=says):
        runner.skill_cases_text(cases_id)


def test_a_cases_file_that_doesnt_read_fails_the_lookup_by_its_name(cases_dir):
    (cases_dir / "broken.yaml").write_text("# Cases\ncases: []\n")

    with pytest.raises(SystemExit, match="broken.yaml: the first line is"):
        runner.skill_cases_text("fixture-skills@2")


@pytest.mark.parametrize(
    ("envelopes", "says"),
    [
        ([_typed("env_q", "qa.test", "qa")], "holds 0 envelopes of strategy.propose_increment"),
        (
            [
                _typed("env_s", "strategy.propose_increment", "strat"),
                _typed("env_s2", "strategy.propose_increment", "strat"),
                _typed("env_q", "qa.test", "qa"),
            ],
            "holds 2 envelopes of strategy.propose_increment",
        ),
    ],
    ids=["none", "two"],
)
def test_a_case_whose_capture_is_missing_or_ambiguous_is_refused(cases_dir, envelopes, says):
    """Bug caught: a case silently skipped because the capture has no task of its type, or run
    on whichever of two captures came first."""
    cases, text = runner.skill_cases_text("fixture-skills@2")

    with pytest.raises(SystemExit, match=says):
        runner.skill_plan(_args(), envelopes, cases, text)


_RUNNER = """\
import pathlib, sys
ok = "ok" in pathlib.Path("tests/Shop.spec.luau").read_text()
print("PASS tests/Lives.spec.luau > a new player starts with five lives")
print("PASS tests/Shop.spec.luau > pays the bonus" if ok else "FAIL tests/Shop.spec.luau > pays the bonus [assertion] expected 11, got 10")
print(f"Tests: {2 if ok else 1} passed, {0 if ok else 1} failed, 0 errored, 0 setup, 2 total")
sys.exit(0 if ok else 1)
"""


@pytest.fixture
def checkout(tmp_path):
    product = tmp_path / "product"
    (product / "tests").mkdir(parents=True)
    (product / "tests" / "run.py").write_text(_RUNNER)
    (product / "tests" / "Lives.spec.luau").write_text("-- the product's own\n")
    (product / ".git").mkdir()
    return product


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("ok", {"passed": ["tests/Shop.spec.luau > pays the bonus"], "failed": []}),
        ("wrong", {"passed": [], "failed": ["tests/Shop.spec.luau > pays the bonus"]}),
    ],
    ids=["passes", "fails"],
)
def test_emitted_specs_are_run_on_a_copy_of_the_product_and_only_their_own_tests_count(
    checkout, spec, expected
):
    """Bugs caught: the product's own passing specs credited to the emitted one, so a spec that
    never ran reads as passing; and the run writing into the checkout it was given."""
    artifacts = [{"name": "tests/Shop.spec.luau", "content": spec}]

    specs = runner.run_specs(checkout, artifacts, (sys.executable, "tests/run.py"))

    assert {
        "passed": specs["passed"],
        "failed": [f.split(" [")[0] for f in specs["failed"]],
    } == expected
    assert not (checkout / "tests" / "Shop.spec.luau").exists()


@pytest.mark.parametrize(
    ("artifacts", "argv", "says"),
    [
        ([{"name": "src/Shop.luau", "content": "x"}], ("true",), "no emitted file is a"),
        (
            [{"name": "tests/Shop.spec.luau", "content": "ok"}],
            ("no-such-runner-binary",),
            "the runner did not run",
        ),
        (
            [{"name": "tests/Shop.spec.luau", "content": "ok"}],
            (sys.executable, "-c", "print('nothing the reader knows')"),
            "unreadable",
        ),
    ],
    ids=["no-spec", "no-runner", "unreadable-output"],
)
def test_a_spec_run_that_shows_nothing_is_a_failure_with_its_reason(
    checkout, artifacts, argv, says
):
    """Bug caught: a missing runtime or an unread run counted as no failures."""
    specs = runner.run_specs(checkout, artifacts, argv)

    assert specs["passed"] == []
    assert any(says in f for f in specs["failed"]), specs


def test_an_emitted_path_that_leaves_the_product_is_refused(checkout):
    with pytest.raises(SystemExit, match="leaves the product"):
        runner.run_specs(checkout, [{"name": "../outside.spec.luau", "content": "x"}], ("true",))


def test_only_the_skills_arm_is_held_to_its_cases_expectation():
    """Bug caught: a baseline, handed no skill, judged against a stop it could never give; or a
    spec expectation read as met when nothing ran it."""
    notes = {
        "env_s#stop": {"expect": {"stop": "no scenario:"}},
        "env_q#qa": {"expect": {"accepted": True, "specs_pass": True}},
    }
    stop = {"skillset": "s", "skill": "k", "opening": "no scenario:", "line": "no scenario: x"}
    spec = [{"name": "tests/Shop.spec.luau", "content": "ok"}]

    def record(envelope_id, case, arm, success, **more):
        return {
            "record": "authoring",
            "envelope_id": envelope_id,
            "case": case,
            "arm": arm,
            "generation": 0,
            "success": success,
            **more,
        }

    records = [
        {"record": "validity", "envelope_id": "env_s#stop", "valid": True},
        record("env_s#stop", "stop", "baseline", True, skill_stop=None),
        record("env_s#stop", "stop", "skills", False, skill_stop=stop),
        record("env_q#qa", "qa", "skills", True, skill_stop=None, artifacts=spec),
    ]
    ran: list[str] = []

    def specs_for(rec):
        ran.append(rec["case"])
        return {"passed": ["tests/Shop.spec.luau > pays the bonus"], "failed": []}

    unrun = runner.judge_records(records, notes, None)
    judged = runner.judge_records(records, notes, specs_for)

    assert [(j["case"], j["arm"], j.get("verdict")) for j in unrun] == [
        ("stop", "baseline", None),
        ("stop", "skills", "met"),
        ("qa", "skills", "not_judged"),
    ]
    assert [j.get("verdict") for j in judged] == [None, "met", "met"]
    assert ran == ["qa"]
    assert judged[2]["specs"]["passed"] == ["tests/Shop.spec.luau > pays the bonus"]
