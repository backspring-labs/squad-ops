"""Every declared route renders (SIP-0109 §8.3; #1705 e, part 3).

The candidate is stood up in the qa container: the backend by the stack's probe profile (the
boot the behavioural probes use, #822) on the port the scaffold's dev proxy targets, the frontend
by its own dev server, which proxies ``/api`` to it. A route with a parameter is brought into
being through the API first, by its seed (the create request the create probe sends). Each page
is then read by headless Chromium, and the ``data-testid`` values it rendered are what is judged.

Anything that could not be read — no browser, an app that did not boot, a seed the app refused —
is ``None`` for that route: unrendered, ``blocked_unverified``, never passed (SIP-0096).
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: The headless browser the qa role's image declares (``agents/instances/qa/system-packages.txt``).
BROWSER = "chromium"
_TESTID = re.compile(r'data-testid="([^"]+)"')


@dataclass(frozen=True)
class RenderProfile:
    """How a stack's application is stood up so its pages can be read (§8.3). The backend is
    booted by the stack's probe profile (#822) on ``backend_port``, the port its frontend proxies
    to; the frontend by ``frontend_argv`` in ``frontend_dir`` after an install there."""

    backend_port: int
    frontend_dir: str
    frontend_argv: tuple[str, ...]


#: Keyed by the ``render_profile`` name a ``ScaffoldStack`` declares, like the probe profiles.
#: A stack that declares none cannot have its pages read: every route is unrendered, blocked.
_PROFILES: dict[str, RenderProfile] = {
    # The scaffold's dev proxy sends ``/api`` to localhost:8000 (``frontend/vite.config.js``).
    "vite_dev_proxy": RenderProfile(
        backend_port=8000,
        frontend_dir="frontend",
        frontend_argv=("npx", "vite", "--host", "127.0.0.1", "--port", "{port}", "--strictPort"),
    ),
}


def render_profile_for(name: str) -> RenderProfile | None:
    return _PROFILES.get(name)


@dataclass(frozen=True)
class RenderSteps:
    """The rendering's side effects, injectable so the orchestration is testable without a
    browser or a Node toolchain. The defaults are the real ones."""

    install_frontend: Callable[[Path], str | None] = field(default=None)  # type: ignore[assignment]
    start: Callable[[Path, list[str]], Any] = field(default=None)  # type: ignore[assignment]
    stop: Callable[[Any], None] = field(default=None)  # type: ignore[assignment]
    ready: Callable[[str, float], bool] = field(default=None)  # type: ignore[assignment]
    seed: Callable[[str, Mapping[str, Any]], Any] = field(default=None)  # type: ignore[assignment]
    dump_dom: Callable[[str], str | None] = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        defaults = {
            "install_frontend": _npm_install,
            "start": _start,
            "stop": _stop,
            "ready": _ready,
            "seed": _seed,
            "dump_dom": _dump_dom,
        }
        for name, step in defaults.items():
            if getattr(self, name) is None:
                object.__setattr__(self, name, step)


def render_routes(
    tree: Mapping[str, str],
    routes: Mapping[str, Any],
    seeds: Mapping[str, Mapping[str, Any]],
    *,
    profile: RenderProfile,
    backend_argv: tuple[str, ...],
    backend_ready_path: str,
    steps: RenderSteps | None = None,
    startup_timeout_s: float = 120.0,
) -> dict[str, frozenset[str] | None]:
    """The test ids each declared route's page rendered, by route; ``None`` for a page that could
    not be read. Every route is answered — an app that would not stand up answers ``None`` for
    all of them, with the reason logged, rather than raising."""
    if not routes:
        return {}
    steps = steps or RenderSteps()
    unread: dict[str, frozenset[str] | None] = {route: None for route in routes}
    # A straggler's late write must not turn a finished reading into a crash.
    with tempfile.TemporaryDirectory(prefix="render-", ignore_cleanup_errors=True) as root:
        workspace = Path(root)
        for path, content in tree.items():
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        failure = steps.install_frontend(workspace / profile.frontend_dir)
        if failure:
            logger.warning("route rendering: frontend install failed: %s", failure)
            return unread
        port = str(profile.backend_port)
        backend = steps.start(workspace, [a.replace("{port}", port) for a in backend_argv])
        ui_port = _free_port()
        frontend = steps.start(
            workspace / profile.frontend_dir,
            [a.replace("{port}", str(ui_port)) for a in profile.frontend_argv],
        )
        try:
            api, ui = f"http://127.0.0.1:{port}", f"http://127.0.0.1:{ui_port}"
            up = steps.ready(api + backend_ready_path, startup_timeout_s) and steps.ready(
                ui + "/", startup_timeout_s
            )
            if not up:
                logger.warning("route rendering: the candidate did not stand up")
                return unread
            rendered: dict[str, frozenset[str] | None] = {}
            for route in routes:
                path = _reachable_path(route, seeds.get(route), api, steps)
                dom = steps.dump_dom(ui + path) if path is not None else None
                rendered[route] = frozenset(_TESTID.findall(dom)) if dom else None
            return rendered
        finally:
            steps.stop(frontend)
            steps.stop(backend)


def _reachable_path(
    route: str, seed: Mapping[str, Any] | None, api: str, steps: RenderSteps
) -> str | None:
    """The concrete path to read ``route`` at, or ``None`` when its page cannot be reached: a
    parameter with no seed, or a seed the app refused or answered without an ``id``."""
    if ":" not in route:
        return route
    if seed is None:
        return None
    created = steps.seed(api + str(seed["path"]), seed["json"])
    identifier = created.get("id") if isinstance(created, Mapping) else None
    if identifier in (None, ""):
        logger.warning("route rendering: seeding %s produced no id", route)
        return None
    return route.replace(f":{seed['param']}", str(identifier))


# --- the real steps ---------------------------------------------------------------------------


def _npm_install(frontend: Path) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, workspace-scoped
            ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
            cwd=str(frontend),
            capture_output=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{type(e).__name__}: {e}"
    if completed.returncode != 0:
        return " ".join(completed.stderr.decode("utf-8", "replace").split())[-500:]
    return None


def _start(cwd: Path, argv: list[str]) -> subprocess.Popen | None:
    """Each server in a session of its own: ``npx`` starts the dev server as a child, and
    stopping ``npx`` alone left that child serving, and writing into the workspace being removed
    (found by the live check on roll 4's app)."""
    try:
        return subprocess.Popen(  # noqa: S603 — fixed argv, workspace-scoped
            argv,
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        logger.warning("route rendering: could not start %s: %s", argv[0], e)
        return None


def _stop(proc: subprocess.Popen | None) -> None:
    """The server's whole process group: the launcher and everything it started."""
    if proc is None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)


def _ready(url: str, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(url, timeout=3).status_code < 500:
                return True
        time.sleep(1)
    return False


def _seed(url: str, body: Mapping[str, Any]) -> Any:
    with contextlib.suppress(httpx.HTTPError, ValueError):
        response = httpx.post(url, json=dict(body), timeout=10)
        if response.is_success:
            return response.json()
    return None


def _dump_dom(url: str) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv
            [
                BROWSER,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--virtual-time-budget=8000",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("route rendering: %s could not read %s: %s", BROWSER, url, e)
        return None
    return completed.stdout or None


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
