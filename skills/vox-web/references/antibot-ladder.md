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
5. **Firecrawl rung (opt-in, capability-gated — key required, no card):** ONLY if the Firecrawl MCP
   is configured — probe `ToolSearch(select:mcp__firecrawl__firecrawl_scrape)`; absent → skip to the
   browser rung (never a halt, same soft-gate posture as Jina). When present, call
   `mcp__firecrawl__firecrawl_scrape` on the blocked URL with `formats:["markdown"]`,
   `onlyMainContent:true`, and `proxy:"auto"` (auto-escalates to stealth residential proxies) — this
   clears most hard 403 / WAF / Cloudflare pages the Jina rung can't, WITHOUT driving the browser.
   CAVEATS to state to the user: routes through a THIRD PARTY (Firecrawl sees the fetch); free tier is
   ~1,000 credits/mo and stealth costs more credits per call, so reserve it for IMPORTANT finalist
   reads, not bulk; public content only — never to defeat auth/paywalls. FRESHNESS: Firecrawl may
   return a CACHED copy (`cacheState:hit`); for freshness-sensitive fields (permanently-closed,
   current hours/prices) pass a low `maxAge` (e.g. `maxAge:0`) to force a live fetch.
6. **Browser rung (escalate, don't drive):** you are a STATELESS agent — you cannot drive the shared
   browser. If the page is important, record its URL in the digest's "sources that failed" block
   tagged `needs-browser`. The orchestrator queues it for the single `vox-browser` agent (a real
   Chrome session loads most blocked pages).
7. If even the browser can't get it: report the gap in "sources that failed". Never fabricate.
