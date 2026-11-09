# game-dev-roblox spikes — phase 0 of `docs/plans/game-dev-roblox-plan.md`

**Status: DONE, 2026-11-08** (started on the owner's "you are good to start"). The record ends at the plan's gate
(§3a): go, narrow or stop. **It holds no game source.** The game's repository is private, so findings describe
patterns and outcomes, and the raw model outputs of S6 stay out of this repository.

| spike | status |
|---|---|
| S1. the Studio transaction | **done:** play, input and read-back proven on a local copy of the game; both checks are cheap enough to run in full; reconnecting after a Studio restart needs a person (findings below) |
| S2. Rojo and Script Sync | **done:** a Rojo build reads the Script Sync layout correctly with one sync rule kept in Project metadata; the game's modules need a loader to run under Lune |
| S4. the network path | **done:** the MacBook reaches the Spark's runtime API outward over Tailscale |
| S5. the designer test | **done:** partial pass, with one finding that narrows the plan's §2.2 (below) |
| S6. a first Luau probe | **done:** six of six samples correct in their Luau and Roblox API use. One context-induced logic error (shared by both samples of one task), tests that run nowhere as delivered, and the output format broken on the largest task (findings below) |

## S1. The Studio transaction

Run 2026-11-08 on the MacBook, against Roblox Studio's built-in MCP server through its stdio proxy
(`RobloxStudio.app/Contents/MacOS/StudioMCP`), driven by a throwaway JSON-RPC client. Everything touched the local
copy and `z_tower-ascension` only.

**The setup:**
- **The place is a local file,** downloaded from the game with File → Download a Copy and opened from disk. A
  read-only copy of it is the reset baseline.
- **It is disconnected:** `game.PlaceId`, `GameId` and `CreatorId` read 0 inside Studio. The game's own startup
  reports that saving is off without DataStore access, so a play session can't write save data.
- **No test universe was needed.** The plan assumed one (§2.6, §2.10); a local file with PlaceId 0 serves.
- **Before every run, the client refuses unless exactly one Studio is connected and it is the copy.**

**Linking Script Sync (the owner's step):**
- **Sync to… creates a folder named after the instance inside the folder chosen.** Each of the three folders is
  linked to `src` itself, which yields `src/Server`, `src/Shared` and `src/Client`. Choosing `src/Server` yields
  `src/Server/Server`. Two wrong attempts wrote Studio's scripts into nested folders; they were moved out with the
  links stopped, and Studio kept all 137 scripts.
- **The game was ahead of its repository:** 132 of 137 scripts matched the repository's `main` (`f2113a6`), and 5
  carried newer work that wasn't in git. The copy's repository took the game's versions as one local commit, so disk
  and the place agree. The real repository was not touched.

**The tools:**
- **38 tools.** Some write to Roblox's servers: `open_cloud_invoke`, `upload_image`, `insert_asset`, `create_skill`
  and the `generate_*` family. §2.6's deny-by-default allow-list has to name them. S1 called none.
- **`execute_luau` takes a required `datamodel_type`** (`Edit`, or `Server` / `Client` during play).
- **A result is capped at 100,000 characters** and ends `... (truncated)` while reporting success. A reader must
  page and refuse a truncated page.
- **A blocking call has no timeout.** `ContentProvider:PreloadAsync` hung the tool twice. Studio stayed responsive,
  and a fresh connection could stop play. **So the worker sets a deadline on every call, and the harness never makes
  an unbounded blocking call.**
- **`_G` persists between `execute_luau` calls,** so the harness clears its own state and never relies on it.
- **The proxy needed about five seconds to see Studio,** and **a restarted Studio has a new id and briefly no name.**
  The worker re-resolves and checks identity by PlaceId 0 and the content digest, not by id or name.

**Script Sync** (times are from the disk write to Studio showing it):

| case | result |
|---|---|
| edit, and its revert | 1.1 s and 0.7 s |
| create a module; create in a new folder (a `Folder` appears) | 0.9 s; 0.7 s |
| rename (a new instance, the old one removed) | 0.7 s |
| delete a file; delete a folder | 0.7 s each |
| classes | `.server.luau` → `Script`, `.local.luau` → `LocalScript`, else `ModuleScript`. This matches S2's Rojo rule |
| **an edit made in Studio** (`Source` assignment or `ScriptEditorService`) | **reaches disk in 0.6 s** |
| conflict: the link stopped on one folder, then the same script changed differently on each side, a script added only on disk and one only in Studio, and the link restored | **a dialog lists the changes from Studio's side** (modify 1, add the Studio-only script, delete the disk-only one). **Keep Disk Version** made Studio equal disk and the link live again in 0.9 s |
| **a Studio restart** | **the links are gone** for a local file. Disk edits stop reaching Studio until a person links the three folders again |

- **Because sync runs both ways,** any script change made in Studio lands in the repository. The worker reads `git
  status` after every operation, and a change it didn't make is §2.6's unexplained mutation.
- **The restart case** means a person re-links after every Studio restart. The worker can detect it (a disk edit
  that read-back doesn't confirm reads `not_executed`), but it can't repair it. **An option for revision 3:** the
  adapter syncs by itself. `execute_luau` can create a script of the right class and set its source, and the
  read-back confirms it. That needs no Script Sync link, so it survives a restart.

**Read-back and the baseline** (§2.6's two checks, measured on the whole place):

| check | cost per run | result |
|---|---|---|
| **every synced script read back through Studio** (137 scripts, about 1.7 MB) | **1.6 s**, 23 pages | equal to the disk digest, 137 of 137 exact |
| **the non-script baseline** (22,840 instances outside the three script folders, about 4.8 MB of records) | **7.0 s**, 55 pages | the same digest on repeated runs; a part moved 0.01 studs changed it, and restoring the part restored it |

- **So neither check needs the scoped fallback.**
- **The baseline covers a fixed property set per kind:**
  - parts: position and rotation, size, colour, material, transparency, anchoring and collision, mesh and texture;
  - values, sounds, decals, lights and UI objects;
  - every instance's attributes and tags.

  It isn't every property, and revision 3 states the set.

**Play, input and reset:**
- **A play session runs unattended,** including with Studio behind other windows: start 2.9 s, stop 1.3 s. In the
  background, the game ran at full rate (120 ticks in 2 s) and drew at about 15 frames a second.
- **Server and client are each scriptable** during play, and the console is readable.
- **Input works:**

  | input | effect, measured in the client |
  |---|---|
  | a mouse click on the title screen's Play button, by instance path | the title screen closed |
  | holding W for 1.5 s | the character walked 24.5 studs |
  | `character_navigation` to a point 21 studs away | it arrived within 0.7 studs |
  | pressing the game's map key | the map opened |

- **The game opens on a title screen,** so every scenario's setup passes it first. That goes in the play-scenario
  playbook.
- **The assertion channel:** a structured line printed by the server came back through the console with its nonce.
- **Reset:** a part created during play was gone after stop, and the edit place was unchanged.
- **Assets load:**
  - all 137 sounds decoded on the client;
  - the meshes render in captures;
  - `PreloadAsync` reported most ids as failed in this context and is not a usable probe.
- **Interruption:** after the hung call, Studio stayed in play, and a new connection stopped it cleanly.

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
- **The Rojo-built classes match what Studio's Script Sync assigns** (S1). The middleware is `clientScript`, and
  `localScript` is refused as unparseable JSON.

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

**Label: "S6 first probe — not a quality rate, no context selection measured."** The Spark session ran it on
2026-11-08, 14:20–14:31Z, with no cycle or Campaign active, after the owner confirmed in that session.

**The tasks,** at `f2113a6`, each prompted twice:
- T1: a shared pricing rule and its spec file;
- T2: a server bounty kind wired to a new Forge signal;
- T3: a client coach hint.

The two largest files (about 28 KB and 31 KB) were left out on purpose.

- **Engine and model, as the squad reaches them:**
  - TensorFold `squadops-tensorfold:0.6.6-cb2ebf05`, recipe `qwen27b-nvfp4`;
  - served id `qwen3.8-27b-tf-nvfp4`;
  - checkpoint `nvidia/Qwen3.8-27B-NVFP4@482ca0f3`, drafter `z-lab/Qwen3.8-27B-DFlash2@50307d4c`.

  The run plan's "`qwen3.6:27b` on Ollama" was wrong: the deploy serves `full` from TensorFold, and Ollama is
  stopped.
- **Options:** sent through the deployed TensorFold adapter inside neo's container, as a `development.develop` call:
  temperature 1.0, top_p 0.95, top_k 20, min_p 0, thinking on at medium effort, max_tokens 14,336.
  - The deployed profile (`full-38-tf`) caps neo at 12,288 completion tokens.
  - No sample reached the cap (the largest was 11,382), so the difference changed no output.

| sample | prompt / completion / reasoning tokens | tok/s | wall time | format |
|---|---|---|---|---|
| T1-1 | 2,470 / 10,849 / 7,659 | 65.3 | 167 s | as asked |
| T1-2 | 2,470 / 11,382 / 7,753 | 71.0 | 160 s | as asked |
| T2-1 | 6,250 / 6,760 / 931 | 129.9 | 54 s | **no parseable block:** no fences; files separated by bare `-- path:` lines |
| T2-2 | 6,250 / 7,266 / 1,319 | 116.2 | 63 s | **no parseable block:** `-- path:` placed before each fence, not inside it |
| T3-1 | 7,926 / 7,208 / 3,391 | 75.9 | 98 s | as asked |
| T3-2 | 7,926 / 9,050 / 5,107 | 74.3 | 122 s | as asked |

- **Compile check:** Lune 0.11.1 (digest-checked), in the sandbox image with no network, a read-only filesystem and
  no capabilities. All 14 files compile: T1's six, T3's two, and T2's six from a lenient extraction made only for
  this check. The strict reading of T2 stands as a format failure.
- **Not executed:** T1's spec (it needs the S2 loader) and anything engine-coupled.
- **Already a finding:**
  - both samples of the largest multi-file task broke the stated output contract, each in a different way, while
    the single-file and small tasks kept it;
  - an emission parser for this specialty can't assume the fence contract holds on a three-file change.
- **The review** (on the MacBook, against the rubric fixed before the run). The outputs came by message, not ssh,
  and all ten digests matched what the Spark holds.
  - **Exactness:**
    - every code file the model returned was rebuilt here from the original plus only the task's change, and its
      digest matched;
    - so across six samples, the only change beyond the task is one header comment updated to match (T2-1).

  | | T1 (shared rule + test) | T2 (server, across services) | T3 (client hint) |
  |---|---|---|---|
  | complete | both | both | both |
  | follows the file's conventions | both | both | both |
  | Roblox API errors | none | none | none |
  | logic errors | none | none in the change | **both samples, the same one** (below) |
  | output format | kept | **broken in both,** two different ways | kept |
  | unrequested changes | none | one comment (T2-1) | none |

  - **The logic error is context, not reasoning.**
    - T3 computes free bag slots from the saved capacity and counts every item. The game's own helpers add the
      boss-floor bonus slots and skip equipped gear, and the client's inventory and shop screens already use them.
    - The helper's module wasn't in the task's context, so both samples reinvented the rule wrongly. This is the
      failure the plan's full-path gate exists to measure: context selection, on a 1.7 MB tree.
  - **Server wiring was right.**
    - T2 added a signal through the game's own Signal module, fired it only on success, hooked it into the bounty
      flow and left saved data's shape alone.
    - The new dependency between the two services creates no require cycle.
    - Neither sample named the deploy-time edge a reviewer would: a new kind reshuffles the current period's seeded
      set, so a board saved before a deploy restores its progress onto different bounties.
  - **The tests run nowhere as delivered.**
    - T1-1 wrote a Studio-side script in `tests/`, a folder Script Sync never syncs into Studio.
    - T1-2 wrote its own instance-to-file loader (the S2 idea), but in Lua 5.x (`io.open`, the four-argument
      `load`), neither of which exists in Luau, and with an instance map missing seven modules the code under test
      requires. By reading; not run.
    - In both, the "never below 1 gold" case can't fail with the configured discount.
  - **The output format held on single-file and small changes and broke on the three-file change,** in both samples:
    - T2-1 used no fences at all;
    - T2-2 put the path line before each fence instead of inside it.
  - **Cost:** 54–167 s per sample; T1 spent about 7,700 reasoning tokens on a small task.
- **What it tells the playbooks** (an input to phase 2f, not a rate):
  1. **ship the loader and the test convention** as tooling (where tests live, which runner, how a module loads
     under Lune), rather than leave each task to write one;
  2. **give each task the module that owns its concept** (here, the item helpers for bag space). The code map is
     the starting point, and the full-path gate measures whether it's enough;
  3. **the emission parser can't rely on the fence contract** for multi-file changes: parse the two shapes seen
     here, or ask for one file per block and repair;
  4. **ask for deploy-time effects on saved state** in server changes.
- **For the gate:** the model's Luau and Roblox API use was right in every sample. The risks it shows are context
  selection, test tooling and output format, all of them things the specialty provides. Six samples give no rate.

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
- **The copy's Studio place** (the owner's step, done 2026-11-08) is a local file downloaded from the game, and never
  the live place (S1). The copy's repository gained one local commit taking the game's 5 newer scripts.

## The gate (§3a): go, accepted by the owner with D1–D10 on 2026-11-08

**S1 proves play, input and read-back, so the claim stands as written (§1).** Both of §2.6's checks run in full
inside a run's budget (1.6 s and 7.0 s), so the scoped fallback isn't needed and nothing narrows.

**What revision 3 takes from the spikes:**

| from | change |
|---|---|
| S1 | **the product is a local place file, not a test universe** (§2.10, D2). PlaceId 0, saving off, reset from a read-only baseline file |
| S1 | **the sync path is a decision for the owner (D10 below):** Script Sync needs a person after every Studio restart |
| S1 | the allow-list names the tools that write to Roblox's servers; every call has a deadline; results are paged and a truncated page is refused; the harness clears `_G`; identity is checked by PlaceId and digest, not by Studio id |
| S1 | the baseline's property set is stated; the play-scenario playbook passes the title screen first |
| S2 | the Rojo rule for `.local.luau`; the Lune loader for instance-tree requires |
| S5 | §2.2 narrows: new kinds of authored work need central task types |
| S6 | the specialty ships the test loader and a convention for where tests live; each task's context includes the module that owns its concept; the emission parser tolerates the two broken formats; change requests ask for effects on saved state at deploy |

**D10 (new), the sync path for the worker:**
- **Script Sync,** as the plan has it now. Proven, but its links are lost on every Studio restart, so the worker
  stops at `not_executed` until a person re-links three folders.
- **Adapter-owned sync:** the adapter writes the manifest's scripts into Studio through `execute_luau` (the right
  class and source per script), with no Script Sync link, then reads back as now. It survives a restart. Studio edits
  no longer flow to disk on their own, so returned Studio edits (§2.6) are read back and returned by the adapter as
  files.
- **Recommendation: adapter-owned sync for the worker's Studio.** The plan's runs are unattended, and the read-back
  that confirms the tested state is already the adapter's. Script Sync stays the game owners' own workflow.
