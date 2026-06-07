## Query
best dumplings in Flushing Queens

## Family
places / food

## Expectations
- Routes place data (rating × review-VOLUME, address, hours) to the PLACES tier `vox-maps` FIRST, in
  Wave 1, in parallel with the stateless sources — NOT to `vox-browser` — when `maps-cli doctor` is ok
  (gosom available).
- Ranked venue table: rating × review-count (VOLUME shown, not raw stars), address, hours, and a
  canonical `/maps/place/…` URL per row. No fabricated ratings or counts.
- A finalist that gosom blocks (exit 3) or returns with empty review-volume is flagged and escalated to
  `vox-browser` for that figure — a per-item gap, not a whole-tier failure.
- Low-confidence / same-name matches are disclosed with `⚠️` and `alternatives`, never asserted.
- Transit / detour logistics (if asked) stay on `vox-browser` — gosom has no directions.
- The places tier is available if gosom OR Chrome is available; HALTS by default only if BOTH are down
  (with `--web-fallback`, degrades to web with explicit lower-confidence marks).
