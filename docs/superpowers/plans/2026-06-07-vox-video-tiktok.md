# Vox Video Tier — TikTok Collection Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subscription-native TikTok collection analyzer to Vox — extend `tiktok-cli` into the full TikTok access backbone, then build a `vox-video` skill that ingests a curated collection (download → transcript → frames/vision → comments), extracts cited place claims, cross-checks them via the existing vox sources, and renders a ranked, honestly-hedged recommendation.

**Architecture:** Two repos. **`tiktok-api-cli`** gains two read-only enumeration commands (`playlist videos` via TikTokApi, `collection videos` via direct Playwright scrape, mirroring `auth.py`). **The vox repo** gains a `vox-video` source skill (markdown playbooks) that drives `tiktok-cli` + `mw` + `ffmpeg` + Claude vision in a two-phase cached pipeline and returns the existing 7-section digest contract, extended with video-native fields. The orchestrator routes collection/playlist/URL-list inputs to `vox-video` as the candidate-discovery driver; the existing Maps/Reddit/X/web sources corroborate.

**Tech Stack:** Python 3.9+ / Typer / `TikTokApi` 7.3.3 / Playwright (tiktok-cli); pytest + ruff + mypy gate. Markdown skills + `tools/validate_skills.py` + `eval/harness.py` (vox). `mw` (MacWhisper parakeet-v3) + `ffmpeg` + Claude vision at runtime.

---

## File structure

**Repo A — `/Users/joseph/projects/tiktok-api-cli`**
- Create `tiktok_cli/commands/playlist.py` — `playlist videos <id>` (TikTokApi `playlist.videos()`).
- Create `tiktok_cli/collection.py` — collection-page scrape lib: pure `_extract_video_urls(html)` + Playwright `scrape_collection(url, …)`, isolated behind `_async_playwright()` (mirrors `auth.py`).
- Create `tiktok_cli/commands/collection.py` — `collection videos <url>` command; renders scraped rows via `Renderer`.
- Modify `tiktok_cli/app.py` — register the two new sub-apps.
- Modify `tests/conftest.py` — add a `playlist(...)` accessor to `FakeTikTokApi`.
- Create `tests/integration/test_playlist.py`, `tests/unit/test_collection.py`, `tests/integration/test_collection_cmd.py`.
- Modify `README.md` — document the two commands.

**Repo B — `/Users/joseph/projects/vox`**
- Create `skills/vox-video/references/ingest-playbook.md` — Phase-1 ingest mechanics + workdir + degradation.
- Create `skills/vox-video/references/tiktok-adapter.md` — the `tiktok-cli` access seam (the IG-swappable boundary).
- Create `skills/vox-video/references/digest-extension.md` — how video fields map onto the 7-section digest + the five honesty rules.
- Create `skills/vox-video/SKILL.md` — the two-phase playbook; links the three references + the orchestrator's digest contract.
- Modify `skills/vox/SKILL.md` — routing (step 2), Wave-1 dispatch (step 3), render note (step 7), and a new "Video tier" gate section.
- Create `eval/goldens/video-collection.md` — the manual capability-gated golden.
- Modify `eval/judge-rubric.md` — add a `PROVENANCE` criterion.
- Modify `eval/run-eval.md` — add a "Video-tier rigor (manual)" section.

> **Naming note:** the spec (§10) called the digest reference `digest-contract.md`; this plan names it `digest-extension.md` to avoid confusion with the orchestrator's `skills/vox/references/digest-contract.md` (which it extends). Functionally identical, clearer on disk.

---

# PART A — tiktok-api-cli backbone (Python, TDD)

All commands below run from `/Users/joseph/projects/tiktok-api-cli` with the venv at `.venv`. The full gate (run at the end of each task) is:

```
.venv/bin/python -m pytest --cov=tiktok_cli --cov-report=term-missing -q
.venv/bin/python -m ruff check tiktok_cli tests
.venv/bin/python -m ruff format --check tiktok_cli tests
.venv/bin/python -m mypy tiktok_cli
```

### Task 1: `playlist videos` command

**Files:**
- Modify: `tests/conftest.py` (add `FakeTikTokApi.playlist`)
- Create: `tiktok_cli/commands/playlist.py`
- Modify: `tiktok_cli/app.py` (register sub-app)
- Test: `tests/integration/test_playlist.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_playlist.py`:

```python
import json

from typer.testing import CliRunner

from tests.conftest import FakeModule
from tiktok_cli.app import app

runner = CliRunner()


def test_playlist_videos(patch_session):
    patch_session.modules[("playlist", "7426714779919797038")] = FakeModule(
        video_items=[{"id": "v1", "author": {"uniqueId": "foodie"}}]
    )
    res = runner.invoke(app, ["--json", "playlist", "videos", "7426714779919797038", "-n", "1"])
    assert res.exit_code == 0 and json.loads(res.stdout.strip())["id"] == "v1"


def test_playlist_videos_empty(patch_session):
    patch_session.modules[("playlist", "999")] = FakeModule(video_items=[])
    res = runner.invoke(app, ["--json", "playlist", "videos", "999"])
    assert res.exit_code == 0 and res.stdout.strip() == ""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_playlist.py -q`
Expected: FAIL — `FakeTikTokApi` has no `playlist` attribute / no `playlist` command registered.

- [ ] **Step 3: Add the `playlist` accessor to the fake API**

In `tests/conftest.py`, inside `class FakeTikTokApi`, add this method directly after the existing `sound` accessor (around line 87):

```python
    def playlist(self, id=None):
        return self.modules.get(("playlist", id), FakeModule())
```

- [ ] **Step 4: Implement the command**

Create `tiktok_cli/commands/playlist.py` (mirrors `commands/sound.py`'s `videos`):

```python
import typer

from ..columns import VIDEO_COLUMNS
from ..runner import run_iter

app = typer.Typer(help="Playlist (mix) videos.", no_args_is_help=True)


@app.command()
def videos(
    ctx: typer.Context,
    playlist_id: str = typer.Argument(..., metavar="ID"),
    count: int = typer.Option(30, "--count", "-n"),
):
    """List videos in a playlist (mix)."""
    run_iter(lambda api: api.playlist(id=playlist_id).videos(count=count), VIDEO_COLUMNS, ctx.obj)
```

- [ ] **Step 5: Register the sub-app**

In `tiktok_cli/app.py`, update the commands import (line 8) to include `playlist`:

```python
from .commands import auth, doctor, hashtag, playlist, search, sound, trending, user, video
```

and add this registration after the `sound` line (around line 21):

```python
app.add_typer(playlist.app, name="playlist")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/integration/test_playlist.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Document the command**

In `README.md`, add this row to the Commands table after the `user playlists` row (line 94):

```
| `playlist videos` | List videos in a playlist/mix | `tiktok-cli playlist videos 7426714779919797038 -n 20` |
```

- [ ] **Step 8: Run the full gate**

Run the four gate commands (top of Part A). Expected: all pass; ruff/mypy clean. If `ruff format --check` flags the new files, run `.venv/bin/python -m ruff format tiktok_cli tests` and re-check.

- [ ] **Step 9: Commit**

```bash
git add tiktok_cli/commands/playlist.py tiktok_cli/app.py tests/conftest.py tests/integration/test_playlist.py README.md
git commit -m "feat: add 'playlist videos' command (TikTokApi playlist enumeration)"
```

---

### Task 2: collection URL extraction (pure helper)

**Files:**
- Create: `tiktok_cli/collection.py`
- Test: `tests/unit/test_collection.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_collection.py`:

```python
from tiktok_cli import collection


def test_extract_video_urls_dedupes_and_orders():
    html = (
        '<a href="https://www.tiktok.com/@a/video/111">x</a>'
        '<a href="https://www.tiktok.com/@b/video/222">y</a>'
        '<a href="https://www.tiktok.com/@a/video/111">dup</a>'
    )
    rows = collection._extract_video_urls(html)
    assert [r["id"] for r in rows] == ["111", "222"]
    assert rows[0] == {
        "id": "111",
        "author": "a",
        "url": "https://www.tiktok.com/@a/video/111",
    }


def test_extract_video_urls_empty():
    assert collection._extract_video_urls("<p>no videos here</p>") == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_collection.py -q`
Expected: FAIL — `ModuleNotFoundError: tiktok_cli.collection`.

- [ ] **Step 3: Implement the pure helper**

Create `tiktok_cli/collection.py`:

```python
"""Collection enumeration: scrape a public TikTok collection page for its video URLs.

TikTokApi 7.3.3 has no collection module, so we drive Playwright directly (the same
pattern auth.py uses for ms_token harvest) to load the collection page, scroll it,
and harvest the ``/@user/video/<id>`` links. The HTML->links step is a pure function
so it stays testable without launching a browser.
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable

VIDEO_HREF_RE = re.compile(r"https://www\.tiktok\.com/@([\w.-]+)/video/(\d+)")


def _extract_video_urls(html: str) -> list[dict]:
    """Return ordered, de-duplicated video rows parsed from collection-page HTML."""
    seen: set[str] = set()
    rows: list[dict] = []
    for match in VIDEO_HREF_RE.finditer(html):
        author, vid = match.group(1), match.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        rows.append({"id": vid, "author": author, "url": match.group(0)})
    return rows
```

(The `asyncio` and `Callable` imports are used by Task 3; adding them now keeps the file's import block stable.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_collection.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add tiktok_cli/collection.py tests/unit/test_collection.py
git commit -m "feat: add pure collection-URL extractor helper"
```

---

### Task 3: collection scrape orchestration (mocked Playwright)

**Files:**
- Modify: `tiktok_cli/collection.py` (add `_async_playwright` + `scrape_collection`)
- Test: `tests/unit/test_collection.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_collection.py`:

```python
HTML = (
    '<a href="https://www.tiktok.com/@a/video/111"></a>'
    '<a href="https://www.tiktok.com/@b/video/222"></a>'
)


class _FakeMouse:
    async def wheel(self, dx, dy):
        return None


class _FakePage:
    def __init__(self, html):
        self._html = html
        self.mouse = _FakeMouse()

    async def goto(self, url, **kwargs):
        self.url = url

    async def content(self):
        return self._html


class _FakeContext:
    def __init__(self, html):
        self._html = html

    async def new_page(self):
        return _FakePage(self._html)


class _FakeBrowser:
    def __init__(self, html):
        self._html = html
        self.closed = False

    async def new_context(self):
        return _FakeContext(self._html)

    async def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, html):
        self._html = html
        self.browser = None

    async def launch(self, headless=True):
        self.browser = _FakeBrowser(self._html)
        return self.browser


class _FakePlaywright:
    def __init__(self, html):
        self.chromium = _FakeChromium(html)


class _FakePwCM:
    def __init__(self, html):
        self.pw = _FakePlaywright(html)

    async def __aenter__(self):
        return self.pw

    async def __aexit__(self, *exc):
        return False


async def test_scrape_collection_harvests_and_closes(monkeypatch):
    cm = _FakePwCM(HTML)
    monkeypatch.setattr(collection, "_async_playwright", lambda: cm)
    rows = await collection.scrape_collection(
        "https://www.tiktok.com/@u/collection/NYC-1", scroll_pause_s=0, max_scrolls=3
    )
    assert [r["id"] for r in rows] == ["111", "222"]
    assert cm.pw.chromium.browser.closed is True


async def test_scrape_collection_empty(monkeypatch):
    cm = _FakePwCM("<p>nothing</p>")
    monkeypatch.setattr(collection, "_async_playwright", lambda: cm)
    rows = await collection.scrape_collection("u", scroll_pause_s=0, max_scrolls=2)
    assert rows == []
    assert cm.pw.chromium.browser.closed is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_collection.py -q`
Expected: FAIL — `collection` has no `_async_playwright` / `scrape_collection`.

- [ ] **Step 3: Implement the orchestration**

Append to `tiktok_cli/collection.py`:

```python
def _async_playwright():
    from playwright.async_api import async_playwright  # lazy: heavy import

    return async_playwright()


async def scrape_collection(
    url: str,
    *,
    headless: bool = True,
    max_scrolls: int = 20,
    scroll_pause_s: float = 0.8,
    timeout_s: float = 30.0,
    on_ready: Callable[[], None] | None = None,
) -> list[dict]:
    """Load a collection page, scroll to load lazy items, and harvest its video URLs.

    ``on_ready`` (for an interactive/--login analogue) fires once the page has loaded.
    Scrolling stops when a pass surfaces no new videos or ``max_scrolls`` is reached.
    """
    pw = _async_playwright()
    async with pw as p:
        browser = await p.chromium.launch(headless=headless)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
            if on_ready is not None:
                on_ready()
            seen = 0
            for _ in range(max_scrolls):
                count = len(_extract_video_urls(await page.content()))
                if count == seen and seen > 0:
                    break
                seen = count
                await page.mouse.wheel(0, 20000)
                await asyncio.sleep(scroll_pause_s)
            return _extract_video_urls(await page.content())
        finally:
            await browser.close()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_collection.py -q`
Expected: PASS (4 passed total in this file).

- [ ] **Step 5: Run the full gate**

Run the four gate commands. Expected: all pass. Run `.venv/bin/python -m ruff format tiktok_cli tests` first if `--check` flags the new file.

- [ ] **Step 6: Commit**

```bash
git add tiktok_cli/collection.py tests/unit/test_collection.py
git commit -m "feat: add Playwright collection-page scraper (mock-tested)"
```

---

### Task 4: `collection videos` command

**Files:**
- Create: `tiktok_cli/commands/collection.py`
- Modify: `tiktok_cli/app.py` (register sub-app)
- Test: `tests/integration/test_collection_cmd.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_collection_cmd.py`:

```python
import json

from typer.testing import CliRunner

from tiktok_cli import collection
from tiktok_cli.app import app

runner = CliRunner()
URL = "https://www.tiktok.com/@u/collection/NYC-1"


def test_collection_videos(monkeypatch):
    async def _fake_scrape(url, **kwargs):
        return [{"id": "111", "author": "a", "url": "https://www.tiktok.com/@a/video/111"}]

    monkeypatch.setattr(collection, "scrape_collection", _fake_scrape)
    res = runner.invoke(app, ["--json", "collection", "videos", URL])
    assert res.exit_code == 0 and json.loads(res.stdout.strip())["id"] == "111"


def test_collection_videos_runtime_error_exits_1(monkeypatch):
    async def _boom(url, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(collection, "scrape_collection", _boom)
    res = runner.invoke(app, ["collection", "videos", URL])
    assert res.exit_code == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_collection_cmd.py -q`
Expected: FAIL — no `collection` command registered.

- [ ] **Step 3: Implement the command**

Create `tiktok_cli/commands/collection.py`:

```python
"""`tiktok-cli collection videos <url>` — enumerate a public collection's videos.

Unlike the TikTokApi-backed commands this drives Playwright directly (no ms_token
session), so it does not use run_iter; it renders the scraped rows through the
standard Renderer for consistent NDJSON/table output.
"""

from __future__ import annotations

import asyncio

import typer

from .. import collection as collection_mod
from ..errors import classify_exception
from ..output import Column, Renderer

app = typer.Typer(help="Collection enumeration.", no_args_is_help=True)

COLLECTION_COLUMNS = [
    Column("ID", lambda d: d.get("id", "")),
    Column("Author", lambda d: d.get("author", "")),
    Column("URL", lambda d: d.get("url", "")),
]


@app.command()
def videos(
    ctx: typer.Context,
    url: str = typer.Argument(..., metavar="URL"),
    scrolls: int = typer.Option(20, "--scrolls", help="max scroll passes to load lazy items"),
):
    """List the video URLs saved in a public collection."""
    try:
        rows = asyncio.run(
            collection_mod.scrape_collection(url, headless=ctx.obj.headless, max_scrolls=scrolls)
        )
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - map to clean exit codes
        err = classify_exception(exc)
        typer.echo(err.message, err=True)
        raise typer.Exit(err.exit_code) from exc
    renderer = Renderer(COLLECTION_COLUMNS, ctx.obj)
    for row in rows:
        renderer.emit(row)
    renderer.close()
```

- [ ] **Step 4: Register the sub-app**

In `tiktok_cli/app.py`, update the commands import (line 8, which now already includes `playlist` from Task 1) to also include `collection`:

```python
from .commands import auth, collection, doctor, hashtag, playlist, search, sound, trending, user, video
```

and add this registration after the `video` line (around line 18):

```python
app.add_typer(collection.app, name="collection")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/integration/test_collection_cmd.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Document the command**

In `README.md`, add this row to the Commands table after the `playlist videos` row (added in Task 1):

```
| `collection videos` | List videos saved in a public collection | `tiktok-cli collection videos "https://www.tiktok.com/@u/collection/NYC-123"` |
```

Also add a short prose note under the table:

```markdown
> `collection videos` drives Playwright directly (TikTokApi has no collection endpoint). It reads
> **public** collections; for your own/private saved collection, run `tiktok-cli auth --login` once,
> then re-run. An empty result is reported, not silently treated as zero videos.
```

- [ ] **Step 7: Run the full gate**

Run the four gate commands. Expected: all pass; ruff/mypy clean (run `ruff format` first if needed).

- [ ] **Step 8: Commit**

```bash
git add tiktok_cli/commands/collection.py tiktok_cli/app.py tests/integration/test_collection_cmd.py README.md
git commit -m "feat: add 'collection videos' command (public collection enumeration)"
```

---

# PART B — vox-video skill (markdown) + orchestrator + eval

All commands below run from `/Users/joseph/projects/vox`. The validator is `python3 tools/validate_skills.py skills` (exits `1` on any problem; prints `[ok]`/`[FAIL]` per skill). It requires each skill dir to contain a `SKILL.md` with `name:` == dir name + a `description:`, and every local markdown link to resolve on disk.

### Task 5: `vox-video` reference playbooks

**Files:**
- Create: `skills/vox-video/references/ingest-playbook.md`
- Create: `skills/vox-video/references/tiktok-adapter.md`
- Create: `skills/vox-video/references/digest-extension.md`

> The validator is NOT run in this task: a `vox-video/` dir without `SKILL.md` fails the validator by design. `SKILL.md` is added in Task 6, where the validator is run. Each reference file's own links resolve independently (verified in Step 4).

- [ ] **Step 1: Create the ingest playbook**

Create `skills/vox-video/references/ingest-playbook.md`:

~~~markdown
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
~~~

- [ ] **Step 2: Create the tiktok-adapter**

Create `skills/vox-video/references/tiktok-adapter.md`:

~~~markdown
# TikTok access adapter (tiktok-cli)

All TikTok access goes through `tiktok-cli` (read-only, session-native via ms_token — free, not a paid
API). This skill touches TikTok no other way. An Instagram adapter would replace THIS file's commands
while leaving the ingest/extract/return stages unchanged.

## Enumerate the input → video URL list
- **Collection URL** (`https://www.tiktok.com/@user/collection/Name-<id>`):
  `tiktok-cli --json collection videos "<url>"` → NDJSON rows `{id, author, url}`.
- **Playlist URL/id**: `tiktok-cli --json playlist videos "<id>"` → NDJSON video rows.
- **Bare URL list** (paste/file): use as-is; no enumeration call.

**Public vs private:** headless enumeration reads PUBLIC collections. If a collection returns zero
rows it may be private/own-saved → tell the user to run `tiktok-cli auth --login` once (visible
browser, log in), then re-run. NEVER treat an empty enumeration as "0 videos" silently — report it.

## Per-video data (during ingest)
- Metadata: `tiktok-cli --json video info "<url>"` → one object (`desc`, author, `createTime`,
  `stats.playCount`/`diggCount`, music). Source of engagement + recency + caption signals.
- Comments: `tiktok-cli --json video comments "<url>" -n 50` → NDJSON `{cid, text, digg_count, ...}`.
- Media: `tiktok-cli video download "<url>" -o <workdir>/<id>/video.mp4`.

## Exit codes → ingest status
`0` ok · `2` usage · `3` token/blocked (treat as ms_token issue) · `4` Playwright/library missing
(a `no-capability` halt). A non-zero on ONE video is recorded in that item's `status.json`; it never
aborts the whole collection.
~~~

- [ ] **Step 3: Create the digest extension**

Create `skills/vox-video/references/digest-extension.md`:

~~~markdown
# Video digest extension

`vox-video` returns the standard 7-section [digest contract](../../vox/references/digest-contract.md).
This file says how video-only signals populate those sections — and the five rules that keep it
honest. The orchestrator ingests the SAME 7 sections; video just makes them richer.

## How video signals map onto the digest
- **Claims table** — each row's source URL is the **video URL with a timestamp/frame** (`…/video/<id>`
  `@0:47` for spoken; `frame f3_50pct` for on-screen). Confidence mark is **capped by signal source**
  (Rule 1). One row per claim atom (price / dish / verdict / logistics), not one prose blob per place.
- **Sentiment & consensus** — creator sentiment and **comment-crowd sentiment are separate**;
  consensus-strength uses cross-video `mention_count` (3 videos by 3 creators = STRONG; 1 = SINGLE-SOURCE).
- **Corroboration notes** — carry the video-native fields: **engagement** (views/likes/saves as a
  popularity proxy), **creator + COI** (organic/sponsored/comped/affiliate), **recency** (upload date;
  flag stale claims).
- **Estimates labeled** — caption/on-screen-derived figures are `~` until verified; band-vs-verified
  prices follow the same rule the maps playbook uses.
- **Sources that failed** — list ingest failures explicitly: empty-transcript videos (by id),
  unresolved/garbled entities, rate-limited comments (`none_fetched` ≠ neutral), un-enumerated items.

## The five honesty rules (each fixes a documented failure of the inspiration run)
1. **Signal-priority confidence** — transcript (spoken) > on-screen > caption; comments are a separate
   crowd channel, never merged into the creator's claim. A claim's confidence is capped by its source.
2. **No phantom quotes** — a transcript-sourced (spoken) claim may exist ONLY if that video's
   transcript status is `ok`. Empty-audio videos still contribute on-screen/caption claims, labeled.
3. **Every claim carries a URL** (+ timestamp/frame when spoken/on-screen) — traceability to the moment.
4. **Engagement & recency are fields, not afterthoughts** — used as ranking inputs/tie-breakers; stale
   claims flagged from the upload date.
5. **"No data" ≠ "neutral"** — record coverage (e.g. `comments: none_fetched`) so silence is never
   read as consensus.
~~~

- [ ] **Step 4: Verify each file's links resolve**

Run:
```
ls skills/vox-video/references/
python3 - <<'PY'
import re, pathlib
root = pathlib.Path("skills/vox-video/references")
for md in root.glob("*.md"):
    for rel in re.findall(r"\]\((?!https?://|mailto:|#)([^)]+)\)", md.read_text()):
        target = (md.parent / rel.split("#",1)[0]).resolve()
        print("OK " if target.exists() else "MISSING", md.name, "->", rel)
PY
```
Expected: three files listed; every link prints `OK` (the `digest-extension.md` → `../../vox/references/digest-contract.md` resolves, and `ingest-playbook.md` → `tiktok-adapter.md`/`digest-extension.md` resolve).

- [ ] **Step 5: Commit**

```bash
git add skills/vox-video/references/
git commit -m "feat(vox-video): ingest, adapter, and digest-extension playbooks"
```

---

### Task 6: `vox-video/SKILL.md`

**Files:**
- Create: `skills/vox-video/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `skills/vox-video/SKILL.md` (frontmatter `description` MUST stay on ONE physical line — the validator's parser is line-based):

~~~markdown
---
name: vox-video
description: Vox video subagent. Use when dispatched by the vox orchestrator with a TikTok collection / playlist / video-URL list to ingest each video (download, transcript, frames/vision, comments), extract cited place claims, and return the Vox digest. Two-phase (ingest then analyze); REQUIRES local mw + ffmpeg + tiktok-cli. Returns the Vox digest.
---

# vox-video

You are the Vox video subagent. Given a TikTok collection / playlist / video-URL list, ingest each
video, extract structured place claims, and return the
[digest contract](../vox/references/digest-contract.md) with the video extensions in
[digest-extension](references/digest-extension.md). NEVER fabricate; a missing signal is recorded,
never papered over.

## Bootstrap (capability probe FIRST — hard prerequisites)
This tier REQUIRES local ASR — there is no caption-only fallback. Probe:
- `mw --help` (MacWhisper CLI, parakeet-v3 transcriber)
- `ffmpeg -version`
- `tiktok-cli doctor` (TikTokApi + Playwright + a resolvable ms_token)

If `mw`, `ffmpeg`, or `tiktok-cli` is missing → **HALT**: return Status `no-capability` naming the
missing tool + its one-line install, and do NOT degrade to a partial answer.

## Phase 1 — Ingest (per video, cached/resumable)
Follow [ingest-playbook](references/ingest-playbook.md): enumerate the input via
[tiktok-adapter](references/tiktok-adapter.md), then for each video
download → `mw` transcript → `ffmpeg` frames → vision on-screen text → comments, writing a cached
workdir with a per-stage `status.json`. Skip already-complete items on re-run.

## Phase 2 — Extract → claims
Per video, build claim atoms in signal-priority order **transcript → on-screen/visual → caption/desc**,
with **comments as a separate crowd channel**. Apply the five honesty rules in
[digest-extension](references/digest-extension.md) — above all: **no spoken-claim quote unless that
video's transcript status is `ok`**. Dedupe mentions to canonical entities; count cross-video
corroboration (`mention_count` / distinct creators).

## Sources & blocks
TikTok access is ONLY via [tiktok-adapter](references/tiktok-adapter.md) (`tiktok-cli`). Record every
ingest failure (empty transcript by id, unresolved entity, rate-limited comments, un-enumerated items)
for the digest's "sources that failed" section. Never retry a hard block; report it.

## Return
The digest contract: claims table with inline **video URL + timestamp/frame** and per-figure
confidence; sentiment + consensus (creator vs comment crowd separate); corroboration notes carrying
engagement / creator+COI / recency; estimates-labeled; sources-that-failed incl. ingest failures;
bottom line. Empty → Status: no-signal.
~~~

- [ ] **Step 2: Run the validator**

Run: `python3 tools/validate_skills.py skills`
Expected: every skill prints `[ok]`, including `vox-video`, and the command exits `0`. (This confirms `name: vox-video` matches the dir and all five links — `../vox/references/digest-contract.md`, `references/ingest-playbook.md`, `references/tiktok-adapter.md`, `references/digest-extension.md` — resolve.)

- [ ] **Step 3: Commit**

```bash
git add skills/vox-video/SKILL.md
git commit -m "feat(vox-video): two-phase collection-analyzer SKILL.md"
```

---

### Task 7: Orchestrator integration

**Files:**
- Modify: `skills/vox/SKILL.md` (steps 2, 3, 7; new Video-tier section)

- [ ] **Step 1: Add video routing (step 2)**

In `skills/vox/SKILL.md`, find the end of step 2 (the routing step), which ends with:

```
   NEED the browser tier (drives the Browser-tier gate below).
```

Replace that line with:

```
   NEED the browser tier (drives the Browser-tier gate below). **Video collections / playlists /
   explicit video-URL lists → the video tier (`vox-video`)**, which ingests each video and surfaces
   candidate places for the other sources to corroborate (drives the Video-tier gate below).
```

- [ ] **Step 2: Add Wave-1 dispatch (step 3)**

In step 3, find the sentence:

```
   more than one browser agent.
```

(at the end of the Wave-1 paragraph). Immediately after it, add:

```
   When the INPUT is a TikTok collection / playlist / video-URL list, `vox-video` is the Wave-1
   **discovery driver**: dispatch exactly ONE `vox-video` agent (it loads `vox-video`/SKILL.md and
   runs its two-phase ingest→extract; it REQUIRES `mw` + `ffmpeg` + `tiktok-cli`). Treat its surfaced
   entities as the candidate set the stateless three + browser then corroborate (steps 4–5).
   `vox-video` uses tiktok-cli's own headless Playwright — a SEPARATE browser from `vox-browser`'s
   Chrome — so it never contends with the browser tier. Never run more than one `vox-video` agent.
```

- [ ] **Step 3: Add the render note (step 7)**

In step 7 (the Render step), find:

```
7. **Render** `references/output-template.md` with per-figure confidence + an auditable scoreboard.
```

Replace with:

```
7. **Render** `references/output-template.md` with per-figure confidence + an auditable scoreboard.
   For video-tier runs, add a **video-provenance** column (video URL + timestamp/frame, creator + COI,
   engagement) and list ingest failures (empty transcripts, unresolved entities, rate-limited comments)
   in the "Sources that failed / blocked" line.
```

- [ ] **Step 4: Add the Video-tier gate section**

Find the end of the `## Browser tier (single serial owner; halt-by-default)` section — the line:

```
NOT a hard halt — `vox-web` already disclosed the gap; note it and move on. A `vox-browser` agent
that returns no usable digest (orphaned/dead) counts as UNavailable for its sub-questions.
```

Immediately after that line (before `## Hard rules`), insert a new section:

```
## Video tier (collection analyzer; halt-by-default on missing prereqs)
Triggered when the input is a TikTok collection / playlist / video-URL list (not a plain topic
query). `vox-video` is the candidate-discovery driver: it ingests each video (download → `mw`
transcript → `ffmpeg` frames/vision → comments), extracts place claims under the five honesty rules,
and returns the digest; the stateless sources + browser then corroborate its candidates.
- **Prereqs REQUIRED** (this tier requires local ASR): `mw`, `ffmpeg`, `tiktok-cli` (+ resolvable
  ms_token). If any is missing → **HALT-AND-REPORT** the missing tool + its install; do NOT produce a
  partial answer (there is no `--web-fallback` for video — the videos ARE the source).
- **Single video agent**: exactly one `vox-video`, ever. It owns tiktok-cli's headless Playwright,
  independent of `vox-browser`'s real Chrome (no contention).
- **Heavy / resumable**: ingest is cached; follow-ups re-weight the candidate set without re-downloading.
- **No phantom quotes**: a video whose transcript came back empty contributes on-screen/caption claims
  only — never a spoken quote.
```

- [ ] **Step 5: Run the validator**

Run: `python3 tools/validate_skills.py skills`
Expected: all `[ok]` (the edits add no new links; `vox` still validates).

- [ ] **Step 6: Commit**

```bash
git add skills/vox/SKILL.md
git commit -m "feat(vox): route collection/playlist/URL inputs to the vox-video tier"
```

---

### Task 8: Eval golden + judge + run-eval

**Files:**
- Create: `eval/goldens/video-collection.md`
- Modify: `eval/judge-rubric.md`
- Modify: `eval/run-eval.md`

- [ ] **Step 1: Create the golden**

Create `eval/goldens/video-collection.md`:

~~~markdown
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
~~~

- [ ] **Step 2: Extend the judge rubric**

In `eval/judge-rubric.md`, find the `DEGRADATION:` criterion line:

```
- DEGRADATION: blocked/failed sources listed; thin evidence stated rather than papered over?
```

Add this line immediately after it:

```
- *PROVENANCE: (video-sourced runs only; pass=n/a otherwise) does every spoken-claim quote trace to a video with a real transcript (no phantom quotes), and does every pick cite a video URL (+ timestamp/frame)?
```

- [ ] **Step 3: Add the run-eval manual section**

In `eval/run-eval.md`, append at the end of the file:

~~~markdown
## Video-tier rigor (manual, capability-gated)
The video tier needs local `mw` + `ffmpeg` + `tiktok-cli` + a real ms_token, which the headless rigor
workflow lacks — so run it by hand, the analogue of the browser-tier rigor:
1. Ensure prereqs: `mw --help`, `ffmpeg -version`, `tiktok-cli doctor` all green.
2. Run `eval/goldens/video-collection.md`'s query through `/vox` with a real PUBLIC collection URL,
   Chrome paired for the Maps corroboration.
3. Capture to `eval/runs/video-collection.md`; grade with both layers — `structural_checks` must print
   `[]`, and the judge `VERDICT` must be `pass` (including the new `PROVENANCE` criterion).
4. Sanity-check the HALT path: with `mw` renamed/unavailable, the run STOPS and names the missing
   prereq instead of producing a partial answer.
~~~

- [ ] **Step 4: Verify the golden's structure + validator unaffected**

Run:
```
grep -c '^## \(Query\|Family\|Expectations\)' eval/goldens/video-collection.md
python3 tools/validate_skills.py skills
```
Expected: the grep prints `3`; the validator prints all `[ok]` (goldens/rubric/run-eval are not skills, so skill validation is unchanged).

- [ ] **Step 5: Commit**

```bash
git add eval/goldens/video-collection.md eval/judge-rubric.md eval/run-eval.md
git commit -m "test(vox-video): collection golden + PROVENANCE judge criterion + manual rigor doc"
```

---

### Task 9: Install + final verification

**Files:** none (integration only)

- [ ] **Step 1: Install the new skill**

Run: `./install.sh`
Expected: output includes `linked vox-video -> …/.claude/skills/vox-video` (or a re-link line); no "skipping" warning for vox-video.

- [ ] **Step 2: Final validator pass**

Run: `python3 tools/validate_skills.py skills`
Expected: all skills `[ok]`, exit `0`.

- [ ] **Step 3: Confirm the installed skill resolves its links**

Run:
```
python3 tools/validate_skills.py "$HOME/.claude/skills"
```
Expected: `vox-video [ok]` among the installed skills (the symlink target's `../vox/...` link resolves because the repo layout is preserved through the symlink).

- [ ] **Step 4: Record the manual rigor as the remaining step**

The automated gate is green. The live capability-gated rigor (Task 8 §"Video-tier rigor") is run interactively with `mw`/`ffmpeg`/`tiktok-cli` present and Chrome paired — it is NOT part of the headless gate, exactly like the browser-tier golden. No commit needed (no file changes); note completion to the user.

---

## Self-review

**1. Spec coverage** — every spec section maps to a task:
- §3 D2 (arch split) → Parts A & B. D3 (enumeration) → Tasks 1–4. D4/D5 (pluggable ASR, signal priority) → Tasks 5–6 (ingest + digest-extension). D6 (two-phase cached) → Task 5 ingest-playbook. D7 (TikTok-only, IG-ready) → tiktok-adapter as the swappable seam (Task 5). D8 (places-first) → golden family (Task 8). D9 (halt on missing prereq) → Task 6 Bootstrap + Task 7 Video-tier gate. D10 (reuse digest/output) → digest-extension (Task 5) + render note (Task 7).
- §5 inputs/enumeration/workdir/prereqs → Tasks 1–4 (CLI) + Task 5 (playbooks) + Task 6 (probe).
- §6 digest contract + five rules → Task 5 digest-extension.md.
- §7 corroboration/ranking/output → Task 7 (orchestrator) + Task 5 (digest-extension).
- §8 execution model → Task 5 ingest-playbook (cached/resumable) + Task 7 (single agent, no contention).
- §9 eval/rigor → Tasks 1–4 (CLI TDD + gate) + Task 8 (golden, judge, run-eval) + Task 9.
- §10 file structure → the File structure section (with the `digest-extension.md` naming note).
- §11/§12 deferred (query-time, IG) + search appendix → out of scope by design; not tasked.

**2. Placeholder scan** — no TBD/TODO; every code and content step is complete and literal. The only angle-bracketed token is `<public-collection-url>` inside the golden's example query, which is intentionally a runtime value the human supplies.

**3. Type/identifier consistency** — `scrape_collection` signature in Task 3 matches its call in Task 4 (`url`, `headless=`, `max_scrolls=`). `_extract_video_urls` row shape `{id, author, url}` (Task 2) matches `COLLECTION_COLUMNS` accessors (Task 4). `FakeTikTokApi.playlist(id=…)` (Task 1) matches the command's `api.playlist(id=playlist_id)` (Task 1) and the real `TikTokApi.playlist(id=…).videos(count=…)`. The `app.py` import line is edited additively (Task 1 adds `playlist`, Task 4 adds `collection`) so the final state is consistent. Skill link paths (`../vox/references/digest-contract.md` from `SKILL.md`; `../../vox/references/digest-contract.md` from `references/digest-extension.md`) reflect their differing directory depths — verified in Task 5 §4 and Task 6 §2.

---

## Execution Handoff

Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, two-stage review between tasks, fast iteration. Well-suited here since the 9 tasks are independently verifiable (CLI tasks by the gate, vox tasks by the validator).

**2. Inline Execution** — execute tasks in this session with batch checkpoints.

Note the cross-repo boundary: Tasks 1–4 run in `/Users/joseph/projects/tiktok-api-cli`; Tasks 5–9 run in `/Users/joseph/projects/vox`. The final live rigor (Task 9 §4) is manual and capability-gated.
