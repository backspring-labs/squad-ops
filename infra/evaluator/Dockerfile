# SIP-0113's evaluator image (A2, #2416): Lighthouse and axe per declared page, #1937's lint over
# the evaluated tree, and a scenario's browser steps (§10k, §10p). The sandbox's scenario runner
# launches it beside the app it measures. Chromium is Debian's (arm64 and amd64 alike); no browser
# is ever downloaded at build or run time.
#
# #1937's tools at #1937's versions, so the two readings are one measure: ruff from its own image,
# pinned by digest to the version requirements/agent.lock pins, and ESLint's packages in the lock
# beside Lighthouse's (test_evaluator_image.py keeps both equal to the qa image's).
FROM ghcr.io/astral-sh/ruff:0.16.6@sha256:77e0110c04fdfdd7c97657a680aad0faa7c7d2161556d698695e87d608071ac2 AS ruff

FROM node:20-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

ENV CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    DELIVERED_LINT_MODULES=/evaluator/node_modules

COPY --from=ruff /ruff /usr/local/bin/ruff

WORKDIR /evaluator
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY driver.mjs browser.mjs puppeteer_page.mjs ./

USER node
ENTRYPOINT ["node", "/evaluator/driver.mjs"]
