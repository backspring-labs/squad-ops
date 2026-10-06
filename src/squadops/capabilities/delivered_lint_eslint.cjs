// Reporting-only ESLint over a delivered app's JS/TS (#1937). Run as: node delivered_lint_eslint.cjs <root>
//
// ESLint and its configs resolve from the global npm root the qa image installs them into
// (agents/instances/qa/npm-global-packages.txt), and the config is this file's alone, so nothing
// in the delivered tree decides what is linted or how. Prints one JSON document:
// {"version": "<eslint version>", "results": [{"file": "<relative path>", "rules": ["<rule id>", ...]}]}
// A message with no rule is a parse error, reported as "parse-error".
"use strict";

const { execFileSync } = require("child_process");
const path = require("path");
const { createRequire } = require("module");

const root = path.resolve(process.argv[2] || ".");
const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
const fromGlobal = createRequire(path.join(globalRoot, "delivered-lint.js"));
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
