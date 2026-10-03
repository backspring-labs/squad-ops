"""The headless browser the release-package captures drive, in one place (#1793).

``capture_delivered_app.py`` and ``capture_prefect_run.py`` both photograph a page with headless
Chromium, and share two facts learned at the 1.9.0 cut:

* **The browser is a setting.** The snap's confined ``chromium`` launcher (revision 3535,
  refreshed 2026-09-29) fails every navigation with ``ERR_ACCESS_DENIED``, while the snap's own
  binary (``/snap/chromium/current/usr/lib/chromium-browser/chrome``) loads the same pages.
  ``--browser`` points a capture at a working binary; 1.9.0's screenshots needed a ``PATH`` shim.
* **A page the browser could not load is the browser's own error page.** Chromium renders it with
  ``<body class="neterror">`` and its error code in ``loadTimeDataRaw``. Read as the app, it was
  reported as "a blank or error page" of the app's; read as Prefect, it would have been written
  as the release's timeline screenshot. ``browser_error`` names it, and the captures refuse it
  as the browser's failure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

DEFAULT_BROWSER = "chromium"
_ERROR_CODE = re.compile(r'"errorCode":"(ERR_[A-Z0-9_]+)"')


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


def _headless(browser: str, budget_ms: int, *flags: str) -> list[str]:
    return [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--virtual-time-budget={budget_ms}",
        *flags,
    ]


def loaded_dom(browser: str, url: str, budget_ms: int) -> str:
    """The DOM the page at ``url`` rendered. Refused when the browser could not load it: that
    page is the browser's, and nothing on it says anything about the page asked for."""
    dom = subprocess.run(
        _headless(browser, budget_ms, "--dump-dom", url), capture_output=True, text=True
    ).stdout
    code = browser_error(dom)
    if code is not None:
        raise SystemExit(
            f"the browser could not load {url}: {code}. That is {browser}'s own error page, not "
            "the page: check the browser before reading this as the page's fault (--browser "
            "points the capture at another binary, #1793)"
        )
    return dom


def screenshot(
    browser: str, url: str, target: Path, width: int, height: int, budget_ms: int
) -> None:
    subprocess.run(
        _headless(
            browser,
            budget_ms,
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={target}",
            url,
        ),
        capture_output=True,
        text=True,
    )
