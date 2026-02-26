"""SquadOps Observability plugin — build artifacts, gate decisions, cycle stats."""


def register(ctx):
    """Register Observability plugin contributions."""
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "signal",
            "component": "squadops-obs-artifacts",
            "priority": 200,
        },
    )

    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "signal",
            "component": "squadops-obs-gate-decisions",
            "priority": 100,
        },
    )

    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.right_rail",
            "perspective": "signal",
            "component": "squadops-obs-cycle-stats",
            "priority": 300,
        },
    )
