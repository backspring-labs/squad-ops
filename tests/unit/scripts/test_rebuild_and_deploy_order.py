"""``rebuild_and_deploy.sh`` syncs prompts before it restarts the agents (#1691).

What bug would this catch? #1691's order: the agents restarted in step 4 and the prompt sync ran
in step 4b. Since #352 an agent refuses to boot against a registry missing an asset its image
ships, so every agent restart-looped until the sync landed, and a skipped or failed sync left
them there with the deploy reporting success. The script is read, not run — running it builds
images — so this pins the three properties the fix is made of.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

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


def test_the_deploy_is_recorded_after_the_agents_restart_and_an_unrecorded_one_fails():
    """#1720: a record taken before the restart would name the images being replaced, and a
    deploy that exited 0 unrecorded would leave every new cycle referencing the previous deploy."""
    text = SCRIPT.read_text()
    restart = text.index("docker compose up -d --wait $agent")
    record = text.index('"$REPO_ROOT/scripts/dev/ops/record_deploy.sh"')

    assert restart < record
    assert text.index("DEPLOY_RECORD_FAILED=1") > record
    assert '[ "${DEPLOY_RECORD_FAILED:-0}" = "1" ] && DEPLOY_FAILED=1' in text


def test_the_default_rebuild_takes_every_agent_service_the_compose_file_defines():
    """The 1.9 deploy's record (#1720) showed han still on a 1.8 image after `all`: the default was
    a literal list of seven agents, and han (the Solo arm, 1.8.1) was never added. The selector is
    run here, as the script runs it, over the compose file's services."""
    import json
    import subprocess
    import sys

    import yaml

    text = SCRIPT.read_text()
    selector = re.search(r"python3 -c '(import json, sys\n.*?)'\)", text, re.S).group(1)
    compose = yaml.safe_load((SCRIPT.parents[3] / "docker-compose.yml").read_text())
    agent_services = sorted(
        name
        for name, svc in compose["services"].items()
        if (svc.get("build") or {}).get("dockerfile") == "agents/Dockerfile"
    )

    selected = subprocess.run(
        [sys.executable, "-c", selector],
        input=json.dumps({"services": compose["services"]}),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    assert selected == agent_services
    assert "han" in selected
    assert 'grep -E "^(max|nat|neo|eve|bob|data|joi)$"' not in text


def test_the_sandbox_is_rebuilt_before_the_record_and_a_failed_one_fails_the_deploy():
    """#2193: the sandbox is opt-in, so `all` never built it. Rebuild 11 rebuilt it by hand after
    the script's record, and the record named the previous sandbox image for every cycle on that
    deploy. `all` now rebuilds it when the deploy runs it, before the record."""
    text = SCRIPT.read_text()
    up = text.index("docker compose --profile sandbox up -d --wait sandbox-service")
    record = text.index('"$REPO_ROOT/scripts/dev/ops/record_deploy.sh"')

    assert up < record
    # `all` asks whether this deploy runs it; it never starts an opt-in service unasked.
    assert "--profile sandbox ps -q --status running sandbox-service" in text[:up]
    assert '[ "${SANDBOX_FAILED:-0}" = "1" ] && DEPLOY_FAILED=1' in text


def test_every_image_built_from_the_source_hash_carries_it_as_its_revision_label():
    """#2193: the sandbox image took SOURCE_HASH and carried no label, so the deploy record could
    name its image but never the commit it was built from (revision ``None``, as for postgres)."""
    import yaml

    root = SCRIPT.parents[3]
    compose = yaml.safe_load((root / "docker-compose.yml").read_text())
    dockerfiles = sorted(
        {
            svc["build"]["dockerfile"]
            for svc in compose["services"].values()
            if "SOURCE_HASH" in ((svc.get("build") or {}).get("args") or {})
        }
    )
    unlabelled = [
        d
        for d in dockerfiles
        if 'LABEL org.opencontainers.image.revision="${SOURCE_HASH}"' not in (root / d).read_text()
    ]

    assert "src/squadops/sandbox/Dockerfile" in dockerfiles
    assert unlabelled == []


@pytest.mark.parametrize(
    ("engine", "running", "outcome"),
    [
        ("tensorfold", "true", "kept"),
        ("tensorfold", "false", "refused"),
        ("ollama", "true", "refused"),
        ("ollama", "false", "ollama"),
        ("ollama", "", "ollama"),
    ],
    ids=[
        "the deploy on TensorFold, serving",
        "the deploy on TensorFold, not serving",
        "TensorFold serving a deploy on Ollama",
        "the deploy on Ollama",
        "no TensorFold container",
    ],
)
def test_a_deploy_keeps_the_engine_its_env_records_and_refuses_a_half_done_switch(
    tmp_path, engine, running, outcome
):
    """SIP-0111 §5.6, after the cutover (#2229). Bugs caught: a rebuild on a TensorFold deploy that
    starts Ollama beside it (two engines in unified memory) or refuses to deploy at all; one on an
    Ollama deploy that runs beside a TensorFold a switch left serving. Only the guard and step 1's
    choice run, against a ``docker`` and a switch that answer as the box would."""
    text = SCRIPT.read_text()
    guard = text.index('DEPLOY_ENGINE="$(')
    end = text.index("elif ! check_ollama; then", guard)
    fake = tmp_path / "docker"
    fake.write_text(f"#!/bin/sh\n[ -n '{running}' ] && echo {running} || exit 1\n")
    fake.chmod(0o755)
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text(f"#!/bin/sh\necho {engine}\n")
    (venv / "python").chmod(0o755)
    done = subprocess.run(
        [
            "bash",
            "-c",
            "RED= YELLOW= GREEN= BLUE= NC=\n"
            + text[guard:end]
            + "else echo ollama-step; fi\necho deployed\n",
        ],
        cwd=tmp_path,
        env={"PATH": f"{tmp_path}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )

    if outcome == "refused":
        assert (done.returncode, "deployed" in done.stdout) == (1, False)
    else:
        assert done.returncode == 0, done.stdout
        assert ("ollama-step" in done.stdout) is (outcome == "ollama")
        assert "deployed" in done.stdout


@pytest.mark.parametrize(("sync_rc", "flag"), [(1, "1"), (0, "0")], ids=["failed", "synced"])
def test_a_failed_realm_sync_fails_the_deploy(sync_rc, flag):
    """#2426. Bug caught: a failed Keycloak realm sync printed a yellow line and the deploy ended
    "complete" with exit 0, so the realms went without the exports' new clients and roles (the
    MacBook's 2026-10-18 deploy). The script's own sync block runs here, with compose and the sync
    stubbed; that the flag fails the deploy is read from the banner's list, as for the others."""
    text = SCRIPT.read_text()
    start = text.index("if docker compose config --services | grep -q '^squadops-keycloak$'")
    block = text[start : text.index("\nfi\n", start) + 4]
    probe = (
        "docker() { echo squadops-keycloak; }\n"
        f"sync_keycloak_realms() {{ return {sync_rc}; }}\n"
        "RED= YELLOW= NC=\n"
        f"{block}"
        'echo "REALM_SYNC_FAILED=${REALM_SYNC_FAILED:-0}"\n'
    )
    done = subprocess.run(["bash", "-c", probe], capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines()[-1] == f"REALM_SYNC_FAILED={flag}"
    assert '[ "${REALM_SYNC_FAILED:-0}" = "1" ] && DEPLOY_FAILED=1' in text
