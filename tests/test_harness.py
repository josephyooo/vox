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
