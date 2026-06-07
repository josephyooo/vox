## Query
Analyze my saved TikTok collection "<public-collection-url>" and tell me which spots are actually worth it

## Family
places / food (video-sourced)

## Expectations
- Routes to the video tier (`vox-video`): ingests each video (transcript + on-screen text + caption +
  comments) and surfaces candidate places; corroborates with Maps (browser) + Reddit/X/web.
- Ranked table with a video-provenance column: each pick cites the **video URL + timestamp** (spoken)
  or frame (on-screen), creator + COI, and engagement (views/likes/saves).
- Signal-priority + no-phantom-quote: no spoken-claim quote for any video whose transcript was empty;
  such videos are marked on-screen/caption-only.
- Quality ranked by Maps rating × review-VOLUME; comped/sponsored picks down-weighted, not dropped.
- "Sources that failed / blocked" lists ingest failures: empty-transcript videos, unresolved entities,
  rate-limited comments, un-enumerated items. `none_fetched` ≠ neutral.
- If `mw`/`ffmpeg`/`tiktok-cli` is missing: HALTS by default naming the missing prereq; never a
  partial answer.
