#!/bin/bash
# Submit WarmBoot request run-128

curl -X POST http://localhost:8000/warmboot/submit \
  -H "Content-Type: application/json" \
  -d @warmboot_request.json | python3 -m json.tool

echo ""
echo "✅ WarmBoot request submitted!"
echo "📊 Monitor status: curl http://localhost:8000/warmboot/status/run-128"
echo "📝 View logs: docker-compose logs -f max neo"
