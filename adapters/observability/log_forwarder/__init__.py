"""Log-forwarder adapter package.

Public surface:
- :func:`create_log_forwarder` — factory selecting the right concrete adapter.
- :class:`NoOpLogForwarder` — always-inject default when no backend is configured.
- :class:`PrefectLogForwarderAdapter` — forwards ``logging`` records to a
  Prefect server's ``/api/logs`` endpoint, scoped by ``flow_run_id`` /
  ``task_run_id`` from the active correlation context.
"""

from adapters.observability.log_forwarder.factory import create_log_forwarder
from adapters.observability.log_forwarder.noop import NoOpLogForwarder
from adapters.observability.log_forwarder.prefect import PrefectLogForwarderAdapter

__all__ = [
    "NoOpLogForwarder",
    "PrefectLogForwarderAdapter",
    "create_log_forwarder",
]
