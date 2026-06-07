# Google playbook (search + blocked-site reads via Chrome)

The real Chrome session is the LAST rung of the anti-bot ladder. Use it for two jobs.

## 1. Google search (complements vox-web's Brave)
- Navigate `https://www.google.com/search?q=<url-encoded query>`; `get_page_text`.
- Mine result TITLES and SNIPPETS as first-class data; cite the real destination URL, never the
  Google redirect.

## 2. Read bot-blocked / JS-shell pages
- For each URL the orchestrator queued (tagged `needs-browser` — 403/429/JS-shell past Jina),
  navigate directly in the paired Chrome and `get_page_text`. A logged-in real browser loads most
  of them.
- If a page STILL won't load, record it in the digest's "sources that failed" block — do not fabricate.

## Hard rules
Public content only. Never defeat auth/paywalls; do not log in on the user's behalf. Cite real URLs.
