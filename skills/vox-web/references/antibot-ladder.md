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
5. If all fail: report the gap in the digest's "sources that failed" block. Never fabricate.
