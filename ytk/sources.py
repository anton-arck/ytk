"""Where the displayed items come from: search, playlist, mix, channel or history."""

import threading

from .storage import history_load
from .youtube import _flat, mix_url, search_lists, search_videos


def fetch(source, count):
    """Fetch the items of a source: {"kind": "search", "q", "mode"}, {"kind": "playlist", "id"}, etc."""
    if source["kind"] == "history":
        return history_load()
    if source["kind"] == "playlist":
        return _flat(f"https://www.youtube.com/playlist?list={source['id']}", end=count)
    if source["kind"] == "channel":
        items = _flat(f"https://www.youtube.com/channel/{source['id']}/{source['tab']}", end=count)
        for it in items:     # channel tabs lack the channel name and id (or have generic ones)
            it["channel"], it["channel_id"] = source["title"], source["id"]
        return items
    if source["kind"] == "mix":      # the "Mix" YouTube generates from a video (RD playlist + id)
        return _flat(mix_url(source["id"]), end=count)
    q, mode = source["q"], source["mode"]
    if mode == "videos":
        return search_videos(q, count)
    if mode == "lists":
        return search_lists(q, count)
    # mixed: videos with playlists interspersed (like the YouTube website); if one part fails, the other is shown
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
