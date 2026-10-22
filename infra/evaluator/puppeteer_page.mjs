// The page interface browser.mjs reads (SIP-0113 §10p ruling 1), on Puppeteer and the image's
// Chromium. Elements are found the way a user finds them: by the role Chromium's accessibility tree
// computes, with the accessible name it computes; never by a test id or a CSS selector.

export class PuppeteerPage {
  static async open(browser) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    return new PuppeteerPage(page);
  }

  constructor(page) {
    this.page = page;
    this._exceptions = [];
    this._console = [];
    this._failed = [];
    page.on("pageerror", (err) => this._exceptions.push(`uncaught: ${err?.message ?? err}`));
    page.on("console", (m) => {
      if (m.type() === "error") this._console.push(`console: ${m.text()}`);
    });
    page.on("requestfailed", (r) => {
      let where = r.url();
      try {
        where = new URL(where).pathname;
      } catch {
        // keep the URL as given
      }
      this._failed.push(`${r.method()} ${where}: ${r.failure()?.errorText ?? "failed"}`);
    });
  }

  async load(url, timeoutMs) {
    const response = await this.page.goto(url, {
      waitUntil: "networkidle0",
      timeout: Math.max(1, timeoutMs),
    });
    return response ? response.status() : 0;
  }

  async find(role) {
    const handles = await this.page.$$(`::-p-aria([role=${JSON.stringify(role)}])`);
    const out = [];
    for (const handle of handles) {
      const node = await this.page.accessibility.snapshot({ root: handle, interestingOnly: false });
      const props = await handle.evaluate((e) => ({
        text: e.innerText ?? e.textContent ?? "",
        disabled: Boolean(e.disabled) || e.getAttribute("aria-disabled") === "true",
      }));
      out.push({
        handle,
        name: node?.name ?? "",
        text: props.text,
        disabled: props.disabled,
        visible: await handle.isVisible(),
      });
    }
    return out;
  }

  async related(a, b) {
    return a.handle.evaluate(
      (x, y) => {
        const fx = x.closest("form");
        let depth = 0;
        for (let n = x; n; n = n.parentElement) {
          if (n.contains(y)) {
            for (let m = n; m; m = m.parentElement) depth += 1;
            break;
          }
        }
        return { sameForm: Boolean(fx) && fx === y.closest("form"), depth };
      },
      b.handle,
    );
  }

  async stable(element) {
    const first = await element.handle.boundingBox();
    await new Promise((resolve) => setTimeout(resolve, 50));
    const second = await element.handle.boundingBox();
    return Boolean(first && second) && JSON.stringify(first) === JSON.stringify(second);
  }

  async fill(element, value) {
    await element.handle.evaluate((e) => {
      e.focus();
      if (typeof e.select === "function") e.select();
    });
    await element.handle.type(value);
  }

  async click(element) {
    await element.handle.click();
  }

  async settle(idleMs, timeoutMs) {
    if (timeoutMs <= 0) return false;
    try {
      await this.page.waitForNetworkIdle({ idleTime: idleMs, timeout: timeoutMs });
      return true;
    } catch {
      return false; // an app that polls never idles: best effort, never a failure
    }
  }

  async bodyText() {
    return this.page.evaluate(() => document.body?.innerText ?? "");
  }

  async axEmpty() {
    const root = await this.page.accessibility.snapshot();
    return !root || !(root.children ?? []).length;
  }

  exceptions() {
    return this._exceptions.length;
  }

  errors() {
    return [...this._exceptions, ...this._console];
  }

  failedRequests() {
    return [...this._failed];
  }

  async screenshot() {
    return this.page.screenshot({ type: "png", encoding: "base64" });
  }
}
