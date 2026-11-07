# 2.6 three-increment Campaign: pre-registration

**Status: REGISTERED 2026-11-07, before the Campaign is created.** Counted for the 2.6 plan's rungs 1 and 2 (§4), on the
owner's ruling of the same day that those two carry the cut.

## Why it runs

Campaign `cmp_a0a7daf13416` accepted three increments on 2026-11-06, but it wasn't pre-registered, and #2945 and #2947 have
since changed code on its path, which voids it for the release claim (§3).

## The deploy and the Campaign

- **The deploy:** `dep_2b6c8b9da0ca`, from `faed0f6f`. Main has moved since by documents only.
- **The product:** battle-trainer at `3c5e123`, Development Configuration revision 9.
- **The goal set:** revision 9, in the owner's order: BT-15, BT-13, BT-10, BT-11. Each item states a measured outcome over
  ten fixed games that the head doesn't meet.
- **The definition:** target 3 accepted increments, `max_cycles` 12, `max_elapsed_s` 28800, sha256
  `21d896c9de410d0ee54963c587983db072520e2732ff66ce8752e4d7a7d4ef01`, on `full-38-tf`.
- **Rulings:** the supervisor approves each proposal as it stands. Nobody edits the product during the run.

## The readings, each with what falsifies it

1. **R1. Three increments accepted in one Campaign, each from a different backlog item,** on the product's own vitest
   runner. Falsified by fewer than three when the Campaign closes.
2. **R2. Each accepted increment is promoted and its Campaign's work reaches a review request.** Falsified by a
   contribution that can't be opened.
3. **R3. Every stop is attributed to a named §10 row.** Falsified by a stop no row names.
4. **R4. Each accepted increment is read against its replays,** after BT-12 (`cmp_a8cc46904e9d`) met a blocked count by
   stopping tanks. The sealed watch set and the tanks' motion are reported beside the verdict. This reads play and does
   not change R1: the rung counts acceptance, and the report says plainly if an accepted change didn't improve play.

## If it misses

The Campaign's result stands as read. Whether the cut narrows further, or the run repeats, is the owner's ruling.
