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


# --- H.33 (#3134): the package roots a Luau product declares -------------------------------------

#: z_tower's shape around its roots: art/ holds Luau that is Studio tooling, never synced (the
#: MacBook lane's read of 0beaac0), so "every folder holding Luau" would name it a package.
_SYNCED_AND_TOOLING = {
    **_SCRIPT_SYNC,
    "art/blender/studio_pull.luau": b"",
    "art/studio-bridge/TABridge.luau": b"",
}


def _declared(*roots):
    import dataclasses

    checks = (Check("luau_tests", LUNE),)
    configuration = dataclasses.replace(_configuration(checks), package_roots=roots)
    return derive_profile(_SYNCED_AND_TOOLING, configuration, _baseline(checks))


def test_the_package_roots_a_luau_product_declares_are_its_package_surfaces():
    """Bugs caught: a Luau product offering no surface, so a Campaign refuses every criterion
    that isn't a scenario (cmp_b7df13549e3d's proposal, three attempts at ``unknown_surface``);
    art/'s tooling named a package; or a declared root the tree doesn't hold named a surface, so
    a criterion is admitted on a package nothing can require."""
    profile = _declared("src/Shared", "src/Server", "src/Client", "src/Gone")

    assert [(s.kind, s.name) for s in profile.public_surfaces] == [
        ("package", "Shared"),
        ("package", "Server"),
        ("package", "Client"),
    ]
    assert ("package_root_missing", "disclosed", None, ("src/Gone/**",)) in _gaps(profile)


def test_a_luau_product_that_declares_no_roots_has_no_package_surface_and_no_gap_for_it():
    """Edge: nothing is guessed from where Luau lives. Bug caught: a fixed src/ or a scan for
    Luau files standing in for the product's own statement."""
    profile = _derive(_SYNCED_AND_TOOLING)

    assert profile.public_surfaces == ()
    assert "package_root_missing" not in [g.id for g in profile.gaps]


@pytest.mark.parametrize(
    ("surface", "admitted"),
    [
        ("Shared.Modules.ShopRules", True),
        # A new module inside a declared package passes by prefix, as a name in a Python one does.
        ("Shared.Modules.Pricing", True),
        ("Shared", True),
        ("blender.studio_pull", False),
        ("SharedModules.X", False),
    ],
)
def test_the_proposal_rails_read_a_luau_products_declared_packages(surface, admitted):
    """Wiring, H.33: the derived profile's document is what a repository-backed proposal's rails
    read (``planning.proposal.product_context``), and ``unknown_surface`` is decided on it. Bug
    caught: the roots derived and never reaching the rails, or a prefix that isn't a package
    (``SharedModules``) admitted."""
    from types import SimpleNamespace

    from squadops.campaigns.change_request import SurfaceKind, _unserved
    from squadops.capabilities.handlers.planning.proposal import product_context

    profile = _declared("src/Shared", "src/Server", "src/Client")
    context = product_context({"profile": profile.to_document()})

    reason = _unserved(SimpleNamespace(surface_kind=SurfaceKind.PACKAGE, surface=surface), context)
    assert (reason is None) is admitted


def test_the_strategy_skill_quotes_the_gap_a_luau_product_discloses_as_it_is_written():
    """``roblox-skills-v2`` (SIP-0116 §17s): a proposal read the gap's "every scenario" as its
    play-scenario criteria and wrote a ``package`` criterion for what a player sees. The skill
    now quotes the gap and says what it is about. Bug caught: the derivation's sentence reworded
    (#3152) and the skill left quoting words no prompt shows."""
    from squadops.capabilities.skillsets import load_skillsets

    (gap,) = [g for g in _derive(_SCRIPT_SYNC).gaps if g.id == "no_start_declaration"]
    skill = load_skillsets()["roblox-increment-design"].skill_files["play-scenario-authoring"]

    quoted = "Outcome Evaluation reads every scenario blocked_unverified"
    assert gap.reason.endswith(quoted)
    assert " ".join(skill["SKILL.md"].split()).count(f'says "{quoted}"') == 1
def test_only_an_operator_names_the_game_profile_and_a_luau_runner_derives_the_neutral_one():
    """Entered at the pin a product's cycle is created with (``development_profile_pin``). Bugs
    caught: the game's profile refused for a product whose runner is Luau (it leaves the suite to
    the product's runner, so nothing contradicts it); and a Luau runner deriving it, which would
    require the Roblox skillsets of any Luau product's squad."""
    from squadops.cycles.development_pin import development_profile_pin

    profile = _derive(_SCRIPT_SYNC)
    planned = {"implementation_plan": True}

    named = development_profile_pin({**planned, "development_profile": "game_dev_roblox"}, profile)
    derived = development_profile_pin(planned, profile)

    assert (named.name, named.origin) == ("game_dev_roblox", "operator")
    assert (derived.name, derived.origin) == ("product_neutral", "derived")
