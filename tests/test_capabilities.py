# tests/test_capabilities.py
import shutil
import subprocess

import pytest


def _help(binary: str) -> str:
    return subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=30).stdout


@pytest.mark.skipif(shutil.which("reddit-cli") is None, reason="reddit-cli not installed")
def test_reddit_cli_has_search_and_comments():
    out = _help("reddit-cli")
    assert "search" in out and "comments" in out


@pytest.mark.skipif(shutil.which("bird") is None, reason="bird not installed")
def test_bird_has_search_subcommand():
    out = _help("bird")
    assert "search" in out


def test_claude_in_chrome_capability_probe_documented():
    """Capability smoke for the Phase 2 browser tier.

    We can't pair Chrome in a headless test, so this DOCUMENTS the probe: if the `claude`
    CLI is present and lists a chrome MCP server, assert it; otherwise skip (the tier is
    capability-gated). Never hard-fails on environment.
    """
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not installed")
    try:
        out = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=30
        )
    except (subprocess.TimeoutExpired, OSError):
        pytest.skip("`claude mcp list` not runnable here")
    listing = (out.stdout + out.stderr).lower()
    if "chrome" not in listing:
        pytest.skip("claude-in-chrome MCP not configured in this environment")
    assert "chrome" in listing
