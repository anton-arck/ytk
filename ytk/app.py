"""La aplicación: junta las piezas y corre el bucle principal."""

import os
import queue
import select
import signal
import sys
import termios
import threading
import time
import tty

from .config import CACHE, MPV_TRIES, PAGE, THUMB_WORKERS
from .downloads import DownloadsMixin
from .keys import KeysMixin
from .navigation import NavigationMixin
from .playback import PlaybackMixin
from .terminal import gfx_transmit
from .text import clean
from .thumbs import fetch_thumb
from .view import ViewMixin
from .youtube import MODES


class App(PlaybackMixin, DownloadsMixin, NavigationMixin, ViewMixin, KeysMixin):
    """Estado de la aplicación; el trabajo está repartido en los mixins de cada módulo."""

    def __init__(self):
        self.items = []
        self.source = None         # {"kind": "search", "q", "mode"} | {"kind": "playlist", "id", "title"}
        self.count = 0
        self.exhausted = False
        self.search_mode = MODES[0]
        self.leader = None         # None = normal; lista = ruta abierta en el menú de la tecla líder
        self.stack = []            # vistas anteriores, para volver con b
        self.scan_local()          # self.local: id -> archivo (el video gana al audio); self.has_video: ids
        self.downloads = {}        # id -> (proceso yt-dlp, título, "audio"|"video")
        self.sock = None           # socket de control del mpv actual
        self.now = None            # "playlist:ID" | "mix:ID" mientras suena una lista o mix lanzado desde ytk
        self.players = []          # procesos mpv lanzados (se recogen al terminar para no dejar zombis)
        self.gen = 0
        self.sel = 0
        self.top = 0
        self.info = None           # video/lista cuyo panel de información está abierto
        self.info_cache = {}       # id -> datos extra (dict) | "loading" | "error: ..."
        self.mode = "normal"       # normal | prompt
        self.prompt = ""
        self.status = "Pulsa / para buscar"
        self.dirty = True
        self.winch = False
        self.events = queue.Queue()
        self.thumb = {}            # id -> queued | ready | fail
        self.sent = {}             # id -> id numérico de imagen ya enviado al terminal
        self.next_img = 1
        self.thumbq = queue.Queue()
        self.layout = (1, 1, 1, 1, 1, 1, 1, 1)
        for _ in range(THUMB_WORKERS):
            threading.Thread(target=self.thumb_worker, daemon=True).start()

    # --- trabajo en segundo plano ---
    def thumb_worker(self):
        while True:
            vid, url = self.thumbq.get()
            try:
                fetch_thumb(vid, url)
                self.events.put(("thumb", vid, True))
            except Exception:
                self.events.put(("thumb", vid, False))

    def drain(self):
        alive = [p for p in self.players if p.poll() is None]
        for p in list(self.players):
            cmd, t0, attempt = p.ytk
            # código 2 = mpv no pudo abrir el video. YouTube firma el enlace con tu IP y con datos móviles
            # la IP cambia entre pedidos (error 403), así que se reintenta con un enlace nuevo.
            if p.returncode == 2 and attempt < MPV_TRIES and time.monotonic() - t0 < 120:
                self.spawn(cmd, attempt + 1)
                alive.append(self.players[-1])
                self.status = f"mpv no pudo abrir el video; reintentando ({attempt + 1}/{MPV_TRIES})…"
            elif p.returncode == 2 and attempt >= MPV_TRIES:
                self.status = f"✘ mpv no pudo abrir el video tras {MPV_TRIES} intentos (mira ~/.cache/ytk/mpv.log)"
        if len(alive) != len(self.players):
            self.dirty = True              # un mpv terminó: puede haber guardado una posición nueva
        self.players = alive
        if not alive:
            self.now = None
            self.rm_sock()
        for vid, (proc, title, kind) in list(self.downloads.items()):
            if proc.poll() is None:
                continue
            del self.downloads[vid]
            self.scan_local()
            self.dirty = True
            self.status = clean(f"✔ descargado ({kind}): {title}" if proc.returncode == 0
                                else f"✘ falló la descarga de {title} (mira ~/.cache/ytk/dl.log)")
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            self.dirty = True
            if ev[0] == "results" and ev[1] == self.gen:
                _, _, items, append, asked = ev
                if append:
                    known = {i["id"] for i in self.items}
                    items = [i for i in items if i["id"] not in known]
                    self.exhausted = not items
                    self.items += items
                else:
                    self.items, self.sel, self.top = items, 0, 0
                    self.exhausted = len(items) < asked * 0.8
                for it in self.items:
                    if it["id"] not in self.thumb:
                        self.thumb[it["id"]] = "queued"
                        self.thumbq.put((it["id"], it.get("thumb")))
                self.status = self.summary()
            elif ev[0] == "error" and ev[1] == self.gen:
                self.status = "Error: " + clean(ev[2])
            elif ev[0] == "info":
                self.info_cache[ev[1]] = ev[2]
            elif ev[0] == "thumb":
                vid, ok = ev[1], ev[2]
                if not ok:
                    self.thumb[vid] = "fail"
                    continue
                try:
                    with open(os.path.join(CACHE, vid + ".png"), "rb") as f:
                        data = f.read()
                    img = self.next_img
                    self.next_img += 1
                    gfx_transmit(img, data)
                    self.sent[vid] = img
                    self.thumb[vid] = "ready"
                except OSError:
                    self.thumb[vid] = "fail"
        sys.stdout.flush()

    def run(self, query):
        os.makedirs(CACHE, exist_ok=True)
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        signal.signal(signal.SIGWINCH, lambda *_: setattr(self, "winch", True))
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        try:
            tty.setcbreak(fd)
            if query:
                self.start_load({"kind": "search", "q": query, "mode": self.search_mode}, PAGE)
            while True:
                self.drain()
                if self.winch:
                    self.winch, self.dirty = False, True
                if self.dirty:
                    self.dirty = False
                    self.draw()
                if select.select([fd], [], [], 0.05)[0]:
                    data = os.read(fd, 4096)
                    if not data or not self.handle(data):
                        break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            sys.stdout.write("\x1b_Ga=d,d=A,q=2\x1b\\\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
