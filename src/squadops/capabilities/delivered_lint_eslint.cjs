// Reporting-only ESLint over a delivered app's JS/TS (#1937). Run as: node delivered_lint_eslint.cjs <root>
//
// ESLint and its configs resolve from the global npm root the qa image installs them into
// (agents/instances/qa/npm-global-packages.txt), or from DELIVERED_LINT_MODULES where it is set:
// the evaluator's image keeps them in its own lock (SIP-0113 §4.2, #2416). The config is this
// file's alone, so nothing in the delivered tree decides what is linted or how. Prints one JSON
// document:
// {"version": "<eslint version>", "results": [{"file": "<relative path>", "rules": ["<rule id>", ...]}]}
// A message with no rule is a parse error, reported as "parse-error".
"use strict";

const { execFileSync } = require("child_process");
const path = require("path");
const { createRequire } = require("module");

const root = path.resolve(process.argv[2] || ".");
const moduleRoot =
  process.env.DELIVERED_LINT_MODULES ||
  execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
const fromGlobal = createRequire(path.join(moduleRoot, "delivered-lint.js"));
const { ESLint } = fromGlobal("eslint");
const js = fromGlobal("@eslint/js");
const tseslint = fromGlobal("typescript-eslint");
const globals = fromGlobal("globals");

async function main() {
  const eslint = new ESLint({
    cwd: root,
    overrideConfigFile: true,
    overrideConfig: [
      { ignores: ["**/node_modules/**", "**/.next/**", "**/dist/**", "**/build/**"] },
      js.configs.recommended,
      ...tseslint.configs.recommended,
      {
        // #2478: named, or a flat-config object applies to .js/.mjs/.cjs alone and no config
        // lints a .jsx file: the canonical stack's whole React UI went unread.
        files: ["**/*.{js,jsx,mjs,cjs,ts,tsx}"],
        languageOptions: {
          ecmaVersion: "latest",
          sourceType: "module",
          globals: { ...globals.browser, ...globals.node },
          parserOptions: { ecmaFeatures: { jsx: true } },
        },
      },
    ],
    errorOnUnmatchedPattern: false,
  });
  const results = await eslint.lintFiles(["**/*.{js,jsx,mjs,cjs,ts,tsx}"]);
  process.stdout.write(
    JSON.stringify({
      version: ESLint.version,
      results: results.map((r) => ({
        file: path.relative(root, r.filePath).split(path.sep).join("/"),
        rules: r.messages.map((m) => m.ruleId || (m.fatal ? "parse-error" : "unknown")),
      })),
    }),
  );
}

main().catch((e) => {
  process.stderr.write(String((e && e.stack) || e));
  process.exit(2);
});
