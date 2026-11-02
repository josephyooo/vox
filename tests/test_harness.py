# tests/test_harness.py
from eval.harness import structural_checks, parse_judge_verdict

GOOD = """
## How I built this
Reddit + web.
| Item | Detail | Source | Conf |
|---|---|---|---|
| Shoe A | great | https://example.com/a | ✅ |
## Sources that failed
none
My call: Shoe A.
"""

BAD = "Here are some shoes: Shoe A, Shoe B. Trust me."

# A compliant run that discloses source coverage with a natural-language heading
# ("returned no signal") instead of the literal phrase "sources that failed".
GOOD_VARIANT = """
## How I built this
Reddit + X + web.
| Item | Detail | Source | Conf |
|---|---|---|---|
| Shoe A | great | https://example.com/a | ✅ |
### Sources that returned no signal
X had 0 results for the budget query; all web fetches returned cleanly.
My call: Shoe A.
"""

# A table cell that merely mentions "blocked" is not a source-coverage disclosure.
BLOCKED_IN_CELL = """
## How I built this
Reddit + web.
| Item | Detail | Source | Conf |
|---|---|---|---|
| Shoe A | the store blocked returns | https://example.com/a | ✅ |
My call: Shoe A.
"""

# An honest no-signal answer for an obscure topic: no table, no URL.
SPARSE = """
## How I built this
Reddit + X + web, searched for the product name and close variants.
The evidence is thin: no reviews, specs, or discussion turned up anywhere.
### Sources that failed / no-signal
Reddit, X and web all returned no results for this product.
"""


def test_good_output_passes_structural_checks():
    assert structural_checks(GOOD) == []


def test_failed_sources_disclosure_accepts_natural_variants():
    assert structural_checks(GOOD_VARIANT) == []


def test_bad_output_flags_missing_table_and_citation():
    problems = structural_checks(BAD)
    assert any("table" in p for p in problems)
    assert any("source URL" in p for p in problems)


def test_parse_judge_verdict_reads_pass_fail():
    text = "ROUTING: pass\nCITATIONS: pass\nCORROBORATION: fail\nFABRICATION: pass\nVERDICT: fail"
    v = parse_judge_verdict(text)
    assert v["corroboration"] is False
    assert v["verdict"] is False
    assert v["routing"] is True


def test_blocked_in_table_cell_is_not_a_disclosure():
    problems = structural_checks(BLOCKED_IN_CELL)
    assert any("source-coverage" in p for p in problems)


def test_sparse_honest_answer_passes_in_sparse_mode():
    assert structural_checks(SPARSE, sparse=True) == []
    assert structural_checks(SPARSE) != []  # default mode still demands table + URL
