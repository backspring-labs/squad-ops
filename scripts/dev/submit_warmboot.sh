#!/bin/bash
# Submit WarmBoot request run-128

# Get repository root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

curl -X POST http://localhost:8000/warmboot/submit \
  -H "Content-Type: application/json" \
  -d @"$REPO_ROOT/warm-boot/examples/warmboot_request.json" | python3 -m json.tool

echo ""
echo "✅ WarmBoot request submitted!"
echo "📊 Monitor status: curl http://localhost:8000/warmboot/status/run-128"
echo "📝 View logs: docker-compose logs -f max neo"
