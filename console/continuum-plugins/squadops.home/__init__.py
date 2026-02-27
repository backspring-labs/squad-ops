"""SquadOps Home plugin — dashboard summary with active cycles and agent status."""


def register(ctx):
    """Register Home plugin contributions."""
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Home",
            "icon": "home",
            "icon_path": "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
            "priority": 999,
            "target": {"type": "panel", "panel_id": "signal"},
        },
    )

    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "signal",
            "component": "squadops-home-summary",
            "priority": 999,
        },
    )
