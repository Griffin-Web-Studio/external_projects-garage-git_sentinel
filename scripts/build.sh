#!/usr/bin/env bash
# git-sentinel build.sh - builds the PyInstaller binary into dist/git-sentinel
# Run from the project root directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv &>/dev/null; then
  echo "ERROR: uv is not installed." >&2
  echo "       Install it from: https://docs.astral.sh/uv/getting-started/installation/" >&2
  echo "       or reopen this project in devcontainer where it will be" >&2
  echo "       installed automatically, along with other dependencies." >&2
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
  echo "ERROR: pyproject.toml not found in $SCRIPT_DIR" >&2
  exit 1
fi

echo "Syncing build dependencies..."
(cd "$SCRIPT_DIR" && uv sync --group dev)

echo "Building binary (this may take a minute)..."
(cd "$SCRIPT_DIR" && uv run pyinstaller \
  --onefile \
  --name git-sentinel \
  --distpath dist \
  --workpath build \
  --specpath build \
  --add-data "$SCRIPT_DIR/src/data/git-sentinel.desktop:data" \
  --add-data "$SCRIPT_DIR/src/data/git-sentinel.svg:data" \
  git-sentinel)

if [ ! -f "$SCRIPT_DIR/dist/git-sentinel" ]; then
  echo "ERROR: build failed - dist/git-sentinel not found" >&2
  exit 1
fi

echo "Build complete → $SCRIPT_DIR/dist/git-sentinel"
