#!/bin/bash
# Quick status check of rebuild process

# Get repository root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="$REPO_ROOT/rebuild_deploy.log"

echo "📊 Quick Status Check"
echo "===================="
echo ""

# Check if script is running
if pgrep -f "scripts/dev/ops/rebuild_and_deploy.sh" > /dev/null; then
    echo "✅ Rebuild script is running"
    echo ""
    echo "Last 10 lines of log:"
    tail -10 rebuild_deploy.log 2>/dev/null || echo "  (No log yet)"
else
    echo "⚠️  Rebuild script is not running"
    if [ -f rebuild_deploy.log ]; then
        echo ""
        echo "Last status from log:"
        tail -5 rebuild_deploy.log
    fi
fi

echo ""
echo "Container status:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}" | head -15
