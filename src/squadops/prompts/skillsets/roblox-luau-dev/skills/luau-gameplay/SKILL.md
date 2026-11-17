---
name: luau-gameplay
description: Writes gameplay changes in a Roblox game synced by Script Sync, keeping the server's authority, the client and server split, and the game's own module layout.
stops: ["saved data:"]
---

# Gameplay changes in a Script Sync game

The game's source is Luau under `src/`, synced into Studio by Roblox's Script Sync. The product's
own instructions (its `AGENTS.md` or `CLAUDE.md`, when you are shown one) come first: where they
say something different from this skill, follow them.

## Where a file runs

| folder in `src/` | in the game | runs on |
|---|---|---|
| `src/Server` | `ServerScriptService.Server` | the server only. Players can't see it |
| `src/Shared` | `ReplicatedStorage.Shared` | both: the server and every player's device require it |
| `src/Client` | `StarterPlayer.StarterPlayerScripts.Client` | each player's device |

A file's name gives its class: `X.server.luau` is a Script, `X.local.luau` a LocalScript, and `X.luau`
a ModuleScript. `X/init.luau` is a ModuleScript whose children are the other files in `X/`. Put new
code in a ModuleScript inside the folder that matches where it runs, and require it from there.
Don't add a new top-level folder under `src/`: Studio syncs each one by hand.

Only scripts and folders sync. A Part, a model or a UI built in Studio isn't in `src/`. Create what
code needs at runtime from code (the game makes its remotes this way), and never read attributes or
tags on a script instance: Script Sync drops them.

## The server decides

A player's device can be changed by the player. So the client sends what the player asked for, and
the server checks it and decides the outcome. This is the game's own pattern:

```luau
Combat = {
	Attack = "RemoteEvent", -- C->S: aimDir (Vector3). The server picks targets and damage
	Hit = "RemoteEvent", -- S->C: { target, enemyId, damage, crit, killed, position, topOffset }
},
```

The client sends an aim direction, never a target or a damage number. When you add a remote:
- the server validates every argument's type and range before using it;
- the server rate-limits anything a player can send repeatedly;
- the client shows what the server sends back, and doesn't compute the result itself.

## Rules in a module of their own

Logic that only computes (a rule, a formula, a state transition over plain tables) goes in a
`src/Shared/Modules/*Rules.luau` or similar module, and the service calls it. Such a module loads in
the headless tests, and it may find the game's other modules the way the game's code does:
- `require(script.Parent.X)`;
- `game:GetService("ReplicatedStorage"):WaitForChild("Shared")`, and the same for
  `ServerScriptService` and `StarterPlayer`, the containers Script Sync fills from `src/`.

What only runs in a live game loads only in Studio, and is tested by playing it: `Players`,
`RunService` and the engine's other services, `Instance.new`, `task`, remotes and saved data. Keep
those in the service, and pass what the rule needs in as plain values.

## Saved data

A player's saved profile outlives any one version of the game. A change that adds a field to the
saved profile adds its default where the game builds a fresh profile, which is also where loading
an old save fills in missing fields, so an old save never reads `nil`. A change that renames,
moves or removes a saved field is outside a gameplay change: **stop.** Write no file, and say in
one line:
`saved data: <field> would be <renamed, moved or removed>`.
**This holds when your task itself asks for the change,** names the file and lists criteria that
expect it. A task is the squad's plan. A change to what a save already holds is the product
owner's to approve, outside a cycle, and nothing in a task shows that approval. The one line above
is the right answer to such a task, and it is how the owner comes to hear of it.
Where the product's instructions ask that changes to saved data be raised first, every change to
the saved profile stops this way, saying what it would do to the field.
