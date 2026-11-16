"""Drawing: thumbnail grid, info panel, leader menu and search box."""

import re
import sys

from .config import GRID_COLS, GRID_ROWS, MIN_CELL_W
from .i18n import t
from .storage import resume_pos
from .terminal import gfx_place, term_size
from .text import fit, fmt_time, human, width, wrap2, wrap_lines


class ViewMixin:
    """Drawing: thumbnail grid, info panel, leader menu and search box."""

    # --- drawing ---
    def compute_layout(self):
        rows, cols, cw, ch = term_size()
        ncols = max(1, min(GRID_COLS, cols // MIN_CELL_W))
        cell_w = cols // ncols
        img_c = max(8, cell_w - 2)
        img_r = max(3, round(img_c * cw * 9 / 16 / ch))
        # the image shrinks (keeping 16:9) so GRID_ROWS rows fit in the available height
        room = (rows - 2) // GRID_ROWS - 4
        if 3 <= room < img_r:
            img_r = room
            img_c = max(8, min(img_c, round(img_r * ch * 16 / 9 / cw)))
        cell_h = img_r + 4          # image + 2 title lines + 1 data line + 1 spacer
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
        # ED 2 (\x1b[2J) is not used: kitty discards the images already sent when it runs; clear line by line instead.
        out = ["\x1b_Ga=d,d=a,q=2\x1b\\"] + [f"\x1b[{y};1H\x1b[2K" for y in range(1, rows + 1)]
        head = f" ytk · {self.status}" + ("" if self.source else t("head.mode", mode=t("mode." + self.search_mode)))
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
                    msg = t("no_thumb") if state == "fail" else t("loading_thumb")
                    out.append(f"\x1b[{y0 + img_r // 2};{x0}H\x1b[2m{fit(msg, img_c)}\x1b[0m")
                tw = cell_w - 2          # the text uses the whole cell width (the image may be narrower)
                t1, t2 = wrap2(it["title"], tw)
                pos = resume_pos(it["url"]) if it["kind"] == "video" else None
                if it["kind"] == "list":
                    parts = (t("card.list"), it["channel"])
                elif pos:
                    parts = (f"▶ {fmt_time(pos)}/{it['duration'] or '?'}", it["channel"])
                else:
                    parts = (it["channel"], it["duration"], human(it["views"]))
                if it["kind"] == "video" and it["id"] in self.downloads:
                    parts = (t("card.downloading"),) + tuple(parts)
                elif it["kind"] == "video" and it["id"] in self.local:
                    parts = ("⬇",) + tuple(parts)
                meta = fit(" · ".join(p for p in parts if p), tw)
                if pos and it.get("secs"):
                    filled = max(1, min(tw, round(pos / it["secs"] * tw)))
                    out.append(f"\x1b[{y0 + img_r + 3};{x0}H\x1b[1m{'━' * filled}\x1b[0m\x1b[2m{'─' * (tw - filled)}\x1b[0m")
                on, off = ("\x1b[7;1m", "\x1b[0m") if selected else ("", "")
                out.append(f"\x1b[{y0 + img_r};{x0}H{on}{t1}{off}")
                out.append(f"\x1b[{y0 + img_r + 1};{x0}H{on}{t2}{off}")
                out.append(f"\x1b[{y0 + img_r + 2};{x0}H\x1b[2m{meta}\x1b[0m")
                if selected:
                    for k in range(img_r + 3):
                        out.append(f"\x1b[{y0 + k};{x0 - 1}H\x1b[1m▌\x1b[0m")
        hint = t("hint.prompt") if self.mode == "prompt" else t("hint.normal")
        out.append(f"\x1b[{rows};1H\x1b[2m{fit(hint, cols)}\x1b[0m")
        if self.leader is not None:
            node = self.leader_node()
            col_w = max(24, cols // 3)
            per_row = max(1, cols // col_w)
            entries = [f"\x1b[1m{k}\x1b[0m  {t(txt)}" + ("" if isinstance(a, str) else " ›") for k, (txt, a) in node.items()]
            lines = [entries[i:i + per_row] for i in range(0, len(entries), per_row)]
            top = rows - len(lines) - 1            # row of the panel title
            path = " ".join([t("menu.space")] + self.leader)
            out.append(f"\x1b[{top};1H\x1b[0m\x1b[7m{fit(' ' + path + '  ·  ' + t('menu.cancel'), cols)}\x1b[0m")
            for i, row in enumerate(lines):
                out.append(f"\x1b[{top + 1 + i};1H\x1b[2K" + "".join(
                    cell + " " * max(0, col_w - width(re.sub(r"\x1b\[[0-9;]*m", "", cell))) for cell in row))
            places = [(y, x, img) for (y, x, img) in places if y + img_r - 1 < top]
        cursor = None
        if self.info is not None:
            lines = self.info_lines(min(cols - 4, 92) - 4)
            bw = min(cols - 4, 92)
            bh = min(len(lines) + 2, rows - 3)
            bx, by = (cols - bw) // 2 + 1, 2
            inner = bw - 4
            ttl = t("box.info")
            out.append(f"\x1b[{by};{bx}H\x1b[0;1m╭─" + ttl + "─" * max(0, bw - 3 - width(ttl)) + "╮\x1b[0m")
            for i in range(bh - 2):
                style, text = lines[i]
                out.append(f"\x1b[{by + 1 + i};{bx}H\x1b[0m│ {style}{fit(text, inner)}\x1b[0m │")
            out.append(f"\x1b[{by + bh - 1};{bx}H\x1b[0m╰" + "─" * (bw - 2) + "╯")
            places = [(y, x, img) for (y, x, img) in places if y + img_r - 1 < by or y > by + bh - 1]
        if self.mode == "prompt":
            bw = min(cols - 4, max(46, cols // 2))
            bx, by = (cols - bw) // 2 + 1, max(2, rows // 3 - 1)
            inner = bw - 4
            title = t("box.search")
            sub = t("box.search_sub", mode=t("mode." + self.search_mode))
            vis_text = self.prompt
            while width(vis_text) > inner - 1:          # if it is long, show the end
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

    def info_lines(self, w):
        """Lines (style, text) of the info panel for the item self.info."""
        it = self.info
        ex = self.info_cache.get(it["id"])
        ex = ex if isinstance(ex, dict) else {}
        B, D = "\x1b[1m", "\x1b[2m"
        lines = [(B, t) for t in wrap_lines(it["title"], w, 3)] + [("", "")]
        if it["kind"] == "list":
            lines += [("", t("info.playlist_by", channel=it["channel"]) if it["channel"] else t("info.playlist")),
                      (D, it["url"]), ("", ""), (D, t("info.playlist_keys"))]
            return lines
        chan = it["channel"] or t("info.unknown_channel")
        if ex.get("subs") is not None:
            chan += f" · {human(ex['subs'])} {t('info.subs')}"
        lines.append((B, t("info.channel", channel=chan)))
        stats = [it["duration"], (human(ex.get("views") if ex.get("views") is not None else it["views"]) + " " + t("info.views")) if (ex.get("views") or it["views"]) else "",
                 f"👍 {human(ex['likes'])}" if ex.get("likes") is not None else "",
                 f"💬 {human(ex['comments'])}" if ex.get("comments") is not None else "", ex.get("date", "")]
        lines.append(("", " · ".join(x for x in stats if x)))
        extra = " · ".join(x for x in (ex.get("res"), ex.get("category")) if x)
        if extra:
            lines.append((D, extra))
        lines.append((D, it["url"]))
        lines.append(("", ""))
        state = self.info_cache.get(it["id"])
        if state == "loading":
            lines.append((D, t("info.loading")))
        elif isinstance(state, str):
            lines.append((D, t("info.no_more", err=state)))
        elif ex.get("desc"):
            lines += [("", t) for t in wrap_lines(ex["desc"], w, 12)]
        elif it.get("channel_id") is None:
            lines.append((D, t("info.no_channel_id")))
        lines += [("", ""), (D, t("info.video_keys"))]
        return lines
