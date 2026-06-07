# tests/test_goldens.py
from pathlib import Path

GOLDENS = sorted((Path(__file__).resolve().parents[1] / "eval" / "goldens").glob("*.md"))


def test_goldens_exist():
    assert len(GOLDENS) >= 3


def test_each_golden_has_required_sections():
    for g in GOLDENS:
        text = g.read_text()
        for section in ("## Query", "## Family", "## Expectations"):
            assert section in text, f"{g.name} missing {section}"
