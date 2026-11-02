# tests/test_capabilities.py
import shutil
import subprocess

import pytest


def _help(binary: str) -> str:
    return subprocess.run(
        [binary, "--help"], capture_output=True, text=True, timeout=30, check=False
    ).stdout


@pytest.mark.skipif(shutil.which("reddit-cli") is None, reason="reddit-cli not installed")
def test_reddit_cli_has_search_and_comments():
    out = _help("reddit-cli")
    assert "search" in out and "comments" in out


@pytest.mark.skipif(shutil.which("bird") is None, reason="bird not installed")
def test_bird_has_search_subcommand():
    out = _help("bird")
    assert "search" in out


@pytest.mark.skipif(shutil.which("maps-cli") is None, reason="maps-cli not installed")
def test_maps_cli_has_places_and_doctor():
    out = _help("maps-cli")
    assert "places" in out and "doctor" in out


@pytest.mark.skipif(shutil.which("vidread") is None, reason="vidread not installed")
def test_vidread_has_json_and_comments():
    out = _help("vidread")
    assert "--json" in out and "--comments" in out
