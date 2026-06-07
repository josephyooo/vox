# Vox

Cross-source recommendation & sentiment for anything — "best running shoes", "how good is the new
Claude model", "best ramen near Union Square". Vox searches Reddit + X + the web, cross-checks
them, and returns a ranked, **cited**, honestly-hedged answer. Read-only; runs on your Claude
subscription (no API).

## Install
```bash
./install.sh                 # symlinks skills/* into ~/.claude/skills/
```
Requires `reddit-cli` and `bird` on PATH for those sources; `WebSearch`/`WebFetch` are built in.

## Use
In Claude Code: `/vox best running shoes for flat feet under $150`

## How it works
A `vox` orchestrator skill probes sources, proposes a rubric, fans out one subagent per source
(`vox-reddit`, `vox-x`, `vox-web`), corroborates across sources (2+ to promote), and renders a
fixed template with per-figure confidence. See `docs/superpowers/specs/2026-06-07-vox-design.md`
and the mined `docs/vox-recipe.md`.

## Dev
```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```

## Roadmap
Phase 2: browser tier (`vox-google`, Maps via Claude-in-Chrome). Later: TikTok/Instagram
(capability-gated), a `vox "..."` shell wrapper over `claude-session-driver`, video.
