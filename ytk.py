#!/usr/bin/env python3
"""ytk: busca videos de YouTube en la terminal y míralos con mpv.

Muestra las miniaturas en una cuadrícula con el protocolo gráfico de kitty (funciona también
dentro de zellij). Necesita: yt-dlp (búsqueda), mpv (reproducción), kitty (imágenes).
Opcional: Pillow (si falta, las miniaturas se convierten con ffmpeg).

Uso: ytk [BÚSQUEDA...]
Variables: YTK_HEIGHT (calidad máxima, 720 por defecto), YTK_MPV_ARGS (opciones extra para mpv).
Teclas: flechas o h j k l mover · Enter reproducir · / buscar · n más resultados · q salir
"""
import base64
import fcntl
import json
import os
import queue
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import tty
import unicodedata
import urllib.request

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ytk")
CELL_W = 34          # ancho objetivo de cada celda, en columnas
PAGE = 30            # resultados por búsqueda (y por cada "más")
THUMB_WORKERS = 6
HEIGHT = os.environ.get("YTK_HEIGHT", "720")   # calidad máxima de reproducción (por defecto 720p)
THUMB_URL = "https://i.ytimg.com/vi/{}/mqdefault.jpg"   # 320x180, 16:9


# ---------- terminal ----------
def term_size():
    """filas, columnas, ancho y alto de una celda en píxeles (con valores por defecto)."""
    try:
        r, c, xp, yp = struct.unpack("HHHH", fcntl.ioctl(1, termios.TIOCGWINSZ, b"\0" * 8))
    except OSError:
        sz = shutil.get_terminal_size()
        r, c, xp, yp = sz.lines, sz.columns, 0, 0
    return r, c, (xp // c if xp and c else 9), (yp // r if yp and r else 18)


def char_w(ch):
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def width(s):
    return sum(char_w(c) for c in s)


def clip(s, w):
    out, res = 0, []
    for c in s:
        k = char_w(c)
        if out + k > w:
            break
        res.append(c)
        out += k
    return "".join(res), out


def fit(s, w):
    """Recorta con … o rellena con espacios hasta exactamente w columnas."""
    if w <= 0:
        return ""
    if width(s) <= w:
        return s + " " * (w - width(s))
    t, o = clip(s, w - 1)
    return t + "…" + " " * (w - 1 - o)


def wrap2(s, w):
    """Reparte un título en dos líneas de w columnas (la segunda con … si no cabe)."""
    words, first, i = s.split(), "", 0
    while i < len(words):
        t = (first + " " + words[i]).strip()
        if width(t) > w:
            break
        first, i = t, i + 1
    if not first:
        first, _ = clip(s, w)
        rest = s[len(first):]
    else:
        rest = " ".join(words[i:])
    return fit(first, w), fit(rest, w)


def human(n):
    if n is None:
        return ""
    for lim, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= lim:
            return f"{n / lim:.1f}".rstrip("0").rstrip(".") + suf
    return str(int(n))


def ytdl_format():
    """Sin AV1 ni audio 5.1 (más ligeros de bajar y de decodificar); cae a lo que haya si no existe."""
    h = HEIGHT if HEIGHT.isdigit() else "720"
    return f"bv*[height<={h}][vcodec!^=av01]+ba[audio_channels<=2]/bv*[height<={h}]+ba/b[height<={h}]/b"


# ---------- protocolo gráfico de kitty ----------
def gfx(ctrl, payload=""):
    sys.stdout.write("\x1b_G" + ctrl + (";" + payload if payload else "") + "\x1b\\")


def gfx_transmit(img_id, png):
    """Guarda la imagen en el terminal (sin mostrarla); se coloca después con gfx_place."""
    b = base64.standard_b64encode(png).decode()
    chunks = [b[i:i + 4096] for i in range(0, len(b), 4096)] or [""]
    for i, ch in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        gfx(f"a=t,f=100,i={img_id},q=2,m={more}" if i == 0 else f"m={more},q=2", ch)


def gfx_place(img_id, cols, rows):
    gfx(f"a=p,i={img_id},c={cols},r={rows},C=1,q=2")


# ---------- teclas ----------
CSI = re.compile(rb"\x1b\[([0-9;]*)([A-Za-z~])")
SS3 = re.compile(rb"\x1bO([A-Za-z])")
CSI_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}
TILDE_KEYS = {"1": "home", "7": "home", "4": "end", "8": "end", "5": "pgup", "6": "pgdn", "3": "del"}


def parse_keys(data):
    toks, i = [], 0
    while i < len(data):
        b = data[i]
        if b == 0x1b:
            m = CSI.match(data, i) or SS3.match(data, i)
            if m:
                i = m.end()
                if m.re is SS3:
                    toks.append(CSI_KEYS.get(m.group(1).decode(), "?"))
                elif m.group(2) == b"~":
                    toks.append(TILDE_KEYS.get(m.group(1).decode().split(";")[0], "?"))
                else:
                    toks.append(CSI_KEYS.get(m.group(2).decode(), "?"))
            else:
                toks.append("esc")
                i += 1
        elif b in (0x0d, 0x0a):
            toks.append("enter")
            i += 1
        elif b in (0x7f, 0x08):
            toks.append("bs")
            i += 1
        elif b == 0x03:
            toks.append("quit")
            i += 1
        elif b < 0x20:
            i += 1
        else:
            j = i
            while j < len(data) and data[j] >= 0x20 and data[j] != 0x7f:
                j += 1
            toks.extend(("ch", c) for c in data[i:j].decode("utf-8", "ignore"))
            i = j
    return toks


# ---------- búsqueda y miniaturas ----------
def search(query, count):
    """yt-dlp a veces devuelve resultados sin canal ni vistas (respuesta alterna de YouTube): se reintenta."""
    best = []
    for _ in range(3):
        items = _search(query, count)
        if sum(1 for i in items if i["channel"]) > len(items) // 2:
            return items
        if len(items) > len(best) or (items and sum(1 for i in items if i["channel"]) > sum(1 for i in best if i["channel"])):
            best = items
    return best


def _search(query, count):
    cmd = ["yt-dlp", "--flat-playlist", "-j", "--no-warnings", "--", f"ytsearch{count}:{query}"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    items = []
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not d.get("id"):
            continue
        items.append({
            "id": d["id"],
            "title": d.get("title") or "(sin título)",
            "channel": d.get("channel") or d.get("uploader") or "",
            "duration": d.get("duration_string") or ("EN VIVO" if d.get("live_status") == "is_live" else ""),
            "views": d.get("view_count"),
            "url": d.get("url") or f"https://www.youtube.com/watch?v={d['id']}",
        })
    if not items and p.returncode != 0:
        raise RuntimeError((p.stderr.strip().splitlines() or ["yt-dlp falló"])[-1])
    return items


def to_png(jpg_path, png_path):
    try:
        from PIL import Image
        with Image.open(jpg_path) as im:
            im.convert("RGB").save(png_path, "PNG")
    except ImportError:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", jpg_path, png_path], check=True)


def fetch_thumb(vid):
    png = os.path.join(CACHE, vid + ".png")
    if os.path.exists(png):
        return png
    jpg = os.path.join(CACHE, vid + ".jpg")
    req = urllib.request.Request(THUMB_URL.format(vid), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as r, open(jpg, "wb") as f:
        f.write(r.read())
    to_png(jpg, png + ".tmp")
    os.replace(png + ".tmp", png)
    os.unlink(jpg)
    return png


# ---------- la aplicación ----------
class App:
    def __init__(self):
        self.items = []
        self.query = ""
        self.count = 0
        self.gen = 0
        self.sel = 0
        self.top = 0
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
            vid = self.thumbq.get()
            try:
                fetch_thumb(vid)
                self.events.put(("thumb", vid, True))
            except Exception:
                self.events.put(("thumb", vid, False))

    def start_search(self, query, count, append=False):
        self.gen += 1
        gen = self.gen
        self.query, self.count = query, count
        self.status = f"Buscando “{query}”…"
        self.dirty = True

        def work():
            try:
                self.events.put(("results", gen, search(query, count), append))
            except Exception as e:
                self.events.put(("error", gen, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def drain(self):
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            self.dirty = True
            if ev[0] == "results" and ev[1] == self.gen:
                _, _, items, append = ev
                if append:
                    known = {i["id"] for i in self.items}
                    items = [i for i in items if i["id"] not in known]
                    self.items += items
                else:
                    self.items, self.sel, self.top = items, 0, 0
                for it in self.items:
                    if it["id"] not in self.thumb:
                        self.thumb[it["id"]] = "queued"
                        self.thumbq.put(it["id"])
                self.status = f"{len(self.items)} resultados para “{self.query}”" if self.items else "Sin resultados"
            elif ev[0] == "error" and ev[1] == self.gen:
                self.status = "Error: " + ev[2]
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

    # --- dibujo ---
    def compute_layout(self):
        rows, cols, cw, ch = term_size()
        ncols = max(1, cols // CELL_W)
        cell_w = cols // ncols
        img_c = max(8, cell_w - 2)
        img_r = max(3, round(img_c * cw * 9 / 16 / ch))
        cell_h = img_r + 4          # imagen + 2 líneas de título + 1 de datos + 1 de aire
        vis = max(1, (rows - 2) // cell_h)
        self.layout = (rows, cols, ncols, cell_w, img_c, img_r, cell_h, vis)
        return self.layout

    def keep_visible(self):
        _, _, ncols, _, _, _, _, vis = self.compute_layout()
        row = self.sel // ncols
        if row < self.top:
            self.top = row
        elif row >= self.top + vis:
            self.top = row - vis + 1

    def draw(self):
        rows, cols, ncols, cell_w, img_c, img_r, cell_h, vis = self.compute_layout()
        self.keep_visible()
        # No se usa ED 2 (\x1b[2J): kitty descarta con él las imágenes ya enviadas; se borra línea a línea.
        out = ["\x1b_Ga=d,d=a,q=2\x1b\\"] + [f"\x1b[{y};1H\x1b[2K" for y in range(1, rows + 1)]
        head = f" ytk · {self.status}"
        out.append("\x1b[1;1H\x1b[7m" + fit(head, cols) + "\x1b[0m")
        places = []
        for r in range(vis):
            for c in range(ncols):
                idx = (self.top + r) * ncols + c
                if idx >= len(self.items):
                    break
                it = self.items[idx]
                y0, x0 = 2 + r * cell_h, c * cell_w + 2
                selected = idx == self.sel
                state = self.thumb.get(it["id"])
                if state == "ready":
                    places.append((y0, x0, self.sent[it["id"]]))
                else:
                    msg = "sin miniatura" if state == "fail" else "cargando…"
                    out.append(f"\x1b[{y0 + img_r // 2};{x0}H\x1b[2m{fit(msg, img_c)}\x1b[0m")
                t1, t2 = wrap2(it["title"], img_c)
                meta = fit(" · ".join(p for p in (it["channel"], it["duration"], human(it["views"])) if p), img_c)
                on, off = ("\x1b[7;1m", "\x1b[0m") if selected else ("", "")
                out.append(f"\x1b[{y0 + img_r};{x0}H{on}{t1}{off}")
                out.append(f"\x1b[{y0 + img_r + 1};{x0}H{on}{t2}{off}")
                out.append(f"\x1b[{y0 + img_r + 2};{x0}H\x1b[2m{meta}\x1b[0m")
                if selected:
                    for k in range(img_r + 3):
                        out.append(f"\x1b[{y0 + k};{x0 - 1}H\x1b[1m▌\x1b[0m")
        if self.mode == "prompt":
            out.append(f"\x1b[{rows};1H\x1b[0m/ {self.prompt}\x1b[K\x1b[?25h")
        else:
            hint = " ←↑↓→ / hjkl mover · Enter reproducir · / buscar · n más · q salir"
            out.append(f"\x1b[{rows};1H\x1b[2m{fit(hint, cols)}\x1b[0m\x1b[?25l")
        for y, x, img in places:
            out.append(f"\x1b[{y};{x}H")
            sys.stdout.write("".join(out))
            out = []
            gfx_place(img, img_c, img_r)
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # --- acciones ---
    def play(self):
        if not self.items:
            return
        it = self.items[self.sel]
        if not shutil.which("mpv"):
            self.status = "mpv no está instalado"
            return
        os.makedirs(CACHE, exist_ok=True)
        log = open(os.path.join(CACHE, "mpv.log"), "ab")
        subprocess.Popen(
            ["mpv", "--force-window=immediate", "--ytdl-format=" + ytdl_format(),
             "--title=" + it["title"], *shlex.split(os.environ.get("YTK_MPV_ARGS", "")), it["url"]],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.status = f"▶ {it['title']}"

    def move(self, delta, absolute=False):
        n = len(self.items)
        if not n:
            return
        self.sel = max(0, min(n - 1, delta if absolute else self.sel + delta))

    def more(self):
        if self.query and self.count == len(self.items) and self.count < 200:
            self.start_search(self.query, self.count + PAGE, append=True)

    def handle(self, data):
        """Devuelve False para salir."""
        for t in parse_keys(data):
            self.dirty = True
            if t == "quit":
                return False
            if self.mode == "prompt":
                if t == "esc":
                    self.mode, self.prompt = "normal", ""
                elif t == "enter":
                    q, self.mode, self.prompt = self.prompt.strip(), "normal", ""
                    if q:
                        self.start_search(q, PAGE)
                elif t == "bs":
                    self.prompt = self.prompt[:-1]
                elif isinstance(t, tuple):
                    self.prompt += t[1]
                continue
            _, _, ncols, _, _, _, _, vis = self.layout
            key = t[1] if isinstance(t, tuple) else t
            if key == "q":
                return False
            elif key in ("left", "h"):
                self.move(-1)
            elif key in ("right", "l"):
                self.move(1)
            elif key in ("up", "k"):
                self.move(-ncols)
            elif key in ("down", "j"):
                last_row = (len(self.items) - 1) // ncols
                if self.sel // ncols >= last_row:
                    self.more()
                self.move(ncols)
            elif key == "pgup":
                self.move(-ncols * vis)
            elif key == "pgdn":
                self.move(ncols * vis)
            elif key in ("home", "g"):
                self.move(0, True)
            elif key in ("end", "G"):
                self.move(len(self.items) - 1, True)
            elif key == "enter":
                self.play()
            elif key == "/":
                self.mode, self.prompt = "prompt", ""
            elif key == "n":
                self.more()
        return True

    def run(self, query):
        os.makedirs(CACHE, exist_ok=True)
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        signal.signal(signal.SIGWINCH, lambda *_: setattr(self, "winch", True))
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        try:
            tty.setcbreak(fd)
            if query:
                self.start_search(query, PAGE)
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


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("ytk necesita una terminal interactiva (kitty).")
    for tool in ("yt-dlp",):
        if not shutil.which(tool):
            sys.exit(f"Falta {tool}: instálalo (sudo pacman -S {tool}).")
    App().run(" ".join(sys.argv[1:]).strip())


if __name__ == "__main__":
    main()
