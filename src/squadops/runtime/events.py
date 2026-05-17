"""
Canonical runtime-state event names (SIP-0089, D14, D18).

Events describe **what happened**. Reasons (in `reasons.py`) describe **why**.
The two vocabularies are deliberately separate — see D18. Both are locked
v1.1 constants after the §1.0 spike normalization pass.

Initial v1.1 vocabulary. Phases 2/3 extend this set for assignments and
focus leases; new names go through the same normalization step.
"""

from __future__ import annotations

from typing import Final

# Mode transitions (Phase 1)
MODE_TRANSITION: Final[str] = "runtime_state.mode_transition"

# Heartbeat lifecycle (Phase 1)
HEARTBEAT_INITIALIZED: Final[str] = "runtime_state.heartbeat_initialized"
HEARTBEAT_RECOVERED: Final[str] = "runtime_state.heartbeat_recovered"
