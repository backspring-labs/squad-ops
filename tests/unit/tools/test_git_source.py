"""The managed clone on Git, against real repositories (SIP-0112 E.4.2, FR-05, FR-06).

The shared fixture (#2407) is the product: cloned through a configured local root, its base ref
must resolve to the recorded commit, and its tree must read back with the recorded identity.
"""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path

import pytest

from adapters.tools.git_source import GitSourceRepository
from squadops.campaigns.evaluator_trees import FileTree
from squadops.projects.models import SourceUnavailable
from squadops.projects.registration import LocatorPolicy
from tests.fixtures.shared_contract.repository import build_repository, recorded

pytestmark = pytest.mark.domain_adapters


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def product(tmp_path):
    return build_repository(tmp_path / "sources" / "tally")


@pytest.fixture
def clones(tmp_path):
    return GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )


async def test_the_fixture_resolves_to_its_recorded_commit_and_tree(product, clones):
    """Bugs caught: a clone that reads a working tree instead of the commit; a byte changed in
    transit (the binary asset, a line ending); a mode lost. Each would make the seeded tree
    differ from the one the recorded mapping names."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    tree = await clones.tree_at("prj-tally", commit)

    captured = recorded("workspace_commit_mapping", "valid")["entries"][1]
    assert commit == product.second_commit == captured["commit"]
    assert FileTree.of(tree.files).identity == captured["tree_identity"]
    assert (tree.executable, tree.capability_gaps) == (frozenset(), [])
    first = await clones.tree_at("prj-tally", product.first_commit)
    assert "tally/report.py" not in first.files


async def test_a_second_sync_fetches_what_upstream_moved_to(product, clones):
    """FR-06: the external repository is the authority. Bug caught: a cached clone answering
    with the commit it first saw, so an outside contribution is never seen (E.4.4's drift)."""
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    (product.path / "NOTES.md").write_text("an outside change\n")
    _git(product.path, "add", "NOTES.md")
    _git(product.path, "commit", "-q", "-m", "outside")
    moved = _git(product.path, "rev-parse", "HEAD")

    assert await clones.sync("prj-tally", str(product.path), "refs/heads/main") == moved
    assert "NOTES.md" in (await clones.tree_at("prj-tally", moved)).files


async def test_modes_symlinks_submodules_and_odd_paths_are_read_as_git_records_them(
    tmp_path, clones
):
    repo = tmp_path / "sources" / "odd"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "gradlew").write_text("#!/bin/sh\necho build\n")
    (repo / "gradlew").chmod(0o755)
    (repo / "README.md").write_text("odd\n")
    os.symlink("README.md", repo / "README-link.md")
    _git(repo, "add", "-A")
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{'a' * 40},vendor/lib")
    # A Latin-1 name, written through the index: macOS refuses it as a file name.
    blob = _git(repo, "hash-object", "-w", "README.md")
    subprocess.run(
        [
            b"git",
            b"update-index",
            b"--add",
            b"--cacheinfo",
            f"100644,{blob},".encode() + b"caf\xe9.txt",
        ],
        cwd=repo,
        check=True,
    )
    _git(repo, "commit", "-q", "-m", "odd")

    commit = await clones.sync("prj-odd", str(repo), "refs/heads/main")
    tree = await clones.tree_at("prj-odd", commit)

    assert tree.executable == frozenset({"gradlew"})
    assert set(tree.files) == {"gradlew", "README.md"}
    assert tree.capability_gaps == [
        "paths that aren't UTF-8: caf\\xe9.txt",
        "tracked symlinks: README-link.md",
        "submodules: vendor/lib",
    ]


async def test_a_captured_tree_is_committed_exactly_and_survives_the_next_sync(product, clones):
    """E.4.3's capture (contract 3). Bugs caught:
    - a mode, a byte or an awkward path lost on the way into Git;
    - a file the candidate dropped kept from the parent;
    - the mirror's ``fetch --prune`` deleting the captured ref, since the product never has it."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    tree = await clones.tree_at("prj-tally", commit)
    files = {p: c for p, c in tree.files.items() if p != "tally/notify.py"}
    files['docs/a "quoted" name\twith tab.md'] = b"odd\r\n"
    files["tools/run.sh"] = b"#!/bin/sh\necho run\n"

    captured = await clones.commit_tree(
        "prj-tally",
        parent=commit,
        files=files,
        executable={"tools/run.sh"},
        ref="refs/squadops/cyc_1/run_1",
        message="a change\n",
    )
    (product.path / "NOTES.md").write_text("an outside change\n")
    _git(product.path, "add", "NOTES.md")
    _git(product.path, "commit", "-q", "-m", "outside")
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    back = await clones.tree_at("prj-tally", captured)
    assert back.files == files
    assert back.executable == frozenset({"tools/run.sh"})
    clone = clones._clone_dir("prj-tally")
    assert _git(clone, "rev-parse", "refs/squadops/cyc_1/run_1") == captured
    assert _git(clone, "rev-parse", f"{captured}^") == commit
    patch = await clones.export_patch("prj-tally", captured)
    assert b"deleted file mode 100644" in patch and b"new file mode 100755" in patch


@pytest.mark.parametrize(
    ("ref", "parent"),
    [("refs/heads/main", None), ("refs/squadops/../heads/main", None), (None, "f" * 40)],
    ids=["a-product-branch", "escaping-ref", "parent-not-in-clone"],
)
async def test_a_capture_names_only_our_namespace_and_a_parent_the_clone_holds(
    product, clones, ref, parent
):
    """Bugs caught: a capture that moves the product's own branch in the clone (the next fetch
    would silently undo it, or a push would publish it), or one committed on a parent nothing
    can check out."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    with pytest.raises(SourceUnavailable):
        await clones.commit_tree(
            "prj-tally",
            parent=parent or commit,
            files={"a.txt": b"a\n"},
            executable=(),
            ref=ref or "refs/squadops/cyc_1/run_1",
            message="m\n",
        )


@pytest.mark.parametrize(
    ("locator", "ref", "reason"),
    [
        ("/elsewhere/tally", "refs/heads/main", "locator_refused"),
        ("SOURCE", "--upload-pack=x", "ref_refused"),
        ("SOURCE", "refs/heads/nowhere", "resolve"),
        ("SOURCE_MISSING", "refs/heads/main", "clone"),
    ],
)
async def test_what_cannot_be_reached_is_named_never_guessed(product, clones, locator, ref, reason):
    locator = {
        "SOURCE": str(product.path),
        "SOURCE_MISSING": str(product.path.parent / "missing"),
    }.get(locator, locator)

    with pytest.raises(SourceUnavailable) as refused:
        await clones.sync("prj-tally", locator, ref)

    assert refused.value.reason == reason


async def test_the_callers_git_environment_never_reaches_the_clone(product, clones, monkeypatch):
    """Under a hook, GIT_DIR names the caller's repository; every call here would act on it."""
    monkeypatch.setenv("GIT_DIR", str(product.path.parent / "callers-repository"))

    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    assert commit == product.second_commit
    assert not (product.path.parent / "callers-repository").exists()


async def test_a_commit_the_clone_lacks_and_a_bad_id_are_refused(product, clones):
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    with pytest.raises(SourceUnavailable) as missing:
        await clones.tree_at("prj-tally", "0" * 40)
    with pytest.raises(SourceUnavailable) as bad:
        await clones.tree_at("prj-tally", "HEAD")
    with pytest.raises(SourceUnavailable) as escaping:
        await clones.sync("../escape", str(product.path), "refs/heads/main")

    assert (missing.value.reason, bad.value.reason, escaping.value.reason) == (
        "read",
        "not_a_commit",
        "bad_project",
    )


async def test_a_public_name_that_resolves_to_the_deploy_itself_is_refused(clones, monkeypatch):
    """#2459, the clone's half. Bug caught: a registered name whose DNS points at loopback or the
    metadata address, so the runtime API's clone reaches the deploy's own services."""
    import socket

    def resolves_to(address):
        return lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolves_to("169.254.169.254"))
    with pytest.raises(SourceUnavailable) as refused:
        await clones.sync("prj-tally", "https://git.example.org/o/r.git", "refs/heads/main")
    assert refused.value.reason == "internal_host"

    monkeypatch.setattr(socket, "getaddrinfo", resolves_to("127.0.0.1"))
    with pytest.raises(SourceUnavailable) as refused:
        await clones.sync("prj-tally", "git@git.example.org:o/r.git", "refs/heads/main")
    assert refused.value.reason == "internal_host"


async def test_a_push_carries_its_token_in_the_environment_never_an_argument(
    product, clones, monkeypatch
):
    """E.4.3's review_request. Bugs caught: the token in an argument, which any process listing
    shows; an ssh locator pushed with no key to push it; a push to the product's own branch."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    tree = await clones.tree_at("prj-tally", commit)
    await clones.commit_tree(
        "prj-tally", parent=commit, files=tree.files, executable=tree.executable,
        ref="refs/squadops/cyc_1/run_1", message="m\n",
    )  # fmt: skip
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("140.82.112.3", 0))])
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr("adapters.tools.git_source.subprocess.run", run)
    await clones.push_capture(
        "prj-tally", "https://github.com/owner/tally.git", ref="refs/squadops/cyc_1/run_1",
        branch="squadops/cyc_1", token="github_pat_s3cr3t",
    )  # fmt: skip

    [(command, env)] = calls
    assert not any("s3cr3t" in arg for arg in command)
    assert command[-2:] == ["https://github.com/owner/tally.git",
                            "refs/squadops/cyc_1/run_1:refs/heads/squadops/cyc_1"]  # fmt: skip
    header = base64.b64decode(env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: Basic "))
    assert (env["GIT_CONFIG_KEY_0"], header) == (
        "http.extraHeader",
        b"x-access-token:github_pat_s3cr3t",
    )
    for locator, branch in (
        ("git@github.com:owner/tally.git", "squadops/cyc_1"),
        ("https://github.com/owner/tally.git", "main"),
    ):
        with pytest.raises(SourceUnavailable):
            await clones.push_capture(
                "prj-tally", locator, ref="refs/squadops/cyc_1/run_1", branch=branch, token="t"
            )
    assert len(calls) == 1


async def test_a_private_repositorys_fetch_carries_its_token_in_the_environment_alone(
    product, clones, monkeypatch
):
    """A private product's validation and sync (E.4.2, E.4.4, E.4.6). Bugs caught: the token in an
    argument, which any process listing shows; a header on the calls that don't reach the
    product, where it has no use; a fetch with no token sending one anyway."""
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("140.82.112.3", 0))])
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, b"a" * 40 + b"\n", b"")

    monkeypatch.setattr("adapters.tools.git_source.subprocess.run", run)
    locator = "https://github.com/owner/tally.git"
    await clones.sync("prj-tally", locator, "refs/heads/main", token="github_pat_s3cr3t")
    tokened = len(calls)
    await clones.sync("prj-tally", locator, "refs/heads/main")

    assert not any("s3cr3t" in arg for command, _ in calls for arg in command)
    headed = [command for command, env in calls if "GIT_CONFIG_KEY_0" in env]
    assert len(headed) == 1 and "fetch" in headed[0]  # the one tokened fetch, and nothing else
    [env] = [env for command, env in calls[:tokened] if "fetch" in command]
    header = base64.b64decode(env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: Basic "))
    assert header == b"x-access-token:github_pat_s3cr3t"
