"""Unit tests for build profile registry (SIP-0071).

Tests BuildProfile dataclass, get_profile() lookup, constants, and
profile immutability.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.assembly_notes import (
    ASSEMBLY_NOTES_DOCUMENT,
    already_supplied_lines,
)
from squadops.capabilities.handlers.build_profiles import (
    ARTIFACT_MODE_MULTI_FILE,
    BUILD_PROFILES,
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
    BuildProfile,
    get_profile,
)

pytestmark = [pytest.mark.domain_capabilities]


class TestGetProfile:
    def test_returns_correct_profile(self):
        profile = get_profile("python_cli_builder")
        assert profile.name == "python_cli_builder"

    def test_raises_value_error_for_unknown_name(self):
        with pytest.raises(ValueError, match="Unknown build profile"):
            get_profile("nonexistent_profile")

    def test_error_message_lists_available_profiles(self):
        with pytest.raises(ValueError, match="python_cli_builder"):
            get_profile("bad_name")


class TestBuildProfileImmutability:
    def test_frozen_dataclass_rejects_mutation(self):
        profile = get_profile("python_cli_builder")
        with pytest.raises(AttributeError):
            profile.name = "hacked"

    def test_frozen_dataclass_rejects_field_assignment(self):
        profile = get_profile("python_cli_builder")
        with pytest.raises(AttributeError):
            profile.artifact_output_mode = "single_file"


class TestPythonCliBuilderProfile:
    def test_required_files_include_dockerfile(self):
        profile = get_profile("python_cli_builder")
        assert "Dockerfile" in profile.required_files

    def test_required_files_include_requirements_txt(self):
        profile = get_profile("python_cli_builder")
        assert "requirements.txt" in profile.required_files

    def test_required_files_include_main_entry(self):
        profile = get_profile("python_cli_builder")
        assert "__main__.py" in profile.required_files

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("python_cli_builder")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE

    def test_has_system_prompt_template(self):
        profile = get_profile("python_cli_builder")
        assert len(profile.system_prompt_template) > 0


class TestTheHandoffIsGoneAndTheNotesAreOptional:
    """#1312: `qa_handoff.md` was required of every builder task, checked by four
    surfaces, and read by nothing — and the builder intermittently completed the
    packaging archetype instead, emitting `.env.example` and `docker-compose.yaml`
    and dropping the report on ~9% of cycles. These would catch its return: a profile
    that requires it again asks for a document no consumer reads, and a profile that
    lists the notes as REQUIRED rebuilds the same generator under a new name.
    """

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_no_profile_requires_the_handoff(self, name, profile):
        assert "qa_handoff.md" not in profile.required_files, (
            f"{name}: the handoff is required again — nothing reads it (#1312)"
        )
        assert "qa_handoff.md" not in profile.optional_files

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_the_notes_are_offered_and_never_required(self, name, profile):
        assert ASSEMBLY_NOTES_DOCUMENT in profile.optional_files, (
            f"{name}: the builder is never told it may write notes"
        )
        assert ASSEMBLY_NOTES_DOCUMENT not in profile.required_files, (
            f"{name}: optional-by-construction is the whole point — a required "
            "notes file is the handoff again"
        )


class TestRoutingConstants:
    def test_routing_builder_present_is_string(self):
        assert isinstance(ROUTING_BUILDER_PRESENT, str)
        assert ROUTING_BUILDER_PRESENT == "builder_role_present"

    def test_routing_fallback_is_string(self):
        assert isinstance(ROUTING_FALLBACK_NO_BUILDER, str)
        assert ROUTING_FALLBACK_NO_BUILDER == "fallback_no_builder"


class TestStaticWebBuilderProfile:
    def test_loads_by_name(self):
        profile = get_profile("static_web_builder")
        assert profile.name == "static_web_builder"

    def test_required_files_include_index_html(self):
        profile = get_profile("static_web_builder")
        assert "index.html" in profile.required_files

    def test_required_files_include_styles_css(self):
        profile = get_profile("static_web_builder")
        assert "styles.css" in profile.required_files

    def test_required_files_include_main_js(self):
        profile = get_profile("static_web_builder")
        assert "main.js" in profile.required_files

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("static_web_builder")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE

    def test_has_system_prompt_template(self):
        profile = get_profile("static_web_builder")
        assert len(profile.system_prompt_template) > 0


class TestWebAppBuilderProfile:
    def test_loads_by_name(self):
        profile = get_profile("web_app_builder")
        assert profile.name == "web_app_builder"

    def test_required_files_include_app_py(self):
        profile = get_profile("web_app_builder")
        assert "app.py" in profile.required_files

    def test_required_files_include_index_html(self):
        profile = get_profile("web_app_builder")
        assert "index.html" in profile.required_files

    def test_required_files_include_requirements(self):
        profile = get_profile("web_app_builder")
        assert "requirements.txt" in profile.required_files

    def test_has_system_prompt_template(self):
        profile = get_profile("web_app_builder")
        assert len(profile.system_prompt_template) > 0


class TestFullstackFastapiReactProfile:
    def test_loads_by_name(self):
        profile = get_profile("fullstack_fastapi_react")
        assert profile.name == "fullstack_fastapi_react"

    def test_required_files_include_dockerfile(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "Dockerfile" in profile.required_files

    def test_docker_compose_is_optional(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "docker-compose.yaml" in profile.optional_files

    def test_optional_files_include_start_sh(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "start.sh" in profile.optional_files

    def test_has_system_prompt_template(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "fullstack" in profile.system_prompt_template.lower()

    def test_validation_rules_mention_multi_stage(self):
        profile = get_profile("fullstack_fastapi_react")
        assert any("multi-stage" in r for r in profile.validation_rules)

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("fullstack_fastapi_react")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE


class TestBuildProfilesRegistry:
    # #838: `assert len(BUILD_PROFILES) == 4` removed rather than bumped to 5 — a count
    # names no bug class, breaks on every legitimate registration, and is the shape
    # docs/TEST_QUALITY_STANDARD.md rules out. Same removal as the DEVELOPMENT_PROFILES
    # count in #836. What matters is the BINDING, pinned in
    # tests/unit/cycles/test_build_profile_registration.py: every scaffoldable stack
    # has a profile, and its absence raises instead of being swallowed.
    def test_all_profiles_are_build_profile_instances(self):
        for name, profile in BUILD_PROFILES.items():
            assert isinstance(profile, BuildProfile), f"{name} is not a BuildProfile"


class TestProfileSourceOfTruthInvariants:
    """Issue #92: required_files/optional_files are the single source of truth.

    The narrative `system_prompt_template` must NOT enumerate filenames; the
    full prompt seen by the LLM is composed via `full_system_prompt` from
    the validator's required/optional tuples. These invariants catch any
    re-introduced drift between the prompt the LLM sees and the validator
    that grades its output.
    """

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_required_and_optional_disjoint(self, name, profile):
        """A filename must appear in exactly one of required_files or
        optional_files. Duplicates were a real source of LLM confusion.
        """
        required_set = set(profile.required_files)
        optional_set = set(profile.optional_files)
        overlap = required_set & optional_set
        assert not overlap, f"{name}: files appear in both required and optional: {sorted(overlap)}"

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_full_system_prompt_lists_every_required_file(self, name, profile):
        """The composed system prompt the LLM sees must mention every
        required file by name. Otherwise the LLM is being graded on a file
        it was never asked to produce.
        """
        prompt = profile.full_system_prompt
        for required in profile.required_files:
            assert required in prompt, (
                f"{name}: required file {required!r} not mentioned in full_system_prompt"
            )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_full_system_prompt_lists_every_optional_file(self, name, profile):
        """Optional files should be advertised so the LLM knows it MAY
        produce them. Without this, optional files become invisible.
        """
        prompt = profile.full_system_prompt
        for optional in profile.optional_files:
            assert optional in prompt, (
                f"{name}: optional file {optional!r} not mentioned in full_system_prompt"
            )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_narrative_template_does_not_enumerate_filenames(self, name, profile):
        """The narrative `system_prompt_template` must NOT enumerate
        filenames — the file list comes from required_files/optional_files
        via `full_system_prompt`. If a filename leaks into the narrative,
        the prompt has two sources of truth again.

        Heuristic: any token containing a recognized file extension or
        a literal known structural file (Dockerfile) appearing in the
        narrative template is a violation. We allow extensions only inside
        backticked code-block languages (e.g. ```python:foo) by stripping
        those before scanning.
        """
        import re

        narrative = profile.system_prompt_template
        # Strip backticked code/format tokens — those describe the output
        # FORMAT (```dockerfile:Dockerfile), not enumerate which files.
        # We only care about filenames that appear as literal prose.
        stripped = re.sub(r"`[^`]*`", "", narrative)

        # Forbidden patterns: anything that looks like a file with an
        # extension, or known extension-less structural files.
        forbidden = []
        # #838: framework names containing a dot are not filenames. The heuristic below
        # cannot tell `Next.js` from `main.js`, and the existing narratives only escaped it
        # by naming frameworks that happen to have no dot (FastAPI, React, Vite). Naming the
        # framework is not what #92 forbids — enumerating the files the validator grades is.
        product_names = {"Next.js", "Node.js", "Vue.js", "Nuxt.js", "Express.js"}
        # Simple file-with-extension regex (word chars + dot + 2-5 letter ext)
        for match in re.finditer(r"\b[\w./-]+\.[a-zA-Z]{2,5}\b", stripped):
            if match.group(0) in product_names:
                continue
            forbidden.append(match.group(0))
        for sentinel in ("Dockerfile", "Makefile"):
            if sentinel in stripped:
                forbidden.append(sentinel)

        assert not forbidden, (
            f"{name}: narrative system_prompt_template enumerates filenames "
            f"{forbidden!r}; move them to required_files/optional_files so the "
            f"prompt and validator share one source of truth (issue #92)."
        )

    @pytest.mark.parametrize("stack", ["fullstack_fastapi_react", "nextjs_ts"])
    def test_the_notes_block_names_the_stacks_own_commands(self, stack):
        """#1312: the exclusion list is DERIVED from the stack's declarations, so it
        cannot tell the builder to omit a fact the test author never received.

        The bug this catches is a hand-written list: a stack changes its start command
        or its test namespace, the prompt keeps saying the old one, and the builder
        omits the fact that actually mattered. Asserted against the declarations
        themselves — the environment contract's argv and the scaffold's namespace —
        so the test moves with them.
        """
        from squadops.capabilities.scaffold import qa_test_namespace_for_stack
        from squadops.sandbox.environment import get_environment_contract

        prompt = get_profile(stack).full_system_prompt
        contract = get_environment_contract(stack)
        for _operation, argv in contract.commands().items():
            rendered = " ".join(argv)
            assert rendered in prompt, f"{stack}: the prompt omits {rendered!r}"
        assert f"port `{contract.app_port}`" in prompt
        for namespace in qa_test_namespace_for_stack(stack):
            assert f"`{namespace}`" in prompt

    def test_a_stack_that_declares_nothing_renders_no_exclusion_list(self):
        """The control, and the reason the list is derived rather than written: a
        profile with no environment contract has nothing to claim as already supplied.
        Inventing a list there would be exactly the drift this design prevents."""
        assert already_supplied_lines("python_cli_builder") == ()
        prompt = get_profile("python_cli_builder").full_system_prompt
        assert "Already supplied to the test author" not in prompt

    @pytest.mark.parametrize("stack", ["fullstack_fastapi_react", "nextjs_ts"])
    def test_the_notes_are_framed_as_omittable(self, stack):
        """A builder that reads "optional" as "produce something" writes a summary of
        its own work — the restatement the exclusion list exists to stop. The prompt
        has to say that writing nothing is a complete answer."""
        prompt = get_profile(stack).full_system_prompt
        assert "omit the file" in prompt
        assert "do not restate" in prompt.lower()


class TestSystemPromptForFiles:
    """Issue #107: when framing decomposes builder work, the active task's
    expected_artifacts is the source of truth for what must be emitted.
    `system_prompt_for_files(scope)` produces a prompt scoped to that
    subset; `full_system_prompt` (no scope) preserves the legacy
    profile-wide behavior for tasks framing didn't decompose."""

    def _profile(self):
        from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES

        return BUILD_PROFILES["fullstack_fastapi_react"]

    def test_full_system_prompt_unchanged_by_default(self):
        # Legacy callers that read full_system_prompt should still get the
        # profile-wide prompt with every required file + qa_handoff block.
        profile = self._profile()
        prompt = profile.full_system_prompt
        for required in profile.required_files:
            assert f"`{required}`" in prompt

    def test_scoped_prompt_lists_only_task_required_files(self):
        # A decomposed build: this task owns the manifests and the recipe, nothing else.
        profile = self._profile()
        scope = ("package.json", "vite.config.js", "Dockerfile")
        prompt = profile.system_prompt_for_files(scope)

        for name in scope:
            assert f"`{name}`" in prompt
        assert "`nginx.conf`" not in prompt.split("## Optional artifacts")[0]

    def test_every_scoped_builder_task_may_still_write_notes(self):
        """#1312: the notes block rides the profile's optional files, not the task's
        scoped required set.

        Scoping it the way the handoff was scoped would mean a decomposed build had
        exactly one task allowed to say something and the rest silently forbidden —
        and the task that learned something while writing the Dockerfile is usually
        not the one framing routed the documentation to.
        """
        profile = self._profile()
        prompt = profile.system_prompt_for_files(("Dockerfile",))
        assert f"`{ASSEMBLY_NOTES_DOCUMENT}`" in prompt
        assert "Already supplied to the test author" in prompt

    def test_none_scope_falls_back_to_profile_required(self):
        # Tasks framing didn't decompose pass through with no scope.
        profile = self._profile()
        prompt_none = profile.system_prompt_for_files(None)
        prompt_full = profile.full_system_prompt
        assert prompt_none == prompt_full

    def test_empty_scope_falls_back_to_profile_required(self):
        profile = self._profile()
        prompt_empty = profile.system_prompt_for_files(())
        prompt_full = profile.full_system_prompt
        assert prompt_empty == prompt_full
