# 2.6 sealed play measure: pre-registration

**Ruled by the owner, 2026-11-07.** Written before any counted Campaign. This is the improvement threshold rung 3 of the
2.6 plan's release claim requires (§4, D8), for the proving Project, battle-trainer.

## Why

The owner ruled the same day that "we should only have rules that come from the game maker". The held-out suite's test
revision 2 therefore checks only that orders are legal, so it can't show that play improved. This measure does.

## The measure

- **Two sealed sets of ten games,** drawn once by the operating system's generator, without looking at any result. Each
  rotates the four house bots and balances sides. They sit outside every repository, and neither the squad nor the
  implementer sees them. Digest of the sets: `f473ab9e9ae8bd73e77637fd4877c9c8395fb862de8392b162016f986f2638af`.
- **The watch set** is read after a Campaign, and its games reach the owner's viewer, so a number can be checked by eye.
- **The claim set** is read twice in all: on the head the counted Campaign starts from, and on the head it ends on. The
  runner refuses a second read of either.
- **What's read:** the engine's match result, unit positions and each objective's radius. A tank has reached an
  objective if it is ever alive inside one's radius. The controller runs confined, on the pinned engine.

## The threshold

Both must hold on the claim set, from the before reading to the after reading:

1. the share of tanks that never reach an objective falls by at least a third of its before value;
2. the wins are higher than the before reading's.

It's a share because the squad may change how many tanks it fields.

## Readings before registration

On commit `3c5e123`: nothing played reads 30 of 30 never reached, as it must. The watch set reads 3 wins of 10, and 21 of
30 tanks never reached an objective. The claim set is unopened.

## What this doesn't cover

Ten games is a small sample. Replaying the same games removes map variance, since the engine is deterministic, but says
less about games outside the set. Wins alone prove little, which is why both conditions must hold. The house bots are a
reference, not a target.
