"""The headless browser the release-package captures drive, in one place (#1793).

``capture_delivered_app.py`` and ``capture_prefect_run.py`` both photograph a page with headless
Chromium, and share two facts learned at the 1.9.0 cut and one at the 2.4.0 cut:

* **The browser is a setting.** The snap's confined ``chromium`` launcher (revision 3535,
  refreshed 2026-09-29) fails every navigation with ``ERR_ACCESS_DENIED``, while the snap's own
  binary (``/snap/chromium/current/usr/lib/chromium-browser/chrome``) loads the same pages.
  ``--browser`` points a capture at a working binary; 1.9.0's screenshots needed a ``PATH`` shim.
* **A page the browser could not load is the browser's own error page.** Chromium renders it with
  ``<body class="neterror">`` and its error code in ``loadTimeDataRaw``. Read as the app, it was
  reported as "a blank or error page" of the app's; read as Prefect, it would have been written
  as the release's timeline screenshot. ``browser_error`` names it, and the captures refuse it
  as the browser's failure.
* **A page the browser could not load may leave nothing but a line on its stderr** (#2713). At the
  2.4.0 cut the snap's Chromium (155.0.8059.84) answered every local page with
  ``Page load failed: net::ERR_ACCESS_DENIED`` on stderr: ``--dump-dom`` printed no error page and
  ``--screenshot`` wrote no file, and the capture blamed snap confinement three times before the
  browser's own error was read by hand. ``load_failure`` reads that line, and both calls refuse
  with it; confinement is named only when the browser reported no load failure.

**Every browser call is bounded in wall-clock time** (#2234). ``--virtual-time-budget`` bounds the
page's own clock, not the process: at the 2.2.1 cut the Prefect capture of a failed flow run ran
until an outer 600-second wrapper killed it, and wrote nothing. A browser that outlives its budget
by ``WALL_MARGIN_S`` is killed and named.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

DEFAULT_BROWSER = "chromium"
#: Seconds a browser may run past its virtual-time budget before it is killed. Pages here load in
#: about a second (a Prefect flow-run page took 1-3 s on 2026-10-12); the margin covers a cold start.
WALL_MARGIN_S = 60
_ERROR_CODE = re.compile(r'"errorCode":"(ERR_[A-Z0-9_]+)"')
#: The line Chromium's headless mode writes to stderr when the page itself did not load.
_LOAD_FAILED = re.compile(r"Page load failed: ((?:net::)?ERR_[A-Z0-9_]+)")


def add_browser_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--browser",
        default=DEFAULT_BROWSER,
        help="the headless Chromium to drive; when the snap launcher cannot load pages, its own "
        "binary: /snap/chromium/current/usr/lib/chromium-browser/chrome (#1793)",
    )


def browser_error(dom: str) -> str | None:
    """Chromium's network error code when ``dom`` is its own error page, else ``None``."""
    if 'class="neterror"' not in dom:
        return None
    found = _ERROR_CODE.search(dom)
    return found.group(1) if found else "an unnamed network error"


def load_failure(stderr: str) -> str | None:
    """The error Chromium names on ``stderr`` when the page did not load
    (``net::ERR_ACCESS_DENIED``), else ``None``."""
    found = _LOAD_FAILED.search(stderr or "")
    return found.group(1) if found else None


def _browsers_failure(browser: str, url: str, code: str) -> SystemExit:
    return SystemExit(
        f"{browser} could not load {url}: {code}. That is the browser's failure, not the app's: "
        "the page never loaded, so nothing was photographed or read from it. Check that "
        "something answers there, then the browser (--browser points the capture at another "
        "binary, #1793)"
    )


def _headless(browser: str, budget_ms: int, *flags: str) -> list[str]:
    return [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--virtual-time-budget={budget_ms}",
        *flags,
    ]


def _run(command: list[str], budget_ms: int, url: str) -> subprocess.CompletedProcess:
    """One browser call, killed when it outlives its budget by ``WALL_MARGIN_S``."""
    limit = budget_ms / 1000 + WALL_MARGIN_S
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"{command[0]} was still running on {url} after {limit:.0f} s, and was stopped. "
            "Nothing was written: check the page loads in a browser, and the browser binary "
            "(--browser, #1793)"
        ) from None


def loaded_dom(browser: str, url: str, budget_ms: int) -> str:
    """The DOM the page at ``url`` rendered. Refused when the browser could not load it: that
    page is the browser's, and nothing on it says anything about the page asked for."""
    done = _run(_headless(browser, budget_ms, "--dump-dom", url), budget_ms, url)
    code = browser_error(done.stdout)
    if code is not None:
        raise SystemExit(
            f"the browser could not load {url}: {code}. That is {browser}'s own error page, not "
            "the page: check the browser before reading this as the page's fault (--browser "
            "points the capture at another binary, #1793)"
        )
    failed = load_failure(done.stderr)
    if failed is not None:
        raise _browsers_failure(browser, url, failed)
    return done.stdout


def screenshot(
    browser: str, url: str, target: Path, width: int, height: int, budget_ms: int
) -> None:
    """Photograph the page at ``url`` into ``target``. Refused when no file is written: as the
    browser's failure when it says the page did not load, and otherwise as a browser that loaded
    the page and could not write ``target`` (a confined snap writes only where it may)."""
    done = _run(
        _headless(
            browser,
            budget_ms,
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={target}",
            url,
        ),
        budget_ms,
        url,
    )
    if target.exists() and target.stat().st_size > 0:
        return
    failed = load_failure(done.stderr)
    if failed is not None:
        raise _browsers_failure(browser, url, failed)
    raise SystemExit(
        f"{browser} reported no load failure for {url} and wrote no file at {target}: it "
        "could not write there. Is it snap-confined? (--browser points the capture at another "
        "binary, #1793)"
    )
