---
name: luau-conventions
description: How a Roblox game's Luau files are written, so a new or changed file reads like its neighbours.
---

# Luau conventions

Write a file the way the files around it are written. When a convention below and the file
you are changing disagree, the file wins.

- **Requires by instance path, at the top of the file:** `local Rules = require(Shared.Modules.LivesRules)`
  or `require(script.Parent.PlayerDataService)`. Never a string path, which Roblox's `require` doesn't
  take.
- **A ModuleScript returns one table** of its functions: `local Rules = {}`, then
  `function Rules.Die(profile, floorId: number): boolean`, then `return Rules`.
- **Types on what crosses a boundary:** a public function's parameters and return values, and a
  remote's handler arguments. Locals don't need them.
- **Tuning values live in a config module** under `Shared/Config`, never as numbers in the logic, so
  a designer can change one without reading code.
- **String interpolation** uses backticks: `` warn(`[TA:Lives] Could not spawn {player.Name}`) ``.
  Use the file's own log prefix.
- **`+=` and `-=`** for counters, as Luau allows.
- **No globals.** Everything a file uses is a `local` or a require.
