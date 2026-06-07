# Maps playbook (Google Maps via Chrome)

Answer places/logistics by driving Maps with direct-URL navigation. Never average scores; disclose
estimates.

## Navigate
- Search: `/maps/search/<url-encoded query>/@lat,lng,zoom` → rows like
  `Name 4.5(7,129) · $20-30 · cuisine · address`.
- Directions: `/maps/dir/?api=1&origin=<…>&destination=<…>&travelmode=transit`.

## Score & price
- **Goodness = rating × review-VOLUME**, not raw stars (a 4.4 with 1,207 reviews beats a thin 4.9).
- **`$` bands are coarse per-person ESTIMATES, not menu prices.** Use for triage only; for finalists
  replace with a verified read and **disclose band-vs-verified** (mark band figures `~`). A `$1–10`
  band once hid a real `$4.36/slice`; a "5.0 best slice" was a personal-pizza shop with no slices.

## Logistics
- Maps **cannot compute multi-stop transit.** Derive "detour with a stop" as **two sequential transit
  legs (origin→place, place→destination) minus a measured baseline** (origin→destination). Out-and-back
  walking overstates it.
- Menu photo is a low-res thumbnail → **abandon OCR; report the live menu URL** so the orchestrator
  can hand it to a `vox-web` fetch.

## Return rows
Per venue: name, rating × review-count, `$` band (marked `~`/band), address, and any derived detour.
Cite the canonical `/maps/place/…` URL. Flag single-source picks.
