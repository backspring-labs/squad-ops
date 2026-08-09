"""Stacks whose subject cannot run from source build before they boot (#822).

Every stack that exists today is interpreted: `uvicorn backend.main:app` runs the materialized
workspace directly, and there is **no build step anywhere in the probe path** — `frontend_build`
is a separate acceptance check, and probes boot the backend on its own. Stack #2 (Next.js +
TypeScript) breaks that: `next build` must run before `next start`.

**Why not simply a longer boot timeout.** `startup_timeout_s` is 25s and a cold `npm ci` plus a
production build is minutes, so the naive fix is to raise it. That conflates two failures with
two different diagnoses — "the app is slow to start" and "the app does not build" would both
arrive as `subject did not boot`, and the build's own output, the only thing that explains the
second, belongs to a process that already exited.

Bug classes guarded:

- **a build failure reported as a boot failure**, which sends the reader (and #687's failure
  analyzer) looking at a running subject for a defect that killed a compiler;
- **a build failure with no output**, which is undiagnosable — and worse than the boot case,
  because there is no surviving process to interrogate afterwards;
- the preparation step **raising** instead of reporting not-executed: probes are additive
  evidence that "surfaces at the run verdict/rollup, not as a task failure here";
- a hanging build with no bound, which would park a QA task indefinitely;
- **the change being anything but inert for every stack that exists today.** A regression here
  silently deletes the behavioral half of every contract's evidence;
- the subject booting anyway after its build failed, which would probe a stale or absent
  artifact and report whatever it found as truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.handlers.probe_runner import (
    DEFAULT_PROFILE,
    PREPARE_FAILURE_PREFIX,
    ExecutionProfile,
    run_probes,
)
from squadops.cycles.verification_contract import Probe

pytestmark = [pytest.mark.domain_capabilities]


def _probe(pid: str = "vc-probe-runs") -> Probe:
    return Probe.from_dict(
        {"id": pid, "subject": "backend", "request": {"method": "GET", "path": "/runs"}}
    )


def _profile(argv: tuple[str, ...], **kw) -> ExecutionProfile:
    """A profile whose boot would succeed instantly if it were ever reached — so any skip in
    these tests is attributable to preparation, never to the boot that follows it."""
    return ExecutionProfile(boot_argv=(sys.executable, "-c", "pass"), prepare_argv=argv, **kw)


def _no_boot(monkeypatch) -> list:
    """Record whether boot was attempted. A failed build must not be followed by a boot."""
    attempts: list = []

    def _fake(workspace, profile, port):
        attempts.append(profile)
        raise OSError("boot must not be reached")

    monkeypatch.setattr(pr, "_boot", _fake)
    return attempts


# --------------------------------------------------------------------------- #
# Inertness — the property that matters most
# --------------------------------------------------------------------------- #


def test_a_profile_declaring_no_preparation_runs_nothing_extra(monkeypatch, tmp_path: Path):
    """Every stack today is interpreted, so this path must be byte-identical for them. If
    preparation ran — or even shelled out to a no-op — the behavioral half of every contract's
    evidence would be paying for a step none of it needs."""
    calls: list = []
    monkeypatch.setattr(pr.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(pr, "_boot", lambda *a: (_ for _ in ()).throw(OSError("stop here")))

    outcomes = run_probes(tmp_path, [_probe()], profile=DEFAULT_PROFILE)

    assert calls == [], "no subprocess may run for a stack that declares no prepare_argv"
    assert outcomes[0].status == "skipped"
    assert PREPARE_FAILURE_PREFIX not in (outcomes[0].reason or "")


def test_the_shipped_profile_declares_no_preparation():
    """FastAPI runs from source. Naming this pins the inertness above to the real default
    rather than to a fixture that happens to share its shape."""
    assert DEFAULT_PROFILE.prepare_argv == ()


# --------------------------------------------------------------------------- #
# Failure is not-executed, and says which stage
# --------------------------------------------------------------------------- #


def test_a_failed_build_skips_the_probes_and_names_the_stage(monkeypatch, tmp_path: Path):
    """The headline. A non-zero build is not-executed evidence, and the reason has to say
    *build*, or a reader debugs a subject that was never started."""
    attempts = _no_boot(monkeypatch)

    outcomes = run_probes(
        tmp_path,
        [_probe(), _probe("vc-probe-create")],
        profile=_profile((sys.executable, "-c", "import sys; sys.exit(3)")),
    )

    assert [o.status for o in outcomes] == ["skipped", "skipped"]
    assert all(PREPARE_FAILURE_PREFIX in (o.reason or "") for o in outcomes)
    assert "exited 3" in (outcomes[0].reason or "")
    assert attempts == [], "a subject whose build failed must not be booted"


def test_the_builds_own_output_reaches_the_reason(monkeypatch, tmp_path: Path):
    """Worse than the boot case, which at least leaves a process to inspect: if the compiler's
    message is not captured here it exists nowhere. `next build` prints the offending file and
    the type error, and that is the whole diagnosis."""
    _no_boot(monkeypatch)
    script = "import sys; sys.stderr.write('Type error in app/api/runs/route.ts:12'); sys.exit(1)"

    outcome = run_probes(tmp_path, [_probe()], profile=_profile((sys.executable, "-c", script)))[0]

    assert "app/api/runs/route.ts:12" in (outcome.reason or "")


def test_stdout_is_read_when_the_tool_writes_there_instead(monkeypatch, tmp_path: Path):
    """Build tools disagree about which stream carries diagnostics — `tsc` writes to stdout.
    Reading only stderr would silently drop the message for exactly the toolchain this exists
    to support."""
    _no_boot(monkeypatch)
    script = "import sys; sys.stdout.write('TS2345: Argument of type string'); sys.exit(2)"

    outcome = run_probes(tmp_path, [_probe()], profile=_profile((sys.executable, "-c", script)))[0]

    assert "TS2345" in (outcome.reason or "")


def test_a_hanging_build_is_bounded_and_says_so(monkeypatch, tmp_path: Path):
    """An unbounded build parks the QA task forever. The timeout reason must be distinguishable
    from a non-zero exit — "it never finished" and "it failed" are different defects."""
    _no_boot(monkeypatch)

    outcome = run_probes(
        tmp_path,
        [_probe()],
        profile=_profile(
            (sys.executable, "-c", "import time; time.sleep(30)"), prepare_timeout_s=0.5
        ),
    )[0]

    assert outcome.status == "skipped"
    assert "no exit within 0.5s" in (outcome.reason or "")
    assert "exited" not in (outcome.reason or "")


def test_a_missing_build_tool_is_reported_not_raised(monkeypatch, tmp_path: Path):
    """`npm` absent from the image is an environment gap, and the repo's standing rule is that
    those skip rather than fail (#462). Raising here would convert a missing tool into a dead
    QA task, which `qa_test` explicitly forbids: probes are additive evidence."""
    _no_boot(monkeypatch)

    outcome = run_probes(
        tmp_path, [_probe()], profile=_profile(("definitely-not-a-real-build-tool",))
    )[0]

    assert outcome.status == "skipped"
    assert "could not launch" in (outcome.reason or "")


# --------------------------------------------------------------------------- #
# The stage boundary
# --------------------------------------------------------------------------- #


def test_a_build_failure_does_not_read_as_a_boot_failure(monkeypatch, tmp_path: Path):
    """The reason this is a separate stage rather than a longer `startup_timeout_s`. #687's
    analyzer keys on these strings, and pointing it at a subject that never started is how
    #788 happened — a repair chasing a cause that was never there."""
    _no_boot(monkeypatch)

    outcome = run_probes(
        tmp_path, [_probe()], profile=_profile((sys.executable, "-c", "import sys; sys.exit(1)"))
    )[0]

    assert "subject did not boot" not in (outcome.reason or "")
    assert PREPARE_FAILURE_PREFIX in (outcome.reason or "")


def test_a_successful_build_proceeds_to_boot(monkeypatch, tmp_path: Path):
    """The happy path has to actually continue. A preparation step that swallowed control
    would make every compiled stack silently unprobeable — the #818 shape, one stage over."""
    attempts = _no_boot(monkeypatch)

    outcome = run_probes(tmp_path, [_probe()], profile=_profile((sys.executable, "-c", "pass")))[0]

    assert len(attempts) == 1, "boot must be attempted after a clean build"
    assert outcome.status == "skipped"
    assert PREPARE_FAILURE_PREFIX not in (outcome.reason or "")


def test_preparation_runs_in_the_workspace(monkeypatch, tmp_path: Path):
    """`next build` reads `package.json` and writes `.next/` relative to cwd. Running it
    anywhere but the materialized workspace builds the wrong tree — or nothing."""
    _no_boot(monkeypatch)
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    script = "import pathlib,sys; sys.exit(0 if pathlib.Path('package.json').exists() else 9)"

    outcome = run_probes(tmp_path, [_probe()], profile=_profile((sys.executable, "-c", script)))[0]

    assert PREPARE_FAILURE_PREFIX not in (outcome.reason or ""), (
        "the build ran outside the workspace — package.json was not visible to it"
    )
