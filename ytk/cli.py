"""ytk entry point: arguments, --help and --version."""

import shutil
import sys

from . import __version__
from .app import App
from .i18n import t


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(t("cli.help"))
        return
    if "--version" in sys.argv:
        print(f"ytk {__version__}")
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit(t("cli.need_tty"))
    for tool in ("yt-dlp",):
        if not shutil.which(tool):
            sys.exit(t("cli.missing_tool", tool=tool))
    App().run(" ".join(sys.argv[1:]).strip())
