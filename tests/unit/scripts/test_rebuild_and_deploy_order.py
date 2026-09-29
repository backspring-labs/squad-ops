"""``rebuild_and_deploy.sh`` syncs prompts before it restarts the agents (#1691).

What bug would this catch? #1691's order: the agents restarted in step 4 and the prompt sync ran
in step 4b. Since #352 an agent refuses to boot against a registry missing an asset its image
ships, so every agent restart-looped until the sync landed, and a skipped or failed sync left
them there with the deploy reporting success. The script is read, not run — running it builds
images — so this pins the three properties the fix is made of.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "rebuild_and_deploy.sh"


def test_the_sync_precedes_the_restart_which_a_failed_sync_withholds_and_fails_the_deploy():
    text = SCRIPT.read_text()
    sync = text.index("scripts/maintainer/upload_prompts_to_langfuse.py")
    restart = text.index("docker compose up -d --wait $agent")

    assert sync < restart, "the agents restart before their prompts are in the registry"
    # Both ways a sync can fall short set the flag: skipped (LangFuse not up) and failed.
    between = text[sync - 1500 : restart]
    assert len(re.findall(r"PROMPT_SYNC_FAILED=1", between)) == 2
    # The restart is withheld when the sync fell short, and the deploy fails.
    gate = text.rindex('if [ "$PROMPT_SYNC_FAILED" = "1" ]; then', 0, restart)
    assert "Agents NOT restarted" in text[gate:restart]
    assert '[ "${PROMPT_SYNC_FAILED:-0}" = "1" ] && DEPLOY_FAILED=1' in text


def test_the_agent_health_check_reads_the_agents_own_mark_not_a_module_import():
    """The other half of #1691: ``--wait`` returned on a health check that imported a module,
    which passes whether or not the agent process started."""
    dockerfile = (SCRIPT.parents[3] / "agents" / "Dockerfile").read_text()
    (check,) = re.findall(r"HEALTHCHECK[^\n]*\\\n\s*CMD ([^\n]+)", dockerfile)

    assert check.startswith("python -m squadops.agents.readiness")
    assert "import" not in check
