"""Who supplies a remote operation, and with which tool (SIP-0116 §10, SIP-0117 R4.4; #3044).

One resolution, for every caller that asks a provider to run an operation:

- a frozen scenario (``scenario_operation``), which names no contract: plan expansion's appended
  operation step, the baseline step before development and Campaign delivery each ask it, so
  none of them can run a scenario under another tool than the others;
- the tool a supplier requests (``tool_request``), which the operation's handler checks against
  the deployment's catalog.

The supplier is read from the cycle's skillset record, never guessed. The tool is read from the
deployment's catalog, and only when the catalog's skillset is the one the record names by
digest: the kept copy holds skills, not tools, and the digest is what ties the two.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.capability_contracts import VerificationMode
from squadops.capabilities.skillsets import Skillset, ToolRequest
from squadops.tasks.task_types import runs_an_operation

#: The mode a frozen scenario runs in. A scenario declares what a player does, so it is played.
SCENARIO_MODE = VerificationMode.PLAY


class OperationSupplyError(ValueError):
    """No supplier or tool can be named for an operation, with why."""


@dataclass(frozen=True)
class SuppliedOperation:
    """An operation's contract and mode, the skillset the cycle's record says supplies it, and
    the one tool that skillset requests for it."""

    contract: str
    mode: str
    role: str
    skillset: str
    skillset_digest: str
    tool: ToolRequest

    @property
    def provider(self) -> str:
        return self.tool.provider

    @property
    def operation(self) -> str:
        return self.tool.id

    @property
    def location(self) -> str:
        return self.tool.location


def scenario_operation(
    record: Mapping[str, Any] | None, catalog: Mapping[str, Skillset]
) -> SuppliedOperation:
    """The operation a frozen scenario runs under: the one contract the cycle's record offers
    that runs an operation, in ``SCENARIO_MODE``, with its supplier and tool. Raises
    ``OperationSupplyError`` when the record offers none, or more than one supplier: a scenario
    names no contract, so two would be a choice nothing here may make."""
    record = record if isinstance(record, Mapping) else {}
    offers = {
        (row["contract"], row["role"], row["skillset"]): row
        for row in record.get("offered") or ()
        if runs_an_operation(str(row.get("task_type")))
        and (row.get("mode") or "") == SCENARIO_MODE.value
    }
    if not offers:
        raise OperationSupplyError(
            "the cycle's skillset record offers no operation contract in "
            f"`{SCENARIO_MODE.value}` mode, so nothing can run a scenario"
        )
    if len(offers) > 1:
        named = ", ".join(f"{c} by {s} for {r}" for c, r, s in sorted(offers))
        raise OperationSupplyError(
            f"the cycle's skillset record offers more than one supplier of a scenario's "
            f"operation ({named}), and a scenario names none of them"
        )
    return _supplied(record, catalog, next(iter(offers.values())))


def tool_request(catalog: Mapping[str, Skillset], operation: Mapping[str, Any]) -> ToolRequest:
    """The one tool the supplying skillset requests for the operation's contract. Raises
    ``OperationSupplyError`` naming what is wrong: the skillset isn't held, isn't the one the
    cycle recorded, doesn't specialize the contract in this mode, or requests no single tool."""
    skillset = catalog.get(operation["skillset"])
    if skillset is None:
        raise OperationSupplyError(
            f"skillset `{operation['skillset']}` supplies this task by the cycle's record, and "
            "this deployment doesn't hold it"
        )
    if skillset.digest != operation["skillset_digest"]:
        raise OperationSupplyError(
            f"skillset `{skillset.id}` has changed since the cycle was created: the record "
            f"holds digest {operation['skillset_digest']}, and this deployment holds "
            f"{skillset.digest}"
        )
    capability = skillset.capability_for(operation["contract"])
    if capability is None or (
        operation["mode"] and operation["mode"] not in [m.value for m in capability.modes]
    ):
        raise OperationSupplyError(
            f"skillset `{skillset.id}` doesn't specialize `{operation['contract']}`"
            + (f" in `{operation['mode']}` mode" if operation["mode"] else "")
        )
    if len(capability.tools) != 1:
        raise OperationSupplyError(
            f"skillset `{skillset.id}` requests {len(capability.tools)} tools for "
            f"`{operation['contract']}`; the operation to run is the one it requests"
        )
    return capability.tools[0]


def _supplied(
    record: Mapping[str, Any], catalog: Mapping[str, Skillset], offer: Mapping[str, Any]
) -> SuppliedOperation:
    assignment = next(
        (
            row
            for row in record.get("assignment") or ()
            if (row.get("role"), row.get("skillset")) == (offer.get("role"), offer.get("skillset"))
        ),
        None,
    )
    if assignment is None or not assignment.get("digest"):
        raise OperationSupplyError(
            f"the cycle's skillset record offers `{offer['contract']}` by "
            f"`{offer['skillset']}` and holds no assignment of it to `{offer['role']}`"
        )
    operation = {
        "contract": str(offer["contract"]),
        "mode": str(offer.get("mode") or ""),
        "skillset": str(offer["skillset"]),
        "skillset_digest": str(assignment["digest"]),
    }
    return SuppliedOperation(
        contract=operation["contract"],
        mode=operation["mode"],
        role=str(offer["role"]),
        skillset=operation["skillset"],
        skillset_digest=operation["skillset_digest"],
        tool=tool_request(catalog, operation),
    )
