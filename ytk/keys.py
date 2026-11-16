"""Keyboard: the leader-key menu and the handling of each key."""

from .config import PAGE
from .i18n import t, toggle
from .terminal import parse_keys
from .youtube import MODES


# Leader-key menu (space), like LazyVim's which-key: key -> (text key in i18n, action | submenu)
MENU = {
    "f": ("m.search", "search"),
    "m": ("m.mode", {
        "m": ("m.mode_mixed", "mode:mixed"),
        "v": ("m.mode_videos", "mode:videos"),
        "l": ("m.mode_lists", "mode:lists"),
    }),
    "o": ("m.open", "open"),
    "i": ("m.info", "info"),
    "c": ("m.channel", {
        "v": ("m.channel_videos", "channel:videos"),
        "l": ("m.channel_lists", "channel:playlists"),
    }),
    "p": ("m.play_all", "play_all"),
    "a": ("m.dl_audio", "dl_audio"),
    "d": ("m.dl_video", "dl_video"),
    "h": ("m.history", "history"),
    "]": ("m.next", "next"),
    "[": ("m.prev", "prev"),
    "b": ("m.back", "back"),
    "n": ("m.more", "more"),
    "L": ("m.lang", "lang"),
    "q": ("m.quit", "quit"),
}


class KeysMixin:
    """Keyboard: the leader-key menu and the handling of each key."""

    def leader_node(self):
        node = MENU
        for k in self.leader or []:
            node = node[k][1]
        return node

    def run_action(self, action):
        """Run a leader-menu action. Returns False to quit."""
        if action == "search":
            self.mode, self.prompt = "prompt", ""
        elif action.startswith("mode:"):
            self.set_mode(action[5:])
        elif action == "open":
            self.open_list()
        elif action == "info":
            self.open_info()
        elif action.startswith("channel:"):
            self.open_channel(action[8:])
        elif action in ("next", "prev"):
            self.step(1 if action == "next" else -1)
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
        elif action == "lang":
            toggle()
            self.status = t("lang_set")
        elif action == "quit":
            return False
        return True

    def handle(self, data):
        """Returns False to quit."""
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
            if self.info is not None:
                key = t[1] if isinstance(t, tuple) else t
                if key in ("esc", "bs", "i", "q"):
                    self.info = None
                elif key == "c":
                    self.open_channel("videos")
                elif key == "l":
                    self.open_channel("playlists")
                elif key == "enter":
                    self.sel = max(0, self.items.index(self.info)) if self.info in self.items else self.sel
                    self.info = None
                    self.play()
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
            elif key == "i":
                self.open_info()
            elif key == "c":
                self.open_channel("videos")
            elif key == "H":
                self.open_history()
            elif key == "P":
                self.play_all()
            elif key == "]":
                self.step(1)
            elif key == "[":
                self.step(-1)
            elif key in ("b", "bs", "esc"):
                self.back()
            elif key == "tab":
                self.cycle_mode()
            elif key == "/":
                self.mode, self.prompt = "prompt", ""
            elif key == "n":
                self.more()
        return True
