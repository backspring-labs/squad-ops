"""Every image whose composition root builds telemetry ships the SDK it exports with (#2371).

``OTelAdapter`` imports the OpenTelemetry SDK lazily and, by the port's non-blocking contract,
can't raise when it is missing. So an image without the SDK starts, serves, and exports nothing.
That shipped twice: the agents' image until #2203, then the runtime's, whose activity metrics
(#2204) went nowhere until #2371. The dev venv has the SDK, so no test of the adapter sees the
gap. This reads the lock each root's image installs instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_telemetry]

_REPO = Path(__file__).resolve().parents[3]

#: The factories that build an OTel-backed port (adapters/telemetry/factory.py).
_FACTORY_CALL = re.compile(r"\bcreate_(?:metrics|event|telemetry)_provider\(|\bOTelAdapter\(")
#: Each composition root that builds telemetry, and the lock its image installs (its Dockerfile's
#: ``pip install -r``).
_ROOT_LOCKS = {
    "src/squadops/api/runtime/main.py": "requirements/api.lock",
    "src/squadops/agents/entrypoint.py": "requirements/agent.lock",
}
#: What the adapter's import and its OTLP exporters need (adapters/telemetry/otel.py).
_SDK = ("opentelemetry-sdk", "opentelemetry-exporter-otlp-proto-grpc")


def _builders() -> set[str]:
    found = set()
    for top in ("src", "adapters"):
        for path in (_REPO / top).rglob("*.py"):
            rel = path.relative_to(_REPO).as_posix()
            if rel.startswith("adapters/telemetry/"):
                continue  # the factories and the adapter themselves
            if _FACTORY_CALL.search(path.read_text(encoding="utf-8")):
                found.add(rel)
    return found


def test_every_module_that_builds_telemetry_is_a_root_with_a_known_image():
    """Bug caught: a new caller of the telemetry factories, in an image nobody checked for the
    SDK. Derived from the callers, so the table can't silently miss one."""
    builders = _builders()
    assert builders, "found no caller of the telemetry factories; the pattern is stale"
    assert builders == set(_ROOT_LOCKS), (
        f"unmapped: {sorted(builders - set(_ROOT_LOCKS))}; "
        f"mapped but no longer building telemetry: {sorted(set(_ROOT_LOCKS) - builders)}"
    )


@pytest.mark.parametrize("root, lock", sorted(_ROOT_LOCKS.items()))
def test_each_roots_image_lock_pins_the_sdk_and_its_exporter(root: str, lock: str):
    pinned = {
        m.group(1).lower()
        for m in re.finditer(r"^([A-Za-z0-9_.-]+)==", (_REPO / lock).read_text(), re.M)
    }
    missing = [d for d in _SDK if d not in pinned]
    assert not missing, (
        f"{root} builds telemetry, and its image's {lock} does not pin {missing}: the adapter "
        "would export nothing. Declare them in the image's requirements file and regenerate "
        "the lock (scripts/maintainer/update_deps.sh)."
    )
