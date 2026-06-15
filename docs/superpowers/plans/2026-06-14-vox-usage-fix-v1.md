# Vox usage-fix v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ COMMITS ARE HELD.** Per the user's instruction, implement and run the gates but do **not**
> commit or push until the user approves. The `Commit` steps below show the *intended* grouping
> for when that approval comes — execute everything up to them, leave the tree staged/clean, and
> ask before committing.

**Goal:** Ship the three validated P1 fixes from `docs/2026-06-14-vox-usage-fix-v1-design.md`:
A7 (gosom review-volume flag + re-fetch, maps-cli code), A5 (brand-engine availability verify,
prose), A14 (background-browser narration / no false-stall self-stop, prose).

**Architecture:** A7 is real Python in `maps-cli` (TDD): `normalize.py` stops emitting a
misleading `0` and adds `reviewCountStatus`; a new `resolve.py` recovers a missing volume with
one bounded gosom re-fetch via the place's category; `places.py` renders `×⚠` and routes
through it. A5/A14 are prose rules in the `vox`, `vox-maps`, and `vox-browser` skill playbooks.

**Tech Stack:** Python 3.14 + Typer + pytest/ruff (maps-cli); Markdown skill playbooks (vox);
`tools/validate_skills.py` as the vox gate.

---

## File Structure

**maps-cli (A7):**
- Modify: `maps-cli/maps_cli/normalize.py` — add `_review_fields`, emit `reviewCountStatus`.
- Create: `maps-cli/maps_cli/resolve.py` — `resolve_with_volume()` (gosom → match → re-fetch → normalize).
- Modify: `maps-cli/maps_cli/commands/places.py` — route through `resolve.resolve_with_volume`; `×⚠` renderer.
- Modify: `maps-cli/tests/unit/test_normalize.py` — status assertions + 0/None cases.
- Create: `maps-cli/tests/unit/test_resolve.py` — re-fetch behavior with a call-scripted fake.
- Create: `maps-cli/tests/unit/test_places_render.py` — the `_rating_reviews` cell.

**vox skills (A7 carry-forward + A5 + A14):**
- Modify: `vox/skills/vox-maps/SKILL.md` — consume `reviewCountStatus`; note the auto-re-fetch.
- Modify: `vox/skills/vox/SKILL.md` — A7 carry-forward rule; A5 bookable-inventory verify; A14 narration + no-self-stop.
- Modify: `vox/skills/vox-browser/SKILL.md` — brand-engine check; legitimate-pause note.
- Modify: `vox/skills/vox/references/output-template.md` — bookable verification tag.

**Gates:**
- maps-cli: `cd maps-cli && .venv/bin/python -m pytest -q` ; `.venv/bin/python -m ruff check maps_cli tests`
- vox: `cd vox && .venv/bin/python tools/validate_skills.py skills` (prints `[ok]` per skill)

---

## Task Group A7 — gosom review-volume (maps-cli, TDD)

### Task 1: `normalize.py` emits `reviewCountStatus`, nulls the misleading zero

**Files:**
- Modify: `maps-cli/maps_cli/normalize.py`
- Test: `maps-cli/tests/unit/test_normalize.py`

- [ ] **Step 1: Update existing tests + add the 0/None cases**

In `tests/unit/test_normalize.py`, add `reviewCountStatus` to the two existing assertions and add two cases:

```python
def test_normalize_maps_fields():
    out = normalize.normalize_place(RAW, confidence="high", alternatives=[ALT])
    assert out["name"] == "Luigi's Pizza"
    assert out["rating"] == 4.6
    assert out["reviewCount"] == 2487
    assert out["reviewCountStatus"] == "ok"
    assert out["address"] == "686 5th Ave, Brooklyn, NY 11215"
    assert out["hours"] == {"Monday": ["11 AM-10 PM"]}
    assert out["mapsUrl"] == "https://www.google.com/maps/place/Luigis"
    assert out["confidence"] == "high"
    assert out["source"] == "google-maps/gosom"


def test_normalize_alternatives_are_brief():
    out = normalize.normalize_place(RAW, confidence="high", alternatives=[ALT])
    assert out["alternatives"] == [
        {
            "name": "Scarpetta",
            "rating": 4.6,
            "reviewCount": 3251,
            "reviewCountStatus": "ok",
            "address": "88 Madison Ave, New York, NY 10016",
            "mapsUrl": "https://www.google.com/maps/place/Scarpetta",
        }
    ]


def test_normalize_zero_review_count_is_unavailable():
    raw = {**RAW, "review_count": 0}
    out = normalize.normalize_place(raw, confidence="high")
    assert out["reviewCount"] is None
    assert out["reviewCountStatus"] == "unavailable"


def test_normalize_missing_review_count_is_unavailable():
    raw = {k: v for k, v in RAW.items() if k != "review_count"}
    out = normalize.normalize_place(raw, confidence="high")
    assert out["reviewCount"] is None
    assert out["reviewCountStatus"] == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd maps-cli && .venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: FAIL — `KeyError: 'reviewCountStatus'` / the alternatives dict lacks the new key.

- [ ] **Step 3: Implement `_review_fields` and use it**

In `maps_cli/normalize.py`, add the helper and wire it into both `_brief` and `normalize_place`:

```python
def _review_fields(raw: dict) -> dict:
    n = raw.get("review_count")
    if not n:  # 0, None, or missing -> a DOM-extraction miss, NOT a real zero
        return {"reviewCount": None, "reviewCountStatus": "unavailable"}
    return {"reviewCount": n, "reviewCountStatus": "ok"}


def _brief(raw: dict) -> dict:
    return {
        "name": raw.get("title"),
        "rating": raw.get("review_rating"),
        **_review_fields(raw),
        "address": raw.get("address"),
        "mapsUrl": raw.get("link"),
    }
```

In `normalize_place`, replace the line `"reviewCount": raw.get("review_count"),` with `**_review_fields(raw),` (keeping it right after `"rating": ...,`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd maps-cli && .venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** *(HELD — stage only, ask first)*

```bash
git -C maps-cli add maps_cli/normalize.py tests/unit/test_normalize.py
git -C maps-cli commit -m "feat(normalize): flag gosom reviewCount 0/null as volume-unavailable"
```

---

### Task 2: `resolve.py` — recover a missing volume with one bounded re-fetch

**Files:**
- Create: `maps-cli/maps_cli/resolve.py`
- Test: `maps-cli/tests/unit/test_resolve.py`

- [ ] **Step 1: Write the failing test (call-scripted fake gosom)**

Create `tests/unit/test_resolve.py`:

```python
from maps_cli import resolve

TOMPKINS_0 = {"title": "Tompkins Square Bagels", "review_rating": 4.4, "review_count": 0,
              "category": "Bagel shop", "address": "165 Ave A", "link": "https://maps/tsb"}
TOMPKINS_860 = {"title": "Tompkins Square Bagels", "review_rating": 4.4, "review_count": 860,
                "category": "Bagel shop", "address": "165 Ave A", "link": "https://maps/tsb"}
ZUCKERS_460 = {"title": "Zucker's Bagels", "review_rating": 4.5, "review_count": 460,
               "category": "Bagel shop", "address": "146 Chambers St", "link": "https://maps/z"}


def _script(monkeypatch, *batches):
    calls = []

    def fake(query, **kw):
        calls.append(query)
        return batches[len(calls) - 1]

    monkeypatch.setattr(resolve.gosom, "run_gosom", fake)
    return calls


def test_recovers_volume_via_category_refetch(monkeypatch):
    calls = _script(monkeypatch, [TOMPKINS_0], [TOMPKINS_860])
    rec = resolve.resolve_with_volume("Tompkins Square Bagels", "East Village")
    assert rec["reviewCount"] == 860
    assert rec["reviewCountStatus"] == "ok"
    assert len(calls) == 2
    assert calls[1] == "Bagel shop East Village"  # re-fetch uses the matched category


def test_stays_unavailable_when_refetch_also_zero(monkeypatch):
    calls = _script(monkeypatch, [TOMPKINS_0], [TOMPKINS_0])
    rec = resolve.resolve_with_volume("Tompkins Square Bagels", "East Village")
    assert rec["reviewCount"] is None
    assert rec["reviewCountStatus"] == "unavailable"
    assert len(calls) == 2


def test_no_refetch_when_primary_has_volume(monkeypatch):
    calls = _script(monkeypatch, [ZUCKERS_460])
    rec = resolve.resolve_with_volume("Zucker's Bagels", "Tribeca")
    assert rec["reviewCount"] == 460
    assert len(calls) == 1  # no second gosom call


def test_no_refetch_when_no_match(monkeypatch):
    calls = _script(monkeypatch, [{"title": "Totally Different Place", "review_count": 5}])
    rec = resolve.resolve_with_volume("Tompkins Square Bagels", "East Village")
    assert rec["name"] is None  # matcher found no match
    assert len(calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd maps-cli && .venv/bin/python -m pytest tests/unit/test_resolve.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'maps_cli.resolve'`.

- [ ] **Step 3: Implement `resolve.py`**

Create `maps_cli/resolve.py`:

```python
"""Resolve one finalist to a normalized record, recovering review-volume with one
gosom re-fetch when the list-card extraction misses it (returns 0/null)."""

from __future__ import annotations

from . import gosom, matcher, normalize


def _missing_volume(raw: dict | None) -> bool:
    return not (raw or {}).get("review_count")


def resolve_with_volume(
    name: str,
    near: str,
    *,
    search: str | None = None,
    n: int = 5,
    timeout: float = 90.0,
) -> dict:
    """gosom -> match -> (one category re-fetch if volume missing) -> normalize."""
    primary_query = f"{search} {near}" if search else f"{name} {near}"
    rows = gosom.run_gosom(primary_query, depth=1, timeout=timeout)
    match = matcher.select_match(rows[:n] if n else rows, name)
    best = match.best or {}

    # Recover a missing volume with ONE re-fetch via the matched place's category
    # (a broad term that lands a different DOM variant). NEVER re-fetch by exact name
    # alone -- that is the single-page anti-bot trap the --search flag exists to dodge.
    if match.best is not None and _missing_volume(best):
        fallback_term = best.get("category")
        if fallback_term:
            rows2 = gosom.run_gosom(f"{fallback_term} {near}", depth=1, timeout=timeout)
            match2 = matcher.select_match(rows2[:n] if n else rows2, name)
            if match2.best is not None and not _missing_volume(match2.best):
                best = {
                    **best,
                    "review_count": match2.best.get("review_count"),
                    "review_rating": best.get("review_rating") or match2.best.get("review_rating"),
                }

    return normalize.normalize_place(
        best, confidence=match.confidence, alternatives=match.alternatives
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd maps-cli && .venv/bin/python -m pytest tests/unit/test_resolve.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit** *(HELD — stage only, ask first)*

```bash
git -C maps-cli add maps_cli/resolve.py tests/unit/test_resolve.py
git -C maps-cli commit -m "feat(resolve): recover missing gosom review-volume via one category re-fetch"
```

---

### Task 3: `places.py` routes through `resolve_with_volume` and renders `×⚠`

**Files:**
- Modify: `maps-cli/maps_cli/commands/places.py`
- Test: `maps-cli/tests/unit/test_places_render.py`

- [ ] **Step 1: Write the failing renderer test**

Create `tests/unit/test_places_render.py`:

```python
from maps_cli.commands.places import _rating_reviews


def test_rating_reviews_shows_count_when_ok():
    assert _rating_reviews({"rating": 4.5, "reviewCount": 460, "reviewCountStatus": "ok"}) == "4.5×460"


def test_rating_reviews_shows_warning_when_unavailable():
    assert _rating_reviews({"rating": 4.4, "reviewCount": None, "reviewCountStatus": "unavailable"}) == "4.4×⚠"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd maps-cli && .venv/bin/python -m pytest tests/unit/test_places_render.py -q`
Expected: FAIL — `ImportError: cannot import name '_rating_reviews'`.

- [ ] **Step 3: Refactor `places.py` — extract `_rating_reviews`, route through `resolve`**

In `maps_cli/commands/places.py`: replace the import line `from .. import gosom, matcher, normalize` with `from .. import resolve`; add the renderer helper and use it in `PLACE_COLUMNS`; replace the inline gosom/match/normalize block in the `places()` body with a single `resolve` call.

```python
from .. import resolve
...
def _rating_reviews(r: dict) -> str:
    if r.get("reviewCountStatus") == "unavailable":
        return f"{r.get('rating')}×⚠"
    return f"{r.get('rating')}×{r.get('reviewCount')}"


PLACE_COLUMNS = [
    Column("Name", lambda r: r.get("name") or "—"),
    Column("Rating×Reviews", _rating_reviews),
    Column("Address", lambda r: r.get("address") or ""),
    Column("Conf", lambda r: r.get("confidence") or ""),
    Column("MapsUrl", lambda r: r.get("mapsUrl") or ""),
]
```

In the `places()` body, replace the three lines that call `gosom.run_gosom`, `matcher.select_match`, and `normalize.normalize_place` with:

```python
        record = resolve.resolve_with_volume(name, near, search=search, n=n, timeout=timeout)
```

(Delete the now-unused `gosom_query` line.)

- [ ] **Step 4: Run the full maps-cli suite + ruff**

Run: `cd maps-cli && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check maps_cli tests`
Expected: PASS, ruff clean. (The existing `places` integration tests still pass because `resolve_with_volume` preserves the gosom→match→normalize path for the happy case.)

- [ ] **Step 5: Commit** *(HELD — stage only, ask first)*

```bash
git -C maps-cli add maps_cli/commands/places.py tests/unit/test_places_render.py
git -C maps-cli commit -m "feat(places): route through resolve_with_volume; render volume-unavailable as ×⚠"
```

---

### Task 4: vox playbook — consume `reviewCountStatus` + carry-forward rule

**Files:**
- Modify: `vox/skills/vox-maps/SKILL.md`
- Modify: `vox/skills/vox/SKILL.md`

- [ ] **Step 1: Update `vox-maps/SKILL.md` digest rule**

Replace the line that reads `reviewCount of 0/null → flag volume-UNAVAILABLE (⚠), NOT "0 reviews".` with:

```
   `maps-cli` now returns `reviewCountStatus` and auto-re-fetches once when the list-card volume
   is missing. Read it: `reviewCountStatus: "unavailable"` → render `⚠ volume-UNAVAILABLE`
   (never "0 reviews"); `"ok"` → use the `reviewCount`. A finalist whose volume is unavailable
   ranks on rating only — say so in the digest.
```

- [ ] **Step 2: Add the carry-forward rule to `vox/SKILL.md` Places tier**

Under `## Places & browser tier`, add a bullet:

```
- **Carry resolved review-volume forward.** Once a finalist's review volume is resolved in a
  run, reuse that reconciled number across session resumes / follow-ups — never let a finalist's
  volume silently change between turns (gosom can return a different list-card count on a later
  fetch; the first resolved value wins unless a verification step deliberately re-checks it).
```

- [ ] **Step 3: Run the vox skills gate**

Run: `cd vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for every skill (including vox-maps and vox).

- [ ] **Step 4: Commit** *(HELD — stage only, ask first)*

```bash
git -C vox add skills/vox-maps/SKILL.md skills/vox/SKILL.md
git -C vox commit -m "docs(vox-maps): consume reviewCountStatus; carry resolved volume across turns"
```

---

## Task Group A5 — brand-engine availability verification (prose)

### Task 5: `vox/SKILL.md` bookable-inventory verify rule + degrade + honesty tag

**Files:**
- Modify: `vox/skills/vox/SKILL.md`
- Modify: `vox/skills/vox/references/output-template.md`

- [ ] **Step 1: Add the bookable-inventory rule under `## Places & browser tier`**

Insert this block:

```
### Bookable-inventory verification (lodging / housing)
When the query is **bookable-inventory** — lodging/housing intent (hotel, motel, inn, room,
stay, lodge, Airbnb / short-term rental, apartment, rental, lease, sublet) — AND the answer
will present a specific price/availability as actionable, then in **Wave 2** dispatch the single
`vox-browser` agent to verify the **top 3 finalists'** current availability + nightly price on
the **brand booking engine** (the property's own site, or the platform that actually takes the
booking) BEFORE ranking them as bookable. The three checks run serially through the one browser
agent. Aggregator prices (Google Hotels / Booking / Kayak snippets) are **availability signals
only** — they may rank candidates but may NOT be presented as "book this at $X" until brand-
verified. **No Chrome →** present aggregator prices with a `⚠ unverified — aggregator price,
confirm on the brand site` tag, never as a booking instruction (honest degrade, not a halt).
```

- [ ] **Step 2: Add the verification tag to the honesty gate**

In `## Places & browser tier` (or the step-7 honesty gate), add:

```
- **Bookable picks carry a verification tag:** `brand-verified ✓` (rate + availability
  confirmed on the brand engine) or `aggregator-only ⚠` (price is a signal, not confirmed
  bookable). A sold-out finalist confirmed on the brand site is dropped or shown struck-through,
  never ranked #1.
```

- [ ] **Step 3: Add the tag to `references/output-template.md`**

In the scoreboard/finalist section, add a line documenting the `brand-verified ✓ / aggregator-only ⚠`
tag for lodging/bookable rows so the render carries it.

- [ ] **Step 4: Run the vox skills gate**

Run: `cd vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for every skill.

- [ ] **Step 5: Commit** *(HELD — stage only, ask first)*

```bash
git -C vox add skills/vox/SKILL.md skills/vox/references/output-template.md
git -C vox commit -m "feat(vox): brand-engine verify top-3 bookable finalists before ranking"
```

---

### Task 6: `vox-browser/SKILL.md` brand-engine availability check

**Files:**
- Modify: `vox/skills/vox-browser/SKILL.md`

- [ ] **Step 1: Add the brand-engine check playbook**

Add a section:

```
## Brand-engine availability check (lodging)
Given a finalist name + dates, navigate the **brand booking engine** (the property's own site,
or the platform that takes the booking — NOT an aggregator tab), read the live nightly rate +
availability, and return `{available: bool, rate, url}`. Handle the sold-out / "no rooms" state
explicitly (`available: false`) — never infer availability from a Google Hotels / Booking
aggregator price. If the brand engine can't be reached, return `available: null` with the reason
so the orchestrator degrades to the aggregator-only `⚠` tag rather than asserting bookability.
```

- [ ] **Step 2: Run the vox skills gate**

Run: `cd vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for every skill.

- [ ] **Step 3: Commit** *(HELD — stage only, ask first)*

```bash
git -C vox add skills/vox-browser/SKILL.md
git -C vox commit -m "feat(vox-browser): brand-engine availability check for lodging finalists"
```

---

## Task Group A14 — background-browser narration / no false-stall self-stop (prose)

### Task 7: `vox/SKILL.md` + `vox-browser/SKILL.md` narration rules

**Files:**
- Modify: `vox/skills/vox/SKILL.md`
- Modify: `vox/skills/vox-browser/SKILL.md`

- [ ] **Step 1: Add the narration + no-self-stop rule to `vox/SKILL.md` browser tier**

Add a bullet under `## Places & browser tier`:

```
- **Narrate the background browser; never self-stop on an inferred stall.** When you dispatch
  the single browser agent in the background, narrate at launch: what it's doing, which
  finalists it will visit, and that **Chrome will move on its own** and **quiet 30–60s gaps
  between clicks are normal, not a hang.** Do NOT `TaskStop` a browser agent because of a quiet
  period or a "looks frozen" inference — stop ONLY on an explicit user request or a real
  surfaced error. Browser steps legitimately pause between actions (page loads, model
  think-time).
```

- [ ] **Step 2: Add the legitimate-pause note to `vox-browser/SKILL.md`**

Add a line near the bootstrap:

```
Browser steps legitimately pause between actions (navigations, page loads, think-time between
clicks) — a 30–60s quiet gap is NOT a hang. Emit a short progress line between major steps where
the harness allows, so a backgrounded run reads as alive.
```

- [ ] **Step 3: Run the vox skills gate**

Run: `cd vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for every skill.

- [ ] **Step 4: Commit** *(HELD — stage only, ask first)*

```bash
git -C vox add skills/vox/SKILL.md skills/vox-browser/SKILL.md
git -C vox commit -m "feat(vox): narrate background browser; never self-stop on inferred stall"
```

---

## Final verification

- [ ] **maps-cli gate green:** `cd maps-cli && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check maps_cli tests` — all pass, ruff clean.
- [ ] **vox gate green:** `cd vox && .venv/bin/python tools/validate_skills.py skills` — `[ok]` for every skill.
- [ ] **Live-rigor spot check (optional, recommended):** run a lodging vox query (e.g. "hotels near LGA for one night") and confirm: the top-3 finalists get a brand-engine verify pass (A5), bookable picks carry the `✓/⚠` tag, and the background browser run is narrated with no self-stop (A14).
- [ ] **Report to user and ask before committing/pushing** (commits were held).

## Self-review notes
- **Spec coverage:** A7 §→Tasks 1-4; A5 §→Tasks 5-6; A14 §→Task 7. All three spec sections mapped.
- **Type consistency:** `reviewCountStatus` ("ok"/"unavailable") and nulled `reviewCount` used
  identically across `normalize.py`, `resolve.py`, `places.py`, and their tests; `resolve_with_volume`
  signature matches the `places()` call site.
- **No placeholders:** every code and prose step contains the literal content to add.
