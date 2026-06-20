# vox-amazon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full Amazon product + price-history source to vox — Amazon search and current price (stateless HTTP) plus the full daily Keepa price-history (driven real Chrome), with honest CamelCamelCamel fallback.

**Architecture:** A new `amazon-cli` repo holds all Amazon *data* logic (AmzPy/curl_cffi search, CCC summary, and the Keepa `csv` decoder — pure offline transform). A new stateless `vox-amazon` skill calls it and escalates full-history finalists to the single `vox-browser` agent, which captures Keepa's WebSocket payload in your live Chrome and pipes it through `amazon-cli keepa-decode`. The `vox` orchestrator routes product/price queries and degrades to CCC when the browser is unavailable.

**Tech Stack:** Python ≥3.10, `curl_cffi`, `beautifulsoup4`+`lxml`, `amzpy`, `typer`; `pytest`+`ruff` (gate). Skills are markdown validated by `tools/validate_skills.py`. Keepa extraction uses the claude-in-chrome MCP.

**Reference:** `docs/superpowers/specs/2026-06-19-vox-amazon-design.md` (this plan implements it). Keepa protocol constants are reproduced inline where needed.

---

# Phase 1 — `amazon-cli` (new repo): stateless HTTP + Keepa decoder

All Phase-1 work happens in a NEW repo at `/Users/joseph/projects/amazon-cli`. Mirrors the `maps-cli` layout (editable `.venv`, `pytest`+`ruff` gate, fake-HTTP fixtures — no live network in tests).

### Task 1: Scaffold the repo

**Files:**
- Create: `/Users/joseph/projects/amazon-cli/pyproject.toml`
- Create: `/Users/joseph/projects/amazon-cli/amazon_cli/__init__.py`
- Create: `/Users/joseph/projects/amazon-cli/tests/__init__.py`
- Create: `/Users/joseph/projects/amazon-cli/.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "amazon-cli"
version = "0.1.0"
description = "Subscription-native Amazon search + price-history CLI for vox"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "curl_cffi>=0.7",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "amzpy>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]

[project.scripts]
amazon-cli = "amazon_cli.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["amazon_cli*"]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `amazon_cli/__init__.py`**

```python
"""amazon-cli: subscription-native Amazon search + price-history for vox."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `tests/__init__.py`** (empty file).

- [ ] **Step 4: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
*.egg-info/
```

- [ ] **Step 5: Init repo, venv, editable install**

Run:
```bash
cd /Users/joseph/projects/amazon-cli && git init -q && \
python3 -m venv .venv && \
.venv/bin/python -m pip install -q -e ".[dev]" && \
.venv/bin/python -c "import amazon_cli; print(amazon_cli.__version__)"
```
Expected: prints `0.1.0` (and pip resolves curl_cffi/amzpy/typer without error).

- [ ] **Step 6: Commit**

```bash
cd /Users/joseph/projects/amazon-cli && git add -A && \
git commit -m "chore: scaffold amazon-cli (pyproject, package, venv)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: HTTP session factory (`curl_cffi`)

**Files:**
- Create: `amazon_cli/http.py`
- Test: `tests/unit/test_http.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_http.py`:
```python
from amazon_cli import http


def test_new_session_impersonates_a_browser():
    s = http.new_session()
    # curl_cffi Session created with an impersonate target
    assert s is not None
    assert http.IMPERSONATE_TARGETS  # non-empty rotation pool


def test_pick_impersonate_rotates_by_index():
    a = http.pick_impersonate(0)
    b = http.pick_impersonate(1)
    assert a in http.IMPERSONATE_TARGETS
    assert b in http.IMPERSONATE_TARGETS
    assert a != b or len(http.IMPERSONATE_TARGETS) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joseph/projects/amazon-cli && .venv/bin/python -m pytest tests/unit/test_http.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.http`.

- [ ] **Step 3: Implement `amazon_cli/http.py`**

```python
"""curl_cffi session factory with browser TLS/JA3 impersonation + polite pacing.

Amazon and CCC fingerprint plain HTTP clients; impersonating a real browser's TLS
handshake is what lets a keyless, proxy-free GET through at hobby/local-CLI volume.
"""

from __future__ import annotations

import random
import time

from curl_cffi import requests as creq

# Rotate across a few real-browser fingerprints.
IMPERSONATE_TARGETS = ["chrome124", "chrome120", "safari17_0", "edge101"]

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def pick_impersonate(index: int) -> str:
    return IMPERSONATE_TARGETS[index % len(IMPERSONATE_TARGETS)]


def new_session(index: int = 0) -> creq.Session:
    s = creq.Session()
    s.headers.update(DEFAULT_HEADERS)
    s.impersonate = pick_impersonate(index)
    return s


def polite_sleep(rng: random.Random | None = None) -> None:
    """Randomized 2–5s delay between live requests (skip in tests via injected rng)."""
    r = rng or random
    time.sleep(r.uniform(2.0, 5.0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_http.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add amazon_cli/http.py tests/unit/test_http.py && \
git commit -m "feat: curl_cffi session factory with impersonation rotation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Amazon search HTML parser (deterministic, fixture-tested)

The curl_cffi fallback parser is the deterministically-testable search path. AmzPy is layered on top in Task 4.

**Files:**
- Create: `amazon_cli/search.py`
- Create: `tests/fixtures/amazon_search.html`
- Test: `tests/unit/test_search_parse.py`

- [ ] **Step 1: Create the fixture** `tests/fixtures/amazon_search.html` (a minimal slice of Amazon's search-results DOM — two result cards):

```html
<div class="s-main-slot">
  <div data-asin="B09XS7JWHH" data-component-type="s-search-result">
    <h2><span>Sony WH-1000XM5 Wireless Headphones</span></h2>
    <span class="a-price"><span class="a-offscreen">$278.00</span></span>
    <span class="a-icon-alt">4.2 out of 5 stars</span>
    <span class="s-underline-text">19,652</span>
  </div>
  <div data-asin="B0BDHWDR12" data-component-type="s-search-result">
    <h2><span>Apple AirPods Pro (2nd Gen)</span></h2>
    <span class="a-price"><span class="a-offscreen">$199.99</span></span>
    <span class="a-icon-alt">4.7 out of 5 stars</span>
    <span class="s-underline-text">1,204</span>
  </div>
  <div data-component-type="s-search-result"><!-- sponsored, no asin --></div>
</div>
```

- [ ] **Step 2: Write the failing test** `tests/unit/test_search_parse.py`:

```python
from pathlib import Path

from amazon_cli import search

FIX = Path(__file__).parent.parent / "fixtures" / "amazon_search.html"


def test_parse_search_html_extracts_cards():
    rows = search.parse_search_html(FIX.read_text(), domain="us")
    assert len(rows) == 2  # the asin-less card is skipped
    sony = rows[0]
    assert sony["asin"] == "B09XS7JWHH"
    assert sony["title"].startswith("Sony WH-1000XM5")
    assert sony["price"] == 278.00
    assert sony["rating"] == 4.2
    assert sony["review_count"] == 19652
    assert sony["url"] == "https://www.amazon.com/dp/B09XS7JWHH"


def test_parse_search_html_handles_missing_price():
    html = '<div data-asin="B000"><h2><span>No Price Item</span></h2></div>'
    rows = search.parse_search_html(html, domain="us")
    assert rows[0]["price"] is None
    assert rows[0]["review_count"] is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_search_parse.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.search`.

- [ ] **Step 4: Implement the parser in `amazon_cli/search.py`**

```python
"""Amazon search: AmzPy primary (Task 4) with a deterministic curl_cffi+BS4 fallback."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_DOMAIN_HOST = {"us": "www.amazon.com"}


def _num(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _price(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"[\d,]+\.\d{2}", text)
    return float(m.group(0).replace(",", "")) if m else None


def _rating(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d.]+)\s+out of", text)
    return float(m.group(1)) if m else None


def parse_search_html(html: str, *, domain: str = "us") -> list[dict]:
    """Parse an Amazon search-results page into raw candidate dicts (asin-bearing only)."""
    host = _DOMAIN_HOST.get(domain, "www.amazon.com")
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for card in soup.select("[data-asin]"):
        asin = (card.get("data-asin") or "").strip()
        if not asin:
            continue
        title_el = card.select_one("h2 span")
        price_el = card.select_one(".a-price .a-offscreen") or card.select_one(".a-price")
        rating_el = card.select_one(".a-icon-alt")
        reviews_el = card.select_one(".s-underline-text")
        rows.append({
            "asin": asin,
            "title": title_el.get_text(strip=True) if title_el else None,
            "url": f"https://{host}/dp/{asin}",
            "price": _price(price_el.get_text() if price_el else None),
            "currency": "USD",
            "rating": _rating(rating_el.get_text() if rating_el else None),
            "review_count": _num(reviews_el.get_text() if reviews_el else None),
        })
    return rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_search_parse.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add amazon_cli/search.py tests/unit/test_search_parse.py tests/fixtures/amazon_search.html && \
git commit -m "feat(search): deterministic Amazon search HTML parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: AmzPy adapter + `search()` with fallback

**Files:**
- Modify: `amazon_cli/search.py` (add `adapt_amzpy`, `search`, `_amzpy_search`, `_curl_search`)
- Test: `tests/unit/test_search.py`

- [ ] **Step 1: Write the failing test** `tests/unit/test_search.py`:

```python
from amazon_cli import search


def test_adapt_amzpy_maps_field_variants():
    # AmzPy returns its own key names; the adapter normalizes them.
    raw = {"asin": "B09XS7JWHH", "title": "Sony", "price": "$278.00",
           "rating": "4.2", "reviews_count": "19,652", "url": "/dp/B09XS7JWHH"}
    out = search.adapt_amzpy(raw, domain="us")
    assert out["asin"] == "B09XS7JWHH"
    assert out["price"] == 278.00
    assert out["rating"] == 4.2
    assert out["review_count"] == 19652
    assert out["url"] == "https://www.amazon.com/dp/B09XS7JWHH"


def test_search_falls_back_to_curl_when_amzpy_empty(monkeypatch):
    calls = {"curl": 0}
    monkeypatch.setattr(search, "_amzpy_search", lambda q, n, domain: [])
    monkeypatch.setattr(
        search, "_curl_search",
        lambda q, n, domain: (calls.__setitem__("curl", calls["curl"] + 1)
                              or [{"asin": "B1", "title": "x", "url": "u",
                                   "price": 1.0, "currency": "USD",
                                   "rating": None, "review_count": None}]),
    )
    rows = search.search("headphones", n=5, domain="us")
    assert calls["curl"] == 1
    assert rows[0]["asin"] == "B1"


def test_search_uses_amzpy_when_it_returns(monkeypatch):
    monkeypatch.setattr(
        search, "_amzpy_search",
        lambda q, n, domain: [{"asin": "B2", "title": "y", "url": "u",
                               "price": 2.0, "currency": "USD",
                               "rating": None, "review_count": None}],
    )
    monkeypatch.setattr(search, "_curl_search",
                        lambda q, n, domain: (_ for _ in ()).throw(AssertionError("should not run")))
    rows = search.search("headphones", n=5, domain="us")
    assert rows[0]["asin"] == "B2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_search.py -q`
Expected: FAIL — `AttributeError: module 'amazon_cli.search' has no attribute 'adapt_amzpy'`.

- [ ] **Step 3: Extend `amazon_cli/search.py`** — append:

```python
_AMZPY_KEYS = {
    "review_count": ("reviews_count", "reviewsCount", "ratings_count", "review_count"),
    "rating": ("rating", "stars"),
    "title": ("title", "name"),
    "price": ("price", "current_price"),
    "url": ("url", "link"),
}


def _first(raw: dict, names: tuple[str, ...]):
    for n in names:
        if raw.get(n) not in (None, ""):
            return raw[n]
    return None


def adapt_amzpy(raw: dict, *, domain: str = "us") -> dict:
    """Map an AmzPy product dict (key names vary by version) to our raw schema."""
    host = _DOMAIN_HOST.get(domain, "www.amazon.com")
    asin = raw.get("asin") or ""
    url = _first(raw, _AMZPY_KEYS["url"]) or (f"/dp/{asin}" if asin else None)
    if url and url.startswith("/"):
        url = f"https://{host}{url}"
    return {
        "asin": asin,
        "title": _first(raw, _AMZPY_KEYS["title"]),
        "url": url,
        "price": _price(str(_first(raw, _AMZPY_KEYS["price"]) or "")) ,
        "currency": "USD",
        "rating": _rating_value(_first(raw, _AMZPY_KEYS["rating"])),
        "review_count": _num(str(_first(raw, _AMZPY_KEYS["review_count"]) or "")),
    }


def _rating_value(v) -> float | None:
    if v is None:
        return None
    m = re.search(r"[\d.]+", str(v))
    return float(m.group(0)) if m else None


def _amzpy_search(query: str, n: int, domain: str) -> list[dict]:
    """Best-effort AmzPy call; returns [] on any import/runtime/throttle failure."""
    try:
        from amzpy import AmazonScraper  # type: ignore
    except Exception:
        return []
    try:
        scraper = AmazonScraper()
        products = scraper.search_products(query=query, max_pages=1) or []
    except Exception:
        return []
    return [adapt_amzpy(p, domain=domain) for p in products if p.get("asin")][:n]


def _curl_search(query: str, n: int, domain: str) -> list[dict]:
    """Fallback: fetch the search page with curl_cffi and parse it deterministically."""
    from . import http

    host = _DOMAIN_HOST.get(domain, "www.amazon.com")
    s = http.new_session()
    resp = s.get(f"https://{host}/s", params={"k": query})
    if resp.status_code != 200:
        return []
    return parse_search_html(resp.text, domain=domain)[:n]


def search(query: str, *, n: int = 10, domain: str = "us") -> list[dict]:
    """AmzPy primary; curl_cffi+BS4 fallback when AmzPy returns nothing."""
    rows = _amzpy_search(query, n, domain)
    if rows:
        return rows
    return _curl_search(query, n, domain)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_search.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Verify AmzPy's real return shape (one-time, informational)**

Run: `.venv/bin/python -c "from amzpy import AmazonScraper; import inspect; print(inspect.signature(AmazonScraper.search_products))"`
Expected: prints the real signature. If it differs from `search_products(self, query, max_pages=...)`, adjust `_amzpy_search`'s call and the `_AMZPY_KEYS` variants to match, then re-run Step 4. (The adapter already tolerates key-name variation; only the call site may need a tweak.)

- [ ] **Step 6: Commit**

```bash
git add amazon_cli/search.py tests/unit/test_search.py && \
git commit -m "feat(search): AmzPy adapter + curl_cffi fallback in search()

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CamelCamelCamel price summary

**Files:**
- Create: `amazon_cli/ccc.py`
- Create: `tests/fixtures/ccc_product.html`
- Test: `tests/unit/test_ccc.py`

- [ ] **Step 1: Create the fixture** `tests/fixtures/ccc_product.html` (a minimal slice of CCC's summary table — one row per price type):

```html
<table class="product_pane">
  <tr><th>Amazon</th>
    <td class="price_type"></td>
    <td>$278.00</td>
    <td>$248.00</td><td>Nov 29, 2025</td>
    <td>$399.99</td><td>Apr 11, 2024</td>
    <td>$312.40</td></tr>
  <tr><th>3rd Party New</th>
    <td class="price_type"></td>
    <td>$270.00</td>
    <td>$240.00</td><td>Dec 1, 2025</td>
    <td>$389.00</td><td>May 1, 2024</td>
    <td>$305.10</td></tr>
  <tr><th>3rd Party Used</th>
    <td class="price_type"></td>
    <td>$160.34</td>
    <td>$120.00</td><td>Jan 5, 2025</td>
    <td>$220.00</td><td>Jun 1, 2024</td>
    <td>$170.00</td></tr>
</table>
```

- [ ] **Step 2: Write the failing test** `tests/unit/test_ccc.py`:

```python
from pathlib import Path

from amazon_cli import ccc

FIX = Path(__file__).parent.parent / "fixtures" / "ccc_product.html"


def test_parse_ccc_summary():
    types = ccc.parse_ccc_html(FIX.read_text())
    assert types["amazon"]["current"] == 278.00
    assert types["amazon"]["lowest"]["price"] == 248.00
    assert types["amazon"]["lowest"]["date"] == "2025-11-29"
    assert types["amazon"]["highest"]["price"] == 399.99
    assert types["amazon"]["average"] == 312.40
    assert types["used"]["current"] == 160.34


def test_parse_ccc_empty_returns_no_types():
    assert ccc.parse_ccc_html("<html><body>nothing</body></html>") == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_ccc.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.ccc`.

- [ ] **Step 4: Implement `amazon_cli/ccc.py`**

```python
"""CamelCamelCamel product-page summary parser (current/low/high/avg by price type).

CCC server-renders these summary numbers in the product HTML; a curl_cffi GET returns
them with no paid proxy. This is the no-browser fallback — NOT the daily curve (Keepa).
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

_TYPE_LABELS = {
    "amazon": "amazon",
    "3rd party new": "new",
    "new": "new",
    "3rd party used": "used",
    "used": "used",
}


def _price(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"[\d,]+\.\d{2}", text)
    return float(m.group(0).replace(",", "")) if m else None


def _date(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_ccc_html(html: str) -> dict:
    """Return {type: {current, lowest:{price,date}, highest:{price,date}, average}}."""
    soup = BeautifulSoup(html, "lxml")
    out: dict = {}
    for row in soup.select("tr"):
        head = row.find("th")
        if not head:
            continue
        key = _TYPE_LABELS.get(head.get_text(strip=True).lower())
        if not key:
            continue
        tds = row.find_all("td")
        # layout: [type_cell, current, lowest_price, lowest_date, highest_price, highest_date, average]
        if len(tds) < 7:
            continue
        cells = [td.get_text(strip=True) for td in tds]
        out[key] = {
            "current": _price(cells[1]),
            "lowest": {"price": _price(cells[2]), "date": _date(cells[3])},
            "highest": {"price": _price(cells[4]), "date": _date(cells[5])},
            "average": _price(cells[6]),
        }
    return out


def fetch_ccc(asin: str) -> tuple[int, str]:
    """Live GET of the CCC product page. Returns (status_code, html)."""
    from . import http

    s = http.new_session()
    resp = s.get(f"https://camelcamelcamel.com/product/{asin}")
    return resp.status_code, resp.text
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_ccc.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add amazon_cli/ccc.py tests/unit/test_ccc.py tests/fixtures/ccc_product.html && \
git commit -m "feat(price): CamelCamelCamel summary parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Keepa `csv` decoder (pure offline transform)

**Files:**
- Create: `amazon_cli/keepa.py`
- Create: `tests/fixtures/keepa_product.json` (a SMALL hand-authored `basicProducts` payload — real captured payloads are large; this one carries the exact structure)
- Test: `tests/unit/test_keepa.py`

- [ ] **Step 1: Create the fixture** `tests/fixtures/keepa_product.json`. The `csv[0]` points below decode to known dates via `(t + 21564000) * 60000` ms: `t=7900000`→2026-01-08, `t=8000000`→2026-03-18, and a `-1` value = no offer.

```json
{"basicProducts": [{
  "asin": "B09XS7JWHH",
  "title": "Sony WH-1000XM5",
  "csv": [
    [7900000, 27800, 8000000, 24800, 8100000, -1],
    [7900000, 27000, 8100000, 26000],
    [7900000, 16034],
    null,
    [7900000, 39999]
  ]
}]}
```

- [ ] **Step 2: Write the failing test** `tests/unit/test_keepa.py`:

```python
import json
from pathlib import Path

from amazon_cli import keepa

FIX = Path(__file__).parent.parent / "fixtures" / "keepa_product.json"


def test_keepa_minute_to_date():
    assert keepa.keepa_minute_to_date(8000000) == "2026-03-18"


def test_decode_product_amazon_series():
    payload = json.loads(FIX.read_text())
    out = keepa.decode_product(payload["basicProducts"][0])
    amz = out["series"]["amazon"]
    assert amz[0] == {"date": keepa.keepa_minute_to_date(7900000), "price": 278.00}
    assert amz[1] == {"date": keepa.keepa_minute_to_date(8000000), "price": 248.00}
    # the -1 point is dropped (no offer), not rendered as a price
    assert all(p["price"] is not None for p in amz)
    assert out["current"]["amazon"] == 248.00  # last real price
    assert out["stats"]["amazon"]["lowest"] == 248.00
    assert out["stats"]["amazon"]["highest"] == 278.00


def test_decode_handles_null_and_used_series():
    payload = json.loads(FIX.read_text())
    out = keepa.decode_product(payload["basicProducts"][0])
    assert "salesRank" not in out["series"]  # index 3 was null -> skipped
    assert out["series"]["used"][0]["price"] == 160.34
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_keepa.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.keepa`.

- [ ] **Step 4: Implement `amazon_cli/keepa.py`**

```python
"""Decode Keepa's `csv` price arrays into clean date->price series.

Input is the `basicProducts[0]` object captured from Keepa's WebSocket (zstd JSON);
this module is a PURE offline transform — see the vox-browser playbook for capture.

Keepa-minute epoch: minutes since 2011-01-01 UTC (NOT unix). Prices are in cents;
value -1 means "no offer" at that time. Indices 0/1/2/4 are clean [time, price] pairs.
"""

from __future__ import annotations

from datetime import datetime, timezone

KEEPA_EPOCH_OFFSET_MIN = 21564000  # minutes from unix epoch to 2011-01-01

# csv index -> output series name (the clean 2-tuple price series we expose)
PRICE_INDEX = {0: "amazon", 1: "new", 2: "used", 4: "list"}


def keepa_minute_to_date(t: int) -> str:
    unix_ms = (t + KEEPA_EPOCH_OFFSET_MIN) * 60000
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).date().isoformat()


def _decode_pairs(arr: list) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(arr) - 1, 2):
        t, v = arr[i], arr[i + 1]
        if v == -1:  # no offer at this time
            continue
        out.append({"date": keepa_minute_to_date(t), "price": round(v / 100, 2)})
    return out


def decode_product(product: dict) -> dict:
    csv = product.get("csv") or []
    series: dict[str, list] = {}
    for idx, name in PRICE_INDEX.items():
        if idx < len(csv) and isinstance(csv[idx], list) and len(csv[idx]) >= 2:
            pts = _decode_pairs(csv[idx])
            if pts:
                series[name] = pts
    current = {name: pts[-1]["price"] for name, pts in series.items()}
    stats = {
        name: {
            "lowest": min(p["price"] for p in pts),
            "highest": max(p["price"] for p in pts),
            "average": round(sum(p["price"] for p in pts) / len(pts), 2),
        }
        for name, pts in series.items()
    }
    return {
        "asin": product.get("asin"),
        "title": product.get("title"),
        "source": "keepa",
        "series": series,
        "current": current,
        "stats": stats,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_keepa.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add amazon_cli/keepa.py tests/unit/test_keepa.py tests/fixtures/keepa_product.json && \
git commit -m "feat(keepa): pure csv->series decoder (Keepa-minute epoch)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `normalize` — stable schemas + honesty status flags

**Files:**
- Create: `amazon_cli/normalize.py`
- Test: `tests/unit/test_normalize.py`

- [ ] **Step 1: Write the failing test** `tests/unit/test_normalize.py`:

```python
from amazon_cli import normalize


def test_normalize_candidate_sets_status_flags():
    raw = {"asin": "B1", "title": "x", "url": "u", "price": None,
           "currency": "USD", "rating": 4.2, "review_count": None}
    out = normalize.candidate(raw)
    assert out["priceStatus"] == "unavailable"  # None price -> NOT a silent 0
    assert out["price"] is None
    assert out["reviewCountStatus"] == "unavailable"
    assert out["reviewCount"] is None


def test_normalize_candidate_ok_status():
    raw = {"asin": "B1", "title": "x", "url": "u", "price": 12.0,
           "currency": "USD", "rating": 4.2, "review_count": 50}
    out = normalize.candidate(raw)
    assert out["priceStatus"] == "ok"
    assert out["reviewCountStatus"] == "ok"
    assert out["reviewCount"] == 50


def test_search_result_envelope():
    env = normalize.search_result("hp", "us", [{"asin": "B1", "title": "x", "url": "u",
        "price": 1.0, "currency": "USD", "rating": None, "review_count": None}], blocked=False)
    assert env["status"] == "ok"
    assert env["candidates"][0]["asin"] == "B1"
    assert normalize.search_result("hp", "us", [], blocked=True)["status"] == "blocked"
    assert normalize.search_result("hp", "us", [], blocked=False)["status"] == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.normalize`.

- [ ] **Step 3: Implement `amazon_cli/normalize.py`**

```python
"""Stable output schemas with explicit status flags.

Honesty rule (the maps-cli review-volume lesson): a missing price/review-count is
`*Status: "unavailable"`, never a silent 0; a bot-block is surfaced, never an empty success.
"""

from __future__ import annotations


def _status(value) -> str:
    return "ok" if value not in (None, "") else "unavailable"


def candidate(raw: dict) -> dict:
    return {
        "asin": raw.get("asin"),
        "title": raw.get("title"),
        "url": raw.get("url"),
        "price": raw.get("price"),
        "currency": raw.get("currency", "USD"),
        "priceStatus": _status(raw.get("price")),
        "rating": raw.get("rating"),
        "reviewCount": raw.get("review_count"),
        "reviewCountStatus": _status(raw.get("review_count")),
    }


def search_result(query: str, domain: str, raws: list[dict], *, blocked: bool) -> dict:
    if blocked:
        status = "blocked"
    elif raws:
        status = "ok"
    else:
        status = "partial"
    return {
        "query": query,
        "domain": domain,
        "status": status,
        "candidates": [candidate(r) for r in raws],
    }


def price_result(asin: str, types: dict, *, blocked: bool) -> dict:
    return {
        "asin": asin,
        "source": "camelcamelcamel",
        "url": f"https://camelcamelcamel.com/product/{asin}",
        "status": "blocked" if blocked else ("ok" if types else "unavailable"),
        "types": types,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_normalize.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add amazon_cli/normalize.py tests/unit/test_normalize.py && \
git commit -m "feat: normalize layer with explicit status flags

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `doctor` capability probe

**Files:**
- Create: `amazon_cli/doctor.py`
- Test: `tests/unit/test_doctor.py`

- [ ] **Step 1: Write the failing test** `tests/unit/test_doctor.py`:

```python
from amazon_cli import doctor


def test_probe_reports_components():
    rep = doctor.probe()
    assert "curl_cffi" in rep
    assert "amzpy" in rep
    assert isinstance(rep["ok"], bool)


def test_exit_code_ok_vs_unavailable():
    assert doctor.exit_code({"ok": True}) == 0
    assert doctor.exit_code({"ok": False}) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_doctor.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.doctor`.

- [ ] **Step 3: Implement `amazon_cli/doctor.py`**

```python
"""Capability probe. Exit codes mirror maps-cli: 0 = ok, 4 = unavailable."""

from __future__ import annotations

import importlib.util


def _present(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def probe() -> dict:
    curl = _present("curl_cffi")
    amzpy = _present("amzpy")
    bs4 = _present("bs4")
    return {"curl_cffi": curl, "amzpy": amzpy, "bs4": bs4, "ok": curl and bs4}


def exit_code(report: dict) -> int:
    return 0 if report.get("ok") else 4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_doctor.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add amazon_cli/doctor.py tests/unit/test_doctor.py && \
git commit -m "feat: doctor capability probe (exit 0 ok / 4 unavailable)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: CLI wiring (`typer`) — `search`, `price`, `doctor`, `keepa-decode`

**Files:**
- Create: `amazon_cli/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test** `tests/unit/test_cli.py`:

```python
import json

from typer.testing import CliRunner

from amazon_cli import cli

runner = CliRunner()


def test_search_command_outputs_json(monkeypatch):
    monkeypatch.setattr(cli.search, "search",
                        lambda q, n, domain: [{"asin": "B1", "title": "x", "url": "u",
                            "price": 1.0, "currency": "USD", "rating": None, "review_count": None}])
    res = runner.invoke(cli.app, ["search", "headphones", "--n", "3"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["status"] == "ok"
    assert data["candidates"][0]["asin"] == "B1"


def test_price_command_blocked(monkeypatch):
    monkeypatch.setattr(cli.ccc, "fetch_ccc", lambda asin: (503, ""))
    res = runner.invoke(cli.app, ["price", "B09XS7JWHH"])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["status"] == "blocked"


def test_doctor_exit_code(monkeypatch):
    monkeypatch.setattr(cli.doctor, "probe", lambda: {"ok": True, "curl_cffi": True,
                                                      "amzpy": True, "bs4": True})
    res = runner.invoke(cli.app, ["doctor"])
    assert res.exit_code == 0


def test_keepa_decode_reads_payload(tmp_path):
    p = tmp_path / "k.json"
    p.write_text(json.dumps({"basicProducts": [{"asin": "B1", "title": "t",
        "csv": [[7900000, 27800]]}]}))
    res = runner.invoke(cli.app, ["keepa-decode", str(p)])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["current"]["amazon"] == 278.00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: amazon_cli.cli`.

- [ ] **Step 3: Implement `amazon_cli/cli.py`**

```python
"""amazon-cli command surface (typer). All commands print JSON to stdout."""

from __future__ import annotations

import json
import sys

import typer

from . import ccc, doctor, keepa, normalize, search

app = typer.Typer(add_completion=False, help="Subscription-native Amazon data for vox.")


@app.command("search")
def search_cmd(query: str, n: int = typer.Option(10, "--n"),
               domain: str = typer.Option("us", "--domain")):
    """Search Amazon -> ranked candidate products as JSON."""
    try:
        raws = search.search(query, n=n, domain=domain)
        env = normalize.search_result(query, domain, raws, blocked=False)
    except Exception:
        env = normalize.search_result(query, domain, [], blocked=True)
    typer.echo(json.dumps(env, indent=2))


@app.command("price")
def price_cmd(asin: str, domain: str = typer.Option("us", "--domain")):
    """CamelCamelCamel current/low/high/avg summary as JSON."""
    try:
        status, html = ccc.fetch_ccc(asin)
        if status != 200:
            env = normalize.price_result(asin, {}, blocked=True)
        else:
            env = normalize.price_result(asin, ccc.parse_ccc_html(html), blocked=False)
    except Exception:
        env = normalize.price_result(asin, {}, blocked=True)
    typer.echo(json.dumps(env, indent=2))


@app.command("keepa-decode")
def keepa_decode_cmd(path: str = typer.Argument(..., help="File with captured basicProducts JSON, or - for stdin")):
    """Decode a captured Keepa WS payload -> date->price series JSON."""
    raw = sys.stdin.read() if path == "-" else open(path).read()
    payload = json.loads(raw)
    product = payload["basicProducts"][0] if "basicProducts" in payload else payload
    typer.echo(json.dumps(keepa.decode_product(product), indent=2))


@app.command("doctor")
def doctor_cmd():
    """Capability probe; exits 0 (ok) or 4 (unavailable)."""
    rep = doctor.probe()
    typer.echo(json.dumps(rep, indent=2))
    raise typer.Exit(code=doctor.exit_code(rep))


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the FULL gate**

Run: `cd /Users/joseph/projects/amazon-cli && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check amazon_cli tests`
Expected: all tests pass; ruff reports `All checks passed!`. Fix any lint inline (unused imports, line length) and re-run.

- [ ] **Step 6: Commit**

```bash
git add amazon_cli/cli.py tests/unit/test_cli.py && \
git commit -m "feat: typer CLI (search, price, keepa-decode, doctor)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: README + create the private GitHub repo

**Files:**
- Create: `/Users/joseph/projects/amazon-cli/README.md`

- [ ] **Step 1: Write `README.md`** documenting: purpose (vox Amazon source), the no-paid-API/no-proxy stance, install (`python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`), the four commands with example JSON, the Keepa-decode pairing with vox-browser, and the gate command. Keep it factual and short.

- [ ] **Step 2: Commit**

```bash
git add README.md && git commit -m "docs: amazon-cli README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: Create the private GitHub repo (HELD — ask the user before running)**

The user controls when repos are published. When approved:
```bash
cd /Users/joseph/projects/amazon-cli && gh repo create amazon-cli --private --source=. --remote=origin && git push -u origin main
```
Expected: repo created private, `main` pushed. **Do not run without explicit user approval.**

---

# Phase 2 — `vox-browser` Keepa price-history playbook

### Task 11: Capture a real Keepa payload as a parity fixture

**Files:**
- Create: `/Users/joseph/projects/amazon-cli/tests/fixtures/keepa_real_sample.json`
- Test: `tests/unit/test_keepa_real.py`

- [ ] **Step 1: Capture (manual, via the claude-in-chrome MCP)** — drive the user's Chrome to `keepa.com/#!product/1-B09B8V1LZ3`, tee `window.fzstd.decompress`, hash-navigate to force a fetch, and save the captured `{"basicProducts":[...]}` JSON to the fixture path. (This is the exact procedure proven on 2026-06-19; see the playbook prose in Task 12.) Trim to one product to keep the file reasonable.

- [ ] **Step 2: Write a parity test** `tests/unit/test_keepa_real.py`:

```python
import json
from pathlib import Path

import pytest

from amazon_cli import keepa

FIX = Path(__file__).parent.parent / "fixtures" / "keepa_real_sample.json"


@pytest.mark.skipif(not FIX.exists(), reason="real sample not captured")
def test_real_payload_decodes_to_sane_series():
    payload = json.loads(FIX.read_text())
    out = keepa.decode_product(payload["basicProducts"][0])
    assert out["series"].get("amazon"), "expected an Amazon series"
    pts = out["series"]["amazon"]
    assert len(pts) > 10
    # dates are ISO and ascending-ish; prices are positive dollars
    assert all(p["price"] > 0 for p in pts)
    assert all(len(p["date"]) == 10 for p in pts)
    assert out["current"]["amazon"] == pts[-1]["price"]
```

- [ ] **Step 3: Run it**

Run: `cd /Users/joseph/projects/amazon-cli && .venv/bin/python -m pytest tests/unit/test_keepa_real.py -q`
Expected: PASS (1 passed) once the fixture exists. This locks the decoder against a REAL payload, so any future Keepa layout change fails loudly here.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/keepa_real_sample.json tests/unit/test_keepa_real.py && \
git commit -m "test(keepa): parity test against a real captured payload

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 12: Write the `vox-browser` Keepa playbook

**Files:**
- Modify: `/Users/joseph/projects/vox/skills/vox-browser/SKILL.md`

- [ ] **Step 1: Add a `## Keepa price-history playbook` section** with this exact content (adapt headings to the file's style):

  - **When:** invoked by the orchestrator with one or more escalated `keepa-history(asin, domainId)` tags.
  - **Steps:**
    1. `tabs_context_mcp` / create a tab; `navigate` to `https://keepa.com/#!product/{domainId}-{ASIN}` (domainId 1 = amazon.com US). Wait ~4s.
    2. Inject the tee (run via `javascript_tool`):
       ```js
       window.__dec = window.__dec || [];
       if (window.fzstd && !window.fzstd.decompress.__teed) {
         const o = window.fzstd.decompress;
         const w = function(...a){ const r=o.apply(this,a);
           try{ const s=new TextDecoder().decode(r);
             if(s[0]==='{') window.__dec.push(s); }catch(e){} return r; };
         w.__teed = true; window.fzstd.decompress = w;
       }
       ```
    3. For each target ASIN, `javascript_tool`: `location.hash = '#!product/{domainId}-{ASIN}'`, wait ~3s, then read the last `window.__dec` entry whose JSON `.asin` matches.
    4. Save that raw JSON to a temp file and decode with the single tested decoder:
       `amazon-cli keepa-decode <tmpfile>` (via Bash) → `{current, series, stats}`.
    5. Put the decoded current/stats (and, if asked, the series) into the digest, cited to the keepa.com product URL.
  - **Safety (HARD):** if keepa.com presents an interactive **Cloudflare Turnstile** challenge (not the silent pass), or any CAPTCHA, **do not solve it** — mark `status: blocked` and return so the orchestrator degrades to CCC. Never enter Keepa credentials. Read-only.
  - **Note:** the data rides a WebSocket to `push.keepa.com` (no XHR); the Amazon-page Keepa chart is a cross-origin iframe — do not try to read it from the Amazon DOM. Decode logic lives only in `amazon-cli keepa-decode`.

- [ ] **Step 2: Validate**

Run: `cd /Users/joseph/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for every skill including `vox-browser`.

- [ ] **Step 3: Commit (HELD until end-of-phase review — see Task 17).**

---

# Phase 3 — `vox-amazon` skill + `vox` routing

### Task 13: Create the `vox-amazon` skill

**Files:**
- Create: `/Users/joseph/projects/vox/skills/vox-amazon/SKILL.md`
- Create symlink: `~/.claude/skills/vox-amazon` → `…/vox/skills/vox-amazon`

- [ ] **Step 1: Write `skills/vox-amazon/SKILL.md`** with frontmatter (`name: vox-amazon`, a `description:` matching the other `vox-*` skills' voice) and a body covering:
  - Role: stateless vox source (parallel-safe like vox-maps); owns no browser.
  - Capability-probe: `amazon-cli doctor` (exit 0 available; 4 → declare lost coverage, degrade, never fake).
  - Flow: category query → `amazon-cli search "<q>" --n N`; named product/ASIN/URL → resolve ASIN directly. Then `amazon-cli price <ASIN>` per finalist for current/CCC summary.
  - Escalation: for finalists needing the full daily curve, emit a `needs-browser: keepa-history(asin=<ASIN>, domainId=1)` line in the digest (the orchestrator routes it to the single vox-browser agent).
  - Honesty: render `priceStatus`/`reviewCountStatus == unavailable` as `⚠`, never 0; `status: blocked` → partial set, disclosed; cite every figure to the Amazon or CCC URL.
  - Returns the standard Vox digest (per `references/digest-contract.md`).

- [ ] **Step 2: Create the symlink**

Run:
```bash
ln -s /Users/joseph/projects/vox/skills/vox-amazon ~/.claude/skills/vox-amazon && \
ls -l ~/.claude/skills/vox-amazon
```
Expected: symlink resolves to the vox repo path.

- [ ] **Step 3: Validate**

Run: `cd /Users/joseph/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` including `vox-amazon`.

- [ ] **Step 4: Commit (HELD — Task 17).**

### Task 14: Wire `vox-amazon` into the orchestrator

**Files:**
- Modify: `/Users/joseph/projects/vox/skills/vox/SKILL.md`

- [ ] **Step 1: Add a `## Product & price-history tier` section** (mirroring the existing "Places & browser tier"):
  - **Route** product / "good price?" / "price history" / shopping sub-questions to `vox-amazon` (Wave 1, stateless, parallel with reddit/x/web). Mark which finalists NEED the full daily curve.
  - **Availability gate:** `amazon-cli doctor` ok → dispatch `vox-amazon`. Full-history needed + Chrome up → escalate `keepa-history(...)` tags to the single `vox-browser` agent. Full-history needed + no Chrome → degrade to CCC summary with a confidence penalty + a one-line "no daily-curve coverage" note. `amazon-cli` exit 4 → declare lost Amazon coverage, run the HTTP three.
  - **Single-browser coordination:** if a run needs both logistics AND Keepa history, the one `vox-browser` agent serves both serially (never a second browser agent).
  - **No CAPTCHA solving** (restate the hard rule): bot-check/Turnstile challenge → blocked → degrade.

- [ ] **Step 2: Add the dispatch note to the Wave-1 step** — `vox-amazon` is a SKILL, dispatch as `subagent_type: general-purpose` (like vox-maps), told to invoke the `vox-amazon` skill first; pin `model: opus`.

- [ ] **Step 3: Validate**

Run: `cd /Users/joseph/projects/vox && .venv/bin/python tools/validate_skills.py skills`
Expected: `[ok]` for `vox`.

- [ ] **Step 4: Commit (HELD — Task 17).**

### Task 15: Update the output template

**Files:**
- Modify: `/Users/joseph/projects/vox/skills/vox/references/output-template.md`

- [ ] **Step 1: Add a price-history element** to the finalist rendering: a "current vs typical" read (current price vs Keepa/CCC average) with per-figure provenance tag (`keepa ✓` / `ccc-summary ⚠` / `amzpy`) and confidence, honoring the citation + honesty gates.

- [ ] **Step 2: Validate** (`validate_skills.py skills` → `[ok]`).

- [ ] **Step 3: Commit (HELD — Task 17).**

### Task 16: Live-rigor validation run

- [ ] **Step 1: Run a real vox query** that exercises the full path, e.g. *"is the Sony WH-1000XM5 a good price right now, and what's its price history?"* Confirm: `vox-amazon` runs `amazon-cli search`/`price`; a finalist gets escalated; `vox-browser` captures Keepa and `keepa-decode` returns a real series; the render shows current-vs-typical with provenance; CCC degrade fires cleanly if Keepa is blocked.

- [ ] **Step 2: Note any gaps** discovered in a short `docs/2026-06-19-vox-amazon-live-rigor.md` (what worked, what degraded, any fixes), mirroring the prior usage-fix live-rigor section.

### Task 17: Release commits for the vox repo (HELD — confirm with user)

The Phase-2/3 vox edits (Tasks 12–16) were committed-held. When the user approves:

- [ ] **Step 1:** Commit the vox changes in logical chunks (vox-browser playbook; vox-amazon skill; vox routing + template; live-rigor doc) with the standard trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01RCEcQiAbYfuKXtseNKLnnS
  ```
- [ ] **Step 2:** Push only when the user says so.

---

## Self-review notes (author)

- **Spec coverage:** amazon-cli search+CCC+doctor+normalize (Tasks 2–10) ✓; Keepa decode + parity fixture (Tasks 6, 11) ✓; vox-browser playbook (Task 12) ✓; vox-amazon skill (Task 13) ✓; orchestrator routing + tier gate + degrade (Task 14) ✓; output template (Task 15) ✓; testing strategy (fake-HTTP units + real-payload parity + validate_skills + live-rigor) ✓; phasing ✓; no-CAPTCHA-solving safety restated in Tasks 12 & 14 ✓.
- **Type consistency:** raw dicts use `review_count`/`price`/`rating`; `normalize.candidate` renames to `reviewCount`/`reviewCountStatus`; `keepa.decode_product` returns `{series, current, stats}` consumed verbatim by `keepa-decode`. Search engines (`_amzpy_search`/`_curl_search`) and `search()` signatures match the CLI call site.
- **No placeholders:** every code step carries complete code; the two prose-heavy skill tasks (12–15) are markdown content with exact section names and the verbatim tee snippet.
- **Held commits:** repo publication (Task 10 Step 3) and all vox commits (Task 17) require explicit user approval, per the standing commit/push rule.
```
