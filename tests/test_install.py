# tests/test_install.py
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run_install(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(REPO / "install.sh")],
        env={"VOX_SKILLS_TARGET": str(target), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )


def test_install_symlinks_each_skill(tmp_path):
    target = tmp_path / "skills"
    res = _run_install(target)
    assert res.returncode == 0, res.stderr
    link = target / "vox"
    assert link.is_symlink()
    assert link.resolve() == (REPO / "skills" / "vox").resolve()


def test_install_is_idempotent(tmp_path):
    target = tmp_path / "skills"
    assert _run_install(target).returncode == 0
    res2 = _run_install(target)
    assert res2.returncode == 0, res2.stderr
    assert (target / "vox").is_symlink()


def test_install_preserves_real_dir_and_warns(tmp_path):
    target = tmp_path / "skills"
    real = target / "vox"
    real.mkdir(parents=True)
    (real / "keep.txt").write_text("mine")
    res = _run_install(target)
    assert (real / "keep.txt").exists()  # untouched
    assert "skipping" in (res.stdout + res.stderr).lower()
