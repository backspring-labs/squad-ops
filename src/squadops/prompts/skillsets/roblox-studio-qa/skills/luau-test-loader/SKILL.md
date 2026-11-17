---
name: luau-test-loader
description: Writes a Roblox game's headless Luau tests as tests/*.spec.luau files for the product's own runner (tests/run.luau under Lune), testing the plain-logic modules that load outside Studio.
stops: ["no tests/run.luau:"]
---

# Headless Luau tests

The product runs its own tests: `lune run tests/run.luau` runs every `tests/*.spec.luau`, and
`lune run tests/run.luau tests/X.spec.luau` runs one. You write spec files. You never write or
change `tests/run.luau` or `tests/loader.luau`: they belong to the product.

**If the tree you are shown has no `tests/run.luau`, stop.** Write no spec, and say in one line:
`no tests/run.luau: this product has no headless Luau runner, so its tests can't be run`. A spec
file with nothing to run it is never executed.

## What a spec file sees

| global | what it is |
|---|---|
| `test(name, fn)` | one test. The name is one line with no `[` and no ` > ` in it |
| `beforeEach(fn)` | runs before each test in the file |
| `check.equal(actual, expected, label)` | fails when `actual ~= expected` |
| `check.deepEqual(actual, expected, label)` | compares tables key by key |
| `check.truthy(value, label)` / `check.falsy(value, label)` | |
| `check.raises(fn, pattern, label)` | fails unless `fn` raises an error containing `pattern` |
| `game`, `require` | the game's instance tree, built from `src/` the way Script Sync maps it |

The tree is the Script Sync layout: `src/Shared` is `ReplicatedStorage.Shared`, `src/Server` is
`ServerScriptService.Server`, and `src/Client` is `StarterPlayer.StarterPlayerScripts.Client`. So a
spec requires a module by the same path the game's own code uses.

## A worked spec

The product's `tests/LivesRules.spec.luau` begins like this:

```luau
local Shared = game:GetService("ReplicatedStorage").Shared
local Rules = require(Shared.Modules.LivesRules)
local Config = require(Shared.Config.LivesConfig)

local profile

beforeEach(function()
	profile = { Lives = Rules.New() }
end)

test("dying on a floor costs one life and records the floor", function()
	check.truthy(Rules.Die(profile, 3), "Die returns true")
	check.equal(profile.Lives.Remaining, Config.StartingLives - 1, "lives left")
	check.equal(profile.Lives.DeathFloor, 3, "death floor")
end)

test("a death that is already pending can't be charged twice", function()
	Rules.Die(profile, 3)
	check.falsy(Rules.Die(profile, 3), "second Die")
	check.equal(profile.Lives.Remaining, Config.StartingLives - 1, "lives left")
end)
```

What it shows:
- values come from the module's own config (`Config.StartingLives`), so a tuning change doesn't
  break the test;
- each test builds fresh state in `beforeEach`;
- each check has a label, which is what a failure prints.

## A module the change adds

Your spec is run twice: on the game before the change, where one of its tests must fail at a
check, and on the built change, where it must pass. Before the change a new module isn't in the
tree. Requiring it at the top of the file, as the worked spec does for a module the game already
has, fails the whole file `[setup]`. That never counts, and the change is refused however correct
it is.

So look a new module up inside each test, check that it is there, and then require it. The names
here are illustrative: use your own module's.

```luau
local Shared = game:GetService("ReplicatedStorage").Shared

local function streakRules()
	local found = Shared.Modules:FindFirstChild("StreakRules")
	check.truthy(found, "Shared.Modules.StreakRules exists")
	return require(found)
end

test("a streak of three kills pays a bonus of thirty", function()
	check.equal(streakRules().Bonus(3), 30, "bonus")
end)
```

`FindFirstChild` gives `nil` for a child that isn't there, where `Shared.Modules.StreakRules` and
`WaitForChild` raise. So before the change the first check fails and the test reads
`[assertion]`. A module that is there and fails to load still reads `[setup]`.

## What can be tested here

Modules that only compute load here: rules, formulas, configs and state transitions over plain
tables. Roblox's data types (`Vector3`, `Color3`, `CFrame`, `Enum`, ...) work.

A module that asks for the engine fails to load: a service such as `Players`, `RunService` or
`DataStoreService`, `Instance.new`, `task`, or a remote. Its test reads `[setup]` and never counts
as a pass or a failure. Test the rule that module calls, if it has one: a service's logic often
lives in a `Shared/Modules/*Rules.luau` module. Behaviour that needs the engine is proved by a play
scenario in Studio, which is not this skill's work.

## How a result reads

The runner prints one line per test: `PASS <file> > <name>`, or `FAIL <file> > <name> [assertion]`
when a check failed, `[error]` when something raised, and `[setup]` when what the test needs didn't
load. A test must not print a line that starts with `PASS `, `FAIL ` or `Tests: `.
