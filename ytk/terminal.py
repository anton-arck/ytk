"""Terminal: tamaño, protocolo gráfico de kitty y lectura de teclas."""

import base64
import fcntl
import re
import shutil
import struct
import sys
import termios


def term_size():
    """filas, columnas, ancho y alto de una celda en píxeles (con valores por defecto)."""
    try:
        r, c, xp, yp = struct.unpack("HHHH", fcntl.ioctl(1, termios.TIOCGWINSZ, b"\0" * 8))
    except OSError:
        sz = shutil.get_terminal_size()
        r, c, xp, yp = sz.lines, sz.columns, 0, 0
    return r, c, (xp // c if xp and c else 9), (yp // r if yp and r else 18)


def gfx(ctrl, payload=""):
    sys.stdout.write("\x1b_G" + ctrl + (";" + payload if payload else "") + "\x1b\\")


def gfx_transmit(img_id, png):
    """Guarda la imagen en el terminal (sin mostrarla); se coloca después con gfx_place."""
    b = base64.standard_b64encode(png).decode()
    chunks = [b[i:i + 4096] for i in range(0, len(b), 4096)] or [""]
    for i, ch in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        gfx(f"a=t,f=100,i={img_id},q=2,m={more}" if i == 0 else f"m={more},q=2", ch)


def gfx_place(img_id, cols, rows):
    gfx(f"a=p,i={img_id},c={cols},r={rows},C=1,q=2")


CSI = re.compile(rb"\x1b\[([0-9;]*)([A-Za-z~])")


SS3 = re.compile(rb"\x1bO([A-Za-z])")


CSI_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}
TILDE_KEYS = {"1": "home", "7": "home", "4": "end", "8": "end", "5": "pgup", "6": "pgdn", "3": "del"}


def parse_keys(data):
    toks, i = [], 0
    while i < len(data):
        b = data[i]
        if b == 0x1b:
            m = CSI.match(data, i) or SS3.match(data, i)
            if m:
                i = m.end()
                if m.re is SS3:
                    toks.append(CSI_KEYS.get(m.group(1).decode(), "?"))
                elif m.group(2) == b"~":
                    toks.append(TILDE_KEYS.get(m.group(1).decode().split(";")[0], "?"))
                else:
                    toks.append(CSI_KEYS.get(m.group(2).decode(), "?"))
            else:
                toks.append("esc")
                i += 1
        elif b in (0x0d, 0x0a):
            toks.append("enter")
            i += 1
        elif b in (0x7f, 0x08):
            toks.append("bs")
            i += 1
        elif b == 0x03:
            toks.append("quit")
            i += 1
        elif b == 0x09:
            toks.append("tab")
            i += 1
        elif b < 0x20:
            i += 1
        else:
            j = i
            while j < len(data) and data[j] >= 0x20 and data[j] != 0x7f:
                j += 1
            toks.extend(("ch", c) for c in data[i:j].decode("utf-8", "ignore"))
            i = j
    return toks
