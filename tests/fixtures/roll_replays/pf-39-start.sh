#!/bin/sh
# Start FastAPI backend in the background
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Start Nginx in the foreground
nginx -g 'daemon off;'