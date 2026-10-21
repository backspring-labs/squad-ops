"""A reference resolver's calls, each under one time bound (#2575; the MacBook lane's G4).

A resolver's ``bind`` runs under the campaign launcher's single lock (SIP-0110 §5ae), so a family
that hangs would stall every campaign. The bound is applied where a family is registered, and an
overrun is a fault, never a refusal.

What bugs would these catch?
- a call with no bound, so a hung family holds every launch behind it;
- an overrun read as a refusal, so the reference is kept unbound for its unit's life where a launch
  would have repeated it;
- a resolver's own ``TimeoutError`` reported as the bound's;
- a family registered without the bound, at the composition root or anywhere else;
- the configured bound not reaching the registry.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from squadops.config.schema import ProjectsConfig
from squadops.memory.cycle_bindings import instructions_bound_for
from squadops.memory.records import InstructionApplicability, PinnedInstruction, Reference
from squadops.memory.reference_binding import bound_instruction
from squadops.memory.resolvers import ReferenceResolvers, ResolverTimedOut, TimeBoundResolver
from squadops.ports.memory.references import (
    BindingContext,
    BoundReference,
    ReferenceResolverPort,
    ReferenceUnresolved,
)

pytestmark = [pytest.mark.domain_memory]

REF = "fake:doc:spec@current"
CTX = BindingContext("group_run", "cycle", "cyc_bound0000", "c0ffee")
BOUND_S = 0.05


class _Hung(ReferenceResolverPort):
    """A family whose every call waits on something that never answers."""

    family = "fake"

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class _OwnTimeout(ReferenceResolverPort):
    """A family that times out on its own, well inside the bound (its git call's own limit)."""

    family = "fake"

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        raise TimeoutError("git cat-file took too long")

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        raise ReferenceUnresolved("not read")


def _pinned() -> PinnedInstruction:
    where = InstructionApplicability(("development.design_plan",), ("*",), ("*",))
    return PinnedInstruction("mrec_ref", 1, "Read the spec.", where, (Reference(REF, True),))


@pytest.mark.parametrize("call", ["bind", "read"])
async def test_a_hung_call_overruns_its_bound_as_a_fault_not_a_refusal(call):
    """Bugs caught: a call with no bound (the test would hang); an overrun raised as
    ``ReferenceUnresolved``, which every caller keeps as unbound."""
    bounded = TimeBoundResolver(_Hung(), BOUND_S)
    invoke = (
        bounded.bind(REF, CTX)
        if call == "bind"
        else bounded.read(BoundReference("fake:doc:spec@r1", "r1", "d"), CTX)
    )

    with pytest.raises(ResolverTimedOut, match=f"fake resolver's {call} overran its 0.05 s bound"):
        await asyncio.wait_for(invoke, timeout=5)


async def test_a_resolvers_own_timeout_is_its_own_not_the_bounds():
    """Bug caught: a resolver's own ``TimeoutError``, raised well inside the bound, reported as an
    overrun of it, which would send the reader to the bound's setting for a fault in git."""
    with pytest.raises(TimeoutError, match="git cat-file took too long") as raised:
        await TimeBoundResolver(_OwnTimeout(), 5).bind(REF, CTX)
    assert not isinstance(raised.value, ResolverTimedOut)


async def test_each_call_site_keeps_its_rule_for_the_fault():
    """Bug caught: an overrun treated as a refusal. A campaign cycle's launch, which binds strictly,
    raises it so the next drain repeats the launch. Admission, which binds once, names the failure
    in the reference's ``unbound``, so a required reference holds its task rather than reading
    unbound content."""
    resolvers = ReferenceResolvers(BOUND_S)
    resolvers.register(_Hung())

    with pytest.raises(ResolverTimedOut):
        await asyncio.wait_for(instructions_bound_for((_pinned(),), resolvers, CTX), timeout=5)
    admitted = await asyncio.wait_for(bound_instruction(_pinned(), resolvers, CTX), timeout=5)
    assert admitted.unbound == ((REF, "the fake resolver failed: ResolverTimedOut"),)


async def test_a_family_can_be_registered_only_under_the_bound():
    """Bugs caught: the registry taking a family by item assignment, unbounded, as the plain dict it
    replaces did; a second registration of a family silently replacing the first."""
    resolvers = ReferenceResolvers(BOUND_S)
    resolvers.register(_Hung())

    with pytest.raises(TypeError):
        resolvers["fake"] = _Hung()  # type: ignore[index]
    with pytest.raises(ValueError, match="fake family has a resolver registered already"):
        resolvers.register(_Hung())
    with pytest.raises(ResolverTimedOut):
        await asyncio.wait_for(resolvers["fake"].bind(REF, CTX), timeout=5)


@pytest.mark.parametrize("seconds", [0, -1])
def test_a_bound_that_isnt_positive_is_refused(seconds):
    """Bug caught: a zero bound, which would fault every call, or a negative one."""
    with pytest.raises(ValueError, match="must be positive"):
        ReferenceResolvers(seconds)


async def test_the_runtime_registers_families_under_its_configured_bound():
    """Entered where the runtime builds it (``main._init_memory``). Bugs caught: the composition
    root still creating a plain dict, which takes an unbounded family; the configured bound not
    reaching the registry."""
    from squadops.api.runtime import main

    state = SimpleNamespace()
    config = SimpleNamespace(
        cycles=SimpleNamespace(registry_provider="memory"),
        projects=ProjectsConfig(reference_resolver_timeout_seconds=BOUND_S),
    )
    main._init_memory(state, config, None)
    state.reference_resolvers.register(_Hung())

    with pytest.raises(ResolverTimedOut, match="overran its 0.05 s bound"):
        await asyncio.wait_for(state.reference_resolvers["fake"].bind(REF, CTX), timeout=5)
    with pytest.raises(TypeError):
        state.reference_resolvers["other"] = _Hung()
