"""
Agent runtime state — SIP-0089.

Pure coordination layer for `RuntimeMode`, `RuntimeActivity`, `FocusLease`,
`Assignment`, and `DutyWindow`. Depends on `squadops.ports.*`; never on
`adapters.*` (D1, enforced by `tests/unit/architecture/test_forbidden_imports.py`
per D26).
"""

from squadops.runtime.models import AgentRuntimeState

__all__ = ["AgentRuntimeState"]
