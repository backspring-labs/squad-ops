"""Re-present sips/ as a browsable section (mkdocs-gen-files).

The SIPs are already markdown with YAML front matter, so this does not parse,
transform, or restyle them — it copies each one verbatim and builds one index
page. Material reads `title` and the rest of the front matter natively.

The single transformation is link fixing: SIP bodies cross-reference repo paths
(`docs/plans/...`, code, each other) which do not resolve once published. Links
to another published SIP become site links; links to anything else in the repo
become GitHub URLs; links to files that no longer exist lose the link and keep
the text, because a link to nothing is worse than prose.

Generated rather than copied by hand so promotion stays a one-command act:
`scripts/maintainer/update_sip_status.py` moves the file, and the site follows
on the next push with nothing for anyone to remember.
"""

from __future__ import annotations

import re
from pathlib import Path

import mkdocs_gen_files
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BLOB = "https://github.com/backspring-labs/squad-ops/blob/main"

#: Published statuses, in index order. Deprecated proposals are published
#: deliberately — a lifecycle that shows only survivors misrepresents how the
#: decisions were actually made.
STATUSES = {
    "implemented": "Accepted, built, and verified against the code.",
    "accepted": "A design commitment on main. Implementation may be in flight.",
    "proposed": "Filed for review — not a commitment.",
    "deprecated": "Superseded or abandoned. Kept because the record matters.",
}

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
MD_LINK = re.compile(r"\[([^\]]+)\]\((?!https?://|#|/)([^)]+)\)")


def meta_of(text: str) -> dict:
    """Front matter as a dict — via yaml, not a bespoke parser."""
    match = FRONT_MATTER.match(text)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def fix_links(body: str, published: dict[str, str], source: Path, dead: list[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        text, target = match.group(1), match.group(2)
        target, _, anchor = target.partition("#")
        anchor = f"#{anchor}" if anchor else ""
        if not target:
            return match.group(0)
        for base in (source.parent, REPO_ROOT):
            candidate = (base / target).resolve()
            try:
                rel = candidate.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                continue
            if rel in published:
                return f"[{text}]({published[rel]}{anchor})"
            if candidate.exists():
                return f"[{text}]({BLOB}/{rel}{anchor})"
        dead.append(f"{source.name} -> {target}")
        return text

    return MD_LINK.sub(replace, body)


sips = []
for status in STATUSES:
    for path in sorted((REPO_ROOT / "sips" / status).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = meta_of(text)
        sips.append(
            {
                "path": path,
                "rel": path.relative_to(REPO_ROOT).as_posix(),
                "slug": path.stem,
                "text": text,
                "title": meta.get("title") or path.stem,
                "number": meta.get("sip_number", ""),
                "updated": str(meta.get("updated_at", ""))[:10],
                "status": status,
            }
        )

published = {s["rel"]: f"/squad-ops/design/sips/{s['slug']}/" for s in sips}
dead: list[str] = []

for sip in sips:
    out = f"design/sips/{sip['slug']}.md"
    with mkdocs_gen_files.open(out, "w") as fh:
        fh.write(fix_links(sip["text"], published, sip["path"], dead))
    mkdocs_gen_files.set_edit_path(out, sip["rel"])

lines = [
    "# Improvement proposals",
    "",
    "Every architectural decision in Squad Ops is recorded as a **Squad Ops Improvement "
    "Proposal**. A SIP is proposed, reviewed as a *design*, accepted as a commitment, and "
    "only then implemented — so agreeing that something is the right idea stays separate "
    "from agreeing the code is correct.",
    "",
    f"There are **{len(sips)}**. This page is generated from `sips/` on every build. "
    "Search covers the full text of all of them.",
    "",
]
for status, blurb in STATUSES.items():
    group = [s for s in sips if s["status"] == status]
    if not group:
        continue
    group.sort(key=lambda s: (0, f"{int(s['number']):04d}") if str(s["number"]).isdigit()
               else (1, s["title"].lower()))
    lines += [
        f"## {status.title()} ({len(group)})",
        "",
        blurb,
        "",
        "| # | Title | Updated |",
        "|---|---|---|",
    ]
    lines += [
        f"| {s['number'] or '—'} | [{s['title']}]({s['slug']}.md) | {s['updated'] or '—'} |"
        for s in group
    ]
    lines.append("")

with mkdocs_gen_files.open("design/sips/index.md", "w") as fh:
    fh.write("\n".join(lines))

print(f"gen_sips: re-presented {len(sips)} proposals; {len(dead)} dead cross-references unlinked")
