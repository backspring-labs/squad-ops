"""A Roblox game's Luau runner, as the derivation reads it (#2906; SIP-0112 contract 8, H.6;
SIP-0117 R5.13).

Entered at ``derive_profile``, what a baseline capture calls. Two layouts, both run by a runner
script in the product's own tree (``lune run tests/run.luau``):
- a Rojo project, whose ``default.project.json`` names the sources;
- Roblox's Script Sync, as ``z_tower-ascension`` is laid out: ``src/Server``, ``src/Shared`` and
  ``src/Client`` with its own suffixes, and no project file (the MacBook lane's read, ``ddfd2cf``).

What bugs would these catch?
- A game's ``*.spec.luau`` files refused as unclassed (``test_files_unclassed`` blocks a
  Campaign), the gap the 2.6 spike found.
- A spec file run with the whole suite when a criterion's file is run alone, or its path dropped.
- The product's sources taken for the tests' own, or the runner's tests for the product, so a
  test is written where nothing covers it.
- frktest's output given a reader that can't read it, so a criterion reads unread silently.
- A Lune invocation that isn't a runner (a version probe) read as one.
"""

from __future__ import annotations

import json

import pytest

from squadops.projects.development_configuration import Check
from squadops.projects.profile_derivation import derive_profile  # noqa: I001
from squadops.sandbox.findings import LUAU
from tests.unit.projects.test_profile_derivation import _baseline, _configuration, _gaps

LUNE = (".tools/lune", "run", "tests/run.luau")
SPEC = b"local Scoreboard = require('../src/Shared/Scoreboard')\n"

_ROJO = {
    "default.project.json": json.dumps(
        {
            "name": "door",
            "tree": {
                "$className": "DataModel",
                "ReplicatedStorage": {"Shared": {"$path": "src/shared"}},
                "ServerScriptService": {
                    "Server": {"$path": "src/server"},
                    "Tests": {"$path": "tests"},
                },
            },
        }
    ).encode(),
    "src/shared/Scoreboard.luau": b"return {}\n",
    "src/server/Main.server.luau": b"",
    "tests/run.luau": b"",
    "tests/Scoreboard.spec.luau": SPEC,
}
#: z_tower-ascension's shape: Script Sync, its own suffixes, no project file.
_SCRIPT_SYNC = {
    "src/Server/Game.server.luau": b"",
    "src/Shared/Scoreboard.luau": b"return {}\n",
    "src/Client/Hud.local.luau": b"",
    "tests/run.luau": b"",
    "tests/Scoreboard.spec.luau": SPEC,
}


def _derive(files, argv=LUNE):
    checks = (Check("luau_tests", argv),)
    return derive_profile(files, _configuration(checks), _baseline(checks))


@pytest.mark.parametrize(
    ("files", "covers", "manifests"),
    [
        (_ROJO, ("src/server/**", "src/shared/**"), ("default.project.json",)),
        (_SCRIPT_SYNC, ("src/**",), ()),
    ],
    ids=["rojo", "script-sync"],
)
def test_a_games_luau_runner_owns_its_spec_files_and_covers_its_sources(files, covers, manifests):
    profile = _derive(files)

    [runner] = profile.runners
    assert (runner.runner, runner.roots, runner.file_pattern) == ("luau", ("tests",), "*.spec.luau")
    assert runner.suite_argv == LUNE
    # One spec file runs alone: the runner script takes its path after the script.
    assert runner.single_file_argv == (*LUNE, "{path}")
    assert runner.covers == covers
    assert runner.test_ids == LUAU
    assert profile.runner_for("tests/Scoreboard.spec.luau") is runner
    [luau] = [lang for lang in profile.languages if lang.name == "luau"]
    assert (luau.package_manager, luau.manifests) == (None, manifests)
    # The spec files are the runner's, so nothing is unclassed, and its tests are read one by one.
    assert [
        g for g in _gaps(profile) if g[0] in ("test_files_unclassed", "no_test_id_reader")
    ] == []


@pytest.mark.parametrize(
    ("argv", "runtime"),
    [
        (("zune", "run", "tests/run.luau"), "zune"),
        (("lute", "tests/run.luau"), "lute"),
    ],
)
def test_the_other_luau_runtimes_run_a_runner_script_too(argv, runtime):
    [runner] = _derive(_SCRIPT_SYNC, argv).runners

    assert (runner.runner, runner.roots, runner.single_file_argv) == (
        "luau", ("tests",), (*argv, "{path}")
    )  # fmt: skip


def test_a_project_on_frktest_has_no_reader_and_says_how_to_get_one():
    """frktest's output names neither a failure's kind nor a passing test (SIP-0117 R5.13)."""
    files = {
        **_SCRIPT_SYNC,
        "pesde.toml": b'[dependencies]\nfrktest = { name = "itsfrank/frktest" }\n',
    }

    profile = _derive(files)

    [runner] = profile.runners
    assert runner.test_ids is None
    [gap] = [g for g in profile.gaps if g.id == "no_test_id_reader"]
    assert gap.subject == "luau"
    assert "Luau runner contract (SIP-0117 R5.13)" in gap.closes_by
    [luau] = [lang for lang in profile.languages if lang.name == "luau"]
    assert (luau.package_manager, luau.manifests) == ("pesde", ("pesde.toml",))


@pytest.mark.parametrize(
    "argv",
    [(".tools/lune", "--version"), (".tools/lune", "run"), (".tools/lune", "setup")],
    ids=["version-probe", "no-script", "another-subcommand"],
)
def test_a_lune_call_that_runs_no_script_is_no_runner_and_the_specs_are_unclassed(argv):
    profile = _derive(_SCRIPT_SYNC, argv)

    assert profile.runners == ()
    assert "test_files_unclassed" in [g[0] for g in _gaps(profile)]
