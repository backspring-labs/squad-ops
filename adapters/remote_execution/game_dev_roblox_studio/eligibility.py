"""The ``roblox-studio`` provider's authority over a product: its eligibility rules (SIP-0117 R4.2,
SIP-0118 phase 2g, #3042; SIP-0116 §17n).

Cycle creation asks it of every Studio tool a cycle's work requires, with the product the cycle
runs on (``ProductView``). A product that breaks a rule is refused as an authorization outcome,
naming the rule and each file or path that breaks it. The rules:

- ``repository_backed``: the provider runs only on a repository-backed Script Sync product. A
  cycle with no product view (a sample application) breaks it. That is never a pass.
- ``script_sync_layout``: every file under the three synced folders (``src/Server``,
  ``src/Shared``, ``src/Client``) is a script this provider places: a ``.server.luau``,
  ``.local.luau`` or ``.luau`` file whose name has no other dot, ``X/init.luau`` as the script
  ``X``, never an ``init.luau`` at a folder's root nor ``X.luau`` beside ``X/init.luau``
  (``place.manifest_scripts``). At least one script is placed.
- ``footprint_scripts_only``: every path the cycle's ruled change request lets it touch is a
  script under a synced folder or a spec (``*.spec.luau``) under ``tests/``. A model, a ``.rbxm``
  or a UI asset needs instances built in Studio, which a change can't carry. Instances made at
  run time are code, so they pass as scripts. **The product's test runner is never a change's:**
  ``tests/run.luau``, its loader and any other non-spec file under ``tests/`` print the very
  ``PASS`` lines acceptance credits a test by (SIP-0117 R5.13; SIP-0109 §24dy), so a change that
  could rewrite them could pass anything. A glob under ``tests/`` is carried only when its tail
  ends ``.spec.luau``. An increment's own cycle has no change request at its creation, because its
  proposal run authors one, so the rule reads the footprint of the repair or retry that carries it.
  The increment's proposal is held to the Campaign's ``allowed_scope``, so its Campaign should
  scope ``src/Server/**``, ``src/Shared/**``, ``src/Client/**`` and ``tests/**/*.spec.luau``.
- **Placed at the worker, not here:** "no attributes or tags on scripts". Script Sync files can't
  carry them, so the tree can't show them. The worker's read-only harness reports any script in the
  three folders carrying attributes or CollectionService tags, and the transaction refuses it as
  ``not_executed``, naming each script (#3039). The place's non-script instances are held
  unchanged by #3039's baseline digest.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from adapters.remote_execution.game_dev_roblox_studio.place import (
    SCRIPT_SUFFIXES,
    SYNCED_FOLDERS,
    manifest_scripts,
)
from adapters.remote_execution.game_dev_roblox_studio.runner import PROVIDER
from squadops.ports.tool_authority import BrokenRule, ProductView

#: Where a criterion's spec lives (the Luau runner contract, SIP-0117 R5.13).
SPECS = "tests/"
SPEC_SUFFIX = ".spec.luau"
_GLOB = re.compile(r"[*?\[]")


class RobloxStudioAuthority:
    """The ``roblox-studio`` provider's authority (``ToolAuthorityPort``), registered at the
    runtime's composition root under ``PROVIDER``."""

    provider = PROVIDER

    async def broken_rules(
        self,
        tool: Any,
        *,
        project_id: str | None,
        config: Mapping[str, Any],
        product: ProductView | None,
    ) -> list[BrokenRule]:
        if product is None:
            return [
                BrokenRule(
                    "repository_backed",
                    f"{PROVIDER} runs only on a repository-backed Script Sync product, and this "
                    "cycle runs on none",
                )
            ]
        return [*await _layout(product), *_footprint(product.footprint)]


async def _layout(product: ProductView) -> list[BrokenRule]:
    synced = [
        p for p in product.paths if any(p.startswith(d + "/") for d in SYNCED_FOLDERS.values())
    ]
    # Paths alone decide the layout: the texts are read only to hand ``manifest_scripts`` its map.
    placed, unplaced = manifest_scripts({p: "" for p in synced})
    rules = [
        BrokenRule(
            "script_sync_layout",
            f"{path} is under a synced folder and isn't a script {PROVIDER} places "
            f"(suffixes {', '.join(s for s, _ in SCRIPT_SUFFIXES)}; X/init.luau is the script X)",
        )
        for path in unplaced
    ]
    if not placed:
        rules.append(
            BrokenRule(
                "script_sync_layout",
                f"Project {product.project_id} at {product.commit[:12]} places no script in "
                f"{', '.join(SYNCED_FOLDERS.values())}",
            )
        )
    return rules


def _footprint(footprint: tuple[str, ...] | None) -> list[BrokenRule]:
    if footprint is None:
        return []
    rules = []
    for entry in footprint:
        why = _not_carried(entry)
        if why is not None:
            rules.append(BrokenRule("footprint_scripts_only", f"{entry} is {why}"))
    return rules


def _not_carried(entry: str) -> str | None:
    """Why a footprint entry, a path or a glob, names what a change can't carry, or ``None``."""
    literal = _GLOB.split(entry, maxsplit=1)[0]
    tail = entry.rsplit("/", 1)[-1]
    if literal.startswith(SPECS):
        # Only specs: whatever else is under tests/ is the product's runner (R5.13).
        if tail.endswith(SPEC_SUFFIX):
            return None
        return (
            f"the product's test runner or its support, which a change can't carry: only "
            f"{SPECS}…{SPEC_SUFFIX} specs are a change's"
        )
    if not any(literal.startswith(d + "/") for d in SYNCED_FOLDERS.values()):
        return (
            f"outside what a change may carry: a script under "
            f"{', '.join(SYNCED_FOLDERS.values())} or a {SPEC_SUFFIX} spec under {SPECS}"
        )
    if _GLOB.search(tail) is None:
        carried = tail.endswith(SCRIPT_SUFFIXES[-1][0])
    else:
        # A glob: refused when what it names is plainly no script, such as ``*.rbxm``.
        suffix = tail.rsplit(".", 1)[-1] if "." in tail else ""
        carried = suffix in ("", "luau") or _GLOB.search(suffix) is not None
    if carried:
        return None
    return (
        f"outside what a change may carry: a script under "
        f"{', '.join(SYNCED_FOLDERS.values())} or a {SPEC_SUFFIX} spec under {SPECS}"
    )


#: What ``factory.create_tool_authorities`` registers for this package (SIP-0116 §17n).
AUTHORITY = RobloxStudioAuthority()
