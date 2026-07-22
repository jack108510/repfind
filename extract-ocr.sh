#!/usr/bin/env bash
set -euo pipefail

# Extract frames from a video and OCR them.
# Outputs OCR text to stdout for the n8n OpenAI node to consume.
# Usage: extract-ocr.sh /path/to/video.mp4

VIDEO="${1:-}"
if [[ -z "$VIDEO" || ! -f "$VIDEO" ]]; then
  echo "Usage: $0 /path/to/video.mp4" >&2
  exit 2
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Extract 5 frames (one every ~3 seconds for a 15s video, spread for longer)
ffmpeg -y -i "$VIDEO" -vf "fps=1/3" -frames:v 5 "$TMPDIR/frame_%02d.jpg" -loglevel error 2>&1 || true

# OCR each frame
for f in "$TMPDIR"/frame_*.jpg; do
  [[ -f "$f" ]] || continue
  swift /tmp/ocr.swift "$f" 2>/dev/null || true
  echo "---FRAME BREAK---"
done
