"""
RuntimeTransactionPort — unit-of-work for atomic multi-port runtime writes
(SIP-0089 §4.5/D25).

The coordinator's transition applies up to three writes across separate ports —
a FocusLease acquisition/release, a RuntimeActivity transition, and the
`AgentRuntimeState.mode` write. Phase 3/4 shipped these as best-effort
compensation (roll a just-acquired lease back if the mode write fails). D25
prescribes wrapping them in **one** Postgres transaction where the ports share a
pool, so a partial failure becomes a transaction *abort* — no stranded leases, no
orphaned activity transitions.

`begin()` yields an **opaque** connection handle to pass as ``conn=`` to the
participating port methods (`RuntimeStatePort.upsert_state`,
`FocusLeasePort.request/release/revoke/get_current_lease`,
`RuntimeActivityPort.get_current_activity/update_state/abort_activity`). Exiting
the context normally commits; raising inside it aborts and rolls back every write
made on the handle. The handle is deliberately untyped here (`Any`) so the port
layer stays driver-agnostic (D26) — only the asyncpg adapter knows it is a
`Connection`.

When no transaction port is wired (or `conn` is omitted), the ports acquire their
own connection and the coordinator keeps its Phase-3/4 compensation behavior — so
this is additive and opt-in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Any


class RuntimeTransactionPort(ABC):
    """Unit of work spanning the runtime persistence ports (§4.5/D25)."""

    @abstractmethod
    def begin(self) -> AbstractAsyncContextManager[Any]:
        """Open a transaction and yield its opaque connection handle.

        Usage::

            async with transaction.begin() as conn:
                await state.upsert_state(new_state, conn=conn)
                ...  # raising here rolls the whole thing back

        Normal exit commits; an exception aborts (rolls back all writes on the
        handle).
        """
