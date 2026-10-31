"""The pre-push scan for held-out step values (the 2.4 window's prediction 2 remedy). Every suite here
is made up for the test; the held-out suite is never read.

What bugs would these catch?
- a push that adds a step value passing unseen, because only some of a change's lines were read;
- a value missed in the escaped form a JSON file or a test fixture writes it in;
- the scan printing the value or the line it found, which would carry the held-out step out itself;
- a clean change refused, or an unreadable suite read as "nothing found";
- the hook scanning in a clone without the suite, or letting a leaking push through where it is.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"
_SCRIPT = _DEV / "heldout_text_scan.py"
_HOOK = _DEV / "hooks" / "pre-push"

_TITLE = "Glasshouse Relay 4410"
_ODD = 'Ané "Qu\\ote" Lap'  # a quote, a backslash and an accent: every escaped form differs


def _load():
    spec = importlib.util.spec_from_file_location("heldout_text_scan", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _suite(tmp_path: Path) -> Path:
    doc = {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-made-up",
                "goal": "A created run reads back with its title",
                "surfaces": [{"kind": "http_endpoint", "path": "/runs", "method": "POST"}],
                "steps": [
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/runs",
                        "json": {"@Run:title": _TITLE, "@Run:location": _ODD},
                        "save": {"run_id": "id"},
                    }
                ],
                "checks": [{"check": "json", "step": 1, "path": "title", "equals": _TITLE}],
                "fields": {"Run:title": ["title"], "Run:location": ["location"]},
            }
        ],
    }
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "notes.py").write_text('"""Examples."""\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _commit(repo: Path, line: str) -> None:
    with (repo / "notes.py").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    _git(repo, "commit", "-q", "-am", "change")


@pytest.mark.parametrize(
    ("added", "found"),
    [
        (f'EXAMPLE = {{"title": "{_TITLE}"}}', 1),
        (f"EXAMPLE = {json.dumps({'location': _ODD})}", 1),
        ('EXAMPLE = {"title": "Morning Loop"}', 0),
    ],
    ids=["a-step-value-as-is", "a-step-value-json-escaped", "a-made-up-value"],
)
def test_a_change_is_read_for_every_step_value_and_reported_without_it(
    tmp_path, repo, monkeypatch, capsys, added, found
):
    """Entered at ``main`` on a real git range, as the hook runs it."""
    suite = _suite(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, added)
    monkeypatch.chdir(repo)

    code = _load().main(["--suite", str(suite), "--range", f"{base}..HEAD"])

    out = capsys.readouterr().out
    report = json.loads(out)
    assert (code, report["found"]) == (1 if found else 0, found)
    assert _TITLE not in out and "Glasshouse" not in out and "Qu" not in out
    if found:
        [hit] = report["sources"][f"git diff {base}..HEAD"]
        assert (hit["scenario"], len(hit["marker"])) == ("s-made-up", 12)


def test_a_post_is_scanned_before_it_goes_out(tmp_path, capsys):
    """Edge: ``--text`` alone, as a pull request's body is scanned before it's posted."""
    suite = _suite(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(f"Fixed the example ({_TITLE}).\n", encoding="utf-8")

    code = _load().main(["--suite", str(suite), "--no-range", "--text", str(body)])

    report = json.loads(capsys.readouterr().out)
    assert (code, report["found"], list(report["sources"])) == (1, 1, [str(body)])


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("The example reads qx-unseen-thing-41 and gets a 404.\n", 1),
        ("The example reads GET /varnholts/{varnholt_id} and compares {varnholt_id}.\n", 0),
    ],
    ids=["a-path-value", "route-words-and-references"],
)
def test_a_post_naming_a_steps_path_value_is_refused_and_one_quoting_its_route_is_not(
    tmp_path, capsys, text, found
):
    """#2786, entered at ``main`` as the hook runs it. Bugs caught: a push that adds the value a
    step reads an unknown item by passing unseen; one that quotes a route or a saved value's
    reference refused, so the supervisor learns to override the scan."""
    doc = {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-unknown",
                "goal": "A varnholt never filed isn't found",
                "surfaces": [
                    {"kind": "http_endpoint", "method": "POST", "path": "/varnholts"},
                    {"kind": "http_endpoint", "method": "GET", "path": "/varnholts/{varnholt_id}"},
                ],
                "steps": [
                    {"action": "http", "method": "POST", "path": "/varnholts",
                     "json": {"title": _TITLE}, "save": {"varnholt_id": "id"}},
                    {"action": "http", "method": "GET", "path": "/varnholts/qx-unseen-thing-41"},
                ],
                "checks": [{"check": "json", "step": 1, "path": "id", "equals": "{varnholt_id}"}],
            }
        ],
    }  # fmt: skip
    suite = tmp_path / "suite.yaml"
    suite.write_text(yaml.safe_dump(doc), encoding="utf-8")
    body = tmp_path / "body.md"
    body.write_text(text, encoding="utf-8")

    code = _load().main(["--suite", str(suite), "--no-range", "--text", str(body)])

    report = json.loads(capsys.readouterr().out)
    assert (code, report["markers"], report["found"]) == (found, 2, found)
    assert [h["where"] for h in report["sources"][str(body)]] == ["step 2"] * found


def test_an_unreadable_suite_is_an_error_that_quotes_nothing(tmp_path, capsys):
    """Edge: a suite that doesn't parse exits 2, naming the file and never its content."""
    broken = tmp_path / "broken.yaml"
    broken.write_text(f"name: x\nscenarios: [{_TITLE}\n", encoding="utf-8")

    code = _load().main(["--suite", str(broken), "--no-range"])

    err = capsys.readouterr().err
    assert code == 2
    assert str(broken) in err and _TITLE not in err


@pytest.mark.parametrize("named", [False, True], ids=["no-suite-named", "the-suite-named"])
def test_the_hook_scans_only_where_the_suite_is(tmp_path, repo, named):
    """The hook, run as git runs it: a ref line on stdin. Bug caught: a clone without the suite
    refused (or slowed) on every push, or a leaking push let through where the suite is."""
    suite = _suite(tmp_path)
    (repo / "scripts" / "dev").mkdir(parents=True)
    for f in ("heldout_text_scan.py", "heldout_sweep.py"):
        shutil.copy(_DEV / f, repo / "scripts" / "dev" / f)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f'EXAMPLE = "{_TITLE}"')
    head = _git(repo, "rev-parse", "HEAD")
    env = {**os.environ, "SQUADOPS_PYTHON": sys.executable}
    env.pop("SQUADOPS_HELDOUT_SUITES", None)
    if named:
        env["SQUADOPS_HELDOUT_SUITES"] = str(suite)

    done = subprocess.run(
        ["bash", str(_HOOK)],
        cwd=repo,
        env=env,
        input=f"refs/heads/main {head} refs/heads/main {base}\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == (1 if named else 0), done.stderr
    assert _TITLE not in done.stdout + done.stderr
