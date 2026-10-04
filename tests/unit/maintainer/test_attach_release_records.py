"""Attaching a line's records to its public Release (1.8.2 plan §3.2 item 16, decision 7).

What bug would these catch? The two ways this goes wrong for good: a secret leaves the box
inside a tarball on a public Release, which cannot be taken back, or the package records an
asset the Release does not carry. And a quieter one: the line's records gathered by a prefix
that also takes the next line's (``1-8-1`` matching ``1-8-10``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "maintainer" / "attach_release_records.py"
)
_spec = importlib.util.spec_from_file_location("attach_release_records", _SCRIPT)
attach = importlib.util.module_from_spec(_spec)
sys.modules["attach_release_records"] = attach
_spec.loader.exec_module(attach)

_DB_PASSWORD = "s3cret-db-pass"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A main checkout with one line's records, its neighbours' records, a secrets dir, an
    .env and a captured package."""
    main = tmp_path / "squad-ops"
    sets = main / "var" / "verification_sets"
    _write(sets / "1-8-1-fastapi-react" / "roll-01.json", '{"verdict": "accepted"}\n')
    _write(sets / "1-8-1-diagnostics" / "redelivery" / "shakeout.md", "# shakeout\n")
    _write(sets / "1-8-10-fastapi-react" / "roll-01.json", "{}\n")
    _write(sets / "1-8-0-nextjs" / "roll-01.json", "{}\n")
    _write(main / "secrets" / "db_password.txt", _DB_PASSWORD + "\n")
    _write(main / "secrets" / "pin.txt", "1234\n")
    _write(main / ".env", "SQUADOPS__LLM__MODEL=qwen3.8:27b\nLANGFUSE_SECRET_KEY=lf-secret-value\n")
    _write(
        main / "site" / "content" / "releases" / "v1.8.1" / "package.yaml",
        yaml.safe_dump({"version": "1.8.1", "tag": "v1.8.1", "cycles": [{"id": "cyc_1"}]}),
    )
    monkeypatch.setattr(attach, "main_checkout", lambda _p: main)
    return main


def _run(box, tmp_path, *args, deploy=()):
    return attach.main(["1.8.1", "--out-dir", str(tmp_path), *args], deploy_pairs=list(deploy))


def _approved(box, tmp_path, monkeypatch) -> str:
    """The preview's checksum, as the operator reads it before approving the upload."""
    with monkeypatch.context() as m:
        m.setattr(attach.subprocess, "run", lambda *a, **k: pytest.fail("preview acted"))
        assert _run(box, tmp_path) == 0
    return hashlib.sha256((tmp_path / "squadops-1.8.1-records.tar.gz").read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        (f"login failed for postgres:{_DB_PASSWORD}@db", "the value of secrets/db_password.txt"),
        ("key lf-secret-value in a header", "the value of .env LANGFUSE_SECRET_KEY"),
        ("token eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.c2lnbmF0dXJlLXZhbHVl", "jwt"),
        ("public pk-lf-1234abcd-5678", "langfuse key"),
        ("export KEY=sk-proj-abcdefghijklmnopqrstuvwx", "api key (sk-)"),
        (
            "from the deploy: deploy-only-secret-9",
            "the value of deploy env SQUADOPS__AUTH__CLIENT_SECRET",
        ),
    ],
)
def test_a_credential_in_any_record_refuses_the_upload(
    box, tmp_path, monkeypatch, capsys, line, kind
):
    """Entered at ``main`` as the operator runs it, with ``--upload``. Bug this catches: a
    record carrying a secret uploaded to a public Release. The value is never printed."""
    _write(box / "var/verification_sets/1-8-1-diagnostics/redelivery/driver.log", f"a\n{line}\n")
    monkeypatch.setattr(
        attach.subprocess, "run", lambda *a, **k: pytest.fail("uploaded despite a hit")
    )

    rc = _run(
        box,
        tmp_path,
        "--upload",
        "--expect-sha256",
        "any",
        deploy=[("SQUADOPS__AUTH__CLIENT_SECRET", "deploy-only-secret-9")],
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert f"var/verification_sets/1-8-1-diagnostics/redelivery/driver.log:2  {kind}" in out
    assert _DB_PASSWORD not in out and "deploy-only-secret-9" not in out


def test_a_clean_line_is_uploaded_and_recorded_in_its_package(box, tmp_path, monkeypatch):
    """Bug this catches: the package naming a sha256 that is not the uploaded file's, or the
    rest of the captured package disturbed by the write. Only the line's own records go in."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    approved = _approved(box, tmp_path, monkeypatch)
    monkeypatch.setattr(attach.subprocess, "run", fake_run)

    assert _run(box, tmp_path, "--upload", "--expect-sha256", approved) == 0

    tarball = tmp_path / "squadops-1.8.1-records.tar.gz"
    assert calls == [["gh", "release", "upload", "v1.8.1", str(tarball)]]
    package = yaml.safe_load((box / "site/content/releases/v1.8.1/package.yaml").read_text())
    assert package["cycles"] == [{"id": "cyc_1"}]
    assert package["records"]["sha256"] == hashlib.sha256(tarball.read_bytes()).hexdigest()
    assert package["records"]["files"] == 2
    import tarfile

    with tarfile.open(tarball) as tar:
        assert sorted(tar.getnames()) == [
            "squadops-1.8.1-records/var/verification_sets/1-8-1-diagnostics/redelivery/shakeout.md",
            "squadops-1.8.1-records/var/verification_sets/1-8-1-fastapi-react/roll-01.json",
        ]


def test_a_failed_upload_leaves_the_package_untouched(box, tmp_path, monkeypatch):
    """Bug this catches: a package that names an asset the Release never received."""
    package = box / "site/content/releases/v1.8.1/package.yaml"
    before = package.read_text()
    approved = _approved(box, tmp_path, monkeypatch)
    monkeypatch.setattr(
        attach.subprocess,
        "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="release not found"),
    )

    assert _run(box, tmp_path, "--upload", "--expect-sha256", approved) == 1
    assert package.read_text() == before


def test_two_builds_of_the_same_records_are_the_same_bytes(box, tmp_path, monkeypatch):
    """#1732 (the 1.8.2 cut: approved 9edda486…, uploaded 791ad261…, every member identical).
    Bug this catches: the gzip header stamping the build time, so the preview the owner approved
    and the upload's rebuild are never the same file. The clock moves between the builds."""
    import gzip

    members = attach.collect_records(box, "1-8-1", None)
    first = attach.build_tarball(members, tmp_path / "a.tar.gz", "top")
    monkeypatch.setattr(gzip.time, "time", lambda: 2_000_000_000.0)
    second = attach.build_tarball(members, tmp_path / "b.tar.gz", "top")

    assert first == second
    assert (tmp_path / "a.tar.gz").read_bytes() == (tmp_path / "b.tar.gz").read_bytes()


def test_an_upload_whose_rebuild_differs_from_the_approved_preview_uploads_nothing(
    box, tmp_path, monkeypatch, capsys
):
    """Bug this catches: records changed between the owner's approval and the upload, and the
    changed tarball published anyway — the approval was of other bytes."""
    package = box / "site/content/releases/v1.8.1/package.yaml"
    before = package.read_text()
    approved = _approved(box, tmp_path, monkeypatch)
    _write(box / "var/verification_sets/1-8-1-fastapi-react/roll-02.json", "{}\n")
    monkeypatch.setattr(
        attach.subprocess, "run", lambda *a, **k: pytest.fail("uploaded a different tarball")
    )

    assert _run(box, tmp_path, "--upload", "--expect-sha256", approved) == 1

    assert f"not the approved {approved}" in capsys.readouterr().out
    assert package.read_text() == before


def test_an_upload_without_the_approved_checksum_is_refused(box, tmp_path, monkeypatch, capsys):
    """Require, don't default: an upload that names no approved checksum has nothing to be
    checked against, so it is the pre-#1732 shape by another route."""
    monkeypatch.setattr(attach.subprocess, "run", lambda *a, **k: pytest.fail("uploaded"))

    with pytest.raises(SystemExit) as exit_:
        _run(box, tmp_path, "--upload")

    assert exit_.value.code == 2
    assert "--upload requires --expect-sha256" in capsys.readouterr().err


def test_the_preview_uploads_nothing_and_names_a_secret_too_short_to_scan(
    box, tmp_path, monkeypatch, capsys
):
    """Bug this catches: a preview that acts, or a short secret silently left out of the scan."""
    monkeypatch.setattr(attach.subprocess, "run", lambda *a, **k: pytest.fail("preview acted"))

    assert _run(box, tmp_path) == 0

    out = capsys.readouterr().out
    assert "unscanned (shorter than 6 chars): secrets/pin.txt" in out
    assert "clean: no credential found" in out


def test_env_values_are_scanned_only_for_secret_names_and_never_for_references():
    """Bug this catches: every .env value scanned (a model name or a URL buries a real hit in
    false ones), or a ``secret://`` reference scanned as if it were the secret."""
    pairs = [
        ("SQUADOPS__LLM__MODEL", "qwen3.8:27b"),
        ("SQUADOPS__AUTH__CLIENT_SECRET", "secret://agent_client_secret"),
        ("POSTGRES_PASSWORD", "hunter22"),
        ("SQUADOPS__LANGFUSE__PUBLIC_KEY", "pk-lf-abc"),
    ]
    assert [s.source for s in attach._env_secrets(pairs, "env")] == [
        "env POSTGRES_PASSWORD",
        "env SQUADOPS__LANGFUSE__PUBLIC_KEY",
    ]


def test_a_line_with_no_records_attaches_nothing(tmp_path, monkeypatch):
    main = tmp_path / "empty"
    (main / "var" / "verification_sets").mkdir(parents=True)
    monkeypatch.setattr(attach, "main_checkout", lambda _p: main)
    assert attach.main(["1.8.1", "--out-dir", str(tmp_path)], deploy_pairs=[]) == 1


def test_a_version_that_is_not_semver_is_refused():
    with pytest.raises(SystemExit, match="MAJOR.MINOR.PATCH"):
        attach.line_of("1.8")


# --- #1941 item 6: the line's campaigns' outputs ride the same tarball and the same scan ---

_SINCE = "2026-10-01T19:05:17-04:00"  # the previous tag's commit
_UNTIL = "2026-10-06T12:00:00-04:00"  # this tag's commit


@pytest.fixture
def campaigns(box, monkeypatch):
    """Provenance naming the line's campaign, one before the window and one after it, one the
    line names with nothing on this box; and an operator's campaign that no provenance names."""
    from datetime import datetime

    def entry(cid, created):
        return {"campaign_id": cid, "created": created, "definitions": []}

    _write(
        box / "examples/03_group_run/campaigns/provenance.yaml",
        yaml.safe_dump(
            {
                "campaigns": [
                    entry("cmp_line", "2026-10-04T08:58:32.439865+00:00"),
                    entry("cmp_prior", "2026-09-30T10:00:00+00:00"),
                    entry("cmp_next", "2026-10-07T10:00:00+00:00"),
                    entry("cmp_gone", "2026-10-03T10:00:00+00:00"),
                ]
            }
        ),
    )
    runs = box / "var" / "campaigns"
    _write(runs / "cmp_line" / "logs" / "cyc_1" / "runtime-api.log", "a window\n")
    _write(runs / "cmp_line" / "proofs" / "1802-live-lease-proof.log", "5 of 5\n")
    _write(runs / "cmp_line.archive.log", "cyc_1: 10 bytes\n")
    _write(runs / "cmp_prior" / "logs" / "x.log", "an earlier line's\n")
    _write(runs / "cmp_next" / "logs" / "x.log", "a later line's\n")
    _write(runs / "cmp_operator" / "logs" / "y.log", "an operator's own\n")
    window = (datetime.fromisoformat(_SINCE), datetime.fromisoformat(_UNTIL))
    monkeypatch.setattr(attach, "tag_window", lambda _main, _tag: window)
    return box


def test_the_lines_campaigns_are_carried_and_every_other_is_left_and_named(
    campaigns, tmp_path, monkeypatch, capsys
):
    """Entered at ``main``, preview then upload. Bugs this catches: the 2.0 set's evidence left
    on one box (the tarball took only ``var/verification_sets/``); another line's campaign
    carried; an operator's campaign published because it sits in the same directory; and a
    campaign the line names silently missing."""
    approved = _approved(campaigns, tmp_path, monkeypatch)
    out = capsys.readouterr().out
    monkeypatch.setattr(
        attach.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "", "")
    )

    assert _run(campaigns, tmp_path, "--upload", "--expect-sha256", approved) == 0

    import tarfile

    with tarfile.open(tmp_path / "squadops-1.8.1-records.tar.gz") as tar:
        names = sorted(n.removeprefix("squadops-1.8.1-records/") for n in tar.getnames())
    assert [n for n in names if n.startswith("var/campaigns/")] == [
        "var/campaigns/cmp_line.archive.log",
        "var/campaigns/cmp_line/logs/cyc_1/runtime-api.log",
        "var/campaigns/cmp_line/proofs/1802-live-lease-proof.log",
    ]
    package = yaml.safe_load((campaigns / "site/content/releases/v1.8.1/package.yaml").read_text())
    assert package["records"]["campaigns"] == ["cmp_line"]
    assert package["records"]["files"] == 5
    assert "campaigns carried: 1 (cmp_line)" in out
    assert "no outputs on this box: cmp_gone" in out
    assert "not carried, named by no provenance.yaml: cmp_operator" in out


def test_a_credential_in_a_campaigns_log_refuses_the_upload(
    campaigns, tmp_path, monkeypatch, capsys
):
    """Bug this catches: the campaigns' log windows (container logs, the likeliest place for a
    token) added to a public tarball outside the scan."""
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.c2lnbmF0dXJlLXZhbHVl"
    _write(campaigns / "var/campaigns/cmp_line/logs/cyc_1/runtime-api.log", f"ok\nBearer {jwt}\n")
    monkeypatch.setattr(attach.subprocess, "run", lambda *a, **k: pytest.fail("uploaded"))

    assert _run(campaigns, tmp_path, "--upload", "--expect-sha256", "any") == 1

    out = capsys.readouterr().out
    assert "var/campaigns/cmp_line/logs/cyc_1/runtime-api.log:2  jwt" in out
    assert jwt not in out


def test_the_lines_window_runs_from_the_previous_tag_by_version_order(tmp_path):
    """Read from real tags. Bugs this catches: the previous tag taken by string order (v1.10.0
    after v1.9.0 is the version that follows; lexically it sorts before), or a records attach
    before the tag that names the window's end."""
    from datetime import datetime

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args, date=None):
        env = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date} if date else {}
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
            check=True,
            capture_output=True,
            env={**os.environ, **env},
        )

    git("init", "-q")
    for version, date in [
        ("v1.9.0", "2026-09-01T10:00:00+00:00"),
        ("v1.10.0", "2026-09-20T10:00:00+00:00"),
    ]:
        git("commit", "-q", "--allow-empty", "-m", version, date=date)
        git("tag", version)

    since, until = attach.tag_window(repo, "v1.10.0")

    assert (since, until) == (
        datetime.fromisoformat("2026-09-01T10:00:00+00:00"),
        datetime.fromisoformat("2026-09-20T10:00:00+00:00"),
    )
    assert attach.tag_window(repo, "v1.9.0")[0] is None
    with pytest.raises(SystemExit, match="tag v2.0.0 not found"):
        attach.tag_window(repo, "v2.0.0")
