# Vox — full setup on a fresh machine

Vox is a **multi-repo system**: the `vox` orchestrator + its skills (this repo), plus sibling
CLIs and external tools that back each source tier. This guide takes a fresh macOS laptop from
nothing to a working `/vox`. It is written to be followed top-to-bottom (by a human or by another
Claude). Every tier is **capability-gated** — Vox runs with whatever is installed and degrades
honestly when a tool is missing, so you can stop after the tiers you need.

> Quick mental model: `vox` (this repo) is prose skills, no binary. It fans out to source
> subagents, each of which shells out to one CLI or MCP. Install the CLIs/tools for the tiers you
> want, symlink the skills, re-establish the per-tool credentials, then verify.

---

## 0. Prerequisites

- **macOS** (the video and browser tiers are macOS-oriented: MacWhisper, Claude in Chrome).
- **Homebrew**, **Python 3.14** (the repo venvs are built on 3.14.5), **Node** (for `bird`),
  **Go** (for `gosom`). Install as needed: `brew install python go node gh`.
- **GitHub access — the first-party repos are PRIVATE** (`vox`, `tiktok-api-cli`, `maps-cli`;
  `reddit-cli` is third-party via Homebrew, see §3). Authenticate before cloning:

  ```bash
  gh auth login          # HTTPS, or add your SSH key to GitHub instead
  ```

  (If you later make the repos public, this step becomes unnecessary.)

---

## 1. Clone the first-party repos

All under `github.com/josephyooo`:

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/josephyooo/vox.git
git clone https://github.com/josephyooo/maps-cli.git
git clone https://github.com/josephyooo/tiktok-api-cli.git
```

**Repo → binary name map** (the one non-obvious mapping — the skills call the *binary* name):

| Repo | Binary on PATH | Tier it backs |
| --- | --- | --- |
| `vox` | *(skills only, no binary)* | orchestrator |
| `maps-cli` | `maps-cli` | Maps / places (`vox-maps`) |
| `tiktok-api-cli` | **`tiktok-cli`** | Video (`vox-video`) |

---

## 2. Install the first-party Python CLIs

Each is an editable install in its own venv; then symlink the console script onto PATH, because
the skills invoke the bare names `maps-cli` / `tiktok-cli`.

```bash
# maps-cli (Maps/places tier)
cd ~/projects/maps-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
ln -sf "$PWD/.venv/bin/maps-cli" ~/.local/bin/maps-cli

# tiktok-cli (Video tier) — repo is tiktok-api-cli, BINARY is tiktok-cli
cd ~/projects/tiktok-api-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m playwright install chromium   # browser binary; live cmds fail exit 4 without it
ln -sf "$PWD/.venv/bin/tiktok-cli" ~/.local/bin/tiktok-cli

# vox dev tooling (skills are prose; the venv only runs the gate)
cd ~/projects/vox
python3 -m venv .venv && .venv/bin/pip install pytest ruff
```

Ensure `~/.local/bin` is on your PATH. To pin the **exact** known-good dependency set instead of
resolving latest, each Python repo ships a `requirements-lock.txt` (captured on Python 3.14.5):

```bash
.venv/bin/pip install -r requirements-lock.txt && .venv/bin/pip install -e . --no-deps
```

---

## 3. Install the external tools

Install the tools for the tiers you want. Each row is independent; Vox degrades honestly when one
is absent.

| Tool | Tier | Install | Notes |
| --- | --- | --- | --- |
| `reddit-cli` | Reddit (`vox-reddit`) | `brew install alceal/tap/reddit-cli` | third-party (alceal); tested v0.2.2 |
| `bird` | X / Twitter (`vox-x`) | `npm install -g @steipete/bird` | needs Node; tested v0.8.0 |
| `ffmpeg` | Video (`vox-video`) | `brew install ffmpeg` | frame extraction |
| `mw` (MacWhisper) | Video (`vox-video`) | install **MacWhisper** (goodsnooze) → provides `mw` at `/usr/local/bin/mw` | **Pro license** + the **parakeet-v3** model the tier uses |
| `gosom` | Maps (`vox-maps`, via `maps-cli`) | `brew install go && go install github.com/gosom/google-maps-scraper@latest` → `~/go/bin/` | first lookup downloads playwright Chromium |
| `agy` *(optional)* | Video soft cross-check | **user-supplied** — a native binary; no in-repo source | OPTIONAL; only `vox-video`; soft-gated (records "agy unavailable" and proceeds if absent). Needs Gemini access. |

Notes:
- **`agy`** is the one tool with no reproducible source in this system. On the source machine it is
  a ~140 MB native binary at `/opt/homebrew/bin/agy`; it is *not* a Homebrew formula and is not
  checked into any repo. It is **optional** — it only sharpens `vox-video` entity spelling and is
  non-halting when missing. Supply your own `agy` build (Gemini-backed) if you want the cross-check.
- **Pinning external versions:** the skills call specific sub-commands/flags. If a newer `gosom` /
  `bird` / `mw` changes its surface and a tier breaks, pin to the tested version above (e.g.
  `go install github.com/gosom/google-maps-scraper@<commit>` instead of `@latest`).

---

## 4. MCP servers (optional tiers)

Two tiers ride on MCP servers rather than CLIs. Both are capability-gated — skills probe for them
and skip cleanly when absent.

- **`claude-in-chrome`** (browser/logistics tier, `vox-browser`) — provided by the **Claude in
  Chrome** browser extension + its MCP, driving your real Chrome. Set it up per Anthropic's Claude
  in Chrome instructions; the first `vox-browser` run pairs a browser. Without it, the browser tier
  is unavailable (Vox halts only when a place/logistics query genuinely needs it *and* `gosom` is
  also down — otherwise it just proceeds).
- **`firecrawl`** (optional anti-bot rung 5 for `vox-web`) — register user-scope and supply a key:

  ```bash
  export FIRECRAWL_API_KEY=<your-key>     # free tier, no credit card; keep it in your shell rc
  claude mcp add -s user firecrawl -e 'FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}' -- npx -y firecrawl-mcp
  ```

  The config stores only the `${FIRECRAWL_API_KEY}` *reference*, never the literal key. Restart
  Claude Code from a shell where the key is exported. Absent → `vox-web` skips the rung; never a halt.

---

## 5. Install the skills

```bash
cd ~/projects/vox
./install.sh            # symlinks skills/* into ~/.claude/skills/
```

Idempotent; replaces stale symlinks. Override the target dir with `$VOX_SKILLS_TARGET`. Because the
links point **into** `vox/skills/`, the skill source stays versioned in this repo — don't move or
delete the repo or all skills break.

---

## 6. Re-establish credentials

Nothing below is in git (by design) — re-create each on the new machine. Only do the tiers you
installed.

- [ ] **TikTok `ms_token`** → `tiktok-cli auth` (or `tiktok-cli auth --login` for a higher-trust
  token). Saves to `~/.config/tiktok-cli/token`. See `tiktok-api-cli/README.md`.
- [ ] **X / `bird`** → `bird check`; follow its auth flow if it reports unauthenticated.
- [ ] **Reddit** → run any `reddit-cli` command once and complete its auth if prompted.
- [ ] **MacWhisper (`mw`)** → activate the Pro license in the app and download the **parakeet-v3** model.
- [ ] **`agy`** *(optional)* → ensure your Gemini access is configured for the binary.
- [ ] **Chrome pairing** for `claude-in-chrome` → completed on first `vox-browser` run.
- [ ] **Firecrawl** *(optional)* → export `FIRECRAWL_API_KEY` + the `claude mcp add` in §4.

---

## 7. Verify

Run each probe for the tiers you set up; then the vox gate; then a live smoke query.

```bash
maps-cli doctor                 # gosom binary + chromium            (exit 0)
tiktok-cli doctor               # TikTokApi + chromium + ms_token    (exit 0)
bird check                      # X auth OK
reddit-cli --help               # present
which agy mw ffmpeg google-maps-scraper

# vox dev gate (from ~/projects/vox):
.venv/bin/python tools/validate_skills.py skills   # prints [ok] per skill
.venv/bin/python -m pytest
.venv/bin/python -m ruff check tools tests eval
```

Then, in Claude Code: `/vox best ramen near Union Square` (a places query exercises routing →
`vox-maps`/`vox-web`/`vox-reddit`). A clean ranked, cited answer means the core is working.

---

## Source tier reference

| Tier | Skill | Backed by | Hard prereq? |
| --- | --- | --- | --- |
| Web | `vox-web` | WebSearch / WebFetch (built into Claude Code) + optional `firecrawl` MCP | always available |
| Reddit | `vox-reddit` | `reddit-cli` | for the Reddit tier |
| X | `vox-x` | `bird` | for the X tier |
| Maps / places | `vox-maps` | `maps-cli` → `gosom` | for the places tier (or fall back to browser) |
| Browser / logistics | `vox-browser` | `claude-in-chrome` MCP (real Chrome) | for logistics + place-data fallback |
| Video | `vox-video` | `tiktok-cli` + `mw` + `ffmpeg` (+ optional `agy`) | all three hard-required for the video tier |
