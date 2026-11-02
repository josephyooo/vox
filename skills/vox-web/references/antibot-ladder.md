# Anti-bot ladder

**Cardinal rule: never retry a 403/429 — pivot immediately.**

Block signatures: 403 (Yelp /biz/, DoorDash, Seamless, Toast, Michelin, many official sites);
429 terminal (corner.inc); JS-shell stubs ("Prepare your taste buds...", "Loading...", bare name)
on Grubhub/Seamless/Square/baemenu/"Order Now" apps. ECONNREFUSED = wrong domain (different fix
than 403).

Pivot order when blocked:
1. URL variant (trailing slash; alternate domain, e.g. `nan-xiang.com` vs `nanxiangxiaolongbao.com`).
2. Source pivot per the source ladder (Yelp→Tripadvisor/Restaurantji/Guru; official→aggregator).
3. **WebSearch titles/snippets** as the data.
4. **Jina rung (opt-in, flag it):** fetch `https://r.jina.ai/<original-url>` for clean plaintext
   past most 403/JS-shells. CAVEATS to state to the user: routes through a THIRD PARTY (Jina sees
   the fetch); free-tier reliability varies; foreign-IP-blocked sites may still fail. Use for
   public content only; do not use to defeat auth/paywalls.
5. **Archive rung (free), for 404/410/moved/gone pages:** WebFetch (or curl with a generic UA)
   `https://archive.org/wayback/available?url=<url>`; if `archived_snapshots.closest.url` exists,
   fetch that snapshot. Cite the snapshot URL actually read plus its date, and mark
   freshness-sensitive fields (hours, prices, open/closed) `~`.
6. **Firecrawl rung (last resort, METERED: may be billed to the user's card):** only for an
   IMPORTANT page, only after WebFetch failed or was bot-walled AND every free rung above (incl.
   archive) failed, and only if `ToolSearch(select:mcp__firecrawl__firecrawl_scrape)` finds it
   (absent → skip; never a halt). Call `firecrawl_scrape` with `formats:["markdown"]`,
   `onlyMainContent:true`, `proxy:"basic"` (never stealth/enhanced/auto). At most 2 calls per
   vox-web agent; report the count on the digest's Source & capability line. Caveats: a third
   party sees the fetch; public content only, never auth/paywalls; it may return a cached copy, so
   pass `maxAge:0` for freshness-sensitive fields.
7. **Browser rung (escalate, don't drive):** you are a STATELESS agent — you cannot drive the shared
   browser. If the page is important, record its URL in the digest's "sources that failed" block
   tagged `needs-browser`. The orchestrator queues it for the single `vox-browser` agent (a real
   Chrome session loads most blocked pages).
8. If even the browser can't get it: report the gap in "sources that failed". Never fabricate.
