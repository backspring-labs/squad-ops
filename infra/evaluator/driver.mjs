// SIP-0113's evaluator (A2, #2416). Reads one request on stdin, writes one result on stdout:
//   in:  {"base_url": "http://app:8000", "pages": ["/", "/runs/new"]}
//   out: {"pages": [{"path": "/", "lighthouse": {"performance": 0.98, ...}, "axe": {"critical": 0, ...}}]}
// A page that can't be measured carries its error, and is never scored.
// Chromium runs --no-sandbox: its own sandbox can't start with every capability dropped and
// no new privileges, so the container is the boundary.
import lighthouse from "lighthouse";
import puppeteer from "puppeteer-core";
import { AxePuppeteer } from "@axe-core/puppeteer";

const IMPACTS = ["critical", "serious", "moderate", "minor"];
const CATEGORIES = ["performance", "accessibility", "best-practices"];

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function measure(browser, base, path) {
  const url = new URL(path, base).toString();
  const page = await browser.newPage();
  try {
    const response = await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });
    if (!response || !response.ok()) {
      // An error page is never scored: Lighthouse would read it as a page with no content.
      const status = response ? response.status() : "no response";
      return { path, lighthouse: null, axe: null, error: `answered ${status}` };
    }
    const axe = await new AxePuppeteer(page).analyze();
    const byImpact = Object.fromEntries(IMPACTS.map((i) => [i, 0]));
    for (const v of axe.violations) byImpact[v.impact ?? "minor"] += 1;
    const port = new URL(browser.wsEndpoint()).port;
    const run = await lighthouse(url, { port: Number(port), output: "json", logLevel: "error" }, {
      extends: "lighthouse:default",
      settings: { onlyCategories: CATEGORIES, formFactor: "desktop", screenEmulation: { disabled: true } },
    });
    const scores = Object.fromEntries(
      CATEGORIES.map((c) => [c, run?.lhr?.categories?.[c]?.score ?? null]),
    );
    return { path, lighthouse: scores, axe: byImpact, error: null };
  } catch (err) {
    return { path, lighthouse: null, axe: null, error: String(err?.message ?? err).slice(0, 500) };
  } finally {
    await page.close().catch(() => {});
  }
}

const request = await readStdin();
const browser = await puppeteer.launch({
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--remote-debugging-port=0"],
});
try {
  const pages = [];
  for (const path of request.pages ?? []) pages.push(await measure(browser, request.base_url, path));
  process.stdout.write(JSON.stringify({ pages }) + "\n");
} finally {
  await browser.close();
}
