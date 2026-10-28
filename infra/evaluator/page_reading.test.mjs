// page_reading.mjs against invented axe and Lighthouse results (SIP-0113 §10y; #2637), with no
// browser: `node --test infra/evaluator/page_reading.test.mjs`.
// tests/unit/sandbox/test_evaluator_page_reading.py runs it in CI. Every value is invented; the
// results' shape is Lighthouse 13.5's and axe 4.14's, read live in the evaluator's image.
import assert from "node:assert/strict";
import { test } from "node:test";
import { ENVIRONMENT_AUDITS, axeReading, lighthouseReading, pageReading } from "./page_reading.mjs";

// A Lighthouse result from {category: {score, refs: [[id, weight, score]]}}.
function lhr(categories) {
  const out = { categories: {}, audits: {} };
  for (const [id, { score, refs }] of Object.entries(categories)) {
    out.categories[id] = { id, score, auditRefs: refs.map(([ref, weight]) => ({ id: ref, weight })) };
    for (const [ref, , s] of refs) out.audits[ref] = { id: ref, score: s };
  }
  return out;
}

// Best practices as the sandbox serves it: both environment audits failing (weights 5 and 1, as
// Lighthouse 13.5 weighs them), 21 more weight passing, one audit weighted 0 (informative).
function practices({ failing = [], errored = [], score } = {}) {
  const refs = [
    ["is-on-https", 5, 0],
    ["redirects-http", 1, 0],
    ["deprecations", 5, 1],
    ["third-party-cookies", 5, 1],
    ["paste-preventing-inputs", 3, 1],
    ["charset", 1, 1],
    ["doctype", 1, 1],
    ["errors-in-console", 1, 1],
    ["inspector-issues", 1, 1],
    ["image-aspect-ratio", 1, 1],
    ["image-size-responsive", 1, 1],
    ["geolocation-on-start", 1, 1],
    ["notification-on-start", 1, 1],
    ["csp-xss", 0, 0],
  ].map(([id, w, s]) => [id, w, errored.includes(id) ? null : failing.includes(id) ? 0 : s]);
  return { score, refs };
}

const PERFORMANCE = { score: 0.97, refs: [["largest-contentful-paint", 25, 0.9], ["speed-index", 10, 0]] };
const ACCESSIBILITY = {
  score: 0.83,
  refs: [["label", 10, 0], ["button-name", 10, 1], ["color-contrast", 7, 0], ["list", 0, 0], ["bypass", 3, 1]],
};

test("axe counts each violating node under its own impact, beside the rule count", () => {
  const read = axeReading({
    violations: [
      { id: "region", impact: "moderate", nodes: [{ impact: "moderate" }, { impact: "moderate" }, { impact: "moderate" }] },
      { id: "label", impact: "critical", nodes: [{ impact: "critical" }, { impact: "serious" }] },
      { id: "color-contrast", impact: "serious", nodes: [{}] },
      { id: "label", impact: "critical", nodes: [{ impact: "critical" }] },
    ],
  });

  // Rules are counted as before: one per violation, by the violation's impact.
  assert.deepEqual(read.axe, { critical: 2, serious: 1, moderate: 1, minor: 0 });
  // A node without its own impact takes its violation's.
  assert.deepEqual(read.axe_nodes, { critical: 2, serious: 2, moderate: 3, minor: 0 });
  assert.deepEqual(read.failing, ["color-contrast", "label", "region"]);
});

test("a page with no violation reads zero nodes and an empty list, never a missing one", () => {
  assert.deepEqual(axeReading({ violations: [] }), {
    axe: { critical: 0, serious: 0, moderate: 0, minor: 0 },
    axe_nodes: { critical: 0, serious: 0, moderate: 0, minor: 0 },
    failing: [],
  });
});

test("a category's failing list is its weighted audits scoring 0; the environment's are listed apart", () => {
  const read = lighthouseReading(
    lhr({ performance: PERFORMANCE, accessibility: ACCESSIBILITY, "best-practices": practices({ score: 0.74, failing: ["charset"] }) }),
  );

  assert.deepEqual(read.lighthouse, { performance: 0.97, accessibility: 0.83, "best-practices": 0.74 });
  // `list` scores 0 at weight 0 (not applicable): never failing. Performance has no list.
  assert.deepEqual(read.failing, {
    accessibility: ["color-contrast", "label"],
    best_practices: ["charset"],
    environment: ["is-on-https", "redirects-http"],
  });
  assert.deepEqual(read.errored, { accessibility: [], best_practices: [], environment: [] });
  // 20 of the 21 the app's audits weigh.
  assert.equal(read.best_practices_app, 0.95);
  assert.equal(read.best_practices_app_error, null);
});

test("the sandbox's plain HTTP leaves 21 of 27, and the app's best practices is 1", () => {
  const read = lighthouseReading(lhr({ "best-practices": practices({ score: 0.78 }) }));

  assert.equal(read.lighthouse["best-practices"], 0.78);
  assert.equal(read.best_practices_app, 1);
  assert.deepEqual(read.failing.best_practices, []);
  assert.deepEqual(ENVIRONMENT_AUDITS, ["is-on-https", "redirects-http"]);
});

test("an errored audit nulls its category's list, never reads it as passing, and is listed apart", () => {
  const read = lighthouseReading(
    lhr({
      accessibility: { ...ACCESSIBILITY, score: null, refs: [...ACCESSIBILITY.refs, ["aria-roles", 7, null]] },
      "best-practices": practices({ score: null, errored: ["is-on-https"] }),
    }),
  );

  assert.deepEqual(read.failing, { accessibility: null, best_practices: null, environment: null });
  assert.deepEqual(read.errored, { accessibility: ["aria-roles"], best_practices: [], environment: ["is-on-https"] });
  assert.equal(read.best_practices_app, null);
  assert.equal(read.best_practices_app_error, null);
});

test("best_practices_app is null, never 0, when no weight remains without the environment's audits", () => {
  const read = lighthouseReading(
    lhr({ "best-practices": { score: 0, refs: [["is-on-https", 5, 0], ["redirects-http", 1, 0], ["csp-xss", 0, 1]] } }),
  );

  assert.equal(read.best_practices_app, null);
  assert.equal(read.best_practices_app_error, null);
  assert.deepEqual(read.failing.environment, ["is-on-https", "redirects-http"]);
});

test("a category Lighthouse didn't return reads null, with no list", () => {
  const read = lighthouseReading({ categories: {}, audits: {} });

  assert.deepEqual(read.lighthouse, { performance: null, accessibility: null, "best-practices": null });
  assert.deepEqual(read.failing, { accessibility: null, best_practices: null, environment: null });
  assert.equal(read.best_practices_app, null);
});

test("a recomputation that isn't Lighthouse's own score is an error on that measure, not a reading", () => {
  const read = lighthouseReading(lhr({ "best-practices": practices({ score: 0.9 }) }));

  assert.equal(read.best_practices_app, null);
  assert.equal(read.best_practices_app_error, "recomputed 0.78 with the environment's audits, and Lighthouse scored 0.9");
  // The lists are still read: they don't depend on the recomputation.
  assert.deepEqual(read.failing.environment, ["is-on-https", "redirects-http"]);
});

test("a page's reading carries today's keys unchanged and the finer ones beside them", () => {
  const page = pageReading(
    "/notes",
    { violations: [{ id: "label", impact: "critical", nodes: [{ impact: "critical" }, { impact: "critical" }] }] },
    lhr({ performance: PERFORMANCE, accessibility: ACCESSIBILITY, "best-practices": practices({ score: 0.78 }) }),
  );

  assert.deepEqual(Object.keys(page), [
    "path",
    "lighthouse",
    "axe",
    "axe_nodes",
    "failing",
    "errored",
    "best_practices_app",
    "best_practices_app_error",
    "error",
  ]);
  assert.deepEqual(page.axe, { critical: 1, serious: 0, moderate: 0, minor: 0 });
  assert.deepEqual(page.axe_nodes, { critical: 2, serious: 0, moderate: 0, minor: 0 });
  assert.deepEqual(page.failing.axe, ["label"]);
  assert.equal(page.error, null);
});
