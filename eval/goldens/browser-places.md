## Query
best ramen near Union Square under $20 within a short transit detour

## Family
places / food

## Expectations
- Routes place data (rating × review-volume, `$` band, address) to `vox-maps`, and the transit detour
  (logistics) to the one `vox-browser` agent; corroborates with vox-web / Reddit where possible.
- Ranked venue table: rating × review-count, `$` band marked band-vs-verified, address, and a derived
  two-leg transit detour (origin→place + place→dest − baseline).
- $20 ceiling enforced; over-budget venues flagged with their exact value, not dropped.
- Every pick cited with a canonical Maps/destination URL; no fabricated ratings or prices.
- If Chrome is NOT paired: HALTS-AND-REPORTS by default even when gosom is up (gosom has no
  directions), naming the detour sub-question and the missing Chrome (plus the place-data
  sub-questions if gosom is down too); with `--web-fallback`, degrades those sub-questions to web
  with explicit lower-confidence marks. Never fabricates places.
