#!/usr/bin/env bash
set -euo pipefail

BASE="/Users/jackserver/RepFind"
LOG_FILE="$BASE/output/auto-record-and-publish.log"
mkdir -p "$BASE/output"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "=== RepFind record + publish start ==="

# auto-record.sh emits one JSON object on stdout with video_path/product fields.
RECORD_JSON="$(bash "$BASE/auto-record.sh")"
log "Recorder output: $RECORD_JSON"

PARSED="$(python3 - "$RECORD_JSON" <<'PY'
import json, sys
raw = sys.argv[1]
data = json.loads(raw)
video = data.get('video_path') or ''
title = data.get('product_title') or 'rep find'
price = data.get('price') or ''
search = data.get('search_term') or title
caption = f"Found {title} in seconds on repfind.ca 👀 Search 66K+ direct-buy links without dead pages. #repfind #reps #sneakers #streetwear #fashion"
print(json.dumps({
    'video': video,
    'title': title,
    'price': str(price),
    'search': search,
    'caption': caption[:300],
}))
PY
)"

VIDEO="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["video"])' "$PARSED")"
CAPTION="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["caption"])' "$PARSED")"
TITLE="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["title"])' "$PARSED")"

if [[ -z "$VIDEO" || ! -f "$VIDEO" ]]; then
  log "ERROR: video missing: $VIDEO"
  echo "ERROR: video missing: $VIDEO" >&2
  exit 1
fi

log "Publishing draft for: $TITLE"
PUBLISH_JSON="$(bash "$BASE/publish-to-tiktok.sh" "$VIDEO" "$CAPTION")"
log "Publisher output: $PUBLISH_JSON"

python3 - "$RECORD_JSON" "$PUBLISH_JSON" "$CAPTION" <<'PY'
import json, sys
record = json.loads(sys.argv[1])
publish = json.loads(sys.argv[2])
caption = sys.argv[3]
out = {
    'success': True,
    'video_path': record.get('video_path'),
    'product_title': record.get('product_title'),
    'price': record.get('price'),
    'search_term': record.get('search_term'),
    'caption': caption,
    'postGroupId': publish.get('postGroupId'),
    'mediaId': publish.get('mediaId'),
    'fileUrl': publish.get('fileUrl'),
    'account': publish.get('account'),
    'mode': publish.get('mode'),
    'nextStep': publish.get('nextStep'),
}
print(json.dumps(out, indent=2))
PY

log "=== RepFind record + publish complete ==="
