"""Prediction 2's sweep (the 2.4 window's pre-registration §4): its markers, its matchers, and what it
reports. Every suite here is made up for the test; the held-out suite is never read, and the
``no_box`` fixture refuses every way the sweep reaches the deploy.

What bugs would these catch?
- a marker taken from a goal (visible by design), a key, a path, a number or a word too short to
  mean anything, so the sweep "finds" what isn't a leak;
- a step or check value left out (a header, a query string, ``in``, ``contains``), so its leak goes
  unseen;
- a value missed in the form a store writes it in: JSON-escaped, COPY-escaped, or inside LangFuse's
  gzip+base64 full prompt past the display cap (#1756);
- a hit attributed to the wrong table, or a dump's later rows read as an earlier table's;
- the matcher printing a value it found, which would itself carry the held-out step out;
- an unsearched place read as clean: a database or container that didn't answer, a root that isn't
  there, a walk that read nothing, an agent that isn't running, no window cycle to walk;
- the suite's own store or the evaluator's records read as a leak;
- the wrong revision swept, or a malformed suite's error quoting it;
- a marker id an outsider could check against a guessed value.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "heldout_sweep.py"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sweep = _load("heldout_sweep")

from squadops.scenarios.models import parse_suite  # noqa: E402

SECRET_TITLE = "Zephyr Ridge Loop 7731"
SECRET_NAME = "Quillon Varga"
SECRET_WHERE = "Harbor Steps North"
SECRET_HEADER = "trace-Vellum-88"
SECRET_QUERY = "Morrow Basin"
SECRET_IN = "Ostrander Field"
SECRET_CONTAINS = "Kestrel Point"
SECRET_ODD = 'Ané "Qu\\ote" Run'  # a quote, a backslash and an accent: every escaped form differs
SECRET_EMOJI = "Summit 🏔 Dash"


@pytest.fixture(autouse=True)
def no_box(monkeypatch, tmp_path_factory):
    """Every way the sweep reaches the deploy, refused: on the Spark a test that got that far would
    dump the live databases and walk the live containers (2026-10-21, a mutant of this file did).
    - The sweep's functions that reach the box are refused by name.
    - A ``docker`` that refuses comes first on ``PATH``, so a call that gets past them fails
      instead of reaching the live deploy, while a test's own local subprocess still runs."""

    def refused(*args, **kwargs):
        raise AssertionError("the sweep reached the box")

    for name in ("sweep_databases", "walk", "window_cycles", "running_containers"):
        monkeypatch.setattr(sweep, name, refused)
    shim = tmp_path_factory.mktemp("no-docker")
    (shim / "docker").write_text("#!/bin/sh\necho 'docker refused in tests' >&2\nexit 97\n")
    (shim / "docker").chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")


def _suite_doc() -> dict:
    return {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-create",
                "goal": "A created run reads back with its whole title",
                "surfaces": [{"kind": "http_endpoint", "path": "/runs", "method": "POST"}],
                "steps": [
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/runs",
                        "json": {"@Run:title": SECRET_TITLE, "capacity": 3, "tag": "abc"},
                        "save": {"run_id": "id"},
                        "expect_status": 201,
                    },
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/runs/{run_id}/join",
                        "json": {"@Participant:name": SECRET_NAME},
                        "headers": {"X-Trace": SECRET_HEADER, "X-Note": "123456"},
                    },
                    {"action": "http", "method": "GET", "path": f"/runs?near={SECRET_QUERY}&n=5"},
                ],
                "checks": [
                    {"check": "json", "step": 1, "path": "title", "equals": SECRET_TITLE},
                    {
                        "check": "json",
                        "step": 2,
                        "path": "",
                        "where": {"@Run:location": SECRET_WHERE},
                    },
                    {"check": "json", "step": 3, "path": "0.location", "in": [SECRET_IN]},
                    {"check": "json", "step": 3, "path": "", "contains": SECRET_CONTAINS},
                ],
                "fields": {
                    "Run:title": ["title"],
                    "Participant:name": ["name"],
                    "Run:location": ["location", "meeting_location"],
                },
            }
        ],
    }


EXPECTED = [SECRET_TITLE, SECRET_NAME, SECRET_HEADER, SECRET_QUERY, SECRET_WHERE, SECRET_IN,
            SECRET_CONTAINS]  # fmt: skip


def _values(*extra: str) -> dict[str, str]:
    values = {mid: m["value"] for mid, m in sweep.markers(parse_suite(_suite_doc())).items()}
    return values | {sweep.marker_id(v): v for v in extra}


def test_the_markers_are_the_step_and_check_values_and_nothing_else():
    found = sweep.markers(parse_suite(_suite_doc()))

    assert sorted(m["value"] for m in found.values()) == sorted(EXPECTED)
    by_value = {m["value"]: m for m in found.values()}
    assert (by_value[SECRET_HEADER]["where"], by_value[SECRET_QUERY]["where"]) == (
        "step 2",
        "step 3",
    )
    assert (by_value[SECRET_IN]["where"], by_value[SECRET_CONTAINS]["where"]) == (
        "check 3",
        "check 4",
    )
    every = {m["value"] for m in found.values()}
    # Not a goal, a key, a path, a method, a number, a short word, a digit string, or a field name.
    for absent in ("A created run reads back with its whole title", "@Run:title", "/runs", "POST",
                   "abc", "123456", "meeting_location"):  # fmt: skip
        assert absent not in every


def test_a_marker_id_is_keyed_so_a_guess_cant_be_checked_against_it():
    assert sweep.marker_id(SECRET_NAME) != hashlib.sha256(SECRET_NAME.encode()).hexdigest()[:12]
    assert sweep.marker_id(SECRET_NAME) == sweep.marker_id(SECRET_NAME)


def test_a_dump_is_matched_by_table_in_every_form_and_its_counts_are_exact():
    values = _values(SECRET_ODD)
    title, name, odd = (sweep.marker_id(v) for v in (SECRET_TITLE, SECRET_NAME, SECRET_ODD))
    copy_json = json.dumps({"title": SECRET_ODD}).replace("\\", "\\\\")  # json, then COPY
    lines = [
        "SET statement_timeout = 0;\n",
        "COPY public.authoring_envelopes (id, body) FROM stdin;\n",
        f"1\tasked to make {SECRET_TITLE} and {SECRET_TITLE}\n",
        f"2\t{copy_json}\n",
        "\\.\n",
        'COPY public."observations" (id, input) FROM stdin;\n',
        f"9\t{SECRET_NAME}\n",
        "\\.\n",
        f"a stray line naming {SECRET_NAME}\n",
    ]

    hits = sweep.match_dump(lines, values)

    assert {t: dict(c) for t, c in hits.items()} == {
        "authoring_envelopes": {title: 2, odd: 1},
        "observations": {name: 1},
        "-": {name: 1},
    }


def test_a_full_prompt_past_the_display_cap_is_decoded_and_searched():
    """#1756: LangFuse displays 10,000 characters and keeps the whole prompt gzip+base64 in the
    generation's metadata. A value past the cap is only in the blob."""
    prompt = "x" * 12_000 + f" then the step: {SECRET_WHERE}"
    stored = {
        "encoding": "gzip+base64",
        "chars": len(prompt),
        "sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "data": base64.b64encode(gzip.compress(prompt.encode(), mtime=0)).decode(),
    }
    row = f"7\t{prompt[:10_000]}\t{json.dumps({'full_prompt': stored})}\n"
    lines = ["COPY public.observations (id, input, metadata) FROM stdin;\n", row, "\\.\n"]

    hits = sweep.match_dump(lines, _values())

    assert dict(hits["observations"]) == {sweep.marker_id(SECRET_WHERE): 1}


def _run_walker(values: dict[str, str], *roots: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-", *map(str, roots)],
        input=sweep._walker_program(values),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_the_walker_reports_paths_and_ids_and_never_a_value(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "plain.txt").write_text(f"the step said {SECRET_WHERE}")
    (work / "envelope.json").write_text(json.dumps({"t": SECRET_ODD}))
    (work / "emoji.txt").write_text(f"named {SECRET_EMOJI}", encoding="utf-8")
    (work / "clean.txt").write_text("nothing held out")
    (tmp_path / "link.txt").symlink_to(work / "plain.txt")
    values = _values(SECRET_ODD, SECRET_EMOJI)

    done = _run_walker(values, tmp_path, tmp_path / "absent")

    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["hits"] == {
        str(work / "plain.txt"): [sweep.marker_id(SECRET_WHERE)],
        str(work / "envelope.json"): [sweep.marker_id(SECRET_ODD)],
        str(work / "emoji.txt"): [sweep.marker_id(SECRET_EMOJI)],
    }
    assert report["files"] == 4  # the symlink isn't followed or read
    assert report["missing_roots"] == [str(tmp_path / "absent")]
    for value in (*EXPECTED, SECRET_ODD, SECRET_EMOJI):
        assert value not in done.stdout and value not in done.stderr


def test_only_a_place_the_squad_or_product_can_see_counts_as_found_and_unsearched_is_not_clean():
    mid = sweep.marker_id(SECRET_TITLE)
    report = {
        "unsearched": ["agent squadops-joi: not running"],
        "databases": {
            "squadops": {"tables": {"scenario_evaluations": {mid: 3}, "authoring_envelopes": {}}},
            "langfuse": {"tables": {"observations": {mid: 1}}},
            "postgres": {"error": "pg_dump exited 1: permission denied"},
        },
        "containers": {
            "squadops-neo": {"files": 10, "missing_roots": [], "hits": {"/tmp/x.py": [mid]}},
            "squadops-eve": {"error": "the walker exited 126: no python3"},
            "squadops-max": {"files": 4, "missing_roots": [], "hits": {}},
            "squadops-nat": {"files": 0, "missing_roots": ["/home"], "hits": {}},
        },
    }

    assert sweep.found_outside(report) == [
        "agent squadops-joi: not running",
        f"database langfuse, table observations: ['{mid}']",
        "database postgres: not searched (pg_dump exited 1: permission denied)",
        f"container squadops-neo: /tmp/x.py ['{mid}']",
        "container squadops-eve: not searched (the walker exited 126: no python3)",
        "container squadops-nat: roots not there ['/home']",
        "container squadops-nat: no file read",
    ]


def test_the_sweep_walks_every_running_agent_and_names_one_that_isnt(monkeypatch):
    walked: list[str] = []
    clean = {"files": 3, "missing_roots": [], "hits": {}}
    monkeypatch.setattr(sweep, "sweep_databases", lambda values, **_: {"squadops": {"tables": {}}})
    monkeypatch.setattr(sweep, "window_cycles", lambda campaigns: [])
    monkeypatch.setattr(sweep, "expected_agents", lambda: ["squadops-joi", "squadops-neo"])
    monkeypatch.setattr(sweep, "running_containers", lambda: {"squadops-neo"})
    monkeypatch.setattr(sweep, "walk", lambda c, roots, values: walked.append(c) or clean)

    report = sweep.sweep(_values(), [])

    assert walked == ["squadops-runtime-api", "squadops-sandbox-service", "squadops-neo"]
    assert report["unsearched"] == [
        "the vault: no window cycle to walk",
        "agent squadops-joi: not running",
    ]


def test_the_vault_is_walked_at_each_window_cycles_own_directory(monkeypatch):
    """Bug caught: the vault walked at a path its artifacts aren't under, which reads no file and,
    before the zero-files rule, read as clean. Artifacts live at ``data/artifacts/<project>/<cycle>``."""
    walked: dict[str, tuple] = {}
    clean = {"files": 3, "missing_roots": [], "hits": {}}
    monkeypatch.setattr(sweep, "sweep_databases", lambda values, **_: {"squadops": {"tables": {}}})
    monkeypatch.setattr(sweep, "window_cycles", lambda campaigns: ["cyc_aaaaaaaaaaaa", "cyc_b0"])
    monkeypatch.setattr(sweep, "expected_agents", lambda: [])
    monkeypatch.setattr(sweep, "running_containers", lambda: set())
    monkeypatch.setattr(
        sweep, "walk", lambda c, roots, values: walked.setdefault(c, tuple(roots)) and clean
    )

    report = sweep.sweep(_values(), ["cmp_83d63c2ebb50"])

    assert walked["squadops-runtime-api"] == (
        "/app/data/artifacts/group_run/cyc_aaaaaaaaaaaa",
        "/app/data/artifacts/group_run/cyc_b0",
    )
    assert report["unsearched"] == []


def test_the_agents_are_every_service_the_compose_file_builds_from_the_agents_image(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "neo": {"container_name": "squadops-neo",
                            "build": {"context": ".", "dockerfile": "agents/Dockerfile"}},
                    "joi": {"build": {"context": ".", "dockerfile": "agents/Dockerfile"}},
                    "runtime-api": {"build": {"dockerfile": "src/squadops/api/runtime/Dockerfile"}},
                    "redis": {"image": "redis:7"},
                }
            }
        )
    )  # fmt: skip

    assert sweep.expected_agents(compose) == ["joi", "squadops-neo"]


def test_a_campaign_id_that_isnt_one_is_refused_never_dropped():
    """Bug caught: a mistyped id silently dropped, so its cycles are never walked. Refused before
    any query reaches the database."""
    real = _load("heldout_sweep_unpatched")

    with pytest.raises(ValueError, match="not campaign ids"):
        real.window_cycles(["cmp_1234", "cmp_83d63c2ebb50"])


@pytest.mark.parametrize(
    ("found", "code"), [({}, 0), ({"/tmp/leak.txt": ["id"]}, 1)], ids=["clean", "found"]
)
def test_main_exits_by_what_the_sweep_found(tmp_path, monkeypatch, capsys, found, code):
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(_suite_doc()))
    digest = parse_suite(_suite_doc()).digest
    monkeypatch.setattr(
        sweep,
        "sweep",
        lambda values, campaigns, **_: {
            "unsearched": [],
            "databases": {"squadops": {"tables": {}}},
            "containers": {"squadops-neo": {"files": 2, "missing_roots": [], "hits": found}},
        },
    )

    assert sweep.main(["--suite", str(path), "--digest", digest[:8]]) == code
    out = capsys.readouterr().out
    for value in EXPECTED:
        assert value not in out


def test_a_suite_whose_digest_isnt_the_pinned_one_is_refused_before_any_search(tmp_path, capsys):
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(_suite_doc()))

    assert sweep.main(["--suite", str(path), "--digest", "0000000"]) == 2
    assert "not the pinned 0000000" in capsys.readouterr().err


def test_a_suite_that_doesnt_parse_is_refused_without_quoting_it(tmp_path, capsys):
    doc = _suite_doc()
    doc["scenarios"][0]["surfaces"] = [{"kind": SECRET_TITLE, "path": "/runs"}]
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(doc))

    assert sweep.main(["--suite", str(path), "--digest", "0"]) == 2
    err = capsys.readouterr().err
    assert "doesn't parse" in err and SECRET_TITLE not in err


def _browser_suite() -> dict:
    """A page scenario (SIP-0113 §10p): what it types, the text it finds a control by, and the
    words its patterns look for are values; its targets' candidate names are the deliveries' own."""
    return {
        "name": "pages",
        "scenarios": [
            {
                "scenario_id": "join-from-the-page",
                "goal": "A runner joins a run from its page.",
                "surfaces": [{"kind": "page", "path": "/runs/{id}"}],
                "steps": [
                    {"action": "visit", "path": "/runs/r1"},
                    {"action": "fill", "value": "Odalys Fairweather",
                     "target": {"role": "textbox", "names": ["Your name"],
                                "near": {"role": "button", "names": ["Join this run"],
                                         "text": "Lantern Promenade"}}},
                    {"action": "click", "target": {"role": "link", "names": ["Open"],
                                                   "text": "Quarry Overlook"}},
                ],
                "checks": [
                    {"check": "text", "step": 3, "pattern": "Saltmarsh\\ \\(dawn\\)\\s+1\\s*/\\s*5"},
                    {"check": "order", "step": 3, "target": {"role": "listitem"},
                     "patterns": ["(?:Harbor Ridge)", "Mill Lantern"]},
                ],
            }
        ],
    }  # fmt: skip


def test_a_page_scenarios_markers_are_its_values_never_its_targets_names():
    """§10p ruling 9 as built (§10q). Bugs caught: a typed value, a control's text or a pattern's
    words missing from the sweep, so B3 reads clean while a page step leaks; or a candidate name,
    drafted from the deliveries' own labels, counted as a leak in every delivery."""
    values = {m["value"] for m in sweep.markers(parse_suite(_browser_suite())).values()}

    assert values == {
        "Odalys Fairweather", "Lantern Promenade", "Quarry Overlook", "Saltmarsh (dawn)",
        "Harbor Ridge", "Mill Lantern",
    }  # fmt: skip
    assert not {"Your name", "Join this run", "textbox", "listitem"} & values


def test_the_evidence_table_is_searched_as_the_suites_own_store():
    """§10p ruling 9. Bug caught: a page scenario's evidence, which holds its values by design,
    reported as a leak; or the suite's store dropped from the dump's exclusions when a table
    joined it. Read from the command the sweep runs, never by running it."""
    command = sweep.dump_command("squadops")

    assert command[:4] == ["docker", "exec", "squadops-postgres", "pg_dump"]
    assert [a for a in command if a.startswith("--exclude-table=")] == [
        "--exclude-table=public.scenario_evidence",
        "--exclude-table=public.scenario_suites",
    ]


# --- --goals (SIP-0113 §10t ruling 7) --------------------------------------------------------

GOAL = "A created run reads back with its whole title"


def test_the_goal_markers_are_the_goals_and_none_of_the_steps_values():
    """Bug caught: --goals searching for the step values, so a goal copied into a build role's
    prompt passes unfound."""
    found = sweep.goal_markers(parse_suite(_suite_doc()))

    assert [m["value"] for m in found.values()] == [GOAL]
    assert list(found) == [sweep.marker_id(GOAL)]


def test_a_dump_is_counted_by_task_type_where_its_table_names_one():
    """Bug caught: the proposal's rows and another role's counted as one table, so a goal in a
    developer's envelope reads as the proposal's own."""
    values = {sweep.marker_id(GOAL): GOAL}
    lines = [
        "COPY public.authoring_envelopes (envelope_id, run_id, task_id, task_type, seam) FROM stdin;\n",
        f"e1\tr1\tt1\tstrategy.propose_increment\tproposal_writing {GOAL}\n",
        f"e2\tr2\tt2\tdevelopment.develop\tbuild_authoring {GOAL} {GOAL}\n",
        "\\.\n",
        "COPY public.cycle_runs (run_id, notes) FROM stdin;\n",
        f"r1\t{GOAL}\n",
        "\\.\n",
    ]

    hits = sweep.match_dump(lines, values, split_by="task_type")

    mid = sweep.marker_id(GOAL)
    assert {t: dict(c) for t, c in hits.items()} == {
        "authoring_envelopes[strategy.propose_increment]": {mid: 1},
        "authoring_envelopes[development.develop]": {mid: 2},
        "cycle_runs": {mid: 1},
    }


def test_with_goals_only_the_proposals_rows_and_the_evaluators_are_not_found():
    """Bugs caught: the proposal's own rows judged a leak, so every live reading fails; another
    role's row passed; LangFuse's unattributed rows judged or dropped; and a LangFuse dump that
    didn't run read as clean."""
    mid = sweep.marker_id(GOAL)
    databases = {
        "squadops": {
            "tables": {
                "authoring_envelopes[strategy.propose_increment]": {mid: 2},
                "authoring_envelopes[development.develop]": {mid: 1},
                "scenario_evaluations": {mid: 9},
            }
        },
        "langfuse": {"tables": {"observations": {mid: 4}}},
    }
    report = {"unsearched": [], "databases": databases, "containers": {}}

    assert sweep.found_outside(report, goals=True) == [
        f"database squadops, table authoring_envelopes[development.develop]: ['{mid}']"
    ]
    assert sweep.found_outside(report) == [
        f"database squadops, table authoring_envelopes[strategy.propose_increment]: ['{mid}']",
        f"database squadops, table authoring_envelopes[development.develop]: ['{mid}']",
        f"database langfuse, table observations: ['{mid}']",
    ]
    unrun = {**report, "databases": {**databases, "langfuse": {"error": "pg_dump exited 1"}}}
    assert "database langfuse: not searched (pg_dump exited 1)" in sweep.found_outside(
        unrun, goals=True
    )


def test_main_with_goals_reports_langfuse_apart_and_never_prints_a_goal(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(_suite_doc()))
    digest = parse_suite(_suite_doc()).digest
    seen = {}

    def fake_sweep(values, campaigns, *, split_by=None):
        seen.update(values=set(values.values()), split_by=split_by)
        mid = next(iter(values))
        return {
            "unsearched": [],
            "databases": {
                "squadops": {"tables": {}},
                "langfuse": {"tables": {"observations": {mid: 1}}},
            },
            "containers": {"squadops-neo": {"files": 2, "missing_roots": [], "hits": {}}},
        }

    monkeypatch.setattr(sweep, "sweep", fake_sweep)

    assert sweep.main(["--suite", str(path), "--digest", digest[:8], "--goals"]) == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert seen == {"values": {GOAL}, "split_by": "task_type"}
    assert report["mode"] == "goals" and report["langfuse_unattributed"]["observations"]
    assert GOAL not in out
