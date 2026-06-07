# Ingest playbook (Phase 1 — per video → cached workdir)

Heavy and resumable: re-runs skip any item whose `status.json` is already complete. This is the
subscription-native pipeline — `tiktok-cli` (session-native), local `mw`/`ffmpeg`, and Claude vision.
No paid API.

## Workdir layout
```
workdir/<collection-slug>/
  manifest.json                 # {idx, platform:"tiktok", type, author, id, url, ingest_status}
  <id>/
    info.json                   # tiktok-cli video info  (caption, engagement, upload date, music)
    comments.json               # tiktok-cli video comments -n 50   (best-effort)
    video.mp4                   # tiktok-cli video download   (removed after extract unless --keep-media)
    transcript.txt              # mw parakeet-v3            (videos only)
    frames/f{1..5}_{12,30,50,70,88}.jpg   # ffmpeg %-sampling
    onscreen.md                 # Claude vision over frames (prices/addresses/on-screen text)
    status.json                 # {download,transcribe,frames,onscreen,comments}: ok|empty|skipped|error
```

## Per-video steps
1. **Enumerate** the collection/playlist/URL-list via [tiktok-adapter](tiktok-adapter.md) → `manifest.json`.
2. **Branch on type**: `video` → full pipeline; `photo` (carousel) → Claude vision over slides, NO transcript.
3. **Metadata** — `tiktok-cli --json video info "<url>"` → `info.json` (caption `desc`, engagement, upload date).
4. **Download** — `tiktok-cli video download "<url>" -o <id>/video.mp4`.
5. **Transcribe** — `mw` parakeet-v3 → `transcript.txt`. Music-only/silent audio → status `empty`.
6. **Frames** — `ffmpeg` at 12/30/50/70/88% of duration → `frames/`. Percentage sampling is
   duration-robust (intro/mid/outro in 5 frames, cheap).
7. **On-screen text** — Claude vision over the 5 frames → `onscreen.md`. Most TikTok food value
   (prices, addresses, dish names) is ON the slide, not in the audio.
8. **Comments** — `tiktok-cli --json video comments "<url>" -n 50` → `comments.json`; best-effort.
   On rate-limit record `comments: none_fetched` (NOT neutral).
9. Write the item's `status.json`.

## Transcriber interface (pluggable)
v1 backend is `mw` (parakeet-v3). The playbook calls a single transcribe step; swapping to
whisper.cpp/faster-whisper later changes only this step, not the pipeline.

## Degradation discipline (the central fix)
Every signal is optional, but a failure is RECORDED, never hidden. If `transcribe: empty`, mark the
video **on-screen/caption-only** and attribute **no spoken-claim quote** to it — Rule 2 of the
[digest-extension](digest-extension.md).
