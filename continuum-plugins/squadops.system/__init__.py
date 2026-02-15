"""SquadOps System plugin — health, plugins, and infrastructure diagnostics."""


def register(ctx):
    """Register System plugin contributions."""
    ctx.register_contribution("nav", {
        "slot": "ui.slot.left_nav",
        "label": "Systems",
        "icon": "settings",
        "priority": 400,
        "target": {"type": "panel", "panel_id": "systems"},
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "systems",
        "component": "squadops-system-health",
        "priority": 800,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "systems",
        "component": "squadops-system-plugins",
        "priority": 600,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "systems",
        "component": "squadops-system-infra",
        "priority": 400,
    })

    ctx.register_contribution("command", {
        "id": "squadops.health_check",
        "label": "Health Check",
        "action": "squadops.health_check",
        "danger_level": "safe",
    })
