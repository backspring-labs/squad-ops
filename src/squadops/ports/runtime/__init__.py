"""
Runtime ports (SIP-0089).

Matches the namespace pattern of `squadops.ports.cycles` and
`squadops.ports.observability` (established in 1.0.5).
"""

from squadops.ports.runtime.assignments import AssignmentPort
from squadops.ports.runtime.state import RuntimeStatePort

__all__ = ["AssignmentPort", "RuntimeStatePort"]
