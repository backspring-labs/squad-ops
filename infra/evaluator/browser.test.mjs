// browser.mjs's vocabulary against a fake page (SIP-0113 §10p rulings 1 to 5), with no browser:
// `node --test infra/evaluator/browser.test.mjs`. tests/unit/sandbox/test_evaluator_browser.py
// runs it in CI. Every value is invented.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fold, locate, runSegment } from "./browser.mjs";

const FAST = { navigateMs: 200, locateMs: 60, checkMs: 60, settleIdleMs: 1, settleMs: 5, pollMs: 5 };

// A page of elements by role, each {name, text, visible, disabled, form, depth}, that a click or a
// fill can change through `on`.
function fakePage({ elements = {}, status = 200, text = "", empty = false, on = {} } = {}) {
  const state = { elements, text, status, empty, exceptions: 0, acted: [] };
  return {
    state,
    async load() {
      return state.status;
    },
    async find(role) {
      return (state.elements[role] ?? []).map((e) => ({ visible: true, disabled: false, text: "", ...e }));
    },
    async related(a, b) {
      return { sameForm: Boolean(a.form) && a.form === b.form, depth: a.depth ?? 0 };
    },
    async stable() {
      return true;
    },
    async fill(el, value) {
      state.acted.push(["fill", el.name, value]);
      on.fill?.(state, el, value);
    },
    async click(el) {
      state.acted.push(["click", el.name]);
      on.click?.(state, el);
    },
    async settle() {
      return true;
    },
    async bodyText() {
      return state.text;
    },
    async axEmpty() {
      return state.empty;
    },
    exceptions() {
      return state.exceptions;
    },
    errors() {
      return [];
    },
    failedRequests() {
      return [];
    },
    async screenshot() {
      return "iVBORw0KGgo=";
    },
  };
}

const segment = (steps, checks = [], first = 1) => ({
  base_url: "http://app:4173/",
  first_step: first,
  steps,
  checks,
  deadline_s: 5,
});

test("names match exactly after folding, candidates in order, never by substring", async () => {
  const page = fakePage({
    elements: { button: [{ name: "Joined" }, { name: "  JOIN   this run " }, { name: "Join" }] },
  });

  const { element, matched } = await locate(page, { role: "button", names: ["Join", "Join this run"] });
  const second = await locate(page, { role: "button", names: ["Join this run"] });

  assert.equal(element.name, "Join"); // "Joined" is never "Join"
  assert.deepEqual(matched, { name_index: 0, count: 1 });
  assert.equal(second.element.name, "  JOIN   this run ");
  assert.equal(fold("  Ｊoin\tRun "), "join run");
});

test("near picks the control in the same form, so the leave form's name box is never typed into", async () => {
  const page = fakePage({
    elements: {
      textbox: [
        { name: "Name", form: "leave", depth: 9 },
        { name: "Name", form: "join", depth: 3 },
      ],
      button: [{ name: "Leave", form: "leave" }, { name: "Join", form: "join" }],
    },
  });

  const { element } = await locate(page, {
    role: "textbox",
    names: ["Name"],
    near: { role: "button", names: ["Join"] },
  });

  assert.equal(element.form, "join");
});

test("a mixed flow: visit, fill near Join, click, and the check after the click reads the page then", async () => {
  const page = fakePage({
    text: "Ridge Loop 0 / 3 joined",
    elements: { textbox: [{ name: "Your name", form: "join" }], button: [{ name: "Join", form: "join" }] },
    on: { click: (s) => (s.text = "Ridge Loop 1 / 3 joined") },
  });

  const answer = await runSegment(
    page,
    segment(
      [
        { action: "visit", path: "/runs/r1" },
        { action: "fill", target: { role: "textbox", names: ["Name", "Your name"], near: { role: "button", names: ["Join"] } }, value: "Ida" },
        { action: "click", target: { role: "button", names: ["Join"] } },
      ],
      [
        { index: 0, check: { check: "text", step: 1, pattern: "0\\s*/\\s*3" } },
        { index: 1, check: { check: "text", step: 3, pattern: "1\\s*(/|of)\\s*3" } },
      ],
    ),
    FAST,
  );

  assert.deepEqual(answer.steps.map((s) => s.outcome), ["done", "done", "done"]);
  assert.deepEqual(answer.checks.map((c) => [c.index, c.holds]), [[0, true], [1, true]]);
  assert.deepEqual(page.state.acted, [["fill", "Your name", "Ida"], ["click", "Join"]]);
  assert.equal(answer.evidence, null);
});

test("each way a step ends, and the evidence of the one that didn't end done", async () => {
  const cases = [
    [{}, { role: "button", names: ["Join"] }, "not_found"],
    [{ button: [{ name: "Join", disabled: true }] }, { role: "button", names: ["Join"] }, "action_failed"],
  ];
  for (const [elements, target, outcome] of cases) {
    const answer = await runSegment(
      fakePage({ elements }),
      segment([{ action: "visit", path: "/" }, { action: "click", target }]),
      FAST,
    );
    assert.equal(answer.steps.at(-1).outcome, outcome);
    assert.equal(answer.evidence.step, 2);
    assert.equal(answer.evidence.role, "button");
  }
  for (const [page, detail] of [
    [fakePage({ status: 404 }), "answered 404"],
    [fakePage({ empty: true }), "the page rendered nothing"],
  ]) {
    const answer = await runSegment(page, segment([{ action: "visit", path: "/runs/zz" }]), FAST);
    assert.deepEqual([answer.steps[0].outcome, answer.steps[0].detail], ["page_broken", detail]);
  }
  const raising = fakePage({ elements: { button: [{ name: "Join" }] }, on: { click: (s) => (s.exceptions += 1) } });
  const broke = await runSegment(raising, segment([{ action: "visit", path: "/" }, { action: "click", target: { role: "button", names: ["Join"] } }]), FAST);
  assert.equal(broke.steps[1].outcome, "page_broken");
});

test("a step that fails ends the segment: later steps and their checks are never read", async () => {
  const answer = await runSegment(
    fakePage(),
    segment(
      [{ action: "visit", path: "/" }, { action: "click", target: { role: "button", names: ["Join"] } }, { action: "visit", path: "/runs" }],
      [{ index: 4, check: { check: "absent", step: 3, pattern: "error" } }],
    ),
    FAST,
  );

  assert.deepEqual(answer.steps.map((s) => s.step), [1, 2]);
  assert.deepEqual(answer.checks, []);
});

test("count, order, control and absent read the page, and what they saw never quotes it", async () => {
  const page = fakePage({
    text: "Harbor 5K  Quarry Intervals  Mill Pond",
    elements: {
      listitem: [{ text: "Quarry Intervals" }, { text: "Harbor 5K" }, { text: "Mill Pond" }, { text: "Nav: About" }],
      button: [{ name: "Join", disabled: true }],
    },
  });
  const checks = [
    { index: 0, check: { check: "order", step: 1, target: { role: "listitem" }, patterns: ["Harbor", "Mill"] } },
    { index: 1, check: { check: "order", step: 1, target: { role: "listitem" }, patterns: ["Mill", "Harbor"] } },
    { index: 2, check: { check: "count", step: 1, target: { role: "listitem", text: "pond" }, equals: 1 } },
    { index: 3, check: { check: "control", step: 1, target: { role: "button", names: ["Join"] }, is: "unavailable" } },
    { index: 4, check: { check: "absent", step: 1, pattern: "Quarry" } },
  ];

  const answer = await runSegment(page, segment([{ action: "visit", path: "/" }], checks), FAST);

  assert.deepEqual(answer.checks.map((c) => [c.index, c.holds]), [[0, true], [1, false], [2, true], [3, true], [4, false]]);
  for (const c of answer.checks) assert.ok(!/Quarry|Harbor|Mill/.test(c.seen ?? ""), c.seen);
  assert.equal(answer.evidence.step, 1);
});

test("a value Python escaped reads as the character it escapes", async () => {
  const page = fakePage({ text: "Dawn (5k) + coffee" });
  const escaped = "Dawn\\ \\(5k\\)\\ \\+\\ coffee"; // re.escape("Dawn (5k) + coffee")

  const answer = await runSegment(page, segment([{ action: "visit", path: "/" }], [{ index: 0, check: { check: "text", step: 1, pattern: escaped } }]), FAST);

  assert.equal(answer.checks[0].holds, true);
});

test("a check or a step that throws says so in its reading and keeps the error's text in the evidence", async () => {
  const secret = "Moonrise(Relay";
  const answer = await runSegment(
    fakePage({ text: "x" }),
    segment([{ action: "visit", path: "/" }], [{ index: 0, check: { check: "text", step: 1, pattern: secret } }]),
    FAST,
  );

  assert.deepEqual([answer.checks[0].holds, answer.checks[0].seen], [false, "the check couldn't be read"]);
  assert.ok(!JSON.stringify(answer.checks).includes("Moonrise"));
  assert.ok(answer.evidence.errors[0].startsWith("driver: ") && answer.evidence.errors[0].includes("Moonrise"));

  const throwing = fakePage({ elements: { button: [{ name: "Join" }] } });
  throwing.click = async () => {
    throw new Error(`Node is detached: ${secret}`);
  };
  const failed = await runSegment(throwing, segment([{ action: "visit", path: "/" }, { action: "click", target: { role: "button", names: ["Join"] } }]), FAST);

  assert.deepEqual([failed.steps[1].outcome, failed.steps[1].detail], ["action_failed", "Error"]);
  assert.ok(failed.evidence.errors[0].includes("Moonrise"));
});
