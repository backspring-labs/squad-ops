"""The image locks and CI's constraints must not drift further apart (#1041).

Deployment images install ``requirements/{api,agent}.lock``; CI installs
``tests/requirements.txt -c ci-constraints.txt``. The same ``src/squadops/`` code runs
under both, so every version they disagree on is a version CI's greens say nothing about.

Verified on 2026-08-30 in the running agent container, not merely read off the files:
numpy 1.26.4 in the image against 2.4.6 in CI, lancedb 0.8.2 against 0.33.0, pyarrow
15.0.0 against 24.0.0 — major-version gaps under the memory system and the array stack.

The images-up upgrade closed 40 of the 42, and the locks are now compiled *against*
ci-constraints.txt (``scripts/maintainer/update_deps.sh``), so a shared package cannot
diverge by construction. What remains is what genuinely cannot follow CI, and this check
is now about **documentation** rather than a frozen count: every divergence must appear
in ``requirements/constraint-exceptions.txt`` with a recorded reason, and every listed
exception must still be real. A hardcoded baseline could record 42 anonymous numbers; a
reason file cannot, which is the point — "why is this one allowed" has an answer next to
the name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_contracts]

REPO = Path(__file__).resolve().parents[3]
CI_CONSTRAINTS = REPO / "ci-constraints.txt"
LOCKS = ("requirements/api.lock", "requirements/agent.lock", "requirements/base.lock")
EXCEPTIONS_FILE = REPO / "requirements" / "constraint-exceptions.txt"


def _documented_exceptions() -> set[str]:
    """Packages allowed to diverge, read from the file that carries their reasons.

    The same file ``update_deps.sh`` filters out of the constraint, so the exception a
    compile honours and the exception a test permits are one fact, not two.
    """
    return {
        line.split("#", 1)[0].strip().lower().replace("_", "-")
        for line in EXCEPTIONS_FILE.read_text().splitlines()
        if line.split("#", 1)[0].strip()
    }


_PIN = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;]+)")


def _pins(path: Path) -> dict[str, str]:
    """Package -> version from a pip requirements/constraints file, names normalised."""
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        m = _PIN.match(line)
        if m:
            out[m.group(1).lower().replace("_", "-")] = m.group(2)
    return out


def _observed_divergence() -> dict[str, tuple[str, str]]:
    """Packages pinned in BOTH a lock and ci-constraints, at different versions."""
    ci = _pins(CI_CONSTRAINTS)
    seen: dict[str, tuple[str, str]] = {}
    for lock in LOCKS:
        for pkg, image_version in _pins(REPO / lock).items():
            ci_version = ci.get(pkg)
            if ci_version is not None and ci_version != image_version:
                seen[pkg] = (image_version, ci_version)
    return seen


def test_every_divergence_is_documented():
    """A package the images and CI disagree on is a version CI never tests.

    Since the locks compile against ci-constraints.txt, reaching this state at all takes
    a deliberate act: adding the package to the exceptions file, or removing the
    constraint. The first is fine and must carry a reason; the second should be loud.
    """
    observed = _observed_divergence()
    undocumented = sorted(set(observed) - _documented_exceptions())
    assert not undocumented, (
        "These packages disagree between the image locks and ci-constraints.txt with no\n"
        "recorded reason:\n"
        + "\n".join(f"  {p:24} image={observed[p][0]:14} CI={observed[p][1]}" for p in undocumented)
        + "\n\nCI's greens say nothing about the versions the images actually install."
        "\nRe-run scripts/maintainer/update_deps.sh to reconcile. If the package genuinely"
        "\ncannot follow CI, add it to requirements/constraint-exceptions.txt WITH THE"
        "\nREASON — an entry without one is not an exception, it is unfinished work."
    )


def test_no_exception_outlives_its_reason():
    """A listed exception that no longer diverges must go.

    An exceptions file that accumulates is how a documented exception becomes an
    undocumented one: nobody re-reads a name that has been there for a year, and the
    reason quietly stops being true.
    """
    observed = _observed_divergence()
    stale = sorted(_documented_exceptions() - set(observed))
    assert not stale, (
        "These packages no longer diverge — good. Remove them from\n"
        "requirements/constraint-exceptions.txt, with their reasons:\n"
        + "\n".join(f"  {p}" for p in stale)
    )


def test_every_exception_carries_a_reason():
    """The file's own rule, enforced: a bare name is not an exception.

    Without this the file degrades into exactly the anonymous list it replaced.
    """
    lines = EXCEPTIONS_FILE.read_text().splitlines()
    unreasoned = []
    for i, line in enumerate(lines):
        if not line.split("#", 1)[0].strip():
            continue
        preceding = [ln for ln in lines[:i][::-1]]
        commented = next((ln for ln in preceding if ln.strip()), "")
        if not commented.lstrip().startswith("#"):
            unreasoned.append(line.strip())
    assert not unreasoned, (
        "These exceptions have no comment above them explaining why they cannot follow\n"
        "ci-constraints.txt:\n" + "\n".join(f"  {p}" for p in unreasoned)
    )


def test_the_locks_and_constraints_are_parseable_and_nonempty():
    """A parser that silently reads nothing would make both checks above vacuous."""
    ci = _pins(CI_CONSTRAINTS)
    assert len(ci) > 50, f"ci-constraints.txt parsed to only {len(ci)} pins"
    for lock in LOCKS:
        pins = _pins(REPO / lock)
        assert len(pins) > 10, f"{lock} parsed to only {len(pins)} pins"


def test_the_locks_agree_with_each_other():
    """Two images running the same ``src/squadops/`` code must install the same versions.

    The bug this caught: the checks above compare each lock against ci-constraints and
    never against each other, so a package absent from CI's set could sit at different
    versions in two images indefinitely. api.lock had langfuse 2.36.2 with packaging
    23.2 while agent.lock had 2.60.10 with 24.2 — a 24-minor gap in the LangFuse client,
    under one shared adapter (``adapters/telemetry/langfuse/``).

    It survived a regeneration because ``pip-compile`` treats an existing lock as a
    preference and keeps any pin that still satisfies the constraint, so both files were
    rewritten and neither moved. ``update_deps.sh`` passes ``--upgrade`` for exactly this
    reason; this test is what notices if that ever stops being true.
    """
    pins = {lock: _pins(REPO / lock) for lock in LOCKS}
    disagreements: list[str] = []
    for i, left in enumerate(LOCKS):
        for right in LOCKS[i + 1 :]:
            shared = set(pins[left]) & set(pins[right])
            for pkg in sorted(shared):
                if pins[left][pkg] != pins[right][pkg]:
                    disagreements.append(
                        f"  {pkg:24} {Path(left).name}={pins[left][pkg]:14} "
                        f"{Path(right).name}={pins[right][pkg]}"
                    )
    assert not disagreements, (
        "These packages are pinned at different versions across the image locks:\n"
        + "\n".join(disagreements)
        + "\n\nThe same framework code runs in both images. Re-run"
        "\nscripts/maintainer/update_deps.sh (which passes --upgrade) to reconcile."
    )
