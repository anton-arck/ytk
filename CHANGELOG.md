# Changelog

Versions follow [semantic versioning](https://semver.org/): new features bump the middle number, fixes the last.
Download a specific version from the Releases page, or `git clone --branch v0.3.1 <repo>`.

## Unreleased
- Sharper demo GIF: recorded in 4:4:4 and near-lossless, converted at the window's native size with 256 colors and ordered dithering (`tools/record-demo.sh` gained `-c`, `-k` and `-w 0`).

## 0.3.1
- Fix: opening the channel of an item whose author has no "videos" tab (or no "playlists" tab) now shows the other tab, with a note, instead of the raw yt-dlp error.
- `tools/record-demo.sh` records the README demo GIF automatically.

## 0.3.0
- Interface in English and Spanish: starts in the system language (`$LANG`), `space L` switches and remembers the choice, `YTK_LANG` forces one. README in English (`README.md`) with the Spanish version in `README.es.md`.
- Code comments, docstrings and `ROADMAP.md` translated to English.

## 0.2.0
- Code split from one 1200-line `ytk.py` into the `ytk/` package (one module per responsibility). Launch with `bin/ytk` or `python3 -m ytk`; behaviour is unchanged.

## 0.1.0
- Search YouTube from the terminal (mixed, videos only, lists only) with a 3x3 thumbnail grid (kitty graphics protocol).
- Play with mpv: single videos, playlists and YouTube Mixes, with resume position and history.
- Leader key (`space`) menu; next/previous song; download audio or video.
- `space i`: video info panel (channel, subscribers, views, likes, date, description).
- `space c v/l`: browse a channel's videos or playlists (`Tab` toggles).
