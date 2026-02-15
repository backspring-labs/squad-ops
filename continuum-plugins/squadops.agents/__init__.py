"""SquadOps Agents plugin — agent status and task history (view-only)."""


def register(ctx):
    """Register Agents plugin contributions."""
    ctx.register_contribution("panel", {
        "slot": "ui.slot.right_rail",
        "perspective": "signal",
        "component": "squadops-agents-status",
        "priority": 800,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "squadops-agents-tasks",
        "priority": 300,
    })
