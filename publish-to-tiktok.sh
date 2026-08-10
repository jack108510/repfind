#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# RepFind TikTok Publisher — @rep.find.ai ONLY
# Uploads a video, finalizes the media, then schedules it to publish.
# Hardcoded to rep.find.ai — can NEVER post to @salessparring.
# ═══════════════════════════════════════════════════════════════

BASE="/Users/jackserver/RepFind"
ENV_FILE="$BASE/.publora.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

VIDEO="${1:-}"
CAPTION="${2:-Finding reps just got way too easy. Search 66K+ direct-buy links instantly. No dead pages, no fake ratings. repfind.ca}"

# Hard safety check — refuse if somehow pointed at salessparring
_LOWER_USER="$(echo "${PUBLORA_TIKTOK_USERNAME:-}" | tr '[:upper:]' '[:lower:]')"
if [[ "${PUBLORA_TIKTOK_PLATFORM_ID:-}" == *"salessparring"* ]] || \
   [[ "$_LOWER_USER" == "salessparring" ]]; then
  echo "FATAL: Platform ID/username is salessparring, but this script is for rep.find.ai ONLY. Aborting." >&2
  exit 99
fi

if [[ -z "$VIDEO" || ! -f "$VIDEO" ]]; then
  echo "Usage: $0 /path/to/video.mp4 'caption text'" >&2
  exit 2
fi
if [[ -z "${PUBLORA_KEY:-}" ]]; then
  echo "Missing PUBLORA_KEY in $ENV_FILE" >&2
  exit 2
fi
if [[ -z "${PUBLORA_TIKTOK_PLATFORM_ID:-}" ]]; then
  echo "Missing PUBLORA_TIKTOK_PLATFORM_ID in $ENV_FILE" >&2
  exit 2
fi

python3 - "$VIDEO" "$CAPTION" <<'PY'
import json, mimetypes, os, pathlib, sys, urllib.request, urllib.error, uuid
from datetime import datetime, timedelta, timezone

video_path = pathlib.Path(sys.argv[1])
caption = sys.argv[2]
key = os.environ['PUBLORA_KEY']
platform_id = os.environ['PUBLORA_TIKTOK_PLATFORM_ID']
username = os.environ.get('PUBLORA_TIKTOK_USERNAME', 'rep.find.ai')
base = 'https://api.publora.com/api/v1'
ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

def api(method, path, body=None, extra_headers=None):
    data = None
    headers = {
        'Accept': 'application/json',
        'User-Agent': ua,
        'Origin': 'https://docs.publora.com',
        'Referer': 'https://docs.publora.com/',
        'x-publora-key': key,
        'Content-Type': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            text = r.read().decode('utf-8', 'ignore')
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'ignore')
        raise SystemExit(f'Publora HTTP {e.code} at {path}: {text[:2000]}')

# Create as draft (no scheduledTime, no status=scheduled)
settings = {
    'tiktok': {
        'viewerSetting': 'PUBLIC_TO_EVERYONE',
        'allowComments': True,
        'allowDuet': False,
        'allowStitch': False,
        'commercialContent': False,
        'brandOrganic': False,
        'brandedContent': False,
    }
}
create = api('POST', '/create-post', {
    'content': caption[:2200],
    'platforms': [platform_id],
    'platformSettings': settings,
}, {'Idempotency-Key': 'repfind-draft-' + uuid.uuid4().hex})
post_group_id = create.get('postGroupId')
if not post_group_id:
    raise SystemExit('Publora create-post did not return postGroupId: ' + json.dumps(create))

ctype = mimetypes.guess_type(str(video_path))[0] or 'video/mp4'
if not ctype.startswith('video/'):
    ctype = 'video/mp4'
up = api('POST', '/get-upload-url', {
    'fileName': video_path.name,
    'contentType': ctype,
    'postGroupId': post_group_id,
    'type': 'video',
})
upload_url = up.get('uploadUrl')
if not upload_url:
    raise SystemExit('Publora get-upload-url did not return uploadUrl: ' + json.dumps(up))

# Upload to S3
with video_path.open('rb') as f:
    req = urllib.request.Request(upload_url, data=f.read(), method='PUT', headers={'Content-Type': ctype, 'User-Agent': ua})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            upload_status = r.status
            r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f'S3 upload HTTP {e.code}: {e.read().decode("utf-8", "ignore")[:1000]}')

media_id = up.get('mediaId')
if not media_id:
    raise SystemExit('Publora get-upload-url did not return mediaId: ' + json.dumps(up))

# Publora's documented local-file flow requires media finalization before scheduling.
finalize = api('POST', f'/complete-media/{media_id}', {})

# Schedule after upload/finalize. Publora recommends at least 2 minutes ahead;
# use 5 minutes to avoid race conditions with TikTok media processing.
scheduled_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
schedule = api('PUT', f'/update-post/{post_group_id}', {
    'status': 'scheduled',
    'scheduledTime': scheduled_time,
}, {'Idempotency-Key': 'repfind-schedule-' + post_group_id})

# Read back the stored status so n8n logs prove it is not just a draft.
verify = api('GET', f'/get-post/{post_group_id}')

result = {
    'success': True,
    'mode': 'scheduled',
    'account': username,
    'platform': 'tiktok',
    'platformId': platform_id,
    'postGroupId': post_group_id,
    'mediaId': media_id,
    'fileUrl': up.get('fileUrl'),
    'uploadStatus': upload_status,
    'finalizeSuccess': finalize.get('success'),
    'scheduledTime': schedule.get('scheduledTime') or scheduled_time,
    'verifiedStatus': verify.get('status'),
    'postStatus': (verify.get('posts') or [{}])[0].get('status'),
    'nextStep': 'Publora will publish automatically at scheduledTime; no manual TikTok draft step required.',
}
print(json.dumps(result, indent=2))
PY
