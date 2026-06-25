#!/usr/bin/env bash
# local-run.sh - build, install, and force-launch git-sentinel locally.
# Run from any directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Building..."
"$SCRIPT_DIR/build.sh"

echo "==> Installing..."
"$PROJECT_ROOT/dist/git-sentinel"

echo "==> Running..."
"$HOME/.local/bin/git-sentinel" --force
