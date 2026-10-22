# SIP-0113's evaluator image (A2, #2416): Lighthouse and axe per declared page, #1937's lint over
# the evaluated tree, and a scenario's browser steps (§10k, §10p). The sandbox's scenario runner
# launches it beside the app it measures. Chromium is Debian's (arm64 and amd64 alike); no browser
# is ever downloaded at build or run time.
#
# One tag is one image (#2583): the base is pinned by its multi-platform index digest, and apt reads a
# dated snapshot of Debian's archives, so every package (Chromium's version and its libraries alike)
# resolves as it did when the tag was cut. Moving either is a new tag. 20261022T050000Z is the last
# import before `-4` was built (2026-10-22T05:51Z), so `-5`'s packages are `-4`'s (#2583).
#
# #1937's tools at #1937's versions, so the two readings are one measure: ruff from its own image,
# pinned by digest to the version requirements/agent.lock pins, and ESLint's packages in the lock
# beside Lighthouse's (test_evaluator_image.py keeps both equal to the qa image's).
FROM ghcr.io/astral-sh/ruff:0.16.6@sha256:77e0110c04fdfdd7c97657a680aad0faa7c7d2161556d698695e87d608071ac2 AS ruff

FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0

ARG DEBIAN_SNAPSHOT=20261022T050000Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: http://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: http://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      /etc/apt/sources.list.d/debian.sources \
 && ! grep -q "deb.debian.org" /etc/apt/sources.list.d/debian.sources \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends \
      chromium=155.0.8059.79-1~deb12u1 chromium-common=155.0.8059.79-1~deb12u1 fonts-liberation=1:1.07.4-11 \
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
