# The Studio worker on a Mac: starting, stopping, and a dedicated window

The `roblox-studio` worker plays scenarios in Roblox Studio on a Mac a person also uses (SIP-0117 R3.6). This
runbook says how it starts and stops, and how its owner declares a window in which the worker may bring Studio
to the front itself (R5.33, #3193). The worker's setup is `scripts/dev/worker_service.py`; its settings are the
`SQUADOPS__WORKER__*` lines of `~/.config/squadops/worker.env`.

## How it starts and stops

- **It starts when you log in.** `worker_service.py install` makes it a per-user LaunchAgent, which launchd
  starts at login and again whenever it exits. That is outside any window: a worker that is running serves
  claims at any hour its runtime sends them.
- **Stop it:** `launchctl bootout gui/$(id -u)/xyz.backspring.squadops.worker`.
- **Start it again:** `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/xyz.backspring.squadops.worker.plist`.
- **Keep it from starting at login:** `worker_service.py uninstall`, and install it again when you want it.
- **After a restart** with FileVault on, the worker comes back only once you have logged in.

Whether it starts at login is yours to keep or change.

## Studio in front

A scenario that clicks, types or moves acts through Studio's input, which acts only on a Studio in front
(R5.18). A worker that finds another app in front refuses such a play, and the Campaign retries it (R5.28).
That is still what happens unless you declare a dedicated window. Whether dedicated or not, the worker reads the
lock and the console session before every such play, and the lock again before each input action: a locked screen
is never played on (R5.37).

## A dedicated window (R5.33)

Inside a window you declare, the worker may bring the running Studio to the front itself, once per operation,
when nobody has used the Mac for a while. Four lines in the env file declare it:

```
SQUADOPS__WORKER__ROBLOX_STUDIO_DEDICATED=true
SQUADOPS__WORKER__ROBLOX_STUDIO_WINDOW_START=2026-11-27T22:00:00-05:00
SQUADOPS__WORKER__ROBLOX_STUDIO_WINDOW_END=2026-11-28T07:00:00-05:00
SQUADOPS__WORKER__ROBLOX_STUDIO_IDLE_THRESHOLD_S=300
```

- **Write them yourself.** No lane writes them, and the code ships with none. Without all four the worker isn't
  dedicated, and nothing is defaulted.
- **The start and end carry a UTC offset** (`-05:00` above). One without an offset, one that doesn't parse, or an
  end at or before its start is refused at each check as a setting that can't be read.
- **The threshold is at least 60 seconds.** It is how long the Mac must have had no keyboard, mouse or trackpad
  input. A lower value is refused as a setting.
- **The window is one span, not a daily schedule.** Write a new one for each period you give the Mac over.
- **Restart the worker after changing them** (the two `launchctl` lines above).

What the worker reads before every play that clicks, types or moves, whether or not Studio is already in front
(R5.37):
1. the window, against the Mac's clock;
2. that it still holds the operation's lease;
3. the idle counter, at or over the threshold;
4. the screen unlocked, and exactly one console session on the console and logged in;
5. the idle counter again;
6. that a proved Studio is running, and, if it is behind, the clock again before it brings that Studio forward
   by its process id.

Then, immediately before the first input action, the lease, the window and the idle counter again; and before
each input action after it, and as soon as a held key ends, the lock and the idle counter.

If any of them doesn't hold, or can't be read, nothing more is sent, and the play is refused as the Mac's, never
as the work's. It never starts Studio (it brings forward only the running process the proof read), never
unlocks the screen, answers no dialog and sends no input of its own. If you touch the Mac during the activation
or during the play, nothing more is played, and the front isn't moved again. Your keyboard and mouse are what
the idle counter reads: measured on this Mac, a scenario's own clicks and held keys don't move it.

Each play that clicks, types or moves records what happened, in `ran_with`: `front.input` (`permitted` or
`refused`), `front.activated` (`false` when Studio was already in front), `front.was` (`studio`, `other`,
`none` or `unread`), `front.idle_s`, and `front.refused` with one of the rule's reasons. It never records which
app was in front or what you were doing.

## Before you give the Mac over

- On mains power, with the lid open.
- No automatic update that restarts it during the window.
- Studio signed in, and the place open.
- The worker's qualification current (`scripts/dev/studio_requalify.py`). Studio's tool list can change at any
  launch.
