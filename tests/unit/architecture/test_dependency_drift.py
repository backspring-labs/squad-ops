"""The image locks and CI's constraints must not drift further apart (#1041).

Deployment images install ``requirements/{api,agent}.lock``; CI installs
``tests/requirements.txt -c ci-constraints.txt``. The same ``src/squadops/`` code runs
under both, so every version they disagree on is a version CI's greens say nothing about.

Verified on 2026-08-30 in the running agent container, not merely read off the files:
numpy 1.26.4 in the image against 2.4.6 in CI, lancedb 0.8.2 against 0.33.0, pyarrow
15.0.0 against 24.0.0 — major-version gaps under the memory system and the array stack.

Closing those is an upgrade with real breakage risk and is deliberately NOT this check's
job. This is a **ratchet**: it accepts the divergence that exists today, recorded in
``DIVERGENCE_BASELINE``, and fails when the gap widens or narrows without the baseline
being updated. It exists so the gap cannot grow silently while the upgrade is pending.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_contracts]

REPO = Path(__file__).resolve().parents[3]
CI_CONSTRAINTS = REPO / "ci-constraints.txt"
LOCKS = ("requirements/api.lock", "requirements/agent.lock", "requirements/base.lock")

#: Packages the image locks and ci-constraints.txt currently disagree on. Every entry is
#: a version CI does not actually test. SHRINK this list as the images-up upgrade lands;
#: never grow it to make a red test pass — a new entry means a dependency was added or
#: bumped on one side only, which is the defect this guards.
DIVERGENCE_BASELINE = {
    "a2a-sdk",
    "aio-pika",
    "aiormq",
    "anyio",
    "asyncpg",
    "attrs",
    "certifi",
    "charset-normalizer",
    "click",
    "cryptography",
    "ecdsa",
    "fastapi",
    "google-api-core",
    "google-auth",
    "googleapis-common-protos",
    "greenlet",
    "idna",
    "lancedb",
    "numpy",
    "packaging",
    "pamqp",
    "propcache",
    "proto-plus",
    "protobuf",
    "pyarrow",
    "pyasn1",
    "pydantic",
    "pydantic-core",
    "python-dotenv",
    "python-multipart",
    "pyyaml",
    "redis",
    "requests",
    "rpds-py",
    "sqlalchemy",
    "sse-starlette",
    "starlette",
    "tqdm",
    "urllib3",
    "uvicorn",
    "wrapt",
    "yarl",
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


def test_no_new_dependency_divergence():
    """A package the images and CI newly disagree on is a version CI never tests."""
    observed = _observed_divergence()
    new = sorted(set(observed) - DIVERGENCE_BASELINE)
    assert not new, (
        "These packages newly disagree between the image locks and ci-constraints.txt:\n"
        + "\n".join(f"  {p:24} image={observed[p][0]:14} CI={observed[p][1]}" for p in new)
        + "\n\nCI's greens say nothing about the versions the images actually install."
        "\nReconcile the pin rather than adding it to DIVERGENCE_BASELINE — the baseline"
        "\nrecords the debt #1041 inherited, not a place to park new debt."
    )


def test_baseline_has_no_stale_entries():
    """A resolved divergence must leave the baseline, so the debt stays countable."""
    observed = _observed_divergence()
    stale = sorted(DIVERGENCE_BASELINE - set(observed))
    assert not stale, (
        "These packages no longer diverge — good. Remove them from DIVERGENCE_BASELINE:\n"
        + "\n".join(f"  {p}" for p in stale)
        + "\n\nAn unpruned baseline hides how much of #1041 is left."
    )


def test_the_locks_and_constraints_are_parseable_and_nonempty():
    """A parser that silently reads nothing would make both checks above vacuous."""
    ci = _pins(CI_CONSTRAINTS)
    assert len(ci) > 50, f"ci-constraints.txt parsed to only {len(ci)} pins"
    for lock in LOCKS:
        pins = _pins(REPO / lock)
        assert len(pins) > 10, f"{lock} parsed to only {len(pins)} pins"
