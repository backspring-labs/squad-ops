"""DockerAdapter hardening-flag rendering (SIP-0102 — 102.1 slice c1)."""

import pytest

from adapters.tools.docker import DockerAdapter
from squadops.tools.models import ContainerSpec


@pytest.fixture
def captured(monkeypatch):
    calls: list[tuple[str, ...]] = []

    async def fake_run_docker(self, *args, timeout=None):
        calls.append(args)
        return 0, "", ""

    monkeypatch.setattr(DockerAdapter, "_run_docker", fake_run_docker)
    return calls


async def test_hardened_spec_renders_every_flag(captured):
    """Bug caught: a hardening field silently ignored by the adapter — the
    sandbox would believe §7 items 9–10 hold while docker runs soft."""
    await DockerAdapter().run(
        ContainerSpec(
            image="img",
            command=["true"],
            network="none",
            memory_limit="2g",
            cpu_limit=2.0,
            pids_limit=512,
            cap_drop_all=True,
            no_new_privileges=True,
        )
    )
    args = list(captured[0])
    for flag, value in [
        ("--network", "none"),
        ("--memory", "2g"),
        ("--cpus", "2.0"),
        ("--pids-limit", "512"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges"),
    ]:
        i = args.index(flag)
        assert args[i + 1] == value
    # Flags precede the image; nothing leaks into the container command.
    assert args.index("img") > args.index("--security-opt")
    assert args[-1] == "true"


async def test_default_spec_emits_no_hardening_flags(captured):
    """Bug caught: defaults emitting flags — pre-0102 callers' docker
    invocations must stay byte-identical (the inert-to-merge guarantee)."""
    await DockerAdapter().run(ContainerSpec(image="img", command=["true"]))
    args = captured[0]
    for flag in (
        "--network",
        "--memory",
        "--cpus",
        "--pids-limit",
        "--cap-drop",
        "--security-opt",
        "-p",
    ):
        assert flag not in args


async def test_run_detached_publishes_to_loopback_and_returns_id(monkeypatch):
    """Bug caught: a published app port bound to 0.0.0.0 (host-wide exposure)
    instead of loopback, or the container id lost — probes and teardown would
    have nothing to address."""
    calls = []

    async def fake_run_docker(self, *args, timeout=None):
        calls.append(args)
        return 0, "abc123\n", ""

    monkeypatch.setattr(DockerAdapter, "_run_docker", fake_run_docker)
    container_id = await DockerAdapter().run_detached(
        ContainerSpec(image="img", command=["serve"], publish_ports=(8000,))
    )
    assert container_id == "abc123"
    args = list(calls[0])
    assert args[:3] == ["run", "-d", "--rm"]
    assert args[args.index("-p") + 1] == "127.0.0.1:0:8000"


@pytest.mark.parametrize(
    ("exit_code", "stderr", "expected"),
    [(0, "", True), (1, "Error: No such image: img", False)],
    ids=["present", "absent"],
)
async def test_has_image_distinguishes_present_from_absent(
    monkeypatch, exit_code, stderr, expected
):
    """Bug caught: preflight's image evidence inverted or guessed — a missing
    image passing preflight stalls the cycle at task time (#306 class)."""

    async def fake_run_docker(self, *args, timeout=None):
        return exit_code, "", stderr

    monkeypatch.setattr(DockerAdapter, "_run_docker", fake_run_docker)
    assert await DockerAdapter().has_image("img") is expected


async def test_has_image_raises_when_the_daemon_cannot_answer(monkeypatch):
    """Bug caught: daemon-down reported as image-absent — a false preflight
    block on an environment that may be perfectly provisioned."""
    from squadops.tools.exceptions import ToolContainerError

    async def fake_run_docker(self, *args, timeout=None):
        return 1, "", "Cannot connect to the Docker daemon"

    monkeypatch.setattr(DockerAdapter, "_run_docker", fake_run_docker)
    with pytest.raises(ToolContainerError, match="inspect image"):
        await DockerAdapter().has_image("img")


async def test_resolve_host_port_parses_docker_port_output(monkeypatch):
    """Bug caught: the ephemeral port mapping misparsed — every probe would
    target the wrong port and fail an app that is actually healthy."""

    async def fake_run_docker(self, *args, timeout=None):
        return 0, "127.0.0.1:49153\n", ""

    monkeypatch.setattr(DockerAdapter, "_run_docker", fake_run_docker)
    assert await DockerAdapter().resolve_host_port("abc123", 8000) == 49153
