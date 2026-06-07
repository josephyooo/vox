# tests/test_validate_skills.py
from pathlib import Path
from tools.validate_skills import validate_skill


def _make_skill(tmp_path: Path, name: str, frontmatter: str, body: str = "Body.") -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n")
    return d


def test_valid_skill_has_no_problems(tmp_path):
    d = _make_skill(tmp_path, "vox-x", "name: vox-x\ndescription: Drive bird.")
    assert validate_skill(d) == []


def test_missing_skill_md_is_reported(tmp_path):
    d = tmp_path / "vox-x"
    d.mkdir()
    problems = validate_skill(d)
    assert any("SKILL.md" in p for p in problems)


def test_missing_description_is_reported(tmp_path):
    d = _make_skill(tmp_path, "vox-x", "name: vox-x")
    problems = validate_skill(d)
    assert any("description" in p for p in problems)


def test_name_must_match_dir(tmp_path):
    d = _make_skill(tmp_path, "vox-x", "name: wrong\ndescription: x.")
    assert any("name" in p and "match" in p for p in validate_skill(d))


def test_unresolved_local_link_is_reported(tmp_path):
    d = _make_skill(
        tmp_path, "vox", "name: vox\ndescription: d.", body="See [c](references/missing.md)."
    )
    assert any("missing.md" in p for p in validate_skill(d))


def test_resolved_local_link_is_ok(tmp_path):
    d = _make_skill(
        tmp_path, "vox", "name: vox\ndescription: d.", body="See [c](references/here.md)."
    )
    (d / "references").mkdir()
    (d / "references" / "here.md").write_text("ok")
    assert validate_skill(d) == []
