"""Host systemd units: what they may remove, that they render, and that they run (#1465, #2288).

These guard two things a code review cannot reliably catch by eye, on files that run
UNATTENDED AS ROOT'S NEIGHBOUR on a box holding the only copy of the evidence base.

Bug classes guarded:

- **a reclaim script growing a flag that destroys data.** `docker system prune -a` evicts
  every tagged image (the agents, runtime-api, the pinned sandbox env) and
  `docker volume prune` removes the volume `squadops-postgres` keeps its data in — which
  is how a database is lost on a box whose backups were installed the same day. Both are
  one word away from what the script legitimately does, and both would look like a
  reasonable "reclaim more" edit in a diff;
- **a unit template that cannot render.** The installer substitutes exactly `__USER__` and
  `__REPO_ROOT__` and refuses anything with a `__` left; a template introducing a third
  placeholder installs nothing and is only discovered by a human running it with sudo;
- **a unit that never runs.** A scheduled unit needs its timer, and a long-running one (the memory
  watchdog) must be wanted at boot and restarted when it stops, or it reads as protection it is not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_REPO = Path(__file__).resolve().parents[3]
_SYSTEMD = _REPO / "infra" / "systemd"
_PRUNE = _REPO / "scripts" / "dev" / "ops" / "prune_docker.sh"
_INSTALLER = _REPO / "scripts" / "dev" / "ops" / "install_host_unit.sh"

#: What the installer's sed actually replaces. A template may use these and nothing else.
SUBSTITUTED = ("__USER__", "__REPO_ROOT__")


def _units() -> list[Path]:
    return sorted(_SYSTEMD.glob("*.service"))


def _timers() -> list[Path]:
    return sorted(_SYSTEMD.glob("*.timer"))


def _executable_lines(path: Path) -> str:
    """The script with comments and blank lines stripped.

    Scanning the raw file would fail on the script's own documentation — prune_docker.sh
    explains at length that it never uses ``-a`` or ``volume prune``, and a test that reads
    those sentences as usage pressures the next author to DELETE the explanation to get
    green. The guard is about what runs, so it reads what runs.
    """
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(line.split(" #", 1)[0])
    return "\n".join(out)


def test_there_are_units_to_check():
    """A glob that matched nothing would make every test below vacuously pass."""
    assert _units(), f"no *.service templates under {_SYSTEMD}"


@pytest.mark.parametrize(
    "forbidden",
    ["system prune", "volume prune", "prune -a", "prune --all", "-a --volumes", "--volumes"],
)
def test_the_reclaim_script_never_grows_a_destructive_flag(forbidden):
    """`-a` takes the tagged images; `--volumes` takes the database. Neither is a bigger
    version of what this script does — they are different operations that happen to live
    under the same verb, and on this box one of them is unrecoverable."""
    assert forbidden not in _executable_lines(_PRUNE), (
        f"prune_docker.sh contains {forbidden!r} — it may remove dangling images and capped "
        "build cache, never tagged images, containers or volumes"
    )


def test_the_reclaim_script_caps_the_cache_rather_than_emptying_it():
    """A bare `builder prune -f` empties the cache, making the next build cold for no disk
    the cap does not already free. The cap is the whole difference between a weekly reclaim
    and a weekly penalty."""
    body = _executable_lines(_PRUNE)

    assert "--max-used-space" in body
    assert not re.search(r"builder prune -f\s*(?:>|$|\n)", body), (
        "an uncapped `builder prune -f` empties the whole cache"
    )


@pytest.mark.parametrize("unit", _units(), ids=lambda p: p.name)
def test_every_unit_template_uses_only_placeholders_the_installer_substitutes(unit):
    """The installer refuses any `__` it did not replace, so an unknown placeholder is not a
    wrong path — it is a unit that never installs, discovered by a human running sudo."""
    found = set(re.findall(r"__[A-Z_]+__", unit.read_text(encoding="utf-8")))

    assert found <= set(SUBSTITUTED), (
        f"{unit.name} uses {sorted(found - set(SUBSTITUTED))}, which "
        f"{_INSTALLER.name} does not substitute — it would refuse to install this unit"
    )


def _long_running() -> list[Path]:
    return [u for u in _units() if not u.with_suffix(".timer").exists()]


def test_the_watchdog_is_a_long_running_unit():
    """The list below is the units with no timer; an empty one would pass vacuously."""
    assert [u.name for u in _long_running()] == ["squadops-memory-watchdog.service"]


@pytest.mark.parametrize("unit", _long_running(), ids=lambda p: p.name)
def test_a_service_without_a_timer_runs_always(unit):
    """A .service with no .timer never fires, unless it is wanted at boot and restarted
    whenever it stops. The failure mode is silence, which is the one nobody notices: a watchdog
    that died at the last reboot reads as installed."""
    body = unit.read_text(encoding="utf-8")

    assert re.search(r"^WantedBy=multi-user\.target$", body, re.MULTILINE), (
        f"{unit.name} has no .timer and is not wanted at boot"
    )
    assert re.search(r"^Restart=always$", body, re.MULTILINE), (
        f"{unit.name} has no .timer and is not restarted when it stops"
    )


def test_every_timer_has_its_service():
    """A timer activates the service of its name; one without it fires into nothing."""
    orphans = [t.name for t in _timers() if not t.with_suffix(".service").exists()]
    assert not orphans, f"timers with no .service: {orphans}"


@pytest.mark.parametrize("timer", _timers(), ids=lambda p: p.name)
def test_every_timer_survives_a_missed_window(timer):
    """The Spark has hard-halted five times. Without Persistent=true a timer whose window
    passed while the box was down simply skips that run, silently."""
    assert "Persistent=true" in timer.read_text(encoding="utf-8"), (
        f"{timer.name} would skip a missed window"
    )


def test_the_scheduled_timers_do_not_fire_at_the_same_minute():
    """Two unattended jobs at one OnCalendar compete for the box, and the pairing that
    matters is the reclaim slowing the backup — the one job whose failure costs evidence."""
    times = {}
    for timer in _timers():
        body = timer.read_text(encoding="utf-8")
        for match in re.findall(r"^OnCalendar=(.+)$", body, re.MULTILINE):
            times.setdefault(match.strip(), []).append(timer.stem)

    collisions = {when: names for when, names in times.items() if len(names) > 1}
    assert not collisions, f"timers share an OnCalendar: {collisions}"
