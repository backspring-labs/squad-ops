"""Tests for planning task_type prompt fragments (SIP-0078 Phase 2b).

Verifies that all 7 planning/refinement prompt fragments:
- Exist at the expected filesystem paths
- Have valid YAML frontmatter with correct fragment_id, layer, roles
- Content hashes match manifest entries
- Assembler can resolve them via task_type parameter
"""

import re
from pathlib import Path

import pytest
import yaml

from adapters.prompts.filesystem import FileSystemPromptRepository

pytestmark = [pytest.mark.domain_capabilities]

FRAGMENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "fragments"

HEADER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.MULTILINE | re.DOTALL)

PLANNING_FRAGMENTS = [
    {
        "fragment_id": "task_type.data.research_context",
        "path": "shared/task_type/task_type.data.research_context.md",
        "layer": "task_type",
        "roles": ["data"],
    },
    {
        "fragment_id": "task_type.strategy.frame_objective",
        "path": "shared/task_type/task_type.strategy.frame_objective.md",
        "layer": "task_type",
        "roles": ["strat"],
    },
    {
        "fragment_id": "task_type.development.design_plan",
        "path": "shared/task_type/task_type.development.design_plan.md",
        "layer": "task_type",
        "roles": ["dev"],
    },
    {
        "fragment_id": "task_type.qa.define_test_strategy",
        "path": "shared/task_type/task_type.qa.define_test_strategy.md",
        "layer": "task_type",
        "roles": ["qa"],
    },
    {
        "fragment_id": "task_type.governance.review_plan",
        "path": "shared/task_type/task_type.governance.review_plan.md",
        "layer": "task_type",
        "roles": ["lead"],
    },
    {
        "fragment_id": "task_type.governance.prepare_plan_authoring_brief",
        "path": "shared/task_type/task_type.governance.prepare_plan_authoring_brief.md",
        "layer": "task_type",
        "roles": ["lead"],
    },
    {
        "fragment_id": "task_type.development.propose_plan_tasks",
        "path": "shared/task_type/task_type.development.propose_plan_tasks.md",
        "layer": "task_type",
        "roles": ["dev"],
    },
    {
        "fragment_id": "task_type.qa.propose_plan_tasks",
        "path": "shared/task_type/task_type.qa.propose_plan_tasks.md",
        "layer": "task_type",
        "roles": ["qa"],
    },
    {
        "fragment_id": "task_type.strategy.propose_plan_guidance",
        "path": "shared/task_type/task_type.strategy.propose_plan_guidance.md",
        "layer": "task_type",
        "roles": ["strat"],
    },
    {
        "fragment_id": "task_type.governance.incorporate_feedback",
        "path": "shared/task_type/task_type.governance.incorporate_feedback.md",
        "layer": "task_type",
        "roles": ["lead"],
    },
    {
        "fragment_id": "task_type.qa.validate_refinement",
        "path": "shared/task_type/task_type.qa.validate_refinement.md",
        "layer": "task_type",
        "roles": ["qa"],
    },
]


def _load_fragment(rel_path: str) -> tuple[dict, str]:
    """Load a fragment file and return (header_dict, content_after_frontmatter)."""
    full_path = FRAGMENTS_DIR / rel_path
    raw = full_path.read_text(encoding="utf-8")
    m = HEADER_PATTERN.match(raw)
    assert m, f"No YAML frontmatter in {rel_path}"
    header = yaml.safe_load(m.group(1))
    content = raw[m.end() :].strip()
    return header, content


def _load_manifest() -> dict:
    """Load and parse manifest.yaml."""
    manifest_path = FRAGMENTS_DIR / "manifest.yaml"
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


class TestPlanningFragmentsExist:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_file_exists(self, spec):
        path = FRAGMENTS_DIR / spec["path"]
        assert path.exists(), f"Fragment file not found: {path}"


class TestPlanningFragmentsFrontmatter:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_fragment_id_matches(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["fragment_id"] == spec["fragment_id"]

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_layer_is_task_type(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["layer"] == "task_type"

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_roles_match(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["roles"] == spec["roles"]


class TestPlanningFragmentsManifest:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_manifest_entry_exists(self, spec):
        manifest = _load_manifest()
        entries = [
            f
            for f in manifest["fragments"]
            if f["fragment_id"] == spec["fragment_id"] and f["path"] == spec["path"]
        ]
        assert len(entries) == 1, (
            f"Expected exactly 1 manifest entry for {spec['fragment_id']}, found {len(entries)}"
        )

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_content_hash_matches_manifest(self, spec):
        """Manifest sha256 matches the hash the runtime computes for the
        fragment body. Uses the same hasher the repository's integrity check
        and the regen script use, so a drift here is the exact failure the
        assembler would raise at runtime (HashMismatchError) — see issue #195."""
        actual_hash = FileSystemPromptRepository.hash_fragment_file(FRAGMENTS_DIR / spec["path"])

        manifest = _load_manifest()
        entry = next(
            f
            for f in manifest["fragments"]
            if f["fragment_id"] == spec["fragment_id"] and f["path"] == spec["path"]
        )
        assert actual_hash == entry["sha256"], (
            f"Hash mismatch for {spec['fragment_id']}: "
            f"computed={actual_hash}, manifest={entry['sha256']}"
        )

    def test_full_manifest_integrity(self):
        """Every manifest sha256 matches its fragment body across ALL fragments,
        not just the planning ones parametrized above — catches drift in
        identity/constraints/etc. that the per-fragment cases miss (e.g. the
        comms identity hash, #195). Reuses the repository's own integrity sweep
        so the test and the runtime check can't diverge."""
        repo = FileSystemPromptRepository(base_path=FRAGMENTS_DIR)
        assert repo.validate_integrity() is True


class TestPlanningFragmentsContent:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_content_is_non_empty(self, spec):
        _, content = _load_fragment(spec["path"])
        assert len(content) > 50, f"Fragment content too short: {len(content)} chars"

    def test_task_type_fragments_total(self):
        """Exactly 22 task_type fragments exist:
        5 planning + 2 refinement + 5 wrap-up + 3 SIP-0079 impl
        (analyze_failure, correction_decision, define_done —
        moved out of hardcoded constants in impl/*.py) +
        5 SIP-0093 (prepare_plan_authoring_brief, review_plan_manifest,
        development.propose_plan_tasks, qa.propose_plan_tasks,
        strategy.propose_plan_guidance) +
        1 build-segment (qa.test — #448, first build handler routed
        through the fragment system instead of inline prompt literals) +
        1 SIP-0103 (development.author_manifest — #791's authoring stage)."""
        task_type_dir = FRAGMENTS_DIR / "shared" / "task_type"
        md_files = list(task_type_dir.glob("*.md"))
        assert len(md_files) == 22


def test_the_manifest_example_shows_a_quoted_collection_type():
    """#858: two of roll 7's four authoring attempts died on `type: list[X]` unquoted.

    Inside a `{ ... }` flow mapping an unquoted `[` opens a flow sequence and the document
    fails to parse before any gate reads it. The example taught flow style with three scalar
    fields and no collection type at all, so the first list an author needed hit the trap —
    while the reference manifest, which SIP-0103 §4 keeps out of squad inputs, has had the
    quoted form all along.
    """
    from pathlib import Path

    asset = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates/request.development_author_manifest.md"
    )
    text = asset.read_text(encoding="utf-8")

    # Scoped to the fenced example, not the file. The prose below it also contains
    # `type: "list[Tag]"`, so a file-wide check passes with the example field deleted —
    # which is exactly what a mutation test caught it doing.
    example = text.split("```yaml:interface_manifest.yaml", 1)[1].split("```", 1)[0]
    assert 'type: "list[' in example, (
        "the EXAMPLE must show a quoted bracket type — an author copies the block, not the "
        "prose around it"
    )
    assert "must be quoted" in text, (
        "a trailing comment is dropped when an author copies the block — the rule needs prose"
    )


#: The worked example's bytes as of the 1.6 measurement ruling (owner, 2026-08-15).
#: Recompute deliberately — never to make this test pass. See the test below.
AUTHOR_MANIFEST_EXAMPLE_SHA256 = "c189b56ba3e34a9da026fadf82bcca068edb7abc8ffc082c09df130f2c52fb94"


def test_the_manifest_example_is_pinned_for_the_measurement_window():
    """The worked example is a held-constant condition of 1.6's yield measurement.

    SIP-0103's gate banks an authored-mode yield number that **1.8's memory and campaign
    work measure against**, so what the number means depends on the authoring conditions
    being identical at both ends. This example is one of those conditions: it teaches a
    REST spine (collection list, create-201, fetch-by-id-404), and V4 measured that the
    spine is *patterned* from it while the domain surface — entities and fields,
    child-action endpoints, error codes and statuses, view decomposition, test anchors —
    is derived from the PRD.

    The owner ruled on 2026-08-15 to hold the example constant across V6, V7 and 1.8 and
    to narrow the claim's wording instead of swapping the example (the alternative makes
    the two measurements incomparable, which costs more than the flattery it removes).
    That ruling is only sound if the example actually stays fixed — an edit made for some
    unrelated reason silently converts the decision into the option it rejected. Hence a
    pin rather than a note.

    **Changing this is a deliberate act, not a test fix.** Editing the example moves the
    conditions of a measurement in flight, so it needs an owner ruling and a recorded
    reason first; only then update the digest. If a change is genuinely required
    mid-window, the window resets — a yield number spanning two authoring conditions is
    not a baseline.
    """
    import hashlib
    from pathlib import Path

    asset = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates/request.development_author_manifest.md"
    )
    example = (
        asset.read_text(encoding="utf-8")
        .split("```yaml:interface_manifest.yaml", 1)[1]
        .split("```", 1)[0]
    )
    digest = hashlib.sha256(example.encode("utf-8")).hexdigest()

    assert digest == AUTHOR_MANIFEST_EXAMPLE_SHA256, (
        "the authoring worked example changed. It is a held-constant condition of the "
        "1.6 yield measurement (owner ruling 2026-08-15) — do not update the digest to "
        "make this pass. Get the ruling, record the reason, and reset the window."
    )
