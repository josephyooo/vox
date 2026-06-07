# vox-maps — gosom-backed Google Maps place-data tier (design)

**Status:** approved 2026-06-07. Adds a subscription-native, no-paid-API, no-credit-card source for
Google Maps **place data** (rating × review-volume + address + hours) that does NOT require driving the
user's Chrome. Complements — does not replace — the existing `vox-browser` tier.

## 1. Purpose
Vox ranks places by **rating × review-VOLUME** (the field that separates a thin 4.9 from a corroborated
4.4). Today the only source for that figure is `vox-browser` driving the user's real Chrome through the
`claude-in-chrome` MCP (it commandeers the browser, is a single serial owner, and halts the run when
Chrome can't connect). This design adds a second, independent place-data source backed by
[`gosom/google-maps-scraper`](https://github.com/gosom/google-maps-scraper) (MIT, self-hosted) wrapped in
a small tested CLI (`maps-cli`), exposed to the orchestrator as a new stateless `vox-maps` skill. It runs
headless, needs no Chrome and no API key, and produces the same Maps figures the browser tier produces.

## 2. Goals / non-goals
**Goals**
- A `maps-cli places "<name>" --near "<area>"` command that returns a normalized place record
  (rating, review-count, address, hours, maps URL) for a named finalist, with a tested fallback-signalling
  contract (exit codes), backed by gosom run **natively** (arm64 binary, no Docker).
- A stateless `vox-maps` skill that the orchestrator routes place/ratings/hours/address sub-questions to
  FIRST, in parallel (not bound by the single-serial-Chrome-owner rule).
- Orchestrator + `vox-browser` wiring so the places tier is available if **gosom OR Chrome** is available;
  `vox-browser` keeps **logistics/directions** (gosom can't do transit) and serves as the place-data
  **fallback**.
- Keep both repos' gates green; the new repo ships with faithful test doubles (the documented gosom
  failure modes are MODELED, so the path is actually covered).

**Non-goals (separate backlog items)**
- **Review-text sentiment** from gosom (it returns review bodies; deferred — v1 is the rating/volume/
  address/hours backbone only).
- **Logistics/transit detours** — stay on `vox-browser` (gosom has no directions).
- **Private/own data** — N/A; this is public Google Maps.
- A Docker run-mode — rejected on measurement (see §3); native arm64 is the v1 backend. (A Docker
  fallback is a possible future add, not v1.)

## 3. Discovery context (what the 2026-06-07 benchmark established)
All measured on the user's Apple-Silicon Mac against the live-rigor finalists:

- **Data is exact.** gosom returned the rigor's Maps figures field-for-field: Luigi's 4.6×2487,
  The Munchies 4.7×1291, Ubani Midtown 4.9×1168, Peter Luger 4.4×15845, Maru 4.5×218, with full weekly
  `open_hours` and addresses. It is a faithful substitute for the browser scrape on the field that matters.
- **gosom is a SEARCH tool, not a lookup tool.** An exact `name + full address` query resolves to a single
  *place* page with no scrollable results list → gosom errors with
  `playwright: TypeError: Cannot read properties of null (reading 'scrollHeight')` and returns nothing.
  A `name + neighborhood` query returns a *list* with the target on top → works. So vox-maps MUST query
  loosely and **match the intended finalist by name**, and disambiguate locations (the "Ubani Midtown"
  query also surfaced "Ubani - West Village"; broad queries surface adjacent rows like Scarpetta/Cuna).
- **Native arm64 beats emulated Docker decisively.** The published image is `linux/amd64` only (no arm64
  build; no prebuilt release binaries — gosom ships via Docker + source). Under Rosetta the ephemeral
  container ran ~18s scrape + ~15–20s launch ≈ 30–40s/batch AND **hung after completion** (had to
  `docker stop` despite `--rm` + `-exit-on-inactivity`). Built natively (`go install …@latest`, 65 MB
  arm64 binary), a warm run did 5 lookups in **~8s scrape (~23s wall incl. a 15s inactivity wait), 0
  failures, 0 scrollHeight, and exited cleanly (no hang)**. The web-server mode was slower and fiddlier
  (no concurrency param → low default concurrency; empty `status` field → not cleanly pollable; jobs
  serialize on one browser). **Decision: native arm64 binary, ephemeral per-batch, `-c 4`.**
- **Cold `scrollHeight` is intermittent.** It appeared on cold/first runs (container exact-address; native
  first run during Chromium download) and vanished warm. Treat as a **transient → retry once**.
- **gosom CLI emits JSON** with `-json`; fields seen: `title`, `review_rating`, `review_count`, `address`,
  `complete_address`, `open_hours`, `popular_times`, `link` (canonical `/maps/place/…` URL), `cid`,
  `categories`/`category`, `latitude`/`longitude`. (The web-server `/download` is CSV; not used in v1.)
- **One-time setup, already done:** Go 1.26.4 (brew), `go install github.com/gosom/google-maps-scraper@latest`
  → `~/go/bin/google-maps-scraper`, and playwright-go's pinned Chromium build v1200 downloaded to
  `~/Library/Caches/ms-playwright/chromium-1200` on first run.

## 4. Architecture
Three units with clean boundaries:

1. **`maps-cli`** (new repo) — the only thing that knows how to run gosom and normalize/match its output.
2. **`vox-maps`** (new skill, vox repo) — a stateless subagent that calls `maps-cli` and returns the Vox
   digest; knows nothing about gosom internals.
3. **Orchestrator + `vox-browser`** (vox repo edits) — routing + availability gate so vox-maps is the
   primary places source and `vox-browser` becomes logistics + fallback.

Data flow: orchestrator → (Wave 1, parallel) `vox-maps` per finalist → `maps-cli places` → gosom native
→ normalized record → digest rows. Blocked/unavailable place sub-questions escalate to `vox-browser`.

## 5. Component 1 — `maps-cli` (new repo)
**Stack:** Python + Typer, mirroring `tiktok-cli` (same `--json` discipline, same gate:
`pytest --cov` / `ruff check` / `ruff format --check` / `mypy`). Repo name: `maps-cli`
(command `maps-cli`); installed on PATH like `tiktok-cli`.

### 5.1 Commands
- **`maps-cli places "<name>" --near "<area>" [-n 5] [--timeout 90] [--json]`** — look up one named place.
  Runs gosom on the query `"<name> <area>"`, matches the intended finalist among the returned list, and
  prints the matched record (table by default; one NDJSON object with `--json`).
- **`maps-cli doctor`** — capability probe: native binary present + executable? Chromium cache present?
  optional 1-query smoke. Prints a clear ok/missing report; exit 0 if usable, exit 4 if not. This is what
  `vox-maps` calls at bootstrap.

(Batch input — a finalists file — is a thin future convenience; v1 is one place per invocation, which the
skill loops/parallelizes.)

### 5.2 The gosom runner (the tested seam)
A single module function, e.g. `run_gosom(query, *, depth=1, concurrency=4, timeout=90) -> list[dict]`:
- Writes `query` to a temp input file; runs
  `~/go/bin/google-maps-scraper -input <tmp> -results <tmp_out> -json -depth 1 -c 4` (binary path
  resolved from `$MAPS_CLI_GOSOM_BIN` env or the default `~/go/bin/google-maps-scraper`).
- Enforces a **hard wall-clock timeout** (kills the process group on expiry — never relies on gosom
  self-exit). Detects completion by process exit OR output-file stability.
- Parses JSON lines from the results file into raw dicts.
- **Retries once** on a transient failure (zero results + a `scrollHeight`/empty signal in stderr).
- Raises typed errors mapped to exit codes (below). This function is the unit-test boundary; tests inject
  a **fake gosom** (a tiny script / monkeypatched runner) emitting canned JSON or the failure signals.

### 5.3 Matching (gosom is a search, the caller wants a lookup)
`select_match(results, requested_name) -> (best | None, alternatives, confidence)`:
- Normalize titles (casefold, strip punctuation); score each result by token overlap with
  `requested_name`; require a minimum overlap to count as a match.
- Tie-break by `review_count` (prominence). Return the best match, the other candidates as
  `alternatives`, and a **confidence** flag: `high` (clear title match) / `low` (weak/ambiguous — e.g.
  the top row's title doesn't contain the requested tokens, or two strong same-name candidates differ by
  area). Low-confidence and multi-candidate cases keep `alternatives` so `vox-maps` can disambiguate.

### 5.4 Normalized output contract
Per matched place (JSON):
```
{ "name", "rating", "reviewCount", "address", "hours",
  "priceBand"?, "category", "mapsUrl", "lat", "lng",
  "confidence": "high"|"low", "alternatives": [ {name, rating, reviewCount, address, mapsUrl}, … ],
  "source": "google-maps/gosom" }
```
`mapsUrl` is gosom's canonical `link`. `hours` is gosom's `open_hours` map (per-day strings).

### 5.5 Exit codes (mirror tiktok-cli's `classify_exception`)
- `0` ok (a match found).
- `2` usage error (bad args).
- `3` **blocked/empty** after the retry (scrollHeight/anti-bot/no results) → orchestrator escalates to
  `vox-browser`.
- `4` **environment** — native binary or Chromium missing/not executable → escalate to `vox-browser`.
- `1` other unexpected error.

A successful run that finds **no confident match** still exits `0` but emits `confidence:"low"` /
empty match with `alternatives` — "found nothing solid" is not the same as "tool failed."

## 6. Component 2 — `vox-maps` skill (vox repo)
`skills/vox-maps/SKILL.md` + `skills/vox-maps/references/places-playbook.md`.
- **Bootstrap:** run `maps-cli doctor`. If unusable (exit 4), return a digest `Status: no-capability`
  naming the place sub-questions it can't answer (orchestrator escalates to `vox-browser`). Never fabricate.
- **Stateless & parallel:** unlike `vox-browser` (single serial Chrome owner), `vox-maps` holds no shared
  resource — the orchestrator may dispatch it in Wave 1 alongside the other stateless sources, and it may
  process multiple finalists concurrently.
- **Loop:** for each finalist (name + locality), `maps-cli places "<name>" --near "<area>" --json`;
  build digest rows: `name · rating × review-count · address · hours · mapsUrl`. gosom figures are real
  Maps data → mark **✅ verified** (same standing as the browser tier's verified reads); flag
  single-source picks and `confidence:"low"` matches; surface `alternatives` when ambiguous.
- **Return:** the standard 7-section [digest contract]; `Status: ok | no-signal | no-capability`. A blocked
  place (exit 3) for a specific finalist is reported as a per-item gap, not a whole-tier failure.

## 7. Component 3 — orchestrator + `vox-browser` edits (vox repo)
- **Routing (vox `SKILL.md` step 2):** places / ratings × volume / hours / address → **`vox-maps`**
  (primary, Wave 1, parallel). **Logistics / transit detours / "detour with a stop"** → **`vox-browser`**
  (Chrome; unchanged — gosom has no directions). Bot-blocked Google reads → `vox-browser`.
- **Availability gate (vox `SKILL.md` Browser-tier section, generalized to a "places tier"):** the places
  tier is available if **gosom (`maps-cli doctor` ok) OR Chrome** is available.
  - Try `vox-maps` first. Any place sub-question it returns `no-capability`/blocked for → **escalate that
    sub-question to `vox-browser`** (the existing single serial owner).
  - **Halt-by-default only if BOTH gosom and Chrome are unavailable** (the existing `--web-fallback`
    degrades those sub-questions to `vox-web` with a lowered-confidence mark).
- **`vox-browser`:** `maps-playbook.md` stays for **logistics** and as the **place-data fallback**; its
  SKILL description gains a note that place data is now normally served by `vox-maps` and Chrome is the
  fallback/logistics path.
- **`vox-video`:** its corroboration step MAY call `maps-cli places` directly for rating × volume (no
  Chrome) — noted as a beneficiary; the concrete wiring can be a follow-up.

## 8. Error handling & fallback (summary)
- **Transient `scrollHeight`/empty** → `maps-cli` retries once; still empty → exit 3 → escalate to
  `vox-browser`.
- **Hang** → not expected natively (clean exit measured), but the runner's hard timeout + process-group
  kill guarantee termination regardless.
- **Binary/Chromium missing** → exit 4 → `vox-maps` reports `no-capability` → escalate; halt only if Chrome
  is also down.
- **Ambiguous/low-confidence match** → returned with `alternatives`; `vox-maps` discloses rather than
  guessing.
- **Never fabricate**; "no confident match" and "blocked" are distinct and both disclosed.

## 9. Testing
**`maps-cli` repo (the standard gate):**
- **Faithful fake gosom:** a test double that, given a query, emits canned JSON lines OR an injected
  failure (scrollHeight-then-success on retry, persistent-empty, timeout/hang, missing-binary). Models the
  REAL contract so the runner/retry/timeout paths are covered (the lesson from the tiktok-cli fakes).
- **Unit tests:** `run_gosom` (success, single-page parse, retry-on-scrollHeight, persistent-empty→exit3,
  timeout→kill, missing-binary→exit4); `select_match` (exact, fuzzy, low-confidence flag, Midtown-vs-West-
  Village disambiguation, adjacent-noise rejection); normalization (gosom JSON → contract, `open_hours`
  passthrough, `link`→`mapsUrl`); exit-code classification; `doctor` (ok / missing-binary / missing-chromium).
- Gate: `pytest --cov` / `ruff check` / `ruff format --check` / `mypy`, all green.

**vox repo:**
- `vox-maps` eval golden (a places query) + the repo's skill validator `[ok]`; install via `install.sh`.
- An orchestrator routing assertion that a places query dispatches `vox-maps` (not `vox-browser`) when
  gosom is available, and escalates to `vox-browser` when it isn't.

## 10. Files created / changed
**New repo `maps-cli`:** Typer app (`places`, `doctor`), gosom runner, matcher, normalizer, exit-code
classifier; `tests/` with the faithful fake + unit suites; packaging + README; gate config.
**vox repo:**
- `skills/vox-maps/SKILL.md` + `references/places-playbook.md` (new).
- `skills/vox/SKILL.md` — routing + generalized places-tier availability gate.
- `skills/vox-browser/SKILL.md` + `references/maps-playbook.md` — note place-data is now `vox-maps`-first;
  Chrome = logistics + fallback.
- `eval/` — vox-maps golden + routing assertion; `install.sh` symlink for `vox-maps`.

## 11. Risks
- **Google DOM / anti-bot drift breaks gosom** → mitigated by gosom's active release cadence
  (`go install @latest` to update) and the `vox-browser` fallback when gosom returns nothing.
- **Native footprint** — a Go toolchain + 65 MB binary + pinned Chromium live on the host (no container
  sandbox). Acceptable on the user's machine; `doctor` makes the dependency explicit and the fallback keeps
  the tier degradable. (A Docker run-mode remains a possible future add for portability.)
- **Matching picks the wrong same-name place** → mitigated by the confidence flag + returned
  `alternatives`; `vox-maps` discloses ambiguity instead of asserting.
- **Blocking at volume** — irrelevant at 5–20 finalists/query from one IP; if batched heavily, gosom's
  built-in proxy support is the lever (out of scope for v1).
