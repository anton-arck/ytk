"""De dónde salen los elementos que se muestran: búsqueda, lista, mix, canal o historial."""

import threading

from .storage import history_load
from .youtube import _flat, mix_url, search_lists, search_videos


def fetch(source, count):
    """Trae los elementos de una fuente: {"kind": "search", "q", "mode"} o {"kind": "playlist", "id"}."""
    if source["kind"] == "history":
        return history_load()
    if source["kind"] == "playlist":
        return _flat(f"https://www.youtube.com/playlist?list={source['id']}", end=count)
    if source["kind"] == "channel":
        items = _flat(f"https://www.youtube.com/channel/{source['id']}/{source['tab']}", end=count)
        for it in items:     # en las pestañas del canal faltan (o son genéricos) el nombre y el id del canal
            it["channel"], it["channel_id"] = source["title"], source["id"]
        return items
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
