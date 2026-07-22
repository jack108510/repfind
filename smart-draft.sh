#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# RepFind Smart Draft Publisher — @rep.find.ai ONLY
# 
# Takes a video file:
# 1. Extracts key frames
# 2. OCRs them to understand content
# 3. Sends OCR text to OpenAI to generate a TikTok caption
# 4. Saves as a TikTok DRAFT via Publora
#
# Usage: smart-draft.sh /path/to/video.mp4
# ═══════════════════════════════════════════════════════════════

BASE="/Users/jackserver/RepFind"
ENV_FILE="$BASE/.publora.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

VIDEO="${1:-}"
if [[ -z "$VIDEO" || ! -f "$VIDEO" ]]; then
  echo "Usage: $0 /path/to/video.mp4" >&2
  exit 2
fi

# Hard safety check
_LOWER_USER="$(echo "${PUBLORA_TIKTOK_USERNAME:-}" | tr '[:upper:]' '[:lower:]')"
if [[ "${PUBLORA_TIKTOK_PLATFORM_ID}" == *"salessparring"* ]] || [[ "$_LOWER_USER" == "salessparring" ]]; then
  echo "FATAL: This script is for rep.find.ai ONLY. Aborting." >&2
  exit 99
fi

# Extract frames and OCR
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Extracting frames from $VIDEO..."
ffmpeg -y -i "$VIDEO" -vf "fps=1/3" -frames:v 5 "$TMPDIR/frame_%02d.jpg" -loglevel error 2>&1 || true

echo "Running OCR on frames..."
OCR_TEXT=""
if [[ -f /tmp/ocr.swift ]]; then
  for f in "$TMPDIR"/frame_*.jpg; do
    [[ -f "$f" ]] || continue
    FRAME_OCR=$(swift /tmp/ocr.swift "$f" 2>/dev/null || true)
    if [[ -n "$FRAME_OCR" ]]; then
      OCR_TEXT="${OCR_TEXT}${FRAME_OCR}\n---\n"
    fi
  done
fi

# If no OCR text, use the filename as a hint
if [[ -z "$(echo "$OCR_TEXT" | tr -d '[:space:]')" ]]; then
  OCR_TEXT="Video filename: $(basename "$VIDEO")"
fi

echo "Generating caption with AI..."
CAPTION=$(python3 - "$OCR_TEXT" <<'PY'
import json, os, sys, urllib.request

ocr_text = sys.argv[1]

# Use OpenAI to generate a caption
# Get key from n8n credential or env
openai_key = os.environ.get("OPENAI_API_KEY", "")
if not openai_key:
    # Try to read from n8n credential store
    import subprocess
    result = subprocess.run(
        ["sqlite3", os.path.expanduser("~/.n8n/database.sqlite"),
         "select credentials from credentials_entity where id='ae23499e-8e8c-49a2-953e-10785e49d727';"],
        capture_output=True, text=True
    )
    raw = result.stdout.strip()
    if raw:
        try:
            data = json.loads(raw)
            openai_key = data.get("apiKey", "")
        except:
            pass

if not openai_key:
    # Fallback default caption
    print("Finding reps just got way too easy. Search 66K+ direct-buy links instantly. No dead pages, no fake ratings. repfind.ca #reps #repfind #sneakerreps #w2c")
    sys.exit(0)

prompt = f"""You are a TikTok caption writer for @rep.find.ai, a search engine for replica products (sneakers, clothing, electronics from Chinese marketplaces like Weidian, Taobao, 1688). repfind.ca searches 66K+ direct-buy links.

Here is OCR text extracted from a TikTok video:
{ocr_text}

Write a single TikTok caption that:
- Is punchy and hook-first (catches attention in the first 3 words)
- References what's actually shown in the video based on the OCR
- Includes relevant hashtags (5-8)
- Mentions repfind.ca or "link in bio" subtly
- Is under 300 characters
- No emoji spam (1-2 max)

Return ONLY the caption text, nothing else."""

body = json.dumps({
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "system", "content": "You are a social media caption writer. Return only the caption."},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 200,
    "temperature": 0.8,
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.openai.com/v1/chat/completions",
    data=body,
    headers={
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    caption = data["choices"][0]["message"]["content"].strip()
    print(caption)
except Exception as e:
    # Fallback
    print("Finding reps just got way too easy. Search 66K+ direct-buy links instantly. repfind.ca #reps #repfind #sneakerreps #w2c")
PY
)

echo "Caption: $CAPTION"
echo "---"

# Now publish as draft
echo "Saving draft to @rep.find.ai..."
exec bash "$BASE/publish-to-tiktok.sh" "$VIDEO" "$CAPTION"
