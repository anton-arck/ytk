# Changelog

Versions follow [semantic versioning](https://semver.org/): new features bump the middle number, fixes the last.
Download a specific version from the Releases page, or `git clone --branch v0.2.0 <repo>`.

## 0.2.0
- Code split from one 1200-line `ytk.py` into the `ytk/` package (one module per responsibility). Launch with `bin/ytk` or `python3 -m ytk`; behaviour is unchanged.

## 0.1.0
- Search YouTube from the terminal (mixed, videos only, lists only) with a 3x3 thumbnail grid (kitty graphics protocol).
- Play with mpv: single videos, playlists and YouTube Mixes, with resume position and history.
- Leader key (`space`) menu; next/previous song; download audio or video.
- `space i`: video info panel (channel, subscribers, views, likes, date, description).
- `space c v/l`: browse a channel's videos or playlists (`Tab` toggles).
