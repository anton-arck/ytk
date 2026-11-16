"""Consultas a YouTube mediante yt-dlp: búsqueda, listas, canales e información de un video."""

import json
import re
import subprocess
import urllib.parse

from .config import HEIGHT
from .text import clean


CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")   # ids de video (11) y de lista (PL..., hasta ~40)
LIST_PREFIX = ("PL", "RD", "OL", "UU", "LL", "FL")
THUMB_HOSTS = {"i.ytimg.com", "i9.ytimg.com", "yt3.ggpht.com"}
MODES = ["mixto", "videos", "listas"]
CHANNEL_TABS = {"videos": "videos", "playlists": "listas"}   # pestaña de YouTube -> nombre en pantalla
LIST_SEARCH = "https://www.youtube.com/results?search_query={}&sp=EgIQAw%3D%3D"   # filtro: solo listas


def ytdl_format():
    """Sin AV1 ni audio 5.1 (más ligeros de bajar y de decodificar); cae a lo que haya si no existe."""
    h = HEIGHT if HEIGHT.isdigit() else "720"
    return f"bv*[height<={h}][vcodec!^=av01]+ba[audio_channels<=2]/bv*[height<={h}]+ba/b[height<={h}]/b"


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
        cid = str(d.get("channel_id") or "")
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
            "channel_id": cid if CHANNEL_ID.match(cid) else None,
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


def video_info(vid):
    """Datos que la lista plana no trae (fecha, likes, suscriptores, descripción completa...)."""
    p = subprocess.run(["yt-dlp", "-j", "--no-playlist", "--skip-download", "--no-warnings", "--",
                        f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(p.stdout.splitlines()[0])
    except (ValueError, IndexError):
        raise RuntimeError(clean((p.stderr.strip().splitlines() or ["yt-dlp falló"])[-1]))
    num = lambda k: d.get(k) if isinstance(d.get(k), (int, float)) else None
    ud = str(d.get("upload_date") or "")
    desc = "\n".join(clean(l) for l in str(d.get("description") or "").splitlines())[:4000]
    return {
        "date": f"{ud[:4]}-{ud[4:6]}-{ud[6:8]}" if re.fullmatch(r"\d{8}", ud) else "",
        "likes": num("like_count"), "comments": num("comment_count"), "subs": num("channel_follower_count"),
        "views": num("view_count"),
        "res": f"{int(num('width'))}x{int(num('height'))}" + (f" · {int(num('fps'))} fps" if num("fps") else "") if num("width") and num("height") else "",
        "category": clean(", ".join(str(c) for c in (d.get("categories") or [])[:3])),
        "desc": desc,
    }


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
