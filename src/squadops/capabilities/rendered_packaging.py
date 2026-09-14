"""The container packaging a stack ships, rendered from its declaration (#598, SIP-0105 A1).

SIP-0102 §4.2 put it in one line: the environment definition is the contract, and a
Dockerfile is an adapter rendering of it — "checked in, deterministic, never LLM-authored."
Until this module the builder role authored the packaging on every roll instead. pf-38 went
green with a container that could not build or run; pf-39 drew two of the same three defects
from identical seeds; ``container_packaging`` (1.7.1) banked them reporting-only on every roll
since. A defect a template never makes twice was being sampled per cycle.

So both stacks now emit their packaging as scaffold-owned, frozen files, beside the baseline
stylesheet and for the same reason: nothing the fill author writes changes what they must say.

**What each stack's set is, and what it is rendered from.** The environment contract
(``squadops.sandbox.environment``) supplies the runtime versions and the application port;
the stack's own layout supplies the paths. The templates below hold only what no declaration
carries yet — the image family and the nginx wiring — and each is written against the three
findings ``squadops.cycles.container_packaging`` reads, which a unit test runs over every
rendering:

* ``npm install``, never ``npm ci``: an offline-deterministic expansion emits no lockfile,
  and ``npm ci`` refuses to run without one (the sandbox contract says the same).
* nothing is copied out of ``dist-packages``: dependencies install in the final stage.
* apt's nginx default site is removed before the app's server block is installed.

**What this does not assert.** The image is not built here or in CI: ``package_builds`` stays
declared unbuilt, because building needs a Docker-capable locus. The renderings were built and
run by hand against accepted deliverables when this landed, and the PR records it.
"""

from __future__ import annotations

from collections.abc import Callable

#: The header every rendered packaging file carries, in that file's comment syntax.
_OWNED = (
    "Rendered by the scaffold from the stack's environment contract (#598). Frozen — do not edit."
)


def _tool_version(stack: str, tool: str) -> str:
    """The declared version prefix of ``tool`` for ``stack``; raises when it is not declared."""
    from squadops.sandbox.environment import get_environment_contract

    versions = dict(get_environment_contract(stack).required_tools)
    if tool not in versions:
        raise ValueError(f"stack {stack!r} declares no {tool!r} version to render packaging from")
    return versions[tool]


def _app_port(stack: str) -> int:
    from squadops.sandbox.environment import get_environment_contract

    return get_environment_contract(stack).app_port


def _fullstack_fastapi_react() -> list[dict[str, str]]:
    """One container: the Vite build served by nginx, ``/api`` proxied to uvicorn.

    The prefix is stripped at the proxy because the router takes none (SIP-0105 register
    entry 7) and the dev server's proxy strips it the same way (``frontend/vite.config.js``).
    Unknown paths fall back to ``index.html`` because the app routes client-side.
    """
    stack = "fullstack_fastapi_react"
    python, node, port = (
        _tool_version(stack, "python"),
        _tool_version(stack, "node"),
        _app_port(stack),
    )
    dockerfile = f"""# {_OWNED}
FROM node:{node}-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:{python}-slim
WORKDIR /app
RUN apt-get update \\
    && apt-get install -y --no-install-recommends nginx \\
    && rm -rf /var/lib/apt/lists/* \\
    && rm -f /etc/nginx/sites-enabled/default
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/app.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 80
CMD ["/start.sh"]
"""
    nginx = f"""# {_OWNED}
server {{
    listen 80 default_server;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {{
        proxy_pass http://127.0.0.1:{port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""
    start = f"""#!/bin/sh
# {_OWNED}
set -e
python -m uvicorn backend.main:app --host 127.0.0.1 --port {port} &
exec nginx -g 'daemon off;'
"""
    return [
        {"name": "Dockerfile", "content": dockerfile},
        {"name": "nginx.conf", "content": nginx},
        {"name": "start.sh", "content": start},
        {
            "name": ".dockerignore",
            "content": _dockerignore("frontend/node_modules", "frontend/dist"),
        },
    ]


def _nextjs_ts() -> list[dict[str, str]]:
    """One container running ``next start``, built in a stage with the dev dependencies.

    The runtime stage copies the build output, the dependency tree and the two files
    ``next start`` reads at startup; the scaffold's config is JavaScript, so no TypeScript
    toolchain is needed to start.
    """
    stack = "nextjs_ts"
    node, port = _tool_version(stack, "node"), _app_port(stack)
    dockerfile = f"""# {_OWNED}
FROM node:{node}-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npx next build

FROM node:{node}-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json /app/next.config.mjs ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
EXPOSE {port}
CMD ["npx", "next", "start", "--hostname", "0.0.0.0", "--port", "{port}"]
"""
    return [
        {"name": "Dockerfile", "content": dockerfile},
        {"name": ".dockerignore", "content": _dockerignore("node_modules", ".next")},
    ]


def _dockerignore(*derived: str) -> str:
    """Keep derived trees out of the build context, so the image builds what it installs."""
    return f"# {_OWNED}\n" + "".join(f"{path}\n" for path in (*derived, ".git"))


#: The stacks whose packaging is rendered — one entry per registered stack.
_RENDERERS: dict[str, Callable[[], list[dict[str, str]]]] = {
    "fullstack_fastapi_react": _fullstack_fastapi_react,
    "nextjs_ts": _nextjs_ts,
}

#: Every path a rendering emits, across stacks — the files a role no longer authors.
RENDERED_PACKAGING_PATHS: frozenset[str] = frozenset(
    {"Dockerfile", "nginx.conf", "start.sh", ".dockerignore"}
)


def render_packaging(stack: str) -> list[dict[str, str]]:
    """The frozen packaging files for ``stack``, as ``{"name", "content"}`` scaffold files.

    Raises:
        ValueError: ``stack`` has no rendering. There is no default packaging: a stack that
            expands must declare how it ships.
    """
    renderer = _RENDERERS.get(stack)
    if renderer is None:
        raise ValueError(
            f"no packaging rendering for stack {stack!r} (known: {sorted(_RENDERERS)})"
        )
    return renderer()
