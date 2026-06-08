# tests/test_video_agy.py
"""Contract guard on the vox-video agy entity cross-check.

Keyed on stable concept words (not exact sentences) so reasonable rewording survives,
but a silent DROP of any agy guardrail fails the gate.
"""
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1] / "skills" / "vox-video"
# Concatenate all prose in the vox-video skill (SKILL.md + references/*.md), lowercased.
TEXT = "\n".join(p.read_text() for p in sorted(VIDEO.rglob("*.md"))).lower()


def test_agy_crosscheck_reference_exists():
    assert (VIDEO / "references" / "agy-crosscheck.md").exists()


def test_agy_is_supplementary_entity_layer_crosscheck():
    assert "agy" in TEXT
    assert "cross-check" in TEXT
    assert "entity" in TEXT
    assert "supplementary" in TEXT
    # the mw+vision stack stays the source of record
    assert "source-of-record" in TEXT


def test_no_phantom_quotes_still_binds():
    # R-A3: agy never creates a spoken-claim quote
    assert "phantom" in TEXT
    assert "spoken" in TEXT


def test_agy_unavailable_is_non_halting():
    assert "unavailable" in TEXT
    assert "never a halt" in TEXT


def test_three_robustness_guards_documented():
    # 1) hard external timeout  2) success-by-output-not-exit-code  3) retry-once
    assert "timeout" in TEXT
    assert "exit code" in TEXT
    assert "retry" in TEXT


def test_skill_entrypoint_and_playbooks_wire_agy():
    skill = (VIDEO / "SKILL.md").read_text().lower()
    ingest = (VIDEO / "references" / "ingest-playbook.md").read_text().lower()
    # the skill entrypoint points at the cross-check and its reference
    assert "agy" in skill
    assert "agy-crosscheck" in skill
    # the ingest playbook documents the per-video agy stage + status field
    assert "agy" in ingest
    assert "agy.md" in ingest
