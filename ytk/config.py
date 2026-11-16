"""Constantes y rutas de ytk (carpetas XDG, tamaños de la cuadrícula, calidad de reproducción)."""

import os
import re


CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ytk")
STATE_HOME = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
HISTORY_FILE = os.path.join(STATE_HOME, "ytk", "history.json")
WATCH_LATER = os.path.join(STATE_HOME, "mpv", "watch_later")   # donde mpv guarda la posición al salir
HISTORY_MAX = 200
MPV_TRIES = 5
RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or CACHE      # carpeta solo tuya: ahí va el socket de control de mpv
DOWNLOADS = os.path.expanduser(os.environ.get("YTK_DOWNLOADS") or "~/Videos/ytk")
LOCAL_NAME = re.compile(r"\[([A-Za-z0-9_-]{6,64})\]\.(?!part$|ytdl$|temp\.)[A-Za-z0-9]{2,5}$")
GRID_COLS = 3        # cuadrícula objetivo: 3 columnas x 3 filas = 9 videos por pantalla
GRID_ROWS = 3
MIN_CELL_W = 22      # si la ventana es muy angosta, se usan menos columnas
PAGE = 30            # resultados por búsqueda (y por cada "más")
THUMB_WORKERS = 6
HEIGHT = os.environ.get("YTK_HEIGHT", "720")   # calidad máxima de reproducción (por defecto 720p)
THUMB_URL = "https://i.ytimg.com/vi/{}/mqdefault.jpg"   # 320x180, 16:9
