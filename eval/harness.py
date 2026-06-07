# eval/harness.py
"""Deterministic structural checks + judge-verdict parsing for the Vox eval loop."""
from __future__ import annotations

import re

_URL = re.compile(r"https?://")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)


def structural_checks(output_md: str) -> list[str]:
    """Cheap proxies for rubric items. Empty list = passes the structural layer."""
    problems: list[str] = []
    if len(_TABLE_ROW.findall(output_md)) < 2:
        problems.append("no ranked markdown table found")
    if not _URL.search(output_md):
        problems.append("no source URL (citation) found")
    if "how i built this" not in output_md.lower():
        problems.append("missing 'How I built this' methodology section")
    if "sources that failed" not in output_md.lower() and "blocked" not in output_md.lower():
        problems.append("missing a 'sources that failed' / blocked-sources statement")
    return problems


def parse_judge_verdict(text: str) -> dict[str, bool]:
    """Parse 'KEY: pass|fail' lines from the LLM judge into a dict of booleans."""
    out: dict[str, bool] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            v = val.strip().lower()
            if v in ("pass", "fail"):
                out[key.strip().lower()] = v == "pass"
    return out
