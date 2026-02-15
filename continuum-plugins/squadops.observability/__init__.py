"""SquadOps Observability plugin — Prefect flows, LangFuse traces, cost summary."""


def register(ctx):
    """Register Observability plugin contributions."""
    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "squadops-obs-flow-metrics",
        "priority": 200,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "squadops-obs-llm-traces",
        "priority": 100,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.right_rail",
        "perspective": "signal",
        "component": "squadops-obs-cost-summary",
        "priority": 300,
    })
