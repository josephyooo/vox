#!/usr/bin/env bash
# Symlink every Vox skill into the Claude Code skills directory.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${VOX_SKILLS_TARGET:-$HOME/.claude/skills}"
mkdir -p "$TARGET"

for src in "$REPO_DIR"/skills/*/; do
  name="$(basename "$src")"
  dest="$TARGET/$name"
  if [ -L "$dest" ]; then
    rm "$dest"                      # stale symlink — replace
  elif [ -e "$dest" ]; then
    echo "skipping $name: a real directory already exists at $dest" >&2
    continue
  fi
  ln -s "${src%/}" "$dest"
  echo "linked $name -> $dest"
done
