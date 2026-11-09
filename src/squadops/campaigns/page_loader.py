"""The page loader the framework places beside a page criterion's test on a vitest product (#2799).

A repository-backed increment that adds a page proves it with a page criterion (``client_route``),
whose test renders the page's view. Its test runs on the accepted tree, where it must fail, and on
the candidate, where it must pass (SIP-0109 §8.2). A test that imports the view the change adds
fails on the accepted tree before any assertion runs: Vite's import analysis refuses a module that
doesn't exist when it transforms the test, so vitest reports a failed suite. §24ci (a) reads that
as ``only_setup_failures``, never as discrimination, and the increment is refused however correct
the build (``cyc_7cbdae00b2ed``'s T3 to T5).

So the framework places a loader, as it places a criterion's file (§24cj): ``loadView(path)``
resolves the view's module when the test runs and imports it through a variable path, which Vite
leaves to run time (``/* @vite-ignore */``). Where no module is at the path, it returns a component
that renders a not-found marker, so the test fails at its anchor's assertion. A module that is
there is imported as it is, and its own errors stay its own: a view that throws as it loads is a
setup failure on either tree, never a not-found page.

- **Where:** beside the criterion's file, ``criterion_page_loader.js`` (``.ts`` beside a ``.tsx``
  test), so the view's path is the one the test would import it by, relative to its own directory.
  The ``criterion_`` stem is the placed files', which a product's own files never take
  (``criterion_placement.CRITERION_STEM``).
- **Who writes it:** never the squad. Its content is this module's, laid into every tree a
  criterion's test runs on before the candidate exists (the qa task's run tree, the head check),
  and into the candidate at delivery, so the bundle frozen from the candidate carries it
  (``evaluator_trees.freeze_bundle`` follows the test's import) and a later increment's re-run of
  the criterion loads its view as this one did.
- **Its scope:** a ``client_route`` criterion placed under a runner the derived profile names
  ``vitest``, in a ``.jsx`` or ``.tsx`` test (``criterion_placement.runner_placements``). The
  marker is a component that returns a string, which React renders as text.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable

#: The loader's file name, without its extension.
PAGE_LOADER_STEM = "criterion_page_loader"
#: How a criterion's test beside it imports it: extensionless, so a ``.jsx`` test and a ``.tsx``
#: one write it alike, and Vite resolves either file.
PAGE_LOADER_IMPORT = f"./{PAGE_LOADER_STEM}"
#: The loader's extension by its criterion's test's: JSX tests take a JavaScript loader, TSX ones a
#: TypeScript one, so a product that type-checks its tests reads a module of its own language.
_LOADER_EXTENSION = {".jsx": ".js", ".tsx": ".ts"}
#: What the marker says, which a failing test's DOM shows beside the missing anchor.
NOT_FOUND_MARKER = "criterion view not found"

_SOURCE = """\
// Placed by SquadOps beside a page criterion's test (#2799). The framework's file, not the
// product's: delivery writes it, and every criterion test that imports it is frozen with it.
//
// loadView(path) imports a view module when the test runs. Where no module is at `path`, as on
// the product before a change that adds the view, it returns a component that renders a
// not-found marker instead, so the test fails at its assertion rather than at its import. A
// module that exists is imported as it is: an error it raises as it loads is its own.
import { statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ENDINGS = ['', '.jsx', '.tsx', '.js', '.ts', '/index.jsx', '/index.tsx', '/index.js', '/index.ts']

function isFile(path) {
  try {
    return statSync(path).isFile()
  } catch {
    return false
  }
}

function notFound(why) {
  return function CriterionViewNotFound() {
    return `__MARKER__: ${why}`
  }
}

// `path` is the view's module as this directory (the test's own) would import it, such as
// '../views/ExampleView.jsx'. `name` is the export to render: the default one unless named.
export async function loadView(path, name = 'default') {
  const base = resolve(HERE, path)
  const file = ENDINGS.map((ending) => base + ending).find(isFile)
  if (!file) return notFound(`no module at ${path}`)
  const module = await import(/* @vite-ignore */ file)
  return module[name] ?? notFound(`${path} exports no ${name}`)
}
""".replace("__MARKER__", NOT_FOUND_MARKER)


def page_loader_path(test_path: str) -> str | None:
    """Where the loader for the criterion test at ``test_path`` goes: beside it, in the language
    its extension names. ``None`` for a test that renders no JSX, which this loader isn't for."""
    extension = _LOADER_EXTENSION.get(posixpath.splitext(test_path)[1])
    if extension is None:
        return None
    return posixpath.join(posixpath.dirname(test_path), PAGE_LOADER_STEM + extension)


def page_loader_source(path: str) -> str:
    """The loader's content at ``path``: one source, the TypeScript file told not to type-check
    it, since its parameters are untyped and a product's settings for its tests are its own.

    Raises:
        ValueError: ``path`` is no loader's (``page_loader_path``'s).
    """
    name = posixpath.basename(path)
    if name == f"{PAGE_LOADER_STEM}.js":
        return _SOURCE
    if name == f"{PAGE_LOADER_STEM}.ts":
        return "// @ts-nocheck\n" + _SOURCE
    raise ValueError(f"{path} is not a page loader's path")


def page_loader_files(paths: Iterable[str]) -> dict[str, str]:
    """Each loader at ``paths`` with its content, by path, in order and once each."""
    return {path: page_loader_source(path) for path in dict.fromkeys(paths) if path}


__all__ = [
    "NOT_FOUND_MARKER",
    "PAGE_LOADER_IMPORT",
    "PAGE_LOADER_STEM",
    "page_loader_files",
    "page_loader_path",
    "page_loader_source",
]
