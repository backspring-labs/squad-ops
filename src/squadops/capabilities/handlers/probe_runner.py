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
import dataclasses
import logging
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

from squadops.cycles.verification_contract import (
    Probe,
    capture_probe_values,
    resolve_probe_path,
)
from squadops.cycles.verification_integrity import ResultStatus

logger = logging.getLogger(__name__)

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
    #: #822: a one-time command run in the workspace *before* boot, for stacks whose subject
    #: cannot run from source. Empty means none — which is every stack that exists today, so
    #: this is inert until one declares it.
    #:
    #: **Why this is not just a longer boot timeout.** Compiling and starting are different
    #: failures with different diagnoses: "the app is slow to start" and "the app does not
    #: build" would otherwise arrive as the same `subject did not boot` reason, and the
    #: build's own output — the only thing that explains it — is on a process that already
    #: exited. Separating them keeps `_boot_failure_reason` meaning what it says.
    prepare_argv: tuple[str, ...] = ()
    #: Generous on purpose: a cold `npm ci` plus a production build is minutes, and this
    #: bound exists to stop a hang, not to police build speed. Boot keeps its 25s.
    prepare_timeout_s: float = 600.0


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

#: #822: per-stack boot, keyed by the ``probe_profile`` name a ``ScaffoldStack`` declares.
#: Registered here rather than derived from the sandbox ``EnvironmentContract``: that contract's
#: ``START_APPLICATION`` argv runs inside the sandbox container against ``.sandbox-venv``, while
#: this boots in the qa container against a fresh temp dir on ``sys.executable``. Two execution
#: contexts, so the interpreter is context-specific and only the launcher and entry point are
#: stack-specific.
_PROFILES: dict[str, ExecutionProfile] = {
    "fastapi_uvicorn": DEFAULT_PROFILE,
    # #822 stack #2, and the first consumer of `prepare_argv` (#827). A Next app cannot run
    # from source: `next build` compiles it, and only then does `next start` serve. Stack #1
    # is interpreted, so its profile declares no preparation and the step stays inert for it.
    "nextjs_next_start": ExecutionProfile(
        # Install *and* build: `next start` serves `.next/`, which only `next build` produces,
        # so a prepare step that stopped at install would boot into "no production build
        # found" and report as a boot failure — the exact conflation #827 separated. `sh -c`
        # for the two-step, matching the sandbox contract's INSTALL_DEPENDENCIES precedent.
        #
        # `npm install`, NOT `npm ci` (roll 10, cyc_43a216d43e1e): the scaffold emits no
        # `package-lock.json` — an offline-deterministic expansion cannot produce one — and
        # `npm ci` EUSAGE-refuses without a lockfile, so every probe on this stack reported
        # "subject preparation failed" with npm's usage text as the tail. Install is also
        # what every other surface runs (the frontend build check and the vitest runner),
        # so preparation cannot succeed or fail differently from the checks beside it.
        prepare_argv=("sh", "-c", "npm install --no-audit --no-fund && npx next build"),
        boot_argv=("npx", "next", "start", "--port", "{port}"),
    ),
}


def profile_for_stack(stack: str) -> ExecutionProfile | None:
    """The boot profile ``stack`` declares, or ``None`` if it declares none (#822).

    ``None`` is the signal to report the backend probes not-executed rather than to boot
    something else: before this, ``run_probes`` took ``DEFAULT_PROFILE`` as a default argument
    and no caller overrode it, so **every stack was booted as FastAPI**. That is loud rather
    than silent — a Node app does not start under ``uvicorn backend.main:app``, so the probes
    skip and SIP-0096 declines to credit them — but "boot the wrong thing and let it fail" is
    a diagnosis the reader has to reconstruct, and a declared refusal is one they are handed.
    """
    from squadops.capabilities.scaffold import probe_profile_for

    name = probe_profile_for(stack)
    return _PROFILES.get(name) if name else None


@dataclass(frozen=True)
class ProbeOutcome:
    """The result of one probe. ``status`` is a ``ResultStatus`` literal (passed/failed/
    skipped) so it flows straight through ``normalize_task_checks``; ``skipped`` means
    not-executed (boot failed / subject unbootable), never a silent pass.

    ``app_traceback`` (#687): the subject's own stack trace for THIS probe's
    failure, read from the stderr spool delta the request produced — the fact
    the analyzer used to guess at (shk-2: two of five correction attempts
    burned repairing guessed causes while the NameError sat in the spool).
    Bounded to the last traceback block; ``None`` when the failure produced
    none (assertion mismatches on healthy responses don't traceback)."""

    id: str
    status: str  # "passed" | "failed" | "skipped"
    reason: str | None = None
    app_traceback: str | None = None


def run_probes(
    workspace: Path,
    probes: tuple[Probe, ...] | list[Probe],
    *,
    profile: ExecutionProfile | None = None,
    stack: str = "",
) -> list[ProbeOutcome]:
    """Boot the subject once, run every probe against it, tear it down.

    Bootable-subject probes (``SUBJECT_BACKEND``) drive a single booted process; a probe with
    an unbootable subject is reported ``skipped`` (not-executed). If the subject never becomes
    ready, every backend probe is ``skipped`` with a boot reason — a boot failure is a
    not-executed result, not a probe failure. Returns one ``ProbeOutcome`` per probe, in
    contract order.

    **How the subject gets booted (#822).** An explicit ``profile`` wins (the test seam); else
    ``stack``'s declared profile; else ``DEFAULT_PROFILE``, which is today's behavior for every
    caller that cannot name a stack and keeps this change inert for them.

    A *registered* stack declaring no profile is the one case that reports not-executed instead
    of booting something: it means a stack was added without saying how to start it, and the
    completeness test in ``test_stack_seams`` is what makes that a build-time error rather than
    a runtime surprise. **This does not raise**, unlike the emitter's refusal in #818, because
    the caller's contract forbids it — ``qa_test`` treats probes as additive evidence that
    "surfaces at the run verdict/rollup, not as a task failure here."
    """
    backend = [p for p in probes if p.subject == SUBJECT_BACKEND]
    other = [p for p in probes if p.subject != SUBJECT_BACKEND]
    outcomes: dict[str, ProbeOutcome] = {
        p.id: ProbeOutcome(p.id, "skipped", f"no execution profile boots subject {p.subject!r}")
        for p in other
    }

    resolved = profile
    if resolved is None:
        resolved = profile_for_stack(stack) if stack else DEFAULT_PROFILE
    if resolved is None:
        logger.warning(
            "probe_boot_profile_missing stack=%s — stack declares no probe_profile, so its "
            "backend probes report not-executed rather than booting another stack's app",
            stack,
        )
        outcomes.update(
            {
                p.id: ProbeOutcome(p.id, "skipped", f"stack {stack!r} declares no probe profile")
                for p in backend
            }
        )
        backend = []

    if backend:
        outcomes.update({o.id: o for o in _run_backend_probes(workspace, backend, resolved)})

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
    rows: list[dict[str, Any]] = []
    for o in outcomes:
        row: dict[str, Any] = {
            "check": o.id,
            "status": o.status,
            "reason": o.reason,
            "criterion_id": o.id,
        }
        # #687: the app-side stack trace rides the evidence row so
        # build_failure_evidence (and through it data.analyze_failure) reads
        # the actual cause instead of inferring plausible classes.
        if o.app_traceback:
            row["app_traceback"] = o.app_traceback
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# Internals — boot, readiness, request/compare, teardown
# --------------------------------------------------------------------------- #


def _run_backend_probes(
    workspace: Path, probes: list[Probe], profile: ExecutionProfile
) -> list[ProbeOutcome]:
    # #822: stacks whose subject cannot run from source build first. Inert for every stack
    # that declares no prepare_argv, which is all of them today.
    prepare_failure = _prepare(workspace, profile)
    if prepare_failure is not None:
        return [ProbeOutcome(p.id, "skipped", prepare_failure) for p in probes]

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
        # #651: sequenced probes share a capture context in contract order —
        # a create's captured id resolves the {run_id} in join/leave paths.
        context: dict[str, str] = {}
        results: list[ProbeOutcome] = []
        for p in probes:
            # #687: bracket each probe with the spool position so a failed
            # probe's app-side stderr (uvicorn writes the exception traceback
            # synchronously with the 500) is attributable to THAT probe.
            spool_start = _spool_size(stderr_spool)
            outcome = _run_one(base, p, profile, context)
            if outcome.status == ResultStatus.FAILED:
                tb = _read_failure_traceback(stderr_spool, spool_start)
                if tb:
                    outcome = dataclasses.replace(outcome, app_traceback=tb)
            results.append(outcome)
        return results
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


#: The prefix every preparation failure carries, so a reader (and the failure analyzer) can
#: tell "it would not build" from "it would not start" without parsing the rest.
PREPARE_FAILURE_PREFIX = "subject preparation failed"


def _prepare(workspace: Path, profile: ExecutionProfile) -> str | None:
    """Run the stack's one-time build, or ``None`` if it declares none (#822).

    Returns a **reason string on failure** rather than raising: a subject that cannot be built
    is not-executed, exactly as a subject that cannot boot is — never a probe failure and never
    a crashed task. The caller turns it into ``skipped`` outcomes.

    Output is captured and tailed for the same reason boot stderr is (#512): a build failure
    disclosed as "preparation failed" and nothing else is undiagnosable, and unlike a boot
    failure there is no surviving process to interrogate afterwards — if the output is not
    captured here it does not exist anywhere.
    """
    if not profile.prepare_argv:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 — fixed profile argv, workspace-scoped
            list(profile.prepare_argv),
            cwd=str(workspace),
            capture_output=True,
            timeout=profile.prepare_timeout_s,
        )
    except subprocess.TimeoutExpired:
        return (
            f"{PREPARE_FAILURE_PREFIX} (no exit within {profile.prepare_timeout_s}s): "
            f"{' '.join(profile.prepare_argv)}"
        )
    except OSError as exc:
        # The build tool is not on PATH, or the workspace is gone. Same class as a boot
        # launch failure, reported at the stage that actually hit it.
        return f"{PREPARE_FAILURE_PREFIX} (could not launch): {exc}"
    if completed.returncode == 0:
        return None
    tail = _output_tail(completed.stderr) or _output_tail(completed.stdout)
    reason = f"{PREPARE_FAILURE_PREFIX} (exited {completed.returncode})"
    return f"{reason}: {tail}" if tail else reason


def _output_tail(raw: bytes | None, limit: int = 500) -> str:
    """Whitespace-collapsed tail of captured build output. Bounded like ``_stderr_tail``:
    a build's full log would swamp the evidence row it has to ride on."""
    if not raw:
        return ""
    return " ".join(raw.decode("utf-8", "replace").split())[-limit:]


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


def _spool_size(stderr_spool: Any) -> int:
    """Current end position of the spool (the child appends behind us)."""
    try:
        stderr_spool.seek(0, os.SEEK_END)
        return int(stderr_spool.tell())
    except Exception:
        return 0


def _read_spool_from(stderr_spool: Any, start: int) -> str:
    """Best-effort read of everything the subject wrote after ``start``."""
    try:
        stderr_spool.seek(start)
        return stderr_spool.read().decode("utf-8", "replace")
    except Exception:
        return ""


# Bounded per the issue: the last traceback only, never raw log dumps.
_TRACEBACK_MAX_CHARS = 2000
_TRACEBACK_MARKER = "Traceback (most recent call last):"

# The subject's logger flushes the exception traceback asynchronously — the
# 500 response lands ~50ms before the stderr write (measured). A short grace
# poll on FAILED probes only; a failure with no traceback (assertion mismatch
# on a healthy response) pays the full window once, bounded and rare.
_TRACEBACK_GRACE_S = 0.5
_TRACEBACK_POLL_S = 0.05


def _read_failure_traceback(stderr_spool: Any, start: int) -> str | None:
    """The failed probe's traceback from its spool delta, with a grace poll."""
    deadline = time.monotonic() + _TRACEBACK_GRACE_S
    while True:
        tb = _extract_last_traceback(_read_spool_from(stderr_spool, start))
        if tb is not None or time.monotonic() >= deadline:
            return tb
        time.sleep(_TRACEBACK_POLL_S)


def _extract_last_traceback(text: str) -> str | None:
    """The last complete traceback block in ``text``, newlines preserved.

    Newlines are kept (unlike the boot-reason tail) because the analyzer
    reads this as structured evidence — a collapsed one-liner loses the
    frame that names the defect's file and line.
    """
    idx = text.rfind(_TRACEBACK_MARKER)
    if idx == -1:
        return None
    block = text[idx:].strip()
    if len(block) > _TRACEBACK_MAX_CHARS:
        # Trim from the FRONT: the exception line and the deepest (app) frame
        # sit at the tail — a head-kept cap would keep middleware frames and
        # drop the one line that names the defect.
        block = "…" + block[-(_TRACEBACK_MAX_CHARS - 1) :]
    return block


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
    """Poll until the subject answers HTTP on the ready path (#520).

    ANY response — 200 or 404 alike — proves the server is up and routing.
    Demanding 200 from ``/health`` made readiness a hidden product requirement:
    the group_run PRD declares no /health, so a perfectly booted app timed out
    'not ready' and every probe was skipped, forever. Readiness is transport-
    level; the probes themselves are the behavioral assertions.
    """
    url = f"http://{profile.host}:{port}{profile.ready_path}"
    deadline = time.monotonic() + profile.startup_timeout_s
    while time.monotonic() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return True
        except httpx.HTTPError:
            pass
        time.sleep(profile.poll_interval_s)
    return False


def _run_one(
    base_url: str, probe: Probe, profile: ExecutionProfile, context: dict[str, str]
) -> ProbeOutcome:
    method = str(probe.request.get("method", "GET")).upper()
    # #651: resolve captured placeholders. Unresolved = FAILED, not errored —
    # on the bare skeleton the upstream create legitimately failed, and its
    # dependents failing is the correct fill-behavior gate outcome.
    path, missing = resolve_probe_path(str(probe.request.get("path", "/")), context)
    if missing is not None:
        return ProbeOutcome(
            probe.id,
            "failed",
            f"unresolved path placeholder {{{missing}}} — no prior probe captured it "
            f"(its upstream probe failed or captured nothing)",
        )
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

    # #651: captures apply only on a passed probe. A missing capture key is a
    # contract violation by the app (the reference fill proves the key exists).
    if probe.capture:
        captured, missing_key = capture_probe_values(probe, payload)
        if missing_key is not None:
            return ProbeOutcome(
                probe.id, "failed", f"capture key {missing_key!r} missing from response body"
            )
        context.update(captured)

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
