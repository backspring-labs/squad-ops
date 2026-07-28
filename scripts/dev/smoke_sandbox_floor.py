"""Live smoke of the SIP-0102 sandbox floor against real docker.

The shakedown instrument (102.2 wrap; Spark pick-up step 3): materialize the
canonical expander skeleton, seed it, then walk the floor — install →
build_frontend → start_application → probe (bare-skeleton 501 partition) →
converging teardown — asserting the pin holds throughout. In-process backend
(the HTTP surface is ASGI-tested); this validates the CONTAINER layer on the
host it runs on.

Prereqs: docker daemon up; the canonical image built
(./scripts/dev/build_sandbox_env_image.sh). Network needed on first run
(pip/npm installs; the read-through caches warm under the smoke root).

Usage:  .venv/bin/python scripts/dev/smoke_sandbox_floor.py
        SQUADOPS_SANDBOX_SMOKE_ROOT=/somewhere ... (default /tmp/squadops-sandbox-smoke)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

import yaml

from adapters.sandbox.container_backend import ContainerBackend
from adapters.tools.docker import DockerAdapter
from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.sandbox.environment import FULLSTACK_FASTAPI_REACT
from squadops.sandbox.models import RevisionOrigin
from squadops.sandbox.workspace import WorkspaceStore

ROOT = Path(os.environ.get("SQUADOPS_SANDBOX_SMOKE_ROOT", "/tmp/squadops-sandbox-smoke"))
MANIFEST = Path("examples/03_group_run/interface_manifest.yaml")


async def main() -> int:
    shutil.rmtree(ROOT / "cycles", ignore_errors=True)  # keep caches warm across runs
    store = WorkspaceStore(ROOT / "cycles")
    contract = FULLSTACK_FASTAPI_REACT
    backend = ContainerBackend(
        container=DockerAdapter(),
        store=store,
        image=contract.image,
        operation_commands=contract.commands(),
        app_port=contract.app_port,
        install_network=contract.install_network,
        environment_contract_id=contract.contract_id(),
        cache_root=ROOT / "caches",
        timeout_seconds=420.0,
        readiness_timeout_seconds=30.0,
    )

    raw = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    files = {f["name"]: f["content"] for f in expand(InterfaceManifest.from_dict(raw))}
    revision = store.seed("smoke_1", files, origin=RevisionOrigin.SCAFFOLD_SEED)
    print(f"seeded {len(files)} files, revision {revision.revision_id[:12]}")

    report = await backend.environment_report()
    print(f"environment_report: image_present={report['image_present']}")
    assert report["image_present"] is True, (
        "environment image missing — run ./scripts/dev/build_sandbox_env_image.sh"
    )

    install = await backend.install_dependencies(revision=revision)
    print(f"install: ran={install.ran} status={install.status} {install.duration_seconds:.0f}s")
    assert install.status == "succeeded", f"install failed: {install}"
    assert store.verify_pinned("smoke_1", revision.revision_id), "install broke the pin"

    build = await backend.build_frontend(revision=revision)
    print(f"build_frontend: ran={build.ran} status={build.status} {build.duration_seconds:.0f}s")
    assert build.status == "succeeded", f"build failed: {build.diagnostics}"

    start = await backend.start_application(revision=revision)
    print(f"start: ready={start.ready} endpoints={start.endpoints}")
    assert start.ready, f"app never ready: {start.startup_diagnostics}"

    # Bare-skeleton partition (SIP-0098 §6.2): a declared route answers 501 —
    # routing works, behavior honestly unimplemented.
    probe = await backend.probe_http_endpoint(
        revision=revision,
        probe_id="bare-skeleton-501",
        method="GET",
        path="/runs",
        expected_status=501,
    )
    print(f"probe GET /runs: observed={probe.observed_status_code} status={probe.status}")
    assert probe.status == "succeeded", f"probe: {probe.detail}"
    assert probe.environment_contract_id == contract.contract_id()

    stop = await backend.stop_application(revision=revision, cleanup_handle=start.cleanup_handle)
    print(f"stop: status={stop.status}")
    assert stop.status == "succeeded"

    print("\nSMOKE PASSED — the sandbox floor executes end-to-end on this host's docker.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
