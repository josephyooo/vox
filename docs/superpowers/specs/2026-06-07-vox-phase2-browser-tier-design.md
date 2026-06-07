# Vox Phase 2 — Browser Tier Design

**Status:** Approved design (brainstorming output). Successor to the v1 spec
(`2026-06-07-vox-design.md`) and grounded in the mined recipe (`docs/vox-recipe.md`, §2.3–2.4, §6).

**One-line goal:** Add a subscription-native **browser source tier** to Vox — a single serial
`vox-browser` subagent that drives the user's real Chrome via the `claude-in-chrome` MCP to answer
**places/logistics** (Google Maps) and **general-search / bot-blocked-site** (Google) sub-questions
that the stateless HTTP sources (`vox-web`) cannot.

---

## 1. Purpose & context

Vox v1 ships three stateless, parallel HTTP source subagents (`vox-reddit`, `vox-x`, `vox-web`) that
the `vox` orchestrator fans out, corroborates (2+ sources to promote), ranks, and renders into a
fixed, cited, honestly-hedged deliverable. v1 deliberately excluded anything requiring a browser.

Two classes of sub-question are still unreachable:

1. **Places & logistics** — map ratings weighted by review-volume, `$`-per-person bands, opening
   hours, and transit/walking detours. These live in Google Maps, which is JS-heavy and not usefully
   fetchable; the mined recipe answered them by driving **Claude-in-Chrome** (§2.3–2.4).
2. **Bot-blocked / JS-shell pages** — sites that 403, 429, or return a JS shell past even the Jina
   rung of `vox-web`'s anti-bot ladder. A real, logged-in Chrome session loads these where headless
   HTTP cannot, and gives access to **Google search** results (complementing `vox-web`'s Brave).

Phase 2 adds exactly these, as one coherent tier.

## 2. Goals / non-goals

**Goals**
- A `vox-browser` skill that drives Chrome to answer maps and google sub-questions and returns the
  **existing v1 digest contract** (no new envelope).
- Orchestrator integration that respects the **single-shared-browser** constraint: the browser tier
  runs as **one serial subagent**, concurrent with the parallel HTTP agents.
- Make the real browser the **top rung of the anti-bot ladder**, reached via the orchestrator.
- **Halt-by-default** when a needed browser tier is unavailable; opt-in `--degrade` to proceed
  web-only with a confidence penalty.
- Capability-gated rigor: a smoke test + one **manually-run** browser golden graded by the existing
  harness + judge.

**Non-goals (explicitly out; each a later spec)**
- Any **parallel / multi-browser** scheme — impossible under the one-tab constraint.
- **TikTok / Instagram** video sources (zero mined evidence; capability-spike first).
- The `vox "…"` **`csd` shell wrapper** (separate project).
- Changing the v1 HTTP tier's behavior beyond the orchestrator routing edits and the one new
  anti-bot rung in `vox-web`.

## 3. Key decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Scope | **One spec, both playbooks** (maps + google); build maps-first | They share one browser-control machinery; designing it twice is waste. Maps has the densest mined evidence. |
| D2 | Browser owner | **One serial `vox-browser` subagent** (not orchestrator-driven) | Keeps the orchestrator uniform ("a subagent per source", just serialized) and isolates browser complexity behind the digest contract. (Diverges from the recipe's orchestrator-driven pattern — a deliberate, user-chosen trade.) |
| D3 | Browser mechanism | **`claude-in-chrome` MCP** (deferred tools) driving the user's real Chrome | The only browser path present (no Playwright/Chromium). Subscription-native, no API. Same surface the mined sessions used. |
| D4 | Unavailable-browser behavior | **Halt-and-report by default**; opt-in `--degrade` flag | The user wants a trustworthy answer over a silently-degraded one. Degrade stays available for convenience. |
| D5 | Degrade trigger scope | Halt only when a **browser-routed sub-question exists** | A pure-sentiment query that never needed the browser must run normally regardless of Chrome. |
| D6 | Eval | **Capability smoke** + one **manual capability-gated browser golden**; automated workflow stays text-tier | The headless rigor workflow can't pair Chrome; forcing browser eval into automation would only ever test the degraded path. |
| D7 | Digest/output | **Reuse v1 contracts unchanged** | The browser-agent returns the same digest; the deliverable template is unchanged. |

## 4. Architecture

```
vox orchestrator (vox/SKILL.md)
  step 0  capability-probe  ── now also probes claude-in-chrome
  step 2  route             ── routing table gains browser rows
  step 3  Wave 1 (concurrent):
            ├─ vox-reddit   (stateless, parallel)
            ├─ vox-x        (stateless, parallel)
            ├─ vox-web      (stateless, parallel)  ── reports blocked-but-important URLs
            └─ vox-browser  (ONE agent, internally SERIAL: maps → google)   ◀ new
  step 4  corroborate  ·  step 6 rank  ·  step 7 render   (unchanged shapes)
```

The browser-agent is **one** dispatched subagent. Internally it is serial: it pairs Chrome once,
then works its queued browser sub-questions in order (maps places/logistics first, then google
search + any blocked-URL reads handed down from the orchestrator). It returns one digest per the v1
contract (or `Status: no-capability` / `Status: halt-required`; see §7).

**Concurrency:** the three stateless agents and the one browser-agent are all launched in Wave 1
and run concurrently; the browser-agent's internal serialization is invisible to the orchestrator,
which simply awaits all four digests. No two agents ever touch the browser — only `vox-browser` does.

**Failure mode of D2 (named, not designed around twice):** because the browser is owned by a
subagent rather than the orchestrator, if that subagent's context is lost mid-run (death/compaction),
its paired Chrome session is orphaned. The orchestrator treats a `vox-browser` agent that returns no
usable digest as **no-capability for its sub-questions** and applies the §7 halt/degrade gate — never
a silent gap. This is the accepted cost of the cleaner "subagent per source" model (D2).

## 5. Components

### 5.1 `skills/vox-browser/SKILL.md` (new)
The serial browser-agent's playbook. Sections:
- **Bootstrap & capability probe** — `ToolSearch(select:mcp__claude-in-chrome__…)` (tools are
  deferred; generic keyword search returns nothing — pull by exact MCP name), then
  `list_connected_browsers`. If nothing is connectable → return the no-capability/halt envelope
  (§7), do **not** fabricate.
- **Pairing handshake** (once) — `list_connected_browsers` → `AskUserQuestion` (which browser) →
  `select_browser(deviceId)` → `tabs_context_mcp(createIfEmpty:true)`.
- **Browser-control mechanics** — see §6 (shared by both playbooks).
- **Serial work loop** — process the queued browser sub-questions in order; one digest section per
  sub-question; never leave the browser mid-navigation between sub-questions.
- **Return** — the v1 digest contract; lead with a capability/pairing line ("paired: <browser>,
  N tabs" or "no-capability").

### 5.2 `skills/vox-browser/references/maps-playbook.md` (new) — recipe §2.4
- Navigate by **direct URL**: `/maps/search/<url-encoded query>/@lat,lng,zoom` (returns
  `Name 4.5(7,129) · $20-30 · cuisine · address`) and `/maps/dir/?api=1&origin=…&destination=…&travelmode=transit`.
- **Goodness = rating × review-volume**, never raw stars (a 4.4 with 1,207 beats a thin 4.9).
- **`$` bands are coarse per-person estimates, NOT menu prices** — triage only; replace with a
  verified read for finalists and **disclose band-vs-verified**.
- Maps **cannot compute multi-stop transit** — derive "detour with a stop" as **two sequential
  transit legs (origin→place, place→destination) minus a measured baseline**.
- Menu photo is a low-res thumbnail → **abandon OCR, hand the live menu URL back** for a `vox-web`
  fetch (via the orchestrator).

### 5.3 `skills/vox-browser/references/google-playbook.md` (new)
- **Browser Google search** — navigate `https://www.google.com/search?q=<url-encoded>`; mine result
  titles/snippets like `vox-web` does with Brave, but as a complementary engine; `get_page_text`.
- **Blocked-site reads** — for URLs the orchestrator queued (403/429/JS-shell past Jina), navigate
  directly in the paired Chrome and `get_page_text`; a logged-in real browser loads most of them.
- **Hard rules** — public content only; never defeat auth/paywalls; cite the real destination URL,
  not the Google redirect; if a site still won't load, report it in "sources that failed".

### 5.4 Orchestrator edits — `skills/vox/SKILL.md`
- **Step 0 (capability-probe):** add Claude-in-Chrome detection; record whether the browser tier is
  available.
- **Step 2 (route):** add rows — *objective goodness/places/ratings/logistics* → **maps**;
  *search-coverage gaps + blocked-but-important reads* → **google**. Decide per sub-question whether
  the browser tier is **needed**.
- **Step 3 (Wave 1):** when a browser sub-question exists, dispatch **one** `vox-browser` agent
  alongside the stateless three. Pass it the queued browser sub-questions (and any blocked URLs from
  a prior `vox-web` pass, if available).
- **Unavailable-browser gate** (new; see §7): if a browser sub-question is needed and the probe says
  Chrome can't connect → **halt-and-report** unless `--degrade` is set.

### 5.5 Anti-bot top rung — `skills/vox-web/references/antibot-ladder.md` (edit)
Add a final rung after the Jina rung: *"If still blocked AND the page is important, do not fabricate
— record the URL in the digest's 'sources that failed' block tagged `needs-browser`. The orchestrator
will queue it for the `vox-browser` tier (a real Chrome session loads most blocked pages)."* The
stateless `vox-web` agent never drives the browser itself.

## 6. Browser-control mechanics (shared layer, recipe §2.3)

These live in `vox-browser/SKILL.md` and are used by both playbooks:
- **Navigate via direct URL, not UI typing.** Construct the URL, navigate, read.
- **`get_page_text` over screenshots** for result lists — parses rating/count/price/text cleanly,
  no OCR.
- **`browser_batch` with render-wait splits** — text grabs inside a batch fire *before* the page
  renders; split into `navigate → wait → get_page_text` rather than bundling the grab.
- **Recovery ladder** when a click/ref is wrong (panels are flaky): `read_page(filter:'interactive')`
  → grab the canonical `/maps/place/…` (or destination) URL → **navigate directly**.
- **One driver only** — this agent is the sole browser owner for the run; it never spawns a
  sub-subagent that also touches the browser.

## 7. Pairing & degradation

**Availability is decided at capability-probe (step 0), before any browser work.** Outcomes:

1. **Browser available + needed** → pair once (handshake, §5.1), run the serial work loop, return a
   normal digest.
2. **Browser NOT available + NOT needed** (no browser-routed sub-question) → ignore; the run proceeds
   on the HTTP tier exactly as v1. No halt.
3. **Browser NOT available + needed, default mode** → **HALT-AND-REPORT.** The orchestrator stops
   before dispatching browser work and tells the user: which sub-questions/criteria depend on the
   browser, that Chrome isn't connected, and the two ways forward — **(a) pair Chrome and retry**, or
   **(b) re-run with `--degrade`**. It does NOT silently produce a web-only answer.
4. **Browser NOT available + needed, `--degrade` set** → proceed **web-only**: the browser-routed
   sub-questions fall back to `vox-web`, and every figure that would have had browser corroboration
   carries an explicit **lower-confidence mark** plus a one-line note naming the missing coverage.

`--degrade` is recognised as a literal flag in the query **and** via natural language (e.g. "proceed
web-only if Chrome's down"). The flag only matters in outcome 3/4; it is a no-op otherwise.

**Headless contexts** (e.g. the automated rigor workflow) hit outcome 2 for the text goldens (no
browser route) and would hit outcome 3 for a browser golden — which is exactly why the browser golden
is run **manually** (§8).

## 8. Eval / rigor

- **Capability smoke** — `tests/test_capabilities.py` gains a check that the `claude-in-chrome` MCP
  surface is discoverable; **skips** when absent (like the `reddit-cli` / `bird` smokes). It asserts
  presence only — no pairing, no network.
- **Manual capability-gated browser golden** — `eval/goldens/browser-places.md`, e.g.
  *"best ramen near Union Square under $20 within a short transit detour"*. Family: places/food.
  Expectations: routes to maps; ranked venue table with rating×volume + `$` band (disclosed as
  band-vs-verified) + a derived two-leg transit detour; every pick cited; corroborated with `vox-web`
  /Reddit where possible; honest handling of any blocked menu. Run it **interactively with Chrome
  paired**, capture to `eval/runs/`, grade with the **same** `structural_checks` + judge. Documented
  in `eval/run-eval.md` as the browser rigor step (the interactive analog of v1 Task 12).
- **No automation change** — the 3 text goldens keep running in `eval/rigor-workflow.js` unchanged.
- **Validator** — `vox-browser/` is validated like any skill (frontmatter, name match, link
  resolution). `install.sh` globs `skills/*`, so it is symlinked automatically.

## 9. Digest & output (reuse)

The browser-agent returns the **v1 digest contract** unchanged, with:
- a leading **capability/pairing** line (paired browser + tab count, or `no-capability`);
- maps figures carrying the **band-vs-verified** distinction explicitly;
- a `Status:` of `ok` | `no-signal` | `no-capability` | `halt-required`.

The orchestrator renders the **v1 output template** unchanged. Under `--degrade`, missing-browser
coverage shows as per-figure lower-confidence marks in the ranked table and a line in the canonical
"Sources that failed / blocked" disclosure.

## 10. File structure (delta from v1)

**New**
- `skills/vox-browser/SKILL.md`
- `skills/vox-browser/references/maps-playbook.md`
- `skills/vox-browser/references/google-playbook.md`
- `eval/goldens/browser-places.md`

**Edited**
- `skills/vox/SKILL.md` — capability-probe, routing table, Wave-1 dispatch, the halt gate.
- `skills/vox-web/references/antibot-ladder.md` — browser top rung (`needs-browser` handoff).
- `tests/test_capabilities.py` — claude-in-chrome smoke.
- `eval/run-eval.md` — browser rigor step.

`install.sh`, `tools/validate_skills.py`, `eval/harness.py` need **no change**.

## 11. Scope, phases, provenance

- **Build order:** browser-control layer + `vox-browser` skeleton → maps playbook (+ smoke) →
  orchestrator integration + halt gate → google playbook + anti-bot top rung → eval (smoke + manual
  golden + run-eval doc).
- **Provenance:** maps mechanics and the goodness/band/transit rules are mined from real sessions
  (recipe §2.3–2.4, dense & consistent). The google playbook is a lighter extension of the same
  browser-control layer — flagged in the plan as the thinner-evidence piece, proven by the manual
  golden.
- **Deferred (later specs):** TikTok/Instagram video; `vox "…"` `csd` wrapper; any parallel-browser
  scheme.
