# Vox Phase 2 — Browser Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subscription-native browser source tier to Vox — one serial `vox-browser` subagent that drives the user's real Chrome via the `claude-in-chrome` MCP to answer places/logistics (Maps) and bot-blocked/Google-search sub-questions the stateless HTTP sources can't.

**Architecture:** A new `vox-browser` skill (browser-control mechanics + maps & google playbooks) is dispatched as exactly ONE serial subagent, concurrent with the existing parallel `vox-reddit`/`vox-x`/`vox-web` agents. The `vox` orchestrator gains capability-probing, routing, a single-browser Wave-1 dispatch, and a halt-by-default gate (`--web-fallback` to proceed web-only). The browser becomes the top rung of `vox-web`'s anti-bot ladder. All v1 contracts (digest, output template, validator, harness) are reused unchanged.

**Tech Stack:** Markdown skills; the `claude-in-chrome` MCP (deferred tools); existing Python dev tooling (pytest/ruff, validator, eval harness) — unchanged except one capability smoke.

**Reference docs (read before starting):**
- Spec: `docs/superpowers/specs/2026-06-07-vox-phase2-browser-tier-design.md`
- Mined recipe (browser mechanics): `docs/vox-recipe.md` §2.3–2.4, §6
- v1 plan (patterns to follow): `docs/superpowers/plans/2026-06-07-vox.md`

---

## File structure (what each file owns)

**New (runtime skills):**
- `skills/vox-browser/SKILL.md` — the serial browser-agent: bootstrap/probe, pairing, browser-control mechanics, serial work loop, digest return.
- `skills/vox-browser/references/maps-playbook.md` — Google Maps places/logistics playbook (recipe §2.4).
- `skills/vox-browser/references/google-playbook.md` — Google search + bot-blocked-page reads.

**New (eval):**
- `eval/goldens/browser-places.md` — capability-gated places golden (run manually with Chrome paired).

**Edited:**
- `skills/vox/SKILL.md` — capability-probe (add Chrome), routing rows, Wave-1 browser dispatch, the Browser-tier halt/`--web-fallback` gate.
- `skills/vox-web/references/antibot-ladder.md` — browser top rung (`needs-browser` handoff).
- `tests/test_capabilities.py` — `claude-in-chrome` capability smoke.
- `eval/run-eval.md` — manual browser-tier rigor section.

**Unchanged (reused):** `tools/validate_skills.py`, `eval/harness.py`, `eval/judge-rubric.md`, `install.sh` (globs `skills/*` → picks up `vox-browser` automatically), the v1 digest/output/rubric references.

---

## Task 1: `claude-in-chrome` capability smoke

The browser tier is capability-gated and can't pair Chrome headlessly, so this only **documents the probe**: if the `claude` CLI lists a chrome MCP server, assert it; otherwise skip. It mirrors the v1 `reddit-cli`/`bird` smokes (pass-or-skip, never hard-fail on environment).

**Files:**
- Modify: `tests/test_capabilities.py`

- [ ] **Step 1: Append the smoke** to `tests/test_capabilities.py`

```python


def test_claude_in_chrome_capability_probe_documented():
    """Capability smoke for the Phase 2 browser tier.

    We can't pair Chrome in a headless test, so this DOCUMENTS the probe: if the `claude`
    CLI is present and lists a chrome MCP server, assert it; otherwise skip (the tier is
    capability-gated). Never hard-fails on environment.
    """
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not installed")
    try:
        out = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=30
        )
    except (subprocess.TimeoutExpired, OSError):
        pytest.skip("`claude mcp list` not runnable here")
    listing = (out.stdout + out.stderr).lower()
    if "chrome" not in listing:
        pytest.skip("claude-in-chrome MCP not configured in this environment")
    assert "chrome" in listing
```

- [ ] **Step 2: Run it (documents the surface; must not error)**

Run: `cd ~/projects/vox && .venv/bin/python -m pytest tests/test_capabilities.py -q`
Expected: all pass or skip — no failures, no collection errors. (The new test passes if a chrome MCP is configured, otherwise skips.)

- [ ] **Step 3: Lint**

Run: `cd ~/projects/vox && .venv/bin/python -m ruff check tools tests eval`
Expected: "All checks passed!"

- [ ] **Step 4: Commit**

```bash
cd ~/projects/vox && git add -A
git commit -m "test: claude-in-chrome capability smoke for browser tier"
```

---

## Task 2: `vox-browser` skill + maps playbook

Creates the serial browser-agent skill and the Maps playbook. The SKILL.md links only `maps-playbook.md` and the v1 `digest-contract.md` for now; the google playbook link is added in Task 4 (so the validator stays green between tasks). Frontmatter `name` MUST equal `vox-browser`.

**Files:**
- Create: `skills/vox-browser/SKILL.md`
- Create: `skills/vox-browser/references/maps-playbook.md`

- [ ] **Step 1: Write `skills/vox-browser/SKILL.md`**

```markdown
---
name: vox-browser
description: Vox browser subagent. Use when dispatched by the vox orchestrator to answer places/logistics (Google Maps) or bot-blocked/Google-search sub-questions by driving the user's real Chrome via the claude-in-chrome MCP. The single serial owner of the browser for a run. Returns the Vox digest.
---

# vox-browser

You are the Vox browser subagent — the SOLE owner of the user's Chrome for this run. You answer the
browser sub-questions the orchestrator queued (places/logistics via Maps; Google search + reading
bot-blocked pages) and return the [digest contract](../vox/references/digest-contract.md). Never
fabricate. You are SERIAL: one navigation at a time, one sub-question at a time.

## Bootstrap (capability probe FIRST)
1. `ToolSearch(select:mcp__claude-in-chrome__…)` — these tools are deferred; pull them by exact MCP
   name (a generic keyword search returns nothing). Then `list_connected_browsers`.
2. If no browser is connectable, STOP and return a digest with **Status: no-capability** naming the
   sub-questions you could not answer. Do NOT fabricate or guess. (The orchestrator decides whether
   to halt or web-fall-back.)

## Pair once
`list_connected_browsers` → `AskUserQuestion` (which browser) → `select_browser(deviceId)` →
`tabs_context_mcp(createIfEmpty:true)`. Lead your digest with `paired: <browser>, N tabs`.

## Browser-control mechanics (use for every sub-question)
- **Navigate by direct URL**, never UI typing. Build the URL, navigate, read.
- **`get_page_text` over screenshots** for lists — parses text/rating/price cleanly, no OCR.
- **Split `browser_batch` around render waits**: `navigate → wait → get_page_text` (a text grab
  bundled with navigate fires before the page renders).
- **Recovery ladder** when a click/ref is wrong (panels are flaky): `read_page(filter:'interactive')`
  → grab the canonical `/maps/place/…` (or destination) URL → navigate directly.

## Serial work loop
Process queued sub-questions in order. For places/logistics, follow
[maps-playbook](references/maps-playbook.md). Finish one sub-question's navigation before starting
the next — never leave the browser mid-navigation.

## Return
The digest contract, led by the `paired:` (or `no-capability`) line. Maps figures MUST mark
band-vs-verified. Status: `ok` | `no-signal` | `no-capability`. Empty → no-signal. Never fabricate.
```

- [ ] **Step 2: Write `skills/vox-browser/references/maps-playbook.md`** (recipe §2.4)

```markdown
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
```

- [ ] **Step 3: Validate the skill structurally**

Run: `cd ~/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok] vox-browser` (its links to `references/maps-playbook.md` and `../vox/references/digest-contract.md` resolve). The four v1 skills stay `[ok]`. Exit 0.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/vox && git add -A
git commit -m "feat: vox-browser skill + maps playbook"
```

---

## Task 3: Orchestrator integration + halt/`--web-fallback` gate

Edit `skills/vox/SKILL.md` to probe Chrome, route browser sub-questions, dispatch the one serial browser agent in Wave 1, and add the Browser-tier gate. Four exact edits.

**Files:**
- Modify: `skills/vox/SKILL.md`

- [ ] **Step 1: Add the Chrome probe to step 0.** Replace:

```markdown
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`). If one is missing, DECLARE which sub-questions lose
   coverage and proceed with a confidence penalty — never fake a missing source.
```

with:

```markdown
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`; for the browser tier
   `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`). If an HTTP source is
   missing, DECLARE which sub-questions lose coverage and proceed with a confidence penalty — never
   fake a missing source. The browser tier has a stricter rule: see the **Browser tier** section below.
```

- [ ] **Step 2: Add browser routing to step 2.** Replace:

```markdown
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch.
```

with:

```markdown
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch; **places /
   ratings × review-volume / hours / transit-logistics → the browser tier (Maps); general-search
   gaps + bot-blocked-but-important reads → the browser tier (Google)**. Mark which sub-questions
   NEED the browser tier (drives the Browser-tier gate below).
```

- [ ] **Step 3: Add the single browser dispatch to step 3.** Replace:

```markdown
   `~/.claude/skills/vox-<source>/SKILL.md`). Work non-overlapping tasks while they run; do NOT read
   their transcript files — rely on the returned digest.
```

with:

```markdown
   `~/.claude/skills/vox-<source>/SKILL.md`). Work non-overlapping tasks while they run; do NOT read
   their transcript files — rely on the returned digest. When a PLACES/LOGISTICS sub-question is
   NEEDED and the browser tier is available, ALSO dispatch exactly ONE `vox-browser` agent in this
   wave (it loads `vox-browser`/SKILL.md, owns Chrome, works its queued sub-questions SERIALLY),
   concurrent with the stateless three. Bot-blocked reads discovered by `vox-web` during this wave
   are handled by the SAME single agent in a post-Wave-1 follow-up (see **Browser tier**). Never run
   more than one browser agent.
```

- [ ] **Step 4: Add the Browser-tier gate section.** Replace:

```markdown
## Hard rules
Cite every claim with a URL. 2+ sources to promote. Never retry a 403/429 (the web subagent
pivots). When data is missing, say so and show the blocked/failed sources. One honest pick, not a
forced winner.
```

with:

```markdown
## Browser tier (single serial owner; halt-by-default)
The browser is a SINGLE shared resource — exactly one `vox-browser` agent, ever; never parallel,
never a second concurrent one. There are TWO triggers for browser work:
- **(a) Places/logistics** — known at routing (step 2). Dispatch the one browser agent in Wave 1,
  concurrent with the stateless three.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser` in its digest's "sources that failed" block. After Wave 1, collect those tags
  and have the SAME single browser agent read them in a brief follow-up pass.

Availability gate (keyed off the routing-time need, i.e. trigger (a)):
- **Needed + available** → dispatch the one browser agent (Wave 1 for places; follow-up for queued
  `needs-browser` URLs).
- **Not needed** → ignore the browser entirely; run the HTTP tier as normal (no halt regardless of
  Chrome).
- **Needed + UNavailable (Chrome can't connect), default** → **HALT-AND-REPORT.** Do NOT silently
  produce a web-only answer. State which sub-questions/criteria depend on the browser, that Chrome
  isn't connected, and the two ways forward: (a) pair Chrome and re-ask, or (b) re-run with
  `--web-fallback`.
- **Needed + UNavailable + `--web-fallback`** (literal flag OR natural language like "proceed
  web-only if Chrome's down") → fall the browser sub-questions back to `vox-web`; mark every figure
  that lost browser corroboration with a LOWER-confidence mark + a one-line "no browser coverage" note.
A late `needs-browser` escalation (trigger b) that can't be served because Chrome is unavailable is
NOT a hard halt — `vox-web` already disclosed the gap; note it and move on. A `vox-browser` agent
that returns no usable digest (orphaned/dead) counts as UNavailable for its sub-questions.

## Hard rules
Cite every claim with a URL. 2+ sources to promote. Never retry a 403/429 (the web subagent
pivots). When data is missing, say so and show the blocked/failed sources. One honest pick, not a
forced winner.
```

- [ ] **Step 5: Validate + confirm the flag landed**

Run: `cd ~/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: all five skills `[ok]` (`vox`, `vox-reddit`, `vox-x`, `vox-web`, `vox-browser`), exit 0.

Run: `cd ~/projects/vox && grep -c -- '--web-fallback' skills/vox/SKILL.md`
Expected: `2` (the flag appears in the gate's two bullets).

- [ ] **Step 6: Commit**

```bash
cd ~/projects/vox && git add -A
git commit -m "feat: orchestrator browser-tier routing + halt/--web-fallback gate"
```

---

## Task 4: Google playbook + anti-bot browser top rung

Adds the Google playbook (search + blocked-site reads), wires its link into the browser skill, and makes the real browser the final rung of `vox-web`'s anti-bot ladder.

**Files:**
- Create: `skills/vox-browser/references/google-playbook.md`
- Modify: `skills/vox-browser/SKILL.md`
- Modify: `skills/vox-web/references/antibot-ladder.md`

- [ ] **Step 1: Write `skills/vox-browser/references/google-playbook.md`**

```markdown
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
```

- [ ] **Step 2: Wire the google playbook into the serial work loop.** In `skills/vox-browser/SKILL.md`, replace:

```markdown
## Serial work loop
Process queued sub-questions in order. For places/logistics, follow
[maps-playbook](references/maps-playbook.md). Finish one sub-question's navigation before starting
the next — never leave the browser mid-navigation.
```

with:

```markdown
## Serial work loop
Process queued sub-questions in order. For places/logistics, follow
[maps-playbook](references/maps-playbook.md); for Google search and bot-blocked reads, follow
[google-playbook](references/google-playbook.md). Finish one sub-question's navigation before
starting the next — never leave the browser mid-navigation.
```

- [ ] **Step 3: Add the browser rung to the anti-bot ladder.** In `skills/vox-web/references/antibot-ladder.md`, replace:

```markdown
5. If all fail: report the gap in the digest's "sources that failed" block. Never fabricate.
```

with:

```markdown
5. **Browser rung (escalate, don't drive):** you are a STATELESS agent — you cannot drive the shared
   browser. If the page is important, record its URL in the digest's "sources that failed" block
   tagged `needs-browser`. The orchestrator queues it for the single `vox-browser` agent (a real
   Chrome session loads most blocked pages).
6. If even the browser can't get it: report the gap in "sources that failed". Never fabricate.
```

- [ ] **Step 4: Validate**

Run: `cd ~/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: all five skills `[ok]` (the new `references/google-playbook.md` link in `vox-browser` resolves), exit 0.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/vox && git add -A
git commit -m "feat: google playbook + browser top rung of vox-web anti-bot ladder"
```

---

## Task 5: Browser golden + run-eval doc + full gate

Adds the capability-gated golden (so it parses under the existing golden test), documents the manual browser rigor step, reinstalls, and runs the full gate.

**Files:**
- Create: `eval/goldens/browser-places.md`
- Modify: `eval/run-eval.md`

- [ ] **Step 1: Write `eval/goldens/browser-places.md`** (must have `## Query`/`## Family`/`## Expectations` so `tests/test_goldens.py` parses it)

```markdown
## Query
best ramen near Union Square under $20 within a short transit detour

## Family
places / food

## Expectations
- Routes to the browser tier (Maps) for rating × review-volume, `$` band, and the transit detour;
  corroborates with vox-web / Reddit where possible.
- Ranked venue table: rating × review-count, `$` band marked band-vs-verified, address, and a derived
  two-leg transit detour (origin→place + place→dest − baseline).
- $20 ceiling enforced; over-budget venues flagged with their exact value, not dropped.
- Every pick cited with a canonical Maps/destination URL; no fabricated ratings or prices.
- If Chrome is NOT paired: HALTS by default (states the dependency, does not fabricate places); with
  `--web-fallback`, degrades to web with explicit lower-confidence marks.
```

- [ ] **Step 2: Verify the goldens still parse**

Run: `cd ~/projects/vox && .venv/bin/python -m pytest tests/test_goldens.py -q`
Expected: PASS (2 passed) — `test_goldens_exist` now sees 4 goldens, `test_each_golden_has_required_sections` validates the new one.

- [ ] **Step 3: Add the manual browser-rigor section to `eval/run-eval.md`** (append at end)

```markdown

## Browser-tier rigor (manual, capability-gated)

The browser tier needs a paired Chrome, which the headless rigor workflow can't do — so grade it
manually:
1. Install + pair: `./install.sh`, open Chrome, confirm the `claude-in-chrome` MCP can connect.
2. In an interactive Claude session run `/vox best ramen near Union Square under $20 within a short
   transit detour` (the `eval/goldens/browser-places.md` query). Capture to
   `eval/runs/browser-places.md`.
3. Grade with the SAME layers: `structural_checks` must print `[]`; dispatch the judge with
   `eval/judge-rubric.md` + the query + the output; `VERDICT` must be `pass`.
4. Sanity-check the HALT path: with Chrome NOT connected, the same query must STOP and report (not
   fabricate); re-running with `--web-fallback` must degrade with explicit lower-confidence marks.
```

- [ ] **Step 4: Reinstall (picks up `vox-browser`)**

Run: `cd ~/projects/vox && ./install.sh`
Expected: `linked vox`, `vox-reddit`, `vox-x`, `vox-web`, and `vox-browser` (5 links; existing ones replaced cleanly).

- [ ] **Step 5: Full gate**

```bash
cd ~/projects/vox
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```
Expected: all tests pass (capability smokes may SKIP — reddit passes, bird/chrome may skip; nothing FAILS); ruff clean; validator exits 0 with all five `[ok]`.

- [ ] **Step 6: Commit**

```bash
cd ~/projects/vox && git add -A
git commit -m "feat: browser-places golden + manual browser-rigor doc; install vox-browser"
```

---

## Task 6: Manual browser-tier rigor (interactive — run with the user)

This is the behavioral verification for the browser tier. It CANNOT be automated (it pairs a live Chrome and exercises the LLM judge), so it follows `eval/run-eval.md`'s "Browser-tier rigor" section and is run interactively. An automated executor builds Tasks 1–5; a human (with the user) runs this.

**Files:**
- Modify (as needed): `skills/vox-browser/SKILL.md`, `skills/vox-browser/references/*`, `skills/vox/SKILL.md`

- [ ] **Step 1: Pair Chrome**

Open Chrome; confirm the `claude-in-chrome` MCP connects (`list_connected_browsers` returns a device). If it can't, the rest of this task is the HALT-path check only (Step 4).

- [ ] **Step 2: Run the places golden**

Invoke `/vox best ramen near Union Square under $20 within a short transit detour`. Capture output to `eval/runs/browser-places.md`. Expected: pairs Chrome, drives Maps, returns a ranked venue table with rating × review-volume, band-vs-verified `$`, a two-leg transit detour, every pick cited, $20 ceiling enforced.

- [ ] **Step 3: Grade it**

```bash
cd ~/projects/vox
.venv/bin/python -c "from eval.harness import structural_checks; print(structural_checks(open('eval/runs/browser-places.md').read()))"
```
Expected: `[]`. Then dispatch a judge subagent with `eval/judge-rubric.md` + the query + the output; `VERDICT` must be `pass`. Iterate on `skills/vox-browser/*` (or the orchestrator routing) until routing, citation, corroboration, and the band-vs-verified disclosure are correct.

- [ ] **Step 4: Verify the halt path (Chrome disconnected)**

With Chrome NOT connected, invoke the same query. Expected: Vox HALTS and reports the browser dependency + the two options — it does NOT fabricate places. Then invoke `/vox best ramen near Union Square under $20 within a short transit detour --web-fallback`. Expected: it degrades to web with explicit lower-confidence marks on the browser-derived figures.

- [ ] **Step 5: Final commit** (if any skills were edited while iterating)

```bash
cd ~/projects/vox && git add -A
git commit -m "test: vox-browser passes the manual browser golden (rigor)"
```

---

## Notes for the implementer
- The skills are PROMPTS; their "correctness" is proven by Task 6's manual eval, not unit tests. v1's YAGNI rule holds — Phase 2 ships ZERO new runtime code (only one capability smoke).
- The `claude-in-chrome` tools are deferred MCP tools — they MUST be pulled by exact name via `ToolSearch(select:mcp__claude-in-chrome__…)`; generic keyword search returns nothing. This is why the browser-agent's bootstrap step is non-negotiable.
- Keep the single-browser invariant: the orchestrator dispatches AT MOST ONE `vox-browser` agent, and no stateless agent ever drives the browser (it escalates via the `needs-browser` tag instead).
- DRY: maps/google specifics live in the playbook references; the SKILL.md holds only the shared browser-control mechanics and the serial loop.
