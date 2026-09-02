#!/bin/sh
set -e

# Start uvicorn in the background, then foreground nginx.
# nginx starts last so it proxies to an already-running backend.

echo "[start] launching backend on :8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Brief wait for uvicorn to be ready
sleep 2

echo "[start] launching nginx ..."
nginx -g 'daemon off;'