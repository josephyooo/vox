# Vox

Cross-source recommendation & sentiment for anything — "best running shoes", "how good is the new
Claude model", "best ramen near Union Square". Vox searches Reddit + X + the web, cross-checks
them, and returns a ranked, **cited**, honestly-hedged answer. Read-only; runs on your Claude
subscription (no API).

## Install
```bash
./install.sh                 # symlinks skills/* into ~/.claude/skills/
```
The web tier (`WebSearch`/`WebFetch`) is built in. The other tiers are **capability-gated** —
each needs its CLI/tool on PATH: Reddit→`reddit-cli`, X→`bird`, Maps→`maps-cli`(+`gosom`),
Video→`ffmpeg` + `vidread` (or legacy `mw`+`tiktok-cli`), browser/logistics→the `claude-in-chrome`
MCP. Vox runs with whatever is present and degrades honestly.

**Setting up on a fresh machine?** This is a multi-repo system (sibling CLIs + external tools).
Follow **[SETUP.md](SETUP.md)** end-to-end — it covers cloning the public repos, the sibling
installs, external tools, MCP setup, credential re-auth, and verification.

## Use
In Claude Code: `/vox best running shoes for flat feet under $150`

## How it works
A `vox` orchestrator skill probes sources, proposes a rubric, fans out one subagent per relevant
source — `vox-reddit`, `vox-x`, `vox-web`, plus the `vox-maps` (places), `vox-browser`
(logistics/place-data fallback), and `vox-video` (TikTok/YouTube videos) tiers when the query needs
them — corroborates across sources (2+ to promote), resolves or discloses conflicts, and renders
one of two output skeletons (ranked finalists, or a no-finalist sentiment read) with per-figure
confidence. See `docs/superpowers/specs/2026-06-07-vox-design.md` and the mined `docs/vox-recipe.md`.

## Dev
```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
.venv/bin/python tools/validate_skills.py skills
```

## Roadmap
Shipped since v1: the browser tier (`vox-browser`, Maps/logistics via Claude in Chrome), the
gosom-backed places tier (`vox-maps`), the TikTok/YouTube video analyzer (`vox-video`, with an
optional `agy`/Gemini cross-check), and Firecrawl as a metered final-resort scrape rung, after Chrome, in
`vox-web`. Deferred: Instagram video ingest, a `vox "..."` shell wrapper, and private/own-collection
TikTok access.
