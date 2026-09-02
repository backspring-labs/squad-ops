"""Every published SIP link in the site's static content resolves (site build integrity).

``pages.yml`` runs ``mkdocs build --strict``, which promotes a dangling internal link
to a build failure — so one stale link stops the site deploying entirely, and the
symptom appears on whatever PR merges next rather than on the one that caused it.

**The failure this guards.** Release packages are frozen evidence captured at the cut
(``build_release_package.py``); SIP promotion renames files, because a proposal gains
its number when it is accepted. ``gen_sips.py`` publishes each SIP at a slug derived
from its filename, so promoting a SIP moves its page and silently invalidates every
frozen reference to the old name.

``build_release_package.py`` already encodes the rule — it links a move only when the
page exists — but evaluates it **once, at capture**. Frozen evidence outlives that
check.

Observed 2026-08-28: SIP-0106 was accepted and renamed twice
(``SIP-Atlas-Provider-Adapter`` → ``SIP-0106-Atlas-Provider-Adapter-Config-Selected``
→ ``SIP-0106-Atlas-Provider-Adapter``). ``releases/v1.6.0/index.md`` still linked the
original name, and the site build failed on that single warning for **five consecutive
merges** — v1.7.0 was tagged, released, and its package committed, none of it ever
reaching the site.

The fix when this fails is the generator's own rule applied at today's date: the move
is the fact and stays recorded; the link is a convenience. Drop the link, keep the
text — never repoint it at a successor, which would assert a continuity the record
does not claim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT = REPO_ROOT / "site" / "content"

#: A markdown link into the generated SIP tree, e.g. ``../../design/sips/SIP-0104-Foo.md``.
SIP_LINK = re.compile(r"\]\([^)]*design/sips/([A-Za-z0-9._-]+)\.md[^)]*\)")

#: ``gen_sips.py`` also writes the browse page at ``design/sips/index.md``
#: (``gen_sips.py:141``). It is a generated sibling of the SIP pages, not a proposal,
#: so it is legitimately linked from the overview, architecture and roadmap pages and
#: must not be read as a missing SIP.
GENERATED_SIBLINGS = frozenset({"index"})


def published_sip_slugs() -> set[str]:
    """The page slugs ``gen_sips.py`` will publish — its own ``path.stem`` rule."""
    return {path.stem for path in (REPO_ROOT / "sips").glob("*/*.md")} | GENERATED_SIBLINGS


class TestSiteSipLinks:
    def test_every_sip_link_in_site_content_resolves(self) -> None:
        """Bug caught: a SIP renamed by promotion leaves a dangling link in frozen
        release evidence, and ``mkdocs build --strict`` refuses to deploy the site."""
        slugs = published_sip_slugs()
        assert slugs, "no SIPs found — the glob or the layout changed"

        dangling: list[str] = []
        for page in sorted(CONTENT.rglob("*.md")):
            for slug in SIP_LINK.findall(page.read_text(encoding="utf-8")):
                if slug not in slugs:
                    dangling.append(f"{page.relative_to(CONTENT).as_posix()} -> {slug}")

        assert not dangling, (
            "dangling SIP links would fail `mkdocs build --strict` and block the site "
            f"deploy: {dangling}. The SIP was almost certainly renamed by promotion — "
            "drop the link and keep the plain text (the move is the fact; the link is "
            "a convenience), rather than repointing it at the renamed file."
        )

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("[X](../../design/sips/SIP-0104-Foo.md)", ["SIP-0104-Foo"]),
            ("[X](/squad-ops/design/sips/SIP-Bar.md#anchor)", ["SIP-Bar"]),
            ("plain SIP-0104-Foo with no link", []),
            ("[X](../../design/other/SIP-0104-Foo.md)", []),
            ("[Browse](design/sips/index.md)", ["index"]),
        ],
    )
    def test_link_pattern_matches_the_shapes_that_appear(
        self, text: str, expected: list[str]
    ) -> None:
        """Bug caught: a pattern that misses the anchored or absolute form would pass
        this suite while the site build still failed on those links."""
        assert SIP_LINK.findall(text) == expected

    def test_the_generated_browse_page_is_not_read_as_a_missing_sip(self) -> None:
        """Bug caught: a guard that flags ``design/sips/index.md`` — the page
        ``gen_sips.py`` generates for browsing — would fail on three legitimate
        overview links and train the next reader to weaken the assertion."""
        assert "index" in published_sip_slugs()
        assert SIP_LINK.findall("[Browse](design/sips/index.md)") == ["index"]

    def test_a_synthetic_dangling_link_is_detected(self, tmp_path: Path) -> None:
        """Bug caught: the guard silently passing because it scans the wrong tree or
        reads nothing — a green result must mean 'checked and clean', not 'found no
        files'."""
        page = tmp_path / "index.md"
        page.write_text("| [S](../../design/sips/SIP-Does-Not-Exist.md) | new |", encoding="utf-8")
        found = SIP_LINK.findall(page.read_text(encoding="utf-8"))
        assert found == ["SIP-Does-Not-Exist"]
        assert found[0] not in published_sip_slugs()
