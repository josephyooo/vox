# vox-maps Skill + Orchestrator Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-built `maps-cli` into Vox — a new stateless `vox-maps` skill (the primary places source), plus orchestrator + `vox-browser` edits that make place data `vox-maps`-first with Chrome as the logistics + fallback path.

**Architecture:** This is subsystem 2 of the gosom Maps tier (subsystem 1, the `maps-cli` repo, is built + gate-green + on PATH). It touches ONLY the vox repo. A new `skills/vox-maps/` skill calls `maps-cli places --json` per finalist and returns the standard Vox digest; it is stateless (runs in Wave 1, in parallel, owns no shared resource). The orchestrator (`skills/vox/SKILL.md`) gains place-data→`vox-maps` routing and a generalized "places tier" availability gate (available if **gosom OR Chrome**). `vox-browser` keeps logistics/transit and becomes the place-data fallback. The routing contract is locked in by a deterministic regression test plus an eval golden.

**Tech Stack:** Markdown skills (Claude Code), Python 3.14 + pytest + ruff for the repo gate, the `tools/validate_skills.py` validator, the `eval/` golden harness. No new runtime dependencies — `maps-cli` already exists on PATH.

**Subsystem boundary:** Subsystem 1 (`/Users/joseph/projects/maps-cli`) is DONE — do not modify it. This plan modifies only `/Users/joseph/projects/vox`.

**Spec:** `/Users/joseph/projects/vox/docs/superpowers/specs/2026-06-07-vox-maps-gosom-tier-design.md` (§6 vox-maps skill, §7 orchestrator + vox-browser edits, §9 testing).

**Gate (run from `/Users/joseph/projects/vox`):**
```
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```
Expected: pytest all pass; ruff "All checks passed!"; validator prints `[ok]` for every skill (no `[FAIL]`).

---

## File Structure

```
vox/
  skills/
    vox-maps/                         # NEW — the stateless places source
      SKILL.md                        # bootstrap (maps-cli doctor) + per-finalist loop + digest
      references/
        places-playbook.md            # maps-cli call/contract/confidence/exit-code details
    vox/SKILL.md                      # MODIFY — routing step 2 + step 0 probe + Places-tier gate
    vox-browser/SKILL.md              # MODIFY — place-data is vox-maps-first; Chrome = logistics + fallback
    vox-browser/references/maps-playbook.md  # MODIFY — header note: logistics + place-data fallback
  eval/goldens/maps-places.md         # NEW — places-tier routing golden
  tests/test_routing.py               # NEW — deterministic routing-contract regression test
  tests/test_capabilities.py          # MODIFY — add a maps-cli capability probe
  install.sh                          # UNCHANGED — generic loop already picks up skills/vox-maps/
```

---

### Task 1: The `vox-maps` stateless skill (SKILL.md + places-playbook.md)

**Files:**
- Create: `/Users/joseph/projects/vox/skills/vox-maps/references/places-playbook.md`
- Create: `/Users/joseph/projects/vox/skills/vox-maps/SKILL.md`
- Modify: `/Users/joseph/projects/vox/tests/test_capabilities.py`

- [ ] **Step 1: Create the skill directory and the places playbook**

```bash
mkdir -p /Users/joseph/projects/vox/skills/vox-maps/references
```

`/Users/joseph/projects/vox/skills/vox-maps/references/places-playbook.md`:
```markdown
# Places playbook (Google Maps via maps-cli / gosom)

Answer place sub-questions by shelling out to `maps-cli` (a local wrapper around the native
gosom/google-maps-scraper). No Chrome, no API key. Never average scores; disclose missing data.

## Call
- One finalist per call: `maps-cli --json places "<name>" --near "<neighborhood or city>"`.
- Query LOOSELY — `name + neighborhood`, never a full street address. gosom is a SEARCH tool: an exact
  address resolves to a single place page with no results list and fails. Pass the locality you already
  know from the candidate's context, e.g. `--near "Park Slope Brooklyn"`.
- `--json` emits ONE NDJSON object on stdout. Parse it; never screenshot.

## Output contract (per call)
`{ name, rating, reviewCount, address, hours, priceBand?, category, mapsUrl, lat, lng,
   confidence: "high"|"low", alternatives: [{name, rating, reviewCount, address, mapsUrl}],
   source: "google-maps/gosom" }`
- **Goodness = rating × review-VOLUME**, not raw stars (a 4.4 × 1,207 beats a thin 4.9). Report BOTH.
- `mapsUrl` is the canonical `/maps/place/…` link — cite it on every row.
- `hours` is gosom's per-day `open_hours` map; pass it through, don't infer "open now".

## Confidence & disambiguation
- `confidence: "high"` → the matched row clearly is the requested place. Mark the row `✅ verified`
  (gosom figures are real Maps data, same standing as the browser tier's verified reads).
- `confidence: "low"` → the match is weak, or two same-name places competed (e.g. "Ubani Midtown" vs
  "Ubani - West Village"). DISCLOSE it: present the pick with `⚠️` and surface `alternatives` so the
  orchestrator can disambiguate. Never assert a low-confidence pick as fact.
- `name: null` (no confident match) → report "no confident Maps match" and list `alternatives`. This is
  NOT the same as a tool failure.

## Missing volume (important)
- A row can come back with `reviewCount` of `0` or `null` even when the place has reviews — gosom's
  list-card extraction is incomplete under some Google DOM variants. Treat `0`/`null` reviewCount as
  **volume-UNAVAILABLE → flag `⚠️`**, never as "0 reviews". If volume is the deciding figure and it
  came back empty, say so and let the orchestrator escalate THAT figure to `vox-browser`.

## Exit codes → what to do
- `0` → a record was printed (it may be a `confidence:"low"` / null match — still success).
- `3` **blocked/empty** (anti-bot / scrollHeight after one retry) → report THIS finalist as a per-item
  gap (the digest `Status` stays `ok` for the others) so the orchestrator escalates this place to
  `vox-browser`.
- `4` **environment** (gosom binary / Chromium missing) → the whole tier has no capability; the SKILL
  bootstrap handles this (return `no-capability`).
- `2` usage / `1` other → report as a failure row; never fabricate a place to fill the gap.

## Return rows
Per finalist: `name · rating × reviewCount · priceBand(~) · address · hours · mapsUrl`, a confidence
mark, and `alternatives` when ambiguous. Flag single-source picks. Logistics / transit detours are NOT
this tier — the orchestrator routes those to `vox-browser`.
```

- [ ] **Step 2: Create the SKILL.md**

`/Users/joseph/projects/vox/skills/vox-maps/SKILL.md`:
```markdown
---
name: vox-maps
description: Vox places subagent. Use when dispatched by the vox orchestrator to answer place / rating × review-volume / address / hours sub-questions via maps-cli (the native gosom Google-Maps scraper) — no Chrome, no API key. Stateless and parallel-safe. Returns the Vox digest.
---

# vox-maps

You are the Vox places subagent. Answer the place sub-questions the orchestrator queued — rating ×
review-VOLUME, address, hours — by calling `maps-cli` (a local wrapper around the native gosom
Google-Maps scraper). No Chrome, no API key. You are STATELESS: you hold no shared resource, so the
orchestrator may run you in Wave 1 alongside the other stateless sources and you may process multiple
finalists concurrently. Return the [digest contract](../vox/references/digest-contract.md). Never
fabricate.

## Bootstrap (capability probe FIRST)
Run `maps-cli doctor`.
- Exit `0` → the gosom binary + Chromium are present; proceed.
- Exit `4` (or `maps-cli` is not on PATH) → STOP and return a digest with **Status: no-capability**
  naming the place sub-questions you could not answer. Do NOT fabricate. The orchestrator escalates
  those to `vox-browser` (or halts if Chrome is also down).

## Loop
Follow [places-playbook](references/places-playbook.md) for the call details and the output contract.
1. For each finalist `(name, locality)`: `maps-cli --json places "<name>" --near "<locality>"`.
2. Parse the NDJSON record. Build a digest row: `name · rating × reviewCount · priceBand(~) · address ·
   hours · mapsUrl`. gosom figures are real Maps data → mark `✅ verified`.
3. `confidence:"low"` or `name:null` → present with `⚠️` and surface `alternatives`; disclose, never
   assert. `reviewCount` of 0/null → flag volume-UNAVAILABLE (`⚠️`), NOT "0 reviews".
4. A finalist that exits `3` (blocked) is a per-ITEM gap — report it so the orchestrator escalates THAT
   place to `vox-browser`; the rest of the digest stays valid.

## Scope
Place DATA only (rating × volume, address, hours). **Logistics / transit detours are NOT this tier** —
gosom has no directions; the orchestrator routes those to `vox-browser`.

## Return
The digest contract, led by a one-line capability status. Maps figures marked `✅` verified; ambiguous
picks `⚠️` with `alternatives`. Status: `ok` | `no-signal` | `no-capability`. Empty → no-signal. Never
fabricate.
```

- [ ] **Step 3: Run the skill validator — expect `vox-maps` ok and every other skill still ok**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python tools/validate_skills.py skills
```
Expected: a line `[ok] vox-maps` and `[ok]` for every other skill, no `[FAIL]`, exit 0. (The validator
checks the frontmatter `name: vox-maps` matches the directory, that `description` is non-empty, and that
both local links in SKILL.md resolve — `references/places-playbook.md` and
`../vox/references/digest-contract.md`.)

- [ ] **Step 4: Add a `maps-cli` capability probe to the test suite**

Modify `/Users/joseph/projects/vox/tests/test_capabilities.py` — add this function at the END of the
file (it mirrors the existing `reddit-cli` / `bird` probes and is skipped if `maps-cli` is absent):
```python


@pytest.mark.skipif(shutil.which("maps-cli") is None, reason="maps-cli not installed")
def test_maps_cli_has_places_and_doctor():
    out = _help("maps-cli")
    assert "places" in out and "doctor" in out
```

- [ ] **Step 5: Run the new test + the full suite**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_capabilities.py::test_maps_cli_has_places_and_doctor -q
```
Expected: `1 passed` (maps-cli is on PATH at `~/.local/bin/maps-cli` and its `--help` lists both
`places` and `doctor`).

Run the whole suite + ruff to confirm nothing regressed:
```bash
.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check tools tests eval
```
Expected: all tests pass; ruff "All checks passed!".

- [ ] **Step 6: Commit**

```bash
cd /Users/joseph/projects/vox
git add skills/vox-maps tests/test_capabilities.py
git commit -q -m "feat(vox-maps): stateless places skill calling maps-cli + capability probe

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Eval golden for the places (vox-maps) routing

**Files:**
- Create: `/Users/joseph/projects/vox/eval/goldens/maps-places.md`

- [ ] **Step 1: Write the golden**

`/Users/joseph/projects/vox/eval/goldens/maps-places.md`:
```markdown
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
```

- [ ] **Step 2: Run the goldens test to confirm the new golden is well-formed**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_goldens.py -q
```
Expected: PASS. `test_each_golden_has_required_sections` confirms the new file has `## Query`,
`## Family`, and `## Expectations`; `test_goldens_exist` still holds (now 6 goldens).

- [ ] **Step 3: Commit**

```bash
cd /Users/joseph/projects/vox
git add eval/goldens/maps-places.md
git commit -q -m "test(eval): vox-maps places-tier routing golden

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Routing-contract regression test + orchestrator edits

**Files:**
- Create: `/Users/joseph/projects/vox/tests/test_routing.py`
- Modify: `/Users/joseph/projects/vox/skills/vox/SKILL.md`

- [ ] **Step 1: Write the failing routing test**

`/Users/joseph/projects/vox/tests/test_routing.py`:
```python
# tests/test_routing.py
"""Deterministic guard on the place/logistics routing contract in the skill prose.

These assertions key on stable concept words (not exact sentences) so reasonable rewording
survives, but a silent DROP of the vox-maps-first routing or the gosom-or-chrome gate fails.
"""
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
ORCH = (SKILLS / "vox" / "SKILL.md").read_text()
MAPS = (SKILLS / "vox-maps" / "SKILL.md").read_text()


def test_vox_maps_skill_exists_and_is_stateless():
    assert (SKILLS / "vox-maps" / "SKILL.md").exists()
    assert (SKILLS / "vox-maps" / "references" / "places-playbook.md").exists()
    assert "stateless" in MAPS.lower()
    assert "maps-cli doctor" in MAPS  # capability probe


def test_orchestrator_routes_place_data_to_vox_maps():
    assert "vox-maps" in ORCH
    assert "places tier" in ORCH.lower()


def test_orchestrator_gate_is_gosom_or_chrome():
    lower = ORCH.lower()
    assert "maps-cli doctor" in ORCH  # gosom probe wired into the gate
    assert "gosom" in lower and "chrome" in lower
    assert "both" in lower  # halt only if BOTH gosom and Chrome are unavailable


def test_logistics_stays_on_browser():
    assert "logistics" in ORCH.lower()
    assert "vox-browser" in ORCH
```

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py -q
```
Expected: FAIL — `test_orchestrator_routes_place_data_to_vox_maps` and
`test_orchestrator_gate_is_gosom_or_chrome` fail because `vox/SKILL.md` does not yet mention `vox-maps`,
a "places tier", or `maps-cli doctor`. (`test_vox_maps_skill_exists_and_is_stateless` already passes
from Task 1.)

- [ ] **Step 3: Edit the orchestrator — step 0 capability probe**

In `/Users/joseph/projects/vox/skills/vox/SKILL.md`, replace this exact block:
```text
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`; for the browser tier
   `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`). If an HTTP source is
   missing, DECLARE which sub-questions lose coverage and proceed with a confidence penalty — never
   fake a missing source. The browser tier has a stricter rule: see the **Browser tier** section below.
```
with:
```text
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`; for the places tier `maps-cli doctor`; for the browser
   tier `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`). If an HTTP source
   is missing, DECLARE which sub-questions lose coverage and proceed with a confidence penalty — never
   fake a missing source. The places/browser tier has a stricter rule: see the **Places & browser
   tier** section below.
```

- [ ] **Step 4: Edit the orchestrator — routing (step 2)**

Replace this exact substring (inside step 2):
```text
**places /
   ratings × review-volume / hours / transit-logistics → the browser tier (Maps); general-search
   gaps + bot-blocked-but-important reads → the browser tier (Google)**. Mark which sub-questions
   NEED the browser tier (drives the Browser-tier gate below).
```
with:
```text
**place data
   (rating × review-volume / hours / address) → the places tier (`vox-maps`, primary, parallel);
   logistics / transit detours / "detour with a stop" → the browser tier (`vox-browser`, Maps
   directions); general-search gaps + bot-blocked-but-important reads → the browser tier (Google)**.
   Mark which sub-questions NEED the places tier or browser tier (drives the Places-tier gate below).
```

- [ ] **Step 5: Edit the orchestrator — Wave 1 dispatch (step 3)**

Replace this exact substring (end of the step-3 browser paragraph):
```text
(see **Browser tier**). Never run
   more than one browser agent.
```
with:
```text
(see **Places & browser tier**). Never run
   more than one browser agent.
   When PLACE-DATA sub-questions are NEEDED and the places tier is available (`maps-cli doctor` ok),
   dispatch `vox-maps` in Wave 1 as a STATELESS source (like the HTTP three — it owns no shared
   resource, so it runs in parallel and may process multiple finalists concurrently); it loads
   `vox-maps`/SKILL.md and calls `maps-cli places`. Dispatch it as `subagent_type: general-purpose`
   (it is a SKILL, not an agent type). Any place sub-question it returns `no-capability` or blocked
   (exit 3) for → escalate THAT sub-question to the single `vox-browser` agent.
```

- [ ] **Step 6: Edit the orchestrator — generalize the gate heading + triggers**

Replace this exact block:
```text
## Browser tier (single serial owner; halt-by-default)
The browser is a SINGLE shared resource — exactly one `vox-browser` agent, ever; never parallel,
never a second concurrent one. There are TWO triggers for browser work:
- **(a) Places/logistics** — known at routing (step 2). Dispatch the one browser agent in Wave 1,
  concurrent with the stateless three.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser` in its digest's "sources that failed" block. After Wave 1, collect those tags
  and have the SAME single browser agent read them in a brief follow-up pass.
```
with:
```text
## Places & browser tier (places-first via gosom; browser = logistics + fallback; halt-by-default)
Place DATA (rating × review-volume / hours / address) is served by the **places tier**, available if
**`vox-maps` (gosom — `maps-cli doctor` exits 0) OR Chrome** is available. The browser is still a
SINGLE shared resource — exactly one `vox-browser` agent, ever; never parallel — and it now owns
**logistics/transit** and serves as the **place-data fallback**. There are THREE triggers for browser
work:
- **(a-data) Place data `vox-maps` could not serve** — a finalist it returned `no-capability` or
  blocked (exit 3) for. Escalate that sub-question to the one `vox-browser` agent.
- **(a-logistics) Logistics / transit detours** — known at routing (step 2); gosom has no directions,
  so these always go to `vox-browser`. Dispatch the one browser agent in Wave 1 when logistics is
  needed.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser` in its digest's "sources that failed" block. After Wave 1, the SAME single
  browser agent reads them in a brief follow-up pass.
```

- [ ] **Step 7: Edit the orchestrator — generalize the availability gate**

Replace this exact block:
```text
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
```
with:
```text
Availability gate (keyed off the routing-time PLACE / LOGISTICS need):
- **Place data needed + `vox-maps` available (`maps-cli doctor` ok)** → dispatch `vox-maps` in Wave 1
  (stateless, parallel). Escalate ONLY the finalists it returns `no-capability`/blocked for to the one
  `vox-browser` agent (when Chrome is up).
- **Place data needed + `vox-maps` UNavailable (exit 4) + Chrome available** → `vox-browser` serves the
  place data (its Maps playbook), as the fallback.
- **Logistics needed** → always `vox-browser` (one agent, Wave 1), independent of gosom.
- **Not needed** → ignore both tiers; run the HTTP tier as normal.
- **Place / logistics needed + BOTH gosom and Chrome UNavailable, default** → **HALT-AND-REPORT.** Do
  NOT silently produce a web-only answer. State which sub-questions depend on the places/browser tier,
  that neither gosom nor Chrome is available, and the two ways forward: (a) pair Chrome / install gosom
  and re-ask, or (b) re-run with `--web-fallback`.
- **… + `--web-fallback`** (literal flag OR natural language like "proceed web-only if neither's up")
  → fall those sub-questions back to `vox-web`; mark every figure that lost places/browser
  corroboration with a LOWER-confidence mark + a one-line "no places/browser coverage" note.
A late `needs-browser` escalation (trigger b) that can't be served because Chrome is unavailable is
NOT a hard halt — `vox-web` already disclosed the gap; note it and move on. A `vox-maps` or
`vox-browser` agent that returns no usable digest (orphaned/dead) counts as UNavailable for its
sub-questions.
```

- [ ] **Step 8: Run the routing test + the validator to verify the edits**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py -q
```
Expected: PASS (4 passed) — `vox-maps`, "places tier", `maps-cli doctor`, "gosom"+"chrome", "both", and
"logistics" all now appear in `vox/SKILL.md`.

Run the validator (the orchestrator edits add no new local links, so it must stay green):
```bash
.venv/bin/python tools/validate_skills.py skills
```
Expected: `[ok]` for every skill, exit 0.

- [ ] **Step 9: Commit**

```bash
cd /Users/joseph/projects/vox
git add tests/test_routing.py skills/vox/SKILL.md
git commit -q -m "feat(vox): route place data to vox-maps; generalize gate to gosom-OR-chrome

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: vox-browser edits (place-data is vox-maps-first; Chrome = logistics + fallback) + full gate + live install

**Files:**
- Modify: `/Users/joseph/projects/vox/tests/test_routing.py`
- Modify: `/Users/joseph/projects/vox/skills/vox-browser/SKILL.md`
- Modify: `/Users/joseph/projects/vox/skills/vox-browser/references/maps-playbook.md`

- [ ] **Step 1: Append the failing browser-fallback assertion**

Add this function at the END of `/Users/joseph/projects/vox/tests/test_routing.py`:
```python


def test_browser_is_place_data_fallback():
    browser = (SKILLS / "vox-browser" / "SKILL.md").read_text()
    assert "fallback" in browser.lower()
    assert "vox-maps" in browser  # place data is vox-maps-first
```

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py::test_browser_is_place_data_fallback -q
```
Expected: FAIL — `vox-browser/SKILL.md` does not yet mention `vox-maps` or a place-data "fallback".

- [ ] **Step 3: Edit the vox-browser SKILL.md description**

Replace this exact line (the frontmatter `description:`):
```text
description: Vox browser subagent. Use when dispatched by the vox orchestrator to answer places/logistics (Google Maps) or bot-blocked/Google-search sub-questions by driving the user's real Chrome via the claude-in-chrome MCP. The single serial owner of the browser for a run. Returns the Vox digest.
```
with:
```text
description: Vox browser subagent. Use when dispatched by the vox orchestrator for LOGISTICS/transit directions (Google Maps) and as the PLACE-DATA FALLBACK when vox-maps (gosom) cannot serve a finalist, plus bot-blocked/Google-search reads — by driving the user's real Chrome via the claude-in-chrome MCP. The single serial owner of the browser for a run. Place data is normally served first by vox-maps. Returns the Vox digest.
```

- [ ] **Step 4: Edit the vox-browser SKILL.md intro paragraph**

Replace this exact block:
```text
You are the Vox browser subagent — the SOLE owner of the user's Chrome for this run. You answer the
browser sub-questions the orchestrator queued (places/logistics via Maps; Google search + reading
bot-blocked pages) and return the [digest contract](../vox/references/digest-contract.md). Never
fabricate. You are SERIAL: one navigation at a time, one sub-question at a time.
```
with:
```text
You are the Vox browser subagent — the SOLE owner of the user's Chrome for this run. You answer the
browser sub-questions the orchestrator queued: **logistics/transit directions via Maps**, the
**place-data FALLBACK** for finalists `vox-maps` (the gosom places tier) could not serve, and Google
search + reading bot-blocked pages. Return the [digest contract](../vox/references/digest-contract.md).
Never fabricate. You are SERIAL: one navigation at a time, one sub-question at a time. (Place DATA —
rating × review-volume / hours / address — is normally served first by `vox-maps` without Chrome; you
handle the finalists it flags blocked/no-capability, plus all logistics.)
```

- [ ] **Step 5: Edit the vox-browser maps-playbook.md header**

Replace this exact block:
```text
# Maps playbook (Google Maps via Chrome)

Answer places/logistics by driving Maps with direct-URL navigation. Never average scores; disclose
estimates.
```
with:
```text
# Maps playbook (Google Maps via Chrome)

> **Place data is `vox-maps`-first.** The rating × review-VOLUME / hours / address backbone is normally
> served by the `vox-maps` skill (native gosom, no Chrome). This playbook now serves **logistics/transit
> directions** and the **place-data FALLBACK** when `vox-maps` flags a finalist blocked/no-capability.

Answer places/logistics by driving Maps with direct-URL navigation. Never average scores; disclose
estimates.
```

- [ ] **Step 6: Run the browser test + the FULL gate**

Run the new assertion:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py -q
```
Expected: PASS (5 passed).

Run the full repo gate:
```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```
Expected: pytest all pass; ruff "All checks passed!"; validator prints `[ok]` for every skill including
`vox-maps`, no `[FAIL]`.

- [ ] **Step 7: Live install + capability smoke (manual, not a gated test)**

```bash
cd /Users/joseph/projects/vox && ./install.sh
ls -l ~/.claude/skills/vox-maps
maps-cli doctor; echo "doctor exit: $?"
```
Expected: `install.sh` prints `linked vox-maps -> …/.claude/skills/vox-maps` (the generic loop picks up
the new skill — no install.sh edit needed); the symlink resolves to `skills/vox-maps`; `maps-cli doctor`
exits 0. (A live `maps-cli places` lookup is gosom-availability-dependent: an exit 3 under a transient
anti-bot block is the CORRECT fallback signal, not a defect — the orchestrator escalates to
`vox-browser`.)

- [ ] **Step 8: Commit**

```bash
cd /Users/joseph/projects/vox
git add tests/test_routing.py skills/vox-browser/SKILL.md skills/vox-browser/references/maps-playbook.md
git commit -q -m "feat(vox-browser): place data is vox-maps-first; Chrome = logistics + fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criterion

The vox repo gate is green (`pytest` all pass, `ruff check tools tests eval` clean, `validate_skills.py
skills` all `[ok]`), `vox-maps` is symlinked into `~/.claude/skills` and calls the on-PATH `maps-cli`,
the orchestrator routes place data to `vox-maps` first with a gosom-OR-Chrome availability gate, and
`vox-browser` is the logistics + place-data fallback. The remaining validation is a manual,
capability-gated eval rigor run of the `maps-places` golden (per `eval/run-eval.md`), analogous to the
browser-tier rigor — out of scope for this plan's automated gate.
