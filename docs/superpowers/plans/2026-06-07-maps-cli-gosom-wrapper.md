# maps-cli (gosom Maps wrapper) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `maps-cli` repo — a Python/Typer wrapper around the native arm64 `gosom/google-maps-scraper` binary that returns normalized Google-Maps place data (rating × review-volume + address + hours) for a named finalist, with a tested fallback-signalling contract.

**Architecture:** A thin CLI with one tested seam — a subprocess **gosom runner** (`run_gosom`) that runs the native binary with a hard timeout + retry-once, parses its JSON-lines output, and raises typed errors mapped to tiktok-cli-style exit codes. A **matcher** selects the intended finalist from gosom's search-list output (gosom is a search tool, not a lookup tool); a **normalizer** maps gosom's raw dict to the stable contract. Tests drive a **faithful fake gosom executable** (a real script the runner shells out to), so the subprocess/timeout/retry paths are genuinely covered.

**Tech Stack:** Python 3.9+, Typer, Rich, pytest/pytest-cov, ruff, mypy. Mirrors the existing `tiktok-cli` repo conventions. New repo at `/Users/joseph/projects/maps-cli`.

**Subsystem boundary:** This is subsystem 1 of 2. The `vox-maps` skill + orchestrator/`vox-browser` wiring (subsystem 2) is a SEPARATE plan, written after this repo's gate is green. Do not touch the vox repo in this plan.

**Spec:** `/Users/joseph/projects/vox/docs/superpowers/specs/2026-06-07-vox-maps-gosom-tier-design.md`

---

## File Structure

```
maps-cli/
  pyproject.toml                 # packaging + gate config (mirrors tiktok-cli)
  README.md                      # usage + the gosom native-binary prerequisite
  maps_cli/
    __init__.py                  # __version__
    __main__.py                  # python -m maps_cli
    app.py                       # Typer root: global options + command registration
    config.py                    # GlobalOptions dataclass (json/pretty/verbose)
    errors.py                    # EXIT_* + CLIError + BlockedError(3) + GosomUnavailableError(4)
    output.py                    # Renderer/Column/should_use_json (copied from tiktok-cli)
    gosom.py                     # run_gosom() — the subprocess seam (timeout, retry, parse)
    matcher.py                   # select_match() — pick the finalist from gosom's list
    normalize.py                 # normalize_place() — raw gosom dict -> stable contract
    commands/
      __init__.py
      places.py                  # `places` command (run_gosom + match + normalize + render)
      doctor.py                  # `doctor` capability probe (binary + chromium present)
  tests/
    __init__.py
    conftest.py                  # fake-gosom fixture (sets $MAPS_CLI_GOSOM_BIN)
    fakes/
      fake_gosom.py              # the faithful fake gosom executable (chmod +x)
    unit/
      test_errors.py
      test_normalize.py
      test_matcher.py
      test_gosom.py
      test_output.py
    integration/
      test_places_cmd.py
      test_doctor_cmd.py
```

**Gate (run from repo root, after `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`):**
```
.venv/bin/python -m pytest --cov=maps_cli --cov-report=term-missing -q
.venv/bin/python -m ruff check maps_cli tests
.venv/bin/python -m ruff format --check maps_cli tests
.venv/bin/python -m mypy maps_cli
```

---

### Task 1: Scaffold the repo

**Files:**
- Create: `/Users/joseph/projects/maps-cli/pyproject.toml`
- Create: `maps_cli/__init__.py`, `maps_cli/__main__.py`, `maps_cli/app.py`, `maps_cli/commands/__init__.py`
- Create: `tests/__init__.py`, `tests/unit/test_smoke.py`

- [ ] **Step 1: Init the repo and dirs**

```bash
mkdir -p /Users/joseph/projects/maps-cli/maps_cli/commands /Users/joseph/projects/maps-cli/tests/unit /Users/joseph/projects/maps-cli/tests/integration /Users/joseph/projects/maps-cli/tests/fakes
cd /Users/joseph/projects/maps-cli && git init -q
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "maps-cli"
version = "0.1.0"
description = "A command-line wrapper around the native gosom/google-maps-scraper binary"
requires-python = ">=3.9"
dependencies = ["typer>=0.12", "rich>=13"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "mypy"]

[project.scripts]
maps-cli = "maps_cli.app:app"

[tool.hatch.build.targets.wheel]
packages = ["maps_cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["maps_cli"]
omit = ["maps_cli/__main__.py"]

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.10"
ignore_missing_imports = true
```

- [ ] **Step 3: Write the package skeleton**

`maps_cli/__init__.py`:
```python
__version__ = "0.1.0"
```

`maps_cli/__main__.py`:
```python
from .app import app

if __name__ == "__main__":
    app()
```

`maps_cli/commands/__init__.py`: (empty file)

`maps_cli/app.py`:
```python
"""Typer root app: global options, context wiring, subcommand registration."""

from __future__ import annotations

import typer

from . import __version__
from .config import GlobalOptions

app = typer.Typer(
    help="Google Maps place data via the native gosom scraper (read-only).",
    no_args_is_help=True,
    add_completion=False,
)


def _version_cb(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    json_: bool | None = typer.Option(
        None, "--json/--table", help="force output mode (default: auto)"
    ),
    pretty: bool = typer.Option(False, "--pretty", help="pretty JSON instead of NDJSON"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    version: bool | None = typer.Option(None, "--version", callback=_version_cb, is_eager=True),
):
    ctx.obj = GlobalOptions(json_mode=json_, pretty=pretty, verbose=verbose)
```

`maps_cli/config.py`:
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlobalOptions:
    json_mode: bool | None = None
    pretty: bool = False
    verbose: bool = False
```

- [ ] **Step 4: Write the smoke test**

`tests/__init__.py`: (empty)

`tests/unit/test_smoke.py`:
```python
from maps_cli import __version__


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__
```

- [ ] **Step 5: Create venv, install, run the gate**

```bash
cd /Users/joseph/projects/maps-cli
python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]"
.venv/bin/python -m pytest -q
```
Expected: `1 passed`.

```bash
printf '.venv/\n__pycache__/\n*.pyc\n.coverage\n' > .gitignore
```

- [ ] **Step 6: Commit**

```bash
cd /Users/joseph/projects/maps-cli
git add -A
git commit -q -m "chore: scaffold maps-cli repo (Typer skeleton + gate)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Error taxonomy + exit codes

**Files:**
- Create: `maps_cli/errors.py`
- Test: `tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_errors.py`:
```python
from maps_cli import errors


def test_exit_codes():
    assert (errors.EXIT_RUNTIME, errors.EXIT_USAGE, errors.EXIT_BLOCKED, errors.EXIT_ENV) == (
        1,
        2,
        3,
        4,
    )


def test_blocked_error_code():
    assert errors.BlockedError("x").exit_code == 3


def test_unavailable_error_code():
    assert errors.GosomUnavailableError("x").exit_code == 4


def test_base_error_is_runtime():
    assert errors.CLIError("x").exit_code == 1


def test_classify_passes_through_cli_error():
    e = errors.BlockedError("y")
    assert errors.classify_exception(e) is e


def test_classify_wraps_unknown():
    out = errors.classify_exception(ValueError("boom"))
    assert isinstance(out, errors.CLIError)
    assert out.exit_code == 1
    assert "ValueError" in out.message
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_errors.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_cli.errors'`.

- [ ] **Step 3: Write the implementation**

`maps_cli/errors.py`:
```python
"""Error taxonomy and exception classification for maps-cli."""

from __future__ import annotations

EXIT_RUNTIME = 1
EXIT_USAGE = 2
EXIT_BLOCKED = 3  # gosom returned nothing / anti-bot block -> caller escalates to browser fallback
EXIT_ENV = 4  # native binary or chromium missing -> caller escalates to browser fallback


class CLIError(Exception):
    exit_code = EXIT_RUNTIME

    def __init__(self, message: str, exit_code: int | None = None):
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code


class BlockedError(CLIError):
    """gosom produced no results after a retry (scrollHeight / anti-bot / timeout)."""

    exit_code = EXIT_BLOCKED


class GosomUnavailableError(CLIError):
    """The native gosom binary or its Chromium is missing/not executable."""

    exit_code = EXIT_ENV


def classify_exception(exc: Exception) -> CLIError:
    if isinstance(exc, CLIError):
        return exc
    return CLIError(f"{type(exc).__name__}: {exc}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_errors.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/errors.py tests/unit/test_errors.py
git commit -q -m "feat: error taxonomy + exit codes (blocked=3, env=4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Normalizer (raw gosom dict -> stable contract)

**Files:**
- Create: `maps_cli/normalize.py`
- Test: `tests/unit/test_normalize.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_normalize.py`:
```python
from maps_cli import normalize

RAW = {
    "title": "Luigi's Pizza",
    "review_rating": 4.6,
    "review_count": 2487,
    "address": "686 5th Ave, Brooklyn, NY 11215",
    "open_hours": {"Monday": ["11 AM-10 PM"]},
    "link": "https://www.google.com/maps/place/Luigis",
    "category": "Pizza restaurant",
    "latitude": 40.6617,
    "longitude": -73.9934,
}
ALT = {
    "title": "Scarpetta",
    "review_rating": 4.6,
    "review_count": 3251,
    "address": "88 Madison Ave, New York, NY 10016",
    "link": "https://www.google.com/maps/place/Scarpetta",
}


def test_normalize_maps_fields():
    out = normalize.normalize_place(RAW, confidence="high", alternatives=[ALT])
    assert out["name"] == "Luigi's Pizza"
    assert out["rating"] == 4.6
    assert out["reviewCount"] == 2487
    assert out["address"] == "686 5th Ave, Brooklyn, NY 11215"
    assert out["hours"] == {"Monday": ["11 AM-10 PM"]}
    assert out["mapsUrl"] == "https://www.google.com/maps/place/Luigis"
    assert out["confidence"] == "high"
    assert out["source"] == "google-maps/gosom"


def test_normalize_alternatives_are_brief():
    out = normalize.normalize_place(RAW, confidence="high", alternatives=[ALT])
    assert out["alternatives"] == [
        {
            "name": "Scarpetta",
            "rating": 4.6,
            "reviewCount": 3251,
            "address": "88 Madison Ave, New York, NY 10016",
            "mapsUrl": "https://www.google.com/maps/place/Scarpetta",
        }
    ]


def test_normalize_empty_match():
    out = normalize.normalize_place({}, confidence="low", alternatives=[])
    assert out["name"] is None
    assert out["confidence"] == "low"
    assert out["alternatives"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_cli.normalize'`.

- [ ] **Step 3: Write the implementation**

`maps_cli/normalize.py`:
```python
"""Map gosom's raw place dict to the stable maps-cli output contract."""

from __future__ import annotations

from typing import Any

SOURCE = "google-maps/gosom"


def _brief(raw: dict) -> dict:
    return {
        "name": raw.get("title"),
        "rating": raw.get("review_rating"),
        "reviewCount": raw.get("review_count"),
        "address": raw.get("address"),
        "mapsUrl": raw.get("link"),
    }


def normalize_place(
    raw: dict,
    *,
    confidence: str = "high",
    alternatives: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "name": raw.get("title"),
        "rating": raw.get("review_rating"),
        "reviewCount": raw.get("review_count"),
        "address": raw.get("address"),
        "hours": raw.get("open_hours"),
        "priceBand": raw.get("price_range"),
        "category": raw.get("category"),
        "mapsUrl": raw.get("link"),
        "lat": raw.get("latitude"),
        "lng": raw.get("longitude"),
        "confidence": confidence,
        "alternatives": [_brief(a) for a in (alternatives or [])],
        "source": SOURCE,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/normalize.py tests/unit/test_normalize.py
git commit -q -m "feat: normalize gosom dict -> stable place contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Matcher (pick the finalist from gosom's search list)

**Files:**
- Create: `maps_cli/matcher.py`
- Test: `tests/unit/test_matcher.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_matcher.py`:
```python
from maps_cli import matcher

LUIGI = {"title": "Luigi's Pizza", "review_count": 2487}
SCARPETTA = {"title": "Scarpetta", "review_count": 3251}
UBANI_MID = {"title": "Ubani Midtown", "review_count": 1168}
UBANI_WV = {"title": "Ubani - West Village", "review_count": 1212}


def test_single_exact_is_high():
    r = matcher.select_match([LUIGI], "Luigi's Pizza")
    assert r.best is LUIGI
    assert r.confidence == "high"
    assert r.alternatives == []


def test_noise_row_rejected_target_wins():
    r = matcher.select_match([SCARPETTA, LUIGI], "Luigi's Pizza")
    assert r.best is LUIGI
    assert r.confidence == "high"
    assert r.alternatives == [SCARPETTA]


def test_locality_disambiguates_high():
    r = matcher.select_match([UBANI_WV, UBANI_MID], "Ubani Midtown")
    assert r.best is UBANI_MID
    assert r.confidence == "high"
    assert r.alternatives == [UBANI_WV]


def test_ambiguous_same_name_is_low():
    r = matcher.select_match([UBANI_WV, UBANI_MID], "Ubani")
    assert r.best is not None
    assert r.confidence == "low"
    assert len(r.alternatives) == 1


def test_no_candidate_clears_bar():
    r = matcher.select_match([SCARPETTA], "Luigi's Pizza")
    assert r.best is None
    assert r.confidence == "low"
    assert r.alternatives == [SCARPETTA]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_matcher.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_cli.matcher'`.

- [ ] **Step 3: Write the implementation**

`maps_cli/matcher.py`:
```python
"""Select the intended finalist from gosom's search-list output.

gosom is a SEARCH tool: a `name + neighborhood` query returns a list (target usually on
top, plus adjacent rows). We score each row by token overlap with the requested name,
tie-break by review-volume, and flag low-confidence/ambiguous matches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_MATCH = 0.5  # at least half the requested name's tokens must appear in the title
MARGIN = 0.34  # best must beat the runner-up by this score margin to be "high" confidence


@dataclass
class MatchResult:
    best: dict | None
    alternatives: list[dict]
    confidence: str  # "high" | "low"


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t}


def _score(result: dict, req: set[str]) -> float:
    if not req:
        return 0.0
    title = _tokens(result.get("title", ""))
    return len(req & title) / len(req)


def select_match(results: list[dict], requested_name: str) -> MatchResult:
    req = _tokens(requested_name)
    scored = sorted(
        ((_score(r, req), r) for r in results),
        key=lambda sr: (sr[0], sr[1].get("review_count") or 0),
        reverse=True,
    )
    if not scored or scored[0][0] < MIN_MATCH:
        return MatchResult(best=None, alternatives=[r for _, r in scored], confidence="low")
    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    confidence = "high" if (len(scored) == 1 or best_score - second >= MARGIN) else "low"
    return MatchResult(best=best, alternatives=[r for _, r in scored[1:]], confidence=confidence)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_matcher.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/matcher.py tests/unit/test_matcher.py
git commit -q -m "feat: name matcher with locality disambiguation + confidence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: The faithful fake gosom executable + fixture

**Files:**
- Create: `tests/fakes/fake_gosom.py` (chmod +x)
- Create: `tests/conftest.py`
- Test: `tests/unit/test_fake_gosom.py` (validates the test double itself)

- [ ] **Step 1: Write the fake gosom executable**

`tests/fakes/fake_gosom.py`:
```python
#!/usr/bin/env python3
"""Faithful fake of gosom/google-maps-scraper for maps-cli tests.

Honors the real contract: parses -input/-results, writes gosom-style JSON lines to the
-results path, and EXITS 0 even when a job fails (the real binary does too). Behaviour is
driven by FAKE_GOSOM_MODE: success | empty | scrollheight_then_ok | hang.
"""

import json
import os
import sys
import time

PLACES = [
    {
        "title": "Luigi's Pizza",
        "review_rating": 4.6,
        "review_count": 2487,
        "address": "686 5th Ave, Brooklyn, NY 11215",
        "open_hours": {"Monday": ["11 AM-10 PM"]},
        "link": "https://www.google.com/maps/place/Luigis",
        "category": "Pizza restaurant",
        "latitude": 40.6617,
        "longitude": -73.9934,
    },
    {
        "title": "Scarpetta",
        "review_rating": 4.6,
        "review_count": 3251,
        "address": "88 Madison Ave, New York, NY 10016",
        "open_hours": {},
        "link": "https://www.google.com/maps/place/Scarpetta",
        "category": "Restaurant",
        "latitude": 40.7,
        "longitude": -73.9,
    },
]

SCROLL_ERR = "playwright: TypeError: Cannot read properties of null (reading 'scrollHeight')\n"


def _arg(flag: str) -> str | None:
    argv = sys.argv
    return argv[argv.index(flag) + 1] if flag in argv else None


def _write(results: str | None) -> None:
    if not results:
        return
    with open(results, "w") as f:
        for p in PLACES:
            f.write(json.dumps(p) + "\n")


def main() -> int:
    mode = os.environ.get("FAKE_GOSOM_MODE", "success")
    results = _arg("-results")
    if mode == "hang":
        time.sleep(600)
        return 0
    if mode == "empty":
        sys.stderr.write(SCROLL_ERR)
        return 0  # no results written; gosom exits 0 on job failure
    if mode == "scrollheight_then_ok":
        counter = os.environ.get("FAKE_GOSOM_COUNTER", "")
        n = 0
        if counter and os.path.exists(counter):
            n = int(open(counter).read() or "0")
        if counter:
            open(counter, "w").write(str(n + 1))
        if n == 0:
            sys.stderr.write(SCROLL_ERR)
            return 0  # first call fails empty
        _write(results)  # second call succeeds
        return 0
    _write(results)  # success
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/joseph/projects/maps-cli/tests/fakes/fake_gosom.py
```

- [ ] **Step 3: Write the conftest fixture**

`tests/conftest.py`:
```python
from pathlib import Path

import pytest

FAKE_GOSOM = Path(__file__).parent / "fakes" / "fake_gosom.py"


@pytest.fixture
def fake_gosom(monkeypatch, tmp_path):
    """Point maps-cli at the faithful fake gosom; default mode 'success'."""
    monkeypatch.setenv("MAPS_CLI_GOSOM_BIN", str(FAKE_GOSOM))
    monkeypatch.setenv("FAKE_GOSOM_MODE", "success")
    monkeypatch.setenv("FAKE_GOSOM_COUNTER", str(tmp_path / "counter"))
    return FAKE_GOSOM
```

- [ ] **Step 4: Write a test that validates the fake double itself**

`tests/unit/test_fake_gosom.py`:
```python
import json
import os
import subprocess

from tests.conftest import FAKE_GOSOM


def test_fake_is_executable():
    assert os.access(FAKE_GOSOM, os.X_OK), "fake_gosom.py must be chmod +x"


def test_fake_writes_json_lines(tmp_path):
    out = tmp_path / "out.json"
    inp = tmp_path / "in.txt"
    inp.write_text("Luigi's Pizza Park Slope\n")
    subprocess.run(
        [str(FAKE_GOSOM), "-input", str(inp), "-results", str(out), "-json"],
        check=True,
        env={**os.environ, "FAKE_GOSOM_MODE": "success"},
    )
    rows = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert {r["title"] for r in rows} == {"Luigi's Pizza", "Scarpetta"}


def test_fake_empty_writes_nothing(tmp_path):
    out = tmp_path / "out.json"
    r = subprocess.run(
        [str(FAKE_GOSOM), "-results", str(out)],
        capture_output=True,
        text=True,
        env={**os.environ, "FAKE_GOSOM_MODE": "empty"},
    )
    assert r.returncode == 0
    assert not out.exists() or out.read_text() == ""
    assert "scrollHeight" in r.stderr
```

- [ ] **Step 5: Run + verify**

Run: `.venv/bin/python -m pytest tests/unit/test_fake_gosom.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add tests/fakes/fake_gosom.py tests/conftest.py tests/unit/test_fake_gosom.py
git update-index --chmod=+x tests/fakes/fake_gosom.py
git commit -q -m "test: faithful fake gosom executable + fixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: The gosom runner (`run_gosom`)

**Files:**
- Create: `maps_cli/gosom.py`
- Test: `tests/unit/test_gosom.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_gosom.py`:
```python
import pytest

from maps_cli import errors, gosom


def test_run_gosom_success(fake_gosom):
    rows = gosom.run_gosom("Luigi's Pizza Park Slope", timeout=20)
    assert {r["title"] for r in rows} == {"Luigi's Pizza", "Scarpetta"}


def test_run_gosom_retries_once_on_scrollheight(fake_gosom, monkeypatch):
    monkeypatch.setenv("FAKE_GOSOM_MODE", "scrollheight_then_ok")
    rows = gosom.run_gosom("Luigi's Pizza Park Slope", timeout=20)
    assert {r["title"] for r in rows} == {"Luigi's Pizza", "Scarpetta"}


def test_run_gosom_persistent_empty_raises_blocked(fake_gosom, monkeypatch):
    monkeypatch.setenv("FAKE_GOSOM_MODE", "empty")
    with pytest.raises(errors.BlockedError):
        gosom.run_gosom("Nowhere Nope", timeout=20)


def test_run_gosom_timeout_raises_blocked(fake_gosom, monkeypatch):
    monkeypatch.setenv("FAKE_GOSOM_MODE", "hang")
    with pytest.raises(errors.BlockedError):
        gosom.run_gosom("Slow Place", timeout=2)


def test_run_gosom_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setenv("MAPS_CLI_GOSOM_BIN", "/no/such/google-maps-scraper")
    with pytest.raises(errors.GosomUnavailableError):
        gosom.run_gosom("Anywhere", timeout=20)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_gosom.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_cli.gosom'`.

- [ ] **Step 3: Write the implementation**

`maps_cli/gosom.py`:
```python
"""The gosom subprocess seam: run the native binary, enforce a hard timeout, retry once,
parse JSON-lines output. Raises typed errors mapped to exit codes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from .errors import BlockedError, GosomUnavailableError

DEFAULT_BIN = "~/go/bin/google-maps-scraper"


def gosom_bin() -> str:
    return os.path.expanduser(os.environ.get("MAPS_CLI_GOSOM_BIN") or DEFAULT_BIN)


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _parse_results(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def _run_once(binary: str, query: str, depth: int, concurrency: int, timeout: float) -> list[dict]:
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "queries.txt"
        out = Path(d) / "results.json"
        inp.write_text(query + "\n")
        cmd = [
            binary,
            "-input",
            str(inp),
            "-results",
            str(out),
            "-json",
            "-depth",
            str(depth),
            "-c",
            str(concurrency),
            "-exit-on-inactivity",
            "5s",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # own process group so we can kill chromium children
        )
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            proc.communicate()
            raise BlockedError(f"gosom timed out after {timeout}s") from exc
        return _parse_results(out)


def run_gosom(
    query: str,
    *,
    depth: int = 1,
    concurrency: int = 4,
    timeout: float = 90.0,
) -> list[dict]:
    """Run gosom for `query`; return raw place dicts. Retries once on an empty result
    (the intermittent cold scrollHeight failure). Raises GosomUnavailableError if the
    binary is missing, BlockedError if still empty after the retry or on timeout."""
    binary = gosom_bin()
    if not _is_executable(binary):
        raise GosomUnavailableError(
            f"gosom binary not found/executable at {binary}. "
            "Install: brew install go && go install github.com/gosom/google-maps-scraper@latest"
        )
    for _ in range(2):
        rows = _run_once(binary, query, depth, concurrency, timeout)
        if rows:
            return rows
    raise BlockedError("gosom returned no results after a retry (anti-bot / scrollHeight block)")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_gosom.py -q`
Expected: PASS (5 passed). The timeout test should finish in ~2-3s (the hang is SIGKILLed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/gosom.py tests/unit/test_gosom.py
git commit -q -m "feat: gosom subprocess runner (hard timeout, retry-once, typed errors)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Output renderer

**Files:**
- Create: `maps_cli/output.py`
- Test: `tests/unit/test_output.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_output.py`:
```python
import io

from maps_cli.config import GlobalOptions
from maps_cli.output import Column, Renderer, should_use_json


def test_should_use_json_forced():
    assert should_use_json(GlobalOptions(json_mode=True)) is True
    assert should_use_json(GlobalOptions(json_mode=False)) is False


def test_renderer_ndjson_emits_one_line_per_record():
    buf = io.StringIO()
    r = Renderer([Column("Name", lambda d: d.get("name"))], GlobalOptions(json_mode=True), buf)
    r.emit({"name": "Luigi's Pizza"})
    r.close()
    assert buf.getvalue().strip() == '{"name": "Luigi\'s Pizza"}'


def test_renderer_table_when_not_json():
    buf = io.StringIO()
    r = Renderer([Column("Name", lambda d: d.get("name"))], GlobalOptions(json_mode=False), buf)
    r.emit({"name": "Luigi's Pizza"})
    r.close()
    assert "Luigi's Pizza" in buf.getvalue()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_output.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_cli.output'`.

- [ ] **Step 3: Write the implementation**

`maps_cli/output.py`:
```python
"""TTY-aware rendering: NDJSON / pretty-JSON / Rich tables."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

from rich.console import Console
from rich.table import Table

from .config import GlobalOptions


@dataclass
class Column:
    header: str
    accessor: Callable[[dict], Any]


def should_use_json(opts: GlobalOptions, stream=None) -> bool:
    if opts.json_mode is not None:
        return opts.json_mode
    stream = stream or sys.stdout
    isatty = getattr(stream, "isatty", None)
    return not (callable(isatty) and isatty())


class Renderer:
    def __init__(self, columns: list[Column], opts: GlobalOptions, stream=None):
        self.columns = columns
        self.opts = opts
        self.stream = stream or sys.stdout
        self.use_json = should_use_json(opts, self.stream)
        self.stream_ndjson = self.use_json and not opts.pretty
        self._buffer: list[dict] = []

    def emit(self, record: dict) -> None:
        if self.stream_ndjson:
            self.stream.write(json.dumps(record, default=str) + "\n")
            flush = getattr(self.stream, "flush", None)
            if callable(flush):
                flush()
        else:
            self._buffer.append(record)

    def close(self) -> None:
        if self.stream_ndjson:
            return
        if self.use_json:
            self.stream.write(json.dumps(self._buffer, indent=2, default=str) + "\n")
            return
        if not self._buffer:
            self.stream.write("No results\n")
            return
        table = Table()
        for col in self.columns:
            table.add_column(col.header)
        for rec in self._buffer:
            table.add_row(*[str(col.accessor(rec)) for col in self.columns])
        Console(file=self.stream, force_terminal=False).print(table)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_output.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/output.py tests/unit/test_output.py
git commit -q -m "feat: TTY-aware renderer (NDJSON / pretty / table)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `doctor` capability probe

**Files:**
- Create: `maps_cli/commands/doctor.py`
- Modify: `maps_cli/app.py` (register the command)
- Test: `tests/integration/test_doctor_cmd.py`
- Create: `tests/integration/__init__.py` (empty)

- [ ] **Step 1: Write the failing test**

`tests/integration/__init__.py`: (empty)

`tests/integration/test_doctor_cmd.py`:
```python
from typer.testing import CliRunner

from maps_cli.app import app

runner = CliRunner()


def test_doctor_ok_when_binary_and_chromium_present(fake_gosom, monkeypatch, tmp_path):
    browsers = tmp_path / "ms-playwright"
    (browsers / "chromium-1200").mkdir(parents=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "google-maps-scraper" in result.stdout


def test_doctor_fails_when_binary_missing(monkeypatch, tmp_path):
    browsers = tmp_path / "ms-playwright"
    (browsers / "chromium-1200").mkdir(parents=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    monkeypatch.setenv("MAPS_CLI_GOSOM_BIN", "/no/such/bin")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 4


def test_doctor_fails_when_chromium_missing(fake_gosom, monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "empty"))
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 4
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_doctor_cmd.py -q`
Expected: FAIL (no `doctor` command registered → nonzero exit / usage error).

- [ ] **Step 3: Write the implementation**

`maps_cli/commands/doctor.py`:
```python
"""`maps-cli doctor` — capability probe used by vox-maps at bootstrap."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ..errors import EXIT_ENV
from ..gosom import _is_executable, gosom_bin


def _browsers_dir() -> Path:
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env != "0":
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def _check_chromium() -> tuple[bool, str]:
    browsers = _browsers_dir()
    try:
        has = browsers.is_dir() and any(c.name.startswith("chromium") for c in browsers.iterdir())
    except OSError:
        has = False
    if has:
        return True, f"chromium browser present ({browsers})"
    return False, (
        f"no chromium browser under {browsers}; run gosom once or "
        "`go install github.com/gosom/google-maps-scraper@latest` then a first scrape"
    )


def doctor() -> None:
    """Check the gosom native binary and its Chromium are available."""
    binary = gosom_bin()
    bin_ok = _is_executable(binary)
    br_ok, br_msg = _check_chromium()
    typer.echo(
        f"[{'OK' if bin_ok else 'XX'}] gosom binary {binary} "
        f"{'executable' if bin_ok else 'NOT found/executable'}"
    )
    typer.echo(f"[{'OK' if br_ok else 'XX'}] {br_msg}")
    if not (bin_ok and br_ok):
        raise typer.Exit(EXIT_ENV)
```

Modify `maps_cli/app.py` — add the import and registration (place the import with the others, and the registration after the `app = typer.Typer(...)` block):
```python
from .commands import doctor
...
app.command("doctor")(doctor.doctor)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/integration/test_doctor_cmd.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/commands/doctor.py maps_cli/app.py tests/integration/__init__.py tests/integration/test_doctor_cmd.py
git commit -q -m "feat: doctor capability probe (gosom binary + chromium)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: `places` command

**Files:**
- Create: `maps_cli/commands/places.py`
- Modify: `maps_cli/app.py` (register the command)
- Test: `tests/integration/test_places_cmd.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_places_cmd.py`:
```python
import json

from typer.testing import CliRunner

from maps_cli.app import app

runner = CliRunner()


def test_places_json_returns_matched_place(fake_gosom):
    result = runner.invoke(
        app, ["--json", "places", "Luigi's Pizza", "--near", "Park Slope Brooklyn"]
    )
    assert result.exit_code == 0
    rec = json.loads(result.stdout.strip())
    assert rec["name"] == "Luigi's Pizza"
    assert rec["rating"] == 4.6
    assert rec["reviewCount"] == 2487
    assert rec["confidence"] == "high"
    assert rec["source"] == "google-maps/gosom"
    assert {a["name"] for a in rec["alternatives"]} == {"Scarpetta"}


def test_places_low_confidence_when_no_match(fake_gosom):
    result = runner.invoke(app, ["--json", "places", "Totally Absent Cafe", "--near", "Nowhere"])
    assert result.exit_code == 0
    rec = json.loads(result.stdout.strip())
    assert rec["name"] is None
    assert rec["confidence"] == "low"
    assert len(rec["alternatives"]) >= 1


def test_places_blocked_exits_3(fake_gosom, monkeypatch):
    monkeypatch.setenv("FAKE_GOSOM_MODE", "empty")
    result = runner.invoke(app, ["places", "Luigi's Pizza", "--near", "Park Slope"])
    assert result.exit_code == 3


def test_places_missing_binary_exits_4(monkeypatch):
    monkeypatch.setenv("MAPS_CLI_GOSOM_BIN", "/no/such/bin")
    result = runner.invoke(app, ["places", "Luigi's Pizza", "--near", "Park Slope"])
    assert result.exit_code == 4
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_places_cmd.py -q`
Expected: FAIL (no `places` command).

- [ ] **Step 3: Write the implementation**

`maps_cli/commands/places.py`:
```python
"""`maps-cli places "<name>" --near "<area>"` — look up one named finalist."""

from __future__ import annotations

import traceback

import typer

from .. import gosom, matcher, normalize
from ..config import GlobalOptions
from ..errors import CLIError, classify_exception
from ..output import Column, Renderer

PLACE_COLUMNS = [
    Column("Name", lambda r: r.get("name") or "—"),
    Column("Rating×Reviews", lambda r: f"{r.get('rating')}×{r.get('reviewCount')}"),
    Column("Address", lambda r: r.get("address") or ""),
    Column("Conf", lambda r: r.get("confidence") or ""),
    Column("MapsUrl", lambda r: r.get("mapsUrl") or ""),
]


def _fail(err: CLIError, opts: GlobalOptions) -> typer.Exit:
    typer.echo(err.message, err=True)
    if opts.verbose:
        traceback.print_exc()
    return typer.Exit(err.exit_code)


def places(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="The place name (e.g. \"Luigi's Pizza\")"),
    near: str = typer.Option(..., "--near", help="Neighborhood/city to scope the search"),
    n: int = typer.Option(5, "-n", "--count", help="max search rows to consider"),
    timeout: float = typer.Option(90.0, "--timeout", help="hard timeout (seconds)"),
) -> None:
    """Resolve one finalist's rating x review-volume + address + hours via gosom."""
    opts: GlobalOptions = ctx.obj
    try:
        raw = gosom.run_gosom(f"{name} {near}", depth=1, timeout=timeout)
        match = matcher.select_match(raw[:n] if n else raw, name)
        record = normalize.normalize_place(
            match.best or {},
            confidence=match.confidence,
            alternatives=match.alternatives,
        )
        renderer = Renderer(PLACE_COLUMNS, opts)
        renderer.emit(record)
        renderer.close()
    except CLIError as err:
        raise _fail(err, opts) from err
    except Exception as exc:  # noqa: BLE001 - command chokepoint
        raise _fail(classify_exception(exc), opts) from exc
```

Modify `maps_cli/app.py` — add the import and registration:
```python
from .commands import doctor, places
...
app.command("places")(places.places)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/integration/test_places_cmd.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add maps_cli/commands/places.py maps_cli/app.py tests/integration/test_places_cmd.py
git commit -q -m "feat: places command (run_gosom + match + normalize + render)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: README + full gate + PATH install

**Files:**
- Create: `/Users/joseph/projects/maps-cli/README.md`

- [ ] **Step 1: Write the README**

`README.md`:
```markdown
# maps-cli

A read-only command-line wrapper around the native [`gosom/google-maps-scraper`](https://github.com/gosom/google-maps-scraper) binary. Returns normalized Google Maps **place data** — rating × review-volume + address + hours — for a named place. Subscription-native: no paid API, no API key, no credit card.

## Prerequisite: the native gosom binary

`maps-cli` shells out to a locally-built gosom binary (built natively for speed; the published Docker image is amd64-only and slow under emulation on Apple Silicon):

```bash
brew install go
go install github.com/gosom/google-maps-scraper@latest   # -> ~/go/bin/google-maps-scraper
```

The first real lookup downloads playwright-go's pinned Chromium into `~/Library/Caches/ms-playwright`. Override the binary path with `$MAPS_CLI_GOSOM_BIN`.

## Usage

```bash
maps-cli doctor                                            # check binary + chromium
maps-cli --json places "Luigi's Pizza" --near "Park Slope Brooklyn"
```

gosom is a **search** tool, so query loosely (`name + neighborhood`, not a full address — an exact
address resolves to a single place page with no list and fails). `maps-cli` matches the intended place
among the returned rows and returns it with a `confidence` flag and `alternatives` for disambiguation.

## Output (`--json`)

```json
{"name": "...", "rating": 4.6, "reviewCount": 2487, "address": "...", "hours": {...},
 "mapsUrl": "...", "confidence": "high", "alternatives": [...], "source": "google-maps/gosom"}
```

## Exit codes

`0` ok · `2` usage · `3` blocked/empty after retry (caller should fall back) · `4` gosom binary/Chromium missing (caller should fall back) · `1` other.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest --cov=maps_cli --cov-report=term-missing -q
.venv/bin/python -m ruff check maps_cli tests
.venv/bin/python -m ruff format --check maps_cli tests
.venv/bin/python -m mypy maps_cli
```
```

- [ ] **Step 2: Run the FULL gate and fix any findings**

```bash
cd /Users/joseph/projects/maps-cli
.venv/bin/python -m ruff format maps_cli tests
.venv/bin/python -m pytest --cov=maps_cli --cov-report=term-missing -q
.venv/bin/python -m ruff check maps_cli tests
.venv/bin/python -m ruff format --check maps_cli tests
.venv/bin/python -m mypy maps_cli
```
Expected: tests all pass, coverage high (the only likely uncovered lines are defensive branches);
ruff check "All checks passed!"; ruff format "… already formatted"; mypy "Success".

- [ ] **Step 3: Verify it works against the REAL binary (manual, not a gated test)**

```bash
.venv/bin/maps-cli doctor
.venv/bin/maps-cli --json places "Luigi's Pizza" --near "Park Slope Brooklyn"
```
Expected: `doctor` exits 0; `places` prints a record with `"name": "Luigi's Pizza"`, `"rating": 4.6`,
a `reviewCount` near 2487, `"confidence": "high"`. (Requires the gosom binary from the prerequisite;
if it is not installed, `doctor` exits 4 — that is the correct fallback signal, not a bug.)

- [ ] **Step 4: Install on PATH (mirrors how `tiktok-cli` is exposed to the skills)**

```bash
ln -sf /Users/joseph/projects/maps-cli/.venv/bin/maps-cli /Users/joseph/.local/bin/maps-cli
which maps-cli && maps-cli --version
```

- [ ] **Step 5: Commit**

```bash
cd /Users/joseph/projects/maps-cli
git add -A
git commit -q -m "docs: README + green gate; expose maps-cli on PATH

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criterion

The `maps-cli` repo's gate is green (pytest/ruff/mypy), `maps-cli doctor` and `maps-cli places` work against the real native gosom binary, and `maps-cli` is on PATH. Subsystem 2 (the `vox-maps` skill + orchestrator/`vox-browser` wiring) is then written as its own plan against this CLI's contract.
