"""Telemetry domain exceptions.

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""


class TelemetryError(Exception):
    """Base exception for telemetry operations.

    Adapters should catch and handle errors internally (non-blocking contract),
    but this exception is provided for edge cases where error propagation is needed.
    """

    pass
