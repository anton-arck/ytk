"""Dibujo: cuadrícula de miniaturas, panel de información, menú líder y cuadro de búsqueda."""

import re
import sys

from .config import GRID_COLS, GRID_ROWS, MIN_CELL_W
from .storage import resume_pos
from .terminal import gfx_place, term_size
from .text import fit, fmt_time, human, width, wrap2, wrap_lines


class ViewMixin:
    """Dibujo: cuadrícula de miniaturas, panel de información, menú líder y cuadro de búsqueda."""

    # --- dibujo ---
    def compute_layout(self):
        rows, cols, cw, ch = term_size()
        ncols = max(1, min(GRID_COLS, cols // MIN_CELL_W))
        cell_w = cols // ncols
        img_c = max(8, cell_w - 2)
        img_r = max(3, round(img_c * cw * 9 / 16 / ch))
        # la imagen se reduce (manteniendo 16:9) para que quepan GRID_ROWS filas en la altura disponible
        room = (rows - 2) // GRID_ROWS - 4
        if 3 <= room < img_r:
            img_r = room
            img_c = max(8, min(img_c, round(img_r * ch * 16 / 9 / cw)))
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
                tw = cell_w - 2          # el texto usa todo el ancho de la celda (la imagen puede ser más angosta)
                t1, t2 = wrap2(it["title"], tw)
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
        hint = (" Enter busca · Esc cancela · Tab cambia el modo" if self.mode == "prompt"
                else " espacio menú · hjkl mover · Enter reproducir · i info · c canal · / buscar · Tab modo · q salir")
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
        if self.info is not None:
            lines = self.info_lines(min(cols - 4, 92) - 4)
            bw = min(cols - 4, 92)
            bh = min(len(lines) + 2, rows - 3)
            bx, by = (cols - bw) // 2 + 1, 2
            inner = bw - 4
            ttl = " Información "
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

    def info_lines(self, w):
        """Líneas (estilo, texto) del panel de información del elemento self.info."""
        it = self.info
        ex = self.info_cache.get(it["id"])
        ex = ex if isinstance(ex, dict) else {}
        B, D = "\x1b[1m", "\x1b[2m"
        lines = [(B, t) for t in wrap_lines(it["title"], w, 3)] + [("", "")]
        if it["kind"] == "list":
            lines += [("", f"Lista de reproducción · {it['channel']}" if it["channel"] else "Lista de reproducción"),
                      (D, it["url"]), ("", ""), (D, "Enter reproduce · o abre la lista · c / l videos y listas del canal · Esc cierra")]
            return lines
        chan = it["channel"] or "(canal desconocido)"
        if ex.get("subs") is not None:
            chan += f" · {human(ex['subs'])} suscriptores"
        lines.append((B, "Canal: " + chan))
        stats = [it["duration"], (human(ex.get("views") if ex.get("views") is not None else it["views"]) + " vistas") if (ex.get("views") or it["views"]) else "",
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
            lines.append((D, "cargando más datos…"))
        elif isinstance(state, str):
            lines.append((D, "no se pudo traer más: " + state))
        elif ex.get("desc"):
            lines += [("", t) for t in wrap_lines(ex["desc"], w, 12)]
        elif it.get("channel_id") is None:
            lines.append((D, "(sin id de canal: busca de nuevo para poder abrir el canal)"))
        lines += [("", ""), (D, "c videos del canal · l listas del canal · Enter reproducir · Esc cierra")]
        return lines
