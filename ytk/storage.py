"""Datos en disco: historial, posición guardada por mpv y archivos descargados."""

import hashlib
import json
import os

from .config import DOWNLOADS, HISTORY_FILE, HISTORY_MAX, LOCAL_NAME, WATCH_LATER
from .text import clean
from .youtube import CHANNEL_ID, VIDEO_ID, allowed_thumb


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
            "channel_id": e.get("channel_id") if CHANNEL_ID.match(str(e.get("channel_id") or "")) else None,
            "views": e.get("views") if isinstance(e.get("views"), (int, float)) else None,
            "secs": e.get("secs") if isinstance(e.get("secs"), (int, float)) else None,
            "thumb": allowed_thumb(e.get("thumb")) if is_list else None,
            "url": f"https://www.youtube.com/playlist?list={vid}" if is_list else f"https://www.youtube.com/watch?v={vid}",
        })
    return out


def history_add(item):
    entries = [e for e in history_load() if e["id"] != item["id"]]
    keep = {k: item.get(k) for k in ("id", "kind", "title", "channel", "channel_id", "duration", "views", "secs", "thumb")}
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
