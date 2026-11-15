#!/usr/bin/env python3
"""ytk: busca videos de YouTube en la terminal y míralos con mpv.

Muestra las miniaturas en una cuadrícula con el protocolo gráfico de kitty (funciona también
dentro de zellij). Necesita: yt-dlp (búsqueda), mpv (reproducción), kitty (imágenes).
Opcional: Pillow (si falta, las miniaturas se convierten con ffmpeg).

Uso: ytk [BÚSQUEDA...]
Variables: YTK_HEIGHT (calidad máxima, 720 por defecto), YTK_MPV_ARGS (opciones extra para mpv), YTK_DOWNLOADS (carpeta de descargas).
Tecla líder: espacio abre un menú (f buscar, m modo, o abrir, p reproducir todo, a/d descargar audio/video, h historial, b volver, n más, q salir).
Teclas: flechas o h j k l mover · Enter reproducir (listas completas) · o abrir una lista o el Mix de un video · P reproducir todo lo que ves · Tab cambia el modo
(mixto, videos, listas) · b volver · / buscar · n más resultados · q salir
"""
import base64
import fcntl
import hashlib
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
import time
import tty
import unicodedata
import urllib.parse
import urllib.request

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ytk")
STATE_HOME = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
HISTORY_FILE = os.path.join(STATE_HOME, "ytk", "history.json")
WATCH_LATER = os.path.join(STATE_HOME, "mpv", "watch_later")   # donde mpv guarda la posición al salir
HISTORY_MAX = 200
MPV_TRIES = 3
DOWNLOADS = os.path.expanduser(os.environ.get("YTK_DOWNLOADS") or "~/Videos/ytk")
LOCAL_NAME = re.compile(r"\[([A-Za-z0-9_-]{6,64})\]\.(?!part$|ytdl$|temp\.)[A-Za-z0-9]{2,5}$")
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


def clean(s):
    """Quita de un texto externo todo carácter de control o de formato (Cc, Cf...): evita inyectar
    secuencias de escape en la terminal desde títulos, canales o mensajes de error."""
    s = "".join(" " if c in "\t\r\n" else c for c in str(s or ""))
    return "".join(c for c in s if not unicodedata.category(c).startswith("C")).strip()


VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")   # ids de video (11) y de lista (PL..., hasta ~40)
# Menú de la tecla líder (espacio), como which-key de LazyVim: tecla -> (texto, acción | submenú)
MENU = {
    "f": ("buscar", "search"),
    "m": ("modo de búsqueda…", {
        "m": ("mixto: videos y listas", "mode:mixto"),
        "v": ("solo videos", "mode:videos"),
        "l": ("solo listas", "mode:listas"),
    }),
    "o": ("abrir lista / mix", "open"),
    "p": ("reproducir todo", "play_all"),
    "a": ("descargar audio", "dl_audio"),
    "d": ("descargar video", "dl_video"),
    "h": ("historial / continuar viendo", "history"),
    "b": ("volver", "back"),
    "n": ("más resultados", "more"),
    "q": ("salir", "quit"),
}
LIST_PREFIX = ("PL", "RD", "OL", "UU", "LL", "FL")
THUMB_HOSTS = {"i.ytimg.com", "i9.ytimg.com", "yt3.ggpht.com"}
MODES = ["mixto", "videos", "listas"]
LIST_SEARCH = "https://www.youtube.com/results?search_query={}&sp=EgIQAw%3D%3D"   # filtro: solo listas


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
        elif b == 0x09:
            toks.append("tab")
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
def allowed_thumb(url):
    u = urllib.parse.urlparse(str(url or ""))
    return url if u.scheme == "https" and u.hostname in THUMB_HOSTS else None


def _flat(target, end=None):
    """Lista plana de yt-dlp (sin resolver cada video). Devuelve elementos de tipo video o lista."""
    cmd = ["yt-dlp", "--flat-playlist", "-j", "--no-warnings"] + (["--playlist-end", str(end)] if end else []) + ["--", target]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    items = []
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        vid = str(d.get("id") or "")
        if not VIDEO_ID.match(vid):      # el id se usa en rutas de la caché: solo caracteres seguros
            continue
        is_list = d.get("ie_key") == "YoutubeTab" or d.get("_type") == "playlist"
        if is_list and not vid.startswith(LIST_PREFIX):     # canales (UC...) y otros: se omiten
            continue
        views = d.get("view_count")
        thumb = None
        for t in d.get("thumbnails") or []:
            thumb = allowed_thumb(t.get("url")) if isinstance(t, dict) else None
            if thumb:
                break
        items.append({
            "id": vid,
            "kind": "list" if is_list else "video",
            "title": clean(d.get("title")) or "(sin título)",
            "channel": clean(d.get("channel") or d.get("uploader")),
            "duration": clean(d.get("duration_string") or ("EN VIVO" if d.get("live_status") == "is_live" else "")),
            "views": views if isinstance(views, (int, float)) else None,
            "secs": d.get("duration") if isinstance(d.get("duration"), (int, float)) else None,
            "thumb": thumb if is_list else None,     # los videos usan siempre la miniatura por id
            # la URL se construye aquí a partir del id, nunca se usa la del JSON
            "url": f"https://www.youtube.com/playlist?list={vid}" if is_list else f"https://www.youtube.com/watch?v={vid}",
        })
    if not items and p.returncode != 0:
        raise RuntimeError(clean((p.stderr.strip().splitlines() or ["yt-dlp falló"])[-1]))
    return items


def mix_url(vid):
    return f"https://www.youtube.com/watch?v={vid}&list=RD{vid}"


def search_videos(query, count):
    """yt-dlp a veces devuelve resultados sin canal ni vistas (respuesta alterna de YouTube): se reintenta."""
    best = []
    for _ in range(3):
        items = _flat(f"ytsearch{count}:{query}")
        if sum(1 for i in items if i["channel"]) > len(items) // 2:
            return items
        if len(items) > len(best) or (items and sum(1 for i in items if i["channel"]) > sum(1 for i in best if i["channel"])):
            best = items
    return best


def search_lists(query, count):
    return _flat(LIST_SEARCH.format(urllib.parse.quote(query)), end=count)


def fetch(source, count):
    """Trae los elementos de una fuente: {"kind": "search", "q", "mode"} o {"kind": "playlist", "id"}."""
    if source["kind"] == "history":
        return history_load()
    if source["kind"] == "playlist":
        return _flat(f"https://www.youtube.com/playlist?list={source['id']}", end=count)
    if source["kind"] == "mix":      # el "Mix" que genera YouTube a partir de un video (lista RD + id)
        return _flat(mix_url(source["id"]), end=count)
    q, mode = source["q"], source["mode"]
    if mode == "videos":
        return search_videos(q, count)
    if mode == "listas":
        return search_lists(q, count)
    # mixto: videos y, entre ellos, listas (como la web de YouTube); si falla una parte, se muestra la otra
    res = {}

    def lists():
        try:
            res["lists"] = search_lists(q, max(6, count // 5))
        except Exception:
            res["lists"] = []
    t = threading.Thread(target=lists, daemon=True)
    t.start()
    videos = search_videos(q, count)
    t.join()
    out, lst = [], list(res.get("lists", []))
    for i, v in enumerate(videos):
        out.append(v)
        if (i + 1) % 4 == 0 and lst:
            out.append(lst.pop(0))
    return out + lst


# ---------- historial y posición guardada ----------
def fmt_time(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def resume_pos(url):
    """Segundos donde mpv guardó la posición de este video (None si no hay). mpv nombra el archivo con el
    MD5 de la URL en mayúsculas y escribe una línea start=SEGUNDOS."""
    name = hashlib.md5(url.encode()).hexdigest().upper()
    try:
        with open(os.path.join(WATCH_LATER, name), encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("start="):
                    pos = float(line[6:])
                    return pos if pos >= 5 else None
    except (OSError, ValueError):
        pass
    return None


def history_load():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for e in raw if isinstance(raw, list) else []:     # el archivo es local, pero se valida igual
        if not isinstance(e, dict) or not VIDEO_ID.match(str(e.get("id", ""))) or e.get("kind") not in ("video", "list"):
            continue
        vid, is_list = e["id"], e["kind"] == "list"
        out.append({
            "id": vid, "kind": e["kind"], "title": clean(e.get("title")) or "(sin título)",
            "channel": clean(e.get("channel")), "duration": clean(e.get("duration")),
            "views": e.get("views") if isinstance(e.get("views"), (int, float)) else None,
            "secs": e.get("secs") if isinstance(e.get("secs"), (int, float)) else None,
            "thumb": allowed_thumb(e.get("thumb")) if is_list else None,
            "url": f"https://www.youtube.com/playlist?list={vid}" if is_list else f"https://www.youtube.com/watch?v={vid}",
        })
    return out


def history_add(item):
    entries = [e for e in history_load() if e["id"] != item["id"]]
    keep = {k: item.get(k) for k in ("id", "kind", "title", "channel", "duration", "views", "secs", "thumb")}
    entries = ([keep] + entries)[:HISTORY_MAX]
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        os.replace(tmp, HISTORY_FILE)
    except OSError:
        pass


def local_files(sub=""):
    """Archivos descargados en DOWNLOADS[/sub]: id -> ruta. El id va entre corchetes al final del nombre ([id].ext)."""
    out, base = {}, os.path.join(DOWNLOADS, sub)
    try:
        for name in os.listdir(base):
            m = LOCAL_NAME.search(name)
            if m and os.path.isfile(os.path.join(base, name)):
                out[m.group(1)] = os.path.join(base, name)
    except OSError:
        pass
    return out


def to_png(jpg_path, png_path):
    try:
        from PIL import Image
        with Image.open(jpg_path) as im:
            im = im.convert("RGB")
            im.thumbnail((480, 270))
            im.save(png_path, "PNG")
    except ImportError:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", jpg_path, "-vf", "scale=480:-2", "-f", "image2",
                        "-c:v", "png", png_path], check=True)


def fetch_thumb(vid, url=None):
    png = os.path.join(CACHE, vid + ".png")
    if os.path.exists(png):
        return png
    jpg = os.path.join(CACHE, vid + ".jpg")
    url = allowed_thumb(url) if url else THUMB_URL.format(vid)
    if not url:
        raise ValueError("miniatura no permitida")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
        self.source = None         # {"kind": "search", "q", "mode"} | {"kind": "playlist", "id", "title"}
        self.count = 0
        self.exhausted = False
        self.search_mode = MODES[0]
        self.leader = None         # None = normal; lista = ruta abierta en el menú de la tecla líder
        self.stack = []            # vistas anteriores, para volver con b
        self.scan_local()          # self.local: id -> archivo (el video gana al audio); self.has_video: ids
        self.downloads = {}        # id -> (proceso yt-dlp, título, "audio"|"video")
        self.players = []          # procesos mpv lanzados (se recogen al terminar para no dejar zombis)
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
            vid, url = self.thumbq.get()
            try:
                fetch_thumb(vid, url)
                self.events.put(("thumb", vid, True))
            except Exception:
                self.events.put(("thumb", vid, False))

    def start_load(self, source, count, append=False):
        self.gen += 1
        gen = self.gen
        self.source, self.count = source, count
        what = {"history": "historial", "playlist": f"lista “{source.get('title')}”", "mix": f"mix “{source.get('title')}”"}.get(
            source["kind"], f"“{source.get('q')}” ({source.get('mode')})")
        self.status = clean(f"Cargando {what}…")
        self.dirty = True

        def work():
            try:
                self.events.put(("results", gen, fetch(source, count), append, count))
            except Exception as e:
                self.events.put(("error", gen, str(e)))
        threading.Thread(target=work, daemon=True).start()

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
                self.status = "✘ mpv no pudo abrir el video tras 3 intentos (mira ~/.cache/ytk/mpv.log)"
        if len(alive) != len(self.players):
            self.dirty = True              # un mpv terminó: puede haber guardado una posición nueva
        self.players = alive
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

    def summary(self):
        src, n = self.source, len(self.items)
        if not src:
            return "Pulsa / para buscar"
        if not n:
            return "Sin resultados"
        lists = sum(1 for i in self.items if i["kind"] == "list")
        if src["kind"] == "history":
            return f"Historial · {n} (lo último primero)"
        if src["kind"] in ("playlist", "mix"):
            return clean(f"{'Mix' if src['kind'] == 'mix' else 'Lista'} “{src['title']}” · {n} videos")
        extra = f" ({lists} listas)" if lists else ""
        return clean(f"{n} resultados{extra} para “{src['q']}” · modo {src['mode']}")

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
        head = f" ytk · {self.status}" + ("" if self.source else f" · modo {self.search_mode}")
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
                pos = resume_pos(it["url"]) if it["kind"] == "video" else None
                if it["kind"] == "list":
                    parts = ("LISTA", it["channel"])
                elif pos:
                    parts = (f"▶ {fmt_time(pos)}/{it['duration'] or '?'}", it["channel"])
                else:
                    parts = (it["channel"], it["duration"], human(it["views"]))
                if it["kind"] == "video" and it["id"] in self.downloads:
                    parts = ("⏳ descargando",) + tuple(parts)
                elif it["kind"] == "video" and it["id"] in self.local:
                    parts = ("⬇",) + tuple(parts)
                meta = fit(" · ".join(p for p in parts if p), img_c)
                if pos and it.get("secs"):
                    filled = max(1, min(img_c, round(pos / it["secs"] * img_c)))
                    out.append(f"\x1b[{y0 + img_r + 3};{x0}H\x1b[1m{'━' * filled}\x1b[0m\x1b[2m{'─' * (img_c - filled)}\x1b[0m")
                on, off = ("\x1b[7;1m", "\x1b[0m") if selected else ("", "")
                out.append(f"\x1b[{y0 + img_r};{x0}H{on}{t1}{off}")
                out.append(f"\x1b[{y0 + img_r + 1};{x0}H{on}{t2}{off}")
                out.append(f"\x1b[{y0 + img_r + 2};{x0}H\x1b[2m{meta}\x1b[0m")
                if selected:
                    for k in range(img_r + 3):
                        out.append(f"\x1b[{y0 + k};{x0 - 1}H\x1b[1m▌\x1b[0m")
        hint = (" Enter busca · Esc cancela · Tab cambia el modo" if self.mode == "prompt"
                else " espacio menú · hjkl mover · Enter reproducir · / buscar · Tab modo · q salir")
        out.append(f"\x1b[{rows};1H\x1b[2m{fit(hint, cols)}\x1b[0m")
        if self.leader is not None:
            node = self.leader_node()
            col_w = max(24, cols // 3)
            per_row = max(1, cols // col_w)
            entries = [f"\x1b[1m{k}\x1b[0m  {txt}" + ("" if isinstance(a, str) else " ›") for k, (txt, a) in node.items()]
            lines = [entries[i:i + per_row] for i in range(0, len(entries), per_row)]
            top = rows - len(lines) - 1            # fila del título del panel
            path = " ".join(["espacio"] + self.leader)
            out.append(f"\x1b[{top};1H\x1b[0m\x1b[7m{fit(' ' + path + '  ·  Esc cancela', cols)}\x1b[0m")
            for i, row in enumerate(lines):
                out.append(f"\x1b[{top + 1 + i};1H\x1b[2K" + "".join(
                    cell + " " * max(0, col_w - width(re.sub(r"\x1b\[[0-9;]*m", "", cell))) for cell in row))
            places = [(y, x, img) for (y, x, img) in places if y + img_r - 1 < top]
        cursor = None
        if self.mode == "prompt":
            bw = min(cols - 4, max(46, cols // 2))
            bx, by = (cols - bw) // 2 + 1, max(2, rows // 3 - 1)
            inner = bw - 4
            title = " Buscar en YouTube "
            sub = f" modo {self.search_mode} · Tab cambia "
            vis_text = self.prompt
            while width(vis_text) > inner - 1:          # si es largo, se ve el final
                vis_text = vis_text[1:]
            top = "╭─" + title + "─" * max(0, bw - 3 - width(title)) + "╮"
            bot = "╰─" + sub + "─" * max(0, bw - 3 - width(sub)) + "╯"
            out.append(f"\x1b[{by};{bx}H\x1b[0;1m{top}")
            out.append(f"\x1b[{by + 1};{bx}H│ {fit(vis_text, inner)} │")
            out.append(f"\x1b[{by + 2};{bx}H{bot}\x1b[0m")
            cursor = (by + 1, bx + 2 + width(vis_text))
            places = [(y, x, img) for (y, x, img) in places if y + img_r - 1 < by or y > by + 2]
        for y, x, img in places:
            out.append(f"\x1b[{y};{x}H")
            sys.stdout.write("".join(out))
            out = []
            gfx_place(img, img_c, img_r)
        out.append(f"\x1b[{cursor[0]};{cursor[1]}H\x1b[?25h" if cursor else "\x1b[?25l")
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # --- acciones ---
    def launch(self, url, title=None, label=""):
        if not shutil.which("mpv"):
            self.status = "mpv no está instalado"
            return
        os.makedirs(CACHE, exist_ok=True)
        os.makedirs(WATCH_LATER, exist_ok=True)
        cmd = ["mpv", "--force-window=immediate", "--ytdl-format=" + ytdl_format(),
               "--save-position-on-quit", "--resume-playback=yes", "--watch-later-directory=" + WATCH_LATER,
               *(["--title=" + title] if title else []), *shlex.split(os.environ.get("YTK_MPV_ARGS", "")), "--", url]
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
        if it["kind"] == "list":
            self.launch(it["url"], label=f"lista {it['title']}")
        elif it["id"] in self.local and os.path.isfile(self.local[it["id"]]):
            self.launch(self.local[it["id"]], title=it["title"], label="(local) ")
        else:
            self.launch(it["url"], title=it["title"])

    def scan_local(self):
        video = local_files()
        self.has_video = set(video)
        self.local = {**local_files("audio"), **video}

    def download(self, kind):
        if not self.items or self.items[self.sel]["kind"] != "video":
            self.status = "Elige un video para descargarlo (las listas no se descargan)"
            return
        it = self.items[self.sel]
        if not shutil.which("yt-dlp"):
            self.status = "yt-dlp no está instalado"
            return
        if it["id"] in self.downloads:
            self.status = "Ya se está descargando"
            return
        if it["id"] in (self.has_video if kind == "video" else local_files("audio")):
            self.status = f"El {kind} ya está descargado (Enter lo reproduce)"
            return
        outdir = os.path.join(DOWNLOADS, "audio") if kind == "audio" else DOWNLOADS
        os.makedirs(outdir, exist_ok=True)
        os.makedirs(CACHE, exist_ok=True)
        fmt = ["-x"] if kind == "audio" else ["-f", ytdl_format(), "--merge-output-format", "mkv"]
        log = open(os.path.join(CACHE, "dl.log"), "ab")
        proc = subprocess.Popen(
            ["yt-dlp", "--no-playlist", "--windows-filenames", "--no-part", "-o",
             os.path.join(outdir, "%(title).120B [%(id)s].%(ext)s"), *fmt, "--", it["url"]],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        log.close()
        self.downloads[it["id"]] = (proc, it["title"], kind)
        self.status = clean(f"⏳ descargando {kind} en {outdir}: {it['title']}")

    def play_all(self):
        """Reproduce de corrido la lista o el mix que se está viendo."""
        src = self.source
        if not src or src["kind"] not in ("playlist", "mix"):
            self.status = "P reproduce la lista o el mix que estás viendo (ábrelo con o)"
            return
        url = mix_url(src["id"]) if src["kind"] == "mix" else f"https://www.youtube.com/playlist?list={src['id']}"
        self.launch(url, label=("mix " if src["kind"] == "mix" else "lista ") + str(src.get("title")))

    def move(self, delta, absolute=False):
        n = len(self.items)
        if not n:
            return
        self.sel = max(0, min(n - 1, delta if absolute else self.sel + delta))

    def more(self):
        if self.source and not self.exhausted and self.count < 200:
            self.start_load(self.source, self.count + PAGE, append=True)

    def open_list(self):
        if not self.items:
            return
        it = self.items[self.sel]
        if it["kind"] == "list":
            src = {"kind": "playlist", "id": it["id"], "title": it["title"]}
        else:
            src = {"kind": "mix", "id": it["id"], "title": it["title"]}
        self.stack.append(dict(items=self.items, sel=self.sel, top=self.top, source=self.source,
                               count=self.count, exhausted=self.exhausted))
        self.start_load(src, PAGE)

    def open_history(self):
        self.stack.append(dict(items=self.items, sel=self.sel, top=self.top, source=self.source,
                               count=self.count, exhausted=self.exhausted))
        self.start_load({"kind": "history"}, HISTORY_MAX)

    def back(self):
        if not self.stack:
            return
        v = self.stack.pop()
        self.gen += 1                      # descarta lo que aún esté cargando
        self.items, self.sel, self.top = v["items"], v["sel"], v["top"]
        self.source, self.count, self.exhausted = v["source"], v["count"], v["exhausted"]
        self.status = self.summary()

    def set_mode(self, mode):
        self.search_mode = mode
        src = self.source
        if src and src["kind"] == "search":
            self.start_load({"kind": "search", "q": src["q"], "mode": mode}, PAGE)
        else:
            self.status = f"Modo {mode}"

    def cycle_mode(self):
        self.set_mode(MODES[(MODES.index(self.search_mode) + 1) % len(MODES)])

    def leader_node(self):
        node = MENU
        for k in self.leader or []:
            node = node[k][1]
        return node

    def run_action(self, action):
        """Ejecuta una acción del menú líder. Devuelve False para salir."""
        if action == "search":
            self.mode, self.prompt = "prompt", ""
        elif action.startswith("mode:"):
            self.set_mode(action[5:])
        elif action == "open":
            self.open_list()
        elif action == "history":
            self.open_history()
        elif action == "play_all":
            self.play_all()
        elif action in ("dl_audio", "dl_video"):
            self.download(action[3:])
        elif action == "back":
            self.back()
        elif action == "more":
            self.more()
        elif action == "quit":
            return False
        return True

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
                        self.stack = []
                        self.start_load({"kind": "search", "q": q, "mode": self.search_mode}, PAGE)
                elif t == "bs":
                    self.prompt = self.prompt[:-1]
                elif t == "tab":
                    self.search_mode = MODES[(MODES.index(self.search_mode) + 1) % len(MODES)]
                elif isinstance(t, tuple):
                    self.prompt += t[1]
                continue
            if self.leader is not None:
                if t == "esc":
                    self.leader = None
                elif t == "bs":
                    self.leader = self.leader[:-1] if self.leader else None
                elif isinstance(t, tuple):
                    entry = self.leader_node().get(t[1])
                    if entry is None:
                        self.leader = None
                    elif isinstance(entry[1], dict):
                        self.leader.append(t[1])
                    else:
                        self.leader = None
                        if not self.run_action(entry[1]):
                            return False
                continue
            _, _, ncols, _, _, _, _, vis = self.layout
            key = t[1] if isinstance(t, tuple) else t
            if key == " ":
                self.leader = []
                continue
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
            elif key == "o":
                self.open_list()
            elif key == "H":
                self.open_history()
            elif key == "P":
                self.play_all()
            elif key in ("b", "bs", "esc"):
                self.back()
            elif key == "tab":
                self.cycle_mode()
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
