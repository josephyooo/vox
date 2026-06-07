# vox-maps `--search` Query Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let vox-maps reliably obtain a finalist's rating × review-volume under gosom's exact-name anti-bot block, by giving `maps-cli places` an optional broad `--search` term (the matcher still keys on the exact name) and having the vox-maps skill pass the query's cuisine/category as that term.

**Architecture:** Two ordered parts in two repos. Part A (maps-cli): `commands/places.py` gains `--search/-q`; when set, the gosom query becomes `f"{search} {near}"` (a scrollable list) instead of `f"{name} {near}"` (a single place page that blocks), while `select_match` still scores against the positional `name`. Part B (vox repo): the `vox-maps` skill + playbook pass `--search "<category>"` and document the rationale; a routing test asserts the guidance is present. Backward-compatible: omitting `--search` preserves today's behavior.

**Tech Stack:** Python 3.9+ / Typer / pytest / ruff / mypy (maps-cli); Markdown skills + Python 3.14 / pytest / ruff / `validate_skills.py` (vox). No new dependencies.

**Spec:** `/Users/joseph/projects/vox/docs/superpowers/specs/2026-06-07-vox-maps-search-query-refinement-design.md`

**Repos:** Part A → `/Users/joseph/projects/maps-cli` (built, gate-green, editable-installed + symlinked onto PATH, so a code edit takes effect immediately — no reinstall). Part B → `/Users/joseph/projects/vox`.

---

## File Structure

```
maps-cli/
  maps_cli/commands/places.py            # MODIFY — add --search/-q + query construction
  tests/integration/test_places_cmd.py   # MODIFY — 2 unit (query capture) + 1 integration test
vox/
  skills/vox-maps/SKILL.md               # MODIFY — Loop step 1 passes --search
  skills/vox-maps/references/places-playbook.md  # MODIFY — document --search + the why
  tests/test_routing.py                  # MODIFY — assert the --search guidance is present
```

**Gates:**
- maps-cli (from `/Users/joseph/projects/maps-cli`): `.venv/bin/python -m pytest --cov=maps_cli --cov-report=term-missing -q` · `.venv/bin/python -m ruff check maps_cli tests` · `.venv/bin/python -m ruff format --check maps_cli tests` · `.venv/bin/python -m mypy maps_cli`
- vox (from `/Users/joseph/projects/vox`): `.venv/bin/python -m pytest` · `.venv/bin/python -m ruff check tools tests eval` · `.venv/bin/python tools/validate_skills.py skills`

---

### Task 1: maps-cli — add `--search/-q` to `places`

**Files:**
- Modify: `/Users/joseph/projects/maps-cli/maps_cli/commands/places.py`
- Test: `/Users/joseph/projects/maps-cli/tests/integration/test_places_cmd.py`

- [ ] **Step 1: Write the failing tests**

Append these three tests to `/Users/joseph/projects/maps-cli/tests/integration/test_places_cmd.py` (the file already has `import json`, `from typer.testing import CliRunner`, `from maps_cli.app import app`, and `runner = CliRunner()`):

```python
def test_places_search_overrides_gosom_query(monkeypatch):
    captured = {}

    def fake_run(query, **kwargs):
        captured["query"] = query
        return [{"title": "Nan Xiang", "review_rating": 4.5, "review_count": 7131}]

    monkeypatch.setattr("maps_cli.gosom.run_gosom", fake_run)
    result = runner.invoke(
        app,
        ["--json", "places", "Nan Xiang", "--near", "Flushing", "--search", "soup dumplings"],
    )
    assert result.exit_code == 0
    assert captured["query"] == "soup dumplings Flushing"  # gosom gets the broad term, not the name
    rec = json.loads(result.stdout.strip())
    assert rec["name"] == "Nan Xiang"  # matcher still keyed on the positional name


def test_places_without_search_uses_name_query(monkeypatch):
    captured = {}

    def fake_run(query, **kwargs):
        captured["query"] = query
        return [{"title": "Nan Xiang", "review_rating": 4.5, "review_count": 7131}]

    monkeypatch.setattr("maps_cli.gosom.run_gosom", fake_run)
    result = runner.invoke(app, ["--json", "places", "Nan Xiang", "--near", "Flushing"])
    assert result.exit_code == 0
    assert captured["query"] == "Nan Xiang Flushing"  # unchanged default behavior


def test_places_search_does_not_disturb_matching(fake_gosom):
    result = runner.invoke(
        app, ["--json", "places", "Scarpetta", "--near", "Manhattan", "--search", "italian"]
    )
    assert result.exit_code == 0
    rec = json.loads(result.stdout.strip())
    assert rec["name"] == "Scarpetta"
    assert rec["reviewCount"] == 3251
```

- [ ] **Step 2: Run them to verify the new-option tests fail**

Run: `cd /Users/joseph/projects/maps-cli && .venv/bin/python -m pytest tests/integration/test_places_cmd.py -q`
Expected: `test_places_search_overrides_gosom_query` and `test_places_search_does_not_disturb_matching` FAIL (an unknown `--search` option makes Typer exit 2, so `exit_code == 0` fails); `test_places_without_search_uses_name_query` already PASSES (it guards the default behavior).

- [ ] **Step 3: Add the `--search` option + query construction**

Edit `/Users/joseph/projects/maps-cli/maps_cli/commands/places.py`. Add the `search` option to the `places` signature — insert it immediately after the `near` option:
```python
    near: str = typer.Option(..., "--near", help="Neighborhood/city to scope the search"),
    search: str | None = typer.Option(
        None,
        "--search",
        "-q",
        help="broad search term (e.g. cuisine) sent to gosom instead of the exact name; the "
        "matcher still keys on <name>. Sidesteps the exact-name single-page anti-bot block.",
    ),
    n: int = typer.Option(5, "-n", "--count", help="max search rows to consider"),
```

Then replace this line:
```python
        raw = gosom.run_gosom(f"{name} {near}", depth=1, timeout=timeout)
```
with:
```python
        gosom_query = f"{search} {near}" if search else f"{name} {near}"
        raw = gosom.run_gosom(gosom_query, depth=1, timeout=timeout)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/joseph/projects/maps-cli && .venv/bin/python -m pytest tests/integration/test_places_cmd.py -q`
Expected: PASS (7 passed — the 4 existing + 3 new).

- [ ] **Step 5: Run the full maps-cli gate**

```bash
cd /Users/joseph/projects/maps-cli
.venv/bin/python -m ruff format maps_cli tests
.venv/bin/python -m pytest --cov=maps_cli --cov-report=term-missing -q
.venv/bin/python -m ruff check maps_cli tests
.venv/bin/python -m ruff format --check maps_cli tests
.venv/bin/python -m mypy maps_cli
```
Expected: all tests pass; ruff check "All checks passed!"; ruff format "… already formatted"; mypy "Success".

- [ ] **Step 6: Commit**

```bash
cd /Users/joseph/projects/maps-cli
git add maps_cli/commands/places.py tests/integration/test_places_cmd.py
git commit -q -m "feat(places): add --search broad-query option (sidestep exact-name anti-bot block)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: vox repo — vox-maps skill passes `--search` + routing-test guard

**Files:**
- Modify: `/Users/joseph/projects/vox/tests/test_routing.py`
- Modify: `/Users/joseph/projects/vox/skills/vox-maps/SKILL.md`
- Modify: `/Users/joseph/projects/vox/skills/vox-maps/references/places-playbook.md`

- [ ] **Step 1: Write the failing routing-test assertion**

Append this function to the END of `/Users/joseph/projects/vox/tests/test_routing.py` (the file already defines `SKILLS` and `MAPS` at module level):
```python
def test_vox_maps_documents_search_strategy():
    playbook = (SKILLS / "vox-maps" / "references" / "places-playbook.md").read_text()
    combined = MAPS + playbook
    assert "--search" in combined  # the anti-bot broad-query strategy is documented
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py::test_vox_maps_documents_search_strategy -q`
Expected: FAIL — neither the vox-maps SKILL.md nor the playbook mentions `--search` yet.

- [ ] **Step 3: Edit the vox-maps SKILL.md Loop step 1**

In `/Users/joseph/projects/vox/skills/vox-maps/SKILL.md`, replace this exact line:
```text
1. For each finalist `(name, locality)`: `maps-cli --json places "<name>" --near "<locality>"`.
```
with:
```text
1. For each finalist `(name, locality)`: `maps-cli --json places "<name>" --near "<locality>" --search "<cuisine/category>"` — pass the query's cuisine/category (e.g. "dumplings", "ramen", "pizza") as `--search` so gosom searches a broad term that returns a LIST while the matcher keys on `<name>`. A bare exact-name query resolves to a single Maps place page (no list → `scrollHeight` → exit-3 anti-bot block). Omit `--search` only when no sensible category exists.
```

- [ ] **Step 4: Edit the places-playbook.md Call section**

In `/Users/joseph/projects/vox/skills/vox-maps/references/places-playbook.md`, replace this exact block:
```text
## Call
- One finalist per call: `maps-cli --json places "<name>" --near "<neighborhood or city>"`.
- Query LOOSELY — `name + neighborhood`, never a full street address. gosom is a SEARCH tool: an exact
  address resolves to a single place page with no results list and fails. Pass the locality you already
  know from the candidate's context, e.g. `--near "Park Slope Brooklyn"`.
- `--json` emits ONE NDJSON object on stdout. Parse it; never screenshot.
```
with:
```text
## Call
- One finalist per call: `maps-cli --json places "<name>" --near "<neighborhood or city>" --search "<cuisine/category>"`.
- **Use `--search` for the broad query.** gosom is a SEARCH tool, not a lookup tool: an exact business
  NAME (like an exact address) resolves to a single Maps *place* page with no results list →
  `scrollHeight` → exit-3 anti-bot block. So pass a broad cuisine/category term (e.g. "soup dumplings",
  "ramen", "pizza") as `--search`; gosom searches `"<search> <near>"` (a scrollable list) while the
  matcher still finds your `<name>` in it with full rating × volume. The category comes from the query
  family. Omit `--search` only when no sensible category exists (it then falls back to `"<name> <near>"`,
  which may hit the block).
- Query the LOCALITY loosely — `name + neighborhood`, never a full street address. Pass the locality from
  the candidate's context, e.g. `--near "Park Slope Brooklyn"`.
- `--json` emits ONE NDJSON object on stdout. Parse it; never screenshot.
```

- [ ] **Step 5: Run the routing test + the full vox gate**

Run the new test:
```bash
cd /Users/joseph/projects/vox && .venv/bin/python -m pytest tests/test_routing.py -q
```
Expected: PASS (6 passed — the 5 existing + the new one).

Run the full gate:
```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```
Expected: pytest all pass; ruff "All checks passed!"; validator prints `[ok]` for every skill including
`vox-maps`, no `[FAIL]` (the SKILL.md edit adds no new local links, so link-resolution stays clean).

- [ ] **Step 6: Verify end-to-end against the real binary (manual, not gated)**

`maps-cli` is editable-installed, so Task 1's change is already live. Confirm `--search` works:
```bash
maps-cli --json places "Nan Xiang" --near "Flushing Queens" --search "soup dumplings"
```
Expected: exit 0 with a record whose `name` matches Nan Xiang and a non-zero `reviewCount` (broad-query
list path). If gosom is anti-bot-blocked at this moment it may still exit 3 — that is the correct
fallback signal, not a regression; the unit/integration tests already prove the query construction.

- [ ] **Step 7: Commit**

```bash
cd /Users/joseph/projects/vox
git add tests/test_routing.py skills/vox-maps/SKILL.md skills/vox-maps/references/places-playbook.md
git commit -q -m "feat(vox-maps): pass --search broad-query to maps-cli (anti-bot exact-name fix)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criterion

`maps-cli places` accepts `--search/-q` and routes it to gosom as `"<search> <near>"` while matching on
the exact name (maps-cli gate green: pytest/ruff/mypy); the `vox-maps` skill + playbook pass and document
`--search`, with `tests/test_routing.py` guarding the guidance and the validator `[ok]` (vox gate green).
Backward-compatible — omitting `--search` is unchanged. Optional follow-up: a one-off live re-run of the
`maps-places` golden once gosom is unblocked, to confirm the broad-query lookups corroborate more
finalists with verified volume.
