"""The remote-execution worker's entrypoint (SIP-0117 R3.3, R5.5).

Composition root: reads the worker's own ``SQUADOPS__WORKER__*`` section, binds the runtime
API and the provider's runner through their factories, and serves.

Config note: as the sandbox service does, the worker reads only its own section and never
``load_config()``. The layered loader resolves every ``secret://`` reference in the platform
config, and the worker's machine holds one secret: its own client's.

It runs on the machine that hosts the tool, and connects outward. Nothing connects to it::

    SQUADOPS__WORKER__WORKER_ID=macbook \\
    SQUADOPS__WORKER__RUNTIME_API_URL=http://<the runtime's host>:8001 \\
    SQUADOPS__WORKER__TOKEN_ENDPOINT=http://<the identity provider>/realms/<realm>/protocol/openid-connect/token \\
    SQUADOPS__WORKER__CLIENT_ID=squadops-worker \\
    SQUADOPS__WORKER__CLIENT_SECRET=<the deploy's SQUADOPS_WORKER_CLIENT_SECRET> \\
    SQUADOPS__WORKER__PROVIDER=fixture \\
    python -m squadops.remote_execution.worker_main
"""

from __future__ import annotations

import asyncio
import logging
import platform
import signal
import sys
from collections.abc import Awaitable, Callable

from squadops.auth.client_credentials import ServiceTokenClient
from squadops.config.env_section import section_from_env
from squadops.config.schema import WorkerConfig
from squadops.core.secrets import SecretManager
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import RuntimeAnswerUnreadable, WorkerRefused

_ENV_PREFIX = "SQUADOPS__WORKER__"

logger = logging.getLogger(__name__)


def worker_config_from_env() -> WorkerConfig:
    """The worker's section from its variables. A missing field, an unknown one and a provider
    outside the vocabulary each raise, naming it."""
    return WorkerConfig.model_validate(section_from_env(_ENV_PREFIX, WorkerConfig.model_fields))


def client_secret(config: WorkerConfig, secret_manager: SecretManager | None) -> str:
    """The client's secret, with a ``secret://`` reference resolved. A reference with no
    secrets provider to resolve it is refused: sent as it is, it would be a wrong password."""
    secret = config.client_secret
    if not secret.startswith("secret://"):
        return secret
    if secret_manager is None:
        raise ValueError(
            "SQUADOPS__WORKER__CLIENT_SECRET is a secret:// reference, and no secrets provider "
            "is configured to resolve it (set SQUADOPS__SECRETS__PROVIDER)"
        )
    return secret_manager.resolve(secret)


def build_worker(
    config: WorkerConfig, secret_manager: SecretManager | None
) -> tuple[Worker, Callable[[], Awaitable[None]]]:
    """The worker, and the call that releases its connections."""
    # Composition root: the one place the worker meets its adapters.
    from adapters.remote_execution.factory import create_operation_runner, create_worker_api

    tokens = ServiceTokenClient(
        token_endpoint=config.token_endpoint,
        client_id=config.client_id,
        client_secret=client_secret(config, secret_manager),
    )
    api = create_worker_api(config.runtime_api_url, tokens.get_token)
    runner = create_operation_runner(config.provider)
    worker = Worker(
        api,
        runner,
        worker_id=config.worker_id,
        platform=f"{platform.system().lower()}-{platform.machine().lower()}",
    )

    async def close() -> None:
        await api.close()
        await tokens.close()

    return worker, close


async def run() -> None:
    """Serve until the process is told to stop."""
    # deferred (pair): bootstrap's package imports the sandbox, and every root imports bootstrap
    from squadops.bootstrap.secrets import secret_manager_from_env

    worker, close = build_worker(worker_config_from_env(), secret_manager_from_env())
    serving = asyncio.ensure_future(worker.serve())
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, serving.cancel)
    try:
        await serving
    except asyncio.CancelledError:
        logger.info("the worker was stopped")
    finally:
        await close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # The client logs every request at INFO, and an idle worker asks for work every few
    # seconds. What the worker does is logged by its loop.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        asyncio.run(run())
    except (WorkerRefused, RuntimeAnswerUnreadable) as e:
        logger.error("the worker stopped: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
