# ytk: ideas and pending decisions

## Current decision (2026-11-15)

We stay with **Python + yt-dlp + mpv**. The prototype (originally a single file, standard library only; now the
`ytk/` package) already works: thumbnail grid, mixed/videos/playlists search, YouTube Mix and playback with mpv.

## Option for later: rewrite the interface in Rust

**What it would be:** a `ytk` binary in Rust that does the same as the Python version, and **still calls yt-dlp and
mpv** as separate programs. yt-dlp is not replaced.

**What it would gain**
- Faster startup and a single binary, with no dependency on Python.
- Better handling of keyboard, redrawing and images (less flicker).
- Easier to distribute or install on another machine.

**What it does not fix:** the time it takes to open a video (about 30 s on mobile data: ~7 s of yt-dlp extraction plus
the download). That depends on the network and on yt-dlp, not on the interface language.

**When it makes sense:** when daily use convinces us that `ytk` is here to stay, or when Python gets in the way
(startup, dependencies, distribution). Until then it is not needed.

**Possible pieces** (to confirm when starting)
- Terminal and keys: `crossterm`; interface: `ratatui` (or hand-drawn as now).
- Images: kitty's graphics protocol written directly (as in the Python version), or `ratatui-image`.
- Network and images: `ureq` or `reqwest` for thumbnails; `image` to convert to PNG and downscale.
- Processes: `std::process::Command` for yt-dlp (`--flat-playlist -j`) and mpv; threads or `tokio` to avoid blocking.

## What we learned and must keep in any version

- **Do not clear the screen with `ESC[2J`** (ED 2): kitty discards the images already sent. Clear line by line.
- **Images work just as well inside zellij** (0.45): tested with kitty's protocol.
- **YouTube sometimes answers without channel or views** (1 in 8 searches with yt-dlp). Retry if they are missing on
  more than half of the results.
- **External text = untrusted:** strip control and format characters from titles, channels and errors before drawing
  them; validate the `id` before using it in paths; build the URL from the id; pass `--` to mpv; download thumbnails
  only from `i.ytimg.com`, `i9.ytimg.com` and `yt3.ggpht.com`.
- **Light playback:** 720p by default, no AV1 and no 5.1 audio (`YTK_HEIGHT` changes the maximum quality).
- **A video's YouTube Mix** is the `RD` playlist + id: `watch?v=ID&list=RDID`. It does not show up in searches.
- **Reap finished mpv processes** so no zombies are left behind.

## Other ideas, no priority

- **Search without yt-dlp** (querying YouTube's internal API) to save the ~3 s per search. It is fragile because
  YouTube changes it; keep yt-dlp as plan B.
- Search history and favorites; audio-only playback.
- To test: resizing the window, `n` (more results) on long playlists and playing a playlist with audio.

## What we will NOT do

- **Our own yt-dlp clone (in Rust or any other language).** The hard part is keeping up with YouTube's changes
  (JavaScript challenges, tokens), which the yt-dlp team fixes almost every week. A clone would break every time.
- **Licensing:** yt-dlp is Unlicense (public domain) and `ytk` runs it as a separate program, so it imposes nothing.
  `ytk` itself is MIT-licensed (see `LICENSE`).
