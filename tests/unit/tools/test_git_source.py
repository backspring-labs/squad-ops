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
from squadops.projects.models import RebaseConflict, Rebased, RefMoved, SourceUnavailable
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


async def test_a_campaign_branch_moves_only_from_the_commit_its_mover_expected(product, clones):
    """SIP-0109 §24cd point 2: the ref follows its control row by compare-and-swap. Bugs caught:
    - a move from a stale expected commit that lands anyway, so a follow racing the startup
      re-sync puts the branch back on a commit its row has left;
    - a create that overwrites a branch already there;
    - the mirror's ``fetch --prune`` deleting the branch, which the product never has;
    - a ref read by prefix, so a capture's ref under ``refs/squadops/<cycle>/`` answers for a
      name that holds nothing."""
    first = product.first_commit
    second = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    branch = "refs/squadops/campaign/cmp_branch000001"
    await clones.update_ref("prj-tally", branch, new_commit=first, expected_commit=None)

    with pytest.raises(RefMoved) as stale:
        await clones.update_ref("prj-tally", branch, new_commit=second, expected_commit=second)
    with pytest.raises(RefMoved) as exists:
        await clones.update_ref("prj-tally", branch, new_commit=second, expected_commit=None)
    held_after_refusals = await clones.ref_commit("prj-tally", branch)
    await clones.update_ref("prj-tally", branch, new_commit=second, expected_commit=first)
    (product.path / "NOTES.md").write_text("an outside change\n")
    _git(product.path, "add", "NOTES.md")
    _git(product.path, "commit", "-q", "-m", "outside")
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    await clones.commit_tree(
        "prj-tally",
        parent=second,
        files={"a.txt": b"a\n"},
        executable=(),
        ref="refs/squadops/cyc_1/run_1",
        message="m\n",
    )

    assert (stale.value.held, exists.value.held, held_after_refusals) == (first, first, first)
    assert (stale.value.reason, exists.value.reason) == ("ref_moved", "ref_moved")
    assert await clones.ref_commit("prj-tally", branch) == second
    assert await clones.ref_commit("prj-tally", "refs/squadops/cyc_1") is None
    assert await clones.ref_commit("prj-tally", "refs/squadops/campaign/cmp_none") is None


@pytest.mark.parametrize(
    ("ref", "new", "reason"),
    [
        ("refs/heads/main", "FIRST", "ref_refused"),
        ("refs/squadops/../heads/main", "FIRST", "ref_refused"),
        ("refs/squadops/campaign/cmp_1", "f" * 40, "read"),
        ("refs/squadops/campaign/cmp_1", "HEAD", "not_a_commit"),
    ],
    ids=["a-product-branch", "escaping-ref", "commit-not-in-clone", "not-a-commit-id"],
)
async def test_a_branch_moves_only_in_our_namespace_and_to_a_commit_the_clone_holds(
    product, clones, ref, new, reason
):
    """Bugs caught: a move of the product's own branch in the clone (the next fetch would undo
    it, or a push publish it); a branch left naming an object nothing can check out. Each is
    refused before anything moves, and is never read as a lost compare-and-swap."""
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    new = product.first_commit if new == "FIRST" else new

    with pytest.raises(SourceUnavailable) as refused:
        await clones.update_ref("prj-tally", ref, new_commit=new, expected_commit=None)

    assert refused.value.reason == reason
    assert not isinstance(refused.value, RefMoved)
    assert _git(clones._clone_dir("prj-tally"), "rev-parse", "refs/heads/main") == (
        product.second_commit
    )
    if ref.startswith("refs/squadops/campaign/"):
        assert await clones.ref_commit("prj-tally", ref) is None


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


@pytest.mark.parametrize(
    "read",
    [
        lambda clones, commit: clones.file_at("prj-tally", commit, "CONTRIBUTING.md"),
        lambda clones, commit: clones.commit_message("prj-tally", commit),
        lambda clones, commit: clones.export_patch("prj-tally", commit),
        lambda clones, commit: clones.is_ancestor("prj-tally", commit, commit),
    ],
    ids=["file_at", "commit_message", "export_patch", "is_ancestor"],
)
async def test_a_clone_moved_aside_is_named_never_read_as_git_missing(
    product, clones, tmp_path, read
):
    """#2672. Bug caught: git run in a clone directory that isn't there raises the same
    ``FileNotFoundError`` as a git binary that isn't, and each was reported as "git is not
    installed here", sending an operator after git when the clone is what's missing."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    clone = tmp_path / "cache" / "prj-tally.git"
    clone.rename(tmp_path / "cache" / "moved-aside.git")

    with pytest.raises(SourceUnavailable) as missing:
        await read(clones, commit)

    assert (missing.value.reason, str(missing.value)) == (
        "not_cloned",
        f"the managed clone is missing: {clone} does not exist",
    )


async def test_git_missing_from_the_path_is_still_named_as_git(
    product, clones, tmp_path, monkeypatch
):
    """#2672's other half. Bug caught: every ``FileNotFoundError`` read as a missing clone, so a
    deploy whose image has no git sends its operator to a clone that is there."""
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    no_git = tmp_path / "bin-without-git"
    no_git.mkdir()
    monkeypatch.setenv("PATH", str(no_git))

    with pytest.raises(SourceUnavailable) as missing:
        await clones.file_at("prj-tally", commit, "CONTRIBUTING.md")

    assert (missing.value.reason, str(missing.value)) == ("no_git", "git is not installed here")


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


async def test_the_token_never_reaches_the_error_git_reports(product, tmp_path):
    """The owner's ruling of 2026-10-20 kept the token as an environment header (D11), with this
    test for the one path not yet covered: git's own error text, which a ``SourceUnavailable``
    carries to the API's answer and the logs. Real git, against an allow-listed address that
    refuses the connection, on the fetch and the push."""
    unreachable = "https://127.0.0.1:1/owner/tally.git"
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of(["127.0.0.1"], [str(product.path.parent)]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    commit = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    tree = await clones.tree_at("prj-tally", commit)
    await clones.commit_tree(
        "prj-tally", parent=commit, files=tree.files, executable=tree.executable,
        ref="refs/squadops/cyc_1/run_1", message="m\n",
    )  # fmt: skip
    token = "github_pat_s3cr3tTOKEN"
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()

    failures = []
    for attempt in (
        clones.sync("prj-tally", unreachable, "refs/heads/main", token=token),
        clones.push_capture(
            "prj-tally", unreachable, ref="refs/squadops/cyc_1/run_1", branch="squadops/cyc_1",
            token=token,
        ),
    ):  # fmt: skip
        with pytest.raises(SourceUnavailable) as failed:
            await attempt
        failures.append(str(failed.value))

    assert all("127.0.0.1" in f for f in failures)  # git's own text, naming the host it tried
    assert not any(token in f or basic in f or "s3cr3t" in f for f in failures)


# --- SIP-0109 §24bv point 4: a campaign branch rebased onto the commit its Project reconciled ---


async def _branch_of_two(clones, base: str) -> tuple[str, str]:
    """A campaign branch on ``base``: two captures, one on the other, as two promotions leave it.
    The first appends to the report module, the second adds a new file."""
    tree = await clones.tree_at("prj-tally", base)
    report = tree.files["tally/report.py"] + b"\n\ndef total(ledger):\n    return len(ledger)\n"
    first = await clones.commit_tree(
        "prj-tally", parent=base, files={**tree.files, "tally/report.py": report},
        executable=tree.executable, ref="refs/squadops/cyc_1/run_1", message="first increment\n",
    )  # fmt: skip
    second = await clones.commit_tree(
        "prj-tally", parent=first,
        files={**tree.files, "tally/report.py": report, "docs/notes.md": b"notes\n"},
        executable=tree.executable, ref="refs/squadops/cyc_2/run_2", message="second increment\n",
    )  # fmt: skip
    return first, second


def _upstream(product, path: str, content: str, message: str) -> None:
    target = product.path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _git(product.path, "add", "-A")
    _git(product.path, "commit", "-q", "-m", message)


async def test_a_branch_rebases_onto_upstream_keeping_each_change_and_its_author(product, clones):
    """§24bv point 4. Bugs caught:
    - a rebase that squashes the branch, or drops an increment's change;
    - upstream's own change lost from the rebased head (the branch's tree copied over it);
    - a new commit losing its message or author, so the review request reads as another's;
    - a second rebase of the same branch writing other commits, so a replay after a restart is
      read as a conflicting row (the row's key names the base; its content names the head)."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    first, second = await _branch_of_two(clones, base)
    _upstream(product, "README.md", "Tally, as upstream now describes it\n", "upstream docs")
    onto = await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    rebased = await clones.rebase("prj-tally", base=base, head=second, onto=onto)
    again = await clones.rebase("prj-tally", base=base, head=second, onto=onto)

    clone = clones._clone_dir("prj-tally")
    [(old_first, new_first), (old_second, new_second)] = rebased.replayed
    assert (old_first, old_second, new_second, rebased.dropped) == (
        first,
        second,
        rebased.commit,
        (),
    )
    assert _git(clone, "rev-parse", f"{new_first}^") == onto
    assert _git(clone, "log", "-1", "--format=%s|%an", new_first) == "first increment|SquadOps"
    files = (await clones.tree_at("prj-tally", rebased.commit)).files
    assert files["README.md"] == b"Tally, as upstream now describes it\n"
    assert files["tally/report.py"].endswith(b"def total(ledger):\n    return len(ledger)\n")
    assert files["docs/notes.md"] == b"notes\n"
    assert again == rebased
    assert await clones.ref_commit("prj-tally", "refs/squadops/cyc_2/run_2") == second


async def test_a_change_upstream_already_holds_rebases_to_upstream_itself(product, clones):
    """§24cd point 4: the owner's merge is a rebase that ends at the merge commit. Here upstream
    took the branch by a merge, and separately by a squash of the same change. Bugs caught: the
    branch's commits replayed on top as empty or duplicate commits, so the next increment's pin
    is a commit upstream never had and its baseline isn't upstream's; or a merge refused as a
    conflict."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    _first, second = await _branch_of_two(clones, base)
    clone = str(clones._clone_dir("prj-tally"))
    _git(product.path, "fetch", "-q", clone, f"{second}:refs/heads/review")
    _git(product.path, "merge", "-q", "--no-ff", "-m", "Merge the review request", "review")
    merged = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    _git(product.path, "checkout", "-q", "-b", "squash", base)
    _git(product.path, "merge", "-q", "--squash", "review")
    _git(product.path, "commit", "-q", "-m", "Squash the review request")
    squash = _git(product.path, "rev-parse", "HEAD")
    _git(product.path, "checkout", "-q", "main")
    _git(product.path, "reset", "-q", "--hard", squash)
    assert await clones.sync("prj-tally", str(product.path), "refs/heads/main") == squash

    by_merge = await clones.rebase("prj-tally", base=base, head=second, onto=merged)
    by_squash = await clones.rebase("prj-tally", base=base, head=second, onto=squash)

    assert (by_merge.commit, by_merge.replayed) == (merged, ())
    assert (by_squash.commit, by_squash.replayed) == (squash, ())
    assert len(by_merge.dropped) == len(by_squash.dropped) == 2


async def test_a_branch_commit_that_conflicts_upstream_is_named_and_writes_no_ref(product, clones):
    """§24bv point 4: a conflict refuses, and nothing resolves itself. Bugs caught: a conflict
    resolved by taking one side, so upstream's change or the increment's is silently lost; the
    conflict reported without the commit and the file a reader resolves; a ref moved anyway."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    first, second = await _branch_of_two(clones, base)
    report = (product.path / "tally" / "report.py").read_text()
    _upstream(product, "tally/report.py", report + "\n\ndef top(ledger):\n    return None\n", "up")
    onto = await clones.sync("prj-tally", str(product.path), "refs/heads/main")

    with pytest.raises(RebaseConflict) as conflict:
        await clones.rebase("prj-tally", base=base, head=second, onto=onto)

    assert (conflict.value.commit, conflict.value.paths) == (first, ("tally/report.py",))
    assert conflict.value.reason == "rebase_conflict"
    assert await clones.ref_commit("prj-tally", "refs/squadops/cyc_2/run_2") == second


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("same-base", None),
        ("base-not-in-history", "not_an_ancestor"),
        ("bad-id", "not_a_commit"),
        ("a-merge-on-the-branch", "not_linear"),
        ("a-head-the-clone-lacks", "commit_missing"),
        ("onto-the-clone-lacks", "commit_missing"),
    ],
)
async def test_a_rebase_with_nothing_to_move_or_no_history_to_move(product, clones, case, reason):
    """The edges, each refused by a reason the launcher sorts on (SIP-0109 §24cm). A base equal to
    the commit rebased onto is a revision-only reconciliation: the head stays. Bugs caught: the
    head rewritten for nothing; a base that isn't in the head's history replaying commits that
    aren't the branch's own; an id passed to git unchecked; a merge commit replayed as if linear;
    a commit the clone lacks read as git failing (a fault the next drain repeats forever) rather
    than named."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    first, second = await _branch_of_two(clones, base)
    clone = clones._clone_dir("prj-tally")
    merged = _git(
        clone, "commit-tree", f"{second}^{{tree}}", "-p", first, "-p", base, "-m", "a merge"
    )
    arguments = {
        "same-base": dict(base=base, head=second, onto=base),
        "base-not-in-history": dict(base=second, head=base, onto=base),
        "bad-id": dict(base="--all", head=second, onto=base),
        "a-merge-on-the-branch": dict(base=base, head=merged, onto=product.first_commit),
        "a-head-the-clone-lacks": dict(base=base, head="e" * 40, onto=base),
        "onto-the-clone-lacks": dict(base=base, head=second, onto="e" * 40),
    }[case]

    if reason is None:
        assert await clones.rebase("prj-tally", **arguments) == Rebased(second, (), ())
        return
    with pytest.raises(SourceUnavailable) as refused:
        await clones.rebase("prj-tally", **arguments)
    assert refused.value.reason == reason


# --- SIP-0109 §24ci (b): a Campaign's review branch, forced only with a lease ---

_CAMPAIGN = "cmp_review000001"
_CAMPAIGN_REF = f"refs/squadops/campaign/{_CAMPAIGN}"
_CAMPAIGN_BRANCH = f"squadops/{_CAMPAIGN}"


async def _campaign_at(clones, commit: str, expected: str | None) -> None:
    await clones.update_ref("prj-tally", _CAMPAIGN_REF, new_commit=commit, expected_commit=expected)


async def _push(clones, product, lease):
    await clones.push_campaign_branch(
        "prj-tally", str(product.path), campaign_id=_CAMPAIGN, branch=_CAMPAIGN_BRANCH,
        token="tok_invented_for_the_test", lease=lease,
    )  # fmt: skip


async def test_a_campaigns_review_branch_is_rewritten_only_under_its_lease(product, clones):
    """§24ci (b). The first push creates the branch unforced; after a rebase the push replaces it
    under a lease on what was pushed; a retry of a push that landed is up to date; and a branch
    someone else moved since is refused and left as they left it. Bugs caught:
    - a rebased head refused for good, so the review request never shows upstream's change;
    - a force with no lease, so an outside reviewer's commit on the branch is overwritten;
    - a retry after a push whose row never committed read as a moved branch."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    first, second = await _branch_of_two(clones, base)
    rebased = await clones.commit_tree(
        "prj-tally", parent=base, files=(await clones.tree_at("prj-tally", second)).files,
        executable=(), ref="refs/squadops/cyc_3/run_3", message="the rebased second\n",
    )  # fmt: skip
    await _campaign_at(clones, first, None)

    await _push(clones, product, None)
    pushed_first = _git(product.path, "rev-parse", f"refs/heads/{_CAMPAIGN_BRANCH}")
    await _campaign_at(clones, rebased, first)
    await _push(clones, product, first)
    await _push(clones, product, first)  # the retry: the branch is already at the commit
    pushed_rebased = _git(product.path, "rev-parse", f"refs/heads/{_CAMPAIGN_BRANCH}")
    clone = str(clones._clone_dir("prj-tally"))
    _git(product.path, "fetch", "-q", clone, f"+{second}:refs/heads/{_CAMPAIGN_BRANCH}")  # another
    await _campaign_at(clones, first, rebased)

    with pytest.raises(SourceUnavailable) as moved:
        await _push(clones, product, rebased)

    assert (pushed_first, pushed_rebased) == (first, rebased)
    assert moved.value.reason == "lease_refused"
    assert _git(product.path, "rev-parse", f"refs/heads/{_CAMPAIGN_BRANCH}") == second
    assert "tok_invented_for_the_test" not in str(moved.value)


async def test_a_campaigns_first_push_never_forces_over_a_branch_already_there(product, clones):
    """The edge: no push recorded yet, and the product already holds the branch with other
    history. Bug caught: a first push forced over it, since with no lease there is nothing to
    say the branch is the Campaign's."""
    base = await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    first, _second = await _branch_of_two(clones, base)
    await _campaign_at(clones, first, None)
    other = await clones.commit_tree(
        "prj-tally", parent=base, files={"other.txt": b"other\n"}, executable=(),
        ref="refs/squadops/cyc_9/run_9", message="someone else's\n",
    )  # fmt: skip
    _git(
        product.path,
        "fetch",
        "-q",
        str(clones._clone_dir("prj-tally")),
        f"{other}:refs/heads/{_CAMPAIGN_BRANCH}",
    )

    with pytest.raises(SourceUnavailable) as refused:
        await _push(clones, product, None)

    assert refused.value.reason == "not_fast_forward"
    assert _git(product.path, "rev-parse", f"refs/heads/{_CAMPAIGN_BRANCH}") == other


@pytest.mark.parametrize(
    ("campaign_id", "branch", "lease", "reason"),
    [
        ("cmp_review000001", "squadops/cyc_1", None, "ref_refused"),
        ("cmp_review000001", "main", None, "ref_refused"),
        ("cyc_1", "squadops/cyc_1", None, "ref_refused"),
        ("cmp_review000001", "squadops/cmp_review000001", "HEAD~1", "not_a_commit"),
    ],
    ids=["a-runs-branch", "the-products-branch", "not-a-campaign", "a-lease-not-a-commit"],
)
async def test_only_a_campaigns_own_branch_is_pushed_with_a_lease(
    product, clones, campaign_id, branch, lease, reason
):
    """The widening of "never forced" is for a Campaign's review branch alone. Bugs caught: a
    lease used to rewrite a run's review branch or the product's own; a lease git would read as
    a revision expression."""
    with pytest.raises(SourceUnavailable) as refused:
        await clones.push_campaign_branch(
            "prj-tally", str(product.path), campaign_id=campaign_id, branch=branch, token="t",
            lease=lease,
        )  # fmt: skip
    assert refused.value.reason == reason


async def test_a_leased_push_carries_its_token_in_the_environment_never_an_argument(
    product, clones, monkeypatch
):
    """The token's rule for a contribution holds for a Campaign's push: an environment header for
    this one push. Bugs caught: the token in an argument, which a process listing shows; the
    lease left off the command, so the push isn't forced at all, or forced without one."""
    await clones.sync("prj-tally", str(product.path), "refs/heads/main")
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("140.82.112.3", 0))])
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr("adapters.tools.git_source.subprocess.run", run)
    await clones.push_campaign_branch(
        "prj-tally", "https://github.com/owner/tally.git", campaign_id=_CAMPAIGN,
        branch=_CAMPAIGN_BRANCH, token="github_pat_inv3nted", lease="a" * 40,
    )  # fmt: skip

    [(command, env)] = calls
    assert not any("inv3nted" in arg for arg in command)
    assert f"--force-with-lease=refs/heads/{_CAMPAIGN_BRANCH}:{'a' * 40}" in command
    assert command[-2:] == ["https://github.com/owner/tally.git",
                            f"{_CAMPAIGN_REF}:refs/heads/{_CAMPAIGN_BRANCH}"]  # fmt: skip
    header = base64.b64decode(env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: Basic "))
    assert header == b"x-access-token:github_pat_inv3nted"
