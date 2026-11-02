# vox-amazon — live-rigor validation (2026-06-21)

End-to-end check of the implemented `vox-amazon` source against live Amazon / CCC / Keepa.
Query exercised: *"is the Sony WH-1000XM5 (B09XS7JWHH) a good price right now, and its history?"*

## Results

| Component | Result | Notes |
|---|---|---|
| `amazon-cli doctor` | ✅ exit 0 | curl_cffi + amzpy + bs4 present |
| `amazon-cli search "Sony WH-1000XM5"` | ✅ HTTP 200, 16 products | ASIN + title + rating extracted; price + reviewCount came back `null` → flagged `⚠ unavailable` (never a silent 0) |
| `amazon-cli price B09XS7JWHH` (CCC) | ⚠️ `blocked` | CCC returns **HTTP 403 Cloudflare** ("Just a moment…") to a naked curl_cffi GET. Honest degrade fired — status `blocked`, empty types, no fabrication |
| Keepa history (vox-browser playbook) | ✅ | Captured a real WS payload in the live Chrome, `amazon-cli keepa-decode` → current **$278.00**, Amazon series 13 pts (2026-02-03 $298 → 2026-06-02 $278), low/avg/high **$248 / $280.77 / $398** |

## Verdict
The differentiated path — **search → ASIN → Keepa full daily history** — works end to end, and every
honesty contract held (unavailable ≠ 0; blocked is surfaced, not faked). The two HTTP *fallbacks* are
degraded live but the system degrades honestly and Keepa covers the gap:

## Findings (follow-ups, not v1 blockers)
1. **CCC Cloudflare-403 from naked curl_cffi.** The research's HTTP-200 came via Firecrawl's unblocker,
   not a bare request. The CCC summary rung as built does not work live from this IP.
   Options: (a) accept Keepa-only for current price (Keepa already returns current + history, so CCC is
   redundant when the browser tier is up); (b) route CCC through the Firecrawl MCP rung (key-gated, like
   vox-web's ladder); (c) route CCC through the browser tier. Recommend (a) for now, (b) if a no-browser
   summary is wanted.
2. **AmzPy search returns null price + reviewCount** (titles/ratings/ASINs are fine). Discovery works;
   current price/volume come from Keepa. Follow-up: extract price/review-count directly from the search
   HTML (the `_curl_search` BS4 path) or fix the AmzPy field mapping, so a browserless current-price is
   available even when Keepa/CCC are down.

## Unchanged-design conclusion
v1 ships as designed: Keepa (browser tier) is the price-intelligence source of truth; CCC + AmzPy-search
price are best-effort fallbacks that degrade honestly. Findings 1–2 are queued for a v2 follow-up.
