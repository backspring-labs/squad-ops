# game-dev-roblox spikes — phase 0 of `docs/plans/game-dev-roblox-plan.md`

**Status: IN PROGRESS, started 2026-11-08** (the owner: "you are good to start"). The record ends at the plan's gate
(§3a): go, narrow or stop. **It holds no game source.** The game's repository is private, so findings describe
patterns and outcomes, and the raw model outputs of S6 stay out of this repository.

| spike | status |
|---|---|
| S1. the Studio transaction | **ready to set up:** the private copy exists (below); its Studio place is the owner's step |
| S2. Rojo and Script Sync | **done:** a Rojo build reads the Script Sync layout correctly with one sync rule kept in Project metadata; the game's modules need a loader to run under Lune |
| S4. the network path | **done:** the MacBook reaches the Spark's runtime API outward over Tailscale |
| S5. the designer test | **done:** partial pass, with one finding that narrows the plan's §2.2 (below) |
| S6. a first Luau probe | **held by the Spark session for the owner's confirmation there;** it runs on TensorFold, the engine the deploy serves `full` from |

## S2. Rojo and Script Sync

**From reading the source at `f2113a6`** (no tool run yet):
- The game's modules load each other through the instance tree (`require(script.Parent...)`, and
  `ReplicatedStorage:WaitForChild("Shared")` on both sides). That includes the shared rule modules that are pure
  logic.
- **So none of its modules loads under Lune as written,** whatever the build tool. Lune's `require` takes a
  filesystem string and refuses an instance (`roblox-spike-2-6.md`). That spike's headless verdict (yes, for pure
  Luau) holds only for code written with string requires. This game's pure logic needs a loader before #2906's
  runner can test it.
- **The loader to try,** not yet verified: a test entry that loads each module's source with `@lune/luau`'s `load`,
  with an environment supplying a `script` proxy (`Parent` and child names resolved against the Script Sync layout)
  and a `require` that maps such a proxy to its file. Small, and kept in the specialty's test tooling. It doesn't
  touch the game's source.

**The Rojo run** (Rojo 7.7.1, `rojo-7.7.1-macos-aarch64.zip`, GitHub asset digest
`sha256:a702659940f6ca061a62df34aa0002ff024aa264efb859007ba890e9524753a4`, checked). The project file sat outside
the game's tree and mapped `src/Server`, `src/Shared` and `src/Client` to the folders Script Sync uses.

| | `Main.server.luau` | `Main.local.luau` | the other 135 `.luau` files |
|---|---|---|---|
| **no sync rule** | Script | **ModuleScript named `Main.local`**: the client would never run | ModuleScript |
| **one sync rule:** `{"pattern": "*.local.luau", "use": "clientScript", "suffix": ".local.luau"}` | Script, `ServerScriptService.Server.Main` | **LocalScript, `StarterPlayer.StarterPlayerScripts.Client.Main`** | ModuleScript |

- With the rule, all 137 files mapped and `rojo build` produced a 756 KB place.
- **What it settles:**
  - Rojo can produce the source manifest's expected classes for this layout, with one rule kept in the Project's
    metadata and no change to the game (#2405 §R2.8);
  - a place build exists for any later path that needs one.
- **Not verified here:** that the Rojo-built classes match what Studio's Script Sync assigns. S1 reads that back
  inside Studio. The middleware is `clientScript`, and `localScript` is refused as unparseable JSON.

## S5. The designer test, on paper

**The question:** can the specialty declaration and a squad profile describe the Iris design role (Capability-Backed
Agents §13: `design-system-application`, `ux-review`, `design-acceptance-authoring`) with no core change?

| what Iris needs | through the seam? |
|---|---|
| an identity on the roster | **yes:** a profile entry with its own role and `serves_roles`. The role needs an identity fragment (identity is a mandatory prompt layer), which the specialty's fragment directory ships |
| binding to an existing agent instead (§25c's acceptance test) | **yes:** `serves_roles` is a list, so an existing agent can also serve the design role |
| handlers for its work | **yes:** registered through the specialty table. The registry holds one handler per task type |
| design-system resource modules | **yes:** files in the specialty package, loaded into context by its handlers, like playbooks |
| no source writing; proposals only | **yes:** `TaskType` properties (`authors_source` false) keep its steps out of the footprint and patch path |
| **its own kinds of routed work** (apply a design system, review UX, author design acceptance criteria) | **no.** Routing is task type → handler → role → agent. These are new kinds of authored work, so they can't ride an operation id the way `game-dev-roblox`'s tool-backed work rides `qa.run_remote_operation`. They need task types of their own, which today means members of the central enum in a `design.` domain |
| Glyph's stewardship | out of the test: it's duty-shaped and deferred to 3.x (§25a) |

**Result: partial pass.** The seam carries everything except new kinds of authored work. That gap costs the
ordinary core change, new `TaskType` members with their properties and table rows under #559's rules, not plugin
machinery.

**What it changes in the plan:**
- **§2.2 narrows:** "a specialty adds operations, handlers, fragments, playbooks and resources without a core change;
  a specialty that adds a new kind of authored work adds its task types to the central enum, in its own domain".
- **The extraction trigger gains a case:** when a second specialty needs its own task types, the host-owned lookup
  the outside review described (properties, plan validation, routing, expected artifacts, correction mappings) is
  the first piece of plugin machinery to build.
- `game-dev-roblox` itself is unaffected, since its new work is tool-backed.

**Not determined on paper:** how the planners learn which task types they may plan. A designer's steps have to reach
the plan before the plan gate can check them. That's read in the code before revision 3.

## S6. A first Luau probe

The run plan went to the Spark session on 2026-11-08. It has three tasks at `f2113a6`, each prompted twice to the
`full` profile's dev model, a syntax check with pinned Lune, and the review rubric fixed before the run:
- T1: a shared pricing rule and its spec file;
- T2: a server bounty kind wired to a new Forge signal;
- T3: a client coach hint.

**The two large files were left out on purpose** (an item table and the UI controller, about 28 KB and 31 KB). So the
probe doesn't measure context selection, which the plan's full-path gate does. Findings, without the game's code,
come here when the outputs return.

## S4. The network path

- An unauthenticated `GET` from the MacBook to the Spark's runtime API over Tailscale (2026-11-08): `/health`
  answered 200 in 14 ms, `{"status":"healthy","service":"runtime-api","version":"2.6.1"}`, and `/health/infra`
  answered 200.
- **So a worker on the MacBook can connect outward to the runtime API with no port opened on the MacBook.**
- No credentials were used. The worker's service account is D3.

## The private copy (for S1 and phase 2g)

`backspring-labs/z_tower-ascension`, private, created 2026-11-08 on the owner's OK:
- **A single-commit snapshot** of the pinned commit without its history, with its own remote only. The real
  repository was read and never written: its `main` is unchanged at `f2113a6`.
- **The sweep** (plan §2.10):

  | found | in the copy |
  |---|---|
  | the Discord update-log workflow (posts merged PRs to the players' channel; the webhook is a repository secret) | **removed.** Secrets don't copy, and the copy has none |
  | two asset-upload scripts that publish to Roblox under the real account, with an Open Cloud key read from the machine | **removed** |
  | `HttpService` in the game's source | **kept:** its one use generates a GUID, with no network call |
  | the localhost Studio bridge (superseded prior art; localhost only) | **kept** |
  | the PR template's player-update section | **kept:** harmless without the workflow |

- A notice at the root says what the copy is and what was removed.
- **Still the owner's step:** the copy's Studio place. That means a local place file saved from the game, never the
  game's live place.
