// SIP-0113's evaluator (A2, #2416). Reads one request on stdin, writes one result on stdout.
// Pages:
//   in:  {"base_url": "http://app:8000", "pages": ["/", "/runs/new"]}
//   out: {"pages": [{"path": "/", "lighthouse": {"performance": 0.98, ...}, "axe": {"critical": 0, ...},
//                    "axe_nodes": {...}, "failing": {...}, "errored": {...}, "best_practices_app": 1, ...}]}
// A page that can't be measured carries its error, and is never scored. What a scored page carries
// is page_reading.mjs's: from `-7`, §10y's finer reading beside the scores and rule counts.
// Lint (#1937's tools, rules and ESLint runner, all sent by the runner, so they have one source):
//   in:  {"lint": {"files": {"backend/main.py": "..."}, "ruff_args": ["check", ...], "eslint_runner": "..."}}
//   out: {"lint": {"root": "/tmp/lint-…", "ruff": {"version": "ruff 0.16.6", "exit": 0, "stdout": "[…]", "stderr": ""},
//                  "eslint": {"exit": 0, "stdout": "{…}", "stderr": ""}}}
// A tool with no file of its kind isn't run, and is null.
// A segment of a scenario's browser steps (SIP-0113 §10k, §10p; browser.mjs has the vocabulary):
//   in:  {"browse": {"base_url": "http://app:4173", "first_step": 2, "steps": [...],
//                    "checks": [{"index": 0, "check": {...}}], "deadline_s": 90}}
//   out: {"browse": {"browser": "HeadlessChrome/...", "steps": [{"step": 2, "outcome": "done", ...}],
//                    "checks": [{"index": 0, "holds": true, ...}], "evidence": null|{...},
//                    "timings": {"launch_s": 0.9, "total_s": 4.2}}}
// One container per segment, so each starts in a fresh browser, pinned to UTC, en-US and a
// 1280x800 viewport (Lighthouse's desktop setting).
// The app is addressed by its IP: Vite's preview server refuses a Host it doesn't know (read live on
// the Spark, 2026-10-18), and the app's name on the sandbox's app network is one.
// Chromium runs --no-sandbox: its own sandbox can't start with every capability dropped and
// no new privileges, so the container is the boundary.
import { execFile } from "node:child_process";
import { lookup } from "node:dns/promises";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import lighthouse from "lighthouse";
import puppeteer from "puppeteer-core";
import { AxePuppeteer } from "@axe-core/puppeteer";
import { runSegment } from "./browser.mjs";
import { CATEGORIES, pageReading } from "./page_reading.mjs";
import { PuppeteerPage } from "./puppeteer_page.mjs";

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function measure(browser, base, route) {
  const url = new URL(route, base).toString();
  const page = await browser.newPage();
  try {
    const response = await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });
    if (!response || !response.ok()) {
      // An error page is never scored: Lighthouse would read it as a page with no content.
      const status = response ? response.status() : "no response";
      return { path: route, lighthouse: null, axe: null, error: `answered ${status}` };
    }
    const axe = await new AxePuppeteer(page).analyze();
    const port = new URL(browser.wsEndpoint()).port;
    const run = await lighthouse(url, { port: Number(port), output: "json", logLevel: "error" }, {
      extends: "lighthouse:default",
      settings: { onlyCategories: CATEGORIES, formFactor: "desktop", screenEmulation: { disabled: true } },
    });
    const failed = run?.lhr?.runtimeError;
    if (!run?.lhr || failed) {
      // A page that painted nothing (NO_FCP), or a run that failed, is never scored: axe's numbers
      // would be an empty document's.
      return { path: route, lighthouse: null, axe: null, error: `lighthouse: ${failed?.code ?? "no result"}` };
    }
    return pageReading(route, axe, run.lhr);
  } catch (err) {
    return { path: route, lighthouse: null, axe: null, error: String(err?.message ?? err).slice(0, 500) };
  } finally {
    await page.close().catch(() => {});
  }
}

const TOOL_TIMEOUT_MS = 120000;

function tool(command, args, cwd) {
  // Completes with the tool's own exit code and output; a tool that can't start is exit 127.
  return new Promise((resolve) => {
    execFile(command, args, { cwd, timeout: TOOL_TIMEOUT_MS, maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
      const exit = err ? (typeof err.code === "number" ? err.code : err.killed ? 124 : 127) : 0;
      resolve({ exit, stdout: String(stdout), stderr: String(stderr || (err && !stdout ? err.message : "")) });
    });
  });
}

async function lint(request) {
  const root = await mkdtemp(path.join(tmpdir(), "lint-"));
  for (const [rel, content] of Object.entries(request.files ?? {})) {
    const target = path.resolve(root, rel);
    if (!target.startsWith(root + path.sep)) throw new Error(`a path outside the tree: ${rel}`);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }
  const names = Object.keys(request.files ?? {});
  const has = (suffixes) => names.some((n) => suffixes.some((s) => n.endsWith(s)));
  const out = { root, ruff: null, eslint: null };
  if (has([".py"])) {
    const version = await tool("ruff", ["--version"], root);
    out.ruff = { version: version.stdout.trim(), ...(await tool("ruff", request.ruff_args, root)) };
  }
  if (has([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"])) {
    // Outside the tree, so the runner is never linted as one of its files.
    const runner = path.join(await mkdtemp(path.join(tmpdir(), "runner-")), "delivered_lint_eslint.cjs");
    await writeFile(runner, request.eslint_runner, "utf8");
    out.eslint = await tool("node", [runner, root], root);
  }
  return out;
}

async function pages(request) {
  const base = new URL(request.base_url);
  base.hostname = (await lookup(base.hostname, { family: 4 })).address;
  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--remote-debugging-port=0"],
  });
  try {
    const measured = [];
    for (const p of request.pages ?? []) measured.push(await measure(browser, base.toString(), p));
    return measured;
  } finally {
    await browser.close();
  }
}

async function browse(request) {
  const base = new URL(request.base_url);
  base.hostname = (await lookup(base.hostname, { family: 4 })).address;
  const launched = Date.now();
  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--lang=en-US"],
    env: { ...process.env, TZ: "UTC", LANG: "en_US.UTF-8" },
  });
  try {
    const launch_s = (Date.now() - launched) / 1000;
    const page = await PuppeteerPage.open(browser);
    const answer = await runSegment(page, { ...request, base_url: base.toString() });
    return { browser: await browser.version(), ...answer, timings: { launch_s, ...answer.timings } };
  } finally {
    await browser.close();
  }
}

const request = await readStdin();
const result = request.lint
  ? { lint: await lint(request.lint) }
  : request.browse
    ? { browse: await browse(request.browse) }
    : { pages: await pages(request) };
process.stdout.write(JSON.stringify(result) + "\n");
