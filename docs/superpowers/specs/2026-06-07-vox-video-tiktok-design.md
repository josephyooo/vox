# Vox Video Tier — TikTok Collection Analyzer Design

**Status:** Approved design (brainstorming output). Successor to the v1 spec
(`2026-06-07-vox-design.md`) and the Phase 2 browser-tier spec
(`2026-06-07-vox-phase2-browser-tier-design.md`). Spans two repos: the `tiktok-cli` command
additions land in `tiktok-api-cli`; the new analysis skill lands here in the vox repo.

**One-line goal:** Add a subscription-native **video source tier** to Vox — a `vox-video` skill that
ingests a user-curated **TikTok collection** (download → transcript → frames/vision → comments),
extracts structured claims about places, **cross-checks them against the existing vox sources**
(Maps/Reddit/X/web), and renders a ranked, cited, honestly-hedged recommendation.

**Inspiration (reviewed, NOT copied):** a one-off run at `/private/tmp/nyc-food-search` where Claude
turned a saved TikTok collection into a food report. Its bones were good (multi-signal redundancy,
dedup-to-canonical-place, Maps cross-check); its discipline was not (dropped every URL, quoted videos
whose audio was empty, ignored engagement metrics, disclosed only the gaps that didn't hurt its
conclusions). This design keeps the bones and fixes the discipline.

---

## 1. Purpose & context

Vox v1 ships stateless, parallel HTTP sources (`vox-reddit`, `vox-x`, `vox-web`) plus the Phase 2
serial `vox-browser` (Maps + bot-blocked reads). All are **query-driven**: the orchestrator fans them
out on a topic, corroborates (2+ sources), ranks, renders.

Short-form video (TikTok/Instagram) carries recommendation signal **no text source has**: a creator's
spoken verdict, on-screen menus/prices, view/like/save counts as a popularity proxy, and the
human-curated act of *saving a video to a collection*. The richest entry point is therefore **not** a
query — it's a **collection the user already curated**: "here are 24 TikToks I saved; which are worth
it?" That is the use case the user has now demonstrated twice (the nyc run, and bringing it here).

This spec adds that as a first mode. Query-time discovery (TikTok as another parallel source) is real
but deferred — see §11.

## 2. Goals / non-goals

**Goals**
- A `vox-video` skill (platform-agnostic analysis) that takes a **TikTok collection / playlist / URL
  list**, ingests each video, and emits the **existing v1 digest contract**, extended with
  video-native fields (§6).
- Extend `tiktok-cli` into the **complete TikTok access backbone**: add `collection videos` and
  `playlist videos` enumeration to the existing `video info / comments / download` + `auth`.
- A **two-phase** pipeline — heavy **ingest** (cached, resumable workdir) then **analysis** — so
  follow-ups re-weight without re-downloading.
- **Require local ASR** (`mw` + parakeet-v3) behind a **pluggable transcriber interface**; signal
  priority **transcript → on-screen/visual → caption/desc**, with **comments weighed alongside**.
- Reuse the existing corroboration + ranking + output machinery unchanged: `vox-browser` (Maps),
  `vox-reddit/x/web` cross-check; render the v1 output template with a video-provenance column and the
  mandatory "sources that failed / blocked" disclosure extended to **ingest failures**.
- Rigor: TDD the new `tiktok-cli` commands (keep the project gate green); one eval golden for the
  analyzer graded by the existing harness + judge (extended with video checks).

**Non-goals (explicitly out; each a later cycle — §11)**
- **Query-time discovery** (hashtag/sound/keyword search → URL list). Feasibility recorded in §11/§12;
  not built in v1.
- **Instagram** ingest. v1 is TikTok-only but leaves a clean **adapter seam** (§3) so IG plugs in
  later via its own access tool (yt-dlp/instaloader — there is no `ig-cli`).
- Any **non-places** domain as a first target. The claim contract is general (§6), but v1 corroboration
  is **places/food-first** because that's where the Maps cross-check and the demonstrated use case live.
- Changing v1 source behavior beyond consuming the new digest fields.

## 3. Key decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Entry point | **Collection analyzer first**; query-time deferred behind a flag | Curated collections are where video is uniquely valuable; query-time TikTok search is the hard/low-value part (§11). |
| D2 | Arch split | **`tiktok-cli` = full TikTok backbone; new `vox-video` skill = analysis** | All TikTok access in one tested CLI; all reasoning in the skill. Clean seam for IG. |
| D3 | Enumeration gap | Add `tiktok-cli collection videos` (**Playwright scrape**) + `playlist videos` (**TikTokApi**) | TikTokApi has **no collection module**; `playlist.videos()` exists but is unexposed. The collection is the user's primary curation method. |
| D4 | Transcription | **Require local ASR** via a **pluggable** interface; v1 backend = `mw` parakeet-v3 | User choice. Spoken narration carries the real verdict; pluggability leaves room for whisper.cpp/faster-whisper later. |
| D5 | Signal priority | **transcript → on-screen/visual → caption/desc**; **comments alongside** (separate crowd channel) | User-specified. Drives per-claim confidence and the no-phantom-quote rule (§6). |
| D6 | Phasing | **Two-phase** (ingest → analyze) with a **cached, resumable** workdir | Download+`mw`+`ffmpeg` are heavy; Vox does live follow-up re-weighting → cache is essential. |
| D7 | Platform | **TikTok-only v1, IG-ready** adapter seam | Ships value now, zero speculative IG code, boundary stays clean. |
| D8 | Domain | **Places/food-first**, general claim contract | Maps cross-check is place-centric; the demonstrated use case is food. |
| D9 | Missing prereq | **Halt with setup instructions** (no silent fallback) | "Require local ASR" means `mw` is a hard prerequisite, like `tiktok-cli doctor`. |
| D10 | Digest/output | **Reuse v1 contracts**, extended with video fields; **render v1 template** | The orchestrator ingests/ranks/renders unchanged; only richer fields are added. |

## 4. Architecture

```
┌─ tiktok-api-cli (extend) ──────────────────┐      ┌─ vox repo: skills/vox-video (new) ──────────────┐
│  TikTok access backbone (read-only)        │      │  analysis, platform-agnostic                    │
│   NEW  collection videos <url>  (Playwright)│ ───► │   1. enumerate (via adapter) → manifest.json    │
│   NEW  playlist videos <id>     (TikTokApi) │      │   2. INGEST (per video, cached workdir):        │
│        video info / comments / download     │      │        download → mw → ffmpeg frames → vision   │
│        auth (ms_token harvest)              │      │   3. EXTRACT → video digest (claim atoms, §6)   │
└─────────────────────────────────────────────┘      │   4. CORROBORATE via existing vox sources       │
        ▲ TikTok adapter (shells to tiktok-cli)        │        (vox-browser/Maps, reddit, x, web)       │
        └──────── thin access-adapter seam ───────────┤   5. RANK + RENDER (v1 output template, §7)     │
                  (IG adapter slots in later)          └──────────────────────────────────────────────────┘
```

`vox-video` is a **source** in Vox terms, but unlike the lightweight HTTP sources it is a heavy
**two-phase pipeline**. Its access layer is a **thin adapter**: for v1 the adapter shells out to
`tiktok-cli` (NDJSON in, structured out). IG later = a second adapter; steps 2–5 are untouched.

**Browser non-contention:** `tiktok-cli`'s own **headless Playwright** (enumeration/download) is a
*separate* browser from `vox-browser`'s **real Chrome** (Maps via `claude-in-chrome`). They never
share a session, so the Phase 2 single-browser invariant is preserved.

## 5. Input, enumeration & the ingest phase

### 5.1 Input forms (adapter normalizes all three → URL list + manifest)
- **Collection URL** (`@user/collection/Name-<id>`) → `tiktok-cli collection videos <url>` (Playwright:
  navigate, scroll, harvest `/video/<id>` hrefs). **Primary** curation method; the one piece TikTokApi
  cannot do.
- **Playlist URL/id** → `tiktok-cli playlist videos <id>` (TikTokApi `playlist.videos()`).
- **Bare URL list** (paste/file) → straight through, no enumeration.

**Public vs private:** headless Playwright + `ms_token` reads *public* collections (the nyc case). A
user's *own saved/private* collection needs the logged-in session → run `tiktok-cli auth --login` once,
then the saved session reads it. An empty enumeration is **surfaced**, never silently treated as zero
videos.

### 5.2 Cached, resumable workdir
```
workdir/<collection-slug>/
  manifest.json                      # per-item ledger (below)
  <id>/
    info.json                        # tiktok-cli video info  (counts, caption, author, date, music)
    comments.json                    # tiktok-cli video comments -n N
    video.mp4                        # tiktok-cli video download  (removed after extract if --no-keep-media)
    transcript.txt                   # mw parakeet-v3            (videos only)
    frames/f{1..5}_{12,30,50,70,88}.jpg   # ffmpeg %-sampling
    onscreen.md                      # Claude vision over frames (prices/addresses/on-screen text)
    status.json                      # {download,transcribe,frames,onscreen,comments}: ok|empty|skipped|error
```
Two branches: **video** → full pipeline; **photo carousel** → vision over slides, no transcript.

**Manifest item:** `{idx, platform:"tiktok", type:"video"|"photo", author, id, url, ingest_status}` —
replacing the nyc run's useless single-line `.err` files with **structured per-stage status**, so
"audio empty" is a recorded fact, not invisible.

### 5.3 Degradation discipline (the central nyc fix)
Every signal is independently optional, but a failure is **recorded, never papered over**. If
`status.transcribe == empty` (music-only/silent audio), the video is marked **on-screen/caption-only**
and **no spoken-claim quote may be attributed to it** — the single rule that stops the "quoting videos
we never heard" failure.

### 5.4 Prerequisites
A startup capability probe (mirroring `tiktok-cli doctor`) checks `mw`, `ffmpeg`, `tiktok-cli`, and a
resolvable `ms_token`. Missing `mw` → **halt with setup instructions** (hard prerequisite per D4/D9).

## 6. The `vox-video` digest (structured claim atoms + video-native fields)

A strict **superset** of the v1 digest contract, so the orchestrator ingests it unchanged. Per
candidate entity:

```jsonc
{
  "entity": { "name": "Shu Jiao Fu Zhou",
              "resolution_confidence": "high|med|low",   // garbled ASR names → low → hedged, not asserted
              "maps_place_id": null },                    // filled at corroboration
  "claims": [                                             // structured atoms, NOT prose blobs
    { "kind": "price|dish|verdict|logistics",
      "text": "$12 KFC platter, pick-2 flavors",
      "sentiment": "pos|neg|mixed",
      "signal_source": "transcript|onscreen|caption|comment",   // provenance is explicit
      "citation": { "video_url": "https://tiktok.com/@…/video/<id>",
                    "t_seconds": 47,      // spoken → mw timestamp; onscreen → frame time; else null
                    "frame": "f3_50pct.jpg" } }
  ],
  "engagement": { "views": 493600, "likes": 30300, "saves": 269, "comments": 1204 },  // popularity proxy
  "creator":   { "handle": "casserolebites", "followers": 88000,
                 "coi": "organic|sponsored|comped|affiliate" },   // first-class COI flag
  "corroboration": { "mention_count": 3, "distinct_creators": 3 },// co-occurrence across videos
  "coverage":  { "transcript": "ok|empty|skipped", "onscreen": "ok", "comments": "ok|none_fetched" }
}
```

**Rules (each fixes a specific nyc sin):**
1. **Signal-priority confidence** — transcript (spoken) > on-screen > caption; **comments are a
   separate crowd channel**, never merged into the creator's claim. A claim's confidence is **capped by
   its `signal_source`**.
2. **No phantom quotes** — a `signal_source:"transcript"` claim **cannot exist** unless
   `coverage.transcript == ok`. Empty-audio videos still contribute on-screen/caption claims, plainly
   labeled.
3. **Every claim carries a URL** (+ timestamp/frame when spoken/on-screen) — traceability to the
   *moment*, not just the place.
4. **Engagement & recency are fields** — views/likes/saves become a ranking input + tie-breaker;
   `upload_date` (from `info.json`) flags stale claims (closures, price changes).
5. **`coverage` distinguishes "no data" from "neutral"** — `comments:"none_fetched"` is recorded so the
   orchestrator never reads silence as consensus.

## 7. Corroboration, ranking & output (reuse)

**Corroborate (existing machinery):** the digest drops into the orchestrator's candidate × source
matrix. `vox-browser` resolves each entity → `maps_place_id` + rating × review-volume; `vox-reddit/x/web`
cross-check sentiment, closures, prices. Promote on 2+ channels; **intra-video corroboration**
(`mention_count` across distinct creators) is its own strength signal. Wave-2 verifies finalists
(verified price, current rating, open/closed) exactly as today.

**Rank:** hard constraints first → quality = **Maps rating × review-VOLUME**. Video adds
tie-breakers/boosts: **engagement** (popularity proxy), **cross-video corroboration** (confidence
boost), **COI discount** (comped/sponsored down-weighted, not excluded), **recency decay** on stale
claims. One honest pick, not a forced winner.

**Output** = the v1 `output-template`, plus a **video-provenance** column per pick: video URL(s) **+
timestamp**, creator (+ COI), engagement, and the **claim-vs-reality** line — the nyc run's best instinct,
now cited: *"casserolebites @0:47 said $12 platter → Maps/Reddit confirm; 4.5 × 3,024."* The mandatory
**"Sources that failed / blocked"** line is extended to disclose **ingest failures**: empty-transcript
videos (by id), unresolved entities, single-video picks, rate-limited comments, un-enumerated collection
items. Silence is never read as consensus.

## 8. Execution model

Two-phase:
- **Ingest** — a background workflow, per-video fan-out (download → `mw` → `ffmpeg` → vision),
  concurrency-capped, **resumable** via `manifest.json` / `status.json` (completed items skipped on
  re-run).
- **Analysis** — orchestrated: extract → corroborate via existing sources → rank → render.

The cache means follow-ups ("re-rank just the under-$20 ones") re-weight the existing candidate set with
**zero re-download**, consistent with the orchestrator's "follow-ups = live re-weighting" rule.

## 9. Eval / rigor

- **`tiktok-api-cli`** — TDD the two new commands:
  - `playlist videos <id>` — unit tests with a mocked `TikTokApi.playlist().videos()` iterator;
    integration test following the existing `tests/integration/test_video.py` / `test_user.py` patterns
    (NDJSON shape, `-n/--count`, exit codes). Reuse `VIDEO_COLUMNS`.
  - `collection videos <url>` — unit tests with a **mocked Playwright** page (following `auth.py`'s
    direct-Playwright precedent and `tests/unit/test_auth.py`); assert URL harvest + scroll/termination,
    and graceful empty/private handling.
  - Keep the project gate green: `ruff`, `pytest`, the skills validator (per the project-gate memory).
- **vox repo** — one eval golden for the analyzer, `eval/goldens/video-collection.md` (a small fixture
  collection → expected digest shape + a ranked, cited deliverable). `structural_checks → []`. Extend
  the LLM judge rubric with **video checks**: every claim has a URL (+ timestamp where spoken/on-screen);
  **no spoken claim without a transcript**; engagement + COI surfaced; ingest failures disclosed in the
  failed-sources block. Run interactively (heavy ingest can't run headless); capture to `eval/runs/`,
  grade with the same harness + judge — the analog of the Phase 2 manual browser golden.

## 10. File structure (delta)

**`tiktok-api-cli` (new/edited)**
- New: `tiktok_cli/commands/collection.py` (`collection videos`), `playlist videos` (extend
  `commands/user.py` or a new `commands/playlist.py`).
- Edited: `tiktok_cli/app.py` (register), `columns.py` if a new column set is needed; `README.md`.
- Tests: `tests/integration/test_collection.py`, `tests/unit/test_collection_scrape.py`,
  `tests/integration/test_playlist.py`.

**vox repo (new)**
- `skills/vox-video/SKILL.md` — the two-phase pipeline playbook (prereq probe → enumerate → ingest →
  extract → hand digest to orchestrator).
- `skills/vox-video/references/ingest-playbook.md` — download/`mw`/`ffmpeg`/vision mechanics, workdir
  layout, %-frame cadence, photo-carousel branch, degradation discipline.
- `skills/vox-video/references/digest-contract.md` — the §6 superset contract + the five rules.
- `skills/vox-video/references/tiktok-adapter.md` — the access seam (commands, NDJSON shapes, public
  vs private, the IG-adapter boundary).
- `eval/goldens/video-collection.md`.

**vox repo (edited)**
- `skills/vox/SKILL.md` — route a collection/playlist/URL-list input to `vox-video`; consume its digest
  in corroboration/ranking; render the video-provenance column + extended failed-sources line.
- `eval/run-eval.md` — the manual video-collection rigor step.

`install.sh` globs `skills/*` (auto-symlinks `vox-video`); `tools/validate_skills.py`, `eval/harness.py`
need no change.

## 11. Scope, phases, provenance

- **Build order:** `tiktok-cli` enumeration commands (TDD) → `vox-video` ingest pipeline + cached workdir
  → digest contract + extraction → orchestrator integration (routing + corroboration consumption +
  output column) → eval golden + run-eval doc.
- **Provenance:** the multi-signal-redundancy + dedup-to-canonical-place + Maps-cross-check bones are
  mined from the nyc run (`/private/tmp/nyc-food-search`); the discipline fixes (per-claim URLs, no
  phantom quotes, engagement fields, complete failure disclosure) are this design's corrections to that
  run's documented sins.
- **Deferred (each its own brainstorming→spec→plan cycle):**
  - **Query-time discovery mode** — a discovery front-end (hashtag/sound reliable; raw keyword video
    search best-effort) producing a URL list that feeds the same ingest→analyze backbone, behind a flag.
  - **Instagram adapter** — yt-dlp/instaloader access behind the same `vox-video` skill (steps 2–5 reused).

## 12. Appendix — TikTok search feasibility (for the deferred query-time phase)

Read from the installed `TikTokApi` 7.3.3 (`api/search.py`, `api/hashtag.py`, `api/sound.py`):
- **Reliable discovery** (stable `.videos()` iterators): `hashtag videos`, `sound videos`, `user videos`,
  `trending videos`, `video related`. **Topic → hashtag** is the dependable "search and collect URLs"
  path.
- **User keyword search** works: `api.search.users()` (needs an `ms_token` that "has done a search
  before").
- **Video keyword search half-exists:** the underlying `Search.search_type(term, "item")` path is
  implemented (hits `https://www.tiktok.com/api/search/item/full/`, yields videos from `item_list`), but
  there is **no public `search.videos()` wrapper** and the library's own docstring flags it — *"Currently
  only supports searching for users, other endpoints require auth."* In practice it needs a high-trust
  logged-in token, is heavily bot-protected, and frequently returns invalid responses → **best-effort,
  not rankable**. The query-time phase should lead with hashtag/sound discovery and treat keyword video
  search as an experimental extra with honest degradation.
```
