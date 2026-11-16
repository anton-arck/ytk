#!/bin/sh
# Test: is a thumbnail shown in this terminal? Run it in kitty (and then inside zellij).
cd "$(dirname "$0")"
echo "TERM=$TERM  ZELLIJ=${ZELLIJ:-no}  TMUX=${TMUX:-no}"
kitten icat --align left thumb.jpg
echo "(if you see an image above, kitty's protocol works here)"
