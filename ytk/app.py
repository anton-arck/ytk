"""The application: puts the pieces together and runs the main loop."""

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
from .i18n import t
from .terminal import gfx_transmit
from .text import clean
from .thumbs import fetch_thumb
from .view import ViewMixin
from .youtube import MODES


class App(PlaybackMixin, DownloadsMixin, NavigationMixin, ViewMixin, KeysMixin):
    """Application state; the work is split across the mixins of each module."""

    def __init__(self):
        self.items = []
        self.source = None         # {"kind": "search", "q", "mode"} | {"kind": "playlist", "id", "title"}
        self.count = 0
        self.exhausted = False
        self.search_mode = MODES[0]
        self.leader = None         # None = normal; list = path currently open in the leader menu
        self.stack = []            # previous views, to go back with b
        self.scan_local()          # self.local: id -> file (video wins over audio); self.has_video: ids
        self.downloads = {}        # id -> (yt-dlp process, title, "audio"|"video")
        self.sock = None           # control socket of the current mpv
        self.now = None            # "playlist:ID" | "mix:ID" while a playlist or mix launched from ytk is playing
        self.players = []          # launched mpv processes (reaped when they end so no zombies are left)
        self.gen = 0
        self.sel = 0
        self.top = 0
        self.info = None           # video/playlist whose info panel is open
        self.info_cache = {}       # id -> extra data (dict) | "loading" | "error: ..."
        self.mode = "normal"       # normal | prompt
        self.prompt = ""
        self.status = t("press_search")
        self.dirty = True
        self.winch = False
        self.events = queue.Queue()
        self.thumb = {}            # id -> queued | ready | fail
        self.sent = {}             # id -> numeric image id already sent to the terminal
        self.next_img = 1
        self.thumbq = queue.Queue()
        self.layout = (1, 1, 1, 1, 1, 1, 1, 1)
        for _ in range(THUMB_WORKERS):
            threading.Thread(target=self.thumb_worker, daemon=True).start()

    # --- background work ---
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
            # exit code 2 = mpv could not open the video. YouTube signs the link with your IP, and on mobile data
            # the IP changes between requests (error 403), so it retries with a fresh link.
            if p.returncode == 2 and attempt < MPV_TRIES and time.monotonic() - t0 < 120:
                self.spawn(cmd, attempt + 1)
                alive.append(self.players[-1])
                self.status = t("mpv_retry", n=attempt + 1, max=MPV_TRIES)
            elif p.returncode == 2 and attempt >= MPV_TRIES:
                self.status = t("mpv_gave_up", max=MPV_TRIES)
        if len(alive) != len(self.players):
            self.dirty = True              # an mpv ended: it may have saved a new position
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
            self.status = clean(t("dl.done", kind=kind, title=title) if proc.returncode == 0
                                else t("dl.failed", title=title))
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
