"""SquadOps Artifacts plugin — browsing, ingestion, baselines, and download."""


def register(ctx):
    """Register Artifacts plugin contributions."""
    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "squadops-artifacts-list",
        "priority": 400,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "discovery",
        "component": "squadops-artifacts-browser",
        "priority": 500,
    })

    ctx.register_contribution("panel", {
        "slot": "ui.slot.right_rail",
        "perspective": "signal",
        "component": "squadops-artifacts-detail",
        "priority": 500,
    })

    ctx.register_contribution("command", {
        "id": "squadops.ingest_artifact",
        "label": "Ingest Artifact",
        "action": "squadops.ingest_artifact",
        "danger_level": "safe",
    })

    ctx.register_contribution("command", {
        "id": "squadops.set_baseline",
        "label": "Set Baseline",
        "action": "squadops.set_baseline",
        "danger_level": "confirm",
    })

    ctx.register_contribution("command", {
        "id": "squadops.download_artifact",
        "label": "Download Artifact",
        "action": "squadops.download_artifact",
        "danger_level": "safe",
    })
