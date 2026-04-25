"""LogForwarderPort — observability port for task-scoped log forwarding.

Defines the lifecycle contract that core composition roots use to install and
tear down a log-forwarding pipeline (e.g. forwarding `logging` records to a
workflow UI's per-task pane). Vendor-specific concerns — endpoint URLs, auth,
batch sizes, queue topology — live entirely in adapters.

Design mirrors LLMObservabilityPort (SIP-0061): always-inject pattern with a
NoOp adapter so core never branches on "is forwarding enabled". The factory
returns an instance that is already attached to Python's logging tree and has
its background flush task running; callers only need to ``await aclose()`` on
shutdown.
"""

from abc import ABC, abstractmethod


class LogForwarderPort(ABC):
    """Lifecycle handle for a task-scoped log-forwarding pipeline.

    Implementations attach themselves to the logging tree at construction time
    (via the factory). The only behaviour the core requires from them is a
    bounded async teardown.
    """

    @abstractmethod
    async def aclose(self) -> None:
        """Detach from the logging tree and release transport resources.

        MUST NOT block indefinitely. Implementations SHOULD enforce a max time
        budget for any final flush attempt. Idempotent — calling ``aclose``
        twice is a no-op on the second call.
        """
