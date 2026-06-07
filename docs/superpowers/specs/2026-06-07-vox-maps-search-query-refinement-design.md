# vox-maps `--search` query refinement (design)

**Status:** approved 2026-06-07. A small, two-repo refinement of the shipped gosom Maps tier, driven by
the `maps-places` eval-rigor finding.

## 1. Purpose
The shipped vox-maps tier looks up a finalist with `maps-cli places "<exact name>" --near "<locality>"`,
which builds the gosom search string `"<name> <locality>"`. The 2026-06-07 rigor established that a
**precise business name resolves to a single Google Maps *place* page** (no scrollable results list) →
gosom errors with `playwright: TypeError: Cannot read properties of null (reading 'scrollHeight')` and
returns nothing (exit 3). A **broad category term** (`"soup dumplings <locality>"`) returns a scrollable
*list* gosom handles cleanly, and the existing matcher then finds the named finalist in it **with full
rating × review-volume**. This refinement lets vox-maps drive gosom with a broad search term while still
matching the exact finalist — so a finalist's rating × review-volume is obtainable under the anti-bot
single-page block.

## 2. Goals / non-goals
**Goals**
- Add an optional broad-search term to `maps-cli places` so the gosom query is decoupled from the exact
  finalist name, while the matcher continues to key on that name.
- Update the `vox-maps` skill + playbook to pass the cuisine/category (from the orchestrator's brief) as
  that term, with the rationale documented.
- Keep both repos' gates green; backward-compatible (omitting the new option preserves today's behavior).

**Non-goals**
- **Auto-broaden-on-block** inside maps-cli (rejected during brainstorming — the category signal lives in
  the orchestrator's query, not derivable from a business name; an internal heuristic can't reliably
  surface a *specific* finalist).
- A separate discovery/list command (`maps-cli search "<category>"`) — deferred; not needed for the
  per-finalist lookup this fixes.
- Changing exit-code / retry / timeout semantics, the matcher's scoring, or the normalized contract.
- Any orchestrator (`vox/SKILL.md`) routing/gate change — vox-maps derives the category from its brief.

## 3. Component 1 — `maps-cli places` (`commands/places.py`)
Add an optional option `--search` (short `-q`), `str | None = None`:
- **When provided:** the gosom query becomes `f"{search} {near}"`; the matcher is still called with the
  positional `name`. Example: `places "Nan Xiang" --near "Flushing Queens" --search "soup dumplings"` →
  gosom searches `"soup dumplings Flushing Queens"` (a list) → matcher finds **Nan Xiang** with full
  data.
- **When omitted:** the gosom query is `f"{name} {near}"` — unchanged from today.
- Everything else is identical: `depth=1`, `timeout`, `-n` row cap, `select_match(...)`, `normalize_place`,
  the renderer, and the exit codes (`0` ok incl. `confidence:"low"`/null match · `3` blocked · `4` env ·
  `2` usage · `1` other). The ONLY change is which string is handed to `run_gosom`.

The query string used for gosom must be built in a way the unit test can observe (e.g. compute
`query = f"{search} {near}" if search else f"{name} {near}"` and pass it to `gosom.run_gosom`).

## 4. Component 2 — `vox-maps` skill (`SKILL.md` + `references/places-playbook.md`)
- **Loop change:** for each finalist `(name, locality)`, call
  `maps-cli --json places "<name>" --near "<locality>" --search "<cuisine/category>"`, where the
  category comes from the orchestrator's query family (e.g. "dumplings", "ramen", "pizza"). When no
  sensible category exists, fall back to the bare `places "<name>" --near "<locality>"` (current
  behavior).
- **Playbook rationale:** document that an exact-name query resolves to a single Maps place page (no list
  → `scrollHeight` → exit 3 anti-bot block), so `--search` drives gosom with a broad term that returns a
  list while the matcher keys on the exact name. A finalist still not found in the list → `name:null` /
  `confidence:low` → disclose + escalate (unchanged). All other rules (no-capability bootstrap,
  per-item exit-3 gap, `reviewCount` 0/null = volume-UNAVAILABLE) are unchanged.

## 5. Error handling
No new error paths. A `--search` query that itself blocks (exit 3) or finds no name match behaves exactly
as the bare query does today (exit 3 → escalate, or `name:null` → disclose). Backward compatibility:
existing callers and tests that omit `--search` see identical behavior.

## 6. Testing
**maps-cli repo (gate: pytest --cov / ruff check / ruff format --check / mypy):**
- **Unit** (`tests/integration/test_places_cmd.py` or a focused unit test): monkeypatch
  `maps_cli.gosom.run_gosom` to capture the `query` argument. Assert `places "Nan Xiang" --near "Flushing"
  --search "soup dumplings"` calls it with query `"soup dumplings Flushing"`; assert that with no
  `--search` the query is `"Nan Xiang Flushing"`. Assert the matcher is given the positional `name` in
  both cases (the returned record's matching is name-based).
- **Integration** via the existing `fake_gosom` (which returns the canned Luigi's + Scarpetta regardless
  of query): `places "Scarpetta" --near "Y" --search "italian"` returns the Scarpetta record — proving
  `--search` does not disturb name-matching.

**vox repo (gate: pytest / ruff check tools tests eval / validate_skills.py skills):**
- Extend `tests/test_routing.py` with an assertion that the `vox-maps` skill or its places-playbook
  documents the `--search` strategy (e.g. the string `--search` appears in the vox-maps skill files), so
  the guidance can't be silently dropped.
- The skill validator must stay `[ok]` for every skill.

## 7. Files created / changed
**maps-cli repo:** `maps_cli/commands/places.py` (add `--search`/`-q` + query construction); the places
test(s) above.
**vox repo:** `skills/vox-maps/SKILL.md` + `skills/vox-maps/references/places-playbook.md` (use + explain
`--search`); `tests/test_routing.py` (assertion).

## 8. Risks
- **A `--search` term too narrow to include the finalist** (e.g. searching "soup dumplings" for a
  wonton spot) → matcher returns `name:null`; vox-maps discloses + escalates. Mitigated by the playbook
  guidance to pick a category broad enough to contain the finalist, and the honest no-match path.
- **The broad query also gets anti-bot-blocked** → exit 3, same per-item escalation to `vox-browser` as
  today. The refinement reduces block frequency; it does not claim to eliminate it.
