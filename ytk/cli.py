"""ytk: busca videos de YouTube en la terminal y míralos con mpv.

Muestra las miniaturas en una cuadrícula con el protocolo gráfico de kitty (funciona también
dentro de zellij). Necesita: yt-dlp (búsqueda), mpv (reproducción), kitty (imágenes).
Opcional: Pillow (si falta, las miniaturas se convierten con ffmpeg).

Uso: ytk [BÚSQUEDA...]
Variables: YTK_HEIGHT (calidad máxima, 720 por defecto), YTK_MPV_ARGS (opciones extra para mpv), YTK_DOWNLOADS (carpeta de descargas).
Tecla líder: espacio abre un menú (f buscar, m modo, o abrir, p reproducir todo, i información del video, c canal (v videos, l listas), a/d descargar audio/video, h historial, ] [ siguiente/anterior canción, b volver, n más, q salir).
Teclas: flechas o h j k l mover · Enter reproducir (listas completas) · o abrir una lista o el Mix de un video · P reproducir todo lo que ves · Tab cambia el modo
(mixto, videos, listas) · b volver · / buscar · n más resultados · q salir"""

import shutil
import sys

from . import __version__
from .app import App


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    if "--version" in sys.argv:
        print(f"ytk {__version__}")
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("ytk necesita una terminal interactiva (kitty).")
    for tool in ("yt-dlp",):
        if not shutil.which(tool):
            sys.exit(f"Falta {tool}: instálalo (sudo pacman -S {tool}).")
    App().run(" ".join(sys.argv[1:]).strip())
