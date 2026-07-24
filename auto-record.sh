#!/usr/bin/env bash
set -euo pipefail

# RepFind Auto-Record Pipeline
# Called by n8n 3x/day to record a new product demo and post to TikTok
# Picks a random product, updates config, records, outputs JSON for caption generation

BASE="/Users/jackserver/repfind"
CONFIG="$BASE/recording-config.js"
OUTPUT_MP4="$BASE/output/repfind-mobile-screen-recording.mp4"
LOG_FILE="$BASE/output/auto-record.log"

mkdir -p "$BASE/output"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== RepFind Auto-Record Start ==="

# 1. Pick a random product from the catalog
PRODUCT_JSON=$(python3 << 'PYEOF'
import json, random

with open('/Users/jackserver/repfind/data/products.json') as f:
    products = json.load(f)

# Filter for products with real images, IDs, and meaningful titles
good = []
for p in products:
    if len(p) < 6:
        continue
    title = p[0]
    pid = p[5]
    img = p[3]
    if not title or not pid or not img:
        continue
    if 'picsum' in img:
        continue
    good.append(p)

pick = random.choice(good)
print(json.dumps({
    'title': pick[0],
    'price': pick[1],
    'image': pick[3],
    'source': pick[4],
    'id': pick[5]
}))
PYEOF
)

TITLE=$(echo "$PRODUCT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])")
PRODUCT_ID=$(echo "$PRODUCT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
PRICE=$(echo "$PRODUCT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['price'])")

# Use first 2 words as search term (strip generic prefixes)
SEARCH_TERM=$(python3 -c "
import re
title = '''$TITLE'''.strip()
title = re.sub(r'^(Design|Replica)\s+', '', title)
words = title.split()
print(' '.join(words[:2]))
")

log "Selected: $TITLE (ID: $PRODUCT_ID, ¥$PRICE)"
log "Search term: $SEARCH_TERM"

# 2. Update recording-config.js
# No selectedProductId — let the runner auto-pick a non-first result
# No verifyLiveKakobuy — keep it local, faster, no network dependency
chmod 644 "$CONFIG" 2>/dev/null || true
cat > "$CONFIG" << EOF
/*
 * Repfind recording configuration — auto-generated
 * Product context: $TITLE
 * Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
 */
const recordingConfig = {
  searchTerm: '$SEARCH_TERM',
  verifyLiveKakobuy: false
};

if (typeof module !== 'undefined' && module.exports) module.exports = recordingConfig;
if (typeof window !== 'undefined') window.REPFIND_RECORDING_CONFIG = recordingConfig;
EOF
chmod 444 "$CONFIG"

log "Config updated"

# 3. Ensure the static server is running (managed by launchd: com.repfind.recording-server)
#    Health check with retry — if launchd hasn't started it yet, kick it
for i in 1 2 3 4 5; do
  if curl -s -o /dev/null http://127.0.0.1:4173/ 2>/dev/null; then
    break
  fi
  log "Recording server not responding (attempt $i/5), waiting..."
  sleep 2
done

if ! curl -s -o /dev/null http://127.0.0.1:4173/ 2>/dev/null; then
  log "ERROR: Recording server unreachable after 5 retries"
  echo "ERROR: Recording server not running on :4173"
  exit 1
fi

# 4. Run the recording
log "Starting recording..."
cd "$BASE" && node record-and-render-mobile.js >> "$LOG_FILE" 2>&1

if [[ ! -f "$OUTPUT_MP4" ]]; then
  log "ERROR: Recording failed — no MP4 produced"
  echo "ERROR: No MP4 found at $OUTPUT_MP4"
  exit 1
fi

# Copy to timestamped file
STAMP=$(TZ=America/Edmonton date +%Y%m%d-%H%M%S)
STAMPED_MP4="$BASE/output/repfind-${STAMP}.mp4"
cp "$OUTPUT_MP4" "$STAMPED_MP4"

log "Recording complete: $STAMPED_MP4"

# 5. Output product info as JSON for n8n
RESULT=$(python3 -c "
import json
print(json.dumps({
    'video_path': '$STAMPED_MP4',
    'product_title': '''$TITLE''',
    'product_id': '$PRODUCT_ID',
    'price': '$PRICE',
    'search_term': '$SEARCH_TERM',
    'timestamp': '$STAMP'
}))
")

log "=== Done ==="
echo "$RESULT"
