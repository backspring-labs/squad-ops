"""The release-package captures tell the browser's own error page from the page (#1793).

What bug would these catch? The 1.9.0 cut's: a snap Chromium that loaded nothing, whose error
page the delivered-app capture reported as the app rendering blank. The Prefect capture checked
only that a file was written, so it would have put the same error page on the release as the
flow-run timeline. ``_ERROR_PAGE`` is trimmed from the page that browser returned on 2026-10-03
(revision 3535, ``http://127.0.0.1:4200/``): the body tag and the start of ``loadTimeDataRaw``,
verbatim.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, DEV / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


browser = _load("capture_browser")
delivered = _load("capture_delivered_app")
prefect = _load("capture_prefect_run")

_ERROR_PAGE = (
    '<html dir="ltr" lang="en"><head><title>127.0.0.1</title></head>'
    '<body class="neterror" style="font-family: &quot;sans&quot;, Arial, sans-serif; '
    'font-size: 75%"><div id="main-frame-error" class="interstitial-wrapper"></div>'
    '<script>var loadTimeDataRaw = {"details":"Details","errorCode":"ERR_ACCESS_DENIED",'
    '"fontfamily":"\\"sans\\", Arial, sans-serif"};</script></body></html>'
)


@pytest.mark.parametrize(
    ("dom", "error"),
    [
        (_ERROR_PAGE, "ERR_ACCESS_DENIED"),
        (_ERROR_PAGE.replace(',"errorCode":"ERR_ACCESS_DENIED"', ""), "an unnamed network error"),
        ('<body><div data-testid="runs-view"></div></body>', None),
        # An app whose own content quotes a Chromium code is still the app.
        ('<body><pre>{"errorCode":"ERR_ACCESS_DENIED"}</pre></body>', None),
        ("", None),
    ],
    ids=[
        "the snap's error page",
        "an error page without a code",
        "an app page",
        "an app quoting a code",
        "empty",
    ],
)
def test_the_browsers_own_error_page_is_named_and_nothing_else_is(dom, error):
    assert browser.browser_error(dom) == error


def _fake_browser(dom: str, shots: list[str]):
    def run(cmd, **kwargs):
        if "--dump-dom" in cmd:
            return subprocess.CompletedProcess(cmd, 0, dom, "")
        target = next(a for a in cmd if a.startswith("--screenshot=")).split("=", 1)[1]
        shots.append(cmd[0])
        Path(target).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return run


def test_the_delivered_app_capture_blames_the_browser_not_the_app(tmp_path, monkeypatch):
    """Entered at ``shoot``, the capture's own caller: the refusal names the browser and its
    code, where it used to read "rendered none of its view's test ids", and nothing is written."""
    monkeypatch.setattr(delivered.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(subprocess, "run", _fake_browser(_ERROR_PAGE, []))
    assets = tmp_path / "assets"

    with pytest.raises(SystemExit) as refused:
        delivered.shoot(
            "/opt/chrome", 5199, [("/runs", "run-list")], assets, 1180, {"/runs": ["runs-view"]}
        )

    assert "could not load http://localhost:5199/runs: ERR_ACCESS_DENIED" in str(refused.value)
    assert "/opt/chrome's own error page" in str(refused.value)
    assert not assets.exists()


def test_the_prefect_capture_refuses_an_error_page_before_photographing_it(tmp_path, monkeypatch):
    """The bug: a file was the only check, so the browser's error page became the release's
    timeline screenshot."""
    monkeypatch.setattr(prefect.Path, "home", lambda: tmp_path)
    shots: list[str] = []
    monkeypatch.setattr(subprocess, "run", _fake_browser(_ERROR_PAGE, shots))
    dest = tmp_path / "assets" / "prefect-flow-run.png"

    with pytest.raises(SystemExit, match="ERR_ACCESS_DENIED"):
        prefect.shoot("chromium", "f1d2", dest, 1600, 520)

    assert (shots, dest.exists()) == ([], False)


def test_the_prefect_capture_drives_the_browser_it_is_given(tmp_path, monkeypatch):
    """The setting reaches the screenshot: 1.9.0 needed a PATH shim to get past the snap."""
    monkeypatch.setattr(prefect.Path, "home", lambda: tmp_path)
    shots: list[str] = []
    monkeypatch.setattr(subprocess, "run", _fake_browser("<body><main></main></body>", shots))
    dest = tmp_path / "assets" / "prefect-flow-run.png"

    prefect.shoot("/snap/chromium/current/usr/lib/chromium-browser/chrome", "f1d2", dest, 1600, 520)

    assert shots == ["/snap/chromium/current/usr/lib/chromium-browser/chrome"]
    assert dest.read_bytes() == b"png"
