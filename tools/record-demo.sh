#!/usr/bin/env bash
# Record the README demo GIF of ytk, hands-free.
#
# It opens a floating kitty window of a fixed size, drives ytk through it with kitty's remote
# control (search -> browse -> info panel -> channel -> playlists tab), records only that window
# with wf-recorder and converts the video to a small GIF with ffmpeg (custom palette).
#
# Needs: sway, kitty (+ kitten), wf-recorder, ffmpeg, python3, yt-dlp, mpv.
# Do not touch the keyboard or mouse while it runs (about 50 s): the keys go to the demo window.
#
# Usage: tools/record-demo.sh [-q "search terms"] [-o output.gif] [-w width_px] [-s speed]
#   -q  what to search for      (default: "arch linux terminal apps")
#   -o  output file             (default: docs/demo.gif)
#   -w  GIF width in pixels     (default: 0 = the window's own size, no rescaling: sharpest)
#   -c  GIF palette colors      (default: 256)
#   -k  keep the raw recording at this path (to try other conversions)
#   -s  wait multiplier         (default: 1; use 1.5 on a slow network)
#   -m  cursor moves before the info panel, as keys h/j/k/l   (default: "l l j")
#       Search results change from day to day: pick moves that land on a VIDEO (not a playlist,
#       whose channel may have no videos tab). Run with -m "" to see where it lands, or tweak it.
set -euo pipefail

QUERY="arch linux terminal apps"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/demo.gif"
GIF_W=0
COLORS=256
KEEP=""
SPEED=1
MOVES="l l j"
while getopts "q:o:w:c:k:s:m:h" opt; do
  case $opt in
    q) QUERY=$OPTARG ;;
    o) OUT=$OPTARG ;;
    w) GIF_W=$OPTARG ;;
    c) COLORS=$OPTARG ;;
    k) KEEP=$OPTARG ;;
    s) SPEED=$OPTARG ;;
    m) MOVES=$OPTARG ;;
    *) sed -n '2,24p' "$0"; exit 0 ;;
  esac
done

for tool in swaymsg kitty kitten wf-recorder ffmpeg python3 yt-dlp mpv; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

WORK="$(mktemp -d)"
SOCK="unix:${XDG_RUNTIME_DIR:-/tmp}/ytk-demo-$$.sock"
APP_ID="ytk-demo"
KITTY_PID=""
REC_PID=""

cleanup() {
  [ -n "$REC_PID" ] && kill -INT "$REC_PID" 2>/dev/null || true
  [ -n "$KITTY_PID" ] && kill "$KITTY_PID" 2>/dev/null || true
  swaymsg seat seat0 hide_cursor 0 >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# send plain text / named keys to the demo window; every call is followed by a pause
text() { kitten @ --to "$SOCK" send-text -- "$1"; }
key()  { kitten @ --to "$SOCK" send-key "$@"; }
wait_s() { python3 -c "import time,sys; time.sleep(float(sys.argv[1]) * float(sys.argv[2]))" "$1" "$SPEED"; }
typed() { local s="$1" i; for ((i = 0; i < ${#s}; i++)); do text "${s:i:1}"; sleep 0.09; done; }

# 1. the demo window. A clean state dir keeps your history and language out of the recording
#    (the interface is forced to English so the GIF reads well for everyone).
export XDG_STATE_HOME="$WORK/state"
kitty --class "$APP_ID" --listen-on "$SOCK" \
  -o allow_remote_control=socket-only -o remember_window_size=no \
  -o initial_window_width=118c -o initial_window_height=34c \
  -o confirm_os_window_close=0 -o hide_window_decorations=yes \
  -o background_opacity=1 -o dynamic_background_opacity=no \
  env YTK_LANG=en "$ROOT/bin/ytk" &
KITTY_PID=$!

# 2. wait for the window, float and center it, then read its geometry
get_geom() {
  swaymsg -t get_tree | python3 -c '
import json, sys
def walk(n):
    if n.get("app_id") == "'"$APP_ID"'":
        r = n["rect"]; print(r["x"], r["y"], r["width"] & ~1, r["height"] & ~1); return True
    return any(walk(c) for c in n.get("nodes", []) + n.get("floating_nodes", []))
walk(json.load(sys.stdin))'
}
geom=""
for _ in $(seq 1 50); do
  geom=$(get_geom) || true
  [ -n "$geom" ] && break
  sleep 0.2
done
[ -n "$geom" ] || { echo "the demo window never appeared" >&2; exit 1; }
swaymsg "[app_id=$APP_ID] floating enable, move position center" >/dev/null
sleep 1
geom=$(get_geom)      # read again: it has moved and may have changed size
read -r X Y W H <<<"$geom"
echo "recording ${W}x${H} at ${X},${Y}"
swaymsg seat seat0 hide_cursor 100 >/dev/null 2>&1 || true   # no mouse pointer over the demo
sleep 1.5

# 3. start recording only that window
# near-lossless and full-color (4:4:4): the default 4:2:0 smears colored text on dark backgrounds
wf-recorder -g "$X,$Y ${W}x${H}" -r 30 -c libx264 -x yuv444p -p crf=8 -p preset=ultrafast -f "$WORK/rec.mp4" >"$WORK/wf.log" 2>&1 &
REC_PID=$!
sleep 1

# 4. the script of the demo
text "/"; wait_s 0.8
typed "$QUERY"; wait_s 0.8
key enter; wait_s 9                    # results + thumbnails
for m in $MOVES; do text "$m"; wait_s 0.8; done; wait_s 0.8       # move the selection around
text " "; wait_s 1.5                   # leader menu (space) ...
text "i"; wait_s 4.5                   # ... video info panel
key escape; wait_s 0.8
text " "; wait_s 0.8; text "c"; wait_s 1.2; text "v"; wait_s 7    # the channel's videos
key tab; wait_s 5                      # Tab -> the channel's playlists
key escape; wait_s 1.2                 # back to the search results
text " "; wait_s 1.2; text "L"; wait_s 2.2        # space L: language -> Spanish
text " "; wait_s 0.8; text "L"; wait_s 1.5        # ... and back
text "q"; sleep 1

kill -INT "$REC_PID" 2>/dev/null || true
wait "$REC_PID" 2>/dev/null || true
REC_PID=""

# 5. video -> GIF: custom palette, 12 fps; ordered dithering keeps thumbnails from banding and
#    only the pixels that change between frames are stored (small file)
[ -n "$KEEP" ] && cp "$WORK/rec.mp4" "$KEEP"
SCALE=""; [ "$GIF_W" -gt 0 ] && SCALE="scale=${GIF_W}:-1:flags=lanczos,"
mkdir -p "$(dirname "$OUT")"
ffmpeg -v error -y -ss 1 -i "$WORK/rec.mp4" \
  -vf "fps=12,${SCALE}split[a][b];[a]palettegen=max_colors=${COLORS}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -loop 0 "$OUT"
echo "wrote $OUT ($(( $(stat -c %s "$OUT") / 1024 )) KB)"
