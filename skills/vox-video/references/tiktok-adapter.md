# TikTok access adapter (tiktok-cli)

All TikTok access goes through `tiktok-cli` (read-only, session-native via ms_token — free, not a paid
API). This skill touches TikTok no other way. An Instagram adapter would replace THIS file's commands
while leaving the ingest/extract/return stages unchanged.

## Enumerate the input → video URL list
- **Collection URL** (`https://www.tiktok.com/@user/collection/Name-<id>`):
  `tiktok-cli --json collection videos "<url>"` → NDJSON **full video objects** (read `id` +
  `author.uniqueId`). Runs non-headless (the endpoint bot-blocks headless).
- **Playlist URL/id**: `tiktok-cli --json playlist videos "<id>"` → NDJSON video rows.
- **Bare URL list** (paste/file): use as-is; no enumeration call.

**Public only (v1):** `collection videos` reads PUBLIC collections via the signed `item_list` API.
Private/own-saved collections are NOT supported yet (they need an owner-logged-in session — a separate
backlog item). NEVER treat an empty enumeration as "0 videos" silently — report it.

## Per-video data (during ingest)
- Metadata: `tiktok-cli --json video info "<url>"` → one object (`desc`, author, `createTime`,
  `stats.playCount`/`diggCount`, music). Source of engagement + recency + caption signals.
- Comments: `tiktok-cli --json video comments "<url>" -n 50` → NDJSON `{cid, text, digg_count, ...}`.
- Media: `tiktok-cli video download "<url>" -o <workdir>/<id>/video.mp4`.

## Exit codes → ingest status
`0` ok · `2` usage · `3` token/blocked (treat as ms_token issue) · `4` Playwright/library missing
(a `no-capability` halt). A non-zero on ONE video is recorded in that item's `status.json`; it never
aborts the whole collection.
