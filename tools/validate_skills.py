# tools/validate_skills.py
"""Validate Vox skill directories: frontmatter, name match, local-link resolution."""
from __future__ import annotations

import re
import sys
from pathlib import Path

_LOCAL_LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def validate_skill(skill_dir: Path) -> list[str]:
    problems: list[str] = []
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return [f"{skill_dir.name}: SKILL.md is missing"]
    text = md.read_text()
    fm = _parse_frontmatter(text)
    if not fm:
        problems.append(f"{skill_dir.name}: SKILL.md has no valid --- frontmatter ---")
    if not fm.get("name"):
        problems.append(f"{skill_dir.name}: frontmatter is missing a non-empty 'name'")
    elif fm["name"] != skill_dir.name:
        problems.append(
            f"{skill_dir.name}: frontmatter name '{fm['name']}' must match directory name"
        )
    if not fm.get("description"):
        problems.append(f"{skill_dir.name}: frontmatter is missing a non-empty 'description'")
    for rel in _LOCAL_LINK.findall(text):
        target = (skill_dir / rel.split("#", 1)[0]).resolve()
        if not target.exists():
            problems.append(f"{skill_dir.name}: link target does not exist: {rel}")
    return problems


def validate_all(skills_root: Path) -> dict[str, list[str]]:
    return {
        d.name: validate_skill(d)
        for d in sorted(skills_root.iterdir())
        if d.is_dir() and not d.name.startswith(".")
    }


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("skills")
    results = validate_all(root)
    bad = {k: v for k, v in results.items() if v}
    for name, probs in results.items():
        mark = "FAIL" if probs else "ok"
        print(f"[{mark}] {name}")
        for p in probs:
            print(f"    - {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
