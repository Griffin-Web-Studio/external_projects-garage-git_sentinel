#!/bin/sh
# Generates release notes for a git-sentinel GitLab Release.
# Usage: gen-release-notes.sh <tag> <channel>
set -eu

TAG=$1
CHANNEL=$2

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMPLATE="$SCRIPT_DIR/.gitlab/release_notes_templates/default.md"

sed \
  -e "s|{{TAG}}|$TAG|g" \
  -e "s|{{CHANNEL}}|$CHANNEL|g" \
  "$TEMPLATE"
