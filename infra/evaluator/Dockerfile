# SIP-0113's evaluator image (A2, #2416): Lighthouse and axe per declared page, and later the
# browser's scenario steps. The sandbox's scenario runner launches it beside the app it measures.
# Chromium is Debian's (arm64 and amd64 alike); no browser is ever downloaded at build or run time.
FROM node:20-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

ENV CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1

WORKDIR /evaluator
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY driver.mjs ./

USER node
ENTRYPOINT ["node", "/evaluator/driver.mjs"]
