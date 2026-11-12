"""A cycle's tools, checked at creation: within authority, and available (SIP-0116 §8, §9).

Every tool a required skillset requests for a contract the cycle's work requires is checked
twice, and each failure is its own refusal through the create preflight:

- **authorization:** the authority that governs the operation allows it. An ``agent`` tool is the
  handler's own work. A ``sandbox`` tool is one of the sandbox's typed operations, whose policy
  the service owns. A ``worker`` tool is governed by its provider's registered authority
  (``ToolAuthorityPort``), and a provider that registers none governs nothing, so the tool is
  refused, naming the provider;
- **availability:** a provider can run it now. An ``agent`` tool always can. A ``sandbox`` tool
  can when the runtime binds a sandbox client. A ``worker`` tool can when a registered worker that
  serves it is online (``WorkerRegistry.no_worker_for``). A runtime with no registry has none.

An offline worker reads as availability, and the refusal says the squad still carries the
skillset: the squad is right, and the deployment isn't ready. A cycle whose work requires no
tool, which is every existing stack's, is checked for nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.skillsets import Skillset, ToolRequest
from squadops.cycles.skillset_coverage import AUTHORIZATION, AVAILABILITY, Coverage, CoverageFinding
from squadops.ports.tool_authority import ToolAuthorityPort
from squadops.sandbox.models import OperationName


@dataclass(frozen=True)
class RequiredTool:
    """A tool a required skillset requests for a contract the cycle's work requires."""

    contract: str
    skillset: str
    agent_id: str
    tool: ToolRequest

    @property
    def named(self) -> str:
        return (
            f"tool {self.tool.id} ({self.tool.provider}, at {self.tool.location}) that "
            f"{self.skillset} requests for {self.contract}"
        )


def required_tools(coverage: Coverage, catalog: Mapping[str, Skillset]) -> tuple[RequiredTool, ...]:
    """Each tool the cycle's assigned skillsets request for the contracts its work requires, once
    per contract and skillset. ``coverage`` was read against ``catalog``, so each offer's
    skillset and capability are in it: one that isn't is a defect, and raises."""
    tools: dict[tuple[str, str, str], RequiredTool] = {}
    for offer in coverage.offered:
        capability = catalog[offer.skillset].capability_for(offer.contract)
        if capability is None:
            raise ValueError(
                f"{offer.skillset} is offered for {offer.contract} and doesn't specialize it"
            )
        for tool in capability.tools:
            tools.setdefault(
                (offer.contract, offer.skillset, tool.id),
                RequiredTool(offer.contract, offer.skillset, offer.agent_id, tool),
            )
    return tuple(tools.values())


def authorization_findings(
    tools: tuple[RequiredTool, ...],
    authorities: Mapping[str, ToolAuthorityPort],
    *,
    project_id: str | None,
    config: Mapping[str, Any],
) -> list[CoverageFinding]:
    findings = []
    for required in tools:
        tool = required.tool
        if tool.location == "agent":
            continue
        if tool.location == "sandbox":
            if tool.id not in OperationName.ALL:
                findings.append(
                    CoverageFinding(
                        AUTHORIZATION,
                        f"{required.named} is refused by the sandbox's typed operations: "
                        f"{tool.id!r} isn't one of {sorted(OperationName.ALL)}",
                    )
                )
            continue
        authority = authorities.get(tool.provider)
        if authority is None:
            findings.append(
                CoverageFinding(
                    AUTHORIZATION,
                    f"{required.named} is refused: no authority governs provider "
                    f"{tool.provider} in this deployment, and carrying a skillset never "
                    "authorizes an operation",
                )
            )
            continue
        findings.extend(
            CoverageFinding(
                AUTHORIZATION,
                f"{required.named} is refused by {tool.provider}'s rule {broken.rule}: "
                f"{broken.why}",
            )
            for broken in authority.broken_rules(tool, project_id=project_id, config=config)
        )
    return findings


async def availability_findings(
    tools: tuple[RequiredTool, ...], *, worker_registry: Any, sandbox_client: Any
) -> list[CoverageFinding]:
    findings = []
    for required in tools:
        why = await unavailable(
            required.tool, worker_registry=worker_registry, sandbox_client=sandbox_client
        )
        if why is not None:
            findings.append(
                CoverageFinding(
                    AVAILABILITY,
                    f"{required.named} has no provider available: {why}. The squad still "
                    f"carries {required.skillset}; the deployment can't run its tool now",
                )
            )
    return findings


async def unavailable(
    tool: ToolRequest, *, worker_registry: Any, sandbox_client: Any
) -> str | None:
    """Why no provider can run ``tool`` now, or ``None`` when one can."""
    if tool.location == "agent":
        return None
    if tool.location == "sandbox":
        return None if sandbox_client is not None else "this runtime binds no sandbox client"
    if worker_registry is None:
        return "this runtime holds no worker registry"
    no_worker = await worker_registry.no_worker_for(tool.provider, tool.id)
    return None if no_worker is None else no_worker.reason
