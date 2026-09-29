"""Write a deploy record: ``python -m squadops.api.runtime.record_deploy < facts.json`` (#1720).

Run by ``rebuild_and_deploy.sh`` as a one-off in the runtime image
(``docker compose run --rm --no-deps -T runtime-api python -m squadops.api.runtime.record_deploy``),
which is the migrations' trust boundary: the runtime's own configuration and database, no
credential, no route. It is a composition root of the runtime API's (composition-roots.md §2):
it builds the deploy registry, the squad-profile port and the LLM port through their factories,
over the one pool (#577).

**The facts on stdin** are what only the host can read, one JSON document:

    {"recorded_by": "rebuild_and_deploy.sh all", "source_revision": "7acc2bc1",
     "services": [{"service": "neo", "image_id": "sha256:…", "revision": "7acc2bc1"}, …]}

To them it adds the digest of every model an enabled agent of any squad profile names, as the
LLM provider reports it, and writes one record. A provider that cannot be listed leaves every
digest ``None`` and says so on stderr; it does not stop the record, whose images are still true.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from squadops.cycles.deploy_record import (
    DeployFactsError,
    DeployRecord,
    model_weights,
    services_from_facts,
)
from squadops.llm.models import ModelInfo
from squadops.ports.cycles.deploy_registry import DeployRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort
from squadops.ports.llm.provider import LLMPort

logger = logging.getLogger(__name__)


async def record_deploy(
    facts: Mapping[str, Any],
    *,
    registry: DeployRegistryPort,
    profiles: SquadProfilePort,
    llm: LLMPort,
    now: datetime | None = None,
) -> DeployRecord:
    """Build the record from the deploy step's facts, the profiles' models and their digests,
    and write it.

    Raises:
        DeployFactsError: the facts name no services, a service without its image, or no writer.
    """
    services = services_from_facts(facts)
    recorded_by = (facts.get("recorded_by") or "").strip()
    if not recorded_by:
        raise DeployFactsError("the deploy facts do not say what is recording them")
    named = {
        agent.model
        for profile in await profiles.list_profiles()
        for agent in profile.agents
        if agent.enabled and agent.model
    }
    try:
        available: list[ModelInfo] = await llm.list_available_models()
    except Exception as exc:  # the provider is down or unreachable: the images are still true
        print(
            f"record_deploy: model digests unavailable ({exc}); recorded as None", file=sys.stderr
        )
        available = []
    source = (facts.get("source_revision") or "").strip()
    record = DeployRecord(
        deploy_id=f"dep_{uuid.uuid4().hex[:12]}",
        recorded_at=now or datetime.now(UTC),
        recorded_by=recorded_by,
        source_revision=source if source and source != "unknown" else None,
        services=services,
        models=model_weights(named, {m.name: m.digest for m in available}),
    )
    await registry.record(record)
    return record


async def _compose_and_record(facts: Mapping[str, Any]) -> DeployRecord:
    from adapters.cycles.factory import create_deploy_registry, create_squad_profile_port
    from adapters.llm.factory import create_llm_provider
    from adapters.persistence.pool import create_pool
    from squadops.config import load_config

    config = load_config()
    pool = await create_pool(config.db.url, min_size=1, max_size=2)
    try:
        selector = config.cycles.registry_provider
        registry = create_deploy_registry(
            selector, **({"pool": pool} if selector == "postgres" else {})
        )
        profile_selector = config.cycles.squad_profile_provider
        profiles = create_squad_profile_port(
            profile_selector, **({"pool": pool} if profile_selector == "postgres" else {})
        )
        llm = create_llm_provider(
            provider=config.llm.provider,
            base_url=config.llm.url,
            timeout_seconds=float(config.llm.timeout),
            api_key=config.llm.api_key,
            **({"default_model": config.llm.model} if config.llm.model else {}),
        )
        return await record_deploy(facts, registry=registry, profiles=profiles, llm=llm)
    finally:
        await pool.close()


def main() -> int:
    try:
        facts = json.load(sys.stdin)
        record = asyncio.run(_compose_and_record(facts))
    except (json.JSONDecodeError, DeployFactsError) as exc:
        print(f"record_deploy: refused: {exc}", file=sys.stderr)
        return 2
    unrevisioned = [s.service for s in record.services if s.revision is None]
    undigested = [m.model for m in record.models if m.digest is None]
    print(
        f"deploy record {record.deploy_id}: {len(record.services)} services "
        f"({len(unrevisioned)} without a revision label), {len(record.models)} models "
        f"({len(undigested)} without a digest{': ' + ', '.join(undigested) if undigested else ''})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
