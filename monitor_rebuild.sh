#!/bin/bash
# Monitor rebuild and deploy progress

LOG_FILE="rebuild_deploy.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "No log file found. Run ./rebuild_and_deploy.sh first."
    exit 1
fi

echo "📊 Monitoring rebuild progress..."
echo "Press Ctrl+C to stop monitoring"
echo ""
echo "Last 20 lines of log (updates every 2 seconds):"
echo "================================================"

while true; do
    clear
    echo "📊 Rebuild & Deploy Monitor - $(date)"
    echo "================================================"
    tail -20 "$LOG_FILE" 2>/dev/null || echo "Waiting for log file..."
    sleep 2
done
