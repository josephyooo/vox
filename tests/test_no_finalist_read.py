# tests/test_no_finalist_read.py
"""Contract guard on the vox no-finalist read path.

Keyed on stable concept words (not exact sentences) so reasonable rewording survives,
but a silent DROP of Skeleton B, the conflict path, or any step-7 honesty rule fails the gate.
"""
from pathlib import Path

VOX = Path(__file__).resolve().parents[1] / "skills" / "vox"
GOLDENS = Path(__file__).resolve().parents[1] / "eval" / "goldens"

# Whole-skill concatenation, lowercased (cross-file concept presence).
TEXT = "\n".join(p.read_text() for p in sorted(VOX.rglob("*.md"))).lower()
# Per-file views (lowercased) for targeted assertions.
OUT = (VOX / "references" / "output-template.md").read_text().lower()
DIGEST = (VOX / "references" / "digest-contract.md").read_text().lower()
RUBRIC = (VOX / "references" / "rubric-templates.md").read_text().lower()
SKILL = (VOX / "SKILL.md").read_text().lower()


def test_two_named_skeletons_exist():
    assert "skeleton a" in TEXT
    assert "skeleton b" in TEXT
    assert "no rankable finalist" in TEXT


def test_skeleton_b_body_sections():
    assert "core facts" in OUT
    assert "| sources" in OUT  # the `Sources` column header in the claim table
    assert "sentiment & consensus" in OUT
    assert "themes & dissent" in OUT


def test_warn_mark_covers_conflicting_unverified():
    # ⚠️ no longer means only closure/budget risk
    assert "conflicting" in OUT or "unverified" in OUT


def test_legend_carry_forward_rules():
    assert "no silent confidence upgrade" in OUT
    assert "per-claim sources" in OUT


def test_digest_has_conflicts_slot():
    assert "conflicts / disagreements across fetches" in DIGEST
    assert "likely extraction error" in DIGEST


def test_rubric_families_name_skeletons():
    assert "skeleton a" in RUBRIC
    assert "skeleton b" in RUBRIC
    assert "record the chosen skeleton" in RUBRIC


def test_step15_records_skeleton():
    assert "record the output skeleton" in SKILL


def test_step5_conflict_trigger_and_no_finalist_branch():
    assert "conflict trigger" in SKILL
    assert "no-finalist branch" in SKILL
    assert "does not clear" in SKILL          # 2+ promotes but does NOT clear a conflict
    assert "sources disagree" in SKILL        # the disclose-don't-pick render
    assert "intentionally skipped" in SKILL   # the no-finalist Wave-2 decision is stated


def test_step7_four_honesty_rules():
    assert "no silent confidence upgrade" in SKILL
    assert "per-claim sources" in SKILL
    assert "quote provenance" in SKILL
    assert "paraphrase via" in SKILL
    assert "links all n" in SKILL  # "Corroboration count links all N"
