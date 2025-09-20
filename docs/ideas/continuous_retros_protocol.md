# Squad Ops Protocol: Continuous Retrospective (TD-Style)

## Purpose
Replace static sprint retrospectives with a **continuous, temporal-difference (TD) style feedback loop** that provides fluid, real-time course correction during development cycles.

---

## Key Roles
- **Max (Critic Agent)**: Maintains a rolling project health score, observes deltas after each action or milestone, and assigns rewards/flags.
- **Actor Agents (Nat, Neo, Joi, Og, Data, EVE, etc.)**: Execute tasks, propose sparks, and adapt behaviors based on feedback.
- **Squad (Collective)**: Benefits from continuous learning and correction without fixed sprint boundaries.

---

## Inputs for Project Health Score
Max continuously monitors these signals (weights configurable per project):

- Build/test pass rate
- Bug density (open vs. resolved)
- Cycle time (time-to-completion of tasks)
- Scope clarity (changes in scope vs. baseline)
- Velocity predictability (variance in throughput)
- Comms latency and resolution effectiveness
- Spark adoption rate (ideas → accepted → impact)

---

## Process Flow

1. **Baseline Health Score**
   - At project start or pulse initiation, Max initializes a `Project Health Score` (0–100).

2. **Event Observation**
   - After every agent action or pulse milestone, Max recalculates the health score.

3. **Delta Evaluation**
   - If health ↑: Credit recent contributing agents.
   - If health ↓: Trigger an RCA micro-loop to identify contributing factors.

4. **Credit Assignment**
   - Agents receive proportional rewards (tokens/credits) linked to the observed improvement.
   - Neutral actions (no impact) are logged but not rewarded.

5. **Continuous Retros Output**
   - Max generates a short summary in natural language, e.g.:
     > *"After Og’s trade-off suggestion was adopted, scope risk dropped 12%. Nat + Og credited. Team trajectory improving."*

6. **Adaptation**
   - Actor agents adjust behavior mid-cycle (code quality, comms, task proposals).
   - No waiting for end-of-sprint retros; feedback is fluid.

---

## Benefits
- Removes reliance on static sprint boundaries.
- Provides continuous introspection and alignment.
- Encourages fair, real-time credit assignment.
- Mitigates political or biased retrospectives by anchoring to measurable signals.

---

## Example
- Neo submits a new module → EVE reports 30% fewer test failures → Project Health ↑.
- Max credits Neo (delivery) + EVE (validation).  
- Micro-retro summary: *"Code stability improved. Trajectory positive."*

---

## Notes
- This protocol integrates with the **Dev Cycle Protocol** and **Incentive/Reward Protocols**.
- All health signals and reward weights should be configurable via YAML/JSON per squad.
