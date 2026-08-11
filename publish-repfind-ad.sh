#!/usr/bin/env bash
set -euo pipefail

BASE="/Users/jackserver/RepFind"
VIDEO="/Users/jackserver/.openclaw/workspace/repfind-ad.mp4"
LOG_FILE="$BASE/output/publish-repfind-ad.log"
mkdir -p "$BASE/output"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

CAPTION="Stop digging through dead links. repfind.ca searches direct-buy rep links across Weidian, Taobao, and 1688. Find the item, compare options, and go straight to the agent link. #repfind #reps #fashion #sneakers #streetwear"

if [[ ! -f "$VIDEO" ]]; then
  log "ERROR: missing ad video: $VIDEO"
  echo "ERROR: missing ad video: $VIDEO" >&2
  exit 1
fi

log "=== RepFind ad publish start ==="
log "Video: $VIDEO"
PUBLISH_JSON="$(bash "$BASE/publish-to-tiktok.sh" "$VIDEO" "$CAPTION")"
log "Publisher output: $PUBLISH_JSON"

python3 - "$PUBLISH_JSON" "$VIDEO" "$CAPTION" <<'PY'
import json, sys
publish = json.loads(sys.argv[1])
video = sys.argv[2]
caption = sys.argv[3]
out = {
    'success': True,
    'video_path': video,
    'asset': 'repfind-ad.mp4',
    'caption': caption,
    'postGroupId': publish.get('postGroupId'),
    'mediaId': publish.get('mediaId'),
    'fileUrl': publish.get('fileUrl'),
    'account': publish.get('account'),
    'mode': publish.get('mode'),
    'verifiedStatus': publish.get('verifiedStatus'),
    'postStatus': publish.get('postStatus'),
    'scheduledTime': publish.get('scheduledTime'),
    'nextStep': publish.get('nextStep'),
}
print(json.dumps(out, indent=2))
PY

log "=== RepFind ad publish complete ==="
