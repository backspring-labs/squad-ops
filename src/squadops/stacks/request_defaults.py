"""What a stack asks of a cycle beyond its request profile (#316, the taxonomy's R2.3).

A request profile names a depth (``validate``), and the stack says what that depth requires of it:
the checks it requires, the time a scaffolded build on it takes, and how many manifest attempts its
framing gets. ``validated-fullstack`` differed from ``validation`` in exactly these keys besides the
stack itself, so ``validate`` on a stack asks for what ``validated-fullstack`` asked for.

``cycle_request_body`` puts them beneath a profile's own keys and under the caller's overrides. A
profile that sets one keeps it, so every frozen profile that declares these keys resolves as it did.
A leaf: it imports nothing, so the profile loader, the CLI and the runtime read it alike.
"""

from __future__ import annotations

from typing import Any

#: The values ``validated-fullstack`` carried, which every counted roll on either stack ran with:
#: the FastAPI + React rolls on the profile itself, the Next.js rolls with only the stack
#: overridden (``docs/plans/verification-sets/*-nextjs.yaml``).
_SCAFFOLDED_FULLSTACK: dict[str, Any] = {
    "required_checks": ["tests_pass", "frontend_build", "required_files"],
    "time_budget_seconds": 10800,
    "manifest_max_attempts": 4,
}

#: Each stack's request defaults, by the stack's registered name (``scaffold._STACKS``). A stack
#: not named here asks nothing beyond its profile.
STACK_REQUEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "fullstack_fastapi_react": _SCAFFOLDED_FULLSTACK,
    "nextjs_ts": _SCAFFOLDED_FULLSTACK,
}


def request_defaults_for(stack: object) -> dict[str, Any]:
    """The request defaults ``stack`` declares: a fresh copy, so no caller edits the table. A cycle
    that names no stack, or one that isn't listed, gets none."""
    declared = STACK_REQUEST_DEFAULTS.get(stack) if isinstance(stack, str) else None
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in (declared or {}).items()
    }
