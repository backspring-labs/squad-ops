"""A runtime-api that cannot bind its cycle ports must not become healthy (2026-09-11).

`_init_cycle_subsystem` caught `Exception` and logged. On deploy B of the 1.7.5 line a
module-scope import of the A2A SDK — which only the agent lock ships — made
`adapters.comms.factory` unimportable in the runtime-api image. The ModuleNotFoundError
became one ERROR line; the container passed its health check, every other route answered,
and `POST /api/v1/cycles` returned 500 `ProjectRegistryPort not configured`. Both arms of
the shakeout pair died on their first call, and nothing in the deploy said why.

The import bug is fixed separately. This is the second half: the seam that turned a fatal
misconfiguration into a silent one. "Silence is not green" is a rule this repo already
holds for verification evidence (SIP-0096 §6.6.3); it holds for composition too.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.api.runtime import main as runtime_main

pytestmark = [pytest.mark.domain_api]


class _Boom(RuntimeError):
    """A wiring failure — the class of error the removed catch used to hide."""


async def test_a_port_that_cannot_be_built_stops_startup(monkeypatch):
    """Bug caught: the API serves with no cycle ports bound.

    Driven at `_init_cycle_subsystem` with one factory broken, which is the shape every
    real instance of this took: an import, a missing dependency, a misconfigured
    provider. The assertion is that it RAISES — not that it logs, and not that it
    returns having set nothing.
    """
    monkeypatch.setattr(
        "adapters.cycles.factory.create_project_registry",
        MagicMock(side_effect=_Boom("registry unavailable")),
    )

    with pytest.raises(_Boom):
        await runtime_main._init_cycle_subsystem(MagicMock(), MagicMock(), None)


async def test_the_failure_reaches_the_caller_that_owns_the_lifespan(monkeypatch):
    """Bug caught: `_startup` grows its own catch and the silence comes back one level up.

    The property is end-to-end — a wiring failure must reach whoever runs the lifespan, or
    the container is healthy again with nothing bound. Asserted through `_startup` rather
    than by reading it, because a `try` added around one call reads innocuous.
    """
    monkeypatch.setattr(
        runtime_main, "create_pool", AsyncMock(return_value=MagicMock()), raising=True
    )
    monkeypatch.setattr(
        runtime_main, "_init_cycle_subsystem", AsyncMock(side_effect=_Boom("wiring"))
    )
    app = MagicMock()
    app.state.config = MagicMock()

    with pytest.raises(_Boom):
        await runtime_main._startup(app)


def test_the_startup_sweeps_still_own_their_best_effort_catches():
    """The reason removing the outer catch is safe, asserted rather than assumed.

    The four post-crash sweeps touch the database and are genuinely allowed to fail — a
    stranded-lease sweep that cannot reach Postgres must not brick a boot. They each hold
    their own `except`, which is why the outer one guarded nothing. If a sweep ever loses
    its catch, a transient blip becomes a boot loop, and this test is where that is
    noticed rather than at 3am.
    """
    import ast
    from pathlib import Path

    source = Path(inspect.getfile(runtime_main)).parent / "startup_reaps.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    guarded = {
        node.name
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and any(isinstance(child, ast.ExceptHandler) for child in ast.walk(node))
    }
    expected = {
        "reap_stranded_leases",
        "reap_stranded_modes",
        "reap_stranded_activities",
        "detect_stranded_cycles",
    }
    assert expected <= guarded, (
        f"{sorted(expected - guarded)} no longer swallow their own failures — with the "
        f"outer catch in _init_cycle_subsystem gone, a transient database error there is "
        f"now a boot loop"
    )
