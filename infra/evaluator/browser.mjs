// SIP-0113 §10k, §10p: one segment of a scenario's browser steps, and the checks that read them,
// run against a page. The vocabulary lives here; the browser lives behind the page interface
// (puppeteer_page.mjs), so a change of driver changes that module and the image's tag, and
// nothing here, in the runner, or in the suite's vocabulary.
//
// The page interface:
//   load(url, timeoutMs) -> status               find(role) -> [{name, text, visible, disabled}]
//   fill(element, value)    click(element)        related(a, b) -> {sameForm, depth}
//   stable(element) -> bool settle(idleMs, timeoutMs) -> bool
//   bodyText() -> string    axEmpty() -> bool     exceptions() -> count of uncaught page errors
//   errors() -> [string]    failedRequests() -> [string]   screenshot() -> base64 PNG
//
// A step ends `done`, `not_found` (none of its names found a control: the scenario reads
// `control_absent`, never failed), `action_failed`, `timeout` or `page_broken`. A check reads the
// page right after its step. What a check saw never quotes the page: the page shows the
// scenario's own values, which are held out, so only the evidence carries it.

export const BOUNDS = {
  navigateMs: 30000,
  locateMs: 10000,
  checkMs: 10000,
  settleIdleMs: 500,
  settleMs: 5000,
  pollMs: 100,
};
const CAPS = { nodes: 200, nodesBytes: 64 * 1024, errors: 50, errorChars: 500, failedRequests: 50 };

export const fold = (value) =>
  String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/\s+/g, " ")
    .trim();

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Patterns are drafted as the suite's own text and read here as JavaScript regular expressions,
// without the `u` flag, so a value Python escaped (`\ `, `\-`) reads as the character it escapes.
const pattern = (source) => new RegExp(source);

async function poll(bound, deadline, read, bounds) {
  const until = Math.min(Date.now() + bound, deadline);
  for (;;) {
    const value = await read();
    if (value.done || Date.now() >= until) return value;
    await sleep(bounds.pollMs);
  }
}

function narrowed(elements, target) {
  const text = target.text ? fold(target.text) : null;
  return text ? elements.filter((e) => fold(e.text).includes(text)) : elements;
}

// Every element a check's target selects: its role, and its names and text when it gives them.
export async function select(page, target) {
  const pool = narrowed(await page.find(target.role), target);
  if (!target.names) return pool;
  const wanted = new Set(target.names.map(fold));
  return pool.filter((e) => wanted.has(fold(e.name)));
}

// The control a step acts on (§10p ruling 3): the first candidate name that matches any element,
// exactly after case-folding; its first match in document order; or, with `near`, the match that
// shares a form with the near control, else the one under their deepest common ancestor.
export async function locate(page, target) {
  const pool = narrowed(await page.find(target.role), target);
  let hits = [];
  let nameIndex = null;
  for (const [i, name] of (target.names ?? []).entries()) {
    hits = pool.filter((e) => fold(e.name) === fold(name));
    if (hits.length) {
      nameIndex = i;
      break;
    }
  }
  if (!hits.length) return { element: null, matched: null };
  let element = hits[0];
  if (target.near && hits.length > 1) {
    const near = await locate(page, target.near);
    if (!near.element) return { element: null, matched: null };
    let best = null;
    for (const hit of hits) {
      const r = await page.related(hit, near.element);
      const rank = (r.sameForm ? 1e6 : 0) + r.depth;
      if (best === null || rank > best.rank) best = { hit, rank };
    }
    element = best.hit;
  }
  return { element, matched: { name_index: nameIndex, count: hits.length } };
}

async function act(page, step, bounds, deadline) {
  const found = await poll(
    bounds.locateMs,
    deadline,
    async () => {
      const { element, matched } = await locate(page, step.target);
      const usable =
        element && element.visible && !element.disabled && (await page.stable(element));
      return { done: Boolean(usable), element, matched };
    },
    bounds,
  );
  if (!found.element) return { outcome: "not_found", matched: null };
  if (!found.done) {
    const why = found.element.disabled ? "disabled" : "not visible or still moving";
    return { outcome: "action_failed", detail: `the control was ${why}`, matched: found.matched };
  }
  if (step.action === "fill") await page.fill(found.element, step.value);
  else await page.click(found.element);
  const settled = await page.settle(bounds.settleIdleMs, Math.min(bounds.settleMs, deadline - Date.now()));
  return { outcome: "done", matched: found.matched, settled };
}

async function runStep(page, step, baseUrl, bounds, deadline) {
  if (Date.now() >= deadline) return { outcome: "timeout", detail: "the segment's deadline passed" };
  const before = page.exceptions();
  let result;
  if (step.action === "visit") {
    const status = await page.load(new URL(step.path, baseUrl).toString(), Math.min(bounds.navigateMs, deadline - Date.now()));
    if (!(status >= 200 && status < 300)) return { outcome: "page_broken", detail: `answered ${status}` };
    if (await page.axEmpty()) return { outcome: "page_broken", detail: "the page rendered nothing" };
    result = { outcome: "done" };
  } else {
    result = await act(page, step, bounds, deadline);
  }
  if (result.outcome === "done" && page.exceptions() > before) {
    return { outcome: "page_broken", detail: "the page raised an uncaught exception" };
  }
  return result;
}

async function readCheck(page, check, bounds, deadline) {
  const kind = check.check;
  if (kind === "absent") {
    const matched = pattern(check.pattern).test(await page.bodyText());
    return { holds: !matched, seen: matched ? "a text the scenario rules out is on the page" : null };
  }
  const read = {
    text: async () => {
      const done = pattern(check.pattern).test(await page.bodyText());
      return { done, seen: "no text matched the pattern" };
    },
    count: async () => {
      const n = (await select(page, check.target)).length;
      return { done: n === check.equals, seen: `${n} elements, not ${check.equals}` };
    },
    order: async () => {
      const texts = (await select(page, check.target)).map((e) => e.text);
      let at = -1;
      const places = [];
      for (const p of check.patterns) {
        const re = pattern(p);
        at = texts.findIndex((t, i) => i > at && re.test(t));
        places.push(at);
        if (at < 0) break;
      }
      const done = places.length === check.patterns.length && places.every((i) => i >= 0);
      return { done, seen: `in ${texts.length} elements, the patterns were found at ${JSON.stringify(places)}` };
    },
    control: async () => {
      const { element } = await locate(page, check.target);
      const state = element && element.visible && !element.disabled ? "enabled" : "unavailable";
      return { done: state === check.is, seen: `the control is ${state}` };
    },
  }[kind];
  if (!read) return { holds: false, seen: `no reading for a ${kind} check` };
  const result = await poll(bounds.checkMs, deadline, read, bounds);
  return { holds: result.done, seen: result.done ? null : result.seen };
}

async function capture(page, step, role, failure = null) {
  const nodes = [];
  let bytes = 0;
  if (role) {
    for (const e of (await page.find(role)).slice(0, CAPS.nodes)) {
      const node = { name: e.name, visible: e.visible, disabled: e.disabled };
      bytes += JSON.stringify(node).length;
      if (bytes > CAPS.nodesBytes) break;
      nodes.push(node);
    }
  }
  let png = null;
  try {
    png = await page.screenshot();
  } catch {
    // a page that can't be photographed still gives its other evidence
  }
  return {
    step,
    png_b64: png,
    role: role ?? null,
    nodes,
    // The driver's own failure first: an error's text can quote a pattern or the page, so it is
    // the evidence's, never what a step's detail or a check's reading says (§10p ruling 1).
    errors: [...(failure ? [`driver: ${failure}`] : []), ...page.errors()]
      .slice(-CAPS.errors)
      .map((s) => String(s).slice(0, CAPS.errorChars)),
    failed_requests: page.failedRequests().slice(-CAPS.failedRequests),
  };
}

// The segment: each step in turn, each check right after its step, and the evidence of the first
// step or check that didn't end as it should. A step that doesn't end `done` ends the segment.
export async function runSegment(page, request, bounds = BOUNDS) {
  const started = Date.now();
  const deadline = started + request.deadline_s * 1000;
  const byStep = new Map();
  for (const c of request.checks ?? []) {
    const n = c.check.step;
    byStep.set(n, [...(byStep.get(n) ?? []), c]);
  }
  const steps = [];
  const checks = [];
  let evidence = null;
  for (const [offset, step] of request.steps.entries()) {
    const n = request.first_step + offset;
    const t0 = Date.now();
    let result;
    try {
      result = await runStep(page, step, request.base_url, bounds, deadline);
    } catch (err) {
      const timedOut = err?.name === "TimeoutError" || Date.now() >= deadline;
      result = {
        outcome: timedOut ? "timeout" : "action_failed",
        detail: err?.name ?? "Error",
        failure: String(err?.message ?? err).slice(0, 300),
      };
    }
    steps.push({ step: n, outcome: result.outcome, detail: result.detail ?? null, matched: result.matched ?? null, settled: result.settled ?? null, seconds: (Date.now() - t0) / 1000 });
    if (result.outcome !== "done") {
      evidence = await capture(page, n, step.target?.role, result.failure ?? null);
      break;
    }
    for (const c of byStep.get(n) ?? []) {
      const c0 = Date.now();
      let read;
      let failure = null;
      try {
        read = await readCheck(page, c.check, bounds, deadline);
      } catch (err) {
        // A pattern's SyntaxError quotes the pattern, which is held out: only the evidence keeps it.
        failure = String(err?.message ?? err).slice(0, 300);
        read = { holds: false, seen: "the check couldn't be read" };
      }
      checks.push({ index: c.index, holds: read.holds, seen: read.seen, waited_s: (Date.now() - c0) / 1000 });
      if (!read.holds && evidence === null) evidence = await capture(page, n, c.check.target?.role, failure);
    }
  }
  return { steps, checks, evidence, timings: { total_s: (Date.now() - started) / 1000 } };
}
