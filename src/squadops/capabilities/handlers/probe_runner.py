"""Behavioral probe runner + default execution profile (SIP-0098 §6.4/§6.5, phase 98.4).

A *probe* (``contract.behavioral.probes``) is the codified manual validation (#376): boot
the declared subject, issue an HTTP request, assert the response status/shape. This module
executes them — the first code that reads ``behavioral.probes`` for execution (98.1–98.3
only lint/bind them).

Two artifacts, deliberately separate (SIP §6.5):

- The **contract's** ``Probe`` states *what must be true* — method, path, expected status/shape.
  Declarative, roll-invariant, sandbox-portable.
- The runner-owned **execution profile** states *how to make it run* — the boot procedure for a
  subject, port allocation, readiness gate, and timeouts. One default ships here; the
  Externalized-Build-Sandbox SIP later ships a second profile that re-homes execution to an
  ephemeral container **without touching a single contract** (§6.5). Capability *requirements*
  (``requires: node``) stay on the contract — they are facts about the check, validated at plan
  time — so the profile only owns mechanics.

Near-term the runner executes where ``frontend_build`` runs today (the qa container has the
Python toolchain). The core is synchronous (boot via ``subprocess.Popen``, request via
``httpx``) so the CI gate (``scripts/dev/contract_gate.py``) calls it directly; the async
qa.test handler wraps it in a thread.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from squadops.cycles.verification_contract import Probe

# The one subject the default profile knows how to boot: a FastAPI backend. A probe whose
# subject the active profile cannot boot is reported skipped (not-executed), never a false pass.
SUBJECT_BACKEND = "backend"


@dataclass(frozen=True)
class ExecutionProfile:
    """How to make a contract's behavioral checks run (SIP §6.5) — intent-free mechanics.

    ``boot_argv`` boots the subject with ``{port}`` substituted at launch; readiness is a
    GET on ``ready_path`` returning 200 within ``startup_timeout_s``. One default ships;
    the sandbox SIP later ships a second, re-homing execution without a contract revision.
    """

    boot_argv: tuple[str, ...]
    ready_path: str = "/health"
    host: str = "127.0.0.1"
    startup_timeout_s: float = 25.0
    request_timeout_s: float = 10.0
    poll_interval_s: float = 0.1


# The default profile: boot the FastAPI backend with uvicorn on an allocated port, using the
# same interpreter (so the qa container's / CI's installed fastapi+uvicorn are on the path).
DEFAULT_PROFILE = ExecutionProfile(
    boot_argv=(
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "{port}",
    ),
)


@dataclass(frozen=True)
class ProbeOutcome:
    """The result of one probe. ``status`` is a ``ResultStatus`` literal (passed/failed/
    skipped) so it flows straight through ``normalize_task_checks``; ``skipped`` means
    not-executed (boot failed / subject unbootable), never a silent pass."""

    id: str
    status: str  # "passed" | "failed" | "skipped"
    reason: str | None = None


def run_probes(
    workspace: Path,
    probes: tuple[Probe, ...] | list[Probe],
    *,
    profile: ExecutionProfile = DEFAULT_PROFILE,
) -> list[ProbeOutcome]:
    """Boot the subject once, run every probe against it, tear it down.

    Bootable-subject probes (``SUBJECT_BACKEND``) drive a single booted process; a probe with
    an unbootable subject is reported ``skipped`` (not-executed). If the subject never becomes
    ready, every backend probe is ``skipped`` with a boot reason — a boot failure is a
    not-executed result, not a probe failure. Returns one ``ProbeOutcome`` per probe, in
    contract order.
    """
    backend = [p for p in probes if p.subject == SUBJECT_BACKEND]
    other = [p for p in probes if p.subject != SUBJECT_BACKEND]
    outcomes: dict[str, ProbeOutcome] = {
        p.id: ProbeOutcome(p.id, "skipped", f"no execution profile boots subject {p.subject!r}")
        for p in other
    }

    if backend:
        outcomes.update({o.id: o for o in _run_backend_probes(workspace, backend, profile)})

    # preserve contract order
    return [outcomes[p.id] for p in probes]


def probe_check_rows(outcomes: list[ProbeOutcome]) -> list[dict[str, Any]]:
    """Adapt probe outcomes to the standard evidence check-row shape (SIP-0098 §6.4).

    Each probe is its own uniquely-identified check: ``check`` (the aggregation key) and
    ``criterion_id`` are both the probe id, so two probes in one task never collapse on
    ``(check_id, subject)``. The ``status`` key is required — ``normalize_task_checks`` only
    carries ``criterion_id`` on the status-bearing branch — so a probe row always traces back
    to its contract criterion in the rollup.
    """
    return [
        {"check": o.id, "status": o.status, "reason": o.reason, "criterion_id": o.id}
        for o in outcomes
    ]


# --------------------------------------------------------------------------- #
# Internals — boot, readiness, request/compare, teardown
# --------------------------------------------------------------------------- #


def _run_backend_probes(
    workspace: Path, probes: list[Probe], profile: ExecutionProfile
) -> list[ProbeOutcome]:
    port = _free_port(profile.host)
    try:
        proc, stderr_spool = _boot(workspace, profile, port)
    except OSError as exc:
        # e.g. the boot command isn't on PATH, or the workspace is missing — a
        # not-executed result (skipped), never a probe failure or a crash.
        return [ProbeOutcome(p.id, "skipped", f"could not launch subject: {exc}") for p in probes]
    try:
        if not _wait_ready(profile, port):
            # #512: "subject did not boot" alone is undiagnosable — disclose the
            # process state (crashed vs never-ready) and the captured stderr tail
            # in the reason, which is the only channel the evidence row carries.
            reason = _boot_failure_reason(proc, stderr_spool, profile)
            return [ProbeOutcome(p.id, "skipped", reason) for p in probes]
        base = f"http://{profile.host}:{port}"
        return [_run_one(base, p, profile) for p in probes]
    finally:
        _terminate(proc)
        with contextlib.suppress(Exception):
            stderr_spool.close()


def _free_port(host: str) -> int:
    """Allocate an ephemeral port. A small TOCTOU window exists between close and boot;
    acceptable for a single-tenant verifier run (the suite runner accepts the same class)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def _boot(workspace: Path, profile: ExecutionProfile, port: int) -> tuple[subprocess.Popen, Any]:
    """Launch the subject, spooling stderr to an unbounded temp file (#512).

    A pipe would deadlock a chatty subject once the ~64KB buffer fills; DEVNULL
    (the previous behavior) destroyed the only diagnosis channel for a boot
    failure. The spool is read only on ready-timeout and closed at teardown.
    """
    argv = [arg.replace("{port}", str(port)) for arg in profile.boot_argv]
    stderr_spool = tempfile.TemporaryFile()
    try:
        proc = subprocess.Popen(  # noqa: S603 — fixed profile argv, workspace-scoped verifier boot
            argv,
            cwd=str(workspace),
            stdout=subprocess.DEVNULL,
            stderr=stderr_spool,
        )
    except OSError:
        stderr_spool.close()
        raise
    return proc, stderr_spool


def _boot_failure_reason(
    proc: subprocess.Popen, stderr_spool: Any, profile: ExecutionProfile
) -> str:
    """Compose the disclosed reason for a subject that never became ready (#512)."""
    exit_code = proc.poll()
    state = (
        f"exited {exit_code}"
        if exit_code is not None
        else f"no ready response within {profile.startup_timeout_s}s"
    )
    reason = f"subject did not boot ({state})"
    tail = _stderr_tail(stderr_spool)
    if tail:
        reason += f": {tail}"
    return reason


def _stderr_tail(stderr_spool: Any, limit: int = 500) -> str:
    """Best-effort whitespace-collapsed tail of the spooled boot stderr."""
    try:
        stderr_spool.seek(0, os.SEEK_END)
        size = stderr_spool.tell()
        stderr_spool.seek(max(0, size - 4096))
        text = stderr_spool.read().decode("utf-8", "replace")
    except Exception:
        return ""
    return " ".join(text.split())[-limit:]


def _wait_ready(profile: ExecutionProfile, port: int) -> bool:
    url = f"http://{profile.host}:{port}{profile.ready_path}"
    deadline = time.monotonic() + profile.startup_timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(profile.poll_interval_s)
    return False


def _run_one(base_url: str, probe: Probe, profile: ExecutionProfile) -> ProbeOutcome:
    method = str(probe.request.get("method", "GET")).upper()
    path = str(probe.request.get("path", "/"))
    body = probe.request.get("json")
    try:
        resp = httpx.request(method, base_url + path, json=body, timeout=profile.request_timeout_s)
    except httpx.HTTPError as exc:
        return ProbeOutcome(probe.id, "failed", f"request error: {exc}")

    expect = probe.expect
    exp_status = expect.get("status")
    if exp_status is not None and resp.status_code != exp_status:
        return ProbeOutcome(
            probe.id, "failed", f"status {resp.status_code} != expected {exp_status}"
        )

    payload = _json_or_none(resp)

    json_has = expect.get("json_has")
    if json_has:
        if payload is None:
            return ProbeOutcome(probe.id, "failed", "response body is not JSON")
        missing = [key for key in json_has if not _has_key(payload, key)]
        if missing:
            return ProbeOutcome(probe.id, "failed", f"response missing key(s): {missing}")

    error_code = expect.get("error_code")
    if error_code is not None:
        actual = _error_code_of(payload)
        if actual != error_code:
            return ProbeOutcome(
                probe.id, "failed", f"error_code {actual!r} != expected {error_code!r}"
            )

    return ProbeOutcome(probe.id, "passed", None)


def _terminate(proc: subprocess.Popen) -> None:
    with contextlib.suppress(Exception):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)


def _json_or_none(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except (ValueError, httpx.HTTPError):
        return None


def _has_key(payload: Any, key: str) -> bool:
    """A probe's ``json_has`` asserts a top-level key is present in the response object,
    or (for a list response) present in each element."""
    if isinstance(payload, dict):
        return key in payload
    if isinstance(payload, list):
        return all(isinstance(item, dict) and key in item for item in payload)
    return False


def _error_code_of(payload: Any) -> Any:
    """Read the ``code`` from the skeleton's pinned error envelope ``{"error": {"code": …}}``."""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            return err.get("code")
        return payload.get("error_code")
    return None
