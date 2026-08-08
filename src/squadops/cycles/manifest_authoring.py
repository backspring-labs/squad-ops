"""Authored-manifest mode: who writes the interface manifest, and when (#791, M1).

Two questions this module answers, both of which were previously answered by string
literals scattered across three layers:

**Is this cycle authoring its own manifest?** Seeded mode binds an operator-supplied
manifest and the contract derived from it; authored mode has the squad write one. The
distinction is *derived from config that already exists* — a scaffoldable stack with no
pinned contract — rather than announced by a new flag, so there is no third state where
a cycle claims authored mode while a seeded contract sits underneath it.

**What may the author read?** SIP-0103 §5c.1 makes the input contract normative: the PRD,
the blueprint's closed vocabulary, the cycle's own framing outputs, and in-cycle rejection
context — *nothing from outside the cycle*. §4 excludes the reference manifest explicitly,
because an authoring stage that has seen the answer measures nothing. Declared here and
enforced by test, so "undeclared inputs are contamination by definition" is a property
rather than an intention.

Nothing below framing branches on the answer to either question (Guard 1a): the emitted
artifact carries the same filename and type the seeded rail uses, so the expander,
contract derivation, and every 1.4/1.5 enforcement surface cannot tell who wrote it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.capabilities.scaffold import is_scaffoldable_stack

#: The framing stage that authors the manifest (SIP-0103 §3.1). Dev owns it: the manifest
#: is an architecture artifact, and §5a places it at the best-informed moment — after the
#: technical design, rather than riding the lead's plan authoring at the least-informed one.
AUTHOR_MANIFEST_CAPABILITY = "development.author_manifest"
AUTHOR_MANIFEST_ROLE = "dev"

#: The stored artifact's type. Identical to the seeded rail's, deliberately — see the
#: module docstring's Guard 1a note. Single-sourced here because three layers previously
#: spelled it as a bare literal (emitter, forwarding filter, loader).
MANIFEST_ARTIFACT_TYPE = "interface_manifest"

#: Envelope input keys the authoring stage may read — the §5c.1 contract, as data.
#:
#: ``prior_outputs`` carries the cycle's own framing documents (strategy's frame, dev's
#: technical design), which §5a puts *inside* the contract: "strategy's frame constrains
#: scope from above". Which documents land there is the context-assembly registry's
#: declaration, not this module's.
AUTHORING_INPUT_CONTRACT: frozenset[str] = frozenset(
    {
        "prd",
        "prior_outputs",
        "resolved_config",
        # #669 in-cycle rejection context — the revise-don't-re-dice rail.
        "rejection_reasons",
        "rejected_plan_yaml",
        # Dispatch mechanics, not design inputs: model selection and chat kwargs.
        "agent_model",
        "agent_config_overrides",
    }
)

#: Where cross-cycle memory plugs in later, named now so the integration is an intended
#: extension rather than unexplained drift (§5c.9). A recall added here must arrive with
#: its provenance; anything that appears without an entry is contamination by the rule above.
INPUT_CONTRACT_EXTENSION_POINTS: tuple[str, ...] = ("cross_cycle_recall",)


def authors_interface_manifest(resolved_config: Mapping[str, Any] | None) -> bool:
    """True when the squad writes the manifest rather than binding a seeded one.

    Derived, not declared. A pinned ``contract_ref`` means the contract was emitted from
    a manifest that already exists and binds its exact hash — asking framing to re-derive
    it from a product-only PRD is unwinnable, since any naming drift breaks the binding
    (#496). A non-scaffoldable stack has no expander, so a manifest would describe a
    skeleton nothing can build.

    Rollback is therefore a profile edit — point the profile at a seeded contract — not a
    code revert.
    """
    config = resolved_config or {}
    if config.get("contract_ref"):
        return False
    return is_scaffoldable_stack(str(config.get("build_profile") or ""))
