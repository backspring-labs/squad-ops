"""The ``roblox-studio`` provider's eligibility rules (#3042; SIP-0117 R4.2, SIP-0118 phase 2g,
SIP-0116 §17n), entered at ``broken_rules`` as cycle creation asks it, and through the factory the
runtime's root registers it by.

The trees are invented Script Sync layouts, shaped as z_tower-ascension's is: ``src/Server``,
``src/Shared`` and ``src/Client``, its own suffixes, and specs under ``tests/``.
"""

from __future__ import annotations

import pytest

from adapters.remote_execution.factory import create_tool_authorities
from adapters.remote_execution.game_dev_roblox_studio.eligibility import AUTHORITY
from squadops.capabilities.skillsets import ToolRequest
from squadops.capabilities.tool_checks import authorization_findings
from squadops.ports.tool_authority import ProductView

TOOL = ToolRequest("play_scenario", "roblox-studio", "worker")

LAYOUT = (
    "src/Server/Game.server.luau",
    "src/Server/EnemyService/init.luau",
    "src/Server/EnemyService/Spawner.luau",
    "src/Shared/LivesRules.luau",
    "src/Client/Hud.local.luau",
    "tests/run.luau",
    "tests/LivesRules.spec.luau",
    "README.md",
)


def _view(*paths: str, footprint: tuple[str, ...] | None = None) -> ProductView:
    async def read(path: str) -> str:
        return ""

    return ProductView("prj-tower", "a" * 40, tuple(paths), footprint, read)


async def _broken(product: ProductView | None) -> list[tuple[str, str]]:
    rules = await AUTHORITY.broken_rules(TOOL, project_id="prj-tower", config={}, product=product)
    return [(r.rule, r.why) for r in rules]


async def test_a_script_sync_product_with_a_scripts_and_specs_footprint_is_eligible():
    footprint = ("src/Server/**", "src/Shared/LivesRules.luau", "tests/LivesRules.spec.luau")

    assert await _broken(_view(*LAYOUT, footprint=footprint)) == []
    assert await _broken(_view(*LAYOUT, footprint=None)) == []


@pytest.mark.parametrize(
    ("extra", "named"),
    [
        ("src/Shared/Lives.model.luau", None),  # a dot inside the name
        ("src/Server/init.luau", None),  # an init at a folder's root names no script
        # Beside EnemyService/init.luau: two scripts, one name. The second of the pair is named.
        ("src/Server/EnemyService.luau", "src/Server/EnemyService/init.luau"),
        ("src/Client/Hud.rbxm", None),  # a model, which a change can't build
    ],
    ids=["dotted-name", "init-at-the-root", "x-beside-x-init", "a-model"],
)
async def test_a_file_the_provider_cant_place_breaks_the_layout_by_name(extra, named):
    """Bugs caught: a file Studio would place under another name, or not at all, read as part of
    the product, so the copy the worker syncs differs from the repository."""
    [(rule, why)] = await _broken(_view(*LAYOUT, extra))

    assert rule == "script_sync_layout"
    assert why.startswith(f"{named or extra} is under a synced folder")


async def test_a_product_with_no_script_in_the_synced_folders_is_refused():
    [(rule, why)] = await _broken(_view("tests/run.luau", "src/server/main.luau"))

    assert rule == "script_sync_layout"
    assert "places no script in src/Server, src/Shared, src/Client" in why


@pytest.mark.parametrize(
    "entry",
    ["src/Shared/Tower.rbxm", "assets/**", "src/Client/*.rbxmx", "default.project.json"],
)  # fmt: skip
async def test_a_footprint_naming_what_needs_studio_built_instances_is_refused_by_path(entry):
    """Bug caught: an increment allowed to touch a model, a UI asset or a project file, which the
    worker's sync can't carry: the change would land in the repository and never in the place."""
    [(rule, why)] = await _broken(_view(*LAYOUT, footprint=("src/Shared/LivesRules.luau", entry)))

    assert rule == "footprint_scripts_only"
    assert why.startswith(f"{entry} is outside what a change may carry")


@pytest.mark.parametrize(
    "entry",
    [
        "tests/run.luau",
        "tests/loader.luau",
        "tests/**",
        "tests/*.luau",
        "tests/fixtures/rules.json",
    ],
)
async def test_a_footprint_naming_the_products_test_runner_is_refused_by_path(entry):
    """Bug caught (the MacBook lane's review): a change allowed to rewrite ``tests/run.luau`` or
    its loader, which print the ``PASS`` lines acceptance credits a test by (SIP-0117 R5.13,
    SIP-0109 §24dy), so a repair could pass any criterion by printing it passed. A bare
    ``tests/**`` names them too."""
    footprint = ("src/Shared/LivesRules.luau", "tests/**/*.spec.luau", entry)

    [(rule, why)] = await _broken(_view(*LAYOUT, footprint=footprint))

    assert rule == "footprint_scripts_only"
    assert why.startswith(f"{entry} is the product's test runner or its support, which a change")


async def test_a_cycle_on_no_repository_backed_product_breaks_the_provider_never_passes():
    """Bug caught: a sample application's cycle (no product view) read as eligible, so a Studio
    operation runs against a product with no Script Sync tree."""
    assert [rule for rule, _ in await _broken(None)] == ["repository_backed"]


async def test_the_root_registers_it_and_creation_refuses_by_its_rule_as_authorization():
    """Through the factory the composition root calls, and the tool check creation runs. Bug
    caught: the authority never registered, so every Studio tool is refused as ungoverned, or a
    broken rule not reaching creation as an authorization outcome naming it."""
    from squadops.capabilities.tool_checks import RequiredTool

    authorities = create_tool_authorities()
    required = (RequiredTool("play_scenario", "game_dev_roblox_qa", "eve", TOOL),)

    [finding] = await authorization_findings(
        required, authorities, project_id="prj-tower", config={},
        product=_view(*LAYOUT, "src/Client/Hud.rbxm"),
    )  # fmt: skip

    assert authorities["roblox-studio"] is AUTHORITY
    assert finding.kind == "authorization"
    assert "is refused by roblox-studio's rule script_sync_layout: src/Client/Hud.rbxm" in (
        finding.message
    )
