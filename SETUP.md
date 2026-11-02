# Vox — full setup on a fresh machine

Vox is a **multi-repo system**: the `vox` orchestrator + its skills (this repo), plus sibling
CLIs and external tools that back each source tier. This guide takes a fresh machine from
nothing to a working `/vox`. It is written to be followed top-to-bottom (by a human or by another
Claude). Every tier is **capability-gated** — Vox runs with whatever is installed and degrades
honestly when a tool is missing, so you can stop after the tiers you need.

> Quick mental model: `vox` (this repo) is prose skills, no binary. It fans out to source
> subagents, each of which shells out to one CLI or MCP. Install the CLIs/tools for the tiers you
> want, symlink the skills, re-establish the per-tool credentials, then verify.

---

## 0. Prerequisites

- **macOS or Linux.** The legacy `mw` video backend is Mac-only; `vidread` runs anywhere; the browser
  tier needs Chrome + Claude in Chrome.
- **An Anthropic Claude subscription** — Vox is a set of Claude Code skills; every tier runs inside
  Claude Code on your subscription. There is no separate Vox API key.
- **Homebrew**, **Python ≥3.10** (the repo venvs are tested/pinned on 3.14.5), **Node** (for `bird`),
  **Go** (for `gosom`). Install as needed: `brew install python go node gh`.
- **GitHub access — the first-party repos are PUBLIC** (`vox`, `maps-cli`, `tiktok-api-cli`,
  `amazon-cli`; `reddit-cli` is third-party via Homebrew, see §3). No authentication is needed to
  clone them — the `git clone` commands in §1 work anonymously over HTTPS. You only need GitHub auth
  (`gh auth login`, an SSH key, or `GH_TOKEN`) if you intend to **push** changes back.

---

## 1. Clone the first-party repos

All under `github.com/josephyooo` — public, so these clone without authentication:

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/josephyooo/vox.git
git clone https://github.com/josephyooo/maps-cli.git
git clone https://github.com/josephyooo/tiktok-api-cli.git
git clone https://github.com/josephyooo/amazon-cli.git
```

Prefer SSH? Swap each URL for `git@github.com:josephyooo/<repo>.git`.

**Repo → binary name map** (the one non-obvious mapping — the skills call the *binary* name):

| Repo | Binary on PATH | Tier it backs |
| --- | --- | --- |
| `vox` | *(skills only, no binary)* | orchestrator |
| `maps-cli` | `maps-cli` | Maps / places (`vox-maps`) |
| `tiktok-api-cli` | **`tiktok-cli`** | Video, legacy backend; also TikTok comments/collections (`vox-video`) |
| `amazon-cli` | `amazon-cli` | Product & price-history (`vox-amazon`) |

---

## 2. Install the first-party Python CLIs

Each is an editable install in its own venv; then symlink the console script onto PATH, because
the skills invoke the bare names `maps-cli` / `tiktok-cli`.

**First, create the user-local bin dir and put it on your PATH** — it does not exist by default on
macOS, and the symlinks below (and all later verification) fail without it:

```bash
mkdir -p ~/.local/bin
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;                                   # already on PATH
  *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc   # use ~/.bashrc if you use bash
     export PATH="$HOME/.local/bin:$PATH" ;;                   # and for this shell, now
esac
```

```bash
# maps-cli (Maps/places tier)
cd ~/projects/maps-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
ln -sf "$PWD/.venv/bin/maps-cli" ~/.local/bin/maps-cli

# tiktok-cli (Video, legacy backend; also TikTok comments/collections)
# repo is tiktok-api-cli, BINARY is tiktok-cli
cd ~/projects/tiktok-api-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m playwright install chromium   # browser binary; live cmds fail exit 4 without it
ln -sf "$PWD/.venv/bin/tiktok-cli" ~/.local/bin/tiktok-cli

# amazon-cli (Product & price-history tier)
cd ~/projects/amazon-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
ln -sf "$PWD/.venv/bin/amazon-cli" ~/.local/bin/amazon-cli

# vox dev tooling (skills are prose; the venv only runs the gate)
cd ~/projects/vox
python3 -m venv .venv && .venv/bin/pip install -r requirements-lock.txt
```

> **Pin the exact known-good deps (recommended for a faithful clone).** Instead of resolving latest,
> the two CLIs (`maps-cli`, `tiktok-api-cli`) ship a `requirements-lock.txt` captured on Python
> 3.14.5 — use it *in place of* the `pip install -e ".[dev]"` line above:
>
> ```bash
> .venv/bin/pip install -r requirements-lock.txt && .venv/bin/pip install -e . --no-deps
> ```
>
> (`vox` ships one too, pinning just its gate tools — `pytest`/`ruff`.)

---

## 3. Install the external tools

Install the tools for the tiers you want. Each row is independent; Vox degrades honestly when one
is absent.

| Tool | Tier | Install | Notes |
| --- | --- | --- | --- |
| `reddit-cli` | Reddit (`vox-reddit`) | `brew install alceal/tap/reddit-cli` | third-party (alceal); tested v0.2.2 |
| `bird` | X / Twitter (`vox-x`) | `npm install -g @steipete/bird` | needs Node; tested v0.8.0 |
| `ffmpeg` | Video (`vox-video`) | `brew install ffmpeg` | frame extraction |
| `mw` (MacWhisper) | Video (legacy Mac backend) | **[HUMAN-ONLY]** install the **MacWhisper** GUI app (by goodsnooze) → provides `mw` at `/usr/local/bin/mw` | needs a **Pro license** (one-time purchase, activated in-app) + the **parakeet-v3** model (download from the app's Models UI). |
| `vidread` | Video (`vox-video`, preferred backend) | sibling repo `vidread` (no published remote yet): `conda env create -f environment.yml && conda activate vidread && pip install -e .`, then symlink `vidread` onto PATH | needs `ffmpeg` + `yt-dlp`; TikTok + YouTube |
| `gosom` | Maps (`vox-maps`, via `maps-cli`) | `brew install go && go install github.com/gosom/google-maps-scraper@latest` → `~/go/bin/` | installs to `~/go/bin/` — NOT on PATH by default; `maps-cli` auto-discovers it there (override with `$MAPS_CLI_GOSOM_BIN`). First lookup downloads playwright Chromium. |
| `agy` *(optional)* | Video soft cross-check | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` (Google Antigravity CLI) → `~/.local/bin/agy` | OPTIONAL; only `vox-video`; soft-gated (records "agy unavailable" and proceeds if absent). Needs Gemini access. |

Notes:
- **`agy`** is optional; it only sharpens `vox-video` entity spelling and is non-halting when
  missing or not signed in.
- **Pinning external versions:** the skills call specific sub-commands/flags. If a newer `gosom` /
  `bird` / `mw` changes its surface and a tier breaks, pin to the tested version above (e.g.
  `go install github.com/gosom/google-maps-scraper@<commit>` instead of `@latest`).

---

## 4. MCP servers (optional tiers)

Two tiers ride on MCP servers rather than CLIs. Both are capability-gated — skills probe for them
and skip cleanly when absent.

- **`claude-in-chrome`** (browser/logistics tier, `vox-browser`) — provided by the **Claude in
  Chrome** browser extension + its MCP, driving your real Chrome. **[HUMAN-ONLY]** install + set it
  up per Anthropic's [Claude in Chrome instructions](https://code.claude.com/docs/en/chrome); pairing
  happens automatically on the first `vox-browser` run (no pre-pairing — just have the extension
  installed and running). Without it, the browser tier is unavailable (Vox halts only when a
  logistics query needs it, or a place query needs it *and* `gosom` is also down — otherwise it just proceeds).
- **`firecrawl`** (optional, metered final-resort anti-bot rung 7 for `vox-web`) — pinned install + a launcher that loads
  the key from a file:

  ```bash
  npm i -g firecrawl-mcp@3.22.4   # pinned; never `npx -y` (floats the version)
  mkdir -p ~/.config/vox
  (umask 077; echo 'FIRECRAWL_API_KEY=<your-key>' > ~/.config/vox/firecrawl.env)   # 0600
  # launcher bakes in the absolute binary path: a service PATH may lack the npm bin
  printf '#!/usr/bin/env bash\nset -a; . ~/.config/vox/firecrawl.env; set +a\nexec %s\n' \
    "$(command -v firecrawl-mcp)" > ~/.local/bin/firecrawl-mcp-launch
  chmod 700 ~/.local/bin/firecrawl-mcp-launch
  claude mcp add -s user firecrawl -- ~/.local/bin/firecrawl-mcp-launch
  ```

  Firecrawl is metered and may be billed to your card; keep auto-recharge off. `vox-web` uses it only
  after Chrome has failed or is unavailable. Absent → `vox-web` skips the rung; never a halt.

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
installed. Steps marked **[HUMAN-ONLY]** need an interactive browser/GUI and cannot be done
unattended by an agent.

- [ ] **GitHub** (optional — the repos are public, so cloning needs no auth; only needed to *push*)
  → `gh auth login` (**[HUMAN-ONLY]**, or the `GH_TOKEN` / SSH path in §0). Stored in
  `~/.config/gh/hosts.yml` (token) or `~/.ssh/` (key).
- [ ] **TikTok `ms_token`** → `tiktok-cli auth` (**[HUMAN-ONLY]** — opens a browser to harvest the
  cookie; or `tiktok-cli auth --login` for a higher-trust token). Saves to
  `~/.config/tiktok-cli/token` (chmod 600). See `tiktok-api-cli/README.md`.
- [ ] **X / `bird`** → `bird check`, then **[HUMAN-ONLY]** complete its auth flow if unauthenticated.
  `bird` reads your browser cookies — it keeps no on-disk secret (only config under `~/.config/bird/`).
- [ ] **Reddit** → run any `reddit-cli` command once and **[HUMAN-ONLY]** complete its auth if
  prompted. Credentials are stored at `~/.config/reddit-cli/.env`.
- [ ] **MacWhisper (`mw`)** → **[HUMAN-ONLY]** activate the Pro license in the app and download the
  **parakeet-v3** model from its Models UI (both live inside the app).
- [ ] **`agy`** *(optional)* → run `agy` once with no args to complete Google sign-in.
- [ ] **Chrome pairing** for `claude-in-chrome` → **[HUMAN-ONLY]**, completed on first `vox-browser` run.
- [ ] **Firecrawl** *(optional)* → key in `~/.config/vox/firecrawl.env` (0600) + the launcher
  registration in §4.

---

## 7. Verify

Run each probe for the tiers you set up; then the vox gate; then a live smoke query.

```bash
maps-cli doctor                 # gosom binary + chromium            (exit 0)
tiktok-cli doctor               # TikTokApi + chromium + ms_token    (exit 0)
bird check                      # X auth OK
reddit-cli --help               # present
vidread --help                  # video ingest backend present
which vidread yt-dlp mw ffmpeg agy   # tools that live on PATH (mw legacy, agy optional)
ls ~/go/bin/google-maps-scraper # gosom: maps-cli auto-discovers it here (not on PATH by default)

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
| Video | `vox-video` | `ffmpeg` + `vidread` (or legacy `tiktok-cli` + `mw`) (+ optional `agy`) | ffmpeg + one ingest backend |
