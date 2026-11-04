"""#2903: every console plugin that wrote through the Continuum command bus posted
``{command_id, params}``. The pinned shell reads the body as ``{command_id, args, dry_run,
confirmed}`` and drops the rest (Continuum v1.0.2, ``adapters/web/api.py:78-84``), so each handler
got ``{}``, raised, and the bus's 200 ``status: failed`` passed as success because only ``resp.ok``
was read. #2904: no plugin sent ``confirmed``, so a confirm-level command's ``pending`` answer
passed as success too. The body is built in one place now, ``shared/commands.js``'s
``executeCommand``, which reads the answer's ``status``; a plugin that posts to the route itself,
or names a ``params`` key for a body, is the regression.

Grep-shaped, as ``test_paged_lists.py`` is: the scan reads the plugin sources, not a build. What
the helper sends and how it reads the answer is ``shared/commands.test.js`` (node's own runner).
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGINS = Path(__file__).resolve().parents[3] / "console" / "continuum-plugins"
_HELPER = _PLUGINS / "shared" / "commands.js"

#: The command route named anywhere: the helper owns it.
_ROUTE = re.compile(r"commands/execute")

#: A ``params`` key in an object literal (``params: ...``) or its shorthand (``{ ..., params }``),
#: not a variable (``const params =``), a call (``params.set``) or a template (``${params}``).
_PARAMS_KEY = re.compile(r"\bparams\s*:|(?<![$])[{,]\s*params\s*[,}]")


def _sources(root: Path):
    for path in sorted(root.glob("**/*")):
        if path.suffix in (".svelte", ".js") and "node_modules" not in path.parts:
            yield path


def _lines(root: Path, pattern: re.Pattern[str], *, skip: Path | None = None) -> list[str]:
    return [
        f"{path.relative_to(root)}:{source[: m.start()].count(chr(10)) + 1}"
        for path in _sources(root)
        if path != skip
        for source in [path.read_text(encoding="utf-8")]
        for m in pattern.finditer(source)
    ]


def test_only_the_shared_helper_posts_to_the_command_route():
    assert _lines(_PLUGINS, _ROUTE, skip=_HELPER) == []
    assert _ROUTE.search(_HELPER.read_text(encoding="utf-8")), "the helper names the route"


def test_no_plugin_source_names_a_params_key():
    assert _lines(_PLUGINS, _PARAMS_KEY) == []


def test_the_scan_finds_each_old_form_and_not_the_others(tmp_path):
    src = tmp_path / "squadops.x" / "ui" / "src"
    src.mkdir(parents=True)
    (src / "View.svelte").write_text(
        # The three plugins' old bodies (#2903), each a different spelling:
        "const resp = await apiFetch(`${apiBase}/api/commands/execute`, {\n"
        "  body: JSON.stringify({ command_id: commandId, params }),\n"
        "});\n"
        "await apiFetch('/api/commands/execute', { body: JSON.stringify({\n"
        "  command_id: 'squadops.set_active_profile',\n"
        "  params: { profile_id: profileId },\n"
        "}) });\n"
        # Not bodies: a query-string variable, its template, a call, a CSS class, a parameter.
        "const params = new URLSearchParams({ status });\n"
        "params.set('kind', kind);\n"
        "const r = await apiFetch(`${apiBase}/api/v1/memory-records?${params}`);\n"
        ".hljs-params { color: #abb2bf; }\n"
        "function executeCommand(commandId, params) {}\n",
        encoding="utf-8",
    )

    assert _lines(tmp_path, _ROUTE) == [
        "squadops.x/ui/src/View.svelte:1",
        "squadops.x/ui/src/View.svelte:4",
    ]
    assert _lines(tmp_path, _PARAMS_KEY) == [
        "squadops.x/ui/src/View.svelte:2",
        "squadops.x/ui/src/View.svelte:6",
    ]
