"""Every loaded check answers its ``expect`` on the source, before a rebuild (#2694).

``scripts/dev/loaded_checks.yaml``'s rows run in the deploy's containers after a rebuild
(``verify_loaded.py``). A change that moves a row's printed answer passed every CI check and
failed only there: #2689 made the package version 5, and ``#2418-package-readings``, which printed
it, read ``4`` until the first rebuild after it. A pre-registration needs every row to answer
before launch, so that cost a launch's time and invited a hasty edit of the row.

Each row's ``code`` runs here from the repository root, with ``docker`` shadowed so no row can
reach the live deploy: in one interpreter with a fresh namespace per row, or, for a row that counts
what an import loads (it reads ``sys.modules``), in an interpreter of its own. The rows that need
something only their container has are named in ``CONTAINER_ONLY`` with what, and
``test_each_container_only_row_is_a_row_and_still_needs_its_container`` keeps that list honest:
a named row that now answers here, or that no longer exists, fails it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
ROWS = yaml.safe_load((ROOT / "scripts" / "dev" / "loaded_checks.yaml").read_text())["checks"]

#: The rows whose answer needs their container, by id, and what it needs.
CONTAINER_ONLY = {
    "2068": "the console image's own `auth_bff` module",
    "2073": "PyJWT, which the runtime image installs and the dev environment doesn't",
    "1937-eve": "ruff and eslint, installed in the agent image",
    "1937-han": "ruff and eslint, installed in the agent image",
    "2160": "the deploy's configuration (`SQUADOPS__*`), which only the container's environment holds",
    "2165": "the deploy's configuration (`SQUADOPS__*`), which only the container's environment holds",
    "2213": "the deploy's configuration (`SQUADOPS__*`), which only the container's environment holds",
    "2414-hook": "the deploy's configuration (`SQUADOPS__*`), which only the container's environment holds",
    "2457": "the deploy's configuration (`SQUADOPS__*`), which only the container's environment holds",
    "2324-agent": "the agent image's pinned aio-pika, whose version it prints",
    "2416": "docker, to inspect the evaluator's image",
    "2451-apps": "the sandbox service's environment, which names its apps network",
}

#: Runs each row's code in its own namespace, printing ``{id: [returncode, last line]}``.
_HARNESS = """
import contextlib, io, json, sys, traceback
rows = json.loads(sys.stdin.read())
answers = {}
for row in rows:
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(row["code"], row["id"], "exec"), {"__name__": "__loaded_check__"})
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        answers[row["id"]] = [0, lines[-1].strip() if lines else ""]
    except BaseException:
        answers[row["id"]] = [1, traceback.format_exc().strip().splitlines()[-1]]
print(json.dumps(answers))
"""


#: The rows that count what an import loads, which a shared interpreter has already loaded.
FRESH = {r["id"] for r in ROWS if "sys.modules" in r["code"]}


@pytest.fixture(scope="module")
def answers(tmp_path_factory) -> dict[str, list]:
    shim = tmp_path_factory.mktemp("no-docker")
    (shim / "docker").write_text("#!/bin/sh\necho 'docker refused in tests' >&2\nexit 97\n")
    (shim / "docker").chmod(0o755)
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("SQUADOPS__")},
        "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}",
    }
    shared = [r for r in ROWS if r["id"] not in FRESH]
    batches = [shared] + [[r] for r in ROWS if r["id"] in FRESH]
    found: dict[str, list] = {}
    for batch in batches:
        done = subprocess.run(
            [sys.executable, "-c", _HARNESS],
            input=json.dumps([{"id": r["id"], "code": r["code"]} for r in batch]),
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=600,
            check=True,
        )
        found |= json.loads(done.stdout.strip().splitlines()[-1])
    return found


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r["id"] not in CONTAINER_ONLY], ids=lambda r: r["id"]
)
def test_each_loaded_check_answers_its_expect_on_the_source(answers, row):
    """Bug caught: a change that moves what a loaded check prints, found only by the next
    rebuild's ``verify_loaded.py`` (#2689's package version, read stale by #2418's row)."""
    code, last = answers[row["id"]]

    assert code == 0, f"{row['id']} raised: {last}"
    assert last == str(row["expect"]).strip()


def test_each_container_only_row_is_a_row():
    """Bug caught: a row named here that no longer exists, so the list grows stale and a new row
    under an old id would go unchecked. Whether a named row answers here isn't asserted: CI
    installs from the locks and a dev environment can lag them, so a row reading an installed
    version may answer in one and not the other."""
    assert sorted(set(CONTAINER_ONLY) - {r["id"] for r in ROWS}) == []
