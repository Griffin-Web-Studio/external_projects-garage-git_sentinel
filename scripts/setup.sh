#!/usr/bin/env bash

# git-sentinel setup.sh - prepares the local dev environment. Run once after
# cloning, from the project root directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE_SETTINGS="$SCRIPT_DIR/settings.example.ini"
LOCAL_SETTINGS="$SCRIPT_DIR/settings.ini"

# ───────────────────────────────────────────────────────| Environment Setup |──

# Install dependency managers
pipx install uv

# install all dependencies
uv sync --all-extras

# Activate virtual python environment
source .venv/bin/activate

# ────────────────────────────────────────────────────────| Pre-commit hooks |──

if ! command -v pre-commit &>/dev/null; then
  echo "ERROR: pre-commit is not installed." >&2
  echo "       Install it with: pip install pre-commit or look for errors" >&2
  echo "       above as UV should have been already installed and" >&2
  echo "       activated, which means there's another issue." >&2
  exit 1 # early fail - no pre-commit hook
fi

echo "Installing pre-commit hooks..."
(cd "$SCRIPT_DIR" && pre-commit install)
(cd "$SCRIPT_DIR" && pre-commit install --hook-type commit-msg)

# ──────────────────────────────────────────────────────────| Local settings |──

if [ ! -f "$EXAMPLE_SETTINGS" ]; then
  echo "ERROR: $EXAMPLE_SETTINGS not found." >&2
  exit 1
fi

if [ -f "$LOCAL_SETTINGS" ]; then
  echo "Skipping settings.ini - already exists (delete it to regenerate)"
else
  cp "$EXAMPLE_SETTINGS" "$LOCAL_SETTINGS"
  echo "Created settings.ini from settings.example.ini"
fi

echo ""
echo "Dev environment ready."
