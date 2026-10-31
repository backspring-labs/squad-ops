// What the evaluator reads of one page's axe and Lighthouse results (SIP-0113 §4.2, §10y; #2416,
// #2637). Pure: driver.mjs's `measure` hands it the two results, and page_reading.test.mjs reads it
// with no browser.
//
// Today's keys are kept unchanged: Lighthouse's three category scores (`best-practices` the raw
// one, read with the sandbox's plain HTTP), and axe's violated rules counted by impact. Beside them,
// from `-7` (§10y):
//   axe_nodes            the violating nodes per impact, one per (rule, element) pair, each under
//                        its own impact
//   failing              {accessibility, best_practices, environment, axe}: the failing ids, each
//                        sorted. A Lighthouse list is null when its category scored null
//   errored              {accessibility, best_practices, environment}: the weighted audits that
//                        errored, which are never read as passing or failing
//   best_practices_app   best practices without ENVIRONMENT_AUDITS, or null
//   best_practices_app_error   why it is null although its category scored, or null

export const IMPACTS = ["critical", "serious", "moderate", "minor"];
export const CATEGORIES = ["performance", "accessibility", "best-practices"];

// The audits that fail on every instance the sandbox serves, whatever the app does: it serves each
// one over plain HTTP, so the page is never on HTTPS and nothing redirects it there (§10y item 3).
export const ENVIRONMENT_AUDITS = ["is-on-https", "redirects-http"];

// The categories with a failing list, by the key the reading keeps. Performance has none: its
// weighted audits are its five metrics, which score continuously, so "failing" would be noise.
const LISTED = { accessibility: "accessibility", "best-practices": "best_practices" };

const sorted = (ids) => [...new Set(ids)].sort();

// The category's audits that count toward its score: Lighthouse has already zeroed the weight of
// a not-applicable, informative or manual audit in the result's own `auditRefs`.
function weighted(lhr, category) {
  return (lhr.categories?.[category]?.auditRefs ?? [])
    .filter((ref) => ref.weight > 0)
    .map((ref) => ({ id: ref.id, weight: ref.weight, score: lhr.audits?.[ref.id]?.score ?? null }));
}

// Lighthouse's own category score (core/scoring.js `arithmeticMean`): the weighted mean, null when
// a weighted audit scored null, rounded to two decimals. `weight` is what the items carried, so a
// caller can tell Lighthouse's 0 for no weight from a score of 0.
function mean(items) {
  if (items.some((item) => item.score === null)) return { score: null, weight: 0 };
  let weight = 0;
  let sum = 0;
  for (const item of items) {
    weight += item.weight;
    sum += item.score * item.weight;
  }
  return { score: Math.round((sum / weight || 0) * 100) / 100, weight };
}

export function axeReading(results) {
  const rules = Object.fromEntries(IMPACTS.map((i) => [i, 0]));
  const nodes = Object.fromEntries(IMPACTS.map((i) => [i, 0]));
  for (const violation of results.violations ?? []) {
    rules[violation.impact ?? "minor"] += 1;
    for (const node of violation.nodes ?? []) nodes[node.impact ?? violation.impact ?? "minor"] += 1;
  }
  return { axe: rules, axe_nodes: nodes, failing: sorted((results.violations ?? []).map((v) => v.id)) };
}

export function lighthouseReading(lhr) {
  const scores = Object.fromEntries(CATEGORIES.map((c) => [c, lhr.categories?.[c]?.score ?? null]));
  const environment = (ref) => ENVIRONMENT_AUDITS.includes(ref.id);
  const failing = {};
  const errored = {};
  for (const [category, key] of Object.entries(LISTED)) {
    const refs = weighted(lhr, category).filter((ref) => !environment(ref));
    failing[key] = scores[category] === null ? null : sorted(refs.filter((r) => r.score === 0).map((r) => r.id));
    errored[key] = sorted(refs.filter((r) => r.score === null).map((r) => r.id));
  }
  const practices = weighted(lhr, "best-practices");
  const env = practices.filter(environment);
  failing.environment = scores["best-practices"] === null ? null : sorted(env.filter((r) => r.score === 0).map((r) => r.id));
  errored.environment = sorted(env.filter((r) => r.score === null).map((r) => r.id));

  let app = null;
  let appError = null;
  if (scores["best-practices"] !== null) {
    const all = mean(practices).score;
    const without = mean(practices.filter((ref) => !environment(ref)));
    if (all !== scores["best-practices"]) {
      // Recomputed the same way with the environment's audits in, it must be Lighthouse's own
      // score; where it isn't, the recomputation is wrong for this result, and isn't a reading.
      appError = `recomputed ${all} with the environment's audits, and Lighthouse scored ${scores["best-practices"]}`;
    } else if (without.weight > 0) {
      app = without.score;
    }
  }
  return { lighthouse: scores, failing, errored, best_practices_app: app, best_practices_app_error: appError };
}

// One scored page's reading, from its axe results and its Lighthouse result.
export function pageReading(path, axeResults, lhr) {
  const a = axeReading(axeResults);
  const l = lighthouseReading(lhr);
  return {
    path,
    lighthouse: l.lighthouse,
    axe: a.axe,
    axe_nodes: a.axe_nodes,
    failing: { ...l.failing, axe: a.failing },
    errored: l.errored,
    best_practices_app: l.best_practices_app,
    best_practices_app_error: l.best_practices_app_error,
    error: null,
  };
}
