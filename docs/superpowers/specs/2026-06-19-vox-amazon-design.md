# vox-amazon — Design Spec

**Date:** 2026-06-19
**Status:** Approved (design) — pending implementation plan
**Author:** vox maintainers (with Claude)

## Goal

Add an Amazon product + price-history source to vox so product/shopping queries
("best headphones under $300", "is this a good price right now", "price history of
<ASIN>") get a ranked, cited answer that includes **current price, the full daily
price-history, and a current-vs-typical read** — all subscription-native (no paid API,
no paid proxy).

## Locked decisions (from brainstorming)

1. **Form:** a vox **source skill** `vox-amazon` (lives in `vox/skills`, symlinked into
   `~/.claude/skills`, like the other `vox-*` skills).
2. **v1 scope:** **full source** — Amazon search → current price → full daily history,
   with fallbacks. (Not history-only.)
3. **HTTP tool home:** a **new private `amazon-cli` repo**, parallel to `maps-cli` /
   `tiktok-api-cli`.
4. **Keepa history integration:** a **playbook inside `vox-browser`** (the single Chrome
   owner), escalated to exactly like `vox-maps` escalates blocked finalists — NOT a second
   browser agent, NOT headless Playwright (neither passes Cloudflare Turnstile reliably).
5. **Packaging:** one design spec (this doc) + one phased implementation plan.

## Architecture overview

Four pieces, split along the anti-bot line so the "exactly one Chrome agent, ever"
invariant holds:

| Piece | Tier | Resource | Parallel? |
|---|---|---|---|
| `amazon-cli` (search + CCC summary) | stateless HTTP | none | yes (like vox-maps) |
| `vox-amazon` skill | stateless source | calls amazon-cli | yes |
| Keepa price-history | browser | the ONE real Chrome | serial (vox-browser owns it) |
| `vox` routing | orchestrator | — | — |

Stateless HTTP work runs in Wave 1 in parallel with reddit/x/web. The full daily curve
(Keepa) needs the real browser and is served by the single `vox-browser` agent, which
`vox-amazon` escalates to.

## Component 1 — `amazon-cli` (new repo)

Stateless HTTP CLI, no browser. Python, `curl_cffi` + AmzPy + BeautifulSoup. Editable-
installed `.venv` like maps-cli.

### Commands

`amazon-cli search "<query>" [--n N=10] [--domain us]`
→ JSON: `{"query":..., "domain":"us", "candidates":[ ... ], "status":"ok|partial|blocked"}`
where each candidate is:
```json
{
  "asin": "B09XS7JWHH",
  "title": "Sony WH-1000XM5 ...",
  "url": "https://www.amazon.com/dp/B09XS7JWHH",
  "price": 278.00,
  "currency": "USD",
  "priceStatus": "ok|unavailable",
  "rating": 4.2,
  "reviewCount": 19652,
  "reviewCountStatus": "ok|unavailable",
  "prime": true
}
```
- **Engine:** AmzPy `search_products(query, max_pages)` primary; on AmzPy import failure,
  empty result, or HTTP-202 throttle, fall back to a direct `curl_cffi` GET of the search
  page + BeautifulSoup selectors for the same fields.
- **Pacing:** randomized 2–5s delay, retry-on-202 (bounded), rotate `impersonate=`
  targets. Cap volume far under ~100k/day so no residential proxy is ever needed.

`amazon-cli price <ASIN> [--domain us]`
→ CCC summary JSON (the no-browser fallback; current/low/high/avg — NOT the daily curve):
```json
{
  "asin": "B09XS7JWHH",
  "source": "camelcamelcamel",
  "url": "https://camelcamelcamel.com/product/B09XS7JWHH",
  "types": {
    "amazon": {"current": 278.00, "lowest": {"price": 248.00, "date": "2025-11-29"},
               "highest": {"price": 399.99, "date": "2024-04-11"},
               "average": 312.40},
    "new":  { ... },
    "used": { ... }
  },
  "status": "ok|unavailable|blocked"
}
```
- **Engine:** `curl_cffi` GET `camelcamelcamel.com/product/{ASIN}` (returns 200 with a real
  browser UA, no paid proxy), parse the server-rendered summary table.

`amazon-cli doctor`
→ capability probe. Checks AmzPy importable, curl_cffi present, basic reachability.
Exit codes mirror maps-cli: **0 = ok, 4 = unavailable** (used by the vox capability-probe).

### Normalize / honesty layer
A `normalize.py` maps raw engine output → the stable schemas above, attaching explicit
**status flags**. Rules (the maps-cli review-volume lesson): a missing/empty
price/review-count is `*Status: "unavailable"`, NEVER a silent `0`. A bot-block (CAPTCHA /
non-200) is `status: "blocked"`, surfaced — never an empty success.

### Tests & gate
- Unit tests against **fake HTTP fixtures**: saved AmzPy-shaped objects + saved CCC product
  HTML (mirrors maps-cli's fake-gosom fixture). Cover: search happy path, AmzPy→curl_cffi
  fallback on 202, CCC parse, CCC blocked→status, normalize status flags, doctor exit codes.
- **No live network in tests.**
- Gate: `.venv/bin/python -m pytest -q` + `.venv/bin/python -m ruff check`.

## Component 2 — `vox-amazon` skill

A STATELESS vox source (parallel-safe like `vox-maps`). Lives in `vox/skills/vox-amazon/`,
symlinked. Follows the digest contract and output discipline of the other sources.

### Trigger (set by the orchestrator at routing)
Product / shopping / "good price?" / price-history sub-questions where an Amazon product is
in scope (named product, ASIN, Amazon URL, or a product category to search).

### Flow
1. Capability-probe `amazon-cli doctor` (exit 0 → available; 4 → declare lost coverage,
   degrade, do not fake).
2. If the query is a category ("best X under $Y") → `amazon-cli search` → candidate ASINs.
   If it names a product / ASIN / URL → resolve the ASIN directly.
3. For each candidate/finalist → `amazon-cli price <ASIN>` for current + CCC summary.
4. For finalists needing the **full daily curve**, tag the digest's `needs-browser` block:
   `keepa-history(asin=<ASIN>, domainId=1)` → the orchestrator escalates to the single
   `vox-browser` agent (mirrors the vox-maps→vox-browser escalation).
5. Return the Vox digest: candidate×field matrix, citations = Amazon + CCC URLs, per-figure
   status/hedges; list any blocked/partial fetches in "sources that failed / blocked".

### Honesty
- A `priceStatus`/`reviewCountStatus` of `unavailable` renders as a `⚠` marker, never a 0.
- `blocked` search → partial candidate set, explicitly disclosed.

## Component 3 — `vox-browser` Keepa price-history playbook

A new playbook in `vox-browser/SKILL.md` (the single Chrome owner). Implements the
reverse-engineered, live-verified extraction (see "Keepa protocol" below).

### Input / output
- **Input:** one or more `{asin, domainId}` (domainId 1 = amazon.com US) from the
  escalated `needs-browser` tags.
- **Output (per ASIN):**
  ```json
  {"asin":"...", "domainId":1,
   "current": {"amazon":..., "new":..., "used":..., "buyBox":...},
   "series": {"amazon":[{"date":"2026-05-18","price":49.99}, ...],
              "new":[...], "used":[...], "list":[...]},
   "stats": {"amazon": {"lowest":..., "average":..., "highest":...}, ...},
   "depthDays": 1499, "source":"keepa", "status":"ok|blocked"}
  ```

### Extraction recipe (driven real Chrome)
1. Navigate `keepa.com/#!product/{domainId}-{ASIN}` on the user's live session — passes
   Cloudflare **Turnstile** silently (a headless cold fetch will not).
2. Inject a tee over the global **`window.fzstd.decompress`** that records its decompressed
   output. (In the MCP, injection is post-load, so navigate to keepa.com first, install the
   tee, THEN hash-navigate to each target ASIN — each navigation triggers a fresh WebSocket
   fetch that flows through the tee. Tee once, iterate ASINs.)
3. Capture the `{"basicProducts":[{asin,title,csv:[...]}]}` JSON frame per ASIN.
4. Decode `csv` (pure function, see below) → series + current + stats.

### Keepa protocol (reference — reverse-engineered & live-verified 2026-06-19)
- Transport: **WebSocket to `push.keepa.com`** (no XHR is ever emitted — this is why the
  HTTP network monitor and the Amazon-page DOM see nothing).
- Request frame: zlib/deflate JSON (`0x78 0x9C`), e.g.
  `{"path":"product","type":"ws","history":true,"domainId":1,"asin":"<ASIN>","maxAge":3,
  "refreshProduct":false,"id":<n>,"version":"<YYYYMMDD>"}`.
- Response frame: **zstd**-compressed (the `fzstd.min.js` lib) JSON `{"basicProducts":[...]}`.
- `csv[i]` = flat `[keepaMinute, value, keepaMinute, value, ...]`.
  - date: `unix_ms = (keepaMinute + 21564000) * 60000` (Keepa-minute epoch = minutes since
    2011-01-01, NOT unix).
  - price: `value / 100` dollars; `value === -1` = no offer.
  - index legend (subset): 0=AMAZON, 1=NEW, 2=USED, 3=SALES_RANK, 4=LIST_PRICE, 11=BUY_BOX,
    18=BUY_BOX_SHIPPING. Indices 0/1/2/4 are clean 2-tuples; "…with shipping" series
    (Buy Box etc.) use a **3-wide stride** and need stride-aware parsing.

### Safety (hard)
- **Never solve a CAPTCHA / Turnstile interactive challenge.** This deliberately overrides
  the earlier research note recommending `amazoncaptcha`. If Amazon's bot-check or Keepa's
  Turnstile *presents an interactive challenge*, mark `blocked` and degrade — do not solve,
  do not bypass. We only proceed when Turnstile passes silently on the user's live session.
- Read-only. Never enter Keepa credentials (the free in-page chart needs none).
- On `blocked` / no Chrome → degrade to the CCC summary that `vox-amazon` already has; tag
  `history-unavailable`, lower confidence; never fabricate a series.

## Component 4 — `vox` orchestrator routing

Add a **"Product & price-history tier"** section to `vox/skills/vox/SKILL.md`, structured
like the existing "Places & browser tier":
- **Route** product / "good price?" / price-history sub-questions to `vox-amazon` (Wave 1,
  stateless, parallel). Mark which finalists NEED the full daily curve (drives Keepa
  escalation).
- **Availability gate:** `amazon-cli doctor` ok → run vox-amazon. Full-history needed +
  Chrome up → escalate Keepa to the single `vox-browser` agent. Full-history needed +
  no Chrome → degrade to CCC summary (low/high/avg) with a confidence penalty + a one-line
  "no daily-curve coverage" note. amazon-cli unavailable (exit 4) → declare lost coverage,
  proceed with the HTTP three.
- **Single-browser coordination:** if a run needs both logistics AND Keepa history, the one
  `vox-browser` agent does them serially (no new agent).
- **Render:** output template gains a price-history / "current vs typical" element with
  per-figure provenance (Keepa vs CCC vs AmzPy) and confidence, honoring the existing
  citation + honesty gates.

## Data flow (end-to-end)

```
query
  → vox parse (product? full-history needed?)
  → Wave 1 (parallel): vox-amazon [amazon-cli search → candidates; amazon-cli price → CCC
                       summary]  ||  vox-reddit  ||  vox-x  ||  vox-web
                       (+ single vox-browser agent runs the Keepa playbook on finalist
                        ASINs when full-history is needed and Chrome is up)
  → corroborate candidates across sources (2+ channels to promote)
  → Wave 2 verify (per-finalist facts + any contested figure)
  → rank by the user's priorities
  → render: ranked picks + current price + price-history (current vs typical) + provenance
```

## Error handling & degrade matrix

| Failure | Behavior |
|---|---|
| amazon-cli `doctor` exit 4 | declare lost Amazon coverage; run HTTP three; no fabrication |
| AmzPy 202 / parser miss | curl_cffi fallback; if still empty → `status: partial`, disclose |
| Amazon/Keepa CAPTCHA/Turnstile challenge | `blocked`; **do not solve**; degrade |
| CCC non-200 | `status: blocked`; rely on Keepa current; disclose |
| Keepa blocked / no Chrome | degrade to CCC low/high/avg; tag `history-unavailable`; lower confidence |
| All Amazon paths blocked | render reddit/x/web answer; "Amazon coverage unavailable" line |

## Testing strategy

- **amazon-cli:** fake-HTTP unit tests (saved AmzPy objects + CCC HTML fixtures), normalize
  status-flag tests, doctor exit-code tests. No live network. Gate: pytest + ruff.
- **Keepa decode:** the csv→series decoder is a **pure function**, unit-tested against a
  **captured real payload** committed as a fixture (decode → known date/price points;
  Keepa-minute epoch; `-1`=none; 2-tuple vs 3-stride). No browser in these tests.
- **Skills + routing:** `validate_skills.py` gate (`[ok]` per skill), then ONE live-rigor
  vox run on a real product query (verifies search → CCC → Keepa escalation → render).

## Phasing (each phase ships working, tested software)

1. **amazon-cli** — search + price + doctor + normalize + fake-HTTP tests; standalone, gated.
2. **Keepa extractor** — the pure decode module (unit-tested on the captured sample) + the
   `vox-browser` playbook prose.
3. **vox-amazon skill + vox routing** — ties 1+2 together; `validate_skills` + a live-rigor run.

## Out of scope (v1) / future

- Non-US marketplaces (domainId ≠ 1).
- Keepa Pro "Data"/CSV tabular export (login-gated) — we use the free in-page WS data.
- EU/UK keyless JSON trackers (PriceRunner/Idealo) — documented in research, deferred.
- Self-accumulated daily series / any residential-proxy path.

## Open risks

- **Brittleness:** Keepa's WS/compression/csv layout is private and can change without
  notice; AmzPy is thin/single-author. Mitigation: pure-function decoder with a fixture
  test that will fail loudly on layout change; curl_cffi fallback under AmzPy; CCC summary
  as the always-on degrade; everything labeled best-effort.
- **Turnstile dependency:** Keepa history needs a real, Turnstile-passing browser session.
  Acceptable — it's the `vox-browser` tier; degrade to CCC when unavailable.
