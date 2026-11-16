"""ytk constants and paths (XDG folders, grid size, playback quality)."""

import os
import re


CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ytk")
STATE_HOME = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
HISTORY_FILE = os.path.join(STATE_HOME, "ytk", "history.json")
WATCH_LATER = os.path.join(STATE_HOME, "mpv", "watch_later")   # where mpv saves the position on quit
LANG_FILE = os.path.join(STATE_HOME, "ytk", "lang")      # language chosen with space L
HISTORY_MAX = 200
MPV_TRIES = 5
RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or CACHE      # folder only you can use: the mpv control socket goes here
DOWNLOADS = os.path.expanduser(os.environ.get("YTK_DOWNLOADS") or "~/Videos/ytk")
LOCAL_NAME = re.compile(r"\[([A-Za-z0-9_-]{6,64})\]\.(?!part$|ytdl$|temp\.)[A-Za-z0-9]{2,5}$")
GRID_COLS = 3        # target grid: 3 columns x 3 rows = 9 videos per screen
GRID_ROWS = 3
MIN_CELL_W = 22      # if the window is very narrow, fewer columns are used
PAGE = 30            # results per search (and per "more")
THUMB_WORKERS = 6
HEIGHT = os.environ.get("YTK_HEIGHT", "720")   # maximum playback quality (720p by default)
THUMB_URL = "https://i.ytimg.com/vi/{}/mqdefault.jpg"   # 320x180, 16:9
