# IDEA: Agent Squad Self-Play Consensus Benchmark

## Status
Draft

## Summary
Explore an experiment where two agent squads are given a structured game such as chess, a fixed overall time budget to complete play, and the freedom to devise their own internal consensus method.

The goal is not simply to see which squad wins a game. The real goal is to observe whether different consensus methods emerge, how they behave under combinatorial pressure, and whether they produce coherent, repeatable play rather than random motion, accidental wins, or time-loss failures.

This idea is less about chess itself and more about creating a compact benchmark harness for evaluating agent coordination quality.

## Core Intent
The experiment should avoid over-scaffolding the internal decision process.

You want to see whether squads can invent workable consensus approaches on their own, while still making those approaches observable and comparable.

That means the system should provide:
- the game rules
- the win/loss conditions
- the total time budget
- the evidence capture requirements
- a minimal failsafe so the run cannot hang forever

The squads should provide:
- the consensus method
- the authority model
- the candidate-pruning approach
- the escalation behavior
- the tradeoff between move quality and decision speed

## Central Question
Can Spark squads devise distinct consensus methods that produce coherent gameplay under an overall game deadline, and can those methods be compared meaningfully?

## Why Chess or a Similar Game Works
A game like chess is useful because it has:
- clear turns
- deterministic rules
- a massive decision space
- obvious outcomes
- replayable evidence
- enough complexity to expose coordination weakness quickly

The agents do not need to solve chess exhaustively. They only need to create a consensus process that can manage the combinatorial pressure well enough to make coherent moves before time expires.

## Key Hypothesis
A well-designed self-play experiment can surface meaningful differences in squad coordination methods, but only if the benchmark measures more than win/loss.

A weak squad may:
- make random or weak moves
- over-deliberate and lose on time
- fail to converge on decisions
- produce accidental wins that do not reflect true coordination quality

A stronger squad may:
- narrow candidate moves quickly
- coordinate authority effectively
- balance speed and move quality
- maintain a coherent strategy across turns
- improve its method between rounds

## Important Design Principle
Do not prescribe the exact move-loop consensus process.

If you overly define:
- how many debate rounds are allowed
- whether voting must occur
- how tie-breaking must work
- what internal decision sequence is required

then you are testing your scaffolding more than their emergent coordination design.

The better constraint is:
- fixed rules
- fixed overall game deadline
- required observability of method and outcomes

## Proposed Experiment Structure

### Phase 1: Setup
Each squad is asked to:
- understand the game rules
- declare its consensus method before play
- define any internal roles it wants to use
- define how it will prune candidate moves
- define how it will resolve disagreement
- define how it will prevent endless deliberation

The important point is that the method is declared by the squad, not by the benchmark designer.

### Phase 2: Play
The squads play under a fixed overall completion deadline.

They should be free to manage their internal timing however they choose.

This means:
- a squad may spend more time on critical moves and less on obvious ones
- one squad may use a lead-agent model
- another may use weighted voting or challenge-and-override
- another may rotate authority
- another may use a critic/champion pattern

The deadline creates the incentive. Poor coordination should naturally cause time loss.

### Phase 3: Evidence Capture
The system should record enough evidence to compare methods without requiring essay-length reasoning.

Examples:
- declared consensus method
- role assignments
- move candidates considered
- short rationale for final move
- timeout or fallback events
- override frequency
- disagreement frequency
- move times
- game outcome
- post-game reflection

### Phase 4: Review
After the game, each squad should analyze:
- where consensus worked
- where it stalled
- where time was wasted
- whether authority was too centralized or too diffuse
- whether the method helped or hurt move quality
- what they would change next round

### Phase 5: Iteration
Run multiple games so the benchmark evaluates repeatability rather than one noisy outcome.

The real signal is whether a squad's method:
- produces coherent play repeatedly
- avoids collapse under pressure
- adapts after evidence review
- improves over time

## Core Risk
The major risk in v1 is that both squads make effectively random moves, and one squad wins by accident or simply because the other ran out of time.

If that happens, win/loss alone is not meaningful.

So the benchmark needs to separate:
- coherent but imperfect play
from
- chaotic move emission with lucky results

## What Should Be Measured
Early versions of the benchmark should weight coordination quality more heavily than raw victory.

Potential measures:
- legal move rate
- completion within allotted time
- average decision time
- stall frequency
- fallback frequency
- declared-plan versus actual-move alignment
- position quality trend using a lightweight evaluator
- blunder frequency
- repeatability across games
- post-game reflection quality

## Success Tiers
One way to interpret results is through maturity tiers.

### Tier 1
The squad can complete legal games within the overall deadline.

### Tier 2
The squad shows evidence of coherent strategic behavior rather than random move selection.

### Tier 3
The squad produces repeatable performance across multiple games.

### Tier 4
The squad adapts and improves its consensus method between rounds.

This helps prevent accidental wins from being mistaken for meaningful success.

## Enabling Capabilities vs Over-Scaffolding
The squads may need a few enabling capabilities, but not a fully prescribed solution.

Helpful capabilities:
- candidate move generation
- lightweight move evaluation
- budget awareness
- disagreement detection
- final-decision closure
- evidence compression
- post-game review support

Avoid baking in:
- exact consensus flow
- required voting rules
- mandatory internal round structure
- overly detailed reasoning templates

The environment should make good coordination easier without dictating the answer.

## Why This Matters for Spark Squads
This is a compact proxy test for a bigger question:

Can a squad turn reasoning into timely action under pressure?

If a squad cannot:
- prune options
- assign authority
- close deliberation
- act before the clock expires

then the same failure pattern is likely to show up in more important workloads too.

That is what makes this experiment valuable. It is a smaller, safer pressure chamber for the broader coordination problem.

## Benchmark Value
This can become a repeatable harness for comparing consensus styles such as:
- lead-agent override
- majority vote
- weighted vote
- proposal plus veto
- rotating authority
- critic/champion
- hierarchical narrowing
- confidence-weighted selection

The benchmark can then compare not just who won, but which method:
- stayed coherent
- used time well
- avoided stalls
- produced better positions
- improved after review

## Recommended Next Step
Turn this into a more formal IDEA or SIP that defines:
- experiment objective
- minimum viable game implementation
- evidence schema
- benchmark metrics
- iteration protocol
- method declaration requirements
- cross-run comparison model

## Closing Framing
This is not really a chess experiment.

It is an experiment in whether agent squads can invent, inhabit, and improve their own coordination methods under constraint.

The game is just the test chamber.
