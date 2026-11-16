"""mpv playback: launch, retry, skip songs and control the running mpv."""

import json
import os
import shlex
import shutil
import socket
import subprocess
import time

from .config import CACHE, RUNTIME, WATCH_LATER
from .storage import history_add
from .i18n import t
from .text import clean
from .youtube import mix_url, ytdl_format


def mpv_cmd(sock_path, *args):
    """Send a command to the running mpv (control socket). Returns its "data", or None on failure."""
    try:
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(1.5)
            s.connect(sock_path)
            s.sendall((json.dumps({"command": list(args), "request_id": 7}) + "\n").encode())
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    return None
                buf += chunk
                for line in buf.split(b"\n")[:-1]:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("request_id") == 7:
                        return r.get("data") if r.get("error") == "success" else None
                buf = buf.split(b"\n")[-1]
    except (OSError, ValueError):
        return None


class PlaybackMixin:
    """mpv playback: launch, retry, skip songs and control the running mpv."""

    # --- actions ---
    def launch(self, url, title=None, label=""):
        if not shutil.which("mpv"):
            self.status = t("mpv_missing")
            return
        os.makedirs(CACHE, exist_ok=True)
        os.makedirs(WATCH_LATER, exist_ok=True)
        self.rm_sock()
        self.sock = os.path.join(RUNTIME, f"ytk-mpv-{os.getpid()}-{int(time.monotonic() * 1000)}.sock")
        cmd = ["mpv", "--force-window=immediate", "--fs=no", "--input-ipc-server=" + self.sock, "--ytdl-format=" + ytdl_format(),
               "--save-position-on-quit", "--resume-playback=yes", "--watch-later-directory=" + WATCH_LATER,
               *(["--title=" + title] if title else []), *shlex.split(os.environ.get("YTK_MPV_ARGS", "")), "--", url]
        for p in self.players:                 # one mpv at a time: the previous one is closed (it saves its position)
            if p.poll() is None:
                p.terminate()
        self.spawn(cmd, 1)
        self.status = clean(f"▶ {label}{title or ''}")

    def spawn(self, cmd, attempt):
        log = open(os.path.join(CACHE, "mpv.log"), "ab")
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        log.close()
        proc.ytk = (cmd, time.monotonic(), attempt)
        self.players.append(proc)

    def play(self):
        if not self.items:
            return
        it = self.items[self.sel]
        history_add(it)
        if it["kind"] == "video" and self.jump(it):
            return
        if it["kind"] == "list":
            self.launch(it["url"], label=t("label.playlist") + it["title"])
            self.now = f"playlist:{it['id']}"
        elif it["id"] in self.local and os.path.isfile(self.local[it["id"]]):
            self.launch(self.local[it["id"]], title=it["title"], label=t("label.local"))
        else:
            self.launch(it["url"], title=it["title"])

    def rm_sock(self):
        if self.sock:
            try:
                os.unlink(self.sock)
            except OSError:
                pass

    def playing(self):
        return self.sock is not None and any(p.poll() is None for p in self.players)

    def jump(self, it):
        """If the playlist/mix you are viewing is already playing, jump to this song in that mpv (without opening another)."""
        src = self.source
        if not (src and src["kind"] in ("playlist", "mix") and self.now == f"{src['kind']}:{src['id']}" and self.playing()):
            return False
        pl = mpv_cmd(self.sock, "get_property", "playlist")
        if not isinstance(pl, list):
            return False
        for idx, e in enumerate(pl):
            if isinstance(e, dict) and f"v={it['id']}" in str(e.get("filename", "")):
                mpv_cmd(self.sock, "playlist-play-index", idx)
                self.status = clean(f"▶ {idx + 1}/{len(pl)} · {it['title']}")
                return True
        return False

    def step(self, direction):
        if not self.playing():
            self.status = t("nothing_playing")
            return
        mpv_cmd(self.sock, "playlist-next" if direction > 0 else "playlist-prev")
        self.status = clean(t("step.next") if direction > 0 else t("step.prev"))

    def play_all(self):
        """Play the playlist or mix being viewed, straight through."""
        src = self.source
        if not src or src["kind"] not in ("playlist", "mix"):
            self.status = t("play_all_hint")
            return
        url = mix_url(src["id"]) if src["kind"] == "mix" else f"https://www.youtube.com/playlist?list={src['id']}"
        self.launch(url, label=t("label.mix" if src["kind"] == "mix" else "label.playlist") + str(src.get("title")))
        self.now = f"{src['kind']}:{src['id']}"
