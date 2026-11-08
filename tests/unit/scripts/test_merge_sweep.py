"""#2862: a merged contribution syncs its Project and re-validates it, and the sweep only ever reads
from the forge (the owner, 2026-11-08: use the host's current access, and write nothing it
shouldn't)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "merge_sweep.py"
_spec = importlib.util.spec_from_file_location("merge_sweep", _SCRIPT)
sweep_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep_mod)

TOKEN = "gho_" + "x" * 36  # invented; asserted never to reach the output
PR_URL = "https://github.com/acme/widget/pull/11"


class _Api:
    """The runtime API as the sweep sees it, recording every write."""

    def __init__(self, contributions, *, syncs=(), baseline="b0", refuse=None):
        self.contributions = contributions
        self.syncs = list(syncs)
        self.baseline = baseline
        self.refuse = refuse
        self.posts: list[tuple[str, dict]] = []

    def get(self, path):
        if path == "/api/v1/projects":
            return [
                {"project_id": "group_run", "source": None},
                {"project_id": "prj-w", "source": {"repo_uri": "x"},
                 "development_baseline_commit": self.baseline},
            ]  # fmt: skip
        if path.endswith("/contributions"):
            return [{"contribution": c} for c in self.contributions]
        if path.endswith("/syncs"):
            return self.syncs
        raise AssertionError(path)

    def post(self, path, json):
        self.posts.append((path, json))
        if self.refuse and path.endswith(self.refuse):
            raise RuntimeError("SYNC_REFUSED: the baseline moved")
        if path.endswith("/syncs"):
            return {"document": {"upstream_commit": "u1",
                                 "contributions": [{"cycle_id": "cyc_1", "state": "integrated"}]}}  # fmt: skip
        return {"project": {"lifecycle_status": "READY", "development_baseline_commit": "u1"}}


def _forge(merged: bool):
    calls = []

    def get(path):
        calls.append(path)
        return {"merged": merged, "merge_commit_sha": "m" * 40}

    return get, calls


def _pending(**kw):
    return {"cycle_id": "cyc_1", "state": "pending", "review_url": PR_URL, **kw}


def test_a_merged_contribution_syncs_its_project_then_revalidates_it():
    """Bug caught: a merge left the Project's integrated commit where it was until someone synced
    by hand, or synced it without re-validating, so new cycles never waited for the new baseline."""
    api = _Api([_pending()])
    forge, calls = _forge(merged=True)

    lines, ok = sweep_mod.sweep(api, forge_get=forge, token=lambda: TOKEN)

    assert ok and calls == ["repos/acme/widget/pulls/11"]
    assert [path for path, _ in api.posts] == [
        "/api/v1/projects/prj-w/syncs",
        "/api/v1/projects/prj-w/validate",
    ]
    assert all(body["token"] == TOKEN for _, body in api.posts)
    assert api.posts[0][1]["idempotency_key"] == "merge-sweep-" + "m" * 12
    [line] = lines
    assert line["sync"]["contributions"] == [{"cycle_id": "cyc_1", "state": "integrated"}]
    assert line["validated"]["development_baseline_commit"] == "u1"
    assert TOKEN not in json.dumps(lines)


@pytest.mark.parametrize(
    "contributions",
    [[_pending()], [_pending(state="integrated")], [_pending(review_url=None)], []],
    ids=["unmerged", "already-integrated", "no-review-request", "none"],
)
def test_nothing_is_recorded_when_no_pending_contribution_is_merged(contributions):
    """Bug caught: a sync recorded on every poll (noise on the Project, and a re-validation that
    moves the baseline for nothing), or a forge read for a contribution that has no review request."""
    api = _Api(contributions)
    forge, _ = _forge(merged=False)

    lines, ok = sweep_mod.sweep(api, forge_get=forge, token=lambda: TOKEN)

    assert (lines, ok, api.posts) == ([], True, [])


def test_a_refused_sync_is_reported_fails_the_run_and_never_validates():
    """Bug caught: a sync that can't reconcile retried in silence, or a validation run over it."""
    api = _Api([_pending()], refuse="/syncs")
    forge, _ = _forge(merged=True)

    lines, ok = sweep_mod.sweep(api, forge_get=forge, token=lambda: TOKEN)

    assert not ok
    assert [path for path, _ in api.posts] == ["/api/v1/projects/prj-w/syncs"]
    assert lines[0]["error"] == "RuntimeError: SYNC_REFUSED: the baseline moved"


def test_a_validation_that_never_landed_is_retried_on_the_next_sweep():
    """Bug caught: a sync that took the contribution, then a failed validation, left for good:
    nothing reads pending any more, so the next sweep would never look again."""
    took = {"document": {"upstream_commit": "u1",
                         "contributions": [{"cycle_id": "cyc_1", "state": "integrated"}]}}  # fmt: skip
    api = _Api([_pending(state="integrated")], syncs=[took], baseline="b0")
    forge, calls = _forge(merged=True)

    lines, ok = sweep_mod.sweep(api, forge_get=forge, token=lambda: TOKEN)

    assert ok and calls == []
    assert [path for path, _ in api.posts] == ["/api/v1/projects/prj-w/validate"]
    assert lines[0]["revalidating_after"] == "u1"


def test_a_dry_run_reads_and_records_nothing():
    api = _Api([_pending()])
    forge, _ = _forge(merged=True)

    lines, ok = sweep_mod.sweep(api, forge_get=forge, token=lambda: TOKEN, dry_run=True)

    assert ok and api.posts == [] and lines[0]["dry_run"] is True


def test_every_forge_call_is_a_get():
    """The owner's condition. Bug caught: a forge call made with the host's full-scope token that
    writes (a comment, a merge, a label) where the sweep only needed to read."""
    seen = []

    def run(argv, **kw):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout='{"merged": true}', stderr="")

    assert sweep_mod._forge_get("repos/acme/widget/pulls/11", run=run) == {"merged": True}
    assert seen == [["gh", "api", "--method", "GET", "repos/acme/widget/pulls/11"]]
    source = _SCRIPT.read_text()
    assert source.count('"gh", "api"') == 1, "every forge call goes through _forge_get"


def test_the_sign_in_passes_the_password_in_the_environment_only(tmp_path, monkeypatch):
    """Bug caught: the admin password on the command line, where ps shows it to every user; the
    sweep's login overwriting the box's own CLI login; or a token issued by the wrong realm."""
    env = tmp_path / ".env"
    env.write_text(
        'SQUADOPS_ADMIN_PASSWORD="s3cret"\nSQUADOPS_REALM=squadops-local\nSQUADOPS_HOST=spark\n'
    )
    monkeypatch.setattr(sweep_mod, "SWEEP_CONFIG_HOME", tmp_path / "home")
    seen = {}

    def run(argv, **kw):
        seen.update(argv=argv, env=kw["env"])
        return subprocess.CompletedProcess(argv, 0, "", "")

    sweep_mod.sign_in(env, run=run)

    assert "s3cret" not in " ".join(seen["argv"])
    assert seen["argv"][1:] == ["login", "-u", "squadops-admin", "--keycloak-url",
                                "http://spark:8180", "--realm", "squadops-local"]  # fmt: skip
    assert seen["env"]["SQUADOPS_PASSWORD"] == "s3cret"
    assert seen["env"]["XDG_CONFIG_HOME"] == str(tmp_path / "home")
    with pytest.raises(RuntimeError, match="isn't in the deploy's .env"):
        sweep_mod.sign_in(tmp_path / "missing.env", run=run)
