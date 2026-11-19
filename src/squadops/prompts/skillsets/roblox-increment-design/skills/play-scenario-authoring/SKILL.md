---
name: play-scenario-authoring
description: Writes a Roblox game's player-facing criterion as a play scenario the Studio harness runs, in the squadops.scenario/1 form roblox-studio/1 reads, and says what a change does to a player's saved state.
stops: ["no scenario:"]
---

# Play scenarios for a Roblox game

A criterion a player sees in a play session is a `scenario` criterion. Its scenario is played on the
game in Studio, before development and again on the change, and its records decide the criterion:
- **before development, on today's game:** its named assertion must run and fail, and every other
  assertion must pass. A named assertion that already passes proves nothing about the change, and a
  precondition that fails leaves the named one meaning nothing, so either sets the increment aside;
- **on the change:** every assertion must pass.

The scenario is frozen when the change request is approved. You write it once, here.

**A play scenario is not one of Outcome Evaluation's scenarios.** The product may disclose a gap
named `no_start_declaration`, which says "Outcome Evaluation reads every scenario
blocked_unverified". That is another check, of an application that is started and called. It says
nothing of a play scenario: the worker plays yours in Studio whatever that gap says. So a
criterion a player sees is a `scenario` criterion on this product too. A formatter or a list that
a `package` criterion proves is not what the player sees.

**If the criterion's effect is one `roblox-studio/1` can't observe, stop.** That covers a sound, a
particle effect, an animation, a colour or anything only seen in a picture, two players at once, and
a purchase prompt. Write no change request, and say in one line:
`no scenario: <criterion> shows itself as <effect>, which roblox-studio/1 can't observe`.
A scenario that can't read its effect would pass or fail on something else.

**A `package` criterion is no way round that.** A headless test loads only modules that compute.
A module that creates a Sound, an instance or an effect doesn't load there, so its test never runs
and the increment is refused after it is built. A rule beside the effect can be tested (whether
the chime should play), and it proves the rule: nobody has checked that a player hears anything.
So where the effect a player gets is the whole of what was asked, stop as above, however small a
part of it a test could reach.

**A state no action reaches is another case, and there a `package` criterion is the answer.** The
effect is one the reader observes (a text, something shown or hidden), but part of what was asked
holds only in a state the four actions can't bring about: low health, a later level, another place.
Then play the half a scenario reaches, prove the rest headless on a module that only computes, and
say what no play reached. Rule 6 below shows it. A weaker played check never stands in for the
half that can't be played.

## The criterion in `change_request.yaml`

```yaml
criteria:
  - id: S1
    statement: The HUD's energy label reads "50 / 50"
    surface_kind: scenario
    surface: "@player.PlayerGui.TA_HUD.EnergyLabel"   # the path the named assertion observes
    observable: >-
      Played. After Play, the HUD's EnergyLabel's text is exactly "50 / 50".
      Reads: "The HUD shows the player's energy as 50 / 50."
      Fails on: a label with no text, and one reading "50" alone.
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
would also accept `150 / 500`. `Reads:` quotes the sentence of the item this criterion reads
(rule 1).

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

## Six rules, each with an example

The examples are about two changes this game doesn't have: a shield label that counts down, and a
low-health warning. Yours is another change. Take the shape, never the values.

### 1. Coverage: every sentence of the item is read by some criterion

**The item is the objective in your request, word for word.** Before you write anything else, copy
its sentences out, and work from that copy to the end. Each sentence is read by a criterion of
yours, whose `observable` quotes it after `Reads:`. A sentence that a criterion an earlier
increment froze already reads is covered there.

**A criterion reads a sentence when its check fails on a build where that sentence is false.**
For each sentence, name that build, and find the criterion that fails on it.

> A low-health warning shows on the HUD while the player's health is under 25. It is hidden
> otherwise.

| the item's sentence, word for word | a build where it is false | read by |
|---|---|---|
| "A low-health warning shows on the HUD while the player's health is under 25." | a warning that never shows | `P1`, headless: no action lowers the player's health |
| "It is hidden otherwise." | a warning that always shows | `S3`, played: at full health the warning is there and not visible |

A change request holding only `S3` passes on a warning that never shows.

**Your `prd_delta` carries every sentence you copied.** A `prd_delta` saying only "the HUD has a
low-health warning, hidden at full health" has lost the item's first sentence. The criteria then
cover that shorter text completely, and the proposal is returned for the half left out. Your
request says to leave out of `prd_delta` what nothing else in it delivers. That is for something
you thought of adding. A sentence of the item is delivered: by a played criterion, or by a
headless one where no play reaches its state (rule 6).

### 2. Reachability: name only what today's game sets, or your footprint adds

Every setup action, wait and observation names something the product's map or instructions show
the game setting today, or something a file in your `footprint` adds. A wait on anything else never
comes true. In setup that holds the increment. In steps the wait times out, the scenario goes on,
and the assertions read a world the wait never reached, so correct work fails.

```yaml
# Wrong: nothing in the game sets a Zone attribute, and no action walks to the arena.
- action: wait_until
  observe: {kind: attribute, path: "@player", name: Zone, context: server}
  expect: {op: equals, value: Arena}
  deadline_s: 30
```

Where no action reaches the state, don't play it: prove its rule headless (rule 6).

### 3. The broken build: the named check fails on broken work, and passes on correct work

Before you write the named assertion, name two wrong builds of the change:
- **the obvious broken one:** the text written once and never updated, the warning that never
  hides, the counter that never moves;
- **a partial one:** half of what was asked, such as the right number with its words missing.

The named assertion fails on both, and on today's game. It passes on every correct build, whatever
start point or timing the item leaves open. For "the shield label counts down from `Shield in 30 s`":

| a named check | what is wrong with it |
|---|---|
| `contains "Shield in"` | passes on a label stuck at its first text: it reads the format only |
| `not_equals "Shield in 30 s"` | passes on any other text, and where the label is missing |
| `equals "Shield in 15 s"` | fails on correct work: that text holds for one second |
| an attribute `ShieldSeconds` `less_than 30` | passes with no label at all: the player reads the text, not a counter |

### 4. Timing: a band, from a start the criterion states, with margin on both edges

Read a value that changes each second as a band: a part of its text that stays the same for
several seconds (a tens digit), never one that changes every second. State where the count starts,
wait for the band, then read it.

**Read the first band a stuck value can't show.** For a value that moves each second, that band
opens about 10 s after the count starts. It already shows everything a played check can: the
text's format (its separators, and each digit in its place) and that the value moved. A later
band shows nothing more, and costs the wait its margin.

**The band opens early in one wait.** A wait's deadline is at most 60 s, and its time runs from
the moment its own step starts. Setup has finished by then, so none of setup's time comes off the
wait. Choose a band that opens within 30 s of the count's start, and give the wait at least 10 s
more than the band needs to open:

| the band opens | the wait allows | |
|---|---|---|
| 11 s after the count starts | 25 s | sound: 14 s to spare |
| 50 s after | 60 s | fragile: a count that starts 10 s late fails correct work |
| 60 s after | 60 s | fails on correct work: the band opens as the wait ends |

So never wait for what only shows a minute in, such as a digit rolling over or a rate measured
over a minute. An example value in the item ("such as 4:10") shows the format: it is never a time
to wait for. Where the item gives a later value a sentence of its own, no wait reaches it, and
its rule is proved headless (rule 6).

```yaml
criteria:
  - id: S2
    statement: The HUD's shield label counts down by one each second from "Shield in 30 s", starting when the HUD shows
    surface_kind: scenario
    surface: "@player.PlayerGui.TA_HUD.ShieldLabel"
    observable: >-
      Played. From 11 to 20 s after the HUD shows, the label's text holds "in 1".
      Reads: "The shield label counts down from Shield in 30 s."
      Fails on: a label written once, which stays "Shield in 30 s", and a number with no words.
      Band: the count starts when the HUD shows, and the band opens 11 s later. The wait is the
      first step, so it starts with the count, and allows 25 s: 14 s to spare. The read at the
      band's opening has 9 s before it closes.
    scenario:
      schema: squadops.scenario/1
      scenario_id: S2
      reader: roblox-studio/1
      setup:
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
      steps:
        - action: wait_until                          # time passes, and the player doesn't move
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_HUD.ShieldLabel", state: text, context: client}
          expect: {op: contains, value: "in 1"}
          deadline_s: 25
      assertions:
        - id: hud-shown
          observe: {kind: property, path: "@player.PlayerGui.TA_HUD", name: Enabled, context: client}
          expect: {op: equals, value: true}
        - id: shield-counting
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_HUD.ShieldLabel", state: text, context: client}
          expect: {op: contains, value: "in 1"}
      named_assertion: shield-counting
```

The wait is on the label the footprint adds, so on today's game it times out and `shield-counting`
fails, as it must. A stuck label never reaches the band, and fails the same way. A working one
reaches `Shield in 19 s` from any start within the first seconds, and the read comes straight after.

If you let time pass with a `hold_key` instead, hold to the middle of the band (15 s for a band of
11 to 20 s), never to its edge: a count that starts a little late reads the second before. And the
key moves the player (rule 5).

### 5. Preservation: read what must still work on its own

A check that something from before still works (another criterion's label, an earlier screen) is
read where nothing unrelated has happened yet: with the shortest setup, and before any long step.
Holding `W` for 15 seconds walks the player, and can take them through a door into another place,
where a label that was right no longer shows. So let time pass with a `wait_until`, as above, and
never make one criterion's scenario read another criterion's element after a walk.

### 6. The kind of evidence: say played or headless, and what no play reached

Each criterion's `observable` starts `Played.` or `Headless.` The warning's two criteria:

```yaml
criteria:
  - id: S3
    statement: At full health the low-health warning is on the HUD and hidden
    surface_kind: scenario
    surface: "@player.PlayerGui.TA_HUD.LowHealthWarning"
    observable: >-
      Played. After Play, at full health, the warning is there and not visible.
      Reads: "It is hidden otherwise."
      Fails on: a warning that always shows, and today's game, which has none. A warning that
      never shows passes here: P1 is the criterion that fails on it.
    scenario:
      schema: squadops.scenario/1
      scenario_id: S3
      reader: roblox-studio/1
      setup:
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
      steps: []
      assertions:
        - id: hud-shown
          observe: {kind: property, path: "@player.PlayerGui.TA_HUD", name: Enabled, context: client}
          expect: {op: equals, value: true}
        - id: warning-hidden
          observe: {kind: gui_state, path: "@player.PlayerGui.TA_HUD.LowHealthWarning", state: visible, context: client}
          expect: {op: equals, value: false}
      named_assertion: warning-hidden
  - id: P1
    statement: The warning's rule shows it under 25 health, and hides it at 25 and above
    surface_kind: package
    surface: "Shared.Modules.LowHealthRules"         # a module under a package the product lists
    observable: >-
      Headless. LowHealthRules.shows(24) is true, and shows(25) and shows(100) are false.
      Reads: "A low-health warning shows on the HUD while the player's health is under 25."
      Not played: no action lowers the player's health, so nobody has watched the warning show.
      Fails on: a rule that never shows, and one that shows at exactly 25.
```

`warning-hidden` expects `false` with `equals`, which a missing warning fails, so it fails on
today's game. No played check can fail on a warning that never shows, since no play lowers
health. `P1` fails on it, and says what it doesn't prove. The HUD asks `LowHealthRules` whether to
show the warning, so the rule `P1` proves is the one the player's screen uses.

## Before you submit

Answer these in each criterion's `observable`, in these words, as the examples do:
- `Played.` or `Headless.`, then what is observed;
- `Reads:` the sentence of the item the criterion reads, quoted word for word;
- `Fails on:` the obvious broken build, and a partial one;
- `Band:` for a value that changes: where the count starts, how long after that the band opens,
  what the wait allows from its own step's start (60 s at most), the seconds to spare (at least
  10), and how long the band stays open after the read;
- `Not played:` on a headless criterion: what no play reached, and why.

Then read the item once more, and change the request if an answer is no:
1. Copy the item's sentences out again, from the objective and not from your `prd_delta`. Is
   each one quoted after a `Reads:`, by a criterion that fails where that sentence is false, or
   read by a criterion an earlier increment froze? Does your `prd_delta` hold every one?
2. Does every action, wait and observation name something today's game sets or your footprint
   adds?
3. Does each named check fail on the two wrong builds you named, and pass on correct work from
   any start?
4. Is anything that must still work read before any long step, and by its own criterion?
5. Does each band open within 30 s of its count's start, with a wait that allows at least 10 s
   more than that, counted from the wait's own start?

## Saved state

A player's saved progress outlives any one version of the game. When the change adds to, removes
from or reorders anything saved progress points at (a list saved by index, a seeded set for the
period, an item id), say in the change's `prd_delta` text what an existing player's save holds after
the change. A new bounty kind that reshuffles the period's seeded set is the case this exists for:
saved progress restored by index then points at different bounties.
