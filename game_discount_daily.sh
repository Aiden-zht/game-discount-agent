#!/bin/bash
# Game Discount Daily — Phase 1: Data Collection
# Run by Hermes cron as no_agent job
# Uses LOCAL mihomo proxy (127.0.0.1:7890 HTTP)

set -euo pipefail

WORKDIR="/mnt/data/daqian-ai-workshop/tools/game-discount-agent"
cd "$WORKDIR" || { echo "❌ ERROR: workdir not found"; exit 1; }

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
TODAY=$(date '+%Y%m%d')

echo "=== Phase 1: Data Collection ==="
echo "[$TIMESTAMP] Working dir: $WORKDIR"
echo "[$TIMESTAMP] Today: $TODAY"

# Check proxy
echo "[$TIMESTAMP] Checking local proxy (127.0.0.1:7890)..."
if curl -s --max-time 3 http://127.0.0.1:7890/status 2>/dev/null | grep -q "run"; then
    echo "[$TIMESTAMP] ✅ Local proxy (mihomo) is running on 7890"
else
    echo "[$TIMESTAMP] ⚠️  Local proxy check failed, trying 7891..."
    if curl -s --max-time 3 --proxy socks5://127.0.0.1:7891 https://httpbin.org/ip 2>/dev/null | grep -q "origin"; then
        echo "[$TIMESTAMP] ✅ SOCKS5 proxy on 7891 is working"
    else
        echo "[$TIMESTAMP] ⚠️  Proxy unavailable, will try without proxy"
    fi
fi

# Run Phase 1 pipeline
echo "[$TIMESTAMP] Running cron_digest.py..."
python3 cron_digest.py 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    # Find the state file
    STATE_FILE=$(ls -t output/state_${TODAY}*.json 2>/dev/null | head -1)
    HTML_FILE=$(ls -t output/digest_${TODAY}*.html 2>/dev/null | head -1)
    
    if [ -n "$STATE_FILE" ]; then
        echo "✅ State file: $STATE_FILE"
    else
        echo "❌ No state file generated"
        exit 1
    fi
    
    if [ -n "$HTML_FILE" ]; then
        echo "📄 HTML file: $HTML_FILE"
    fi
    
    echo "=== Phase 1 Complete (success) ==="
else
    echo "❌ Phase 1 FAILED (exit $EXIT_CODE)"
    exit $EXIT_CODE
fi
