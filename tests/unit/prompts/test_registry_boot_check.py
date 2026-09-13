"""The registry must serve every shipped asset before the agent takes a task (#352)."""

from __future__ import annotations

import pytest

from squadops.prompts import registry_check as rc
from squadops.prompts.asset_models import AssetVersionInfo

pytestmark = [pytest.mark.unit]


class _Registry:
    """A registry that serves everything except the ids it is told to lack."""

    def __init__(self, missing=()):
        self.missing = set(missing)
        self.asked: list[str] = []

    async def get_asset_version(self, asset_id):
        self.asked.append(asset_id)
        if asset_id in self.missing:
            return None
        return AssetVersionInfo(asset_id=asset_id, version="3", environment="production")

    async def resolve_system_fragment(self, *a, **k):  # pragma: no cover — port shape
        raise NotImplementedError

    async def resolve_request_template(self, *a, **k):  # pragma: no cover — port shape
        raise NotImplementedError


def test_the_shipped_inventory_is_read_from_the_package_not_typed():
    templates = rc.shipped_request_template_ids()
    assert "request.cycle_emission_retry_feedback" in templates and len(templates) >= 40
    dev = rc.shipped_fragment_ids_for_role("dev")
    assert "identity--dev" in dev and all(f.endswith("--dev") for f in dev)
    assert rc.shipped_fragment_ids_for_role("no-such-role") == []


async def test_a_registry_serving_everything_passes_and_every_shipped_asset_was_asked():
    reg = _Registry()
    n = await rc.verify_registry_serves_shipped_assets(reg, role="qa", provider="langfuse")
    assert n == len(reg.asked) == len(set(reg.asked))
    assert set(rc.shipped_request_template_ids()) <= set(reg.asked)
    assert set(rc.shipped_fragment_ids_for_role("qa")) <= set(reg.asked)


async def test_a_stale_registry_refuses_boot_naming_what_is_missing():
    """The bug this catches: an agent booting fine against a registry that lacks the
    retry-feedback template, and failing hours later at the first aimed retry."""
    reg = _Registry(missing={"request.cycle_emission_retry_feedback", "identity--dev"})
    with pytest.raises(rc.PromptRegistryStaleError) as exc:
        await rc.verify_registry_serves_shipped_assets(reg, role="dev", provider="langfuse")
    assert exc.value.missing == ["request.cycle_emission_retry_feedback", "identity--dev"]
    assert "stale" in str(exc.value) and "identity--dev" in str(exc.value)


async def test_a_fragment_another_role_ships_is_not_this_roles_problem():
    reg = _Registry(missing={"identity--dev"})
    assert await rc.verify_registry_serves_shipped_assets(reg, role="qa", provider="langfuse")
