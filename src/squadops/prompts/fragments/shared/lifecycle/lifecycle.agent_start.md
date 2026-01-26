---
fragment_id: lifecycle.agent_start
layer: lifecycle
version: "0.8.5"
roles: ["*"]
---
## Agent Initialization

You are starting a new execution cycle. Before proceeding:

1. Verify your role configuration is loaded correctly
2. Confirm access to required resources (database, queue, secrets)
3. Check for any pending tasks from previous cycles
4. Report your ready status to the orchestrator

If any initialization step fails, halt and report the error immediately.
