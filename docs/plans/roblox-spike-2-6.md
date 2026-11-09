# The Roblox spike: Luau tests headless on Linux (2.6, #2895)

**Run:** 2026-11-04 on the Spark (arm64), in throwaway containers of the sandbox image
`squadops-sandbox-env:py3.12-node20-1.4` (image id `ab1206ff0b9b…`, Debian 13, glibc 2.41, has `curl`, `tar`,
`python3`; no `unzip`, no `git`). Decision D3 of `docs/plans/2-6-0-plan.md` (§2.6 Track F): the spike only, no box time.

**Verdict: yes, headless, with a hard boundary.** A Rojo-structured project's Luau tests run on Linux inside the
sandbox image from declared commands, with no Studio and no Roblox account, **when the code under test is pure Luau**
(game logic, state machines, scoring, data shaping). The runner is [Lune](https://github.com/lune-org/lune) 0.11.1
(arm64 build, pinned zip, digest-checked, unpacked by the image's own `python3 -m zipfile`), running either a
plain `require`-based runner script kept in the repository or the published `frktest` framework. The exit code
reflects failure and the output names the failing test. **What it cannot exercise is anything that reaches the
engine:** `game`, `script`, `workspace` and `Instance` are nil globals under Lune; Lune's `@lune/roblox` library
models the Instance tree (classes, properties, parenting, serialising `.rbxl`) but implements **no engine
behaviour** (no service methods, no physics, no events, no remotes, no `require` of a `ModuleScript` instance),
so a test touching those needs Studio (or a fake per method). So a Roblox game can be a repository-backed Project
in 2.6 for its logic modules, **once the derivation knows a Luau runner (gap 1 below): today its `*.spec.luau`
files raise a blocking `test_files_unclassed` gap and a Campaign is refused.** Engine-dependent verification is
#2405's remote worker, not 2.6.

## Runners for Luau outside Studio

| tool | version | arm64 Linux | install | single file | parseable output | notes |
|---|---|---|---|---|---|---|
| `luau` CLI (luau-lang/luau) | 0.745 | **no**: `luau-ubuntu.zip` is x86_64 only (ELF `e_machine 0x3e`, read from the binary) | release zip, sha256 `186e5dda…` | `luau <file>` | a script's prints only; no test framework | can't run on the Spark or the MacBook (both arm64; no amd64 emulation here: `exec format error`). `luau-analyze` same |
| **Lune** (lune-org/lune) | 0.11.1 | **yes** (`lune-0.11.1-linux-aarch64.zip`, sha256 `f8d7d633…`; binary `1b4f4f05…`) | release zip; GitHub's asset digest matched | `lune run <script> [args]`: args reach `process.args` | whatever the script prints; `process.exit(n)` sets the exit code (verified: 3, 1, 0) | ran in the image. `@lune/fs`, `@lune/process`, `@lune/task`, `@lune/net`, `@lune/roblox` |
| **Lute** (luau-lang/lute) | 1.0.0 | **yes** (`lute-linux-aarch64.zip`, sha256 `78638a20…`) | release zip | `lute <script>`; also `lute check` and `lute lint` (type checker: `path:5:30-34: (W0) TypeError: …`, exit 1) | as Lune | ran in the image; `@std/*`, `@lute/*`. No test command. A lint-check candidate |
| Zune (Scythe-Technology/zune) | 0.5.9 | yes (asset listed) | release zip | has a built-in test runner **(not verified: not run)** | — | frktest names it as a runtime |
| **frktest** (itsfrank/frktest) | 0.0.4 | runtime-agnostic (Lune, Lute, Zune) | tarball sha256 `f50ebc79…`; wally or pesde in a real project; `.luaurc` alias `@frktest` | one suite file per `lune run` | `Test: <name>` / `CHECK FAILED: <file>:<line>` for each failure, `Tests Ran: 2 \| Passed: 1 \| Failed: 1`, `status: FAIL`; exit via `process.exit` in the entry script | ran in the image (below). Passing tests are not listed by name. 14 stars, pushed 2025-09 |
| plain `require` runner (in the repository) | — | as its runtime | none | `lune run tests/run.luau tests/X.spec.luau` | `PASS\|FAIL <file> > <name>`, a `Tests:` summary; exit 1 on failure | the demonstration's runner, 50 lines |
| TestEZ (Roblox/testez) | — | n/a | — | — | — | archived 2024-03-05; Roblox-only (`script.Parent` requires) **(reading, not run)** |
| Jest-Lua (jsdotlua/jest-lua) | 3.10.0 | n/a | — | — | — | its README: "can currently only run inside of Roblox" |
| Rojo (rojo-rbx/rojo) | 7.7.1 | yes (sha256 `7190d4bc…`) | release zip | `rojo build default.project.json -o build.rbxl` ran headless | — | not a test runner: builds the place/model; `sourcemap` for luau-lsp |
| package managers | pesde 0.7.4 arm64 yes; wally 0.3.2 one `linux.zip` (arch **not verified**) | | | | | how a real project pulls frktest/TestEZ |

## The demonstration

A Rojo layout: `default.project.json` (`src` → `ReplicatedStorage.Shared`, `tests` → `ServerScriptService.Tests`),
`src/Scoreboard.luau` (`--!strict`, pure: `award` clamps at a cap, `leader`), `tests/Scoreboard.spec.luau` (two
tests, the second asserting the runner-up on purpose), `tests/run.luau` (the runner). One `docker run --rm` of the
sandbox image, cwd `/repo`, running what a Development Configuration would declare:

```
install: curl -fsSLo lune.zip https://github.com/lune-org/lune/releases/download/v0.11.1/lune-0.11.1-linux-aarch64.zip
         echo "f8d7d63384fad5edfaf5423b0ff1a1dbca9c44ec43beaa35c234b20a584aea66  lune.zip" | sha256sum -c   → OK
         python3 -m zipfile -e lune.zip .tools && chmod +x .tools/lune               (the image has no unzip)
check:   lune run tests/run.luau                         single file: lune run tests/run.luau tests/Scoreboard.spec.luau
PASS tests/Scoreboard.spec.luau > award clamps a player's total at the cap
FAIL tests/Scoreboard.spec.luau > leader is the highest scorer (fails on purpose: expects the runner-up)
  /repo/tests/Scoreboard.spec:15: expected ada, got bob
Tests: 1 passed, 1 failed, 0 errored, 2 total
exit=1                                                   (both invocations; rojo build → build.rbxl, 2410 bytes, exit 0)
```

The same module under frktest 0.0.4 (`check.equal(board:leader(), "ada")`) printed `CHECK FAILED: …:17  bob == ada`,
`Tests Ran: 2 | Passed: 1 | Failed: 1`, exit 1. Requires: Lune resolves `./`, `../` and `@alias` paths on the
filesystem relative to the requiring file (`require("../src/Scoreboard")` from `tests/` worked); it refuses an
absolute path. A relative alias in a package's own `.luaurc` (`"frktest": "src/"`) did not resolve when run from
another cwd, an absolute one did (cause not verified). The runner's `install` could equally be `pesde install`.

## What it can't exercise (the `@lune/roblox` probe, same container)

| worked | failed |
|---|---|
| `Instance.new("DataModel")`, `GetService("Workspace")`, `Instance.new("Part")`, `Parent`, `Position`, `GetFullName` | `Humanoid.Health` ("missing default value"), `Part:GetMass()`, `Players:GetPlayers()`, `RemoteEvent:FireAllClients()`, `Part.Touched:Connect` — each "not a valid member" |
| `roblox.implementMethod("Players", "GetPlayers", fn)`: a hand-written fake per method | `require(<ModuleScript instance>)` from a deserialised place: Lune's `require` takes a string only |
| `deserializePlace(build.rbxl)` and reading `Shared.Scoreboard.Source` (864 bytes) | the globals: `game`, `script`, `workspace`, `Instance` are all nil in a plain script |
| `@lune/task` (`task.wait(0.01)` → 0.010), `@lune/net` HTTP (not Roblox's `HttpService`) | replication, physics, rendering, `DataStoreService`, `Players` joining, any server/client split |

So **testable headless:** a module that takes data and returns data or mutates its own tables — controllers,
round/score/inventory logic, serialisation, pathing math on `Vector3`/`CFrame` (the datatypes exist). **Needs
Studio or a per-method fake:** anything that reads or drives the live DataModel. The engine's own `require` now
resolves `./` and `../` strings on the Instance tree (creator-docs `LuaGlobals.yaml`), so one source tree can run
in both, **only if the Rojo tree mirrors the directory layout** (`src` and `tests` as siblings under one parent); the
demo's layout does not, and the Studio side was not run. Roblox Open Cloud's Luau execution API may run engine code
without Studio: **not tried** (needs an account, a key and a published place).

## The implication for SquadOps, and the gaps to file

Gaps 1–4 are filed together as #2906, unplaced until the owner rules on D3's follow-up.

A Roblox game fits the Development Configuration shape battle-trainer uses: `install` (pinned Lune, or `pesde
install`), one check `[".tools/lune", "run", "tests/run.luau"]`, read whole or with the `lines` reader; the toolchain
reads as available because the install step provides it (`_toolchains` reads the baseline's own evidence, not the
image). What refuses it today is the derivation (`src/squadops/projects/profile_derivation.py`):

1. **A `luau` runner kind** (`_runner_of` returns `None` for `lune run …`; `RUNNERS` has no Luau). Any `*.spec.luau`
   matches `_TEST_LOOKING`, no runner owns it, and `test_files_unclassed` is **blocking** for Campaigns. The runner:
   roots from the script's directory, `file_pattern` `*.spec.luau`, `single_file_argv` `(*argv, "{path}")`, `covers`
   the Rojo `$path` sources; `Language("luau", pesde|wally|None)` from `default.project.json`/`pesde.toml`/`wally.toml`,
   which `_languages` doesn't read, so `no_test_runner` can't fire either.
2. **A test-id reader** in `squadops.sandbox.findings` for a declared Luau output format (`no_test_id_reader` until
   then, disclosed): either the plain runner's `FAIL <file> > <name>` + `Tests:` line, or frktest's console reporter
   (failures only, with the summary's counts). Which format is the product's choice to pin, like vitest 2's reporter.
3. **The worked example's language** (#2876's shape): `JAVASCRIPT_RUNNERS` chooses JavaScript or Python; a Luau
   product needs a Luau example or its proposer writes tests in the wrong language.
4. **`lute check`/`lute lint` as a lint tool** (`_LINT_TOOLS`, a findings reader for `path:l:c-c: (W0) Class: …`): small,
   optional; `lint_without_reader` is disclosed only.
5. **Engine-API verification** stays #2405's: a Studio or Open Cloud worker, outside this spike.

**Not verified:** the Studio side of string requires and the mirrored layout; Zune's test runner; wally's Linux
arch; the `.luaurc` relative-alias cause; Open Cloud execution; x86_64 behaviour of any tool (this box is arm64).
