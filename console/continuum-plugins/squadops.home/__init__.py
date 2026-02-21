"""SquadOps Home plugin — dashboard summary with active cycles and agent status."""


def register(ctx):
    """Register Home plugin contributions."""
    ctx.register_contribution("nav", {
        "slot": "ui.slot.left_nav",
        "label": "Home",
        "icon": "activity",
        "priority": 999,
        "target": {"type": "panel", "panel_id": "signal"},
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "squadops-home-summary",
        "priority": 999,
    })
