"""The shared fixture's own checks (SIP-0112 §8.2.3, #2407).

Both lanes build against the fixture's recorded outputs until the other lane's code ships, and each
contract test reads them. These checks keep the fixture saying what it claims. A recording that names
a commit the fixture no longer builds, or a bad form that differs from valid in two ways, would let a
consumer's refusal test pass for the wrong reason.
"""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from fnmatch import fnmatch

import pytest

from squadops.campaigns.evaluator_trees import FileTree
from tests.fixtures.shared_contract.repository import (
    FORMS,
    OUTPUTS,
    PRODUCT,
    FixtureRepository,
    build_repository,
    recorded,
    tracked_files,
)

_VERSION_KEYS = ("schema", "api_version")


def _flatten(value, prefix: tuple = ()) -> dict[tuple, object]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    else:
        return {prefix: value}
    flat: dict[tuple, object] = {}
    for key, child in items:
        flat.update(_flatten(child, (*prefix, key)))
    return flat


def _identities(repository: FixtureRepository) -> dict[str, str]:
    """Each second-commit identifier, mapped to the first commit's identifier of the same kind."""
    first = tracked_files(repository.path, repository.first_commit)
    second = tracked_files(repository.path, repository.second_commit)
    return {
        repository.second_commit: repository.first_commit,
        FileTree.of(second).identity: FileTree.of(first).identity,
    }


def test_the_commits_hash_the_same_whatever_the_machine_git_config(tmp_path, monkeypatch):
    hostile = tmp_path / "gitconfig"
    hostile.write_text(
        "[commit]\n\tgpgsign = true\n[core]\n\tautocrlf = true\n"
        "[user]\n\tname = Someone Else\n[init]\n\tdefaultBranch = trunk\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Someone Else")
    # Under a hook, GIT_DIR names the caller's repository.
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "callers-repository"))

    built = build_repository(tmp_path / "tally")

    mapping = recorded("workspace_commit_mapping", "valid")
    assert [e["commit"] for e in mapping["entries"]] == [built.first_commit, built.second_commit]
    context = recorded("project_source_context", "valid")
    assert context["development_baseline_commit"] == built.second_commit
    assert not (tmp_path / "callers-repository").exists()


def test_every_identifier_a_valid_recording_names_is_what_the_fixture_builds(repository):
    for entry in recorded("workspace_commit_mapping", "valid")["entries"]:
        files = tracked_files(repository.path, entry["commit"])
        assert entry["tree_identity"] == FileTree.of(files).identity, entry["direction"]

    configuration = recorded("development_configuration", "valid")["configuration"]
    second = tracked_files(repository.path, repository.second_commit)
    assert configuration["validated_at_commit"] == repository.second_commit
    for source in configuration["instruction_sources"]:
        digest = hashlib.sha256(second[source["path"]]).hexdigest()
        assert (source["digest"], source["at_commit"]) == (
            f"sha256:{digest}",
            repository.second_commit,
        )
    assert recorded("inherited_baseline", "valid")["commit"] == repository.second_commit
    profile = recorded("derived_profile", "valid")
    assert (profile["commit"], profile["development_configuration_revision"]) == (
        repository.second_commit,
        configuration["revision"],
    )


def test_the_derived_profile_names_only_the_checks_and_files_the_fixture_has(repository):
    profile = recorded("derived_profile", "valid")
    commands = recorded("development_configuration", "valid")["configuration"]["technical"]
    checks = {c["id"] for c in commands["commands"]["checks"]}
    files = tracked_files(repository.path, repository.second_commit)
    (runner,) = profile["test_runners"]

    assert (
        profile["environment"]["image"]
        == (recorded("inherited_baseline", "valid")["environment"]["image"])
    )
    assert set(runner["checks"]) <= checks
    assert {c for t in profile["toolchains"] for c in t["required_by"]} == checks
    tests = {p for p in files if any(fnmatch(p, g) for g in profile["files"]["test"])}
    assert tests == {p for p in files if p.startswith("checks/")}


def test_the_derived_one_file_command_runs_that_file_alone(repository):
    (runner,) = recorded("derived_profile", "valid")["test_runners"]

    def run(name: str) -> subprocess.CompletedProcess:
        argv = [a.replace("{name}", name) for a in runner["single_file_argv"]]
        return subprocess.run(argv, cwd=repository.path, capture_output=True, text=True, timeout=60)

    # check_parse.py fails before any change (IR-9), so a command that ran the whole suite would
    # fail for ledger too.
    ledger, parse = run("check_ledger.py"), run("check_parse.py")
    assert ledger.returncode == 0, ledger.stderr[-2000:]
    assert parse.returncode == 1 and "Ran 3 tests" in parse.stderr


@pytest.mark.parametrize("output", OUTPUTS)
@pytest.mark.parametrize("form", [f for f in FORMS if f != "valid"])
def test_each_bad_form_differs_from_valid_only_as_it_says(repository, output, form):
    valid = _flatten(recorded(output, "valid"))
    bad = _flatten(recorded(output, form))
    changed = {path for path in valid.keys() & bad.keys() if valid[path] != bad[path]}

    if form == "missing_field":
        assert len(valid.keys() - bad.keys()) == 1 and bad.keys() < valid.keys()
        assert not changed
    elif form == "unknown_major":
        assert bad.keys() == valid.keys() and len(changed) == 1
        ((key,),) = changed
        assert key in _VERSION_KEYS
        assert valid[(key,)].endswith("/v1") and bad[(key,)].endswith("/v2")
    else:
        assert bad.keys() == valid.keys() and changed
        stale = _identities(repository)
        assert {(valid[p], bad[p]) for p in changed} <= set(stale.items())


def test_the_binary_asset_reaches_the_repository_byte_for_byte(repository):
    asset = tracked_files(repository.path, repository.second_commit)["assets/mark.png"]

    assert asset == (PRODUCT / "assets" / "mark.png").read_bytes()
    assert asset.startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnicodeDecodeError):
        asset.decode("utf-8")


def test_the_native_checks_reproduce_the_inherited_baseline(repository, monkeypatch):
    commands = recorded("development_configuration", "valid")["configuration"]["technical"]
    checks = {c["id"]: c for c in commands["commands"]["checks"]}
    baseline = {c["id"]: c for c in recorded("inherited_baseline", "valid")["checks"]}
    for check in checks.values():
        for name in check.get("requires_environment", []):
            monkeypatch.delenv(name, raising=False)

    assert list(checks) == list(baseline)
    for check_id, check in checks.items():
        expected = baseline[check_id]["result"]
        if expected == "UNVERIFIED":
            assert check.get("requires_environment"), check_id
            continue
        ran = subprocess.run(
            check["argv"], cwd=repository.path, capture_output=True, text=True, timeout=60
        )
        assert (ran.returncode == 0) == (expected == "PASS"), (check_id, ran.stderr[-2000:])

    # The build's dist/ and the checks' bytecode never enter the tracked tree.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repository.path, capture_output=True, text=True
    )
    assert status.stdout == ""


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_the_start_declaration_starts_the_product(repository):
    start = recorded("development_configuration", "valid")["configuration"]["technical"][
        "commands"
    ]["start"]
    readiness, (entry,) = start["readiness"], start["entry_points"]
    port = int(start["start"][start["start"].index("--port") + 1])
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0, f"port {port} is already in use"
    cwd = repository.path / start["working_directory"]
    for argv in start["build"]:
        subprocess.run(argv, cwd=cwd, check=True, capture_output=True, timeout=60)
    # The runner resolves each evaluation_environment reference into the copy's environment.
    environment = {
        **os.environ,
        **{name: "evaluation-token" for name in start["evaluation_environment"]},
    }

    product = subprocess.Popen(start["start"], cwd=cwd, env=environment, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + readiness["timeout_seconds"]
        status = None
        while time.monotonic() < deadline and status != 200:
            try:
                status, _ = _get(readiness["target"])
            except OSError:
                time.sleep(0.1)
        assert status == 200, product.stderr.read1().decode() if product.poll() is not None else ""

        assert _get(entry["url"] + "no-such-route")[0] == 404
        assert _get(entry["url"] + "mark.png") == (
            200,
            (PRODUCT / "assets" / "mark.png").read_bytes(),
        )
        assert _get(entry["url"] + "admin", {"Authorization": "Bearer evaluation-token"})[0] == 200
    finally:
        product.terminate()
        product.wait(timeout=10)


def test_the_repository_is_never_built_over_an_existing_directory(tmp_path):
    (tmp_path / "tally").mkdir()

    with pytest.raises(FileExistsError):
        build_repository(tmp_path / "tally")
