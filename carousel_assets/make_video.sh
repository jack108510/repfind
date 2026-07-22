#!/bin/bash
set -e

ASSETS="/Users/jackserver/repfind/carousel_assets"
TMP="/tmp/repfind_slides"
OUT="/Users/jackserver/.openclaw/workspace/repfind-ad.mp4"
FPS=25
DUR=4         # seconds per slide
FRAMES=100    # FPS * DUR
TRANS=0.5     # crossfade duration (seconds)

mkdir -p "$TMP"
cd "$TMP"

echo "==> Rendering slide clips with Ken Burns zoom..."

# Slide 1: subtle zoom (UI showcase)
ffmpeg -y -loop 1 -i "$ASSETS/slide1.png" \
  -vf "scale=1080:1920,zoompan=z='min(zoom+0.0003,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$FRAMES:s=1080x1920:fps=$FPS" \
  -t $DUR -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p clip1.mp4
echo "  clip1.mp4 done"

# Slide 2: Jordan 4 — zoom in from bottom-center (feels cinematic)
ffmpeg -y -loop 1 -i "$ASSETS/slide2.png" \
  -vf "scale=1080:1920,zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)':d=$FRAMES:s=1080x1920:fps=$FPS" \
  -t $DUR -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p clip2.mp4
echo "  clip2.mp4 done"

# Slide 3: Chrome Hearts — zoom from center
ffmpeg -y -loop 1 -i "$ASSETS/slide3.png" \
  -vf "scale=1080:1920,zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$FRAMES:s=1080x1920:fps=$FPS" \
  -t $DUR -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p clip3.mp4
echo "  clip3.mp4 done"

# Slide 4: Prada — zoom from center
ffmpeg -y -loop 1 -i "$ASSETS/slide4.png" \
  -vf "scale=1080:1920,zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$FRAMES:s=1080x1920:fps=$FPS" \
  -t $DUR -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p clip4.mp4
echo "  clip4.mp4 done"

# Slide 5: CTA — very subtle zoom out feel (start 1.03, end 1.0)
ffmpeg -y -loop 1 -i "$ASSETS/slide5.png" \
  -vf "scale=1080:1920,zoompan=z='if(eq(on,1),1.03,max(zoom-0.0003,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$FRAMES:s=1080x1920:fps=$FPS" \
  -t $DUR -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p clip5.mp4
echo "  clip5.mp4 done"

echo ""
echo "==> Combining clips with xfade transitions..."

# xfade offset calculations (each clip 4s, trans 0.5s):
# [0+1]: offset=3.5  → output 7.5s
# [01+2]: offset=7.0 → output 11.0s
# [012+3]: offset=10.5 → output 14.5s
# [0123+4]: offset=14.0 → output 18.0s

ffmpeg -y \
  -i clip1.mp4 -i clip2.mp4 -i clip3.mp4 -i clip4.mp4 -i clip5.mp4 \
  -filter_complex "
    [0:v][1:v]xfade=transition=fade:duration=${TRANS}:offset=3.5[x01];
    [x01][2:v]xfade=transition=fade:duration=${TRANS}:offset=7.0[x012];
    [x012][3:v]xfade=transition=fade:duration=${TRANS}:offset=10.5[x0123];
    [x0123][4:v]xfade=transition=fade:duration=${TRANS}:offset=14.0[out]
  " \
  -map "[out]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart \
  -r $FPS \
  "$OUT"

echo ""
echo "==> Done!"
echo "Output: $OUT"
ffprobe -v quiet -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT"
