"""Interface languages (Spanish / English): detection, saved preference and text lookup."""

import os

from .config import LANG_FILE

LANGS = ("es", "en")

STRINGS = {
    "es": {
        # status and search
        "press_search": "Pulsa / para buscar",
        "loading": "Cargando {what}…",
        "what.history": "historial",
        "what.playlist": "lista “{title}”",
        "what.mix": "mix “{title}”",
        "what.channel": "canal “{title}” ({tab})",
        "what.search": "“{q}” ({mode})",
        "no_results": "Sin resultados",
        "summary.history": "Historial · {n} (lo último primero)",
        "summary.playlist": "Lista “{title}” · {n} videos",
        "summary.mix": "Mix “{title}” · {n} videos",
        "summary.channel": "Canal “{title}” · {tab} · {n} (Tab cambia videos/listas)",
        "summary.channel_missing": "Canal “{title}” · {tab} · {n} (este canal no tiene {missing})",
        "summary.search": "{n} resultados{extra} para “{q}” · modo {mode}",
        "summary.extra_lists": " ({n} listas)",
        "mode.mixed": "mixto",
        "mode.videos": "videos",
        "mode.lists": "listas",
        "tab.videos": "videos",
        "tab.playlists": "listas",
        "mode_set": "Modo {mode}",
        "channel_missing": "Este elemento no trae el canal (búscalo de nuevo)",
        "untitled": "(sin título)",
        "ytdlp_failed": "yt-dlp falló",
        # playback and downloads
        "mpv_missing": "mpv no está instalado",
        "label.playlist": "lista ",
        "label.mix": "mix ",
        "label.local": "(local) ",
        "step.next": "⏭ siguiente",
        "step.prev": "⏮ anterior",
        "nothing_playing": "No hay nada sonando",
        "play_all_hint": "P reproduce la lista o el mix que estás viendo (ábrelo con o)",
        "mpv_retry": "mpv no pudo abrir el video; reintentando ({n}/{max})…",
        "mpv_gave_up": "✘ mpv no pudo abrir el video tras {max} intentos (mira ~/.cache/ytk/mpv.log)",
        "dl.pick_video": "Elige un video para descargarlo (las listas no se descargan)",
        "dl.no_ytdlp": "yt-dlp no está instalado",
        "dl.running": "Ya se está descargando",
        "dl.already": "El {kind} ya está descargado (Enter lo reproduce)",
        "dl.started": "⏳ descargando {kind} en {outdir}: {title}",
        "dl.done": "✔ descargado ({kind}): {title}",
        "dl.failed": "✘ falló la descarga de {title} (mira ~/.cache/ytk/dl.log)",
        "card.downloading": "⏳ descargando",
        "card.list": "LISTA",
        # drawing
        "head.mode": " · modo {mode}",
        "no_thumb": "sin miniatura",
        "loading_thumb": "cargando…",
        "hint.prompt": " Enter busca · Esc cancela · Tab cambia el modo",
        "hint.normal": " espacio menú · hjkl mover · Enter reproducir · i info · c canal · / buscar · Tab modo · q salir",
        "menu.space": "espacio",
        "menu.cancel": "Esc cancela",
        "box.search": " Buscar en YouTube ",
        "box.search_sub": " modo {mode} · Tab cambia ",
        "box.info": " Información ",
        "info.playlist": "Lista de reproducción",
        "info.playlist_by": "Lista de reproducción · {channel}",
        "info.playlist_keys": "Enter reproduce · o abre la lista · c / l videos y listas del canal · Esc cierra",
        "info.unknown_channel": "(canal desconocido)",
        "info.channel": "Canal: {channel}",
        "info.subs": "suscriptores",
        "info.views": "vistas",
        "info.loading": "cargando más datos…",
        "info.no_more": "no se pudo traer más: {err}",
        "info.no_channel_id": "(sin id de canal: busca de nuevo para poder abrir el canal)",
        "info.video_keys": "c videos del canal · l listas del canal · Enter reproducir · Esc cierra",
        # leader-key menu
        "m.search": "buscar",
        "m.mode": "modo de búsqueda…",
        "m.mode_mixed": "mixto: videos y listas",
        "m.mode_videos": "solo videos",
        "m.mode_lists": "solo listas",
        "m.open": "abrir lista / mix",
        "m.info": "información del video y canal",
        "m.channel": "canal…",
        "m.channel_videos": "videos del canal",
        "m.channel_lists": "listas del canal",
        "m.play_all": "reproducir todo",
        "m.dl_audio": "descargar audio",
        "m.dl_video": "descargar video",
        "m.history": "historial / continuar viendo",
        "m.next": "siguiente canción",
        "m.prev": "canción anterior",
        "m.back": "volver",
        "m.more": "más resultados",
        "m.lang": "idioma: español ⇄ English",
        "m.quit": "salir",
        "lang_set": "Idioma: español",
        # command line
        "cli.need_tty": "ytk necesita una terminal interactiva (kitty).",
        "cli.missing_tool": "Falta {tool}: instálalo (sudo pacman -S {tool}).",
        "cli.help": """ytk: busca videos de YouTube en la terminal y míralos con mpv.

Muestra las miniaturas en una cuadrícula con el protocolo gráfico de kitty (funciona también
dentro de zellij). Necesita: yt-dlp (búsqueda), mpv (reproducción), kitty (imágenes).
Opcional: Pillow (si falta, las miniaturas se convierten con ffmpeg).

Uso: ytk [BÚSQUEDA...]
Opciones: --version, -h/--help
Variables: YTK_HEIGHT (calidad máxima, 720 por defecto), YTK_MPV_ARGS (opciones extra para mpv),
YTK_DOWNLOADS (carpeta de descargas), YTK_LANG (es | en; si no, el idioma del sistema).
Tecla líder: espacio abre un menú (f buscar, m modo, o abrir, p reproducir todo, i información del video,
c canal (v videos, l listas), a/d descargar audio/video, h historial, ] [ siguiente/anterior canción,
b volver, n más, L idioma, q salir).
Teclas: flechas o h j k l mover · Enter reproducir (listas completas) · o abrir una lista o el Mix de un video ·
P reproducir todo lo que ves · Tab cambia el modo (mixto, videos, listas) · b volver · / buscar ·
n más resultados · q salir""",
    },
    "en": {
        "press_search": "Press / to search",
        "loading": "Loading {what}…",
        "what.history": "history",
        "what.playlist": "playlist “{title}”",
        "what.mix": "mix “{title}”",
        "what.channel": "channel “{title}” ({tab})",
        "what.search": "“{q}” ({mode})",
        "no_results": "No results",
        "summary.history": "History · {n} (most recent first)",
        "summary.playlist": "Playlist “{title}” · {n} videos",
        "summary.mix": "Mix “{title}” · {n} videos",
        "summary.channel": "Channel “{title}” · {tab} · {n} (Tab toggles videos/playlists)",
        "summary.channel_missing": "Channel “{title}” · {tab} · {n} (this channel has no {missing})",
        "summary.search": "{n} results{extra} for “{q}” · {mode} mode",
        "summary.extra_lists": " ({n} playlists)",
        "mode.mixed": "mixed",
        "mode.videos": "videos",
        "mode.lists": "playlists",
        "tab.videos": "videos",
        "tab.playlists": "playlists",
        "mode_set": "Mode: {mode}",
        "channel_missing": "This item has no channel (search again)",
        "untitled": "(untitled)",
        "ytdlp_failed": "yt-dlp failed",
        "mpv_missing": "mpv is not installed",
        "label.playlist": "playlist ",
        "label.mix": "mix ",
        "label.local": "(local) ",
        "step.next": "⏭ next",
        "step.prev": "⏮ previous",
        "nothing_playing": "Nothing is playing",
        "play_all_hint": "P plays the playlist or mix you are viewing (open it with o)",
        "mpv_retry": "mpv could not open the video; retrying ({n}/{max})…",
        "mpv_gave_up": "✘ mpv could not open the video after {max} tries (see ~/.cache/ytk/mpv.log)",
        "dl.pick_video": "Pick a video to download (playlists cannot be downloaded)",
        "dl.no_ytdlp": "yt-dlp is not installed",
        "dl.running": "Already downloading",
        "dl.already": "The {kind} is already downloaded (Enter plays it)",
        "dl.started": "⏳ downloading {kind} to {outdir}: {title}",
        "dl.done": "✔ downloaded ({kind}): {title}",
        "dl.failed": "✘ download of {title} failed (see ~/.cache/ytk/dl.log)",
        "card.downloading": "⏳ downloading",
        "card.list": "PLAYLIST",
        "head.mode": " · {mode} mode",
        "no_thumb": "no thumbnail",
        "loading_thumb": "loading…",
        "hint.prompt": " Enter searches · Esc cancels · Tab changes the mode",
        "hint.normal": " space menu · hjkl move · Enter play · i info · c channel · / search · Tab mode · q quit",
        "menu.space": "space",
        "menu.cancel": "Esc cancels",
        "box.search": " Search YouTube ",
        "box.search_sub": " {mode} mode · Tab changes ",
        "box.info": " Info ",
        "info.playlist": "Playlist",
        "info.playlist_by": "Playlist · {channel}",
        "info.playlist_keys": "Enter plays · o opens the playlist · c / l channel videos and playlists · Esc closes",
        "info.unknown_channel": "(unknown channel)",
        "info.channel": "Channel: {channel}",
        "info.subs": "subscribers",
        "info.views": "views",
        "info.loading": "loading more data…",
        "info.no_more": "could not fetch more: {err}",
        "info.no_channel_id": "(no channel id: search again to be able to open the channel)",
        "info.video_keys": "c channel videos · l channel playlists · Enter play · Esc closes",
        "m.search": "search",
        "m.mode": "search mode…",
        "m.mode_mixed": "mixed: videos and playlists",
        "m.mode_videos": "videos only",
        "m.mode_lists": "playlists only",
        "m.open": "open playlist / mix",
        "m.info": "video and channel info",
        "m.channel": "channel…",
        "m.channel_videos": "channel videos",
        "m.channel_lists": "channel playlists",
        "m.play_all": "play all",
        "m.dl_audio": "download audio",
        "m.dl_video": "download video",
        "m.history": "history / continue watching",
        "m.next": "next song",
        "m.prev": "previous song",
        "m.back": "back",
        "m.more": "more results",
        "m.lang": "language: English ⇄ español",
        "m.quit": "quit",
        "lang_set": "Language: English",
        "cli.need_tty": "ytk needs an interactive terminal (kitty).",
        "cli.missing_tool": "Missing {tool}: install it (sudo pacman -S {tool}).",
        "cli.help": """ytk: search YouTube from the terminal and watch with mpv.

Shows thumbnails in a grid using kitty's graphics protocol (also works inside zellij).
Requires: yt-dlp (search), mpv (playback), kitty (images).
Optional: Pillow (if missing, thumbnails are converted with ffmpeg).

Usage: ytk [SEARCH...]
Options: --version, -h/--help
Variables: YTK_HEIGHT (max quality, 720 by default), YTK_MPV_ARGS (extra mpv options),
YTK_DOWNLOADS (downloads folder), YTK_LANG (es | en; otherwise the system language).
Leader key: space opens a menu (f search, m mode, o open, p play all, i video info,
c channel (v videos, l playlists), a/d download audio/video, h history, ] [ next/previous song,
b back, n more, L language, q quit).
Keys: arrows or h j k l move · Enter play (whole playlists) · o open a playlist or a video's Mix ·
P play everything you see · Tab changes the mode (mixed, videos, playlists) · b back · / search ·
n more results · q quit""",
    },
}

_lang = None


def _system_lang():
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v and v not in ("C", "POSIX"):
            return "es" if v.lower().startswith("es") else "en"
    return "en"


def detect():
    """Order: YTK_LANG, then the preference saved with space L, then the system language."""
    forced = os.environ.get("YTK_LANG", "").strip().lower()[:2]
    if forced in LANGS:
        return forced
    try:
        with open(LANG_FILE, encoding="utf-8") as f:
            saved = f.read().strip()
        if saved in LANGS:
            return saved
    except OSError:
        pass
    return _system_lang()


def lang():
    global _lang
    if _lang is None:
        _lang = detect()
    return _lang


def set_lang(code, save=True):
    global _lang
    _lang = code if code in LANGS else "en"
    if save:
        try:
            os.makedirs(os.path.dirname(LANG_FILE), exist_ok=True)
            with open(LANG_FILE, "w", encoding="utf-8") as f:
                f.write(_lang)
        except OSError:
            pass


def toggle():
    set_lang("en" if lang() == "es" else "es")
    return lang()


def t(key, **kw):
    s = STRINGS[lang()].get(key) or STRINGS["en"][key]
    return s.format(**kw) if kw else s
