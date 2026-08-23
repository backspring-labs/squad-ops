# Operate a cycle

Task-oriented walkthrough of the operations you will actually perform. For the
full command surface see the [CLI reference](cli.md).

## Start a cycle

```bash
squadops login
squadops cycles create play_game \
  --squad-profile full \
  --request-profile validated-fullstack
```

`cycles create` runs a **preflight** before anything is persisted — the squad
profile's models must be available on the target, required roles must be
filled, and the request profile must resolve. A misconfiguration fails here with
a 422 rather than forty minutes into a run.

## Watch it

```bash
squadops cycles show play_game <cycle-id>
squadops runs list  play_game <cycle-id>
```

The run graph and per-task logs are in Prefect at `http://localhost:4200`; what
the model was sent and returned is in LangFuse at `http://localhost:3001`. See
[observability](observability.md) for which surface answers which question.

## Decide a gate

A cycle showing `paused` is waiting for you at an inter-workload gate.

```bash
squadops runs show play_game <cycle-id> <run-id>          # what is waiting
squadops runs gate play_game <cycle-id> <run-id> progress_plan_review --approve
```

A gate can be accepted **with a waiver**, which records the waived check ids and
a reason on the decision. The waiver sits above the evidence and never edits it,
so a later reader sees both what was waived and what was actually verified.

## Get the application out

```bash
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

`assemble` materialises the run's promoted artifacts into a runnable project
directory — the command that turns a cycle result into something you can install
and boot.

## Recover an interrupted run

```bash
squadops runs checkpoints play_game <cycle-id> <run-id>   # what state exists
squadops runs resume      play_game <cycle-id> <run-id>   # continue from it
squadops runs retry       play_game <cycle-id> <run-id>   # re-execute
```

Because each workload is its own run with its own promoted artifacts, resuming
does not re-author work that already completed.

## Check models are present

```bash
squadops models list      # what the squad profiles reference
squadops models pulled    # what is actually on the inference host
squadops models pull qwen3.6:27b
```

The gap between *referenced* and *pulled* is what a preflight failure is usually
pointing at.
