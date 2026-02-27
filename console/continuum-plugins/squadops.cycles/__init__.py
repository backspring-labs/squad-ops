"""SquadOps Cycles plugin — cycle lifecycle management, run monitoring, gate decisions."""


def register(ctx):
    """Register Cycles plugin contributions (1 nav + 1 panel + 7 commands)."""
    # ── Navigation ──────────────────────────────────────────────
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Cycles",
            "icon": "refresh-cw",
            "priority": 800,
            "target": {"type": "panel", "panel_id": "cycles"},
        },
    )

    # ── Panels (SIP-0074: single composite perspective) ─────────
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "cycles",
            "component": "squadops-cycles-perspective",
            "priority": 800,
        },
    )

    # ── Commands ────────────────────────────────────────────────
    ctx.register_contribution(
        "command",
        {
            "id": "squadops.create_cycle",
            "label": "Create Cycle",
            "action": "squadops.create_cycle",
            "danger_level": "safe",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.create_run",
            "label": "Create Run",
            "action": "squadops.create_run",
            "danger_level": "safe",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.cancel_cycle",
            "label": "Cancel Cycle",
            "action": "squadops.cancel_cycle",
            "danger_level": "confirm",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.cancel_run",
            "label": "Cancel Run",
            "action": "squadops.cancel_run",
            "danger_level": "confirm",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.gate_approve",
            "label": "Approve Gate",
            "action": "squadops.gate_approve",
            "danger_level": "safe",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.gate_reject",
            "label": "Reject Gate",
            "action": "squadops.gate_reject",
            "danger_level": "confirm",
        },
    )

    ctx.register_contribution(
        "command",
        {
            "id": "squadops.open_create_cycle",
            "label": "New Cycle",
            "description": "Open the cycle creation modal",
            "action": "squadops.open_create_cycle",
            "danger_level": "safe",
        },
    )
