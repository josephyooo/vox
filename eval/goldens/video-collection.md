## Query
Analyze my saved TikTok collection "<public-collection-url>" and tell me which spots are actually worth it

## Family
places / food (video-sourced)

## Expectations
- Routes to the video tier (`vox-video`): ingests each video (transcript + on-screen text + caption +
  comments) and surfaces candidate places; corroborates with vox-maps (place data, per finalist) + Reddit/X/web.
- Ranked table with a video-provenance column: each pick cites the **video URL + timestamp** (spoken)
  or frame (on-screen), creator + COI, and engagement (views/likes/saves).
- Signal-priority + no-phantom-quote: no spoken-claim quote for any video whose transcript was empty;
  such videos are marked on-screen/caption-only.
- Quality ranked by Maps rating × review-VOLUME; comped/sponsored picks down-weighted, not dropped.
- "Sources that failed / blocked" lists ingest failures: empty-transcript videos, unresolved entities,
  rate-limited comments, un-enumerated items. `unavailable` ≠ neutral.
- If vox-video returns `no-capability` (ffmpeg missing, or no ingest backend: neither `vidread` nor
  `mw`+`tiktok-cli`), or the collection cannot be enumerated: HALTS-AND-REPORTS naming the missing
  prereq (or asking for explicit video URLs); never a partial answer and never "0 videos"; no
  `--web-fallback`.
- TikTok run without `tiktok-cli`: comments are reported `unavailable` as a coverage note (creator
  signal only), never as empty and never a halt.
- agy entity cross-check (supplementary, soft-gated): a proper-noun correction (a name the transcript garbled) is
  shown transparently as "via agy cross-check"; `agy` is NEVER the source of a spoken-claim quote
  (Rule 2 still binds); an agy-only on-screen entity is added at lower confidence with a "no frame
  anchor" label.
- If `agy` is unavailable for a video (flake/timeout) or absent (disabled), it is noted in "sources
  that failed / blocked" — NOT halted; the transcript/`ffmpeg`/vision stack remains
  source-of-record.
