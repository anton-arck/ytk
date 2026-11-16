"""Navegación: cargar fuentes, abrir listas/canales/información, volver y cambiar de modo."""

import threading

from .config import HISTORY_MAX, PAGE
from .sources import fetch
from .text import clean
from .youtube import CHANNEL_TABS, MODES, video_info


class NavigationMixin:
    """Navegación: cargar fuentes, abrir listas/canales/información, volver y cambiar de modo."""

    def start_load(self, source, count, append=False):
        self.gen += 1
        gen = self.gen
        self.source, self.count = source, count
        what = {"history": "historial", "playlist": f"lista “{source.get('title')}”", "mix": f"mix “{source.get('title')}”",
            "channel": f"canal “{source.get('title')}” ({CHANNEL_TABS.get(source.get('tab'), '')})"}.get(
            source["kind"], f"“{source.get('q')}” ({source.get('mode')})")
        self.status = clean(f"Cargando {what}…")
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
            return "Pulsa / para buscar"
        if not n:
            return "Sin resultados"
        lists = sum(1 for i in self.items if i["kind"] == "list")
        if src["kind"] == "history":
            return f"Historial · {n} (lo último primero)"
        if src["kind"] in ("playlist", "mix"):
            return clean(f"{'Mix' if src['kind'] == 'mix' else 'Lista'} “{src['title']}” · {n} videos")
        if src["kind"] == "channel":
            return clean(f"Canal “{src['title']}” · {CHANNEL_TABS[src['tab']]} · {n} (Tab cambia videos/listas)")
        extra = f" ({lists} listas)" if lists else ""
        return clean(f"{n} resultados{extra} para “{src['q']}” · modo {src['mode']}")

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
            self.status = "Este elemento no trae el canal (búscalo de nuevo)"
            return
        self.info = None
        src = {"kind": "channel", "id": it["channel_id"], "tab": tab, "title": it["channel"] or "canal"}
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
        src = self.source
        if src and src["kind"] == "channel":      # en un canal, Tab alterna entre sus videos y sus listas
            tab = "playlists" if src["tab"] == "videos" else "videos"
            self.start_load({**src, "tab": tab}, PAGE)
            return
        self.set_mode(MODES[(MODES.index(self.search_mode) + 1) % len(MODES)])
