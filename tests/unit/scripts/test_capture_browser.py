"""The release-package captures tell the browser's own error page from the page (#1793).

What bug would these catch? The 1.9.0 cut's: a snap Chromium that loaded nothing, whose error
page the delivered-app capture reported as the app rendering blank. The Prefect capture checked
only that a file was written, so it would have put the same error page on the release as the
flow-run timeline. ``_ERROR_PAGE`` is trimmed from the page that browser returned on 2026-10-03
(revision 3535, ``http://127.0.0.1:4200/``): the body tag and the start of ``loadTimeDataRaw``,
verbatim. And the 2.4.0 cut's (#2713): a browser that loaded nothing and said so only on stderr,
whose missing screenshot the capture blamed on snap confinement.
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


def test_a_browser_that_outlives_its_budget_is_stopped_and_named(tmp_path, monkeypatch):
    """#2234. The bug: ``--virtual-time-budget`` bounds the page's clock, not the process, so the
    2.2.1 cut's Prefect capture ran until an outer 600-second wrapper killed it, and said nothing."""
    stuck = tmp_path / "chrome"
    stuck.write_text("#!/bin/sh\nsleep 30\n")
    stuck.chmod(0o755)
    monkeypatch.setattr(browser, "WALL_MARGIN_S", 1)

    with pytest.raises(SystemExit, match=r"still running on http://x/ after 1 s, and was stopped"):
        browser.loaded_dom(str(stuck), "http://x/", 0)


# #2713. What the 2.4.0 cut's snap Chromium (155.0.8059.84) did with every local page: no error
# page on stdout, no file, and the cause one line among the usual noise on stderr. The bus line is
# noise every headless run prints; the console line is a page that DID load reporting a missing
# favicon, which names a net:: error too.
_NOISE = (
    "[2513:2513:1023/224412.481920:ERROR:dbus/bus.cc(408)] Failed to connect to the bus: "
    "Could not parse server address: Unknown address type"
)
_LOAD_FAILED = (
    "[2513:2513:1023/224412.517033:ERROR:headless/lib/browser/headless_command_handler.cc(213)] "
    "Page load failed: net::ERR_ACCESS_DENIED"
)
_SUBRESOURCE = (
    '[2513:2513:1023/224412.517090:INFO:CONSOLE(0)] "Failed to load resource: '
    'net::ERR_FILE_NOT_FOUND", source: http://localhost:5199/favicon.ico (0)'
)


def _chromium_that_writes_nothing(tmp_path: Path, *stderr: str) -> tuple[Path, Path]:
    """A browser executable that prints ``stderr``, writes no file, exits 0, and logs each call."""
    said = tmp_path / "stderr.txt"
    said.write_text("".join(f"{line}\n" for line in stderr))
    calls = tmp_path / "calls.txt"
    exe = tmp_path / "chrome"
    exe.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\ncat "{said}" >&2\nexit 0\n')
    exe.chmod(0o755)
    return exe, calls


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        ((_NOISE, _LOAD_FAILED), "net::ERR_ACCESS_DENIED"),
        ((_NOISE, _SUBRESOURCE), None),
        ((), None),
    ],
    ids=["the page did not load", "a page that loaded, missing a favicon", "silent"],
)
def test_only_the_pages_own_load_failure_is_read_off_stderr(stderr, code):
    assert browser.load_failure("\n".join(stderr)) == code


def test_the_delivered_app_capture_names_the_browsers_load_failure_not_confinement(
    tmp_path, monkeypatch
):
    """The bug: ``wrote no file for /runs — is it snap-confined?``, a guess that sent the 2.4.0
    cut after the snap three times. Entered at ``shoot``: the screenshot is the first call."""
    monkeypatch.setattr(delivered.Path, "home", lambda: tmp_path)
    exe, _ = _chromium_that_writes_nothing(tmp_path, _NOISE, _LOAD_FAILED)
    assets = tmp_path / "assets"

    with pytest.raises(SystemExit) as refused:
        delivered.shoot(str(exe), 5199, [("/runs", "run-list")], assets, 1180, {"/runs": ["x"]})

    said = str(refused.value)
    assert f"{exe} could not load http://localhost:5199/runs: net::ERR_ACCESS_DENIED" in said
    assert "the browser's failure, not the app's" in said
    assert "snap" not in said
    assert not assets.exists()


def test_the_prefect_capture_refuses_a_load_failure_only_its_stderr_names(tmp_path, monkeypatch):
    """The bug: ``--dump-dom`` printed no error page, so ``loaded_dom`` passed the page and the
    screenshot was refused as ``snap confinement, or Prefect is down``. Refused at the first
    call now, so no screenshot is attempted."""
    monkeypatch.setattr(prefect.Path, "home", lambda: tmp_path)
    exe, calls = _chromium_that_writes_nothing(tmp_path, _NOISE, _LOAD_FAILED)
    dest = tmp_path / "assets" / "prefect-flow-run.png"

    with pytest.raises(SystemExit) as refused:
        prefect.shoot(str(exe), "f1d2", dest, 1600, 520)

    said = str(refused.value)
    assert "could not load http://localhost:4200/flow-runs/flow-run/f1d2: net::" in said
    assert ("snap" in said, dest.exists()) == (False, False)
    assert ["--dump-dom" in call for call in calls.read_text().splitlines()] == [True]


def test_confinement_is_named_only_when_the_browser_reported_no_load_failure(tmp_path, monkeypatch):
    """Edge: the page loaded (only a favicon was missing) and still no file was written. That is
    the browser unable to write, and must not be reported as the page failing to load."""
    monkeypatch.setattr(delivered.Path, "home", lambda: tmp_path)
    exe, _ = _chromium_that_writes_nothing(tmp_path, _NOISE, _SUBRESOURCE)
    staged = tmp_path / "squadops-capture-staging" / "run-list.png"

    with pytest.raises(SystemExit) as refused:
        delivered.shoot(str(exe), 5199, [("/runs", "run-list")], tmp_path / "a", 1180, {})

    assert str(refused.value) == (
        f"{exe} reported no load failure for http://localhost:5199/runs and wrote no file at "
        f"{staged}: it could not write there. Is it snap-confined? (--browser points the "
        "capture at another binary, #1793)"
    )


def _prefect_main(monkeypatch, tmp_path, state: str) -> list[str]:
    run = {"id": "f1d2", "name": "group_run/cyc_78515574/run_41a819d3", "state": {"type": state}}
    shot: list[str] = []

    def _shoot(browser_, flow_run_id, dest, width, height):
        shot.append(flow_run_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"png")

    monkeypatch.setattr(prefect, "api", lambda path, body=None: run if "flow_runs/" in path else [])
    monkeypatch.setattr(prefect, "shoot", _shoot)
    monkeypatch.setattr(prefect, "REPO", tmp_path)
    monkeypatch.setattr(prefect, "RELEASES", tmp_path / "releases")
    monkeypatch.setattr(
        sys, "argv", ["capture", "--flow-run", "f1d2", "--version", "2.3.0", "--browser", "b"]
    )
    prefect.main()
    return shot


@pytest.mark.parametrize("state", ["FAILED", "CRASHED", "CANCELLED", "COMPLETED"])
def test_a_finished_flow_run_is_photographed_as_it_ended(monkeypatch, tmp_path, state):
    """#2234: a refused proposal run's timeline is evidence. Entered at ``main``."""
    assert _prefect_main(monkeypatch, tmp_path, state) == ["f1d2"]


@pytest.mark.parametrize("state", ["RUNNING", "PENDING", "SCHEDULED", "PAUSED", "CANCELLING"])
def test_a_flow_run_that_is_still_going_is_refused_whatever_its_state(monkeypatch, tmp_path, state):
    """The bug: only RUNNING was refused, so a pending or paused run's half-drawn timeline could
    be written as the finished article."""
    with pytest.raises(SystemExit, match=f"REFUSING: the run is {state}"):
        _prefect_main(monkeypatch, tmp_path, state)
