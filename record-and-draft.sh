#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# RepFind: record a mobile demo → MP4 → TikTok DRAFT (@rep.find.ai)
#
#   ./record-and-draft.sh --term "Chrome Hearts"
#   ./record-and-draft.sh --term "Amiri" --caption "custom text"
#   ./record-and-draft.sh --term "Corteiz" --dry-run   # record only, no upload
#
# Emits a single JSON object on stdout. All progress goes to stderr so the
# JSON stays machine-readable for n8n.
# ═══════════════════════════════════════════════════════════════

BASE="/Users/jackserver/repfind"
PORT="${REPFIND_PORT:-4173}"
OUTPUT_DIR="$BASE/output"
LOG_DIR="$BASE/logs"

TERM_ARG=""
CAPTION=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --term) TERM_ARG="${2:-}"; shift 2 ;;
    --caption) CAPTION="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$TERM_ARG" ]]; then
  echo "Usage: $0 --term \"Search Term\" [--caption \"text\"] [--dry-run]" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"
cd "$BASE"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

STARTED_SERVER=0
cleanup() {
  if [[ "$STARTED_SERVER" == "1" && -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Start the local static server only if nothing is already serving the port.
if ! curl -sf -o /dev/null "http://127.0.0.1:$PORT/"; then
  echo "Starting recording server on $PORT..." >&2
  PORT="$PORT" node recording-server.js > "$LOG_DIR/recording-server.log" 2>&1 &
  SERVER_PID=$!
  STARTED_SERVER=1
  for _ in $(seq 1 30); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break
    sleep 0.5
  done
  if ! curl -sf -o /dev/null "http://127.0.0.1:$PORT/"; then
    echo "Recording server failed to start. See $LOG_DIR/recording-server.log" >&2
    exit 1
  fi
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
SLUG="$(echo "$TERM_ARG" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')"
MP4="$OUTPUT_DIR/repfind-$SLUG-$STAMP.mp4"

echo "Recording \"$TERM_ARG\"..." >&2
REPFIND_SEARCH_TERM="$TERM_ARG" node record-screen-demo-mobile.js >> "$LOG_DIR/record.log" 2>&1
WEBM="$OUTPUT_DIR/repfind-mobile-screen-recording.webm"
if [[ ! -f "$WEBM" ]]; then
  echo "Recording produced no output. See $LOG_DIR/record.log" >&2
  exit 1
fi

echo "Converting to MP4..." >&2
ffmpeg -y -i "$WEBM" -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -movflags +faststart "$MP4" >> "$LOG_DIR/record.log" 2>&1

DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MP4" 2>/dev/null || echo 0)"
BYTES="$(wc -c < "$MP4" | tr -d ' ')"

# A capture that came out too short means the scripted flow bailed early.
if awk "BEGIN{exit !($DURATION < 5)}"; then
  echo "Recording is only ${DURATION}s — the scripted flow likely failed for \"$TERM_ARG\"." >&2
  exit 1
fi

if [[ -z "$CAPTION" ]]; then
  CAPTION="Looking for $TERM_ARG reps? Search 66K+ direct-buy links in seconds. No dead pages, no fake ratings. repfind.ca"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  python3 -c '
import json, sys
print(json.dumps({
    "success": True, "mode": "dry-run", "searchTerm": sys.argv[1],
    "video": sys.argv[2], "durationSeconds": round(float(sys.argv[3]), 2),
    "bytes": int(sys.argv[4]), "caption": sys.argv[5],
}, indent=2))' "$TERM_ARG" "$MP4" "$DURATION" "$BYTES" "$CAPTION"
  exit 0
fi

echo "Uploading draft to TikTok..." >&2
PUBLISH_JSON="$("$BASE/publish-to-tiktok.sh" "$MP4" "$CAPTION")"

python3 -c '
import json, sys
result = json.loads(sys.argv[1])
result.update({
    "searchTerm": sys.argv[2],
    "video": sys.argv[3],
    "durationSeconds": round(float(sys.argv[4]), 2),
    "bytes": int(sys.argv[5]),
    "caption": sys.argv[6],
})
print(json.dumps(result, indent=2))' \
  "$PUBLISH_JSON" "$TERM_ARG" "$MP4" "$DURATION" "$BYTES" "$CAPTION"
