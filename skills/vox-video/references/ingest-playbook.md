# Ingest playbook (Phase 1 — per video → cached workdir)

Heavy and resumable: re-runs skip any item whose `status.json` is already complete. This is the
subscription-native pipeline — an ingest backend (`vidread`, or legacy `tiktok-cli` + `mw`), `ffmpeg`,
and Claude vision. No paid API.

## Workdir layout
```
workdir/<collection-slug>/
  manifest.json                 # {idx, platform:"tiktok|youtube", type, author, id, url, ingest_status}
  <id>/
    info.json                   # tiktok-cli video info  (caption, engagement, upload date, music)
    comments.json               # tiktok-cli video comments -n 50   (best-effort)
    video.mp4                   # tiktok-cli video download   (removed after extract unless --keep-media)
    transcript.txt              # mw parakeet-v3            (videos only)
    frames/f{1..5}_{12,30,50,70,88}.jpg   # ffmpeg %-sampling
    onscreen.md                 # Claude vision over frames (prices/addresses/on-screen text)
    agy.md                      # agy cross-check (video-only, supplementary) — see agy-crosscheck.md
    status.json                 # {download,transcribe,frames,onscreen,agy,comments}: ok|empty|skipped|error|unavailable|disabled
```
`vidread` writes `<workdir>/<extractor>-<id>/` instead, with `meta.json` in place of `info.json`, no
`manifest.json`/`onscreen.md` (steps 1 and 7 are yours), and stage statuses nested under
`status.json`'s `status` key next to `transcript_source`.

## Per-video steps
1. **Enumerate** → `manifest.json`. A bare URL list is used as-is. A YouTube playlist or TikTok
   collection: `yt-dlp --flat-playlist --print url "<url>"` (for YouTube, add `--proxy socks5://127.0.0.1:1055`
   if yt-dlp hits a bot wall), or `tiktok-cli` per [tiktok-adapter](tiktok-adapter.md). If nothing can
   enumerate it, return Status `no-capability` asking the user to paste the video URLs. Never report
   "0 videos".
2. **Branch on type**: `video` → full pipeline; `photo` (carousel) → Claude vision over slides, NO transcript.
3. **Metadata** — `tiktok-cli --json video info "<url>"` → `info.json` (caption `desc`, engagement, upload date).
4. **Download** — `tiktok-cli video download "<url>" -o <id>/video.mp4`.
5. **Transcribe** — `mw` parakeet-v3 → `transcript.txt`. Music-only/silent audio → status `empty`.
6. **Frames** — `ffmpeg` at 12/30/50/70/88% of duration → `frames/`. Percentage sampling is
   duration-robust (intro/mid/outro in 5 frames, cheap).
7. **On-screen text** — Claude vision over the 5 frames → `onscreen.md`. Most TikTok food value
   (prices, addresses, dish names) is ON the slide, not in the audio.
8. **agy cross-check** (video-only, supplementary; SKIP for photo carousels → `agy: skipped`) — run
   `agy` ONCE on `video.mp4` **before it is removed** → `agy.md`, per
   [agy-crosscheck](agy-crosscheck.md). Best-effort with three mandatory guards: a hard ~150s external
   timeout (agy can hang past its own timeout), success judged by OUTPUT not exit code (it returns exit
   0 with `Error: timed out` as the body), and retry-once-on-flake. On give-up record `agy: unavailable`
   and continue — **never a halt**. If `agy` was absent at bootstrap, record `agy: disabled` and skip.
9. **Comments** — `tiktok-cli --json video comments "<url>" -n 50` → `comments.json`; best-effort.
   On rate-limit record `comments: unavailable` (NOT neutral).
10. Write the item's `status.json`.

**vidread backend:** steps 3–6 and YouTube comments are the single `vidread` call (see SKILL.md);
steps 1, 2, 7, 8 (on the kept `video.*`, then delete it) and TikTok comments via `tiktok-cli` (when
its soft probe passed) stay yours; add `onscreen`/`agy` to its status.

## Transcriber interface (pluggable)
Backends: legacy `mw` (parakeet-v3); `vidread` uses caption tracks, else Whisper. The playbook calls a
single transcribe step; swapping to whisper.cpp/faster-whisper later changes only this step, not the
pipeline.

## Degradation discipline (the central fix)
Every signal is optional, but a failure is RECORDED, never hidden. If `transcribe: empty`, mark the
video **on-screen/caption-only** and attribute **no spoken-claim quote** to it — Rule 2 of the
[digest-extension](digest-extension.md).
