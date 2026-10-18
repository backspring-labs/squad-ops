"""The runtime API's one binding of the sandbox client (#2451): SIP-0112's seeding and SIP-0113's
runner both read it from ``create_sandbox_client``."""

from __future__ import annotations

import httpx
import pytest

from adapters.sandbox.factory import create_sandbox_client
from squadops.config.loader import load_config
from squadops.config.schema import SandboxClientConfig
from squadops.sandbox.api import create_app
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.unit.config.test_loader_secrets_seam import _ENV

_DEPLOY = {
    "SQUADOPS__SANDBOX_CLIENT__PROVIDER": "http",
    "SQUADOPS__SANDBOX_CLIENT__SERVICE_URL": "http://squadops-sandbox-service:8002",
    "SQUADOPS__SANDBOX_CLIENT__SERVICE_TOKEN": "tok-2451",
}


async def test_the_deploys_env_reaches_the_service_through_the_client_the_runtime_binds(
    monkeypatch, tmp_path
):
    """The wiring test (#2451): entered where the runtime API's startup does, at ``load_config``
    with the env compose writes, then the factory ``_init_cycle_subsystem`` calls; asserted at the
    service, which holds the seeded tree. Bug caught: the env read into the service's section
    (its own provider is ``docker``, and the preflight's would be overwritten), an optional
    section the env's path map never walks (http read as absent), or a client built without
    the token or against the service's loopback default."""
    for key, value in {**_ENV, **_DEPLOY}.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "cycles"
    store = WorkspaceStore(root)
    service = create_app(
        SandboxService(store=store, journal=OperationEvidenceJournal(root)),
        service_token="tok-2451",
    )
    asked: list[str] = []

    async def record(request: httpx.Request) -> None:
        asked.append(f"{request.url.host}:{request.url.port}")

    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real(
            transport=httpx.ASGITransport(app=service), event_hooks={"request": [record]}, **kw
        ),
    )
    config = load_config(cli_overrides={"secrets": {"provider": "env"}})

    revision = await create_sandbox_client(config.sandbox_client).seed_workspace(
        "cyc-2451", {"app/main.py": "print('seeded')\n"}
    )

    assert asked == ["squadops-sandbox-service:8002"]
    assert revision.cycle_id == "cyc-2451"
    assert store.current_files("cyc-2451") == {"app/main.py": "print('seeded')\n"}
    assert config.sandbox.provider == "noop"  # the preflight's selector, untouched


def test_none_is_no_client_and_an_absent_section_refuses_to_start():
    """#1568: required where it is read. Bug caught: a runtime API that starts with no word on its
    sandbox client and quietly calls nothing, every seed and evaluation reading as unavailable
    with no one having chosen it."""
    assert create_sandbox_client(SandboxClientConfig(provider="none")) is None
    with pytest.raises(ValueError, match="SQUADOPS__SANDBOX_CLIENT__PROVIDER"):
        create_sandbox_client(None)
