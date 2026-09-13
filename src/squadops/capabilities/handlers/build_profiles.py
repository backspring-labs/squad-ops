"""Build profile registry for builder role (SIP-0071).

Typed build profiles that control handler behavior: prompt templates,
required files, validation rules, and QA handoff expectations.
V1 profiles are code-defined frozen dataclass instances.

Issue #92 (2026-05-03): each profile's `required_files` and `optional_files`
are the single source of truth. The system prompt that the builder LLM sees
is composed at access time via `BuildProfile.full_system_prompt` so the
narrative `system_prompt_template` cannot drift away from what the validator
will accept. Adding a file to `required_files` automatically adds it to the
prompt; the file list cannot be edited in the prompt without also editing
the validator's `required_files`.

#452: the narrative TEXT lives in ``src/squadops/prompts/profile_narratives/``
(one ``.md`` per profile, loaded once at import) — prompt prose is reviewable
and editable as prose under the prompts seam, never a Python literal (#448).
The profile dimension stays deliberate contract data rather than a fragment
layer; extending the fragment model with a non-role dimension is the deferred
SIP-sized question. Byte-equivalence with the pre-move literals is pinned by
test (the #452 hard acceptance gate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import squadops.prompts as _prompts_pkg
from squadops.capabilities.assembly_notes import (
    ASSEMBLY_NOTES_DOCUMENT,
    assembly_notes_block,
)

_NARRATIVES_DIR = Path(_prompts_pkg.__file__).parent / "profile_narratives"


def _narrative(profile_name: str) -> str:
    """Load a profile's system-prompt narrative from its packaged ``.md`` file.

    Files are stored with one trailing newline (editor/git hygiene); exactly
    one is stripped so a future editor auto-adding the final newline cannot
    change rendered prompt bytes. A missing file raises at module import —
    loud and immediate, never a silently-empty narrative in a prompt.
    """
    text = (_NARRATIVES_DIR / f"{profile_name}.md").read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


# ---------------------------------------------------------------------------
# Routing reason constants (D14)
# ---------------------------------------------------------------------------

ROUTING_BUILDER_PRESENT = "builder_role_present"
ROUTING_FALLBACK_NO_BUILDER = "fallback_no_builder"

# ---------------------------------------------------------------------------
# Artifact output mode constants
# ---------------------------------------------------------------------------

ARTIFACT_MODE_MULTI_FILE = "multi_file"
ARTIFACT_MODE_SINGLE_FILE = "single_file"
ARTIFACT_MODE_STRUCTURED_BUNDLE = "structured_bundle"


# ---------------------------------------------------------------------------
# Build profile dataclass (D2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildProfile:
    """Typed build profile definition (SIP-0071 §5.2).

    Handlers must not mutate profile fields; treat get_profile() return
    as read-only.

    `system_prompt_template` holds only the *narrative* portion (stack
    description and stack-specific guidance). The concrete file list seen
    by the builder LLM is generated from `required_files`/`optional_files`
    via `full_system_prompt`. Do not list specific filenames inside
    `system_prompt_template`.
    """

    name: str
    system_prompt_template: str
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    artifact_output_mode: str = ARTIFACT_MODE_MULTI_FILE
    default_task_tags: dict[str, str] = field(default_factory=dict)

    @property
    def full_system_prompt(self) -> str:
        """Profile-level prompt — every file the profile requires.

        Used when the executing task has no `expected_artifacts` to scope
        the requirements down (legacy single-task builder flows). Prefer
        :meth:`system_prompt_for_files` when the framing step decomposed
        builder work and the active task only owns a subset of the
        profile's required files.
        """
        return self.system_prompt_for_files(None)

    def system_prompt_for_files(
        self, task_required_files: tuple[str, ...] | list[str] | None
    ) -> str:
        """Compose the system prompt scoped to the active task's required files.

        Issue #107 (cyc_d1c1a259c983, 2026-05-03): when framing decomposes
        builder work into multiple tasks (one for manifests, one for the
        packaging recipe), the profile-level required_files forced every
        builder task to redundantly emit the full set — which exceeded the
        per-call token budget and produced incomplete outputs that failed
        the validator. When `task_required_files` is provided and non-empty,
        the prompt scopes the required-files list to only those files. This
        makes the framing decomposition load-bearing instead of overridden.

        #1312: the notes block rides the profile's OPTIONAL files rather than
        the task's scoped required set, because the notes are optional on
        every builder task — scoping them the way `qa_handoff.md` was scoped
        would mean a decomposed build had one task allowed to say something
        and the rest silently forbidden. What the block may not restate is
        derived from the stack's declarations (`capabilities.assembly_notes`),
        never written here: a hand list drifts the moment a stack changes a
        command, and the builder is then told to omit a fact the test author
        never received.
        """
        scoped = tuple(task_required_files) if task_required_files else self.required_files
        required_lines = "\n".join(f"- `{name}`" for name in scoped)
        optional_block = ""
        if self.optional_files:
            optional_lines = "\n".join(f"- `{name}`" for name in self.optional_files)
            optional_block = f"\n\n## Optional artifacts (emit only if needed)\n\n{optional_lines}"

        notes_block = ""
        if ASSEMBLY_NOTES_DOCUMENT in tuple(scoped) + self.optional_files:
            notes_block = assembly_notes_block(self.name)

        return (
            f"{self.system_prompt_template}\n\n"
            "## Required artifacts (you MUST emit every file in this list)\n\n"
            f"{required_lines}"
            f"{optional_block}"
            f"{notes_block}"
        )

    def expand(self, manifest: object) -> list[dict[str, str]]:
        """Materialize the walking skeleton for ``manifest`` (SIP-0099 §4).

        Thin dispatch: the profile is the seam the executor calls (phase 99.3), while
        all template logic stays in the pure ``scaffold`` module so it keeps no port /
        NoOp / factory. ``scaffold.expand`` owns the stack→expander registry and raises
        if ``manifest.stack`` has no expander, so profiles without a scaffold need no
        special-casing here. Lazily imported to keep ``scaffold`` a leaf sibling.
        """
        from squadops.capabilities.scaffold import expand as _expand

        return _expand(manifest)


# ---------------------------------------------------------------------------
# V1 profile registry
# ---------------------------------------------------------------------------

BUILD_PROFILES: dict[str, BuildProfile] = {
    "python_cli_builder": BuildProfile(
        name="python_cli_builder",
        system_prompt_template=_narrative("python_cli_builder"),
        required_files=("Dockerfile", "__main__.py", "requirements.txt"),
        optional_files=(ASSEMBLY_NOTES_DOCUMENT,),
        validation_rules=(
            "Dockerfile must be valid",
            "__main__.py must wire to developer's entry point",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
    ),
    "static_web_builder": BuildProfile(
        name="static_web_builder",
        system_prompt_template=_narrative("static_web_builder"),
        required_files=("index.html", "styles.css", "main.js"),
        optional_files=("favicon.ico", "manifest.json", ASSEMBLY_NOTES_DOCUMENT),
        validation_rules=(
            "index.html must be valid HTML5",
            "All asset references must use relative paths",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
    ),
    "web_app_builder": BuildProfile(
        name="web_app_builder",
        system_prompt_template=_narrative("web_app_builder"),
        required_files=("app.py", "index.html", "requirements.txt"),
        optional_files=(
            "static/styles.css",
            "static/main.js",
            "templates/",
            ASSEMBLY_NOTES_DOCUMENT,
        ),
        validation_rules=(
            "app.py must be valid Python",
            "requirements.txt must list all dependencies",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
    ),
    "fullstack_fastapi_react": BuildProfile(
        name="fullstack_fastapi_react",
        system_prompt_template=_narrative("fullstack_fastapi_react"),
        required_files=("Dockerfile",),
        optional_files=(
            "docker-compose.yaml",
            "start.sh",
            ".env.example",
            "nginx.conf",
            ASSEMBLY_NOTES_DOCUMENT,
        ),
        validation_rules=(
            "Dockerfile must use multi-stage build",
            "docker-compose.yaml must define backend and frontend services",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
    ),
    # #838 stack #2. The SIXTH per-stack registry, and the one VS found by its absence:
    # `_seed_skeleton_artifacts` resolves `get_profile(manifest.stack)`, which raises for an
    # unregistered name — and the call site swallowed it. A correct `nextjs_ts` manifest would
    # therefore have produced a silently UNSCAFFOLDED cycle, so the wrong manifest was the
    # only one that worked.
    "nextjs_ts": BuildProfile(
        name="nextjs_ts",
        system_prompt_template=_narrative("nextjs_ts"),
        # One project at the root: no docker-compose pairing two services, and the packaging
        # story is a single container serving `next start`.
        required_files=("Dockerfile",),
        optional_files=(".dockerignore", ".env.example", "start.sh", ASSEMBLY_NOTES_DOCUMENT),
        validation_rules=("Dockerfile must build the Next.js app and run `next start`",),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
    ),
}


def get_profile(name: str) -> BuildProfile:
    """Resolve build profile by name.

    Args:
        name: Profile name to look up.

    Returns:
        The matching BuildProfile.

    Raises:
        ValueError: If name is not a registered profile.
    """
    profile = BUILD_PROFILES.get(name)
    if profile is None:
        available = sorted(BUILD_PROFILES.keys())
        raise ValueError(f"Unknown build profile {name!r}. Available profiles: {available}")
    return profile
