"""The baseline stylesheet both walking skeletons emit (#906, #1463).

One sheet, two stacks. The rationale below is the whole design and it is stack-neutral:
the sheet selects on elements, so it has no opinion about which framework rendered them.
Duplicating it per stack would mean two copies drifting apart, and a delivered app's floor
differing by stack for no reason anyone chose — which is the defect this module closes, in
its second instance.

Each stack keeps its own *filename*, because that part is convention and not shared:
Next.js emits ``app/globals.css`` imported by the frozen root layout, stack #1 emits
``frontend/src/index.css`` imported by the frozen ``main.jsx``.
"""

from __future__ import annotations

#: The baseline stylesheet. Scaffold-owned, frozen, and never a fill slot.
#:
#: Delivered apps rendered with browser default styles, because the skeleton shipped no
#: stylesheet at all — nothing chose that look, it was simply absent. This supplies a floor.
#:
#: **Every rule is element-scoped on purpose.** A class-based stylesheet is a vocabulary the
#: fill author has to be taught, remember, and apply — which is a per-roll lottery, a new way
#: for a roll to fail, and a prompt surface to maintain. Selecting on elements instead means
#: the sheet styles whatever markup the author happens to write, with zero coordination: no
#: prompt change, nothing to learn, nothing to get wrong. The author never needs to know it
#: exists. That is the difference between a styling *capability* and a styling *floor*, and
#: only the floor is free.
#:
#: Consequences accepted deliberately:
#: - **Best-effort by construction.** A page built from semantic elements gets styled; a page
#:   built from a pile of `<div>`s gets the container and type treatment and little else.
#:   Improving that means teaching a vocabulary, which is the trade this rule exists to refuse.
#: - **Light only, no `prefers-color-scheme` block.** A dark scheme here would invert the page
#:   ground while any inline or component-level color the author wrote stays light, so the
#:   failure mode is a half-dark page that looks broken. A predictable floor beats a
#:   conditional one.
#: - **No reset.** Normalizing every element is a larger surface for no benefit at this scope.
BASELINE_CSS = """/* Baseline presentation. Scaffold-owned and frozen — do not edit.
   Element-scoped on purpose: it styles the markup you write without you doing anything. */

:root {
  --ink: #1c1e21;
  --muted: #61656b;
  --line: #e3e5e8;
  --accent: #2d6cdf;
  --surface: #ffffff;
  --ground: #f6f7f9;
  --radius: 8px;
}

* { box-sizing: border-box; }

body {
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  max-width: 56rem;
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial,
    sans-serif;
  font-size: 16px;
  line-height: 1.55;
  color: var(--ink);
  background: var(--ground);
}

h1, h2, h3 { line-height: 1.25; margin: 0 0 0.5rem; font-weight: 650; }
h1 { font-size: 1.75rem; margin-top: 0.5rem; }
h2 { font-size: 1.25rem; margin-top: 2rem; }
h3 { font-size: 1.05rem; margin-top: 1.5rem; }
p { margin: 0 0 1rem; }
small { color: var(--muted); }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

ul, ol { padding-left: 1.25rem; margin: 0 0 1rem; }
li { margin: 0.25rem 0; }

/* An unadorned list of records is the most common shape these apps render. */
ul li { list-style: none; }
ul {
  padding-left: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
ul li {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
}

table { width: 100%; border-collapse: collapse; margin: 0 0 1.5rem; background: var(--surface); }
th, td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--line); }
th { font-weight: 600; color: var(--muted); font-size: 0.85rem; text-transform: uppercase;
  letter-spacing: 0.03em; }
tr:last-child td { border-bottom: none; }

form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin: 0 0 1.5rem;
}

label { font-size: 0.9rem; font-weight: 550; color: var(--muted); }

input, select, textarea {
  font: inherit;
  color: inherit;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  width: 100%;
}
input:focus, select:focus, textarea:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
  border-color: var(--accent);
}

button {
  font: inherit;
  font-weight: 550;
  padding: 0.55rem 1.1rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  align-self: flex-start;
}
button:hover { filter: brightness(1.08); }
button:disabled { opacity: 0.55; cursor: not-allowed; }

code, pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
}
pre {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem;
  overflow-x: auto;
}
"""
