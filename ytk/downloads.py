"""Descargas de audio y video en segundo plano y archivos locales."""

import os
import shutil
import subprocess

from .config import CACHE, DOWNLOADS
from .storage import local_files
from .text import clean
from .youtube import ytdl_format


class DownloadsMixin:
    """Descargas de audio y video en segundo plano y archivos locales."""

    def scan_local(self):
        video = local_files()
        self.has_video = set(video)
        self.local = {**local_files("audio"), **video}

    def download(self, kind):
        if not self.items or self.items[self.sel]["kind"] != "video":
            self.status = "Elige un video para descargarlo (las listas no se descargan)"
            return
        it = self.items[self.sel]
        if not shutil.which("yt-dlp"):
            self.status = "yt-dlp no está instalado"
            return
        if it["id"] in self.downloads:
            self.status = "Ya se está descargando"
            return
        if it["id"] in (self.has_video if kind == "video" else local_files("audio")):
            self.status = f"El {kind} ya está descargado (Enter lo reproduce)"
            return
        outdir = os.path.join(DOWNLOADS, "audio") if kind == "audio" else DOWNLOADS
        os.makedirs(outdir, exist_ok=True)
        os.makedirs(CACHE, exist_ok=True)
        fmt = ["-x"] if kind == "audio" else ["-f", ytdl_format(), "--merge-output-format", "mkv"]
        log = open(os.path.join(CACHE, "dl.log"), "ab")
        proc = subprocess.Popen(
            ["yt-dlp", "--no-playlist", "--windows-filenames", "--no-part", "-o",
             os.path.join(outdir, "%(title).120B [%(id)s].%(ext)s"), *fmt, "--", it["url"]],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        log.close()
        self.downloads[it["id"]] = (proc, it["title"], kind)
        self.status = clean(f"⏳ descargando {kind} en {outdir}: {it['title']}")
