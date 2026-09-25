"""Attaching a line's records to its public Release (1.8.2 plan §3.2 item 16, decision 7).

What bug would these catch? The two ways this goes wrong for good: a secret leaves the box
inside a tarball on a public Release, which cannot be taken back, or the package records an
asset the Release does not carry. And a quieter one: the line's records gathered by a prefix
that also takes the next line's (``1-8-1`` matching ``1-8-10``).
"""

from __future__ import annotations

import hashlib
import importlib.util
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

    monkeypatch.setattr(attach.subprocess, "run", fake_run)

    assert _run(box, tmp_path, "--upload") == 0

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
    monkeypatch.setattr(
        attach.subprocess,
        "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="release not found"),
    )

    assert _run(box, tmp_path, "--upload") == 1
    assert package.read_text() == before


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
