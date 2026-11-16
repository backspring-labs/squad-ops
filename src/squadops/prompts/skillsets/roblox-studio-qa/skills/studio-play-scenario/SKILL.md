---
name: studio-play-scenario
description: Plays a frozen squadops.scenario/1 scenario on a Roblox game in Studio through the worker's roblox-studio provider, and reads one record per declared assertion, keeping what ran apart from what didn't.
---

# Playing a scenario in Studio

A scenario criterion's play is the framework's step, not a task anyone writes. It is appended once
per scenario criterion, and runs `play_scenario` on the `roblox-studio` worker. That is the Mac
holding Studio open on the place, with the candidate's scripts synced in. The scenario is the one
frozen when the change request was approved, read by `roblox-studio/1`. Its declaration is
`scenario_vocabulary.json`, beside this skill.

## What a play returns

One record per declared assertion, each with what it observed, what it expected and the context it
read in:

| outcome | ran | means |
|---|---|---|
| `passed` | yes | the observation met its expectation |
| `failed` | yes | it didn't: the game behaves otherwise |
| `setup_failed` | no | the world the steps start in wasn't established, or a step couldn't be done, so nothing was asserted |
| `missing` | no | the path couldn't be read, such as one that starts at neither a service nor `@player` |
| `unsupported_input` | no | the observation isn't one the reader takes on that instance, such as `text` on a frame |
| `wrong_context` | no | it ran somewhere other than the context it names |

Only `passed` and `failed` ran. A record that didn't run is never a failure of the game, and never a
pass. Report it as not executed, with its reason.

The play as a whole can also end without records:
- `not_executed` means nothing was played. Examples: Studio isn't the version the worker was proved
  on, the place isn't its pinned baseline, or another app is in front for a scenario that clicks;
- `interrupted` means it was cut off once play had begun, so whatever ran is unknown.

Each completed play names the source revision it played and the scenario's digest. So a record
belongs to one candidate and one frozen scenario, and to no other.
