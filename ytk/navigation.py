"""Navigation: load sources, open playlists/channels/info, go back and change mode."""

import threading

from .config import HISTORY_MAX, PAGE
from .sources import fetch
from .text import clean
from .i18n import t
from .youtube import MODES, video_info


class NavigationMixin:
    """Navigation: load sources, open playlists/channels/info, go back and change mode."""

    def start_load(self, source, count, append=False):
        self.gen += 1
        gen = self.gen
        self.source, self.count = source, count
        kind, title = source["kind"], source.get("title")
        if kind == "history":
            what = t("what.history")
        elif kind in ("playlist", "mix"):
            what = t("what." + kind, title=title)
        elif kind == "channel":
            what = t("what.channel", title=title, tab=t("tab." + source.get("tab", "videos")))
        else:
            what = t("what.search", q=source.get("q"), mode=t("mode." + source.get("mode", "mixed")))
        self.status = clean(t("loading", what=what))
        self.dirty = True

        def work():
            try:
                self.events.put(("results", gen, fetch(source, count), append, count))
            except Exception as e:
                self.events.put(("error", gen, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def summary(self):
        src, n = self.source, len(self.items)
        if not src:
            return t("press_search")
        if not n:
            return t("no_results")
        lists = sum(1 for i in self.items if i["kind"] == "list")
        if src["kind"] == "history":
            return t("summary.history", n=n)
        if src["kind"] in ("playlist", "mix"):
            return clean(t("summary." + src["kind"], title=src["title"], n=n))
        if src["kind"] == "channel":
            return clean(t("summary.channel", title=src["title"], tab=t("tab." + src["tab"]), n=n))
        extra = t("summary.extra_lists", n=lists) if lists else ""
        return clean(t("summary.search", n=n, extra=extra, q=src["q"], mode=t("mode." + src["mode"])))

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

    def target_item(self):
        return self.info if self.info is not None else (self.items[self.sel] if self.items else None)

    def open_info(self):
        if not self.items:
            return
        it = self.items[self.sel]
        self.info = it
        if it["kind"] == "video" and it["id"] not in self.info_cache:
            self.info_cache[it["id"]] = "loading"
            vid = it["id"]

            def work():
                try:
                    self.events.put(("info", vid, video_info(vid)))
                except Exception as e:
                    self.events.put(("info", vid, "error: " + clean(e)))
            threading.Thread(target=work, daemon=True).start()

    def open_channel(self, tab):
        it = self.target_item()
        if not it:
            return
        if not it.get("channel_id"):
            self.status = t("channel_missing")
            return
        self.info = None
        src = {"kind": "channel", "id": it["channel_id"], "tab": tab, "title": it["channel"] or "?"}
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
        self.gen += 1                      # discard whatever is still loading
        self.items, self.sel, self.top = v["items"], v["sel"], v["top"]
        self.source, self.count, self.exhausted = v["source"], v["count"], v["exhausted"]
        self.status = self.summary()

    def set_mode(self, mode):
        self.search_mode = mode
        src = self.source
        if src and src["kind"] == "search":
            self.start_load({"kind": "search", "q": src["q"], "mode": mode}, PAGE)
        else:
            self.status = t("mode_set", mode=t("mode." + mode))

    def cycle_mode(self):
        src = self.source
        if src and src["kind"] == "channel":      # inside a channel, Tab toggles between its videos and its playlists
            tab = "playlists" if src["tab"] == "videos" else "videos"
            self.start_load({**src, "tab": tab}, PAGE)
            return
        self.set_mode(MODES[(MODES.index(self.search_mode) + 1) % len(MODES)])
