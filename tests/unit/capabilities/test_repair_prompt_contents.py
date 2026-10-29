"""What a correction repair's prompt shows of its tree, rendered and counted from one module (#2810).

The repair handlers render the current files, the edit form and a qa repair's failing-case frames
through ``repair_prompt_contents``, on the agents. The composer counts a repair's tree
(``acceptance_workspace_files`` with ``failed_task_artifacts`` over it) through
``repair_prompt_contents.repair_prompt_contents`` (``prompt_budget.rendered_input_tokens``), in the
runtime, where ``REPAIR_CONTEXT_CONTRACT`` names the rendering. The runtime carries no JavaScript
parser, so the composer counts the edit form by its bound, ``edit_form_bound``, and parses nothing.
The handlers' prompts are pinned byte for byte in
``tests/unit/capabilities/handlers/test_repair_prompt_characterization.py``.

What bugs would these catch?
- **The composer counting the whole tree** where the repair shows its named files, so a repair on
  a product larger than half its window is held on an instruction that fits (#2810).
- **The composer counting less than the prompt shows:** the edit form lists each file's entities
  beside the file, which on a small file is longer than the file; the failing frames are a third
  showing. Counted short, a binding is admitted that the window then can't hold.
- **The composer parsing a file** (#2812's review): tree-sitter is the agents', so a repair naming
  a JavaScript or TypeScript file raised out of the runtime's budget on every React and Next.js
  cycle, and a parse there blocks the runtime's event loop.
- **The base read wrong:** the failed task's own file not laid over the workspace's, a scaffold
  shell or an unsafe path offered, or a file the repair creates shown as if it existed.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from collections import Counter
from types import SimpleNamespace

import pytest

from squadops.capabilities import context_assembly
from squadops.capabilities.prompt_budget import (
    prompt_budget,
    prompt_without_memory_tokens,
    rendered_input_tokens,
)
from squadops.capabilities.repair_prompt_contents import (
    REPAIR_BASE_INPUTS,
    anchorable_files,
    edit_form,
    edit_form_bound,
    repair_prompt_contents,
)
from squadops.cycles import structural_jsx, structural_resolution
from squadops.cycles.structural_jsx import ECMASCRIPT_SUFFIXES, SELECTORS_PER_STATEMENT_MAX
from squadops.cycles.structural_resolution import (
    SELECTOR_KIND_MAX,
    SELECTOR_NAMES_MAX,
    SELECTOR_SUFFIX_MAX,
    entity_selectors,
)
from squadops.memory.lessons import _tokens
from tests.unit.cycles._product_increment import INSTRUCTION_TOKENS, LONG_LINE_FILES

pytestmark = [pytest.mark.domain_capabilities]

_ROUTES = "def list_moons():\n    return []\n\n\ndef moon_period(name):\n    return 0\n"
_SUITE = "".join(f"def test_moon_{i}():\n    assert moon_period('io') == {i}\n\n\n" for i in (1, 2))
_EVIDENCE = {
    "validation_result": {
        "checks": [
            {
                "check": "tests_pass",
                "failing_cases": [
                    {"file": "tests/test_orbit.py", "title": "test_moon_2", "failing_line": 6}
                ],
            }
        ]
    }
}


def _inputs(**extra) -> dict:
    return {
        "prd": "Orbit lists each moon and its period.",
        "expected_artifacts": ["orbit/routes.py", "tests/test_orbit.py", "orbit/new.py"],
        "acceptance_workspace_files": {"orbit/routes.py": _ROUTES, "orbit/store.py": "ROWS = []\n"},
        "failed_task_artifacts": [{"name": "tests/test_orbit.py", "content": _SUITE}],
        "failure_evidence": _EVIDENCE,
        **extra,
    }


def _escaped(text: str) -> int:
    """``text``'s length as the composer counts it: JSON, without the quotes."""
    return len(json.dumps(text)) - 2


def test_the_prompt_shows_the_named_files_their_edit_form_and_the_failing_frame():
    """The three sections, exactly as the handler renders them: the named files that exist in the
    base (the workspace's, and the failed task's own over it), never the file it creates nor one it
    doesn't name. The composer counts the first and the last as shown, and the edit form by its
    bound. Bug caught: the base read without the overlay, or a named new file shown."""
    inputs = _inputs()
    shown = repair_prompt_contents(inputs)
    lines, offered = edit_form(inputs)

    assert shown["current_files"] == (
        "`orbit/routes.py`:\n```\n" + _ROUTES + "```\n\n"
        "`tests/test_orbit.py`:\n```\n" + _SUITE + "```"
    )
    assert lines == [
        "- `orbit/routes.py` — entities: `function:list_moons`, `function:list_moons#body`, "
        "`function:moon_period`, `function:moon_period#body`",
        "- `tests/test_orbit.py` — entities: `function:test_moon_1`, "
        "`function:test_moon_1#body`, `function:test_moon_2`, `function:test_moon_2#body`",
    ]
    assert offered == {"orbit/routes.py": 4, "tests/test_orbit.py": 4}
    assert shown["editable_files"] == " " * edit_form_bound(inputs)
    assert shown["case_frames"] == (
        "`tests/test_orbit.py:6` › test_moon_2\n```\n"
        "     1 | def test_moon_1():\n"
        "     2 |     assert moon_period('io') == 1\n"
        "     3 | \n     4 | \n"
        "     5 | def test_moon_2():\n"
        "→    6 |     assert moon_period('io') == 2\n"
        "     7 | \n     8 | \n```"
    )


_SIXTY = "".join(f"def phase_{i}(moon):\n    return moon.phase + {i}\n\n\n" for i in range(60))
#: A class whose name is long, and more long-named methods than the form lists, so every listed
#: selector carries two long names (``method:CLASS.NAME#body``).
_REGISTRY = "class TheRegistryOfEveryMoonOrbitingEveryPlanetInTheSystem:\n" + "".join(
    f"    def record_the_orbital_period_of_moon_number_{i:02d}(self):\n        return {i}\n\n"
    for i in range(45)
)
_TABLE = "PERIODS = [" + ", ".join(str(i) for i in range(1500)) + "]\n\n\ndef f():\n    return 1\n"
#: Route handlers whose long names each give three selectors (the function, its body and its
#: ``try``), more than the form lists.
_HANDLERS = "".join(
    f"export async function {'handle_the_orbit_of_every_moon_' * 6}{i}() {{\n"
    "  try {\n    return 1;\n  } catch (e) {\n    return 2;\n  }\n}\n\n"
    for i in range(15)
)
#: Invented files of each kind of selector either resolver writes, and how many entities each
#: lists: a class and its methods (``method:CLASS.NAME``), an import a backslash continues and
#: decorators; more entities than the form lists, ``(+N more)``; names outside ASCII, which JSON
#: writes six characters each; Windows line endings; one very long line; JSX, TypeScript and a
#: route handler's ``#try``; a JavaScript import source a backslash continues; an unparseable file;
#: and a file no resolver reads.
_FORMS = {
    "orbit/routes.py": (_ROUTES, 4),
    "orbit/ledger.py": (
        "from orbit.\\\n    store import ROWS\nimport json, os\n\n\n"
        "class OrbitalLedgerOfEveryMoonAroundEveryPlanet:\n"
        "    def record_the_period_of_one_moon(self, moon):\n        return ROWS\n\n"
        "    @property\n    def total(self):\n        return len(ROWS)\n",
        8,
    ),
    "orbit/phases.py": (_SIXTY, 120),
    "orbit/registry.py": (_REGISTRY, 91),
    "orbit/lunes.py": (
        "class Lune:\n    def périhélie(self):\n        return 'é'\n\n\n"
        "def année_lunaire():\n    return 354\n",
        5,
    ),
    "orbit/crlf.py": ("def ebb():\r\n    return 1\r\n", 2),
    "orbit/table.py": (_TABLE, 2),
    "console/src/Panel.jsx": (
        "import React from 'react';\nimport { moons } from '../data/moons-of-every-planet';\n\n"
        "export function Panel({ items }) {\n  return items.map((m) => m.name).join(', ');\n}\n\n"
        "const Row = ({ moon }) => {\n  return moon.name;\n};\n\nclass Orbit {}\n",
        8,
    ),
    "console/src/types.ts": (
        "import type { Moon } from './very/long/path/to/the/shared/moon/types/module';\n\n"
        "export interface MoonPeriod {\n  days: number;\n}\n\n"
        "export type Phase = 'new' | 'full';\n\nexport enum Planet {\n  Jupiter,\n}\n",
        5,
    ),
    "app/api/moons/route.ts": (
        "export async function GET() {\n  try {\n    return Response.json([]);\n  } catch (e) {\n"
        "    return Response.json({ error: 'x' }, { status: 500 });\n  }\n}\n",
        3,
    ),
    "app/api/handlers/route.ts": (_HANDLERS, 45),
    "console/src/continued.js": (
        "import data from './moons\\\n-table.js';\n\nexport const n = 1;\n",
        3,
    ),
    # A form feed inside an import's source: a line break to ``str.splitlines``, not to either
    # resolver.
    "console/src/formfeed.js": (
        "import data from 'a" + "\x0ca" * 80 + "';\n\nexport const n = 1;\n",
        3,
    ),
    "console/src/broken.jsx": ("export function Panel( {\n", 0),
    "docs/notes.md": ("# Notes\n", 0),
}


@pytest.mark.parametrize("path", list(_FORMS))
def test_the_edit_forms_bound_is_never_below_the_form_the_agent_renders(path):
    """Entered at ``edit_form_bound``, the edit form's count, beside ``edit_form``, which the agent
    renders with the parsers this test's environment carries, for each file above. Bug caught: a
    selector longer than the bound assumes, so the composer counts the form short."""
    content, entities = _FORMS[path]
    inputs = {"expected_artifacts": [path], "acceptance_workspace_files": {path: content}}

    lines, offered = edit_form(inputs)

    assert offered == {path: entities}
    assert _escaped("\n".join(lines)) <= edit_form_bound(inputs)


@pytest.mark.parametrize(
    "path", [p for p in _FORMS if p.endswith(".py")] + ["docs/notes.md", "tests/fixture.json"]
)
def test_a_python_file_and_one_no_resolver_reads_are_counted_exactly(path):
    """Python's resolver is ``ast``, in process, and a file no resolver reads is listed by its path
    alone, so neither needs a bound (#2812's third reading). Bug caught: either counted at the
    JavaScript bound, forty times its longest line."""
    content = _FORMS[path][0] if path in _FORMS else LONG_LINE_FILES[path]
    inputs = {"expected_artifacts": [path], "acceptance_workspace_files": {path: content}}

    assert edit_form_bound(inputs) == _escaped("\n".join(edit_form(inputs)[0]))


def test_the_edit_forms_bound_covers_every_file_in_one_form():
    """Every file above in one form, with the lines between them; and on an ordinary TypeScript
    module of about 1,100 tokens whose form lists forty of its eighty entities, the bound is under
    500 tokens, near the form's own 281. Bug caught: the separators uncounted, or a bound so loose
    that it holds a repair whose prompt fits."""
    every = {
        "expected_artifacts": list(_FORMS),
        "acceptance_workspace_files": {p: c for p, (c, _n) in _FORMS.items()},
    }
    module = "\n".join(
        f"export function moonPeriod{i}(moon) {{\n  const days = moon.days + {i};\n"
        "  const hours = days * 24;\n  return hours;\n}\n"
        for i in range(40)
    )
    one = {
        "expected_artifacts": ["web/src/moons.ts"],
        "acceptance_workspace_files": {"web/src/moons.ts": module},
    }
    lines, offered = edit_form(one)

    assert _escaped("\n".join(edit_form(every)[0])) <= edit_form_bound(every)
    assert offered == {"web/src/moons.ts": 80}
    assert _tokens(module) > 1_000
    assert _escaped("\n".join(lines)) <= edit_form_bound(one) < 500 * 4


@pytest.mark.parametrize("path", list(LONG_LINE_FILES))
def test_the_edit_forms_bound_covers_every_file_it_lists_and_stays_near_it(path, monkeypatch):
    """A file whose one long line is an SVG path, a paragraph, a JSON fixture, a long string or a
    minified bundle (#2812's third reading). Its bound is never below the form the agent renders,
    and on a small product, with no JavaScript parser in reach, its repair's budget is no less
    than main's count, which counted the whole tree, gave. Bug caught: the bound charged forty times
    the longest line whatever the file, so these repairs, which main bound, were held."""
    small = {f"app/m{i}.py": "def f(x):\n    return x + 1\n" * 60 for i in range(10)}
    inputs = {
        "agent_model": "qwen3.8-27b-tf-nvfp4",
        "prd": "Orbit lists each moon.",
        "expected_artifacts": [path],
        "acceptance_workspace_files": {**small, path: LONG_LINE_FILES[path]},
    }
    envelope = SimpleNamespace(task_type="development.correction_repair", inputs=inputs)

    real = _escaped("\n".join(edit_form(inputs)[0]))
    monkeypatch.setitem(sys.modules, "tree_sitter", None)
    monkeypatch.setattr(structural_jsx, "_in_worker", _parsed)
    budget = prompt_budget(envelope)
    whole = dataclasses.replace(context_assembly.REPAIR_CONTEXT_CONTRACT, scoped_rendering="")
    monkeypatch.setattr(context_assembly, "REPAIR_CONTEXT_CONTRACT", whole)
    mains = prompt_budget(envelope)

    assert real <= edit_form_bound(inputs)
    assert budget >= mains > INSTRUCTION_TOKENS, (budget, mains)


@pytest.mark.parametrize(
    ("extra", "anchorable"),
    [
        ({}, ["orbit/routes.py", "tests/test_orbit.py"]),
        # The failed task's own copy wins over the workspace's.
        (
            {"failed_task_artifacts": [{"name": "orbit/routes.py", "content": "X = 1\n"}]},
            ["orbit/routes.py"],
        ),
        # A scaffold shell is filled by slot, never anchored (§9.3).
        (
            {"verification_scaffold": {"files": [{"name": "tests/test_orbit.py"}]}},
            ["orbit/routes.py"],
        ),
        # A path leaving the workspace, an empty one, and a malformed failed artifact.
        (
            {
                "expected_artifacts": ["../orbit/routes.py", "", "./orbit/routes.py"],
                "failed_task_artifacts": [{"content": "no name"}, "not a dict"],
            },
            ["orbit/routes.py"],
        ),
        ({"acceptance_workspace_files": None, "failed_task_artifacts": None}, []),
    ],
    ids=["overlay", "own-copy-wins", "shell", "unsafe-and-malformed", "no-tree"],
)
def test_the_files_offered_are_the_named_ones_in_the_base(extra, anchorable):
    """Edges of the base and the named files, read as the handler reads them. Bug caught: an
    unsafe path or a shell offered for editing, the overlay applied the wrong way round, or a
    missing tree read as an error rather than nothing to show."""
    assert anchorable_files(_inputs(**extra)) == anchorable


def test_the_failed_tasks_own_copy_is_what_the_repair_is_shown():
    """The verifier lays the failed task's files over the workspace (#1264), and the repair edits
    that tree. Bug caught: the workspace's older copy shown, so every anchor copied from it misses."""
    inputs = _inputs(
        expected_artifacts=["orbit/routes.py"],
        failed_task_artifacts=[{"name": "orbit/routes.py", "content": "X = 1\n"}],
    )

    assert repair_prompt_contents(inputs)["current_files"] == "`orbit/routes.py`:\n```\nX = 1\n```"


def _rest(envelope) -> int:
    return rendered_input_tokens(
        SimpleNamespace(
            task_type=envelope.task_type,
            inputs={k: v for k, v in envelope.inputs.items() if k not in REPAIR_BASE_INPUTS},
        )
    )


@pytest.mark.parametrize("task_type", ["development.correction_repair", "qa.test_repair"])
def test_the_composer_counts_a_repairs_tree_as_its_prompt_shows_it(task_type):
    """Entered at ``rendered_input_tokens``, the count ``prompt_budget`` takes. A tree of forty
    modules beside the two named files is counted as what the prompt shows: the named files, their
    edit form and the frame. Bug caught: the whole tree counted (#2810), or the tree and the failed
    task's files each counted again beside the rendering."""
    big = {
        f"orbit/module_{i:02d}.py": "def track(moon):\n    return moon\n" * 60 for i in range(40)
    }
    inputs = _inputs(acceptance_workspace_files={**_inputs()["acceptance_workspace_files"], **big})
    envelope = SimpleNamespace(task_type=task_type, inputs=inputs)
    shown = repair_prompt_contents(inputs)

    assert rendered_input_tokens(envelope) == _rest(envelope) + _tokens(
        json.dumps(shown, sort_keys=True)
    )
    assert _tokens(json.dumps(inputs["acceptance_workspace_files"])) > 10 * _tokens(
        json.dumps(shown)
    )


def test_a_repair_with_no_tree_counts_nothing_for_it():
    """Edge: a repair of a task that carried no workspace (a framing task's) and wrote nothing.
    Bug caught: three empty sections counted for a tree that isn't there, or a crash on the absent
    keys."""
    inputs = {k: v for k, v in _inputs().items() if k not in REPAIR_BASE_INPUTS}
    envelope = SimpleNamespace(task_type="development.correction_repair", inputs=inputs)

    assert repair_prompt_contents(inputs) == {
        "current_files": "",
        "editable_files": "",
        "case_frames": "",
    }
    assert rendered_input_tokens(envelope) == _rest(envelope)


def test_a_task_that_shows_its_inputs_whole_counts_them_whole():
    """The rendering is the repair contract's alone. Bug caught: the repair's scoping reaching a
    task whose prompt shows a workspace-named input whole, under-counting it."""
    inputs = _inputs()
    envelope = SimpleNamespace(task_type="strategy.propose_increment", inputs=inputs)

    assert rendered_input_tokens(envelope) == sum(
        _tokens(v if isinstance(v, str) else json.dumps(v, sort_keys=True)) for v in inputs.values()
    )


def _parsed(*_args, **_kwargs):
    raise AssertionError("the composer parsed a file")


@pytest.mark.parametrize(
    "path", ["console/src/Panel.jsx", "console/src/types.ts", "orbit/ledger.py"]
)
async def test_the_composer_counts_a_repair_with_no_parser_in_reach(path, monkeypatch):
    """#2812's review, entered at ``prompt_budget``: with tree-sitter unimportable, its worker
    raising and the JavaScript resolver raising, as in the runtime, which carries no tree-sitter, a
    repair naming a JSX, TypeScript or Python file is given a budget. Python's resolver is the
    stdlib ``ast``, in process, and stays in reach. The agent's real rendering of the same repair,
    with every parser in reach, is no larger than the count. Bug caught: the composer listing a
    JavaScript file's entities, which raised out of every React and Next.js repair's supply, or a
    count below what the agent renders."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )
    from tests.unit.capabilities.test_repair_decision_section import _context
    from tests.unit.memory.test_prompt_budget_parity import _real_prompts, _rendered

    inputs = {
        **_inputs(
            expected_artifacts=[path],
            acceptance_workspace_files={p: c for p, (c, _n) in _FORMS.items()},
            failed_task_artifacts=[],
        ),
        "agent_model": "qwen3.8-27b-tf-nvfp4",
        "failed_task_type": "development.develop",
        "correction_decision": {"correction_path": "patch", "decision_rationale": "patch it"},
    }
    envelope = SimpleNamespace(task_type="development.correction_repair", inputs=inputs)
    monkeypatch.setitem(sys.modules, "tree_sitter", None)
    monkeypatch.setattr(structural_jsx, "_in_worker", _parsed)
    monkeypatch.setattr(structural_resolution, "jsx_entities", _parsed)

    budget = prompt_budget(envelope)
    estimate = prompt_without_memory_tokens(envelope)
    monkeypatch.undo()
    ctx = _real_prompts(_context("no change", "no change"), "dev")
    await DevelopmentCorrectionRepairHandler().handle(ctx, dict(inputs))
    rendered = _rendered(ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0])

    assert budget > 0
    assert estimate >= rendered, (estimate, rendered)
    assert edit_form(inputs)[1] == {path: _FORMS[path][1]}


#: A selector as both resolvers write it: ``KIND:NAME`` and an optional ``#SUFFIX``.
_SELECTOR = re.compile(r"(?P<kind>[a-z]+:)(?P<name>.*?)(?P<suffix>#[a-z]+)?", re.DOTALL)


@pytest.mark.parametrize("path", list(_FORMS))
def test_every_selector_the_resolvers_write_fits_the_grammar_the_bound_assumes(path):
    """The bound reads selectors' shape from ``structural_resolution.SELECTOR_*`` and, for
    JavaScript, ``structural_jsx.SELECTORS_PER_STATEMENT_MAX``, never from a parse. Entered at
    ``entity_selectors`` on every file above: each selector's kind and suffix fit, its name is at
    most ``SELECTOR_NAMES_MAX`` names each no longer than the file's longest logical line, and a
    JavaScript file's names are identifiers but an import's source, at most three to a statement.
    Bug caught: a resolver that comes to write a longer kind or suffix, a selector of three names,
    or a longer name, so the bound counts the form short without any test failing."""
    content = _FORMS[path][0]
    # The longest logical line, as the bound measures it: physical lines a backslash continues
    # joined, their own characters kept.
    longest = current = 0
    for line in content.split("\n"):
        current += _escaped(line + "\n")
        if not line.rstrip("\r").endswith("\\"):
            longest, current = max(longest, current), 0
    selectors = entity_selectors(path, content) or ()

    for selector in selectors:
        if selector == structural_jsx.SELECTOR_IMPORTS:
            continue
        parts = _SELECTOR.fullmatch(selector)
        assert parts, selector
        assert len(parts["kind"]) <= SELECTOR_KIND_MAX, selector
        assert len(parts["suffix"] or "") <= SELECTOR_SUFFIX_MAX, selector
        name = parts["name"]
        names = [name] if _escaped(name) <= longest else name.split(".")
        assert len(names) <= SELECTOR_NAMES_MAX, selector
        assert all(_escaped(n) <= longest for n in names), selector
        if path.endswith(ECMASCRIPT_SUFFIXES) and parts["kind"] != "import:":
            assert re.fullmatch(r"[\w$\\{}\u200c\u200d]+", name), selector
    if path.endswith(ECMASCRIPT_SUFFIXES):
        per_statement = Counter(
            s.partition("#")[0] for s in selectors if s != structural_jsx.SELECTOR_IMPORTS
        )
        assert max(per_statement.values(), default=0) <= SELECTORS_PER_STATEMENT_MAX
