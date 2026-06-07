# tests/test_routing.py
"""Deterministic guard on the place/logistics routing contract in the skill prose.

These assertions key on stable concept words (not exact sentences) so reasonable rewording
survives, but a silent DROP of the vox-maps-first routing or the gosom-or-chrome gate fails.
"""
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
ORCH = (SKILLS / "vox" / "SKILL.md").read_text()
MAPS = (SKILLS / "vox-maps" / "SKILL.md").read_text()


def test_vox_maps_skill_exists_and_is_stateless():
    assert (SKILLS / "vox-maps" / "SKILL.md").exists()
    assert (SKILLS / "vox-maps" / "references" / "places-playbook.md").exists()
    assert "stateless" in MAPS.lower()
    assert "maps-cli doctor" in MAPS  # capability probe


def test_orchestrator_routes_place_data_to_vox_maps():
    assert "vox-maps" in ORCH
    assert "places tier" in ORCH.lower()


def test_orchestrator_gate_is_gosom_or_chrome():
    lower = ORCH.lower()
    assert "maps-cli doctor" in ORCH  # gosom probe wired into the gate
    assert "gosom" in lower and "chrome" in lower
    assert "both" in lower  # halt only if BOTH gosom and Chrome are unavailable


def test_logistics_stays_on_browser():
    assert "logistics" in ORCH.lower()
    assert "vox-browser" in ORCH


def test_browser_is_place_data_fallback():
    browser = (SKILLS / "vox-browser" / "SKILL.md").read_text()
    assert "fallback" in browser.lower()
    assert "vox-maps" in browser  # place data is vox-maps-first


def test_vox_maps_documents_search_strategy():
    playbook = (SKILLS / "vox-maps" / "references" / "places-playbook.md").read_text()
    combined = MAPS + playbook
    assert "--search" in combined  # the anti-bot broad-query strategy is documented
