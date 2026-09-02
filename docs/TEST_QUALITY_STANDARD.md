# Test Quality Standard

This document defines the test quality bar for SquadOps. Every new test must pass this standard. Existing tests should be improved to meet it over time.

## Core Principle

**Before writing a test, answer: "What bug would this catch?"**

If you cannot name a specific, realistic bug the test would detect, do not write the test. A test that cannot fail under any realistic code change is not a test — it is noise.

---

## Anti-Patterns (Do Not Write These)

### 1. Tautological Tests

Tests that verify the code does what the code does.

**Bad:**
```python
def test_cycle_status_created_value(self):
    assert CycleStatus.CREATED == "created"
```
This proves the enum's value is its own value. If someone changed it to `"initialized"`, both the code and test would need updating — the test catches nothing the compiler/linter wouldn't.

**Bad:**
```python
def test_construction(self):
    cycle = Cycle(project_id="p1", name="Test")
    assert cycle.project_id == "p1"
    assert cycle.name == "Test"
```
This verifies that a frozen dataclass stores what you give it. Python guarantees this. The test catches no bug.

**Good alternative — test behavior that dataclass construction enables:**
```python
def test_cycle_is_immutable(self):
    cycle = Cycle(project_id="p1", name="Test")
    with pytest.raises(FrozenInstanceError):
        cycle.project_id = "p2"

def test_cycle_replace_preserves_identity(self):
    original = Cycle(cycle_id="c1", project_id="p1", name="Test")
    replaced = dataclasses.replace(original, name="Updated")
    assert replaced.cycle_id == "c1"  # Identity preserved
    assert replaced.name == "Updated"  # Field changed
```

### 2. Over-Mocking

Tests where mocks dominate the test, proving you called the mock, not that the logic is correct.

**Bad:**
```python
async def test_handler_calls_llm(self, handler, mock_context):
    await handler.handle(mock_context, {"prd": "Build X"})
    mock_context.ports.llm.chat.assert_awaited_once()
```
This proves the handler calls `llm.chat()`. It does NOT verify the messages were correct, the response was processed correctly, or the output is valid. A completely broken handler that calls `chat()` with garbage passes this test.

**Good alternative — assert on outputs, not call counts:**
```python
async def test_handler_produces_valid_output(self, handler, mock_context):
    mock_context.ports.llm.chat.return_value = ChatMessage(
        role="assistant", content="## Analysis\nThe approach is sound."
    )
    result = await handler.handle(mock_context, {"prd": "Build X"})
    assert result.success is True
    assert "analysis" in result.outputs  # Real output key exists
    assert len(result.outputs["analysis"]) > 0  # Non-empty content

async def test_handler_fails_on_empty_llm_response(self, handler, mock_context):
    mock_context.ports.llm.chat.return_value = ChatMessage(
        role="assistant", content=""
    )
    result = await handler.handle(mock_context, {"prd": "Build X"})
    assert result.success is False
```

### 3. Happy-Path Only

Suites that only test success. If a suite has no tests with `FAILED`, `raises`, error conditions, or edge cases, it is incomplete.

**Rule:** Every test file must have at least one error/edge case test for each public function tested. For handlers, test at minimum:
- Empty/missing input
- LLM returning empty or malformed content
- Unexpected input types

### 4. Weak Assertions

**Bad:**
```python
assert result is not None
assert len(artifacts) > 0
assert isinstance(health, dict)
```

**Good:**
```python
assert result.status == "SUCCEEDED"
assert len(artifacts) == 3
assert health == {"healthy": True, "agent_id": "a1", "role_id": "lead"}
```

Assert on **exact expected values** when they are deterministic. Use `is not None` only when the value is genuinely non-deterministic (e.g., a generated UUID).

### 5. Copy-Paste Fixtures That Hide Variation

**Bad:**
```python
@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content="LLM output")
    )
    return ctx
```
Every test using this fixture gets the exact same LLM response. No test discovers what happens when the response is different.

**Good — use parametrize or fixture factories:**
```python
def make_context(llm_response: str = "LLM output"):
    ctx = MagicMock()
    ctx.ports.llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=llm_response)
    )
    return ctx

@pytest.mark.parametrize("response", [
    "## Analysis\nValid structured response",
    "",
    "Just a plain string with no structure",
    "```python\ncode_block()\n```",
])
async def test_handler_handles_varied_responses(self, response):
    ctx = make_context(response)
    result = await handler.handle(ctx, {"prd": "Build X"})
    # Assert based on expected behavior per response type
```

### 6a. Seam Tests That Hand the Seam Its Input

A test that constructs a seam's input by hand proves the seam and says nothing about who
calls it. Three defects in the 1.7.1 line were latent from their own PRs for exactly this
reason, and every one was found by a live cycle rather than by CI:

- #1250 — the repair hand-off was tested with an envelope that already carried the
  workspace key; the executor handed the runner a different envelope that never had it.
- #1256 — the verifier was tested with the repair's rows passed straight in; the executor
  read them off the *failed task's* result, where they never are. Rule B ran for three
  weeks and never delivered a row in a live round.
- #1261 — the tsc classifier was tested with a `TS1005` line; the live tree carried
  `TS18048`, which the prefix rule also matched.

```python
# Anti-pattern: the seam is proven, the wiring is not
async def test_agent_rows_decide():
    verdict = await verify_patched_artifacts(criteria, patch, agent_checks=rows)
    assert verdict.decided_by_agent == 1

# Correct: enter where the live path enters, with the collaborators the live path has
async def test_the_protocol_results_rows_reach_the_verifier(monkeypatch):
    ex._correction_runner.run_correction_protocol = AsyncMock(
        return_value=CorrectionProtocolResult(correction_path="patch", repair_typed_checks=(rows,))
    )
    monkeypatch.setattr(executor_module, "verify_patched_artifacts", capture)
    await ex._handle_task_outcome(result=failed, envelope=envelope, ...)
    assert handed["agent_checks"] == (rows,)
```

For any change to a seam another component calls — a new output key, a new parameter, a
row another environment consumes — the PR carries **both**: the seam test, and one test
that enters at the caller the live cycle uses (the executor's outcome handler, the
correction protocol, the check registry) and asserts what arrives. Name the entry point in
the PR's Evidence section. Fixtures replayed from stored artifacts prove the seam's logic;
only the wiring test proves the cycle reaches it.

### 6. Tests That Can Never Fail

**Bad:**
```python
def test_default_is_empty(self):
    cycle = Cycle(project_id="p1", name="Test")
    assert cycle.applied_defaults == {}
```
The dataclass field has `default_factory=dict`. Python guarantees this. The test is testing Python, not your code.

---

## What to Test (Priority Order)

### P0: Always Test
- **State machine transitions** — legal transitions succeed, illegal transitions raise
- **Security boundaries** — path traversal, injection, auth enforcement
- **Data transformation correctness** — input X produces output Y (exact values)
- **Error handling** — what happens when things break (not just that they don't break when things work)
- **Invariants** — immutability, uniqueness, ordering guarantees that business logic depends on
- **Wiring of a changed seam** — one test that enters at the live caller and asserts what
  reaches the seam (anti-pattern 6a); the seam's own test is necessary, not sufficient

### P1: Test When Non-Trivial
- **Edge cases** — empty inputs, max-length inputs, boundary values, None where Optional
- **Integration seams** — serialization round-trips, DTO mapping with real (not mock) transformers
- **Concurrency** — if the code is async, test concurrent access where relevant

### P2: Test If High-Risk
- **Regression anchors** — when a specific bug was fixed, add a test for that exact scenario
- **Contract tests** — verify adapters satisfy port contracts with real (not mocked) adapter instances

### Skip
- Enum member existence (the import itself proves this)
- Frozen dataclass field assignment (Python guarantees this)
- Mock call counts as the sole assertion
- Type checking (`isinstance`) as the sole assertion

---

## Test Structure Rules

1. **Name tests for the behavior, not the method.** `test_resume_skips_completed_tasks` not `test_resume`.
2. **One logical assertion per test.** Multiple `assert` lines are fine if they verify one behavior. Don't combine unrelated checks.
3. **Arrange-Act-Assert.** Clear separation. No interleaved assertions and actions.
4. **Fixtures build context, not answers.** Fixtures set up the world. Tests verify behavior in that world. Fixtures should not contain the expected answers.
5. **Parametrize varied inputs, not varied setups.** Use `@pytest.mark.parametrize` for input variation. Use separate test functions for different behaviors.

---

## Minimum Coverage for New Features

For each new feature (handler, model, port method), provide:

| Area | Minimum Tests |
|------|---------------|
| Happy path | 1-2 (with exact value assertions) |
| Error paths | 1-2 (missing input, invalid input, upstream failure) |
| Edge cases | 1-2 (empty, boundary, None) |
| Integration seam | 1 (round-trip or DTO mapping, if applicable) |
| Seam wiring | 1 per changed seam, entering at the live caller (anti-pattern 6a) |

A handler with 4 strong tests is worth more than 20 weak ones.

---

## Reviewing Existing Tests

When modifying a test file, take 60 seconds to scan for anti-patterns. If you find tautological or mock-call-only tests, note them but do not delete them in the same PR — improvements are separate work. Exception: if you are already modifying that specific test, improve it in place.

---

## Enforcement

- **CLAUDE.md** contains the condensed rules that are checked every conversation.
- **This document** is the full reference with examples and rationale.
- **AST linter** (`scripts/dev/lint_test_quality.py`) detects anti-patterns 1-4 automatically. It runs as a Claude Code `PostToolUse` hook (`.claude/hooks/lint-test-quality.sh`) after every test file Write/Edit, providing immediate feedback before violations land. The linter is also **blocking** in `run_regression_tests.sh` — any violation fails the regression suite. All 235 pre-existing violations have been resolved.
- When writing tests, the question "what bug does this catch?" must have a concrete answer.
