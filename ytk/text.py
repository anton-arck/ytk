"""Text utilities: column widths, clipping, sanitising of external text and number/time formats."""

import unicodedata


def char_w(ch):
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def width(s):
    return sum(char_w(c) for c in s)


def clip(s, w):
    out, res = 0, []
    for c in s:
        k = char_w(c)
        if out + k > w:
            break
        res.append(c)
        out += k
    return "".join(res), out


def fit(s, w):
    """Clip with … or pad with spaces to exactly w columns."""
    if w <= 0:
        return ""
    if width(s) <= w:
        return s + " " * (w - width(s))
    t, o = clip(s, w - 1)
    return t + "…" + " " * (w - 1 - o)


def wrap2(s, w):
    """Split a title into two lines of w columns (the second ends with … if it does not fit)."""
    words, first, i = s.split(), "", 0
    while i < len(words):
        t = (first + " " + words[i]).strip()
        if width(t) > w:
            break
        first, i = t, i + 1
    if not first:
        first, _ = clip(s, w)
        rest = s[len(first):]
    else:
        rest = " ".join(words[i:])
    return fit(first, w), fit(rest, w)


def wrap_lines(s, w, limit=None):
    """Split a text into lines of w columns keeping line breaks (limit = maximum number of lines)."""
    out = []
    for para in str(s).split("\n"):
        line = ""
        for word in para.split():
            while width(word) > w:                      # word longer than the line: split it
                head, _ = clip(word, w)
                if line:
                    out.append(line)
                    line = ""
                out.append(head)
                word = word[len(head):]
            if line and width(line) + 1 + width(word) > w:
                out.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        out.append(line)
    while out and not out[-1]:
        out.pop()
    if limit is not None and len(out) > limit:
        out = out[:limit]
        out[-1] = fit(out[-1], w - 1).rstrip() + "…"
    return out


def clean(s):
    """Strip every control or format character (Cc, Cf...) from external text: prevents injecting
    escape sequences into the terminal through titles, channel names or error messages."""
    s = "".join(" " if c in "\t\r\n" else c for c in str(s or ""))
    return "".join(c for c in s if not unicodedata.category(c).startswith("C")).strip()


def human(n):
    if n is None:
        return ""
    for lim, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= lim:
            return f"{n / lim:.1f}".rstrip("0").rstrip(".") + suf
    return str(int(n))


def fmt_time(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
