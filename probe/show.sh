#!/bin/sh
# Prueba: ¿se ve una miniatura en esta terminal? Ejecuta esto en kitty (y luego dentro de zellij).
cd "$(dirname "$0")"
echo "TERM=$TERM  ZELLIJ=${ZELLIJ:-no}  TMUX=${TMUX:-no}"
kitten icat --align left thumb.jpg
echo "(si arriba ves una imagen, el protocolo de kitty funciona aquí)"
