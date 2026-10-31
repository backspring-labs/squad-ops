"""The draft-time check that refuses a held-out marker already public (#2617).

What bugs would these catch? A value the repository tracks, or once tracked and deleted, or a
delivery in the vault holds, passing as a marker the squad couldn't produce; a value printed in the
report; a vault that isn't there read as one with nothing in it; and a suite that doesn't parse
quoted in the error. Every value here is invented.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from squadops.scenarios.models import parse_suite

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "heldout_public_check.py"
_spec = importlib.util.spec_from_file_location("heldout_public_check", _SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

IN_TRACKED = "Tamarind Quay 4410"
IN_HISTORY = "Orrin Velasquez-Pike"
IN_VAULT = "Cobalt Meadow Loop"
NOWHERE = "Brightwater Ferry 77"


def _suite() -> dict:
    return {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-one",
                "goal": "A created thing reads back",
                "surfaces": [{"kind": "http_endpoint", "path": "/things", "method": "POST"}],
                "steps": [
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/things",
                        "json": {"a": IN_TRACKED, "b": IN_HISTORY, "c": IN_VAULT, "d": NOWHERE},
                    }
                ],
                "checks": [{"check": "status", "step": 1, "equals": 201}],
            }
        ],
    }


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def places(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "notes.md").write_text(f"a note naming {IN_HISTORY}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "first")
    (repo / "notes.md").write_text("nothing now\n")
    (repo / "app.py").write_text(f'TITLE = "{IN_TRACKED}"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "second")
    vault = tmp_path / "vault" / "group_run" / "cyc_1" / "run_1" / "art_1"
    vault.mkdir(parents=True)
    (vault / "runs.json").write_text(json.dumps([{"title": IN_VAULT}]))
    suite = tmp_path / "suite.yaml"
    suite.write_text(yaml.safe_dump(_suite()))
    return repo, tmp_path / "vault", suite


def test_a_value_tracked_once_tracked_or_in_the_vault_is_found_and_never_printed(places, capsys):
    """Bugs caught: the history not read, so a value deleted after it was committed passes; the
    vault not read; and a value in the report."""
    repo, vault, suite = places

    code = check.main(["--suite", str(suite), "--repo", str(repo), "--vault", str(vault)])

    out = capsys.readouterr().out
    report = json.loads(out)
    found = list(report["found"].values())
    assert code == 1 and report["markers"] == 4 and report["unsearched"] == []
    # The tracked value is also in the commit that added it; the deleted one in the commits that
    # added and removed it; the vault's only in the vault. The fourth is nowhere.
    assert sorted(
        ((m.get("tracked"), m.get("history_count"), m.get("vault")) for m in found), key=repr
    ) == sorted(
        [
            (["app.py"], 1, None),
            (None, 2, None),
            (None, None, ["group_run/cyc_1/run_1/art_1/runs.json"]),
        ],
        key=repr,
    )
    for value in (IN_TRACKED, IN_HISTORY, IN_VAULT, NOWHERE):
        assert value not in out


def test_each_place_is_counted_for_the_marker_it_holds(places):
    """Bug caught: a hit credited to every marker of the step it came from, so the author is told
    to replace values that are fine."""
    repo, vault, suite = places
    sweep = check._sweep()
    markers = sweep.markers(parse_suite(yaml.safe_load(suite.read_text())))
    by_value = {m["value"]: mid for mid, m in markers.items()}
    matcher = check.Matcher({mid: m["value"] for mid, m in markers.items()}, sweep.forms)

    assert set(check.tracked(repo, matcher)) == {by_value[IN_TRACKED]}
    assert set(check.history(repo, matcher)) == {by_value[IN_TRACKED], by_value[IN_HISTORY]}
    assert set(check.vault(vault, matcher)) == {by_value[IN_VAULT]}


def test_a_vault_that_isnt_there_fails_unless_it_is_declared_absent(places, capsys):
    """Bug caught: an unsearched vault read as one with nothing in it."""
    repo, _vault, suite = places
    (repo / "app.py").write_text("clean\n")
    _git(repo, "commit", "-q", "-am", "clean")
    args = ["--suite", str(suite), "--repo", str(repo), "--vault", str(repo / "absent")]

    assert check.main(args) == 1
    assert "isn't there" in json.loads(capsys.readouterr().out)["unsearched"][0]
    assert check.main([*args, "--no-vault"]) == 1  # the history still holds two values


PATH_VALUE = "qx-unseen-thing-41"
MIXED_RUN = "for Halvard Nettlefield"


def _referencing_suite() -> dict:
    """A scenario that reads an unknown item by a value in its path, and compares one response
    with another through a saved value (SIP-0113 §10ab), as the 2.5 suites do."""
    return {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-refs",
                "goal": "A filed thing reads back, and one never filed isn't found",
                "surfaces": [
                    {"kind": "http_endpoint", "path": "/things", "method": "POST"},
                    {"kind": "http_endpoint", "path": "/things/{thing_id}", "method": "GET"},
                ],
                "steps": [
                    {"action": "http", "method": "POST", "path": "/things",
                     "json": {"title": NOWHERE}, "save": {"thing_id": "id"}},
                    {"action": "http", "method": "GET", "path": f"/things/{PATH_VALUE}",
                     "expect_status": 404},
                    {"action": "http", "method": "GET", "path": "/things/{thing_id}"},
                ],
                "checks": [
                    {"check": "json", "step": 3, "path": "id", "equals": "{thing_id}"},
                    {"check": "json", "step": 3, "path": "note",
                     "equals": f"{{thing_id}} {MIXED_RUN}"},
                ],
            }
        ],
    }  # fmt: skip


def test_the_check_searches_a_paths_values_and_never_a_route_word_or_a_reference(
    tmp_path, monkeypatch, capsys
):
    """#2786, entered at ``main`` as the author runs it. Bugs caught: the value a step reads an
    unknown item by never searched, so a public one passes; a reference (``{thing_id}``) searched
    as a value, found in any file that quotes the route, and reported as public; a route word
    (``things``) reported as public in every repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "routes.md").write_text(f"GET /things/{{thing_id}}, and {PATH_VALUE} is never filed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "routes")
    suite = tmp_path / "suite.yaml"
    suite.write_text(yaml.safe_dump(_referencing_suite()))
    searched: list[set[str]] = []

    class Recorded(check.Matcher):
        def __init__(self, values, forms):
            searched.append(set(values.values()))
            super().__init__(values, forms)

    monkeypatch.setattr(check, "Matcher", Recorded)

    code = check.main(["--suite", str(suite), "--repo", str(repo), "--no-vault"])

    report = json.loads(capsys.readouterr().out)
    assert searched == [{NOWHERE, PATH_VALUE, MIXED_RUN}]
    assert (code, report["markers"]) == (1, 3)
    assert [(m["scenario"], m["where"], m["tracked"]) for m in report["found"].values()] == [
        ("s-refs", "step 2", ["routes.md"])
    ]


def test_a_suite_that_doesnt_parse_is_refused_without_quoting_it(tmp_path, capsys):
    bad = tmp_path / "suite.yaml"
    bad.write_text(f"name: x\nscenarios: [{{scenario_id: s, goal: {IN_TRACKED}}}]\n")

    assert check.main(["--suite", str(bad), "--no-vault"]) == 2
    err = capsys.readouterr().err
    assert "doesn't parse" in err and IN_TRACKED not in err
