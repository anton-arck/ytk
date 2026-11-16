"""Thumbnail download and conversion."""

import os
import subprocess
import urllib.request

from .config import CACHE, THUMB_URL
from .youtube import allowed_thumb


def to_png(jpg_path, png_path):
    try:
        from PIL import Image
        with Image.open(jpg_path) as im:
            im = im.convert("RGB")
            im.thumbnail((480, 270))
            im.save(png_path, "PNG")
    except ImportError:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", jpg_path, "-vf", "scale=480:-2", "-f", "image2",
                        "-c:v", "png", png_path], check=True)


def fetch_thumb(vid, url=None):
    png = os.path.join(CACHE, vid + ".png")
    if os.path.exists(png):
        return png
    jpg = os.path.join(CACHE, vid + ".jpg")
    url = allowed_thumb(url) if url else THUMB_URL.format(vid)
    if not url:
        raise ValueError("miniatura no permitida")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as r, open(jpg, "wb") as f:
        f.write(r.read())
    to_png(jpg, png + ".tmp")
    os.replace(png + ".tmp", png)
    os.unlink(jpg)
    return png
