# Places playbook (Google Maps via maps-cli / gosom)

Answer place sub-questions by shelling out to `maps-cli` (a local wrapper around the native
gosom/google-maps-scraper). No Chrome, no API key. Never average scores; disclose missing data.

## Call
- One finalist per call: `maps-cli --json places "<name>" --near "<neighborhood or city>" --search "<cuisine/category>"`.
- **Use `--search` for the broad query.** gosom is a SEARCH tool, not a lookup tool: an exact business
  NAME (like an exact address) resolves to a single Maps *place* page with no results list →
  `scrollHeight` → exit-3 anti-bot block. So pass a broad cuisine/category term (e.g. "soup dumplings",
  "ramen", "pizza") as `--search`; gosom searches `"<search> <near>"` (a scrollable list) while the
  matcher still finds your `<name>` in it with full rating × volume. The category comes from the query
  family. Omit `--search` only when no sensible category exists (it then falls back to `"<name> <near>"`,
  which may hit the block).
- Query the LOCALITY loosely — `name + neighborhood`, never a full street address. Pass the locality from
  the candidate's context, e.g. `--near "Park Slope Brooklyn"`.
- `--json` emits ONE NDJSON object on stdout. Parse it; never screenshot.

## Output contract (per call)
`{ name, rating, reviewCount, address, hours, priceBand?, category, mapsUrl, lat, lng,
   confidence: "high"|"low", alternatives: [{name, rating, reviewCount, address, mapsUrl}],
   source: "google-maps/gosom" }`
- **Goodness = rating × review-VOLUME**, not raw stars (a 4.4 × 1,207 beats a thin 4.9). Report BOTH.
- `mapsUrl` is the canonical `/maps/place/…` link — cite it on every row.
- `hours` is gosom's per-day `open_hours` map; pass it through, don't infer "open now".

## Confidence & disambiguation
- `confidence: "high"` → the matched row clearly is the requested place. Mark the row `✅ verified`
  (gosom figures are real Maps data, same standing as the browser tier's verified reads).
- `confidence: "low"` → the match is weak, or two same-name places competed (e.g. "Ubani Midtown" vs
  "Ubani - West Village"). DISCLOSE it: present the pick with `⚠️` and surface `alternatives` so the
  orchestrator can disambiguate. Never assert a low-confidence pick as fact.
- `name: null` (no confident match) → report "no confident Maps match" and list `alternatives`. This is
  NOT the same as a tool failure.

## Missing volume (important)
- A row can come back with `reviewCount` of `0` or `null` even when the place has reviews — gosom's
  list-card extraction is incomplete under some Google DOM variants. Treat `0`/`null` reviewCount as
  **volume-UNAVAILABLE → flag `⚠️`**, never as "0 reviews". If volume is the deciding figure and it
  came back empty, say so and let the orchestrator escalate THAT figure to `vox-browser`.

## Exit codes → what to do
- `0` → a record was printed (it may be a `confidence:"low"` / null match — still success).
- `3` **blocked/empty** (anti-bot / scrollHeight after one retry) → report THIS finalist as a per-item
  gap (the digest `Status` stays `ok` for the others) so the orchestrator escalates this place to
  `vox-browser`.
- `4` **environment** (gosom binary / Chromium missing) → the whole tier has no capability; the SKILL
  bootstrap handles this (return `no-capability`).
- `2` usage / `1` other → report as a failure row; never fabricate a place to fill the gap.

## Return rows
Per finalist: `name · rating × reviewCount · priceBand(~) · address · hours · mapsUrl`, a confidence
mark, and `alternatives` when ambiguous. Flag single-source picks. Logistics / transit detours are NOT
this tier — the orchestrator routes those to `vox-browser`.
