---
name: play-scenario-authoring
description: Writes a Roblox game's player-facing criterion as a play scenario the Studio harness runs, in the squadops.scenario/1 form roblox-studio/1 reads, and says what a change does to a player's saved state.
---

# Play scenarios for a Roblox game

A criterion a player sees in a play session is a `scenario` criterion. Its scenario is played on the
game in Studio, before development and again on the change, and its records decide the criterion:
- **before development, on today's game:** its named assertion must run and fail, and every other
  assertion must pass. A named assertion that already passes proves nothing about the change, and a
  precondition that fails leaves the named one meaning nothing, so either sets the increment aside;
- **on the change:** every assertion must pass.

The scenario is frozen when the change request is approved. You write it once, here.

**If the criterion's effect is one `roblox-studio/1` can't observe, stop.** That covers a sound, a
particle effect, an animation, a colour or anything only seen in a picture, two players at once, and
a purchase prompt. Write no change request, and say in one line:
`no scenario: <criterion> shows itself as <effect>, which roblox-studio/1 can't observe`.
A scenario that can't read its effect would pass or fail on something else.

## The criterion in `change_request.yaml`

```yaml
criteria:
  - id: S1
    statement: The HUD's energy label reads "50 / 50"
    surface_kind: scenario
    surface: "@player.PlayerGui.TA_HUD.EnergyLabel"   # the path the named assertion observes
    observable: "after Play, the HUD's EnergyLabel's text is exactly 50 / 50"
    scenario:
      schema: squadops.scenario/1
      scenario_id: S1                                 # the criterion's id
      reader: roblox-studio/1
      setup:                                          # the world the steps start in
        - action: wait_until
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_Title.Content.Column.Play", state: visible, context: client}
          expect: {op: equals, value: true}
          deadline_s: 20
        - action: click_gui
          path: "@player.PlayerGui.TA_Title.Content.Column.Play"
        - action: wait_until
          observe: {kind: property, path: "@player.PlayerGui.TA_Title", name: Name, context: client}
          expect: {op: absent}
          deadline_s: 10
      steps:                                          # what the player does
        - action: hold_key
          key: W
          seconds: 1
      assertions:                                     # what the player then sees
        - id: hud-shown
          observe: {kind: property, path: "@player.PlayerGui.TA_HUD", name: Enabled, context: client}
          expect: {op: equals, value: true}
        - id: energy-full
          observe: {kind: attribute, path: "@player", name: Energy, context: server}
          expect: {op: equals, value: 50}
        - id: energy-text
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_HUD.EnergyLabel", state: text, context: client}
          expect: {op: equals, value: "50 / 50"}
      named_assertion: energy-text                    # the one the criterion is about
```

The setup is this game's own title screen: it opens on `TA_Title`, and pressing Play removes it and
shows `TA_HUD`, with the player's `Energy` at 50 on the server. On today's game `hud-shown` and
`energy-full` pass, and `energy-text` fails, because the `EnergyLabel` the example change adds
isn't there yet. `equals` holds the text to exactly what the criterion promises, where `contains`
would also accept `150 / 500`.

This criterion is about the label's text, and reading text doesn't check that the label is shown.
That the player sees it is a criterion of its own, beside this one in the same change request, whose
named assertion is the label's visibility:

```yaml
        - id: energy-label-shown
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_HUD.EnergyLabel", state: visible, context: client}
          expect: {op: equals, value: true}
```

Visibility can't be a precondition of the text criterion instead. On today's game the label isn't
there, so the precondition would fail and set the increment aside. Its `surface` is the named assertion's path, and its `scenario_id` is the
criterion's `id`. A scenario that breaks either is refused.

## What `roblox-studio/1` reads

**Paths** are instance paths joined by `.`. Each starts at a service (`Workspace`,
`ReplicatedStorage`, …) or at `@player`, the one player of the play session. A name holding a `.`
can't be addressed. Never name a person's account: `@player` stands for whoever plays.

| action | arguments | what it does |
|---|---|---|
| `wait_until` | `observe`, `expect`, `deadline_s` | waits for an observation to meet an expectation. In setup, one that times out means the world wasn't established, and nothing is asserted. In steps, the scenario goes on |
| `click_gui` | `path` | clicks a visible GUI object with the mouse |
| `hold_key` | `key` (a `KeyCode` name, such as `W`), `seconds` | holds a key down |
| `move_to` | `point` (`[x, y, z]`), `deadline_s` | walks the character to within a stud of a point |

| observation | arguments | reads |
|---|---|---|
| `property` | `path`, `name` | a property's value: a number, text or boolean as it is, anything else as its text |
| `attribute` | `path`, `name` | an attribute's value, the same way |
| `gui_state` | `path`, `state` | `visible` (shown on screen, with every ancestor visible and its screen enabled) or `text` |
| `value` | `path` | a `ValueBase`'s `Value` |

Every observation names its `context`: `client` for what the player's device shows (anything under
`@player.PlayerGui`), and `server` for the server's state (an attribute the server keeps on
`@player`, a part in `Workspace`).

An instance that isn't there observes absent: it meets `{op: absent}` and `not_equals`, and fails
every other `op`. So expect the value the effect has, with `equals`, `greater_than`, `less_than` or
`contains`, which a missing instance fails. A `not_equals` passes wherever the thing is missing:
- **on today's game,** for something the change adds, so it can't be the named assertion there;
- **on the change,** for something the change deleted. A button's `Active` `not_equals false` fails
  correctly today, then passes if development removes the button.

So when only `not_equals` says it, add an assertion that the thing is there (`{kind: gui_state,
state: visible}` with `equals: true`, or a property it always has), which passes on both. Leave that
out only when the effect is the thing's absence, and then say it with `{op: absent}`. A path that
doesn't start at a service or `@player` can't be read at all, and its assertion reads as not run.

An `expect` is `{op, value}`, with `op` one of `equals`, `not_equals`, `greater_than`, `less_than`
or `contains`, or `{op: absent}`, which takes no value. A deadline is at most 60 seconds. A
scenario has at most 8 setup actions, 32 steps and 16 assertions. `scenario_vocabulary.json`, beside
this skill, is the reader's own declaration of all of this.

## Writing one

- **Observe the effect the criterion names, as the player meets it.** For "the bonus adds 10
  coins", read the player's `Coins` after the claim, not the configured bonus amount: a value the
  change itself sets passes whether or not the game uses it.
- **Every action runs on today's game too.** The scenario is played there before development, so
  each setup action and step must be doable on the game as it is: click only what exists today. An
  action that can't be done stops the play, every assertion reads as not run, and the increment is
  held, never judged. So a change that adds a button is checked by observing the button. What
  pressing it does is a later increment's criterion, once the button exists.
- **The named assertion fails on today's game, and the rest pass.** The named one reads something the
  change brings about. The others are its preconditions, such as the HUD being up and the player's
  energy at its start, which hold today and after the change.
- **Setup establishes; steps act.** Put getting past the title screen and any waiting for the world
  in setup. Put what the criterion's player does in steps.
- **Wait for what you then read.** After a step whose effect takes time, add a `wait_until` on it
  before the assertions.

## Saved state

A player's saved progress outlives any one version of the game. When the change adds to, removes
from or reorders anything saved progress points at (a list saved by index, a seeded set for the
period, an item id), say in the change's `prd_delta` text what an existing player's save holds after
the change. A new bounty kind that reshuffles the period's seeded set is the case this exists for:
saved progress restored by index then points at different bounties.
