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

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
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


async def authorization_findings(
    tools: tuple[RequiredTool, ...],
    authorities: Mapping[str, ToolAuthorityPort],
    *,
    project_id: str | None,
    config: Mapping[str, Any],
    product: Any = None,
) -> list[CoverageFinding]:
    """Each required tool's authorization finding. ``product`` is the cycle's ``ProductView``, or
    ``None`` when it runs on no repository-backed product (SIP-0116 §17n)."""
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
            for broken in await authority.broken_rules(
                tool, project_id=project_id, config=config, product=product
            )
        )
    return findings


#: Why a worker's tool can't run on a runtime that binds no remote execution: the words every
#: reader of that state uses, a cycle's creation and a scenario's reading alike (#3159).
NO_REMOTE_EXECUTION = "this runtime binds no remote execution (remote_execution.provider none)"


@dataclass(frozen=True)
class AgentRemoteExecution:
    """What an agent last said of its own remote-execution port, in its heartbeat (#3235).

    The agent binds that port itself, from its own configuration, when its process starts. The
    runtime's provider says nothing of it: on 2026-11-19 the runtime was switched to
    ``runtime_api`` and rebuilt, the QA agent still bound none, and a cycle was created whose
    in-run evaluation could ask no worker."""

    #: The provider the agent's port binds, as the agent reports it: ``none`` for no port.
    #: ``None`` when its heartbeat names none: an agent built before agents reported it.
    provider: str | None
    #: The commit the agent's image was built from (#1720), its deploy identity.
    revision: str | None
    reported_at: datetime
    #: Whether that heartbeat is inside the runtime's own freshness window.
    fresh: bool


#: Reads an agent's own report by its id, or ``None`` when it has sent none.
AgentReport = Callable[[str], Awaitable["AgentRemoteExecution | None"]]


def agent_cant_ask(
    agent_id: str, report: AgentRemoteExecution | None, *, heard_from_now: bool
) -> str | None:
    """Why ``agent_id`` can't ask a worker for an operation now, by its own report, or ``None``
    when it can (#3235). Every refusal names the component, what was expected of it and what it
    said, the build it runs and when it said so.

    ``heard_from_now`` asks that the report be fresh as well. A cycle's creation asks it: an
    agent not being heard from can't be vouched for. A task's dispatch doesn't: the question
    there is whether the agent was recreated without the provider, and one that was says so in
    its first heartbeat. An agent that is only late with a heartbeat keeps what it last said."""
    if report is None:
        return (
            f"agent {agent_id}, which runs it, has sent this runtime no heartbeat, so whether "
            "it binds remote execution can't be read"
        )
    said = (
        f"at revision {report.revision or 'unrecorded'}, last heard at "
        f"{report.reported_at.isoformat(timespec='seconds')}"
    )
    if heard_from_now and not report.fresh:
        return f"agent {agent_id}, which runs it, isn't being heard from ({said})"
    if report.provider is None:
        return (
            f"agent {agent_id}, which runs it, doesn't say what remote execution it binds "
            f"({said}): it was built before agents reported it"
        )
    if report.provider == "none":
        return (
            f"agent {agent_id}, which runs it, binds no remote execution: expected a provider, "
            f"and it reports remote_execution.provider none ({said}). This runtime binds one, "
            "so the agent wasn't recreated when the provider was set"
        )
    return None


async def availability_findings(
    tools: tuple[RequiredTool, ...],
    *,
    worker_registry: Any,
    sandbox_client: Any,
    remote_execution: Any,
    agent_report: AgentReport | None,
) -> list[CoverageFinding]:
    """Each required tool no provider can run now, as a cycle's creation asks: its agent is
    being heard from as well (``agent_heard_from_now``)."""
    findings = []
    for required in tools:
        why = await unavailable(
            required.tool,
            agent_id=required.agent_id,
            worker_registry=worker_registry,
            sandbox_client=sandbox_client,
            remote_execution=remote_execution,
            agent_report=agent_report,
            agent_heard_from_now=True,
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
    tool: ToolRequest,
    *,
    agent_id: str,
    worker_registry: Any,
    sandbox_client: Any,
    remote_execution: Any,
    agent_report: AgentReport | None,
    agent_heard_from_now: bool,
) -> str | None:
    """Why no provider can run ``tool`` now, or ``None`` when one can.

    A worker's tool needs every part of the way to it:
    - this runtime binds remote execution (``remote_execution``, its own port: ``None`` under
      ``remote_execution.provider none``), and a worker serves the tool (#3159). The registry
      takes a worker's session whatever the provider is, so a worker online says nothing of
      whether an operation would be sent to it;
    - the agent that runs the tool binds remote execution too, by its own report (#3235). It
      asks for the operation through its own port, and the runtime's provider says nothing of
      that one."""
    if tool.location == "agent":
        return None
    if tool.location == "sandbox":
        return None if sandbox_client is not None else "this runtime binds no sandbox client"
    if remote_execution is None:
        return NO_REMOTE_EXECUTION
    if worker_registry is None:
        return "this runtime holds no worker registry"
    if agent_report is None:
        return "this runtime keeps no record of what its agents report, so none can be read"
    cant_ask = agent_cant_ask(
        agent_id, await agent_report(agent_id), heard_from_now=agent_heard_from_now
    )
    if cant_ask is not None:
        return cant_ask
    no_worker = await worker_registry.no_worker_for(tool.provider, tool.id)
    return None if no_worker is None else no_worker.reason
